"""Nhận dạng loại file bằng magic bytes.

Đuôi file do người dùng đặt nên không tin được: một file .exe đổi tên thành .pdf vẫn qua
được kiểm tra theo đuôi. Ở đây đọc vài byte đầu để xác định loại thật.
"""

import zipfile
from io import BytesIO

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PNG = "image/png"
JPEG = "image/jpeg"
TIFF = "image/tiff"

SUPPORTED = {PDF, DOCX, PNG, JPEG, TIFF}

_SIGNATURES: list[tuple[bytes, str]] = [
    (b"%PDF-", PDF),
    (b"\x89PNG\r\n\x1a\n", PNG),
    (b"\xff\xd8\xff", JPEG),
    (b"II*\x00", TIFF),
    (b"MM\x00*", TIFF),
]


def detect_mime(data: bytes) -> str | None:
    """Trả về mime type nhận ra được, hoặc None nếu không thuộc loại hỗ trợ."""
    for signature, mime in _SIGNATURES:
        if data.startswith(signature):
            return mime
    if data.startswith(b"PK\x03\x04") and _is_docx(data):
        return DOCX
    return None


def _is_docx(data: bytes) -> bool:
    """DOCX là file zip; phân biệt với xlsx/pptx bằng phần tử bắt buộc word/document.xml."""
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            return "word/document.xml" in archive.namelist()
    except (zipfile.BadZipFile, OSError):
        return False
