import unicodedata

from app.ingestion.normalize import (
    clean_text,
    find_repeated,
    fingerprint,
    join_broken_lines,
    normalize_text,
)


def test_normalize_converts_decomposed_vietnamese_to_nfc():
    decomposed = unicodedata.normalize("NFD", "Điều khoản hiệu lực")
    composed = unicodedata.normalize("NFC", "Điều khoản hiệu lực")
    assert decomposed != composed  # hai cách mã hoá khác nhau thật
    assert normalize_text(decomposed) == composed


def test_normalize_collapses_whitespace_and_strips_control_chars():
    assert normalize_text("Điều  1.\t Nội\x00 dung  ") == "Điều 1. Nội dung"
    assert normalize_text("a\r\nb\rc") == "a\nb\nc"


def test_join_continues_sentence_broken_across_lines():
    text = "Hợp đồng có hiệu lực từ ngày\n16/10/2025 đến hết ngày\nnghiệm thu."
    # Dòng bắt đầu bằng chữ số là dòng mới; dòng bắt đầu bằng chữ thường thì nối.
    assert join_broken_lines(text) == (
        "Hợp đồng có hiệu lực từ ngày\n16/10/2025 đến hết ngày nghiệm thu."
    )


def test_join_keeps_separate_clauses_and_bullets():
    text = "Điều 1. Nội dung.\nĐiều 2. Giá trị.\n- mục a\n- mục b"
    assert join_broken_lines(text) == text


def test_join_repairs_hyphenated_word():
    assert join_broken_lines("thanh toán theo tiến đ-\nộ công việc") == (
        "thanh toán theo tiến độ công việc"
    )


def test_clean_text_applies_both_steps():
    decomposed = unicodedata.normalize("NFD", "giá trị hợp\nđồng")
    assert clean_text(decomposed) == "giá trị hợp đồng"


def test_fingerprint_ignores_page_numbers():
    assert fingerprint("Trang 1 / 25") == fingerprint("Trang 12 / 25")
    assert fingerprint("Điều 5") != fingerprint("Khoản 5")


def test_find_repeated_detects_footer_across_pages():
    pairs = [(page, f"Trang {page}/4") for page in range(1, 5)]
    pairs += [(page, f"Nội dung riêng trang {page} nói về chuyện khác") for page in range(1, 5)]
    repeated = find_repeated(pairs)
    assert fingerprint("Trang 1/4") in repeated
    # Nội dung riêng cũng khớp fingerprint vì chỉ khác số -> đây là giới hạn đã biết,
    # nên parse.py chỉ áp dụng bộ lọc này cho khối ngắn (<= 80 ký tự).
    assert len(repeated) == 2


def test_find_repeated_needs_at_least_three_pages():
    pairs = [(1, "Công ty TNHH ABC"), (2, "Công ty TNHH ABC")]
    assert find_repeated(pairs) == set()
