"""
import_aw_contracts_to_neo4j.py
================================
Imports the newly-generated AdventureWorks CUAD-style contracts
(aw_contracts_index.csv + 22 PDFs) into the existing Neo4j graph.

New nodes created / updated:
  - Contract  (source='AdventureWorks', contract_type='Sales_Agreement')
  - Party     (Party A = Adventure Works Cycles, Inc. / Party B = buyer)
  - Territory (linked from existing graph)
  - Country   (linked from existing graph)
  - Product   (per line-item in AW data)
  - ProductCategory / ProductSubcategory
  - Clause    (14 standard CUAD clauses per contract, from contract text)
  - ClauseType

Relationships added:
  HAS_PARTY, BELONGS_TO (Dataset), GOVERNED_BY (Country/Territory),
  HAS_CLAUSE, OF_TYPE, INCLUDES_PRODUCT, IN_TERRITORY
"""

import sys, os, re, json
import pandas as pd
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding="utf-8")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = r"d:\CUAD"
AW_INDEX    = os.path.join(BASE_DIR, "cuad", "CUAD_v1", "aw_contracts", "aw_contracts_index.csv")
AW_CSV      = os.path.join(BASE_DIR, "cuad", "adventureworks_merged_200.csv")
AW_PDF_DIR  = os.path.join(BASE_DIR, "cuad", "CUAD_v1", "aw_contracts")

URI  = "bolt://localhost:7687"
AUTH = ("neo4j", "12345678")

# ── Standard CUAD clauses for all AW contracts ────────────────────────────────
AW_CLAUSE_TEMPLATES = [
    ("Scope of Goods and Services",
     "Seller agrees to supply, and Buyer agrees to purchase, goods as specified in the Sales Order "
     "and incorporated Purchase Order, per Adventure Works Cycles product specifications."),
    ("Payment Terms",
     "Total contract value includes subtotal, tax amount, and freight charges as itemized in the agreement. "
     "Payment due per terms specified (Net 30/45/60 or 50-50 milestone arrangement)."),
    ("Effective Date",
     "Agreement becomes effective on the Order Date as stated in the contract header."),
    ("Expiration Date",
     "Agreement expires one (1) year from the Due Date of the corresponding Sales Order, "
     "unless renewed or terminated per Section 8."),
    ("Governing Law",
     "Agreement governed by and construed in accordance with the specified state/provincial law, "
     "without regard to conflict-of-law provisions."),
    ("Delivery and Shipping Terms",
     "Delivery made via designated carrier (Cargo Transport 5, XRQ Truck Ground, ZY Express, etc.). "
     "Risk of loss transfers to Buyer upon handover to carrier at Seller's facility."),
    ("Warranties",
     "Seller warrants goods conform to specifications, are free from defects in materials and workmanship "
     "for twelve (12) months from delivery, and are fit for intended commercial purpose."),
    ("Confidentiality",
     "Each Party shall maintain strict confidence of all Confidential Information for five (5) years "
     "post-termination. No disclosure without prior written consent, except as required by law."),
    ("Termination For Convenience",
     "Either Party may terminate upon thirty (30) days written notice. Material breach triggers "
     "immediate termination right if not cured within fifteen (15) days of notice."),
    ("Indemnification",
     "Each Party indemnifies, defends, and holds harmless the other Party from claims arising from "
     "breach, gross negligence, willful misconduct, or third-party IP infringement."),
    ("Cap On Liability",
     "Aggregate liability of either Party capped at total amounts paid or payable in the twelve (12) "
     "months preceding the claim. No liability for indirect, consequential, or punitive damages."),
    ("Audit Rights",
     "Buyer may audit Seller's books and records related to transactions under this Agreement upon "
     "reasonable notice. Records maintained for minimum three (3) years per transaction."),
    ("Anti-Assignment",
     "Neither Party may assign or transfer this Agreement without prior written consent of the other Party. "
     "Any unauthorized assignment shall be void ab initio."),
    ("Entire Agreement",
     "This Agreement, together with all Exhibits and Purchase Orders incorporated by reference, "
     "constitutes the entire agreement and supersedes all prior negotiations and understandings."),
]

