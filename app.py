import os
import subprocess
import platform
import difflib
import streamlit as st
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from neo4j import GraphDatabase
from groq import Groq

# === CẤU HÌNH THƯ MỤC PDF THỰC TẾ TRÊN MÁY ===
BASE_PDF_DIR = r"D:\CUAD\cuad\CUAD_v1"

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(
    page_title="CUAD Contract Hybrid GraphRAG (Groq AI)",
    page_icon="📜",
    layout="wide"
)

st.title("📜 CUAD Contract Search & Analysis (Hybrid GraphRAG + Groq)")
st.markdown("Hệ thống truy vấn hợp đồng kết hợp **Qdrant (Vector DB)**, **Neo4j (Knowledge Graph)** và **Groq LLM**.")

# Sidebar cấu hình API Key & Model cập nhật mới nhất theo Groq Deprecations
st.sidebar.header("🔑 Cấu hình Groq API")
groq_api_key = st.sidebar.text_input("Nhập Groq API Key:", type="password")
selected_model = st.sidebar.selectbox(
    "Chọn Model Groq:",
    ["openai/gpt-oss-120b", "qwen/qwen3.6-27b", "llama-3.3-70b-specdec"]
)

# --- HÀM TÌM FILE THÔNG MINH (QUÉT SÂU QUA CÁC FOLDER CON CHO CẢ PDF VÀ CSV) ---
@st.cache_data(show_spinner=False)
def get_all_project_files(base_dir=BASE_PDF_DIR):
    """Quét và cache toàn bộ file PDF và CSV trong dự án."""
    files_map = {}
    if not os.path.exists(base_dir):
        return files_map
    for root, _, files in os.walk(base_dir):
        if ".git" in root or "__pycache__" in root:
            continue
        for f in files:
            ext = f.lower().split('.')[-1]
            if ext in ['pdf', 'csv', 'xlsx', 'txt', 'json']:
                files_map[f.lower()] = (os.path.join(root, f), ext, f)
    return files_map

def find_best_matching_source_file(target_name, fallback_ext="pdf"):
    """Tìm file PDF hoặc CSV khớp nhất trong toàn bộ thư mục dự án."""
    if not target_name:
        return None, "unknown", ""
    
    # 0. Nếu là đường dẫn tuyệt đối đang tồn tại
    if os.path.isabs(target_name) and os.path.exists(target_name):
        ext = target_name.lower().split('.')[-1]
        return os.path.abspath(target_name), ext, os.path.basename(target_name)
    
    clean_target = os.path.basename(target_name).lower()
    all_files = get_all_project_files(r"D:\CUAD")
    
    if not all_files:
        return None, "unknown", ""
        
    # 1. So khớp chính xác
    if clean_target in all_files:
        return all_files[clean_target]
        
    # 2. Thử thêm đuôi mở rộng
    if not clean_target.endswith(f".{fallback_ext}"):
        with_ext = f"{clean_target}.{fallback_ext}"
        if with_ext in all_files:
            return all_files[with_ext]
            
    # 3. So khớp mềm (Fuzzy Search)
    matches = difflib.get_close_matches(clean_target, list(all_files.keys()), n=1, cutoff=0.3)
    if matches:
        return all_files[matches[0]]
        
    return None, "unknown", ""

# --- HÀM MỞ FILE AN TOÀN ---
def open_local_file(filepath):
    """Mở file local bằng ứng dụng mặc định trên các hệ điều hành."""
    abs_path = os.path.abspath(os.path.normpath(filepath))
    
    if not os.path.exists(abs_path):
        return False, abs_path
        
    if platform.system() == "Windows":
        os.startfile(abs_path)
    elif platform.system() == "Darwin":  # macOS
        subprocess.run(["open", abs_path])
    else:  # Linux
        subprocess.run(["xdg-open", abs_path])
        
    return True, abs_path

# --- KẾT NỐI DỮ LIỆU (OPTIMIZED CACHE) ---
@st.cache_resource(show_spinner=False)
def get_embedding_model():
    return SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

@st.cache_resource(show_spinner=False)
def get_qdrant_client():
    return QdrantClient(path="./qdrant_db")

@st.cache_resource(show_spinner=False)
def get_neo4j_driver():
    neo4j_uri = "bolt://localhost:7687"
    neo4j_auth = ("neo4j", "12345678")
    return GraphDatabase.driver(neo4j_uri, auth=neo4j_auth)

