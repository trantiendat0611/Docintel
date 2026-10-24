# ADR 0001: PostgreSQL + pgvector làm kho dữ liệu duy nhất

Trạng thái: chấp nhận (tuần 1)

## Bối cảnh

Hệ thống cần lưu metadata tài liệu, khối đã parse, chunk kèm vector, full-text và kết quả
trích xuất. Quy mô MVP khoảng vài chục tài liệu (vài nghìn chunk). Chạy trên một máy 16GB,
chi phí 0đ.

## Quyết định

Dùng một PostgreSQL 17 với extension pgvector cho tất cả: bảng quan hệ, cột `vector(1024)` với
index HNSW (cosine), cột `tsvector` cho full-text (cấu hình `simple`), JSONB cho kết quả
trích xuất.

## Lý do

- Một service thay vì ba (DB + vector DB + search), giảm RAM và độ phức tạp vận hành.
- Join metadata với vector trong một câu SQL, lọc theo `document_ids`/`doc_type` dễ.
- Hybrid search (FTS + vector, gộp RRF) làm được bằng SQL thuần.
- Backup/restore một chỗ (`pg_dump`).

## Đánh đổi và rủi ro

- Lọc metadata cùng HNSW có thể trả ít kết quả hơn k; cần bật `hnsw.iterative_scan` và có test.
- Postgres không có từ điển tiếng Việt, FTS dùng `simple` không tách từ.
- Ở quy mô triệu chunk, Qdrant hoặc pgvectorscale có thể tốt hơn; sẽ đo bằng benchmark 100k chunk
  ở tuần 12 thay vì phỏng đoán.

## Phương án đã cân nhắc

Qdrant (thêm một service, tách metadata khỏi vector), Chroma/FAISS (thiếu lọc và lưu trữ quan hệ).
