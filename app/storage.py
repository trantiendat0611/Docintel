"""Lưu file gốc trên ổ đĩa local.

Giao diện (put/get/delete theo key) giữ giống object storage kiểu S3 để có thể đổi sang
MinIO sau này mà không sửa code gọi.
"""

import json
from functools import lru_cache
from pathlib import Path

from app.config import get_settings


class LocalStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError(f"Key không hợp lệ: {key}")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def put_json(self, key: str, payload: dict) -> None:
        self.put(key, json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def get_json(self, key: str) -> dict:
        return json.loads(self.get(key).decode("utf-8"))


@lru_cache
def get_storage() -> LocalStorage:
    return LocalStorage(get_settings().storage_dir)
