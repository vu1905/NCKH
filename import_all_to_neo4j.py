"""
=============================================================================
  COMPREHENSIVE NEO4J GRAPH IMPORT:
  1. CUAD Dataset: master_clauses.csv (510 contracts, 41 clause types) + full_contract_pdf/ (199 PDFs)
  2. AdventureWorks Dataset: adventureworks_merged_200.csv (200 orders, products, customers, locations, payments)
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
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
CUAD_DIR     = os.path.join(BASE_DIR, "cuad", "CUAD_v1")
MASTER_CSV   = os.path.join(CUAD_DIR, "master_clauses.csv")
FULL_PDF_DIR = os.path.join(CUAD_DIR, "full_contract_pdf")
AW_CSV       = os.path.join(BASE_DIR, "cuad", "adventureworks_merged_200.csv")

# ─── Neo4j Config ─────────────────────────────────────────────────────────────
URI  = "bolt://localhost:7687"
AUTH = ("neo4j", "12345678")

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

# ─── Constraints & Indexes ────────────────────────────────────────────────────
INIT_CONSTRAINTS = [
    "CREATE CONSTRAINT contract_id_unique IF NOT EXISTS FOR (c:Contract) REQUIRE c.contract_id IS UNIQUE",
    "CREATE CONSTRAINT party_name_unique  IF NOT EXISTS FOR (p:Party)    REQUIRE p.name IS UNIQUE",
    "CREATE CONSTRAINT product_id_unique  IF NOT EXISTS FOR (pr:Product)  REQUIRE pr.product_id IS UNIQUE",
    "CREATE CONSTRAINT clausetype_unique  IF NOT EXISTS FOR (ct:ClauseType) REQUIRE ct.name IS UNIQUE",
    "CREATE CONSTRAINT prodcat_unique     IF NOT EXISTS FOR (pc:ProductCategory) REQUIRE pc.name IS UNIQUE",
    "CREATE CONSTRAINT prodsubcat_unique  IF NOT EXISTS FOR (psc:ProductSubcategory) REQUIRE psc.name IS UNIQUE",
    "CREATE CONSTRAINT shipper_unique     IF NOT EXISTS FOR (s:Shipper)   REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT country_unique     IF NOT EXISTS FOR (co:Country)  REQUIRE co.name IS UNIQUE",
    "CREATE CONSTRAINT territory_unique   IF NOT EXISTS FOR (t:Territory) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT dataset_unique     IF NOT EXISTS FOR (d:Dataset)   REQUIRE d.name IS UNIQUE",
]

INIT_INDEXES = [
    "CREATE INDEX contract_title_idx IF NOT EXISTS FOR (c:Contract) ON (c.title)",
    "CREATE INDEX contract_type_idx  IF NOT EXISTS FOR (c:Contract) ON (c.contract_type)",
    "CREATE INDEX contract_source_idx IF NOT EXISTS FOR (c:Contract) ON (c.source)",
    "CREATE INDEX product_name_idx   IF NOT EXISTS FOR (pr:Product) ON (pr.name)",
]

# ─── Cypher Templates: CUAD ───────────────────────────────────────────────────
CYPHER_CUAD_CONTRACT = """
UNWIND $batch AS row
MERGE (ds:Dataset {name: 'CUAD-Original'})
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
WHERE row.governing_law <> '' AND row.governing_law <> 'No'
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

# ─── Cypher Templates: AdventureWorks ─────────────────────────────────────────
CYPHER_AW_ORDER = """
UNWIND $batch AS row
MERGE (ds:Dataset {name: 'AdventureWorks'})
MERGE (c:Contract {contract_id: row.contract_id})
SET c.title               = row.title,
    c.contract_type       = 'SALES ORDER AGREEMENT',
    c.sales_order_id      = row.sales_order_id,
    c.sales_order_number  = row.sales_order_number,
    c.purchase_order_num  = row.purchase_order_number,
    c.order_date          = row.order_date,
    c.due_date            = row.due_date,
    c.ship_date           = row.ship_date,
    c.order_status        = row.order_status,
    c.online_order        = row.online_order_flag,
    c.sub_total           = row.sub_total,
    c.tax_amt             = row.tax_amt,
    c.freight             = row.freight,
    c.total_due           = row.total_due,
    c.source              = 'AdventureWorks'
MERGE (c)-[:BELONGS_TO]->(ds)

WITH c, row
MERGE (cust:Party {name: row.customer_name})
SET cust.customer_id    = row.customer_id,
    cust.account_number = row.account_number,
    cust.party_role     = 'Buyer/Customer'
MERGE (c)-[:HAS_PARTY {role: 'Buyer'}]->(cust)

WITH c, cust, row
WHERE row.country_name IS NOT NULL AND row.country_name <> ''
MERGE (co:Country {name: row.country_name})
SET co.code = row.country_code
MERGE (c)-[:GOVERNED_BY]->(co)
MERGE (cust)-[:LOCATED_IN]->(co)
"""

