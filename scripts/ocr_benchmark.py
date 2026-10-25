"""Đo CER của các engine OCR tiếng Việt trên tập trang scan đã gõ đáp án.

Hai bước, vì đáp án đúng phải do người gõ:

    # 1. Render trang scan ra ảnh và tạo file đáp án rỗng
    uv run python -m scripts.ocr_benchmark prepare data/raw/scans/*.pdf

    # 2. Mở từng eval/ocr/pages/<tên>.gt.txt và gõ đúng nội dung nhìn thấy trên trang

    # 3. Chạy đo
    uv run python -m scripts.ocr_benchmark run

Script gọi thẳng engine OCR, không qua Docling. Mục đích là so chất lượng nhận dạng ký tự;
đi qua Docling sẽ trộn thêm lỗi dựng bảng và lỗi thứ tự đọc của tầng layout.
"""

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pypdfium2 as pdfium

from eval.ocr_metrics import cer, cer_sorted_words, wer

PAGES_DIR = Path("eval/ocr/pages")
REPORTS_DIR = Path("eval/reports/ocr")
RENDER_DPI = 300

_easyocr_reader = None


def _read_easyocr(path: Path) -> str:
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr

        _easyocr_reader = easyocr.Reader(["vi", "en"], gpu=False)
    return "\n".join(_easyocr_reader.readtext(str(path), detail=0, paragraph=False))


def _check_easyocr() -> str | None:
    try:
        import easyocr  # noqa: F401
    except ImportError:
        return "Chưa cài easyocr: uv add easyocr"
    return None


def _read_tesseract(path: Path) -> str:
    import pytesseract
    from PIL import Image

    return pytesseract.image_to_string(Image.open(path), lang="vie")


def _check_tesseract() -> str | None:
    import pytesseract

    try:
        pytesseract.get_tesseract_version()
    except Exception:
        return (
            "Không tìm thấy binary tesseract trong PATH. "
            "Windows: cài từ https://github.com/UB-Mannheim/tesseract/wiki"
        )
    if "vie" not in pytesseract.get_languages():
        return "Thiếu gói ngôn ngữ 'vie'. Thêm vie.traineddata vào thư mục tessdata"
    return None


ENGINES: dict[str, tuple[Callable[[Path], str], Callable[[], str | None]]] = {
    "easyocr": (_read_easyocr, _check_easyocr),
    "tesseract": (_read_tesseract, _check_tesseract),
}


def prepare(paths: list[Path], pages_dir: Path, dpi: int) -> list[Path]:
    """Render từng trang ra PNG và tạo file đáp án rỗng cho trang chưa có."""
    pages_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for path in paths:
        pdf = pdfium.PdfDocument(path.read_bytes())
        try:
            for index in range(len(pdf)):
                page = pdf[index]
                image = page.render(scale=dpi / 72).to_pil()
                page.close()
                stem = f"{path.stem}-p{index + 1:03d}"
                image.save(pages_dir / f"{stem}.png")
                truth = pages_dir / f"{stem}.gt.txt"
                if not truth.exists():
                    truth.write_text("", encoding="utf-8")
                    created.append(truth)
        finally:
            pdf.close()
    return created


@dataclass
class PageResult:
    page: str
    engine: str
    cer: float
    cer_sorted_words: float
    wer: float
    seconds: float
    ref_chars: int


def load_pages(pages_dir: Path) -> list[tuple[Path, str]]:
    """Các trang đã có đáp án. Trang chưa gõ đáp án bị bỏ qua."""
    found = []
    for image in sorted(pages_dir.glob("*.png")):
        truth = image.with_name(f"{image.stem}.gt.txt")
        if truth.exists() and truth.read_text(encoding="utf-8").strip():
            found.append((image, truth.read_text(encoding="utf-8")))
    return found


