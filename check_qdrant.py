from qdrant_client import QdrantClient

def main():
    # 1. Kết nối vào thư mục qdrant_db local của dự án
    client = QdrantClient(path="./qdrant_db")

    # 2. Xem danh sách tất cả các Collection hiện có
    collections = client.get_collections()
    print("Danh sách các Collection:", collections)

    # 3. Kiểm tra thông tin chi tiết của collection 'cuad_clauses'
    collection_name = "cuad_clauses"
    if client.collection_exists(collection_name):
        collection_info = client.get_collection(collection_name=collection_name)
        print("\nThông tin chi tiết collection:")
        print(f"- Số lượng vector đang lưu: {collection_info.points_count}")
        print(f"- Số chiều vector (Vector size): {collection_info.config.params.vectors.size}")

        # 4. Lấy thử vài điểm dữ liệu (points) đầu tiên ra xem
        records, next_offset = client.scroll(
            collection_name=collection_name,
            limit=2,  # Lấy 2 bản ghi đầu tiên
            with_payload=True,  # Lấy cả nội dung chữ bên trong (metadata)
            with_vectors=False  # Không cần hiện chuỗi số vector cho gọn
        )

        print("\nXem thử dữ liệu mẫu bên trong:")
        for idx, record in enumerate(records):
            print(f"\n--- Bản ghi {idx+1} ---")
            print(f"ID: {record.id}")
            print(f"Payload (Metadata): {record.payload}")
    else:
        print(f"Không tìm thấy collection '{collection_name}' trong database.")

    # 5. Đóng kết nối thủ công để tránh lỗi cảnh báo cổng hệ thống (portalocker/msvcrt) trên Windows
    client.close()
    print("\nĐã đóng kết nối Qdrant thành công.")

if __name__ == "__main__":
    main()