CYPHER_AW_PRODUCT = """
UNWIND $batch AS row
MATCH (c:Contract {contract_id: row.contract_id})

MERGE (pr:Product {product_id: row.product_id})
SET pr.name           = row.product_name,
    pr.product_number = row.product_number,
    pr.color          = row.color,
    pr.size           = row.size,
    pr.weight         = row.weight,
    pr.standard_cost  = row.standard_cost,
    pr.list_price     = row.list_price

MERGE (c)-[rel:INCLUDES_PRODUCT]->(pr)
SET rel.order_qty          = row.order_qty,
    rel.unit_price         = row.unit_price,
    rel.unit_price_discount = row.unit_price_discount,
    rel.line_total         = row.line_total

WITH pr, row
WHERE row.category_name IS NOT NULL AND row.category_name <> ''
MERGE (pc:ProductCategory {name: row.category_name})

WITH pr, pc, row
WHERE row.subcategory_name IS NOT NULL AND row.subcategory_name <> ''
MERGE (psc:ProductSubcategory {name: row.subcategory_name})
MERGE (psc)-[:BELONGS_TO_CATEGORY]->(pc)
MERGE (pr)-[:BELONGS_TO_SUBCATEGORY]->(psc)
"""

CYPHER_AW_LOGISTICS = """
UNWIND $batch AS row
MATCH (c:Contract {contract_id: row.contract_id})

WITH c, row
WHERE row.ship_method IS NOT NULL AND row.ship_method <> ''
MERGE (s:Shipper {name: row.ship_method})
MERGE (c)-[:SHIPPED_BY]->(s)

WITH c, row
WHERE row.territory_name IS NOT NULL AND row.territory_name <> ''
MERGE (t:Territory {name: row.territory_name})
SET t.group = row.territory_group
MERGE (c)-[:IN_TERRITORY]->(t)
"""


# =============================================================================
# BATCH EXECUTOR
# =============================================================================
def run_batched(session, cypher, records, label="records", batch_size=BATCH_SIZE):
    total = len(records)
    if total == 0:
        return
    for i in range(0, total, batch_size):
        batch = records[i : i + batch_size]
        session.execute_write(lambda tx, b=batch: tx.run(cypher, batch=b))
        done = min(i + batch_size, total)
        pct  = "#" * int((done / total) * 20) + "." * (20 - int((done / total) * 20))
        print(f"\r    [{pct}] {done:4d}/{total}", end="", flush=True)
    print()


