# Bộ đánh giá

| File | Nội dung | Ghi chú |
|---|---|---|
| `qa_dev.jsonl` | 30 câu hỏi dùng khi chỉnh chunk/embedding/prompt | Gồm 5 câu không đáp án |
| `qa_test.jsonl` | 20 câu giữ kín, chỉ chạy 1 lần để lấy số liệu cuối | Đang gitignore; thêm vào repo khi chốt kết quả |
| `extraction.jsonl` | Nhãn trích xuất; phần tổng hợp do `scripts/seed_data.py` sinh | Thêm tay ~10 tài liệu thật |

Mỗi dòng của `qa_*.jsonl`:

```json
{"id": "q017", "question": "...", "answer": "...", "sources": [{"doc": "quy-che.pdf", "page": 12}], "type": "lookup"}
```

`type`: `lookup`, `table`, `multi_hop`, `no_answer` (với `no_answer` thì `sources` là `[]`).
Có thể nhờ LLM soạn nháp nhưng phải tự đọc và sửa từng câu.
