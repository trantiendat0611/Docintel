from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    sha256: str
    mime_type: str
    status: str
    doc_type: str | None
    page_count: int | None
    ocr_page_count: int | None
    parse_seconds: int | None
    error: str | None
    created_at: datetime


class BlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page: int
    position: int
    block_type: str
    content: str
    heading_path: str | None
    bbox: dict | None
    from_ocr: bool


class PageOut(BaseModel):
    document_id: int
    page: int
    used_ocr: bool
    blocks: list[BlockOut]


class UploadOut(BaseModel):
    document: DocumentOut
    created: bool
    task_id: str | None = None
