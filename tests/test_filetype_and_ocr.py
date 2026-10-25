import io
import zipfile

from app.ingestion.filetype import DOCX, JPEG, PDF, PNG, detect_mime
from app.ingestion.ocr import pages_needing_ocr, pdf_page_count, scan_pdf_pages


def _docx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", "<document/>")
    return buffer.getvalue()


def _xlsx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/workbook.xml", "<workbook/>")
    return buffer.getvalue()


def test_detect_mime_by_signature():
    assert detect_mime(b"%PDF-1.7\nrest") == PDF
    assert detect_mime(b"\x89PNG\r\n\x1a\n...") == PNG
    assert detect_mime(b"\xff\xd8\xff\xe0JFIF") == JPEG
    assert detect_mime(_docx_bytes()) == DOCX


def test_detect_mime_rejects_unsupported_and_lookalikes():
    assert detect_mime(b"MZ\x90\x00 fake exe renamed to .pdf") is None
    assert detect_mime(_xlsx_bytes()) is None  # cũng là zip nhưng không phải docx
    assert detect_mime(b"") is None


def test_text_pdf_needs_no_ocr(sample_pdf_bytes):
    pages = scan_pdf_pages(sample_pdf_bytes)
    assert pdf_page_count(sample_pdf_bytes) == len(pages) == 1
    assert pages[0].char_count > 300
    assert pages_needing_ocr(sample_pdf_bytes) == set()


def test_high_threshold_forces_ocr(sample_pdf_bytes):
    """Cùng một file, ngưỡng cao hơn số ký tự thật thì trang bị coi là cần OCR."""
    assert pages_needing_ocr(sample_pdf_bytes, min_chars=10_000) == {1}
