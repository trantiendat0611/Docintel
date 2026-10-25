"""Định tuyến OCR theo từng trang.

Tài liệu thật hay trộn lẫn: phần in số ở đầu, phụ lục scan đính sau. Nếu bật OCR cho cả
tài liệu thì vừa chậm vừa làm hỏng những trang vốn đã có text layer sạch. Vì vậy quyết
định theo từng trang: trang nào có quá ít ký tự trong text layer thì mới đưa qua OCR.
"""

from dataclasses import dataclass

import pypdfium2 as pdfium

# Một trang A4 in chữ thường có trên 1.000 ký tự. Trang scan gần như không có ký tự nào
# (chỉ vài ký tự rác từ con dấu hoặc watermark). Ngưỡng 100 nằm giữa hai nhóm.
DEFAULT_MIN_CHARS = 100


@dataclass(frozen=True)
class PageScan:
    page: int  # đánh số từ 1
    char_count: int
    needs_ocr: bool


def scan_pdf_pages(data: bytes, *, min_chars: int = DEFAULT_MIN_CHARS) -> list[PageScan]:
    """Đếm ký tự trong text layer của từng trang PDF."""
    pdf = pdfium.PdfDocument(data)
    try:
        result = []
        for index in range(len(pdf)):
            page = pdf[index]
            textpage = page.get_textpage()
            try:
                count = len(textpage.get_text_range().strip())
            finally:
                textpage.close()
                page.close()
            result.append(PageScan(index + 1, count, count < min_chars))
        return result
    finally:
        pdf.close()


def pages_needing_ocr(data: bytes, *, min_chars: int = DEFAULT_MIN_CHARS) -> set[int]:
    return {p.page for p in scan_pdf_pages(data, min_chars=min_chars) if p.needs_ocr}


def pdf_page_count(data: bytes) -> int:
    pdf = pdfium.PdfDocument(data)
    try:
        return len(pdf)
    finally:
        pdf.close()
