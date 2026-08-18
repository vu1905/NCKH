# 📜 CUAD Contract Search & Analysis (Hybrid GraphRAG + Groq AI)

Hệ thống tra cứu, phân tích và trích xuất hợp đồng thông minh kết hợp **Qdrant (Vector Database)**, **Neo4j (Knowledge Graph)** và **Groq LLM** thông qua giao diện **Streamlit**.

---

## 📋 Mục lục
1. [Cấu trúc thư mục & Các file quan trọng](#-cấu-trúc-thư-mục--các-file-quan-trọng)
2. [Chi tiết các Script Import & Xử lý Dữ liệu](#-chi-tiết-các-script-import--xử-lý-dữ-liệu)
3. [Danh sách thư viện & Cài đặt môi trường](#-danh-sách-thư-viện--cài-đặt-môi-trường)
4. [Cấu hình CSDL (Neo4j & Qdrant)](#-cấu-hình-csdl-neo4j--qdrant)
5. [Quy trình nạp dữ liệu hoàn chỉnh](#-quy-trình-nạp-dữ-liệu-hoàn-chỉnh)
6. [Tổng hợp câu lệnh chạy Streamlit](#-tổng-hợp-câu-lệnh-chạy-streamlit)
7. [Hướng dẫn sử dụng giao diện](#-hướng-dẫn-sử-dụng-giao-diện)

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
| **`index_northwind_to_qdrant.py`** | 🔍 Nạp Vector DB | Lập chỉ mục ngữ nghĩa cho dữ liệu Northwind vào Qdrant Local. |
| **`hybrid_graphrag.py`** | 🧠 Backend Core | File core chứa logic truy vấn kết hợp Vector + Graph và gọi Groq API. |
| **`check_neo4j.py`** | 🧪 Kiểm tra | Kiểm tra số lượng Node và Relationship hiện có trong Neo4j. |
| **`check_qdrant.py`** | 🧪 Kiểm tra | Kiểm tra trạng thái Collection và số lượng vector trong Qdrant Local. |
| **`search_qdrant.py`** | 🧪 Kiểm tra | Script kiểm tra nhanh kết quả truy vấn vector từ terminal. |
| **`test_token_lookup.py`** | 🧪 Kiểm tra | Thử nghiệm thuật toán bóc tách mã đơn hàng / token truy vấn. |
| **`requirements.txt`** | 📦 Quản lý gói | Danh sách các thư viện Python kèm phiên bản cần thiết cho dự án. |
| **`qdrant_db/`** | 📁 CSDL Vector | Thư mục lưu trữ CSDL Qdrant dạng file local (không cần chạy server riêng). |
| **`cuad/`** | 📁 Dữ liệu | Chứa dữ liệu `CUAD_v1` (file PDF gốc, `master_clauses.csv`, `adventureworks_merged_200.csv`, PDF sinh tự động). |

---

## 🗂️ Chi tiết các Script Import & Xử lý Dữ liệu

| Tên File Script | Nguồn dữ liệu đầu vào | Đích đến | Chức năng chi tiết |
| :--- | :--- | :--- | :--- |
| **`import_all_to_neo4j.py`** *(Khuyên dùng)* | `cuad/CUAD_v1/master_clauses.csv` & `cuad/adventureworks_merged_200.csv` | **Neo4j** | Nạp tổng thể toàn bộ dữ liệu CUAD (510 hợp đồng, 41 loại điều khoản) và 200 đơn hàng AdventureWorks vào Knowledge Graph. |
| **`import_cuad_to_neo4j.py`** | `cuad/CUAD_v1/master_clauses.csv` | **Neo4j** | Chỉ nạp riêng tập dữ liệu pháp lý CUAD vào Knowledge Graph Neo4j. |
| **`import_aw_contracts_to_neo4j.py`** | `cuad/adventureworks_merged_200.csv` | **Neo4j** | Chỉ nạp riêng các mối quan hệ đơn hàng, khách hàng, sản phẩm của AdventureWorks vào Neo4j. |
| **`import_to_qdrant_local.py`** | `cuad_extracted_clauses.csv` | **Qdrant** (`./qdrant_db`) | Mã hóa embedding (`all-MiniLM-L6-v2`) và nạp các đoạn văn bản điều khoản CUAD vào collection `cuad_clauses`. |
| **`index_aw_to_qdrant.py`** | `cuad/adventureworks_merged_200.csv` | **Qdrant** (`./qdrant_db`) | Mã hóa embedding thông tin đơn hàng/hợp đồng AdventureWorks vào Qdrant để tìm kiếm ngữ nghĩa. |
| **`index_northwind_to_qdrant.py`** | `northwind_contracts_index.csv` | **Qdrant** (`./qdrant_db`) | Lập chỉ mục ngữ nghĩa cho tập dữ liệu hợp đồng Northwind. |
| **`generate_aw_contracts.py`** | `cuad/adventureworks_merged_200.csv` | `cuad/CUAD_v1/aw_contracts/` | Tiền xử lý sinh tự động các file PDF hợp đồng mẫu trước khi nạp dữ liệu. |

---

## 🛠️ Danh sách thư viện & Cài đặt môi trường

### 1. Bảng danh sách các thư viện cần cài

| Thư viện | Lệnh import trong Python | Mục đích sử dụng |
| :--- | :--- | :--- |
| **`streamlit`** | `import streamlit as st` | Giao diện web tương tác tra cứu hợp đồng. |
| **`watchdog`** | *(Tự động nạp bởi Streamlit)* | Theo dõi và tự reload khi có thay đổi trong file code. |
| **`sentence-transformers`** | `from sentence_transformers import SentenceTransformer` | Mô hình sinh vector embedding ngữ nghĩa (`all-MiniLM-L6-v2`). |
| **`torch` & `torchvision`** | `import torch` | Nền tảng PyTorch xử lý tính toán mô hình học sâu. |
| **`transformers`** | `import transformers` | Thư viện HuggingFace chạy các pipeline NLP. |
| **`qdrant-client`** | `from qdrant_client import QdrantClient` | Kết nối và quản lý Vector Database Qdrant (Local Storage). |
| **`neo4j`** | `from neo4j import GraphDatabase` | Driver kết nối Knowledge Graph Neo4j. |
| **`groq`** | `from groq import Groq` | SDK kết nối API Groq Cloud chạy các LLM (LLaMA 3.3, Mixtral,...). |
| **`pandas`** | `import pandas as pd` | Đọc, lọc và xử lý các tập tin dữ liệu CSV, bảng điều khoản. |
| **`openpyxl`** | *(Dùng ngầm bởi Pandas)* | Đọc/ghi các file Excel phân loại `.xlsx`. |
| **`tqdm`** | `from tqdm import tqdm` | Hiển thị thanh tiến trình trực quan khi nạp dữ liệu. |
| **`fpdf2`** | `from fpdf import FPDF` | Tạo file PDF hợp đồng tự động hỗ trợ font Unicode tiếng Việt. |

---

### 2. Hướng dẫn cài đặt

#### Cách 1: Cài đặt qua file `requirements.txt` (Khuyên dùng)
```powershell
pip install -r requirements.txt
```

#### Cách 2: Cài đặt trực tiếp qua lệnh pip
```powershell
pip install streamlit watchdog sentence-transformers torch torchvision transformers qdrant-client neo4j groq pandas openpyxl tqdm fpdf2
```

#### Thiết lập Môi trường ảo (Virtual Environment - Khuyến nghị):
```powershell
# 1. Tạo môi trường ảo
python -m venv venv

# 2. Kích hoạt môi trường ảo:
# Trên Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Hoặc trên Windows Command Prompt (cmd):
.\venv\Scripts\activate.bat

# 3. Nâng cấp pip và cài đặt thư viện:
python -m pip install --upgrade pip
pip install -r requirements.txt
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

## 🔄 Quy trình nạp dữ liệu hoàn chỉnh (Chỉ chạy lần đầu)

Chạy lần lượt các lệnh sau trong terminal:

```powershell
# 1. Sinh các tệp PDF hợp đồng từ dữ liệu AdventureWorks
python generate_aw_contracts.py

# 2. Nạp dữ liệu Graph vào Neo4j
python import_all_to_neo4j.py

# 3. Lập chỉ mục Vector vào Qdrant Local
python import_to_qdrant_local.py
python index_aw_to_qdrant.py

# 4. (Tùy chọn) Kiểm tra kết nối và số lượng bản ghi CSDL
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

### 2. Chạy với tùy chọn Watcher (Khắc phục nếu gặp lỗi torchvision)
```powershell
# Chạy với watchdog (mặc định)
python -m streamlit run app.py --server.fileWatcherType watchdog

# Chạy tắt file watcher (nhẹ máy và tránh lỗi module)
python -m streamlit run app.py --server.fileWatcherType none
```

### 3. Chạy với cổng tùy chỉnh (Custom Port)
Nếu cổng mặc định 8501 bị bận:

```powershell
streamlit run app.py --server.port 8502
```

### 4. Chạy ở chế độ Headless (Không tự mở trình duyệt tự động)
Hữu ích khi chạy trên server hoặc môi trường remote:

```powershell
streamlit run app.py --server.headless true
```

---

## 💡 Hướng dẫn sử dụng giao diện

1. **Nhập Groq API Key:**
   - Lấy API Key miễn phí tại [Groq Console](https://console.groq.com/keys).
   - Dán API Key vào ô **"Nhập Groq API Key"** ở thanh công cụ bên trái (Sidebar).
   - Chọn Model Groq mong muốn (ví dụ: `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`,...).

2. **Thực hiện truy vấn:**
   - **Tìm theo mã đơn hàng / Sales Order ID:** `43659`, `SO43659`, `AW-43659`
   - **Tìm theo loại điều khoản pháp lý:** `Non-Compete`, `Termination for Convenience`, `Governing Law`
   - **Tìm theo ngữ nghĩa / câu hỏi tự nhiên:** `Điều khoản bảo mật thông tin có thời hạn bao lâu?`

3. **Xem và tải tài liệu:**
   - Nhấn **"👁 Mở file PDF"** / **"👁 Mở file CSV"** để mở trực tiếp trên máy tính.
   - Nhấn **"📥 Tải file PDF"** / **"📥 Tải file CSV"** để tải file về máy qua trình duyệt.
