"""
=============================================================================
  CUAD + NORTHWIND CONTRACTS -> NEO4J GRAPH IMPORT
=============================================================================
  Sources:
    1. CUAD Original:    master_clauses.csv (510 contracts, 83 clause cols)
                         full_contract_pdf/ (199 PDFs, 22 categories)
    2. Northwind Synth:  northwind_contracts_index.csv (200 synthetic PDFs)
  
  Graph Schema (Nodes):
    (:Contract)        - A commercial agreement (CUAD original or Northwind)
    (:Party)           - A named party/company in a contract
    (:Clause)          - A specific legal clause extracted from a contract
    (:ClauseType)      - A category of clause (e.g. "Governing Law")
    (:ProductCategory) - Product/service category in the contract
    (:Employee)        - Sales rep who handled a Northwind order
    (:Shipper)         - Logistics company for a Northwind order
    (:Country)         - Governing jurisdiction / buyer country
    (:Dataset)         - Source dataset label (CUAD or Northwind)

  Relationships:
    (Contract)-[:HAS_PARTY]->(Party)
    (Contract)-[:HAS_CLAUSE]->(Clause)
    (Clause)-[:OF_TYPE]->(ClauseType)
    (Contract)-[:COVERS_CATEGORY]->(ProductCategory)
    (Contract)-[:HANDLED_BY]->(Employee)
    (Contract)-[:SHIPPED_BY]->(Shipper)
    (Contract)-[:GOVERNED_BY]->(Country)
    (Contract)-[:BELONGS_TO]->(Dataset)
    (Party)-[:LOCATED_IN]->(Country)
=============================================================================
"""

import sys
import os
import re
import pandas as pd
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CUAD_DIR      = os.path.join(BASE_DIR, "cuad", "CUAD_v1")
MASTER_CSV    = os.path.join(CUAD_DIR, "master_clauses.csv")
FULL_PDF_DIR  = os.path.join(CUAD_DIR, "full_contract_pdf")
NW_DIR        = os.path.join(CUAD_DIR, "northwind_contracts")
NW_INDEX_CSV  = os.path.join(NW_DIR, "northwind_contracts_index.csv")

# ─── Neo4j Config ─────────────────────────────────────────────────────────────
URI  = "bolt://localhost:7687"
AUTH = ("neo4j", "12345678")

# ─── CUAD clause columns (41 clause types) ───────────────────────────────────
CUAD_CLAUSE_COLS = [
    "Document Name", "Parties", "Agreement Date", "Effective Date",
    "Expiration Date", "Renewal Term", "Notice Period To Terminate Renewal",
    "Governing Law", "Most Favored Nation", "Competitive Restriction Exception",
    "Non-Compete", "Exclusivity", "No-Solicit Of Customers",
    "No-Solicit Of Employees", "Non-Disparagement", "Termination For Convenience",
    "Rofr/Rofo/Rofn", "Change Of Control", "Anti-Assignment",
    "Revenue/Profit Sharing", "Price Restrictions", "Minimum Commitment",
    "Volume Restriction", "Ip Ownership Assignment", "Joint Ip Ownership",
    "License Grant", "Non-Transferable License", "Affiliate License-Licensor",
    "Affiliate License-Licensee", "Unlimited/All-You-Can-Eat-License",
    "Irrevocable Or Perpetual License", "Source Code Escrow",
    "Post-Termination Services", "Audit Rights", "Uncapped Liability",
    "Cap On Liability", "Liquidated Damages", "Warranty Duration",
    "Insurance", "Covenant Not To Sue", "Third Party Beneficiary",
]

BATCH_SIZE = 200


# =============================================================================
# CYPHER QUERIES
# =============================================================================

INIT_CONSTRAINTS = [
    "CREATE CONSTRAINT contract_id_unique IF NOT EXISTS FOR (c:Contract) REQUIRE c.contract_id IS UNIQUE",
    "CREATE CONSTRAINT party_name_unique  IF NOT EXISTS FOR (p:Party)    REQUIRE p.name IS UNIQUE",
    "CREATE CONSTRAINT clausetype_unique  IF NOT EXISTS FOR (ct:ClauseType) REQUIRE ct.name IS UNIQUE",
    "CREATE CONSTRAINT prodcat_unique     IF NOT EXISTS FOR (pc:ProductCategory) REQUIRE pc.name IS UNIQUE",
    "CREATE CONSTRAINT employee_unique    IF NOT EXISTS FOR (e:Employee)  REQUIRE e.name IS UNIQUE",
    "CREATE CONSTRAINT shipper_unique     IF NOT EXISTS FOR (s:Shipper)   REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT country_unique     IF NOT EXISTS FOR (co:Country)  REQUIRE co.name IS UNIQUE",
    "CREATE CONSTRAINT dataset_unique     IF NOT EXISTS FOR (d:Dataset)   REQUIRE d.name IS UNIQUE",
]

