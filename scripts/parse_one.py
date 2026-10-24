"""Parse một file và ghi kết quả ra data/parsed/ để xem Docling hiểu tài liệu thế nào.

Chạy: uv run python -m scripts.parse_one data/raw/synthetic/hoa-don-001.pdf

Ghi ra ba file: ``<tên>.blocks.md`` (các khối đã chuẩn hoá, dễ đọc),
``<tên>.blocks.json`` (kèm trang và bounding box) và ``<tên>.docling.json`` (bản đầy đủ).
"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from app.ingestion.ocr import scan_pdf_pages
from app.ingestion.parse import parse_document

OUT_DIR = Path("data/parsed")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    data = args.path.read_bytes()
    if args.path.suffix.lower() == ".pdf":
        pages = scan_pdf_pages(data)
        need = [p.page for p in pages if p.needs_ocr]
        print(f"{len(pages)} trang, {len(need)} trang cần OCR: {need or 'không có'}")

    result = parse_document(data, args.path.name)
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.path.stem

    (args.out / f"{stem}.blocks.md").write_text(
        "\n\n".join(
            f"<!-- trang {b.page} · {b.block_type} · {b.heading_path or '-'} -->\n{b.content}"
            for b in result.blocks
        ),
        encoding="utf-8",
    )
    (args.out / f"{stem}.blocks.json").write_text(
        json.dumps([asdict(b) for b in result.blocks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.out / f"{stem}.docling.json").write_text(
        json.dumps(result.docling_dict, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    by_type: dict[str, int] = {}
    for block in result.blocks:
        by_type[block.block_type] = by_type.get(block.block_type, 0) + 1
    print(
        f"Parse {args.path.name} trong {result.seconds:.1f}s: {len(result.blocks)} khối {by_type}"
    )
    print(f"Kết quả trong {args.out}/{stem}.*")


if __name__ == "__main__":
    main()
