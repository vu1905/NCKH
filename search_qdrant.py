from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

# 1. Kết nối Qdrant DB local
client = QdrantClient(path="./qdrant_db")
COLLECTION_NAME = "cuad_clauses"

# 2. Tải mô hình Embedding
model = SentenceTransformer("all-MiniLM-L6-v2")

# 3. Câu truy vấn thử nghiệm (Ví dụ: Tìm các điều khoản liên quan đến chấm dứt hợp đồng)
query_text = "Termination for convenience or notice period"
print(f"Câu truy vấn: '{query_text}'\n")

# 4. Chuyển câu hỏi thành Vector
query_vector = model.encode(query_text).tolist()

# 5. Tìm kiếm top 3 kết quả tương đồng nhất trong Qdrant
results = client.query_points(
    collection_name=COLLECTION_NAME,
    query=query_vector,
    limit=3
).points

print("=== KẾT QUẢ TÌM KIẾM TRÊN QDRANT ===")
for idx, hit in enumerate(results, 1):
    print(f"\n[{idx}] Đánh giá tương đồng (Score): {hit.score:.4f}")
    print(f"Hợp đồng: {hit.payload.get('contract_title')}")
    print(f"Loại điều khoản: {hit.payload.get('clause_type')}")
    print(f"Nội dung: {hit.payload.get('extracted_text')[:200]}...")

client.close()