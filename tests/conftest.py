"""Cấu hình test.

Test chạy trên PostgreSQL thật (database riêng ``docintel_test``) chứ không phải SQLite:
schema dùng JSONB và ON DELETE CASCADE, SQLite sẽ cho kết quả không giống production.
Biến môi trường được đặt trước khi import ``app`` vì engine tạo lúc import module.
"""

import os
from pathlib import Path

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://docintel:docintel@localhost:5433/docintel_test"
)
os.environ.setdefault("STORAGE_DIR", "")  # được fixture thay bằng thư mục tạm

import psycopg  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.storage import LocalStorage  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TABLES = ("ingest_progress", "blocks", "documents")


def _admin_dsn() -> str:
    url = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")
    return url.rsplit("/", 1)[0] + "/postgres"


def _ensure_database() -> None:
    name = get_settings().database_url.rsplit("/", 1)[-1]
    with psycopg.connect(_admin_dsn(), autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{name}"')


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    """Tạo database test và chạy migration. Bỏ qua cả nhóm test nếu Postgres không chạy."""
    try:
        _ensure_database()
    except psycopg.OperationalError as exc:
        pytest.skip(f"Không kết nối được PostgreSQL ({exc}). Chạy: docker compose up -d")

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "head")


@pytest.fixture
def session():
    """Session sạch cho mỗi test: xoá sạch bảng trước khi chạy."""
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    with SessionLocal() as db:
        yield db


@pytest.fixture
def storage(tmp_path) -> LocalStorage:
    return LocalStorage(tmp_path / "storage")


@pytest.fixture(scope="session")
def sample_pdf_bytes() -> bytes:
    path = ROOT / "data" / "raw" / "synthetic" / "hoa-don-001.pdf"
    if not path.exists():
        pytest.skip("Chưa có dữ liệu mẫu. Chạy: uv run python -m scripts.seed_data")
    return path.read_bytes()
