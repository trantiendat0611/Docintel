from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import BlockOut, DocumentOut, PageOut, UploadOut
from app.config import Settings, get_settings
from app.db.models import Block, Document, IngestProgress
from app.db.session import get_session
from app.ingestion.service import UnsupportedFile, register_upload
from app.storage import LocalStorage, get_storage

router = APIRouter(prefix="/documents", tags=["documents"])

SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[LocalStorage, Depends(get_storage)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

_CHUNK = 1024 * 1024


async def _read_capped(upload: UploadFile, max_bytes: int) -> bytes:
    """Đọc theo từng khối và dừng ngay khi vượt giới hạn.

    Không dùng ``await upload.read()`` một lần: làm vậy thì một file 10 GB đã nằm trên đĩa
    tạm trước khi ta kịp từ chối.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(_CHUNK):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"File vượt quá {max_bytes // (1024 * 1024)} MB",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("", response_model=UploadOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    session: SessionDep,
    storage: StorageDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
) -> UploadOut:
    """Nhận file, trả về document_id ngay, phần parse chạy nền trong worker."""
    data = await _read_capped(file, settings.max_upload_mb * 1024 * 1024)
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File rỗng")

    try:
        document, created = register_upload(
            session, storage, filename=file.filename or "khong-ten", data=data
        )
    except UnsupportedFile as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc

    task_id = None
    if created:
        from app.worker import ingest_document

        task_id = ingest_document.delay(document.id).id

    return UploadOut(
        document=DocumentOut.model_validate(document), created=created, task_id=task_id
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(
    session: SessionDep,
    doc_status: Annotated[str | None, Query(alias="status")] = None,
    doc_type: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Document]:
    query = select(Document).order_by(Document.created_at.desc())
    if doc_status:
        query = query.where(Document.status == doc_status)
    if doc_type:
        query = query.where(Document.doc_type == doc_type)
    return list(session.scalars(query.limit(limit).offset(offset)))


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, session: SessionDep) -> Document:
    return _require(session, document_id)


@router.get("/{document_id}/pages/{page}", response_model=PageOut)
def get_page(document_id: int, page: int, session: SessionDep) -> PageOut:
    """Nội dung đã parse của một trang, dùng để kiểm tra chất lượng parse."""
    document = _require(session, document_id)
    blocks = list(
        session.scalars(
            select(Block)
            .where(Block.document_id == document.id, Block.page == page)
            .order_by(Block.position)
        )
    )
    if not blocks and (document.page_count is None or page > document.page_count or page < 1):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Tài liệu không có trang {page}")

    progress = session.scalar(
        select(IngestProgress).where(
            IngestProgress.document_id == document.id, IngestProgress.page == page
        )
    )
    return PageOut(
        document_id=document.id,
        page=page,
        used_ocr=bool(progress and progress.used_ocr),
        blocks=[BlockOut.model_validate(block) for block in blocks],
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, session: SessionDep, storage: StorageDep) -> None:
    document = _require(session, document_id)
    for key in (document.storage_key, document.parsed_key):
        if key:
            storage.delete(key)
    session.delete(document)  # blocks và ingest_progress xoá theo nhờ ON DELETE CASCADE
    session.commit()


def _require(session: Session, document_id: int) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Không có tài liệu id={document_id}")
    return document
