import os
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from neo4j import GraphDatabase
from groq import Groq
import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
# ==========================================
# 1. CẤU HÌNH KẾT NỐI & TÀI NGUYÊN
# ==========================================
# Thay bằng GROQ_API_KEY của bạn (lấy tại https://console.groq.com)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "your_groq_api_key_here") 

# Kết nối Qdrant Database (Local Storage)
qdrant_client = QdrantClient(path="./qdrant_db")
QDRANT_COLLECTION = "cuad_clauses"

# Kết nối Neo4j Database
NEO4J_URI = "bolt://127.0.0.1:7687"
NEO4J_AUTH = ("neo4j", "12345678")

# Khởi tạo Groq Client & Embedding Model
groq_client = Groq(api_key=GROQ_API_KEY)
embed_model = SentenceTransformer("all-MiniLM-L6-v2")


# ==========================================
# 2. HÀM TRUY VẤN VECTOR (QDRANT)
# ==========================================
def get_vector_context(query: str, top_k: int = 3) -> str:
    """Tìm kiếm đoạn văn bản có ngữ nghĩa tương đồng nhất trong Qdrant."""
    query_vector = embed_model.encode(query).tolist()
    results = qdrant_client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        limit=top_k
    ).points

    context = []
    for i, hit in enumerate(results, 1):
        contract = hit.payload.get('contract_title', 'N/A')
        clause_type = hit.payload.get('clause_type', 'N/A')
        text = hit.payload.get('extracted_text', '')
        context.append(f"[{i}] Hợp đồng: {contract}\n    Loại điều khoản: {clause_type}\n    Nội dung: {text}")
    
    return "\n\n".join(context) if context else "Không tìm thấy ngữ cảnh phù hợp trên Qdrant."


# ==========================================
# 3. HÀM TRUY VẤN ĐỒ THỊ (NEO4J)
# ==========================================
def get_graph_context(clause_type_keyword: str) -> str:
    """Truy vấn mối quan hệ thực thể trên Neo4j theo loại điều khoản."""
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
        cypher_query = """
        MATCH (c:Contract)-[:HAS_CLAUSE]->(cl:Clause)
        WHERE cl.type CONTAINS $type
        RETURN c.title AS Contract, cl.type AS ClauseType
        LIMIT 5
        """
        context = []
        with driver.session() as session:
            result = session.run(cypher_query, type=clause_type_keyword)
            for record in result:
                context.append(f"- Hợp đồng '{record['Contract']}' chứa điều khoản dạng: {record['ClauseType']}")
        driver.close()
        return "\n".join(context) if context else "Không tìm thấy cấu trúc tương ứng trên Neo4j."
    except Exception as e:
        print(f"⚠️ Cảnh báo kết nối Neo4j: {e}")
        return "Không lấy được dữ liệu từ Neo4j Graph (vẫn tiếp tục với dữ liệu Qdrant)."


# ==========================================
# 4. LUỒNG TỔNG HỢP HYBRID GRAPHRAG (GROQ)
# ==========================================
def ask_graphrag(user_query: str):
    print(f"\n❓ Câu hỏi: {user_query}")
    print("-" * 60)

    # Bước A: Truy vấn Vector từ Qdrant
    print("🔎 Đang truy vấn Qdrant (Semantic Search)...")
    vector_data = get_vector_context(user_query, top_k=3)

    # Bước B: Truy vấn Đồ thị từ Neo4j
    print("🕸️  Đang truy vấn Neo4j (Knowledge Graph)...")
    graph_keyword = "Termination" if "term" in user_query.lower() else "Renewal"
    graph_data = get_graph_context(graph_keyword)

    # Bước C: Ghép Ngữ cảnh & Gọi Groq API
    prompt = f"""Bạn là một chuyên gia pháp lý AI. Hãy trả lời câu hỏi của người dùng dựa TRỰC TIẾP vào các thông tin được trích xuất dưới đây.

=== DỮ LIỆU TỪ QDRANT (NỘI DUNG NGỮ NGHĨA) ===
{vector_data}

=== DỮ LIỆU TỪ NEO4J (MỐI QUAN HỆ ĐỒ THỊ) ===
{graph_data}

=== YÊU CẦU ===
- Trả lời bằng tiếng Việt một cách rõ ràng, chuyên nghiệp.
- Trích dẫn rõ tên hợp đồng và nội dung điều khoản cụ thể làm bằng chứng.
- Nếu thông tin chưa đủ để đưa ra kết luận chắc chắn, hãy thành thật nêu rõ.

Câu hỏi của người dùng: {user_query}
"""

    print("🤖 Đang tổng hợp câu trả lời từ Groq (LLaMA 3.3)...")
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        print("\n💡 CÂU TRẢ LỜI CỦA HYBRID GRAPHRAG:")
        print("=" * 60)
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"❌ Lỗi khi gọi Groq API: {e}")

    qdrant_client.close()


# ==========================================
# 5. CHẠY THỬ NGHIỆM
# ==========================================
if __name__ == "__main__":
    query = "Các hợp đồng quy định như thế nào về việc chấm dứt hợp đồng do hủy bỏ hoặc thông báo trước (Termination for convenience)?"
    ask_graphrag(query)