"""Sinh hợp đồng và hoá đơn giả bằng Faker (vi_VN) + Jinja, kèm nhãn trích xuất đúng tuyệt đối.

Chạy: uv run python -m scripts.seed_data --contracts 15 --invoices 15

Đầu ra:
  data/raw/synthetic/*.pdf    PDF có text layer (bản scan tạo sau bằng augmentation)
  eval/extraction.jsonl       nhãn cho các file tổng hợp (nhãn thủ công được giữ nguyên)
  data/manifest.csv           cập nhật các dòng có source = synthetic
"""

import argparse
import csv
import json
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from faker import Faker
from jinja2 import Environment
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "raw" / "synthetic"
MANIFEST = ROOT / "data" / "manifest.csv"
EXTRACTION = ROOT / "eval" / "extraction.jsonl"
MANIFEST_FIELDS = ["file", "doc_type", "source", "is_scan", "pages"]

FONT_CANDIDATES = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
]

COMPANY_KINDS = ["TNHH", "Cổ phần"]
COMPANY_TAILS = ["Thương mại", "Công nghệ", "Xây dựng", "Vận tải", "Dịch vụ", "Sản xuất"]
ITEMS = [
    "Máy in laser",
    "Giấy A4 (ream)",
    "Dịch vụ bảo trì hệ thống",
    "Mực in",
    "Bàn làm việc",
    "Ghế văn phòng",
    "Dịch vụ vận chuyển",
    "Phí thiết kế website",
    "Màn hình 24 inch",
    "Thiết bị mạng",
]
CONTRACT_BODY = Environment(autoescape=True).from_string(
    "Hôm nay, ngày {{ signed }}, tại {{ city }}, chúng tôi gồm:\n"
    "BÊN A: {{ a.name }}, mã số thuế {{ a.tax_code }}, "
    "đại diện bởi ông/bà {{ a.representative }}.\n"
    "BÊN B: {{ b.name }}, mã số thuế {{ b.tax_code }}, "
    "đại diện bởi ông/bà {{ b.representative }}.\n"
    "Điều 1. Nội dung hợp đồng: Bên B cung cấp {{ subject }} cho Bên A theo yêu cầu của Bên A.\n"
    "Điều 2. Giá trị hợp đồng: Tổng giá trị hợp đồng là {{ value }} đồng (đã bao gồm thuế).\n"
    "Điều 3. Thời hạn: Hợp đồng có hiệu lực từ ngày {{ effective }} đến hết ngày {{ expiry }}.\n"
    "Điều 4. Thanh toán: Bên A thanh toán cho Bên B trong vòng {{ days }} ngày "
    "kể từ ngày nghiệm thu.\n"
    "Điều 5. Trách nhiệm: Mỗi bên cam kết thực hiện đúng các điều khoản đã thoả thuận. "
    "Mọi tranh chấp được giải quyết thông qua thương lượng, nếu không thành thì đưa ra "
    "toà án có thẩm quyền."
)


def fmt_vnd(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def fmt_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _company(fake: Faker, rng: random.Random) -> str:
    return f"Công ty {rng.choice(COMPANY_KINDS)} {rng.choice(COMPANY_TAILS)} {fake.last_name()}"


def _party(fake: Faker, rng: random.Random) -> dict:
    return {
        "name": _company(fake, rng),
        "tax_code": "".join(rng.choices("0123456789", k=10)),
        "representative": fake.name(),
    }


def generate_contract(fake: Faker, rng: random.Random) -> dict:
    """Trả về nhãn đúng (trùng ContractExtraction, chưa có evidence)."""
    start = date(2024, 1, 1) + timedelta(days=rng.randint(0, 900))
    return {
        "contract_number": f"HD-{rng.randint(1, 999):03d}/{start.year}",
        "party_a": _party(fake, rng),
        "party_b": _party(fake, rng),
        "total_value_vnd": rng.randint(20, 5000) * 1_000_000,
        "effective_date": start.isoformat(),
        "expiry_date": (start + timedelta(days=rng.choice([90, 180, 365, 730]))).isoformat(),
    }


def generate_invoice(fake: Faker, rng: random.Random) -> dict:
    """Trả về nhãn đúng (trùng InvoiceExtraction, chưa có evidence)."""
    lines = []
    for item in rng.sample(ITEMS, k=rng.randint(1, 5)):
        qty = rng.randint(1, 20)
        unit = rng.randint(10, 3000) * 1000
        lines.append(
            {"description": item, "quantity": qty, "unit_price_vnd": unit, "amount_vnd": qty * unit}
        )
    subtotal = sum(line["amount_vnd"] for line in lines)
    vat = round(subtotal * rng.choice([0.08, 0.1]))
    return {
        "invoice_number": f"{rng.randint(1, 99999):07d}",
        "issue_date": (date(2024, 1, 1) + timedelta(days=rng.randint(0, 900))).isoformat(),
        "seller_name": _company(fake, rng),
        "seller_tax_code": "".join(rng.choices("0123456789", k=10)),
        "buyer_name": _company(fake, rng),
        "lines": lines,
        "subtotal_vnd": subtotal,
        "vat_vnd": vat,
        "total_vnd": subtotal + vat,
    }


def register_fonts() -> tuple[str, str]:
    env_font = os.environ.get("DOCINTEL_FONT")
    candidates = ([(env_font, env_font)] if env_font else []) + FONT_CANDIDATES
    for regular, bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("VN", regular))
            pdfmetrics.registerFont(TTFont("VN-Bold", bold))
            return "VN", "VN-Bold"
    raise SystemExit(
        "Không tìm thấy font hỗ trợ tiếng Việt. Đặt biến DOCINTEL_FONT=<đường dẫn .ttf>."
    )