try:
    with st.spinner("Đang khởi tạo mô hình và kết nối CSDL..."):
        model = get_embedding_model()
        qdrant_client = get_qdrant_client()
        neo4j_driver = get_neo4j_driver()
    st.sidebar.success("✅ Đã kết nối Qdrant Local & Neo4j")
except Exception as e:
    st.sidebar.error(f"❌ Lỗi kết nối CSDL: {e}")

# --- TRUY VẤN HYBRID (NEO4J GRAPH + QDRANT VECTOR) ---
def hybrid_search(query_text, top_k=5):
    combined_results = []
    seen_keys = set()
    
    # ── 1. GRAPH TRAVERSAL TRÊN NEO4J (Entity & Keyword & ID matching) ─────────
    import re
    tokens = [t.strip() for t in re.findall(r'[A-Za-z0-9\-_]+', query_text) if len(t.strip()) >= 2]
    
    with neo4j_driver.session() as session:
        for token in tokens:
            cypher_id = """
            MATCH (c:Contract)
            WHERE c.sales_order_id = $token 
               OR c.sales_order_number CONTAINS $token 
               OR c.contract_no CONTAINS $token 
               OR c.order_id = $token
               OR c.contract_id CONTAINS $token
            OPTIONAL MATCH (c)-[:HAS_PARTY]->(p:Party)
            OPTIONAL MATCH (c)-[rel:INCLUDES_PRODUCT]->(pr:Product)
            OPTIONAL MATCH (c)-[:COVERS_CATEGORY]->(pc:ProductCategory)
            OPTIONAL MATCH (c)-[:SHIPPED_BY]->(s:Shipper)
            OPTIONAL MATCH (c)-[:GOVERNED_BY]->(co:Country)
            RETURN c, collect(DISTINCT p.name) AS parties, collect(DISTINCT pr.name) AS products, 
                   s.name AS shipper, co.name AS country, pc.name AS category
            LIMIT 5
            """
            graph_res = session.run(cypher_id, token=token).data()
            for rec in graph_res:
                c = rec["c"]
                cid = c.get("contract_id", "")
                if cid and cid not in seen_keys:
                    seen_keys.add(cid)
                    
                    parties = [p for p in rec["parties"] if p]
                    products = [pr for pr in rec["products"] if pr]
                    
                    details = []
                    if c.get("sales_order_number"): details.append(f"SalesOrder: {c.get('sales_order_number')}")
                    if c.get("sales_order_id"): details.append(f"SalesOrderID: {c.get('sales_order_id')}")
                    if c.get("order_id"): details.append(f"Order ID: {c.get('order_id')}")
                    if c.get("contract_no"): details.append(f"Contract No: {c.get('contract_no')}")
                    if c.get("order_status"): details.append(f"Status: {c.get('order_status')}")
                    if c.get("order_date"): details.append(f"Date: {c.get('order_date')}")
                    if c.get("total_due"): details.append(f"Total Due: USD {c.get('total_due')}")
                    elif c.get("total_value"): details.append(f"Total: {c.get('total_value')}")
                    if parties: details.append(f"Khách hàng/Bên mua: {', '.join(parties)}")
                    if products: details.append(f"Sản phẩm: {', '.join(products)}")
                    if rec["shipper"]: details.append(f"Vận chuyển: {rec['shipper']}")
                    if rec["country"]: details.append(f"Quốc gia: {rec['country']}")
                    
                    desc_text = " | ".join(details)
                    
                    pdf_file = c.get("pdf_filename") or ""
                    pdf_path = c.get("pdf_path") or ""
                    csv_file = ""
                    if c.get("source") == "AdventureWorks" or c.get("sales_order_id") or "AW-" in cid:
                        csv_file = "adventureworks_merged_200.csv"
                    elif c.get("source") == "Northwind-Synthetic" or "NW-" in cid or c.get("order_id"):
                        csv_file = "northwind_contracts_index.csv"
                        if not pdf_file and c.get("pdf_filename"):
                            pdf_file = c.get("pdf_filename")
                    elif c.get("source") == "CUAD" or "CUAD-" in cid:
                        csv_file = "master_clauses.csv"
                    
                    combined_results.append({
                        "score": 1.0,
                        "contract_title": c.get("title", f"Contract {cid}"),
                        "clause_type": f"Graph Entity Match ({c.get('contract_type', 'Contract')})",
                        "text": desc_text,
                        "pdf_path": pdf_path,
                        "pdf_name": pdf_file,
                        "csv_name": csv_file,
                        "parties": parties
                    })

    # ── 2. VECTOR SEARCH TRÊN QDRANT (Semantic Search) ──────────────────────────
    query_vector = model.encode(query_text).tolist()
    
    vector_response = qdrant_client.query_points(
        collection_name="cuad_clauses",
        query=query_vector,
        limit=top_k
    )
    vector_results = vector_response.points
    
    with neo4j_driver.session() as session:
        for hit in vector_results:
            payload = hit.payload
            title = payload.get("contract_title", "")
            cno = payload.get("contract_no", "")
            pdf_name = payload.get("pdf_name", "")
            txt = payload.get("text", "")
            
            key = f"{title}_{payload.get('clause_type')}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            
            cypher = """
            MATCH (c:Contract)
            WHERE c.title = $title OR (c.contract_no IS NOT NULL AND c.contract_no = $cno) OR (c.pdf_filename IS NOT NULL AND c.pdf_filename = $pdf_name)
            OPTIONAL MATCH (c)-[:HAS_PARTY]->(p:Party)
            RETURN coalesce(c.title, $title) AS contract_title, collect(DISTINCT p.name) AS parties
            """
            neo_res = session.run(cypher, title=title, cno=cno, pdf_name=pdf_name).single()
            if neo_res and neo_res["parties"]:
                parties = [p for p in neo_res["parties"] if p]
            else:
                parties = []
                if payload.get("buyer_company"):
                    parties.append(payload.get("buyer_company"))
                if payload.get("customer_name"):
                    parties.append(payload.get("customer_name"))
            
            csv_file = "master_clauses.csv"
            if "northwind" in pdf_name.lower() or "NW-" in title or payload.get("category"):
                csv_file = "northwind_contracts_index.csv"
            elif payload.get("sales_order_id") or payload.get("sales_order_num") or payload.get("source") == "AdventureWorks":
                csv_file = "adventureworks_merged_200.csv"
            
            combined_results.append({
                "score": hit.score,
                "contract_title": title,
                "clause_type": payload.get("clause_type", ""),
                "text": txt,
                "pdf_path": payload.get("pdf_path", ""),
                "pdf_name": pdf_name,
                "csv_name": csv_file,
                "parties": parties
            })
            
    return combined_results[:top_k]