INIT_INDEXES = [
    "CREATE INDEX contract_title_idx IF NOT EXISTS FOR (c:Contract) ON (c.title)",
    "CREATE INDEX contract_type_idx  IF NOT EXISTS FOR (c:Contract) ON (c.contract_type)",
    "CREATE INDEX contract_source_idx IF NOT EXISTS FOR (c:Contract) ON (c.source)",
]

CYPHER_CUAD_CONTRACT = """
UNWIND $batch AS row
MERGE (ds:Dataset {name: row.dataset_name})
MERGE (c:Contract {contract_id: row.contract_id})
SET c.title         = row.title,
    c.contract_type = row.contract_type,
    c.pdf_filename  = row.pdf_filename,
    c.pdf_path      = row.pdf_path,
    c.source        = 'CUAD',
    c.agreement_date = row.agreement_date,
    c.effective_date = row.effective_date,
    c.expiration_date = row.expiration_date,
    c.renewal_term  = row.renewal_term,
    c.termination_convenience = row.termination_convenience,
    c.anti_assignment = row.anti_assignment,
    c.governing_law = row.governing_law,
    c.audit_rights  = row.audit_rights,
    c.cap_on_liability = row.cap_on_liability,
    c.warranty_duration = row.warranty_duration,
    c.insurance     = row.insurance
MERGE (c)-[:BELONGS_TO]->(ds)
WITH c, row
WHERE row.governing_law <> ''
  AND row.governing_law <> 'No'
MERGE (co:Country {name: row.governing_law})
MERGE (c)-[:GOVERNED_BY]->(co)
"""

CYPHER_CUAD_PARTIES = """
UNWIND $batch AS row
MATCH (c:Contract {contract_id: row.contract_id})
UNWIND row.parties AS party_name
WITH c, party_name
WHERE party_name IS NOT NULL AND trim(party_name) <> ''
MERGE (p:Party {name: trim(party_name)})
MERGE (c)-[:HAS_PARTY]->(p)
"""

CYPHER_CUAD_CLAUSES = """
UNWIND $batch AS row
MATCH (c:Contract {contract_id: row.contract_id})
MERGE (ct:ClauseType {name: row.clause_type})
CREATE (cl:Clause {
    text: row.clause_text,
    clause_type: row.clause_type,
    has_provision: row.has_provision
})
CREATE (c)-[:HAS_CLAUSE]->(cl)
CREATE (cl)-[:OF_TYPE]->(ct)
"""

CYPHER_NW_CONTRACT = """
UNWIND $batch AS row
MERGE (ds:Dataset {name: 'Northwind-CUAD-Synthetic'})
MERGE (c:Contract {contract_id: row.contract_id})
SET c.title          = row.title,
    c.contract_no    = row.contract_no,
    c.contract_type  = row.contract_type,
    c.order_id       = row.order_id,
    c.pdf_filename   = row.filename,
    c.pdf_path       = row.pdf_path,
    c.source         = 'Northwind-Synthetic',
    c.agreement_date = row.agreement_date,
    c.expiration_date = row.expiration_date,
    c.order_status   = row.order_status,
    c.total_value    = row.total_value,
    c.unit_price     = row.unit_price,
    c.quantity       = row.quantity,
    c.discount       = row.discount
MERGE (c)-[:BELONGS_TO]->(ds)
WITH c, row

MERGE (seller:Party {name: row.seller_company})
SET seller.party_role = 'Seller/Vendor'
MERGE (c)-[:HAS_PARTY {role: 'Seller'}]->(seller)

MERGE (buyer:Party {name: row.buyer_company})
SET buyer.customer_id = row.buyer_id
MERGE (c)-[:HAS_PARTY {role: 'Buyer'}]->(buyer)

WITH c, row
WHERE row.buyer_country IS NOT NULL AND row.buyer_country <> ''
MERGE (co:Country {name: row.buyer_country})
MERGE (c)-[:GOVERNED_BY]->(co)
MERGE (buyer_node:Party {name: row.buyer_company})
MERGE (buyer_node)-[:LOCATED_IN]->(co)
"""

CYPHER_NW_CATEGORY = """
UNWIND $batch AS row
MATCH (c:Contract {contract_id: row.contract_id})
WITH c, row
WHERE row.category IS NOT NULL AND row.category <> ''
MERGE (pc:ProductCategory {name: row.category})
MERGE (c)-[:COVERS_CATEGORY]->(pc)
"""

