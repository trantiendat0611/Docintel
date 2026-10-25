"""Metric cho OCR: CER và WER.

Chuẩn hoá trước khi so là bắt buộc với tiếng Việt. Nếu không đưa về NFC thì hai chuỗi
hiển thị giống hệt nhau vẫn bị tính là sai toàn bộ, và con số CER trở nên vô nghĩa.
"""

import re
import unicodedata

import jiwer

_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """NFC và gộp mọi khoảng trắng thành một dấu cách."""
    return _WS.sub(" ", unicodedata.normalize("NFC", text)).strip()


def cer(reference: str, hypothesis: str) -> float:
    """Tỉ lệ ký tự sai, tính cả thứ tự. Đây là số dùng để so với mục tiêu."""
    return jiwer.cer(normalize(reference), normalize(hypothesis))


def wer(reference: str, hypothesis: str) -> float:
    return jiwer.wer(normalize(reference), normalize(hypothesis))


def cer_sorted_words(reference: str, hypothesis: str) -> float:
    """CER sau khi sắp xếp các từ, tức là bỏ qua hoàn toàn thứ tự.

    Tách lỗi nhận dạng ký tự khỏi lỗi thứ tự đọc: ``cer`` cao mà số này thấp nghĩa là
    engine đọc đúng chữ nhưng trả về sai thứ tự.

    Sắp xếp theo từ chứ không theo dòng, vì engine OCR cắt dòng theo vùng nhận dạng được,
    không trùng với cách xuống dòng của đáp án; so theo dòng cho ra số vô nghĩa.
    """
    return cer(_sorted_words(reference), _sorted_words(hypothesis))


def _sorted_words(text: str) -> str:
    return " ".join(sorted(normalize(text).split()))
