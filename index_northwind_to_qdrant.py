"""
=============================================================================
  INDEX NORTHWIND CONTRACT CLAUSES INTO QDRANT LOCAL
=============================================================================
  Reads:  northwind_contracts_index.csv (200 contracts)
  Embeds: all-MiniLM-L6-v2 vectors
  Writes: qdrant_db (collection 'cuad_clauses')
=============================================================================
"""

import os
import sys
import pandas as pd
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from tqdm import tqdm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CUAD_DIR    = os.path.join(BASE_DIR, "cuad", "CUAD_v1")
NW_INDEX    = os.path.join(CUAD_DIR, "northwind_contracts", "northwind_contracts_index.csv")
NW_PDF_DIR  = os.path.join(CUAD_DIR, "northwind_contracts")
DB_PATH     = os.path.join(BASE_DIR, "qdrant_db")
COLLECTION  = "cuad_clauses"

CATEGORY_DESCRIPTIONS = {
    "Beverages"       : "Non-alcoholic and alcoholic beverages including soft drinks, coffees, teas, beers, ales, and specialty beverages.",
    "Condiments"      : "Sweet and savory sauces, relishes, spreads, and seasonings for culinary and food-service applications.",
    "Confections"     : "Confectionery products including candies, desserts, sweetmeats, and related sugar-based products.",
    "Dairy Products"  : "Cheeses, dairy-based products, and refrigerated specialty foods produced from milk and milk derivatives.",
    "Grains & Cereals": "Breads, crackers, pasta, cereal products, and grain-based food items for retail and food-service distribution.",
    "Meat & Poultry"  : "Prepared meats, poultry products, and processed protein foods for culinary and food-service use.",
    "Produce"         : "Fresh and dried fruits, vegetables, bean curd, and plant-based food products.",
    "Seafood"         : "Fresh, frozen, smoked, and preserved seafood products including fish, shellfish, and related marine products.",
}

def generate_northwind_clause_records():
    df_idx = pd.read_csv(NW_INDEX, encoding="utf-8-sig").fillna("")
    
    records = []
    
    for _, row in df_idx.iterrows():
        fname       = str(row.get("filename", "")).strip()
        cno         = str(row.get("contract_no", "")).strip()
        ctype       = str(row.get("contract_type", "SUPPLY AGREEMENT")).strip()
        buyer_co    = str(row.get("buyer_company", "")).strip()
        buyer_id    = str(row.get("buyer_id", "")).strip()
        buyer_ctry  = str(row.get("buyer_country", "")).strip()
        seller_co   = str(row.get("seller_company", "Northwind Traders International")).strip()
        seller_rep  = str(row.get("seller_rep", "")).strip()
        prod_name   = str(row.get("product_name", "")).strip()
        category    = str(row.get("category", "")).strip()
        unit_price  = str(row.get("unit_price", "")).strip()
        quantity    = str(row.get("quantity", "")).strip()
        discount    = str(row.get("discount", "")).strip()
        total_val   = str(row.get("total_value", "")).strip()
        shipper     = str(row.get("shipper", "")).strip()
        agr_date    = str(row.get("agreement_date", "")).strip()
        exp_date    = str(row.get("expiration_date", "")).strip()
        order_id    = str(row.get("order_id", "")).strip()
        status      = str(row.get("order_status", "Delivered")).strip()
        pdf_path    = os.path.join(NW_PDF_DIR, fname)
        
        cat_desc = CATEGORY_DESCRIPTIONS.get(category, "Commercial food and beverage products.")
        title = f"{ctype} - {buyer_co} - {prod_name}"
        
        clauses = [
            # 1. Scope of Goods
            ("Scope of Goods", (
                f"ARTICLE 1 - SCOPE OF GOODS AND SERVICES: Seller ({seller_co}, represented by {seller_rep}) agrees to supply, "
                f"and Buyer ({buyer_co}, located in {buyer_ctry}) agrees to purchase {quantity} units of {prod_name} "
                f"(Category: {category}, Order Ref: {order_id}, Contract Ref: {cno}) at a unit price of {unit_price} per unit. "
                f"Category description: {cat_desc}. All Products conform to applicable food safety standards and certifications."
            )),
            
            # 2. Contract Value & Payment Terms
            ("Price Restrictions", (
                f"ARTICLE 2 - CONTRACT VALUE AND PAYMENT TERMS: Total Contract Value is {total_val} (Unit Price: {unit_price}, "
                f"Quantity: {quantity}, Trade Discount: {discount}). Contracted under {cno}. "
                f"Payment terms are Net 30 days via bank wire transfer. Overdue payments accrue late payment interest at 1.5% per month."
            )),
            
            # 3. Delivery Terms & Logistics
            ("Post-Termination Services", (
                f"ARTICLE 3 - DELIVERY TERMS AND LOGISTICS: Agreement date: {agr_date}. Order status: {status}. "
                f"Logistics and shipping delivery provided by {shipper} (Contract Ref: {cno}). "
                f"Risk of loss transfers upon handover to carrier. Buyer inspection period is 5 business days upon delivery."
            )),
            
            # 4. Warranty & Food Safety Standards & HACCP
            ("Warranty Duration", (
                f"ARTICLE 4 - WARRANTIES AND PRODUCT STANDARDS: Seller warrants that all {category} products ({prod_name}) "
                f"under Agreement {cno} are free from defects, fit for consumption, and fully compliant with applicable food safety regulations (FDA, EU Food Safety Authority). "
                f"Warranty duration is ninety (90) days from delivery date. Seller maintains strict food safety compliance, HACCP, and ISO 22000 certifications "
                f"for all Produce, Meat & Poultry, Dairy Products, Seafood, Confections, and Beverage products. Claims must be submitted within 7 days."
            )),
            
            # 5. Limitation of Liability & Cap
            ("Cap On Liability", (
                f"ARTICLE 5 - LIMITATION OF LIABILITY: In no event shall either Party be liable for indirect, consequential, or lost profit damages. "
                f"Cap on Liability: Aggregate liability of each Party under this Agreement ({cno}) shall not exceed the total amounts paid or payable by Buyer "
                f"during the preceding twelve (12) months. Seller indemnifies Buyer against third-party claims arising from defective goods."
            )),
            
            # 6. Confidentiality
            ("Non-Disparagement", (
                f"ARTICLE 6 - CONFIDENTIALITY: Each Party agrees to protect all non-public proprietary information disclosed under Agreement {cno}. "
                f"Confidentiality obligations survive for a period of three (3) years following termination or expiration."
            )),
            
            # 7. Term and Termination
            ("Termination For Convenience", (
                f"ARTICLE 7 - TERM AND TERMINATION: Effective Date: {agr_date}. Expiration Date: {exp_date}. "
                f"Either Party may terminate this Agreement ({cno}) for convenience upon sixty (60) days prior written notice. "
                f"Termination for cause upon fifteen (15) days notice if material breach remains uncured."
            )),
            
            # 8. Force Majeure
            ("Competitive Restriction Exception", (
                f"ARTICLE 8 - FORCE MAJEURE: Neither Party is liable for delays caused by acts of God, pandemic, government actions, or transportation disruptions. "
                f"If a Force Majeure Event continues for more than sixty (60) days, either Party may terminate this Agreement upon written notice."
            )),
            
            # 9. Governing Law & Dispute Resolution
            ("Governing Law", (
                f"ARTICLE 9 - GOVERNING LAW AND DISPUTE RESOLUTION: This Agreement ({cno}) shall be governed by and construed under the laws of {buyer_ctry}. "
                f"Disputes shall be resolved through good-faith negotiation, and if unresolved, submitted to binding arbitration under the Rules of the "
                f"International Chamber of Commerce (ICC)."
            )),
            
            # 10. Audit Rights & General Provisions
            ("Audit Rights", (
                f"ARTICLE 10 - GENERAL PROVISIONS & AUDIT RIGHTS: Buyer has the right to audit Seller records relating to {prod_name} deliveries "
                f"under Agreement {cno} once per contract year upon thirty (30) days prior written notice. Anti-Assignment: Neither Party may assign without prior written consent."
            ))
        ]
        
        for ctype_name, text in clauses:
            records.append({
                "contract_title": title,
                "clause_type"   : ctype_name,
                "text"          : text,
                "pdf_path"      : pdf_path,
                "pdf_name"      : fname,
                "contract_no"   : cno,
                "category"      : category,
                "buyer_company" : buyer_co,
            })
            
    return records


