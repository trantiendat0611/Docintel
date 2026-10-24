"""Celery worker cho các job nạp tài liệu.

Parse và OCR mất từ vài giây tới vài phút trên CPU, nên phải tách khỏi request HTTP.

Chạy trên Windows cần pool ``solo`` (pool prefork mặc định không hoạt động trên Windows):

    uv run celery -A app.worker worker --loglevel=info --pool=solo

Trên Linux/WSL:

    uv run celery -A app.worker worker --loglevel=info --concurrency=1
"""

import logging

from celery import Celery

from app.config import get_settings
from app.db.session import SessionLocal
from app.ingestion.service import ingest, mark_failed
from app.storage import get_storage

logger = logging.getLogger(__name__)
settings = get_settings()

celery_app = Celery("docintel", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    # OCR ngốn RAM; để worker nhận lần lượt từng job thay vì gom sẵn nhiều job.
    task_time_limit=settings.job_timeout_seconds,
    task_soft_time_limit=settings.job_timeout_seconds - 60,
)

MAX_RETRIES = 3


@celery_app.task(bind=True, max_retries=MAX_RETRIES)
def ingest_document(self, document_id: int) -> dict:
    """Parse một tài liệu. Lỗi tạm thời được thử lại với backoff tăng dần."""
    with SessionLocal() as session:
        try:
            document = ingest(session, get_storage(), document_id)
            return {"document_id": document.id, "status": document.status}
        except Exception as exc:  # noqa: BLE001 - ghi lại mọi lỗi parse rồi quyết định retry
            logger.exception("Nạp tài liệu thất bại", extra={"document_id": document_id})
            if self.request.retries >= MAX_RETRIES:
                mark_failed(session, document_id, f"{type(exc).__name__}: {exc}")
                return {"document_id": document_id, "status": "failed"}
            raise self.retry(exc=exc, countdown=30 * (2**self.request.retries)) from exc