# =============================================================================
# DATA PREPARATION
# =============================================================================
def build_cuad_records():
    print("\n[1/2] Reading CUAD master_clauses.csv & full_contract_pdf ...")
    df = pd.read_csv(MASTER_CSV).fillna("")
    
    pdf_map = {}
    for root, _, files in os.walk(FULL_PDF_DIR):
        for f in files:
            if f.endswith(".pdf"):
                rel = os.path.relpath(root, FULL_PDF_DIR).replace("\\", "/")
                pdf_map[f] = {"full_path": os.path.join(root, f), "category": rel}
                
    contract_records = []
    party_records    = []
    clause_records   = []
    
    for _, row in df.iterrows():
        fname = str(row.get("Filename", "")).strip()
        title = str(row.get("Document Name-Answer", "")).strip()
        cid   = f"CUAD-{fname[:40]}"
        
        pdf_info = pdf_map.get(fname, {})
        cat_path = pdf_info.get("category", "")
        parts = [p for p in cat_path.split("/") if p not in ("Part_I","Part_II","Part_III",".","..","Commercial Contracts (Part II-A)")]
        contract_type = parts[-1] if parts else "Commercial Agreement"
        
        contract_records.append({
            "contract_id"            : cid,
            "title"                  : title or fname,
            "contract_type"          : contract_type,
            "pdf_filename"           : fname,
            "pdf_path"               : pdf_info.get("full_path", ""),
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
        
        parties_raw = str(row.get("Parties-Answer", ""))
        if parties_raw and parties_raw not in ("", "No"):
            parts_list = [p.strip() for p in re.split(r";| and ", parties_raw) if p.strip()]
            cleaned = []
            for p in parts_list:
                clean = re.sub(r'\s*\(.*?\)', '', p).strip().strip('"').strip("'")
                if clean and len(clean) > 2:
                    cleaned.append(clean)
            if cleaned:
                party_records.append({"contract_id": cid, "parties": cleaned[:10]})
                
        for col in CUAD_CLAUSE_COLS:
            ans_col = f"{col}-Answer"
            if ans_col not in df.columns:
                continue
            text = str(row.get(ans_col, "")).strip()
            if text and text.lower() not in ("", "no", "nan"):
                clause_records.append({
                    "contract_id"  : cid,
                    "clause_type"  : col,
                    "clause_text"  : text[:1000],
                    "has_provision": True,
                })
                
    print(f"      {len(contract_records)} CUAD contracts, {len(party_records)} party sets, {len(clause_records)} clauses.")
    return contract_records, party_records, clause_records


def build_adventureworks_records():
    print(f"\n[2/2] Reading AdventureWorks dataset from:\n      {AW_CSV}")
    df = pd.read_csv(AW_CSV, encoding="utf-8-sig").fillna("")
    print(f"      {len(df)} AdventureWorks records loaded.")
    
    order_records   = []
    product_records = []
    logistic_records= []
    
    for _, row in df.iterrows():
        so_id   = str(row.get("SalesOrderID", "")).strip()
        sod_id  = str(row.get("SalesOrderDetailID", "")).strip()
        so_num  = str(row.get("SalesOrderNumber", "")).strip()
        cid     = f"AW-{so_num}-{sod_id}"
        
        cust_name = str(row.get("CustomerDisplayName", "")).strip() or f"Customer {row.get('CustomerID')}"
        prod_name = str(row.get("ProductName", "")).strip()
        
        title = f"Sales Order {so_num} (Item #{sod_id}) - {cust_name} - {prod_name}"
        
        order_records.append({
            "contract_id"           : cid,
            "title"                 : title,
            "sales_order_id"        : so_id,
            "sales_order_number"    : so_num,
            "purchase_order_number" : str(row.get("PurchaseOrderNumber", "")),
            "order_date"            : str(row.get("OrderDate", "")),
            "due_date"              : str(row.get("DueDate", "")),
            "ship_date"             : str(row.get("ShipDate", "")),
            "order_status"          : str(row.get("OrderStatus", "")),
            "online_order_flag"     : bool(row.get("OnlineOrderFlag", False)),
            "sub_total"             : str(row.get("SubTotal", "")),
            "tax_amt"               : str(row.get("TaxAmt", "")),
            "freight"               : str(row.get("Freight", "")),
            "total_due"             : str(row.get("TotalDue", "")),
            "customer_id"           : str(row.get("CustomerID", "")),
            "customer_name"         : cust_name,
            "account_number"        : str(row.get("CustomerAccountNumber", "")),
            "country_name"          : str(row.get("CountryRegionName", "")),
            "country_code"          : str(row.get("CountryRegionCode", "")),
        })
        
        product_records.append({
            "contract_id"        : cid,
            "product_id"         : str(row.get("ProductID", "")),
            "product_name"       : prod_name,
            "product_number"     : str(row.get("ProductNumber", "")),
            "color"              : str(row.get("Color", "")),
            "size"               : str(row.get("Size", "")),
            "weight"             : str(row.get("Weight", "")),
            "standard_cost"      : str(row.get("StandardCost", "")),
            "list_price"         : str(row.get("ListPrice", "")),
            "order_qty"          : int(row.get("OrderQty", 1) or 1),
            "unit_price"         : str(row.get("UnitPrice", "")),
            "unit_price_discount": str(row.get("UnitPriceDiscount", "")),
            "line_total"         : str(row.get("LineTotal", "")),
            "category_name"      : str(row.get("ProductCategoryName", "")),
            "subcategory_name"   : str(row.get("ProductSubcategoryName", "")),
        })
        
        logistic_records.append({
            "contract_id"     : cid,
            "ship_method"     : str(row.get("ShipMethodName", "")),
            "territory_name"  : str(row.get("TerritoryName", "")),
            "territory_group" : str(row.get("TerritoryGroup", "")),
        })
        
    return order_records, product_records, logistic_records


# =============================================================================
# MAIN PIPELINE
# =============================================================================
def main():
    print("=" * 65)
    print("  NEO4J GRAPH IMPORT: CUAD + ADVENTUREWORKS")
    print("=" * 65)
    
    cuad_contracts, cuad_parties, cuad_clauses = build_cuad_records()
    aw_orders, aw_products, aw_logistics        = build_adventureworks_records()
    
    print(f"\n[Neo4j] Connecting to {URI} ...")
    try:
        with GraphDatabase.driver(URI, auth=AUTH) as driver:
            driver.verify_connectivity()
            print("  => Connected successfully!\n")
            
            with driver.session() as session:
                print("--- [1/4] Setting Constraints and Indexes ---")
                for c in INIT_CONSTRAINTS + INIT_INDEXES:
                    try:
                        session.run(c)
                    except Exception:
                        pass
                print("    Done.\n")
                
                print("--- [2/4] Importing CUAD Original Contracts ---")
                print("    Contracts ...")
                run_batched(session, CYPHER_CUAD_CONTRACT, cuad_contracts, "CUAD contracts")
                print("    Parties ...")
                run_batched(session, CYPHER_CUAD_PARTIES, cuad_parties, "CUAD party sets")
                print("    Clauses ...")
                run_batched(session, CYPHER_CUAD_CLAUSES, cuad_clauses, "CUAD clauses")
                print()
                
                print("--- [3/4] Importing AdventureWorks Dataset ---")
                print("    Orders & Customers ...")
                run_batched(session, CYPHER_AW_ORDER, aw_orders, "AdventureWorks orders")
                print("    Products & Categories ...")
                run_batched(session, CYPHER_AW_PRODUCT, aw_products, "AdventureWorks products")
                print("    Logistics & Territories ...")
                run_batched(session, CYPHER_AW_LOGISTICS, aw_logistics, "AdventureWorks logistics")
                print()
                
                print("--- [4/4] Summary Graph Statistics ---")
                stats_queries = {
                    "Total Contracts/Orders": "MATCH (c:Contract)            RETURN count(c) AS n",
                    "Parties / Customers"   : "MATCH (p:Party)               RETURN count(p) AS n",
                    "Products"              : "MATCH (pr:Product)            RETURN count(pr) AS n",
                    "Product Categories"    : "MATCH (pc:ProductCategory)    RETURN count(pc) AS n",
                    "Product Subcategories" : "MATCH (psc:ProductSubcategory)RETURN count(psc) AS n",
                    "CUAD Clauses"          : "MATCH (cl:Clause)             RETURN count(cl) AS n",
                    "Clause Types"          : "MATCH (ct:ClauseType)         RETURN count(ct) AS n",
                    "Shippers"              : "MATCH (s:Shipper)             RETURN count(s) AS n",
                    "Countries"             : "MATCH (co:Country)            RETURN count(co) AS n",
                    "Territories"           : "MATCH (t:Territory)           RETURN count(t) AS n",
                    "Datasets"              : "MATCH (d:Dataset)             RETURN count(d) AS n",
                    "Total Relationships"   : "MATCH ()-[r]->()              RETURN count(r) AS n",
                }
                print("  " + "-" * 42)
                for label, q in stats_queries.items():
                    result = session.run(q).single()
                    n = result["n"] if result else 0
                    print(f"  {label:<24}: {n:>6,}")
                print("  " + "-" * 42)
                
        print("\n" + "=" * 65)
        print("  ALL DATASETS IMPORTED TO NEO4J SUCCESSFULLY!")
        print("=" * 65)
        
    except Exception as e:
        print(f"\n❌ Error connecting to Neo4j: {e}")

if __name__ == "__main__":
    main()