def _styles(font: str, bold: str) -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle("t", fontName=bold, fontSize=15, alignment=1, spaceAfter=14),
        "body": ParagraphStyle("b", fontName=font, fontSize=11, leading=17, spaceAfter=6),
        "cell": ParagraphStyle("c", fontName=font, fontSize=10),
    }


def render_contract(data: dict, path: Path, fonts: tuple[str, str], rng: random.Random) -> int:
    st = _styles(*fonts)
    effective = date.fromisoformat(data["effective_date"])
    text = CONTRACT_BODY.render(
        signed=fmt_date(effective - timedelta(days=3)),
        city=rng.choice(["Hà Nội", "TP. Hồ Chí Minh", "Đà Nẵng", "Cần Thơ"]),
        a=data["party_a"],
        b=data["party_b"],
        subject=rng.choice(ITEMS).lower(),
        value=fmt_vnd(data["total_value_vnd"]),
        effective=fmt_date(effective),
        expiry=fmt_date(date.fromisoformat(data["expiry_date"])),
        days=rng.choice([15, 30, 45]),
    )
    story = [
        Paragraph("CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM", st["title"]),
        Paragraph(f"HỢP ĐỒNG SỐ {data['contract_number']}", st["title"]),
        Spacer(1, 0.3 * cm),
    ]
    story += [Paragraph(line, st["body"]) for line in text.split("\n")]
    doc = SimpleDocTemplate(str(path), pagesize=A4, title=data["contract_number"])
    doc.build(story)
    return doc.page


def render_invoice(data: dict, path: Path, fonts: tuple[str, str]) -> int:
    st = _styles(*fonts)
    rows = [["STT", "Tên hàng hoá, dịch vụ", "SL", "Đơn giá", "Thành tiền"]]
    for i, line in enumerate(data["lines"], start=1):
        rows.append(
            [
                str(i),
                Paragraph(line["description"], st["cell"]),
                str(line["quantity"]),
                fmt_vnd(line["unit_price_vnd"]),
                fmt_vnd(line["amount_vnd"]),
            ]
        )
    table = Table(rows, colWidths=[1.2 * cm, 7 * cm, 1.5 * cm, 3.5 * cm, 3.8 * cm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), fonts[0]),
                ("FONTNAME", (0, 0), (-1, 0), fonts[1]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    issue = date.fromisoformat(data["issue_date"])
    story = [
        Paragraph("HOÁ ĐƠN GIÁ TRỊ GIA TĂNG", st["title"]),
        Paragraph(f"Số hoá đơn: {data['invoice_number']}", st["body"]),
        Paragraph(f"Ngày lập: {fmt_date(issue)}", st["body"]),
        Paragraph(
            f"Đơn vị bán hàng: {data['seller_name']} - Mã số thuế: {data['seller_tax_code']}",
            st["body"],
        ),
        Paragraph(f"Đơn vị mua hàng: {data['buyer_name']}", st["body"]),
        Spacer(1, 0.4 * cm),
        table,
        Spacer(1, 0.4 * cm),
        Paragraph(f"Cộng tiền hàng: {fmt_vnd(data['subtotal_vnd'])} đồng", st["body"]),
        Paragraph(f"Tiền thuế GTGT: {fmt_vnd(data['vat_vnd'])} đồng", st["body"]),
        Paragraph(f"Tổng cộng tiền thanh toán: {fmt_vnd(data['total_vnd'])} đồng", st["body"]),
    ]
    doc = SimpleDocTemplate(str(path), pagesize=A4, title=data["invoice_number"])
    doc.build(story)
    return doc.page


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def update_manifest(rows: list[dict]) -> None:
    """Thay các dòng source=synthetic, giữ nguyên các dòng nhập tay."""
    kept: list[dict] = []
    if MANIFEST.exists():
        with MANIFEST.open(encoding="utf-8", newline="") as f:
            kept = [r for r in csv.DictReader(f) if r["source"] != "synthetic"]
    with MANIFEST.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(kept + rows)


def _manifest_row(name: str, doc_type: str, pages: int) -> dict:
    return {
        "file": f"synthetic/{name}",
        "doc_type": doc_type,
        "source": "synthetic",
        "is_scan": "false",
        "pages": pages,
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--contracts", type=int, default=15)
    parser.add_argument("--invoices", type=int, default=15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    fake = Faker("vi_VN")
    fake.seed_instance(args.seed)
    fonts = register_fonts()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    labels: list[dict] = []
    manifest: list[dict] = []
    for i in range(1, args.contracts + 1):
        name = f"hop-dong-{i:03d}.pdf"
        data = generate_contract(fake, rng)
        pages = render_contract(data, OUT_DIR / name, fonts, rng)
        labels.append({"doc": name, "doc_type": "hop_dong", "data": data})
        manifest.append(_manifest_row(name, "hop_dong", pages))
    for i in range(1, args.invoices + 1):
        name = f"hoa-don-{i:03d}.pdf"
        data = generate_invoice(fake, rng)
        pages = render_invoice(data, OUT_DIR / name, fonts)
        labels.append({"doc": name, "doc_type": "hoa_don", "data": data})
        manifest.append(_manifest_row(name, "hoa_don", pages))

    new_names = {m["file"].removeprefix("synthetic/") for m in manifest}
    manual = [r for r in _read_jsonl(EXTRACTION) if r["doc"] not in new_names]
    EXTRACTION.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in manual + labels),
        encoding="utf-8",
    )
    update_manifest(manifest)
    print(f"Đã sinh {len(labels)} tài liệu vào {OUT_DIR}")


if __name__ == "__main__":
    main()