# ── Cypher statements ─────────────────────────────────────────────────────────
CYPHER_AW_CONTRACT = """
UNWIND $batch AS row
MERGE (ds:Dataset {name: 'AdventureWorks-Contracts'})
  SET ds.description = 'Adventure Works Cycles sales agreements generated from AW transaction data'

MERGE (c:Contract {contract_id: row.contract_id})
SET   c.title              = row.title,
      c.contract_type      = 'Sales_Agreement',
      c.source             = 'AdventureWorks',
      c.pdf_filename       = row.pdf_filename,
      c.pdf_path           = row.pdf_path,
      c.agreement_date     = row.order_date,
      c.effective_date     = row.order_date,
      c.expiration_date    = row.expiration_date,
      c.governing_law      = row.governing_law,
      c.sales_order_id     = row.sales_order_id,
      c.sales_order_number = row.sales_order_number,
      c.purchase_order_number = row.purchase_order_number,
      c.total_due          = toFloat(row.total_due),
      c.subtotal           = toFloat(row.subtotal),
      c.tax_amount         = toFloat(row.tax_amount),
      c.freight            = toFloat(row.freight),
      c.ship_method        = row.ship_method,
      c.carrier_tracking   = row.carrier_tracking,
      c.card_type          = row.card_type,
      c.product_categories = row.product_categories,
      c.total_line_items   = toInteger(row.total_line_items),
      c.termination_convenience = 'Yes',
      c.audit_rights       = 'Yes',
      c.cap_on_liability   = 'Yes',
      c.anti_assignment    = 'Yes',
      c.warranty_duration  = 'Yes',
      c.insurance          = 'No'

MERGE (c)-[:BELONGS_TO]->(ds)

// Party A: Adventure Works Cycles
MERGE (pa:Party {name: row.party_a})
  SET pa.role = 'Seller', pa.source = 'AdventureWorks'
MERGE (c)-[:HAS_PARTY]->(pa)

// Party B: Buyer
MERGE (pb:Party {name: row.party_b})
  SET pb.role = 'Buyer',
      pb.customer_id = row.customer_id,
      pb.account_number = row.customer_account,
      pb.source = 'AdventureWorks'
MERGE (c)-[:HAS_PARTY]->(pb)

// Territory
MERGE (t:Territory {name: row.territory})
MERGE (c)-[:IN_TERRITORY]->(t)

// Country
MERGE (co:Country {name: row.country})
MERGE (c)-[:GOVERNED_BY]->(co)
"""

CYPHER_AW_CLAUSES = """
UNWIND $batch AS row
MATCH (c:Contract {contract_id: row.contract_id})
MERGE (ct:ClauseType {name: row.clause_type})
CREATE (cl:Clause {
  clause_id:   row.clause_id,
  clause_type: row.clause_type,
  answer:      row.answer,
  source:      'AdventureWorks'
})
MERGE (c)-[:HAS_CLAUSE]->(cl)
MERGE (cl)-[:OF_TYPE]->(ct)
"""

CYPHER_AW_PRODUCTS = """
UNWIND $batch AS row
MATCH (c:Contract {contract_id: row.contract_id})
MERGE (pc:ProductCategory {name: row.category})
MERGE (psc:ProductSubcategory {name: row.subcategory})
MERGE (psc)-[:BELONGS_TO_CATEGORY]->(pc)
MERGE (pr:Product {product_id: row.product_id})
  SET pr.name        = row.product_name,
      pr.number      = row.product_number,
      pr.category    = row.category,
      pr.subcategory = row.subcategory,
      pr.color       = row.color,
      pr.size        = row.size,
      pr.list_price  = toFloat(row.list_price),
      pr.source      = 'AdventureWorks'
MERGE (pr)-[:BELONGS_TO_SUBCATEGORY]->(psc)
MERGE (c)-[:INCLUDES_PRODUCT]->(pr)
"""


def run_batch(session, cypher: str, batch: list, label: str):
    if not batch:
        return
    session.run(cypher, batch=batch)
    print(f"    Imported {len(batch)} {label}")


