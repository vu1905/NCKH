# 📜 CUAD Contract Search & Analysis (Hybrid GraphRAG + Groq AI)

Hệ thống tra cứu, phân tích và trích xuất hợp đồng thông minh kết hợp **Qdrant (Vector Database)**, **Neo4j (Knowledge Graph)** và **Groq LLM** thông qua giao diện **Streamlit**.

---

## 📋 Mục lục
1. [Cấu trúc thư mục & Các file quan trọng](#-cấu-trúc-thư-mục--các-file-quan-trọng)
2. [Cài đặt môi trường & Thư viện](#-cài-đặt-môi-trường--thư-viện)
3. [Cấu hình CSDL (Neo4j & Qdrant)](#-cấu-hình-csdl-neo4j--qdrant)
4. [Các bước chuẩn bị & Nạp dữ liệu](#-các-bước-chuẩn-bị--nạp-dữ-liệu)
5. [Tổng hợp câu lệnh chạy Streamlit](#-tổng-hợp-câu-lệnh-chạy-streamlit)
6. [Hướng dẫn sử dụng giao diện](#-hướng-dẫn-sử-dụng-giao-diện)

---

## 📂 Cấu trúc thư mục & Các file quan trọng

| File / Thư mục | Loại | Mô tả chức năng |
| :--- | :--- | :--- |
| **`app.py`** | 🚀 Ứng dụng chính | Giao diện Streamlit tra cứu Hybrid GraphRAG, tích hợp Groq AI, xem/tải PDF & CSV trực tiếp. |
| **`generate_aw_contracts.py`** | ⚙️ Tiền xử lý | Sinh các hợp đồng PDF từ dữ liệu đơn hàng AdventureWorks kèm Unicode font. |
| **`import_all_to_neo4j.py`** | 🗄️ Nạp Graph DB | Nạp toàn bộ dữ liệu CUAD (510 hợp đồng, 41 loại điều khoản) và AdventureWorks vào Neo4j. |
| **`import_cuad_to_neo4j.py`** | 🗄️ Nạp Graph DB | Nạp riêng tập dữ liệu CUAD vào Neo4j. |
| **`import_aw_contracts_to_neo4j.py`** | 🗄️ Nạp Graph DB | Nạp riêng các hợp đồng AdventureWorks vào Neo4j. |
| **`import_to_qdrant_local.py`** | 🔍 Nạp Vector DB | Mã hóa embedding (`all-MiniLM-L6-v2`) và nạp điều khoản CUAD vào Qdrant Local. |
| **`index_aw_to_qdrant.py`** | 🔍 Nạp Vector DB | Lập chỉ mục ngữ nghĩa cho dữ liệu AdventureWorks vào Qdrant Local. |
| **`check_neo4j.py`** | 🧪 Kiểm tra | Kiểm tra số lượng Node và Relationship hiện có trong Neo4j. |
| **`check_qdrant.py`** | 🧪 Kiểm tra | Kiểm tra trạng thái Collection và số lượng vector trong Qdrant Local. |
| **`search_qdrant.py`** | 🧪 Kiểm tra | Script kiểm tra nhanh kết quả truy vấn vector từ terminal. |
| **`test_token_lookup.py`** | 🧪 Kiểm tra | Thử nghiệm thuật toán bóc tách mã đơn hàng / token truy vấn. |
| **`qdrant_db/`** | 📁 CSDL Vector | Thư mục lưu trữ CSDL Qdrant dạng file local (không cần chạy server riêng). |
| **`cuad/`** | 📁 Dữ liệu | Chứa dữ liệu `CUAD_v1` (file PDF gốc, `master_clauses.csv`, `adventureworks_merged_200.csv`, PDF sinh tự động). |

---

## 🛠️ Cài đặt môi trường & Thư viện

### 1. Cài đặt Python (khuyến nghị Python 3.10+)
Cài đặt các gói thư viện cần thiết bằng lệnh:

```bash
pip install streamlit sentence-transformers qdrant-client neo4j groq pandas tqdm fpdf2
```

*(Hoặc tạo Virtual Environment trước khi cài đặt):*
```powershell
# Tạo môi trường ảo
python -m venv venv

# Kích hoạt trên Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Hoặc trên Command Prompt (cmd):
.\venv\Scripts\activate.bat

# Cài đặt thư viện:
pip install streamlit sentence-transformers qdrant-client neo4j groq pandas tqdm fpdf2
```

---

## 🔌 Cấu hình CSDL (Neo4j & Qdrant)

1. **Qdrant (Vector DB):** 
   - Đã được cấu hình ở chế độ **Local Storage** tại thư mục `./qdrant_db`. 
   - Tự động nạp và đọc file cục bộ, không cần cài đặt Docker hay Qdrant Server.

2. **Neo4j (Knowledge Graph):**
   - Đảm bảo Neo4j Server (hoặc Neo4j Desktop) đang chạy tại: `bolt://localhost:7687`
   - Thông tin xác thực mặc định trong `app.py`:
     - **URI:** `bolt://localhost:7687`
     - **Username:** `neo4j`
     - **Password:** `12345678` *(chỉnh sửa trong `app.py` nếu mật khẩu của bạn khác)*

---

## 🔄 Các bước chuẩn bị & Nạp dữ liệu (Chỉ chạy lần đầu)

Nếu cần khởi tạo hoặc làm mới toàn bộ cơ sở dữ liệu:

```powershell
# 1. Sinh các tệp PDF hợp đồng từ dữ liệu AdventureWorks
python generate_aw_contracts.py

# 2. Nạp dữ liệu Graph vào Neo4j
python import_all_to_neo4j.py

# 3. Lập chỉ mục Vector vào Qdrant Local
python import_to_qdrant_local.py
python index_aw_to_qdrant.py

# 4. (Tùy chọn) Kiểm tra kết nối CSDL
python check_neo4j.py
python check_qdrant.py
```

---

## 🚀 Tổng hợp câu lệnh chạy Streamlit

### 1. Chạy ứng dụng cơ bản
Mở terminal tại thư mục gốc của dự án (`d:\CUAD`) và chạy:

```powershell
streamlit run app.py
```

### 2. Chạy với cổng tùy chỉnh (Custom Port)
Nếu cổng mặc định 8501 bị bận:

```powershell
streamlit run app.py --server.port 8502
```

### 3. Chạy ở chế độ Headless (Không tự mở trình duyệt tự động)
Hữu ích khi chạy trên server hoặc môi trường remote:

```powershell
streamlit run app.py --server.headless true
```

### 4. Chạy và theo dõi dung lượng upload (nếu có tính năng upload lớn)
```powershell
streamlit run app.py --server.maxUploadSize 200
```

---

## 💡 Hướng dẫn sử dụng giao diện

1. **Nhập Groq API Key:**
   - Lấy API Key miễn phí tại [Groq Console](https://console.groq.com/keys).
   - Dán API Key vào ô **"Nhập Groq API Key"** ở thanh công cụ bên trái (Sidebar).
   - Chọn Model Groq mong muốn (ví dụ: `llama-3.3-70b-versatile`).

2. **Thực hiện truy vấn:**
   - **Tìm theo mã đơn hàng / Sales Order ID:** `43659`, `SO43659`, `AW-43659`
   - **Tìm theo loại điều khoản pháp lý:** `Non-Compete`, `Termination for Convenience`, `Governing Law`
   - **Tìm theo ngữ nghĩa / câu hỏi tự nhiên:** `Điều khoản bảo mật thông tin có thời hạn bao lâu?`

3. **Xem và tải tài liệu:**
   - Nhấn **"👁 Mở file PDF"** / **"👁 Mở file CSV"** để mở trực tiếp trên máy tính.
   - Nhấn **"📥 Tải file PDF"** / **"📥 Tải file CSV"** để tải file về máy qua trình duyệt.
