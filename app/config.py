"""Cấu hình ứng dụng, đọc từ biến môi trường / file .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://docintel:docintel@localhost:5433/docintel"
    redis_url: str = "redis://localhost:6380/0"

    storage_dir: str = "data/storage"
    max_upload_mb: int = 50
    max_pages: int = 500
    job_timeout_seconds: int = 1800

    ollama_base_url: str = "http://localhost:11434"
    llm_answer_model: str = "qwen2.5:7b-instruct"
    llm_small_model: str = "qwen2.5:3b-instruct"

    phoenix_endpoint: str = "http://localhost:6006"
    api_key: str = "change-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()
