# ADR 0002: Định tuyến OCR theo từng trang

Trạng thái: chấp nhận một phần (tuần 2) – lựa chọn engine OCR **chưa chốt**, chờ số đo CER.

## Bối cảnh

Tài liệu hành chính tiếng Việt thường trộn lẫn: phần chính in số có text layer sạch, phụ lục
scan đính sau. Bật OCR cho cả tài liệu thì chậm (CPU, không GPU) và không cần thiết. Tắt hẳn
thì mất toàn bộ nội dung phụ lục.

## Quyết định

Trước khi parse, đọc text layer từng trang bằng pypdfium2 và đếm ký tự
(`app/ingestion/ocr.py`). Trang dưới 100 ký tự được coi là trang scan.

Kết quả dùng cho hai việc:

1. Tài liệu không có trang nào cần OCR thì dựng Docling với `do_ocr=False`, không nạp
   engine OCR. Đo trên hoá đơn tổng hợp 1 trang: 10–13 giây thay vì phải nạp thêm EasyOCR.
2. Ghi lại từng trang đã qua OCR vào `ingest_progress.used_ocr` và
   `documents.ocr_page_count`, để sau này đo CER đúng trên nhóm trang scan.

Ngưỡng 100 ký tự: trang A4 in chữ thường có trên 1.000 ký tự, trang scan gần như bằng 0.
Đo trên hoá đơn tổng hợp: bản số 432 ký tự, bản scan 0 ký tự.

## Giới hạn đã biết

Docling nhận tham số OCR theo cả tài liệu, không theo từng trang. Hiện tại khi tài liệu có
ít nhất một trang scan thì bật `do_ocr=True` cho toàn bộ. Docling chỉ chạy OCR trên vùng
bitmap nên trang có text layer hầu như không bị ảnh hưởng, nhưng đây vẫn là xấp xỉ. Muốn
tách thật thì phải cắt PDF theo khoảng trang rồi ghép kết quả – để lại cho giai đoạn tối ưu.

## Chưa quyết định

Engine OCR vẫn là EasyOCR (`lang=["vi", "en"]`) làm mốc. Mục tiêu gợi ý là CER dưới 5% với
bản in rõ. **Chưa có số đo nào**, không trích dẫn con số nào trong README cho tới khi có.

Công cụ đo đã sẵn sàng (`scripts/ocr_benchmark.py`, hướng dẫn trong `eval/ocr/README.md`):

```bash
uv run python -m scripts.ocr_benchmark prepare data/raw/scans/*.pdf
# gõ đáp án vào eval/ocr/pages/*.gt.txt
uv run python -m scripts.ocr_benchmark run
```

Script đo CER, WER và thời gian mỗi trang, đồng thời báo thêm CER sau khi sắp xếp từ để
tách lỗi nhận dạng khỏi lỗi thứ tự đọc. Khi có kết quả, dán bảng tổng hợp vào đây kèm lựa
chọn và lý do.

## Dữ liệu scan để thử

`scripts/make_scans.py` dựng PDF chỉ có ảnh kèm nhiễu (lệch trang, mờ, hạt, giảm tương phản)
từ PDF số. Nhiễu giả không thay thế được bản chụp thật, nên bộ dữ liệu vẫn cần khoảng 10 file
in ra và chụp lại; CER sẽ được đo riêng trên hai nhóm.
