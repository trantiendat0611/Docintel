# docintel – Document Intelligence System

Hệ thống đọc tài liệu tiếng Việt (PDF, ảnh scan, DOCX): hỏi đáp có trích dẫn, phân loại và
trích xuất dữ liệu có cấu trúc. Chạy hoàn toàn local, chi phí 0đ (Ollama + công cụ mã nguồn mở).

Kế hoạch chi tiết: `../Kế hoạch dự án v2.md`. Trạng thái: **Giai đoạn 0 (tuần 1)**.

## Chạy nhanh

```bash
uv sync
cp .env.example .env
docker compose up -d            # Postgres :5433, Redis :6380, Phoenix http://localhost:6006
uv run alembic upgrade head     # tạo extension vector và bảng documents
uv run uvicorn app.main:app --reload   # http://localhost:8000/health
```

## Dữ liệu

```bash
uv run python -m scripts.seed_data --contracts 15 --invoices 15
```

Sinh PDF hợp đồng/hoá đơn giả vào `data/raw/synthetic/` cùng nhãn trong `eval/extraction.jsonl`
và `data/manifest.csv`. Cần font hỗ trợ tiếng Việt (tự tìm Arial/DejaVu; hoặc đặt
`DOCINTEL_FONT`). Văn bản công khai (quy chế, văn bản pháp luật) tự tải vào `data/raw/` và thêm
dòng vào `data/manifest.csv`. File trong `data/raw/` không được commit.

## Phát triển

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest
uv run pre-commit install       # chạy một lần
```

Máy WSL2/Docker Desktop: đặt `memory=14GB` trong `%UserProfile%\.wslconfig` để chừa RAM cho
embedding và LLM local. Không chạy worker ingest và LLM 7B cùng lúc.

## Cấu trúc

`app/` (API, ingestion, indexing, rag, extraction, llm, db), `migrations/` (Alembic), `eval/`
(bộ đánh giá và metric), `scripts/`, `tests/`, `docs/adr/` (quyết định kiến trúc).
