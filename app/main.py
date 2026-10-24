import logging

from fastapi import FastAPI
from sqlalchemy import text

from app.api import documents
from app.db.session import engine

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Document Intelligence System")
app.include_router(documents.router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Tiến trình còn sống. Không chạm vào DB để Docker restart đúng lý do."""
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
def ready() -> dict[str, object]:
    """Kết nối được các thành phần phụ thuộc hay chưa."""
    checks = {"database": _check_database()}
    return {"ready": all(checks.values()), "checks": checks}


def _check_database() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        logging.getLogger(__name__).warning("Không kết nối được database", exc_info=True)
        return False
