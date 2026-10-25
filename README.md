# docintel – Document Intelligence System

Hệ thống đọc tài liệu tiếng Việt (PDF, ảnh scan, DOCX): hỏi đáp có trích dẫn, phân loại và
trích xuất dữ liệu có cấu trúc. Chạy hoàn toàn local, chi phí 0đ (Ollama + công cụ mã nguồn mở).

Kế hoạch chi tiết: `../Kế hoạch dự án v2.md`. Trạng thái: **Giai đoạn 1 – ingestion, parsing, OCR**.

## Chạy nhanh

```bash
uv sync
cp .env.example .env
docker compose up -d            # Postgres :5433, Redis :6380, Phoenix http://localhost:6006
uv run alembic upgrade head
```

Mở hai terminal:

```bash
uv run uvicorn app.main:app --reload
```

```bash
uv run celery -A app.worker worker --loglevel=info --pool=solo
```

Trên Windows bắt buộc dùng `--pool=solo`; pool prefork mặc định của Celery không chạy được
trên Windows. Trên Linux/WSL dùng `--concurrency=1` (OCR ngốn RAM, không chạy song song).

Thử upload:

```bash
curl -F "file=@data/raw/synthetic/hoa-don-001.pdf" http://localhost:8000/documents
```

Tài liệu API: http://localhost:8000/docs

## API hiện có

| Method | Endpoint | Mục đích |
|---|---|---|
| POST | `/documents` | Upload file, trả `document_id` ngay, parse chạy nền |
| GET | `/documents` | Danh sách, lọc theo `status` và `doc_type` |
| GET | `/documents/{id}` | Trạng thái và metadata |
| GET | `/documents/{id}/pages/{n}` | Nội dung đã parse của một trang, để debug |
| DELETE | `/documents/{id}` | Xoá tài liệu, khối và file gốc |
| GET | `/health`, `/ready` | Kiểm tra tiến trình và kết nối DB |

Upload cùng một nội dung hai lần trả về `document_id` cũ (so khớp SHA-256) và không parse lại.
Loại file kiểm tra bằng magic bytes, không theo đuôi file.

## Dữ liệu

```bash
uv run python -m scripts.seed_data --contracts 15 --invoices 15
uv run python -m scripts.make_scans data/raw/synthetic/hoa-don-00*.pdf
```

`seed_data` sinh PDF hợp đồng/hoá đơn giả cùng nhãn đúng trong `eval/extraction.jsonl` và
`data/manifest.csv`. Cần font hỗ trợ tiếng Việt (tự tìm Arial/DejaVu, hoặc đặt `DOCINTEL_FONT`).
`make_scans` biến PDF số thành PDF chỉ có ảnh kèm nhiễu, để có tài liệu scan mà không phải in
và chụp từng file. Vẫn nên có khoảng 10 bản chụp thật, vì nhiễu giả không giống nhiễu thật.

Văn bản công khai tự tải vào `data/raw/` và thêm dòng vào `data/manifest.csv`.
File trong `data/raw/` không được commit.

## Thí nghiệm OCR

```bash
uv run python -m scripts.ocr_benchmark prepare data/raw/scans/*.pdf
# gõ đáp án vào eval/ocr/pages/*.gt.txt
uv run python -m scripts.ocr_benchmark run
```

Đo CER, WER và thời gian mỗi trang cho từng engine, báo cáo ra `eval/reports/ocr/`.
Hướng dẫn chi tiết: `eval/ocr/README.md`. Kết quả chốt vào `docs/adr/0002-ocr-routing.md`.

## Xem parser hiểu tài liệu thế nào

```bash
uv run python -m scripts.parse_one data/raw/synthetic/hoa-don-001.pdf
```

Ghi ra `data/parsed/<tên>.blocks.md` (dễ đọc), `.blocks.json` (kèm trang và bounding box) và
`.docling.json` (bản đầy đủ của Docling).

## Phát triển

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest            # nhanh, cần Postgres đang chạy
uv run pytest -m slow    # chạy Docling và OCR thật, vài phút
```

Test dùng database `docintel_test` riêng, tự tạo và tự chạy migration.

Máy WSL2/Docker Desktop: đặt `memory=14GB` trong `%UserProfile%\.wslconfig` để chừa RAM cho
embedding và LLM local. Không chạy worker ingest và LLM 7B cùng lúc.

## Cấu trúc

`app/` (api, ingestion, indexing, rag, extraction, llm, db), `migrations/` (Alembic), `eval/`
(bộ đánh giá và metric), `scripts/`, `tests/`, `docs/adr/` (quyết định kiến trúc).

## Giấy phép của các thành phần

Docling là MIT. Model layout và table của Docling tải từ Hugging Face, kiểm tra giấy phép
trước khi dùng cho mục đích thương mại. Dự án không dùng PyMuPDF (AGPL); việc đọc text layer
dùng pypdfium2 (Apache 2.0 / BSD 3-Clause).