# --- GỌI GROQ TỔNG HỢP CÂU TRẢ LỜI ---
def generate_groq_response(api_key, model_name, user_query, search_results):
    client = Groq(api_key=api_key)
    
    context = ""
    for idx, res in enumerate(search_results, 1):
        context += f"\n--- Trích dẫn #{idx} ---\n"
        context += f"Tên Hợp đồng / Đơn hàng: {res['contract_title']}\n"
        context += f"Loại điều khoản / Thông tin: {res['clause_type']}\n"
        if res.get('pdf_name'):
            context += f"File PDF liên quan: {res['pdf_name']}\n"
        if res.get('csv_name'):
            context += f"File CSV nguồn: {res['csv_name']}\n"
        if res['parties']:
            context += f"Các bên liên quan: {', '.join(res['parties'])}\n"
        context += f"Nội dung chi tiết: {res['text']}\n"
    
    prompt = f"""Bạn là một chuyên gia phân tích pháp lý và dữ liệu thương mại. Hãy trả lời câu hỏi của người dùng dựa TRỰC TIẾP trên các đoạn trích dẫn được cung cấp dưới đây.

Câu hỏi: {user_query}

Dữ liệu trích dẫn từ CSDL:
{context}

Yêu cầu:
1. Trả lời chính xác, rõ ràng và có cấu trúc.
2. Nêu rõ thông tin đó thuộc Hợp đồng/Đơn hàng nào, liên quan đến file PDF hoặc file CSV nào.
3. Nếu dữ liệu không đủ để trả lời, hãy nêu rõ điều đó.
"""

    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1024
    )
    return response.choices[0].message.content

# --- GIAO DIỆN TRUY VẤN ---
query = st.text_input("🔍 Nhập câu hỏi truy vấn hợp đồng & dữ liệu:", placeholder="e.g. tim các cái salesorderid có mã là 43659 hoặc show non-compete clauses")

col1, col2 = st.columns([1, 5])
with col1:
    top_k = st.number_input("Số ngữ cảnh trích xuất:", min_value=1, max_value=10, value=3)

