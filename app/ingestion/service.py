"""Nghiệp vụ nạp tài liệu, tách khỏi Celery và FastAPI để test được mà không cần cả hai."""

import hashlib
import logging
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Block, DocStatus, Document, IngestProgress, PageStage
from app.ingestion.filetype import PDF, detect_mime
from app.storage import LocalStorage

logger = logging.getLogger(__name__)

_EXTENSIONS = {
    PDF: ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tif",
}


class UnsupportedFile(ValueError):
    pass


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def storage_key_for(digest: str, mime: str) -> str:
    """Chia thư mục theo 2 ký tự đầu để một thư mục không chứa quá nhiều file."""
    return f"raw/{digest[:2]}/{digest}{_EXTENSIONS.get(mime, '.bin')}"


def register_upload(
    session: Session, storage: LocalStorage, *, filename: str, data: bytes
) -> tuple[Document, bool]:
    """Lưu file và tạo bản ghi tài liệu.

    Trả về ``(document, is_new)``. File trùng SHA-256 thì trả lại bản ghi cũ và không xử lý
    lại: người dùng upload nhầm hai lần không làm tốn thêm vài phút OCR.
    """
    mime = detect_mime(data)
    if mime is None:
        raise UnsupportedFile(f"Loại file không được hỗ trợ: {filename}")

    digest = sha256_of(data)
    existing = session.scalar(select(Document).where(Document.sha256 == digest))
    if existing is not None:
        return existing, False

    key = storage_key_for(digest, mime)
    storage.put(key, data)
    document = Document(
        filename=Path(filename).name,
        sha256=digest,
        mime_type=mime,
        storage_key=key,
        status=DocStatus.QUEUED.value,
    )
    session.add(document)
    session.commit()
    return document, True


def ingest(session: Session, storage: LocalStorage, document_id: int) -> Document:
    """Parse tài liệu và ghi các khối vào database.

    Hàm này chạy lại được: các khối và tiến độ cũ của tài liệu bị xoá trước khi ghi mới,
    nên một job bị retry không tạo ra khối trùng lặp.
    """
    # Import ở đây chứ không ở đầu file: parse kéo theo Docling và torch (hơn 1 GB).
    # Tiến trình API chỉ gọi register_upload nên không cần nạp chúng.
    from app.ingestion.parse import parse_document

    document = session.get(Document, document_id)
    if document is None:
        raise LookupError(f"Không có tài liệu id={document_id}")

    document.status = DocStatus.PROCESSING.value
    document.error = None
    session.commit()

    data = storage.get(document.storage_key)
    result = parse_document(data, document.filename)

    session.execute(delete(Block).where(Block.document_id == document.id))
    session.execute(delete(IngestProgress).where(IngestProgress.document_id == document.id))
    session.add_all(
        Block(
            document_id=document.id,
            page=block.page,
            position=block.position,
            block_type=block.block_type,
            content=block.content,
            heading_path=block.heading_path,
            bbox=block.bbox,
            from_ocr=block.from_ocr,
        )
        for block in result.blocks
    )

    pages_with_blocks = {block.page for block in result.blocks}
    session.add_all(
        IngestProgress(
            document_id=document.id,
            page=page,
            stage=PageStage.PARSED.value if page in pages_with_blocks else PageStage.FAILED.value,
            used_ocr=page in result.ocr_pages,
            error=None if page in pages_with_blocks else "Không trích được nội dung nào",
        )
        for page in range(1, result.page_count + 1)
    )

    document.status = DocStatus.READY.value
    document.page_count = result.page_count
    document.ocr_page_count = len(result.ocr_pages)
    document.parse_seconds = int(result.seconds)
    document.parsed_key = f"parsed/{document.sha256}.json"
    session.commit()

    storage.put_json(document.parsed_key, result.docling_dict)
    logger.info(
        "Đã parse tài liệu",
        extra={
            "document_id": document.id,
            "pages": result.page_count,
            "blocks": len(result.blocks),
            "ocr_pages": len(result.ocr_pages),
            "seconds": round(result.seconds, 1),
        },
    )
    return document


def mark_failed(session: Session, document_id: int, error: str) -> None:
    document = session.get(Document, document_id)
    if document is None:
        return
    document.status = DocStatus.FAILED.value
    document.error = error[:2000]
    session.commit()