def main():
    print("=" * 60)
    print("  AdventureWorks Contracts -> Neo4j Import")
    print("=" * 60)

    # Load data
    idx = pd.read_csv(AW_INDEX, encoding="utf-8-sig").fillna("")
    aw  = pd.read_csv(AW_CSV,   encoding="utf-8-sig").fillna("")

    # Group AW line-items by SalesOrderID for product import
    product_groups = {}
    for _, row in aw.iterrows():
        sid = str(int(row["SalesOrderID"]))
        if sid not in product_groups:
            product_groups[sid] = []
        product_groups[sid].append(row)

    driver = GraphDatabase.driver(URI, auth=AUTH)

    with driver.session() as s:
        # ── Constraints (idempotent) ───────────────────────────────────────────
        constraints = [
            "CREATE CONSTRAINT aw_contract_id IF NOT EXISTS FOR (c:Contract) REQUIRE c.contract_id IS UNIQUE",
            "CREATE CONSTRAINT clause_id_unique IF NOT EXISTS FOR (cl:Clause) REQUIRE cl.clause_id IS UNIQUE",
        ]
        for c in constraints:
            try:
                s.run(c)
            except Exception:
                pass

        # ── Step 1: Import Contract + Party + Territory + Country nodes ────────
        print("\n[1/3] Importing AW contracts, parties, territories...")
        contract_batch = []
        for _, row in idx.iterrows():
            so_id = str(int(row["sales_order_id"]))
            contract_batch.append({
                "contract_id":         "AW-" + str(row["sales_order_number"]),
                "title":               "SALES AND DISTRIBUTION AGREEMENT - " + str(row["sales_order_number"]),
                "pdf_filename":        str(row["pdf_filename"]),
                "pdf_path":            str(row["pdf_path"]),
                "order_date":          str(row["order_date"]),
                "expiration_date":     str(row["expiration_date"]),
                "governing_law":       str(row["governing_law"]),
                "sales_order_id":      so_id,
                "sales_order_number":  str(row["sales_order_number"]),
                "purchase_order_number": str(row["purchase_order_number"]),
                "party_a":             str(row["party_a"]),
                "party_b":             str(row["party_b"]),
                "customer_id":         str(row["customer_id"]),
                "customer_account":    str(row["customer_account"]),
                "territory":           str(row["territory"]),
                "country":             str(row["country"]),
                "total_due":           str(row["total_due"]),
                "subtotal":            str(row["subtotal"]),
                "tax_amount":          str(row["tax_amount"]),
                "freight":             str(row["freight"]),
                "ship_method":         str(row["ship_method"]),
                "carrier_tracking":    str(row["carrier_tracking"]),
                "card_type":           str(row["card_type"]),
                "product_categories":  str(row["product_categories"]),
                "total_line_items":    str(row["total_line_items"]),
            })
        run_batch(s, CYPHER_AW_CONTRACT, contract_batch, "contracts + parties")

        # ── Step 2: Import Clauses (14 per contract) ───────────────────────────
        print("\n[2/3] Importing CUAD-style clauses per contract...")
        clause_batch = []
        for _, row in idx.iterrows():
            cid = "AW-" + str(row["sales_order_number"])
            for i, (clause_type, answer_text) in enumerate(AW_CLAUSE_TEMPLATES, start=1):
                clause_batch.append({
                    "contract_id": cid,
                    "clause_id":   cid + "-CL" + str(i).zfill(2),
                    "clause_type": clause_type,
                    "answer":      answer_text,
                })
        run_batch(s, CYPHER_AW_CLAUSES, clause_batch, "clauses")

        # ── Step 3: Import Products per contract ───────────────────────────────
        print("\n[3/3] Importing products per contract...")
        product_batch = []
        for _, row in idx.iterrows():
            so_id = str(int(row["sales_order_id"]))
            cid   = "AW-" + str(row["sales_order_number"])
            for pr in product_groups.get(so_id, []):
                product_batch.append({
                    "contract_id":  cid,
                    "product_id":   "AW-P-" + str(int(pr["ProductID"])),
                    "product_name": str(pr["ProductName"]),
                    "product_number": str(pr["ProductNumber"]),
                    "category":     str(pr["ProductCategoryName"]),
                    "subcategory":  str(pr["ProductSubcategoryName"]),
                    "color":        str(pr["Color"]),
                    "size":         str(pr["Size"]),
                    "list_price":   str(pr["ListPrice"]),
                })
        run_batch(s, CYPHER_AW_PRODUCTS, product_batch, "product-contract links")

        # ── Summary ────────────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  Import complete! Verifying graph stats...")
        totals = {
            "Contract":         "MATCH (n:Contract) RETURN count(n) as c",
            "Party":            "MATCH (n:Party) RETURN count(n) as c",
            "Clause":           "MATCH (n:Clause) RETURN count(n) as c",
            "Product":          "MATCH (n:Product) RETURN count(n) as c",
            "ProductCategory":  "MATCH (n:ProductCategory) RETURN count(n) as c",
            "Territory":        "MATCH (n:Territory) RETURN count(n) as c",
            "Country":          "MATCH (n:Country) RETURN count(n) as c",
            "HAS_PARTY":        "MATCH ()-[r:HAS_PARTY]->() RETURN count(r) as c",
            "HAS_CLAUSE":       "MATCH ()-[r:HAS_CLAUSE]->() RETURN count(r) as c",
            "INCLUDES_PRODUCT": "MATCH ()-[r:INCLUDES_PRODUCT]->() RETURN count(r) as c",
        }
        for label, cypher in totals.items():
            cnt = s.run(cypher).single()["c"]
            print(f"    {label:25s} {cnt:>6}")

        aw_cnt = s.run("MATCH (c:Contract) WHERE c.source = 'AdventureWorks' RETURN count(c) as c").single()["c"]
        print(f"\n  AW contracts in graph : {aw_cnt}")

    driver.close()
    print("=" * 60)
    print("  Done.")


if __name__ == "__main__":
    main()