if query:
    with st.spinner("Đang truy vấn Hybrid (Qdrant Vector + Neo4j Graph)..."):
        results = hybrid_search(query, top_k=top_k)
        
    if groq_api_key:
        with st.spinner("🤖 Groq AI đang phân tích và tổng hợp câu trả lời..."):
            try:
                ai_answer = generate_groq_response(groq_api_key, selected_model, query, results)
                st.subheader("💡 Trả lời từ Groq AI:")
                st.markdown(ai_answer)
                st.markdown("---")
            except Exception as e:
                st.error(f"Lỗi khi gọi Groq API: {e}")
    else:
        st.warning("⚠️ Bạn chưa nhập Groq API Key ở thanh bên (Sidebar). Hiển thị kết quả truy vấn gốc dưới đây:")

    st.subheader(f"📌 Các trích dẫn nguồn & Tệp liên quan ({len(results)} kết quả):")
    
    for idx, res in enumerate(results, start=1):
        with st.expander(f"#{idx} | [{res['clause_type']}] - {res['contract_title']} (Score: {res['score']:.2f})"):
            st.markdown("**Nội dung chi tiết:**")
            st.info(res['text'])
            
            if res['parties']:
                st.markdown(f"**Các bên tham gia / Khách hàng:** {', '.join(res['parties'])}")
            
            pdf_candidate = res.get('pdf_name') or (os.path.basename(res['pdf_path']) if res.get('pdf_path') else "")
            csv_candidate = res.get('csv_name', "")
            
            matched_pdf, _, pdf_fname = find_best_matching_source_file(pdf_candidate, fallback_ext="pdf") if pdf_candidate else (None, "", "")
            matched_csv, _, csv_fname = find_best_matching_source_file(csv_candidate, fallback_ext="csv") if csv_candidate else (None, "", "")
            
            st.markdown("---")
            st.markdown("**📂 Các tệp liên quan đến kết quả này:**")
            
            # Khối PDF
            if matched_pdf and os.path.exists(matched_pdf):
                pdf_uri = f"file:///{matched_pdf.replace(os.sep, '/')}"
                st.markdown(f"📄 **Tệp PDF:** [{pdf_fname}]({pdf_uri})  `({os.path.getsize(matched_pdf)/1024:.0f} KB)`")
                st.caption(f"📍 Đường dẫn máy: `{matched_pdf}`")
                p_col1, p_col2 = st.columns([1, 1])
                with p_col1:
                    if st.button(f"👁 Mở file PDF #{idx}", key=f"open_pdf_{idx}"):
                        success, full_path = open_local_file(matched_pdf)
                        if success:
                            st.toast(f"Đã mở file: {pdf_fname}")
                        else:
                            st.error(f"Không thể mở: {full_path}")
                with p_col2:
                    with open(matched_pdf, "rb") as f:
                        st.download_button(
                            label=f"📥 Tải file PDF #{idx}",
                            data=f,
                            file_name=pdf_fname,
                            mime="application/pdf",
                            key=f"dl_pdf_{idx}"
                        )
            
            # Khối CSV
            if matched_csv and os.path.exists(matched_csv):
                csv_uri = f"file:///{matched_csv.replace(os.sep, '/')}"
                st.markdown(f"📊 **Tệp CSV nguồn:** [{csv_fname}]({csv_uri})  `({os.path.getsize(matched_csv)/1024:.0f} KB)`")
                st.caption(f"📍 Đường dẫn máy: `{matched_csv}`")
                c_col1, c_col2 = st.columns([1, 1])
                with c_col1:
                    if st.button(f"👁 Mở file CSV #{idx}", key=f"open_csv_{idx}"):
                        success, full_path = open_local_file(matched_csv)
                        if success:
                            st.toast(f"Đã mở file: {csv_fname}")
                        else:
                            st.error(f"Không thể mở: {full_path}")
                with c_col2:
                    with open(matched_csv, "rb") as f:
                        st.download_button(
                            label=f"📥 Tải file CSV #{idx}",
                            data=f,
                            file_name=csv_fname,
                            mime="text/csv",
                            key=f"dl_csv_{idx}"
                        )
            
            if (not matched_pdf or not os.path.exists(matched_pdf)) and (not matched_csv or not os.path.exists(matched_csv)):
                st.caption("ℹ️ Dữ liệu được trích xuất trực tiếp từ Neo4j Knowledge Graph.")