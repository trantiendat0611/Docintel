from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DocStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class BlockType(StrEnum):
    HEADING = "heading"
    TEXT = "text"
    TABLE = "table"
    LIST = "list"
    CAPTION = "caption"
    OTHER = "other"


class PageStage(StrEnum):
    """Trạng thái xử lý của một trang, dùng để chạy tiếp job dài sau khi bị ngắt."""

    PARSED = "parsed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    mime_type: Mapped[str] = mapped_column(String(128))
    storage_key: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(16), default=DocStatus.QUEUED.value)
    doc_type: Mapped[str | None] = mapped_column(String(16))
    page_count: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    parsed_key: Mapped[str | None] = mapped_column(String(512))
    ocr_page_count: Mapped[int | None] = mapped_column(Integer)
    parse_seconds: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Block(Base):
    """Một khối nội dung do parser trả về. Giữ nguyên thứ tự và vị trí trên trang
    để dùng cho trích dẫn và để debug chất lượng parse."""

    __tablename__ = "blocks"
    __table_args__ = (
        Index("blocks_document_page_idx", "document_id", "page"),
        UniqueConstraint("document_id", "position", name="blocks_document_position_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    block_type: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    heading_path: Mapped[str | None] = mapped_column(Text)
    bbox: Mapped[dict | None] = mapped_column(JSONB)
    from_ocr: Mapped[bool] = mapped_column(default=False)


class IngestProgress(Base):
    """Tiến độ theo từng trang. Worker bị ngắt giữa chừng sẽ bỏ qua các trang đã xong."""

    __tablename__ = "ingest_progress"
    __table_args__ = (UniqueConstraint("document_id", "page", name="ingest_progress_doc_page_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    page: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(16))
    used_ocr: Mapped[bool] = mapped_column(default=False)
    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
