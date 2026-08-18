import os
import pandas as pd
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from tqdm import tqdm

COLLECTION_NAME = "cuad_clauses"
DB_PATH = "./qdrant_db"  # Thư mục lưu CSDL Vector ngay trong ổ đĩa D:\CUAD

# 1. Khởi tạo Qdrant ở chế độ Local File (Không cần Docker / Không cần Server)
print(f"Đang khởi tạo CSDL Qdrant Local tại thư mục '{DB_PATH}'...")
qdrant_client = QdrantClient(path=DB_PATH)

# 2. Tải mô hình Embedding
print("Đang tải mô hình Embedding (all-MiniLM-L6-v2)...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

if hasattr(model, "get_embedding_dimension"):
    VECTOR_SIZE = model.get_embedding_dimension()
else:
    VECTOR_SIZE = model.get_sentence_embedding_dimension()

# 3. Tạo Collection nếu chưa có
collections = qdrant_client.get_collections().collections
collection_names = [c.name for c in collections]

if COLLECTION_NAME not in collection_names:
    print(f"Đang tạo Collection '{COLLECTION_NAME}'...")
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
    )
else:
    print(f"Collection '{COLLECTION_NAME}' đã tồn tại.")

# 4. Đọc dữ liệu CSV
print("Đang đọc dữ liệu từ cuad_extracted_clauses.csv...")
df = pd.read_csv("cuad_extracted_clauses.csv")

if 'text' in df.columns:
    df['clean_text'] = df['text'].fillna('')
elif 'extracted_text' in df.columns:
    df['clean_text'] = df['extracted_text'].fillna('')
else:
    raise KeyError("Không tìm thấy cột 'text' hoặc 'extracted_text' trong file CSV!")

df = df[df['clean_text'].astype(str).str.strip() != ''].reset_index(drop=True)
print(f"-> Tổng số dòng điều khoản hợp lệ cần nạp: {len(df)}")

# 5. Mã hóa & Nạp vào Qdrant Local
BATCH_SIZE = 256
points = []

for idx, row in tqdm(df.iterrows(), total=len(df), desc="Đang mã hóa & Nạp Vector"):
    text_content = str(row['clean_text'])
    vector = model.encode(text_content).tolist()
    
    payload = {
        "contract_title": str(row.get('contract_title', '')),
        "clause_type": str(row.get('clause_type', '')),
        "text": text_content,
        "pdf_path": str(row.get('pdf_path', '')),
        "pdf_name": str(row.get('pdf_name', ''))
    }
    
    points.append(PointStruct(id=idx, vector=vector, payload=payload))
    
    if len(points) >= BATCH_SIZE:
        qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
        points = []

if points:
    qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)

print("\n=> ĐÃ NẠP THÀNH CÔNG TOÀN BỘ VECTOR VÀO QDRANT LOCAL!")