CYPHER_NW_EMPLOYEE = """
UNWIND $batch AS row
MATCH (c:Contract {contract_id: row.contract_id})
WITH c, row
WHERE row.seller_rep IS NOT NULL AND row.seller_rep <> ''
MERGE (e:Employee {name: row.seller_rep})
MERGE (c)-[:HANDLED_BY]->(e)
"""

CYPHER_NW_SHIPPER = """
UNWIND $batch AS row
MATCH (c:Contract {contract_id: row.contract_id})
WITH c, row
WHERE row.shipper IS NOT NULL AND row.shipper <> ''
MERGE (s:Shipper {name: row.shipper})
MERGE (c)-[:SHIPPED_BY]->(s)
"""


# =============================================================================
# HELPER: Run batched Cypher
# =============================================================================
def run_batched(session, cypher, records, label="records", batch_size=BATCH_SIZE):
    total = len(records)
    if total == 0:
        print(f"    (no {label} to import)")
        return
    for i in range(0, total, batch_size):
        batch = records[i : i + batch_size]
        session.execute_write(lambda tx, b=batch: tx.run(cypher, batch=b))
        done = min(i + batch_size, total)
        pct  = "#" * int((done / total) * 20) + "." * (20 - int((done / total) * 20))
        print(f"\r    [{pct}] {done:4d}/{total}", end="", flush=True)
    print()


# =============================================================================
# SOURCE 1: Build CUAD records from master_clauses.csv
# =============================================================================
def build_cuad_records():
    print("\n[CUAD] Reading master_clauses.csv ...")
    df = pd.read_csv(MASTER_CSV).fillna("")
    print(f"  {len(df)} contracts loaded.")

    # Build PDF path lookup: walk full_contract_pdf to map filename -> path
    pdf_map = {}
    for root, _, files in os.walk(FULL_PDF_DIR):
        for f in files:
            if f.endswith(".pdf"):
                # Store relative subdir for category inference
                rel = os.path.relpath(root, FULL_PDF_DIR).replace("\\", "/")
                pdf_map[f] = {"full_path": os.path.join(root, f), "category": rel}

    contract_records = []
    party_records    = []
    clause_records   = []

    for _, row in df.iterrows():
        fname    = str(row.get("Filename", "")).strip()
        title    = str(row.get("Document Name-Answer", "")).strip()
        cid      = f"CUAD-{fname[:40]}"

        # Infer category from PDF path
        pdf_info = pdf_map.get(fname, {})
        cat_path = pdf_info.get("category", "")
        # Take the last meaningful segment
        parts = [p for p in cat_path.split("/") if p not in ("Part_I","Part_II","Part_III",".","..",
                 "Commercial Contracts (Part II-A)")]
        contract_type = parts[-1] if parts else "Unknown"

        contract_records.append({
            "contract_id"            : cid,
            "title"                  : title or fname,
            "contract_type"          : contract_type,
            "pdf_filename"           : fname,
            "pdf_path"               : pdf_info.get("full_path", ""),
            "dataset_name"           : "CUAD-Original",
            "agreement_date"         : str(row.get("Agreement Date-Answer", "")),
            "effective_date"         : str(row.get("Effective Date-Answer", "")),
            "expiration_date"        : str(row.get("Expiration Date-Answer", "")),
            "renewal_term"           : str(row.get("Renewal Term-Answer", "")),
            "termination_convenience": str(row.get("Termination For Convenience-Answer", "")),
            "anti_assignment"        : str(row.get("Anti-Assignment-Answer", "")),
            "governing_law"          : str(row.get("Governing Law-Answer", "")),
            "audit_rights"           : str(row.get("Audit Rights-Answer", "")),
            "cap_on_liability"       : str(row.get("Cap On Liability-Answer", "")),
            "warranty_duration"      : str(row.get("Warranty Duration-Answer", "")),
            "insurance"              : str(row.get("Insurance-Answer", "")),
        })

        # Parties
        parties_raw = str(row.get("Parties-Answer", ""))
        if parties_raw and parties_raw not in ("", "No"):
            # Split by semicolon or " and "
            parts_list = [p.strip() for p in re.split(r";| and ", parties_raw) if p.strip()]
            # Clean parenthetical nicknames
            cleaned = []
            for p in parts_list:
                clean = re.sub(r'\s*\(.*?\)', '', p).strip().strip('"').strip("'")
                if clean and len(clean) > 2:
                    cleaned.append(clean)
            if cleaned:
                party_records.append({
                    "contract_id": cid,
                    "parties"    : cleaned[:10],  # cap at 10 parties
                })

        # Clauses (only non-empty, non-No answers)
        for col in CUAD_CLAUSE_COLS:
            ans_col = f"{col}-Answer"
            if ans_col not in df.columns:
                continue
            text = str(row.get(ans_col, "")).strip()
            if text and text.lower() not in ("", "no", "nan"):
                clause_records.append({
                    "contract_id"  : cid,
                    "clause_type"  : col,
                    "clause_text"  : text[:1000],  # cap at 1000 chars
                    "has_provision": True,
                })

    print(f"  Prepared: {len(contract_records)} contracts, "
          f"{len(party_records)} party records, "
          f"{len(clause_records)} clauses.")
    return contract_records, party_records, clause_records


