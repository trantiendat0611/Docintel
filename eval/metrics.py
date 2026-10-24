"""Metric cho retrieval. Một chunk được tính là trúng nếu cùng tài liệu và khoảng trang
của chunk chứa trang đáp án."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Hit:
    doc: str
    page_start: int
    page_end: int


def is_relevant(hit: Hit, sources: list[dict]) -> bool:
    return any(hit.doc == s["doc"] and hit.page_start <= s["page"] <= hit.page_end for s in sources)


def recall_at_k(hits: list[Hit], sources: list[dict], k: int) -> float:
    """Tỷ lệ trang đáp án được phủ bởi top-k. Câu không có đáp án (sources rỗng) trả 0.0;
    nên loại các câu này khỏi phép tính trung bình."""
    if not sources:
        return 0.0
    covered = sum(
        1
        for s in sources
        if any(h.doc == s["doc"] and h.page_start <= s["page"] <= h.page_end for h in hits[:k])
    )
    return covered / len(sources)


def reciprocal_rank(hits: list[Hit], sources: list[dict]) -> float:
    for rank, hit in enumerate(hits, start=1):
        if is_relevant(hit, sources):
            return 1.0 / rank
    return 0.0
