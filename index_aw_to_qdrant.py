"""
=============================================================================
  INDEX ADVENTUREWORKS DATASET INTO QDRANT LOCAL
=============================================================================
  Reads:  cuad/adventureworks_merged_200.csv (200 records)
  Embeds: all-MiniLM-L6-v2 vectors
  Writes: qdrant_db (collection 'cuad_clauses')
=============================================================================
"""

import os
import sys
import pandas as pd
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from tqdm import tqdm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
AW_CSV     = os.path.join(BASE_DIR, "cuad", "adventureworks_merged_200.csv")
DB_PATH    = os.path.join(BASE_DIR, "qdrant_db")
COLLECTION = "cuad_clauses"

def main():
    print("=" * 65)
    print("  INDEXING ADVENTUREWORKS DATASET INTO QDRANT LOCAL")
    print("=" * 65)
    
    df = pd.read_csv(AW_CSV, encoding="utf-8-sig").fillna("")
    print(f"\n[1/3] Loaded {len(df)} AdventureWorks records from {AW_CSV}")
    
    records = []
    for _, row in df.iterrows():
        so_id     = str(row.get("SalesOrderID", "")).strip()
        sod_id    = str(row.get("SalesOrderDetailID", "")).strip()
        so_num    = str(row.get("SalesOrderNumber", "")).strip()
        po_num    = str(row.get("PurchaseOrderNumber", "")).strip()
        order_date= str(row.get("OrderDate", "")).strip()
        due_date  = str(row.get("DueDate", "")).strip()
        ship_date = str(row.get("ShipDate", "")).strip()
        status    = str(row.get("OrderStatus", "Shipped")).strip()
        
        cust_id   = str(row.get("CustomerID", "")).strip()
        cust_name = str(row.get("CustomerDisplayName", "")).strip() or f"Customer {cust_id}"
        acc_num   = str(row.get("CustomerAccountNumber", "")).strip()
        
        prod_id   = str(row.get("ProductID", "")).strip()
        prod_name = str(row.get("ProductName", "")).strip()
        prod_num  = str(row.get("ProductNumber", "")).strip()
        cat_name  = str(row.get("ProductCategoryName", "")).strip()
        subcat    = str(row.get("ProductSubcategoryName", "")).strip()
        color     = str(row.get("Color", "")).strip()
        size      = str(row.get("Size", "")).strip()
        weight    = str(row.get("Weight", "")).strip()
        
        qty       = str(row.get("OrderQty", "1")).strip()
        unit_price= str(row.get("UnitPrice", "0")).strip()
        discount  = str(row.get("UnitPriceDiscount", "0")).strip()
        line_total= str(row.get("LineTotal", "0")).strip()
        subtotal  = str(row.get("SubTotal", "0")).strip()
        tax       = str(row.get("TaxAmt", "0")).strip()
        freight   = str(row.get("Freight", "0")).strip()
        total_due = str(row.get("TotalDue", "0")).strip()
        card_type = str(row.get("CardType", "")).strip()
        
        ship_meth = str(row.get("ShipMethodName", "")).strip()
        tracking  = str(row.get("CarrierTrackingNumber", "")).strip()
        city      = str(row.get("City", "")).strip()
        state     = str(row.get("StateProvinceName", "")).strip()
        country   = str(row.get("CountryRegionName", "")).strip()
        postal    = str(row.get("PostalCode", "")).strip()
        territory = str(row.get("TerritoryName", "")).strip()
        terr_group= str(row.get("TerritoryGroup", "")).strip()
        
        title = f"Sales Order {so_num} (SalesOrderID: {so_id}, Item #{sod_id}) - {cust_name} - {prod_name}"
        
        # Text representation for vector embedding & retrieval
        text_desc = (
            f"ADVENTUREWORKS SALES ORDER: SalesOrderID={so_id}, SalesOrderNumber={so_num}, ItemID={sod_id}, PurchaseOrderNumber={po_num}. "
            f"Customer: {cust_name} (CustomerID: {cust_id}, AccountNumber: {acc_num}). "
            f"Product: {prod_name} (ProductID: {prod_id}, ProductNumber: {prod_num}, Category: {cat_name}, Subcategory: {subcat}, Color: {color}, Size: {size}, Weight: {weight}). "
            f"Quantity: {qty}, Unit Price: USD {unit_price}, Discount: {discount}, Line Total: USD {line_total}. "
            f"Order Financials: SubTotal=USD {subtotal}, Tax=USD {tax}, Freight=USD {freight}, TotalDue=USD {total_due}. Payment: {card_type}. "
            f"Dates: OrderDate={order_date}, DueDate={due_date}, ShipDate={ship_date}, Status={status}. "
            f"Shipping & Location: ShipMethod={ship_meth}, TrackingNumber={tracking}, Destination={city}, {state}, {country} (PostalCode: {postal}), Territory={territory} ({terr_group})."
        )
        
        records.append({
            "contract_title": title,
            "clause_type"   : "AdventureWorks Sales Order",
            "text"          : text_desc,
            "sales_order_id": so_id,
            "sales_order_num": so_num,
            "customer_name" : cust_name,
            "product_name"  : prod_name,
            "category_name" : cat_name,
            "total_due"     : total_due,
            "dataset"       : "AdventureWorks",
        })
        
    print(f"\n[2/3] Loading embedding model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    
    print(f"\n[3/3] Connecting to Qdrant Local at '{DB_PATH}'...")
    client = QdrantClient(path=DB_PATH)
    
    existing_info = client.get_collection(collection_name=COLLECTION)
    start_id = existing_info.points_count + 50000
    print(f"      Current vector count in '{COLLECTION}': {existing_info.points_count}")
    print(f"      Appending {len(records)} AdventureWorks vectors starting from ID {start_id}...")
    
    batch_size = 64
    points = []
    
    for idx, rec in enumerate(tqdm(records, desc="Encoding & Upserting")):
        point_id = start_id + idx
        vec = model.encode(rec["text"]).tolist()
        payload = {
            "contract_title" : rec["contract_title"],
            "clause_type"    : rec["clause_type"],
            "text"           : rec["text"],
            "sales_order_id" : rec["sales_order_id"],
            "sales_order_num": rec["sales_order_num"],
            "customer_name"  : rec["customer_name"],
            "product_name"   : rec["product_name"],
            "category_name"  : rec["category_name"],
            "total_due"      : rec["total_due"],
            "source"         : "AdventureWorks",
        }
        points.append(PointStruct(id=point_id, vector=vec, payload=payload))
        
        if len(points) >= batch_size:
            client.upsert(collection_name=COLLECTION, points=points)
            points = []
            
    if points:
        client.upsert(collection_name=COLLECTION, points=points)
        
    updated_info = client.get_collection(collection_name=COLLECTION)
    print("\n" + "=" * 65)
    print("  ADVENTUREWORKS INDEXING COMPLETED!")
    print(f"  Total Vectors now in '{COLLECTION}': {updated_info.points_count}")
    print("=" * 65)

if __name__ == "__main__":
    main()