# =============================================================================
# SOURCE 2: Build Northwind records from index CSV
# =============================================================================
def build_northwind_records():
    print("\n[Northwind] Reading northwind_contracts_index.csv ...")
    df = pd.read_csv(NW_INDEX_CSV, encoding="utf-8-sig").fillna("")
    print(f"  {len(df)} Northwind contracts loaded.")

    contract_records = []
    category_records = []
    employee_records = []
    shipper_records  = []

    for _, row in df.iterrows():
        fname = str(row.get("filename", "")).strip()
        cno   = str(row.get("contract_no", "")).strip()
        cid   = f"NW-{cno}"
        title = (f"{row.get('contract_type','')} - "
                 f"{row.get('buyer_company','')} - "
                 f"{row.get('product_name','')}")

        rec = {
            "contract_id"  : cid,
            "title"        : title,
            "contract_no"  : cno,
            "contract_type": str(row.get("contract_type", "")),
            "order_id"     : str(row.get("order_id", "")),
            "filename"     : fname,
            "pdf_path"     : os.path.join(NW_DIR, fname),
            "agreement_date"  : str(row.get("agreement_date", "")),
            "expiration_date" : str(row.get("expiration_date", "")),
            "order_status"    : str(row.get("order_status", "")),
            "total_value"     : str(row.get("total_value", "")),
            "unit_price"      : str(row.get("unit_price", "")),
            "quantity"        : int(row.get("quantity", 0) or 0),
            "discount"        : str(row.get("discount", "")),
            "seller_company"  : str(row.get("seller_company", "")),
            "seller_rep"      : str(row.get("seller_rep", "")),
            "buyer_company"   : str(row.get("buyer_company", "")),
            "buyer_id"        : str(row.get("buyer_id", "")),
            "buyer_country"   : str(row.get("buyer_country", "")),
            "category"        : str(row.get("category", "")),
            "shipper"         : str(row.get("shipper", "")),
        }
        contract_records.append(rec)
        category_records.append({"contract_id": cid, "category": rec["category"]})
        employee_records.append({"contract_id": cid, "seller_rep": rec["seller_rep"]})
        shipper_records.append( {"contract_id": cid, "shipper": rec["shipper"]})

    print(f"  Prepared: {len(contract_records)} Northwind contracts.")
    return contract_records, category_records, employee_records, shipper_records


