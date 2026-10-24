from fastapi import FastAPI

app = FastAPI(title="Document Intelligence System")


@app.get("/health")
def health() -> dict[str, str]:
    """Tiến trình còn sống. /ready (kiểm tra DB, Redis) sẽ thêm ở giai đoạn production."""
    return {"status": "ok"}
