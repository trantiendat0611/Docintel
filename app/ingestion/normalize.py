"""Chuẩn hoá văn bản sau khi parse.

Ghi chú về tiếng Việt: NFC chỉ gộp được dấu tổ hợp (``e`` + ``◌́`` thành ``é``). Nó không
đồng nhất được hai quy ước đặt dấu như ``hòa`` và ``hoà`` – đó là hai chuỗi khác nhau thật
sự. Việc đó để tầng truy hồi xử lý nếu đo thấy có ảnh hưởng.
"""

import re
import unicodedata
from collections.abc import Iterable

# Ký tự kết thúc câu: không nối dòng sau các ký tự này.
_SENTENCE_END = ".!?:;…"
# Đầu dòng là mục mới (số điều khoản, gạch đầu dòng): không nối vào dòng trước.
_LIST_START = re.compile(
    r"^\s*(?:[-–—•*]|\(?\d+[.)]|[a-zđ]\)|Điều\s+\d+|Chương\s+[IVXLCDM\d]+|Khoản\s+\d+|Mục\s+\d+)",
    re.IGNORECASE,
)
_WS = re.compile(r"[ \t  -​]+")
_DIGITS = re.compile(r"\d+")


def normalize_text(text: str) -> str:
    """NFC, bỏ ký tự điều khiển, gộp khoảng trắng, bỏ khoảng trắng thừa ở mỗi dòng."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if ch == "\n" or not unicodedata.category(ch).startswith("C"))
    lines = [_WS.sub(" ", line).strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def join_broken_lines(text: str) -> str:
    """Nối dòng bị ngắt giữa câu.

    Chỉ nối khi dòng trước không kết thúc câu và dòng sau trông như phần tiếp của câu đó
    (không viết hoa, không phải đầu mục). Thà bỏ sót còn hơn nối nhầm hai đoạn khác nhau.
    """
    out: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not out or not stripped or not out[-1]:
            out.append(stripped)
            continue

        prev = out[-1]
        if prev.endswith("-"):  # từ bị gạch nối cuối dòng
            out[-1] = prev[:-1] + stripped
            continue
        if prev[-1] in _SENTENCE_END or _LIST_START.match(stripped):
            out.append(stripped)
            continue
        if stripped[0].isupper() or stripped[0].isdigit():
            out.append(stripped)
            continue
        out[-1] = f"{prev} {stripped}"
    return "\n".join(out)


def clean_text(text: str) -> str:
    """Chuẩn hoá một đoạn văn bản thô: NFC rồi nối dòng gãy."""
    return join_broken_lines(normalize_text(text))


def fingerprint(text: str) -> str:
    """Khoá so sánh bỏ qua số, để ``Trang 1`` và ``Trang 2`` được coi là cùng một footer."""
    return _DIGITS.sub("#", text).strip().lower()


def find_repeated(values_by_page: Iterable[tuple[int, str]], *, min_ratio: float = 0.6) -> set[str]:
    """Tìm các nội dung lặp lại trên phần lớn số trang (header, footer, số trang).

    Nhận các cặp ``(số trang, nội dung)`` và trả về tập fingerprint xuất hiện ở ít nhất
    ``min_ratio`` số trang. Tài liệu dưới 3 trang trả về tập rỗng vì không đủ cơ sở thống kê:
    một hợp đồng 2 trang có thể lặp tên hai bên ở cả hai trang mà đó vẫn là nội dung thật.
    """
    seen_pages: dict[str, set[int]] = {}
    pages: set[int] = set()
    for page, value in values_by_page:
        key = fingerprint(value)
        pages.add(page)
        if key:
            seen_pages.setdefault(key, set()).add(page)

    if len(pages) < 3:
        return set()
    threshold = max(2, int(len(pages) * min_ratio))
    return {key for key, found in seen_pages.items() if len(found) >= threshold}
