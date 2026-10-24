"""Test tầng API. Worker được thay bằng bản giả để không phải chạy Docling trong test."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import worker
from app.api.documents import router
from app.db.models import Block, DocStatus, Document, IngestProgress
from app.db.session import get_session
from app.ingestion.service import UnsupportedFile, register_upload
from app.main import app as fastapi_app
from app.storage import get_storage

PDF_BYTES = b"%PDF-1.7\n" + b"0" * 200


@pytest.fixture
def client(session, storage, monkeypatch):
    """Client dùng session và storage của test, và không đẩy job thật vào Celery."""
    queued: list[int] = []

    class FakeTask:
        id = "task-test"

    def fake_delay(document_id: int) -> FakeTask:
        queued.append(document_id)
        return FakeTask()

    monkeypatch.setattr(worker.ingest_document, "delay", fake_delay)
    fastapi_app.dependency_overrides[get_session] = lambda: session
    fastapi_app.dependency_overrides[get_storage] = lambda: storage
    with TestClient(fastapi_app) as test_client:
        test_client.queued = queued
        yield test_client
    fastapi_app.dependency_overrides.clear()


def _upload(client, name="a.pdf", data=PDF_BYTES):
    return client.post("/documents", files={"file": (name, data, "application/pdf")})


def test_upload_returns_id_and_queues_job(client):
    response = _upload(client)
    assert response.status_code == 202
    body = response.json()
    assert body["created"] is True
    assert body["document"]["status"] == DocStatus.QUEUED.value
    assert client.queued == [body["document"]["id"]]


def test_upload_is_idempotent_on_identical_content(client):
    first = _upload(client).json()
    second = _upload(client, name="ten-khac.pdf").json()

    assert second["created"] is False
    assert second["document"]["id"] == first["document"]["id"]
    assert client.queued == [first["document"]["id"]]  # không chạy lại job


def test_upload_rejects_unsupported_type(client):
    response = _upload(client, name="x.pdf", data=b"MZ\x90\x00 not a pdf")
    assert response.status_code == 415


def test_upload_rejects_empty_file(client):
    assert _upload(client, data=b"").status_code == 400


def test_upload_rejects_file_over_limit(client, monkeypatch):
    from app.config import Settings, get_settings

    small = Settings(_env_file=None, max_upload_mb=1)
    fastapi_app.dependency_overrides[get_settings] = lambda: small
    try:
        response = _upload(client, data=b"%PDF-1.7\n" + b"0" * (2 * 1024 * 1024))
    finally:
        fastapi_app.dependency_overrides.pop(get_settings, None)
    assert response.status_code == 413


def test_get_document_and_missing_document(client):
    document_id = _upload(client).json()["document"]["id"]
    assert client.get(f"/documents/{document_id}").json()["filename"] == "a.pdf"
    assert client.get("/documents/999999").status_code == 404


def test_list_documents_filters_by_status(client, session):
    _upload(client)
    assert len(client.get("/documents").json()) == 1
    assert client.get("/documents", params={"status": "ready"}).json() == []


def test_get_page_returns_blocks_in_order(client, session):
    document_id = _upload(client).json()["document"]["id"]
    document = session.get(Document, document_id)
    document.status = DocStatus.READY.value
    document.page_count = 1
    session.add_all(
        [
            Block(
                document_id=document_id,
                page=1,
                position=1,
                block_type="text",
                content="Nội dung sau",
            ),
            Block(
                document_id=document_id,
                page=1,
                position=0,
                block_type="heading",
                content="Tiêu đề",
            ),
            IngestProgress(document_id=document_id, page=1, stage="parsed", used_ocr=True),
        ]
    )
    session.commit()

    body = client.get(f"/documents/{document_id}/pages/1").json()
    assert body["used_ocr"] is True
    assert [b["content"] for b in body["blocks"]] == ["Tiêu đề", "Nội dung sau"]
    assert client.get(f"/documents/{document_id}/pages/7").status_code == 404


def test_delete_removes_document_blocks_and_file(client, session, storage):
    document_id = _upload(client).json()["document"]["id"]
    document = session.get(Document, document_id)
    key = document.storage_key
    session.add(Block(document_id=document_id, page=1, position=0, block_type="text", content="x"))
    session.commit()
    assert storage.exists(key)

    assert client.delete(f"/documents/{document_id}").status_code == 204
    assert session.get(Document, document_id) is None
    assert session.scalars(select(Block).where(Block.document_id == document_id)).all() == []
    assert not storage.exists(key)


def test_register_upload_rejects_unsupported(session, storage):
    with pytest.raises(UnsupportedFile):
        register_upload(session, storage, filename="x.bin", data=b"not a known type")


def test_router_prefix_is_documents():
    assert router.prefix == "/documents"
