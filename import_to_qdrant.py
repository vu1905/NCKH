import pandas as pd
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from tqdm import tqdm

# 1. Kết nối Qdrant Server
print("Đang kết nối tới Qdrant Server...")
qdrant_client = QdrantClient("localhost", port=6333)

COLLECTION_NAME = "cuad_clauses"

# 2. Tải mô hình Embedding
print("Đang tải mô hình Embedding...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
VECTOR_SIZE = model.get_sentence_embedding_dimension() # 384 dimensions

# 3. Tạo Collection nếu chưa tồn tại
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

# 4. Đọc dữ liệu từ file CSV
print("Đang đọc dữ liệu từ cuad_extracted_clauses.csv...")
df = pd.read_csv("cuad_extracted_clauses.csv")

# SỬA LỖI TẠI ĐÂY: Lấy giá trị cột 'text' hoặc 'extracted_text' một cách an toàn
if 'text' in df.columns:
    df['clean_text'] = df['text'].fillna('')
elif 'extracted_text' in df.columns:
    df['clean_text'] = df['extracted_text'].fillna('')
else:
    raise KeyError("Không tìm thấy cột 'text' hoặc 'extracted_text' trong file CSV!")

# Lọc các dòng không có nội dung text
df = df[df['clean_text'].astype(str).str.strip() != ''].reset_index(drop=True)

print(f"-> Tổng số dòng điều khoản hợp lệ cần nạp: {len(df)}")

# 5. Mã hóa & Nạp vào Qdrant theo Batching
BATCH_SIZE = 128
points = []

for idx, row in tqdm(df.iterrows(), total=len(df), desc="Đang mã hóa & Nạp Vector"):
    text_content = str(row['clean_text'])
    
    # Tạo vector
    vector = model.encode(text_content).tolist()
    
    # Chuẩn bị Payload
    payload = {
        "contract_title": str(row.get('contract_title', '')),
        "clause_type": str(row.get('clause_type', '')),
        "text": text_content,
        "pdf_path": str(row.get('pdf_path', '')),
        "pdf_name": str(row.get('pdf_name', ''))
    }
    
    point = PointStruct(
        id=idx,
        vector=vector,
        payload=payload
    )
    points.append(point)
    
    # Đẩy lên Qdrant khi đủ batch
    if len(points) >= BATCH_SIZE:
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        points = []

# Đẩy nốt phần còn lại
if points:
    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=points
    )

print("\n=> ĐÃ NẠP THÀNH CÔNG TOÀN BỘ VECTOR VÀO QDRANT!")