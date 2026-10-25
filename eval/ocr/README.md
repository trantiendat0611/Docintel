# Thí nghiệm OCR

Chọn engine OCR cho tiếng Việt dựa trên số đo, không dựa trên cảm nhận. Kết quả cuối ghi
vào `docs/adr/0002-ocr-routing.md`.

## Quy trình

```bash
# 1. Render trang scan ra ảnh, tạo file đáp án rỗng
uv run python -m scripts.ocr_benchmark prepare data/raw/scans/*.pdf

# 2. Gõ tay đáp án vào từng eval/ocr/pages/<tên>.gt.txt

# 3. Đo
uv run python -m scripts.ocr_benchmark run
```

Báo cáo ra `eval/reports/ocr/<thời điểm>/report.md`, kèm bản OCR từng trang để phân tích lỗi.

## Gõ đáp án thế nào

- Gõ đúng những gì nhìn thấy trên trang, giữ nguyên dấu và chữ hoa/thường.
- Mỗi dòng trên trang là một dòng trong file.
- Bảng: gõ nội dung các ô, cách nhau bằng dấu cách. Không gõ ký tự kẻ bảng.
- Bỏ qua header/footer lặp và số trang.

Theo kế hoạch cần 20 trang scan, trong đó gõ đáp án cho ít nhất 5 trang.

## Chọn trang

Lấy cả hai nhóm, vì CER của chúng khác nhau đáng kể:

- **Scan giả** từ `scripts/make_scans.py`: nhiễu sinh bằng thuật toán, dễ hơn thực tế.
- **Bản chụp thật**: in tài liệu ra rồi chụp hoặc scan lại. Cần khoảng 10 file.

Báo cáo nên tách số đo của hai nhóm, nếu không con số sẽ lạc quan hơn thực tế.

## Đọc hai cột CER

| Cột | Ý nghĩa |
|---|---|
| `CER` | Tỉ lệ ký tự sai, tính cả thứ tự. Đây là số so với mục tiêu dưới 5%. |
| `CER (sắp xếp từ)` | Sắp xếp toàn bộ từ trước khi so, nên không phạt lỗi thứ tự. |

Chênh lệch lớn giữa hai cột nghĩa là engine đọc đúng chữ nhưng trả về sai thứ tự đọc.
Đây là vấn đề của tầng layout chứ không phải của engine, và sửa bằng cách khác.

Sắp xếp theo từ chứ không theo dòng là có chủ ý: engine cắt dòng theo vùng nhận dạng
được, không trùng cách xuống dòng của đáp án. Đo thử trên scan giả cho thấy so theo
dòng ra 63–69% trong khi so theo từ ra 0,5–1,1% trên cùng dữ liệu.

## Engine

| Engine | Cài đặt |
|---|---|
| `easyocr` | Có sẵn (đi kèm `docling[easyocr]`), tự tải model lần chạy đầu |
| `tesseract` | Cần binary hệ thống và `vie.traineddata`. Windows: https://github.com/UB-Mannheim/tesseract/wiki |

Engine thiếu điều kiện sẽ bị bỏ qua kèm lý do trong báo cáo, không làm hỏng cả lần chạy.

PaddleOCR-VL và SenOCR-Vi chưa được thêm: cả hai cần adapter riêng. Thêm một mục vào
`ENGINES` trong `scripts/ocr_benchmark.py` là đủ để đưa vào so sánh.