def main():
    print("=" * 65)
    print("  INDEXING NORTHWIND CONTRACT CLAUSES INTO QDRANT LOCAL")
    print("=" * 65)
    
    records = generate_northwind_clause_records()
    print(f"\n[1/3] Generated {len(records)} clause chunks from 200 Northwind contracts.")
    
    print(f"\n[2/3] Loading embedding model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    
    print(f"\n[3/3] Connecting to Qdrant Local at '{DB_PATH}'...")
    client = QdrantClient(path=DB_PATH)
    
    # Get current point count to create unique IDs
    existing_info = client.get_collection(collection_name=COLLECTION)
    start_id = existing_info.points_count + 10000  # avoid collisions
    print(f"      Current vector count in '{COLLECTION}': {existing_info.points_count}")
    print(f"      Appending {len(records)} new points starting from ID {start_id}...")
    
    batch_size = 128
    points = []
    
    for idx, rec in enumerate(tqdm(records, desc="Encoding & Upserting")):
        point_id = start_id + idx
        vec = model.encode(rec["text"]).tolist()
        payload = {
            "contract_title": rec["contract_title"],
            "clause_type"   : rec["clause_type"],
            "text"          : rec["text"],
            "pdf_path"      : rec["pdf_path"],
            "pdf_name"      : rec["pdf_name"],
            "contract_no"   : rec["contract_no"],
            "category"      : rec["category"],
            "buyer_company" : rec["buyer_company"],
        }
        points.append(PointStruct(id=point_id, vector=vec, payload=payload))
        
        if len(points) >= batch_size:
            client.upsert(collection_name=COLLECTION, points=points)
            points = []
            
    if points:
        client.upsert(collection_name=COLLECTION, points=points)
        
    updated_info = client.get_collection(collection_name=COLLECTION)
    print("\n" + "=" * 65)
    print("  INDEXING COMPLETED SUCCESSFULLY!")
    print(f"  Total Vectors now in '{COLLECTION}': {updated_info.points_count}")
    print("=" * 65)

if __name__ == "__main__":
    main()
