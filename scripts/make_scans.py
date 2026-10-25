"""Biến PDF có text layer thành PDF "scan": chỉ còn ảnh, kèm nhiễu như bản chụp thật.

Dùng để có đủ tỉ lệ tài liệu scan trong bộ dữ liệu mà không phải in và chụp từng file.
Bản chụp thật vẫn cần một ít (khoảng 10 file) vì nhiễu giả không giống hệt nhiễu thật –
giữ cả hai loại thì số đo CER mới đáng tin.

Chạy: uv run python -m scripts.make_scans data/raw/synthetic/hoa-don-001.pdf --out data/raw/scans
"""

import argparse
import random
import sys
from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageEnhance, ImageFilter


def degrade(image: Image.Image, rng: random.Random) -> Image.Image:
    """Mô phỏng bản scan: lệch trang, mờ nhẹ, nhiễu hạt, giảm tương phản."""
    image = image.convert("L")
    image = image.rotate(rng.uniform(-1.2, 1.2), resample=Image.BICUBIC, fillcolor=255)
    image = image.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.8)))
    image = ImageEnhance.Contrast(image).enhance(rng.uniform(0.75, 0.95))

    noise = Image.effect_noise(image.size, rng.uniform(8, 18)).convert("L")
    return Image.blend(image, noise, alpha=0.08)


def pdf_to_scan(data: bytes, *, dpi: int = 200, seed: int = 0) -> bytes:
    rng = random.Random(seed)
    pdf = pdfium.PdfDocument(data)
    try:
        pages = []
        for index in range(len(pdf)):
            page = pdf[index]
            bitmap = page.render(scale=dpi / 72)
            pages.append(degrade(bitmap.to_pil(), rng))
            page.close()
    finally:
        pdf.close()

    buffer = BytesIO()
    pages[0].save(
        buffer, format="PDF", save_all=True, append_images=pages[1:], resolution=float(dpi)
    )
    return buffer.getvalue()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=Path("data/raw/scans"))
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    for index, path in enumerate(args.paths):
        scan = pdf_to_scan(path.read_bytes(), dpi=args.dpi, seed=index)
        target = args.out / f"{path.stem}-scan.pdf"
        target.write_bytes(scan)
        print(f"{path.name} -> {target} ({len(scan) // 1024} KB)")


if __name__ == "__main__":
    main()
