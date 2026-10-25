"""Bọc Docling: từ file gốc ra danh sách khối có số trang và bounding box.

Bounding box được giữ lại vì nó là thứ cho phép trích dẫn chỉ đúng vị trí trên trang,
không chỉ đúng số trang. Đó cũng là lý do chọn Docling thay vì một parser chỉ trả text.
"""

import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from io import BytesIO

from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import EasyOcrOptions, PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import DocItemLabel, TableItem, TextItem

from app.db.models import BlockType
from app.ingestion.normalize import find_repeated, fingerprint, normalize_text
from app.ingestion.ocr import pages_needing_ocr

_LABEL_TO_BLOCK_TYPE = {
    DocItemLabel.TITLE: BlockType.HEADING,
    DocItemLabel.SECTION_HEADER: BlockType.HEADING,
    DocItemLabel.TABLE: BlockType.TABLE,
    DocItemLabel.LIST_ITEM: BlockType.LIST,
    DocItemLabel.CAPTION: BlockType.CAPTION,
    DocItemLabel.TEXT: BlockType.TEXT,
    DocItemLabel.PARAGRAPH: BlockType.TEXT,
}
# Header/footer do Docling nhận ra thì bỏ thẳng, không cần dò theo thống kê.
_DROP_LABELS = {DocItemLabel.PAGE_HEADER, DocItemLabel.PAGE_FOOTER}


@dataclass(frozen=True)
class ParsedBlock:
    page: int
    position: int
    block_type: str
    content: str
    heading_path: str | None
    bbox: dict | None
    from_ocr: bool


@dataclass
class ParseResult:
    page_count: int
    blocks: list[ParsedBlock]
    docling_dict: dict
    ocr_pages: set[int] = field(default_factory=set)
    seconds: float = 0.0


def build_converter(
    *, do_ocr: bool, ocr_langs: tuple[str, ...] = ("vi", "en")
) -> DocumentConverter:
    options = PdfPipelineOptions(do_ocr=do_ocr, do_table_structure=True)
    if do_ocr:
        options.ocr_options = EasyOcrOptions(lang=list(ocr_langs))
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )


def parse_document(
    data: bytes, filename: str, *, ocr_langs: tuple[str, ...] = ("vi", "en")
) -> ParseResult:
    """Parse file và trả về các khối đã chuẩn hoá.

    OCR được quyết định theo từng trang: trang nào có đủ ký tự trong text layer thì giữ
    nguyên text đó. Nếu cả tài liệu không có trang nào cần OCR thì không bật engine OCR,
    tránh tải model và tiết kiệm vài phút cho mỗi tài liệu in số.
    """
    ocr_pages = pages_needing_ocr(data) if filename.lower().endswith(".pdf") else set()
    started = time.monotonic()
    converter = build_converter(do_ocr=bool(ocr_pages), ocr_langs=ocr_langs)
    source = DocumentStream(name=filename, stream=BytesIO(data))
    document = converter.convert(source).document
    seconds = time.monotonic() - started

    blocks = list(_collect_blocks(document, ocr_pages))
    return ParseResult(
        page_count=len(document.pages) or 1,
        blocks=_drop_repeated(blocks),
        docling_dict=document.export_to_dict(),
        ocr_pages=ocr_pages,
        seconds=seconds,
    )


def _collect_blocks(document, ocr_pages: set[int]) -> Iterator[ParsedBlock]:
    headings: dict[int, str] = {}
    position = 0
    for item, _ in document.iterate_items():
        label = getattr(item, "label", None)
        if label in _DROP_LABELS:
            continue

        content = _content_of(item, document)
        if not content:
            continue

        page, bbox = _provenance(item, document)
        block_type = _LABEL_TO_BLOCK_TYPE.get(label, BlockType.OTHER)

        if block_type is BlockType.HEADING:
            level = getattr(item, "level", 1) or 1
            headings = {lv: text for lv, text in headings.items() if lv < level}
            headings[level] = content

        yield ParsedBlock(
            page=page,
            position=position,
            block_type=block_type.value,
            content=content,
            heading_path=" > ".join(headings[lv] for lv in sorted(headings)) or None,
            bbox=bbox,
            from_ocr=page in ocr_pages,
        )
        position += 1


def _content_of(item, document) -> str:
    """Bảng giữ nguyên dạng markdown thành một khối riêng, không trộn vào đoạn văn."""
    if isinstance(item, TableItem):
        return normalize_text(item.export_to_markdown(document))
    if isinstance(item, TextItem):
        return normalize_text(item.text)
    return ""


def _provenance(item, document) -> tuple[int, dict | None]:
    prov = getattr(item, "prov", None)
    if not prov:
        return 1, None
    first = prov[0]
    page = first.page_no
    box = first.bbox
    if box is None:
        return page, None
    size = document.pages[page].size if page in document.pages else None
    return page, {
        "l": round(box.l, 2),
        "t": round(box.t, 2),
        "r": round(box.r, 2),
        "b": round(box.b, 2),
        "origin": str(box.coord_origin.value),
        "page_width": round(size.width, 2) if size else None,
        "page_height": round(size.height, 2) if size else None,
    }


def _drop_repeated(blocks: list[ParsedBlock]) -> list[ParsedBlock]:
    """Bỏ các khối lặp lại trên phần lớn số trang mà Docling không gắn nhãn header/footer.

    Chỉ áp dụng cho khối văn bản ngắn: một điều khoản dài giống nhau giữa các trang là nội
    dung thật, còn ``Trang 3/25`` thì không.
    """
    candidates = [(b.page, b.content) for b in blocks if len(b.content) <= 80]
    repeated = find_repeated(candidates)
    if not repeated:
        return blocks
    kept = [b for b in blocks if not (len(b.content) <= 80 and fingerprint(b.content) in repeated)]
    return [
        ParsedBlock(**{**block.__dict__, "position": index}) for index, block in enumerate(kept)
    ]
