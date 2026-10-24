import random

import pytest
from faker import Faker
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.storage import LocalStorage
from eval.metrics import Hit, recall_at_k, reciprocal_rank
from scripts.seed_data import generate_contract, generate_invoice


def test_health():
    resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_settings_defaults():
    assert Settings(_env_file=None).max_upload_mb == 50


def test_storage_roundtrip_and_traversal(tmp_path):
    storage = LocalStorage(tmp_path)
    storage.put("a/b.bin", b"xyz")
    assert storage.get("a/b.bin") == b"xyz"
    storage.delete("a/b.bin")
    with pytest.raises(FileNotFoundError):
        storage.get("a/b.bin")
    with pytest.raises(ValueError):
        storage.put("../escape.bin", b"x")


def test_retrieval_metrics():
    sources = [{"doc": "a.pdf", "page": 3}, {"doc": "a.pdf", "page": 9}]
    hits = [Hit("b.pdf", 1, 5), Hit("a.pdf", 2, 4), Hit("a.pdf", 8, 10)]
    assert recall_at_k(hits, sources, 1) == 0.0
    assert recall_at_k(hits, sources, 2) == 0.5
    assert recall_at_k(hits, sources, 3) == 1.0
    assert reciprocal_rank(hits, sources) == 0.5
    assert recall_at_k(hits, [], 3) == 0.0


def test_synthetic_invoice_is_consistent_and_reproducible():
    def make():
        fake = Faker("vi_VN")
        fake.seed_instance(1)
        return generate_invoice(fake, random.Random(1))

    inv = make()
    assert inv == make()
    assert sum(line["amount_vnd"] for line in inv["lines"]) == inv["subtotal_vnd"]
    assert inv["subtotal_vnd"] + inv["vat_vnd"] == inv["total_vnd"]
    assert len(inv["seller_tax_code"]) == 10


def test_synthetic_contract_dates_ordered():
    c = generate_contract(Faker("vi_VN"), random.Random(2))
    assert c["effective_date"] < c["expiry_date"]
