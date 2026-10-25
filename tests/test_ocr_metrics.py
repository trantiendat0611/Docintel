import unicodedata

import pytest

from eval.ocr_metrics import cer, cer_sorted_words, normalize, wer


def test_normalize_makes_nfd_and_nfc_comparable():
    text = "Hoá đơn giá trị gia tăng"
    assert unicodedata.normalize("NFD", text) != text
    assert normalize(unicodedata.normalize("NFD", text)) == normalize(text)
    # Không chuẩn hoá thì CER bằng 0 lại hoá thành lỗi toàn bộ -> đây là lý do có hàm này.
    assert cer(unicodedata.normalize("NFD", text), text) == 0.0


def test_normalize_collapses_whitespace():
    assert normalize("Số  hoá\tđơn\n\n0098993 ") == "Số hoá đơn 0098993"


def test_cer_counts_character_errors():
    assert cer("Ngày lập", "Ngày lập") == 0.0
    # Một ký tự sai trên tám ký tự (không tính dấu cách sau khi chuẩn hoá).
    assert cer("Ngày lập", "Ngày Iập") == pytest.approx(1 / 8)


def test_cer_penalises_missing_diacritics():
    assert cer("Dịch vụ", "Dich vu") == pytest.approx(2 / 7)


def test_wer_counts_word_errors():
    assert wer("tổng cộng tiền thanh toán", "tổng cộng tiền thanh toan") == pytest.approx(1 / 5)


def test_sorted_words_separates_reading_order_from_recognition():
    reference = "Đơn vị bán hàng\nMã số thuế: 4184782742"
    scrambled = "Mã số thuế: 4184782742\nĐơn vị bán hàng"

    assert cer(reference, scrambled) > 0.5  # thứ tự sai -> CER thường rất cao
    assert cer_sorted_words(reference, scrambled) == 0.0  # nhưng chữ thì đọc đúng


def test_sorted_words_is_robust_to_different_line_breaks():
    """Engine OCR cắt dòng theo vùng nhận dạng, không trùng cách xuống dòng của đáp án."""
    reference = "Đơn vị bán hàng: Công ty Cổ phần Dịch vụ"
    split_differently = "Đơn vị bán hàng:\nCông ty Cổ\nphần Dịch vụ"

    assert cer_sorted_words(reference, split_differently) == 0.0


def test_sorted_words_still_counts_recognition_errors():
    assert cer_sorted_words("Ngày lập", "Ngày Iập") > 0.0