# =============================================================================
# MAIN IMPORT PIPELINE
# =============================================================================
def main():
    print("=" * 65)
    print("  CUAD + NORTHWIND -> NEO4J GRAPH IMPORT")
    print("=" * 65)

    # ── Build records ──────────────────────────────────────────────────────────
    cuad_contracts, cuad_parties, cuad_clauses = build_cuad_records()
    nw_contracts, nw_cats, nw_emps, nw_ships   = build_northwind_records()

    # ── Connect & Import ───────────────────────────────────────────────────────
    print(f"\n[Neo4j] Connecting to {URI} ...")
    try:
        with GraphDatabase.driver(URI, auth=AUTH) as driver:
            driver.verify_connectivity()
            print("  => Connected successfully!\n")

            with driver.session() as session:

                # ── 0. Schema: Constraints & Indexes ──────────────────────────
                print("[0/5] Creating constraints and indexes ...")
                for cypher in INIT_CONSTRAINTS + INIT_INDEXES:
                    try:
                        session.run(cypher)
                    except Exception:
                        pass  # Constraint may already exist
                print("  Done.\n")

                # ── 1. Import CUAD Contracts ───────────────────────────────────
                print(f"[1/5] Importing {len(cuad_contracts)} CUAD contracts ...")
                run_batched(session, CYPHER_CUAD_CONTRACT, cuad_contracts,
                            "CUAD contracts")

                # ── 2. Import CUAD Parties ─────────────────────────────────────
                print(f"[2/5] Importing parties for {len(cuad_parties)} CUAD contracts ...")
                run_batched(session, CYPHER_CUAD_PARTIES, cuad_parties,
                            "CUAD party records")

                # ── 3. Import CUAD Clauses ─────────────────────────────────────
                print(f"[3/5] Importing {len(cuad_clauses)} CUAD clauses ...")
                run_batched(session, CYPHER_CUAD_CLAUSES, cuad_clauses,
                            "CUAD clauses")

                # ── 4. Import Northwind Contracts + Relationships ──────────────
                print(f"[4/5] Importing {len(nw_contracts)} Northwind contracts ...")
                run_batched(session, CYPHER_NW_CONTRACT, nw_contracts,
                            "Northwind contracts")
                print("  -> ProductCategory relationships ...")
                run_batched(session, CYPHER_NW_CATEGORY, nw_cats,
                            "Northwind categories")
                print("  -> Employee (HANDLED_BY) relationships ...")
                run_batched(session, CYPHER_NW_EMPLOYEE, nw_emps,
                            "Northwind employees")
                print("  -> Shipper (SHIPPED_BY) relationships ...")
                run_batched(session, CYPHER_NW_SHIPPER, nw_ships,
                            "Northwind shippers")

                # ── 5. Summary stats ───────────────────────────────────────────
                print("\n[5/5] Graph summary ...")
                stats_queries = {
                    "Contracts"       : "MATCH (c:Contract)         RETURN count(c) AS n",
                    "Parties"         : "MATCH (p:Party)            RETURN count(p) AS n",
                    "Clauses"         : "MATCH (cl:Clause)          RETURN count(cl) AS n",
                    "ClauseTypes"     : "MATCH (ct:ClauseType)      RETURN count(ct) AS n",
                    "ProductCategories":"MATCH (pc:ProductCategory) RETURN count(pc) AS n",
                    "Employees"       : "MATCH (e:Employee)         RETURN count(e) AS n",
                    "Shippers"        : "MATCH (s:Shipper)          RETURN count(s) AS n",
                    "Countries"       : "MATCH (co:Country)         RETURN count(co) AS n",
                    "Datasets"        : "MATCH (d:Dataset)          RETURN count(d) AS n",
                    "Relationships"   : "MATCH ()-[r]->()           RETURN count(r) AS n",
                }
                print()
                print("  Neo4j Graph Statistics:")
                print("  " + "-" * 40)
                for label, q in stats_queries.items():
                    result = session.run(q).single()
                    n = result["n"] if result else 0
                    print(f"  {label:<22}: {n:>6,}")
                print("  " + "-" * 40)

        print("\n" + "=" * 65)
        print("  IMPORT COMPLETE")
        print(f"  CUAD Contracts  : {len(cuad_contracts)}")
        print(f"  CUAD Clauses    : {len(cuad_clauses)}")
        print(f"  Northwind PDFs  : {len(nw_contracts)}")
        print(f"  Total Contracts : {len(cuad_contracts) + len(nw_contracts)}")
        print("=" * 65)
        print()
        print("  Sample Cypher queries to explore the graph:")
        print()
        print("  // All contract types and counts")
        print("  MATCH (c:Contract) RETURN c.contract_type, count(c) ORDER BY count(c) DESC;")
        print()
        print("  // Northwind contracts with their buyers and categories")
        print("  MATCH (c:Contract {source:'Northwind-Synthetic'})-[:HAS_PARTY {role:'Buyer'}]->(p:Party)")
        print("  MATCH (c)-[:COVERS_CATEGORY]->(pc:ProductCategory)")
        print("  RETURN c.contract_no, p.name, pc.name, c.total_value LIMIT 10;")
        print()
        print("  // CUAD contracts by governing law")
        print("  MATCH (c:Contract {source:'CUAD'})-[:GOVERNED_BY]->(co:Country)")
        print("  RETURN co.name, count(c) AS contracts ORDER BY contracts DESC LIMIT 10;")
        print()
        print("  // Find all contracts involving a specific party")
        print("  MATCH (c:Contract)-[:HAS_PARTY]->(p:Party)")
        print("  WHERE p.name CONTAINS 'Northwind' RETURN c.title, c.contract_type;")

    except Exception as e:
        print(f"\n  ERROR: {e}")
        print("\n  Troubleshooting:")
        print("  1. Open Neo4j Desktop and start your DBMS.")
        print("  2. Ensure port 7687 is open (bolt://).")
        print("  3. Verify credentials: neo4j / 12345678")


if __name__ == "__main__":
    main()