def run_engines(
    pages: list[tuple[Path, str]], engines: list[str], out_dir: Path
) -> list[PageResult]:
    results = []
    for name in engines:
        recognize = ENGINES[name][0]
        for image, reference in pages:
            started = time.monotonic()
            hypothesis = recognize(image)
            seconds = time.monotonic() - started
            (out_dir / f"{image.stem}.{name}.txt").write_text(hypothesis, encoding="utf-8")
            result = PageResult(
                page=image.stem,
                engine=name,
                cer=cer(reference, hypothesis),
                cer_sorted_words=cer_sorted_words(reference, hypothesis),
                wer=wer(reference, hypothesis),
                seconds=seconds,
                ref_chars=len(reference.strip()),
            )
            results.append(result)
            print(f"  {name:10} {image.stem:28} CER={result.cer:6.2%} ({seconds:.1f}s)")
    return results


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def write_report(results: list[PageResult], out_dir: Path, skipped: dict[str, str]) -> Path:
    engines = sorted({r.engine for r in results})
    lines = [
        "# Kết quả đo OCR",
        "",
        f"Thời điểm: {datetime.now().isoformat(timespec='seconds')}  ",
        f"Số trang có đáp án: {len({r.page for r in results})}",
        "",
        "## Tổng hợp",
        "",
        "| Engine | CER | CER (sắp xếp từ) | WER | Giây/trang |",
        "|---|---|---|---|---|",
    ]
    for engine in engines:
        rows = [r for r in results if r.engine == engine]
        lines.append(
            f"| {engine} | {_mean([r.cer for r in rows]):.2%} "
            f"| {_mean([r.cer_sorted_words for r in rows]):.2%} "
            f"| {_mean([r.wer for r in rows]):.2%} "
            f"| {_mean([r.seconds for r in rows]):.1f} |"
        )

    lines += [
        "",
        "`CER` tính cả thứ tự. `CER (sắp xếp từ)` sắp xếp toàn bộ từ trước khi so nên không",
        "phạt lỗi thứ tự. Chênh lệch lớn giữa hai cột nghĩa là engine đọc đúng chữ nhưng",
        "trả về sai thứ tự đọc — đó là vấn đề của tầng layout, không phải của engine.",
        "",
        "## Theo từng trang",
        "",
        "| Trang | Engine | CER | CER (sắp xếp từ) | WER | Ký tự đáp án |",
        "|---|---|---|---|---|---|",
    ]
    for result in sorted(results, key=lambda r: (r.page, r.engine)):
        lines.append(
            f"| {result.page} | {result.engine} | {result.cer:.2%} "
            f"| {result.cer_sorted_words:.2%} | {result.wer:.2%} | {result.ref_chars} |"
        )

    if skipped:
        lines += ["", "## Engine bị bỏ qua", ""]
        lines += [f"- **{name}**: {reason}" for name, reason in skipped.items()]

    lines += [
        "",
        "## Phân tích lỗi",
        "",
        "Bản OCR của từng trang nằm cùng thư mục này (`<trang>.<engine>.txt`), đối chiếu với",
        "đáp án trong `eval/ocr/pages/<trang>.gt.txt`.",
        "",
    ]

    report = out_dir / "report.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "results.json").write_text(
        json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Đo CER của các engine OCR tiếng Việt")
    sub = parser.add_subparsers(dest="command", required=True)

    prep = sub.add_parser("prepare", help="render trang scan ra ảnh và tạo file đáp án rỗng")
    prep.add_argument("paths", nargs="+", type=Path)
    prep.add_argument("--pages-dir", type=Path, default=PAGES_DIR)
    prep.add_argument("--dpi", type=int, default=RENDER_DPI)

    run = sub.add_parser("run", help="chạy các engine và xuất báo cáo")
    run.add_argument("--pages-dir", type=Path, default=PAGES_DIR)
    run.add_argument("--engines", nargs="+", choices=sorted(ENGINES), default=sorted(ENGINES))
    run.add_argument("--out", type=Path, default=REPORTS_DIR)

    args = parser.parse_args()

    if args.command == "prepare":
        created = prepare(args.paths, args.pages_dir, args.dpi)
        print(f"Đã render ảnh vào {args.pages_dir}")
        if created:
            print(f"Tạo {len(created)} file đáp án rỗng, cần gõ nội dung trước khi đo:")
            for path in created[:10]:
                print(f"  {path}")
            if len(created) > 10:
                print(f"  ... và {len(created) - 10} file nữa")
        return

    pages = load_pages(args.pages_dir)
    if not pages:
        raise SystemExit(
            f"Chưa có trang nào có đáp án trong {args.pages_dir}. "
            "Chạy lệnh prepare rồi gõ nội dung vào các file .gt.txt."
        )

    available: list[str] = []
    skipped: dict[str, str] = {}
    for name in args.engines:
        reason = ENGINES[name][1]()
        if reason:
            skipped[name] = reason
        else:
            available.append(name)
    if not available:
        raise SystemExit("Không có engine nào dùng được:\n" + "\n".join(skipped.values()))

    out_dir = args.out / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Đo {len(pages)} trang với engine: {', '.join(available)}")
    results = run_engines(pages, available, out_dir)
    report = write_report(results, out_dir, skipped)

    for name in available:
        rows = [r for r in results if r.engine == name]
        print(f"{name:10} CER trung bình {_mean([r.cer for r in rows]):.2%}")
    for name, reason in skipped.items():
        print(f"{name:10} bỏ qua: {reason}")
    print(f"Báo cáo: {report}")


if __name__ == "__main__":
    main()
