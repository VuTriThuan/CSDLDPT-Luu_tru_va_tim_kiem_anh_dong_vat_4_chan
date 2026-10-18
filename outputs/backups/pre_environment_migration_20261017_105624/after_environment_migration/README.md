# Lưu trữ và tìm kiếm ảnh động vật bốn chân

Dự án gồm công cụ chuẩn bị ảnh, tạo và duyệt mask, cùng báo cáo so sánh động vật
và thiết kế bộ thuộc tính tìm kiếm. Phần thiết kế đặc trưng là đề xuất phân tích;
chưa phải hệ thống tìm kiếm đã triển khai hoặc đã đánh giá.

## Đọc tài liệu

| Tài liệu | Nội dung |
|---|---|
| [So sánh ảnh động vật](docs/reports/animal_comparison.md) | Đặc điểm giống/khác, các cặp ảnh minh họa và phạm vi quan sát |
| [Thiết kế thuộc tính tìm kiếm](docs/reports/search_feature_design.md) | Phân tích mã tham khảo, đề xuất đặc trưng và giới hạn của kết quả |
| [Hướng dẫn công cụ ảnh](docs/guides/image_tools.md) | Cài môi trường, cắt ảnh, duyệt/lật/loại ảnh và kiểm thử |
| [Hướng dẫn GrabCut](docs/guides/grabcut.md) | Tạo mask, duyệt overlay, chỉnh mask và đồng bộ |
| [Hướng dẫn tạo lại mask](docs/guides/mask_regeneration.md) | Tạo mask U²-Net từ hàng đợi và kiểm tra kết quả lịch sử |

Các báo cáo giữ số liệu và kết luận theo thời điểm quan sát. Một số kết quả hoặc
tệp trung gian được mô tả trong lịch sử hiện không còn trên cây; xem
[báo cáo kiểm tra tài liệu](docs/documentation_migration.md) để biết phạm vi kiểm tra.

## Cấu trúc hiện tại

| Vị trí | Vai trò |
|---|---|
| [docs/reports/](docs/reports/) | Hai báo cáo phân tích |
| [docs/guides/](docs/guides/) | Ba hướng dẫn sử dụng |
| [tools/image_processing/](tools/image_processing/) | Cắt ảnh, xem trước đổi tên, duyệt ảnh |
| [tools/segmentation/](tools/segmentation/) | Tạo, duyệt, chỉnh và đồng bộ mask/overlay |
| [tools/validation/](tools/validation/) | Kiểm kê ảnh và xác minh kết quả |
| [tests/](tests/) | Kiểm thử compatibility và chuyển mã |
| [data/source_images/](data/source_images/) | Ảnh nguồn |
| [data/cropped_images_576x384/](data/cropped_images_576x384/) | Ảnh cắt đang dùng |
| [data/rejected_crops/](data/rejected_crops/) | Ảnh cắt đã loại khi duyệt |
| [outputs/inventory/](outputs/inventory/) | Kiểm kê ảnh, danh sách ảnh đã xem, số liệu và môi trường mẫu GrabCut |
| [outputs/segmentation/grabcut/](outputs/segmentation/grabcut/) | Mask, overlay, manifest, nhật ký và lịch sử chỉnh sửa |
| [bo_tool_anh_576x384/](bo_tool_anh_576x384/) | Requirements và cache lịch sử; không còn môi trường đang dùng |
| [outputs/backups/](outputs/backups/) | Bản sao lưu nguyên trạng đã xác minh |

Ba thư mục ảnh đã dùng tên mới như bảng trên; tên và nội dung từng ảnh giữ nguyên.
Kết quả GrabCut nằm ở `outputs/segmentation/grabcut/`; cấu hình chạy nằm trong bộ kết quả,
kiểm kê nguồn trước chạy ở `provenance/source_before.json`. Hai môi trường hiện dùng là `.venv/` và `.venv-image-tools/` ở root.
`reports/` chỉ còn cache cũ và metadata hệ thống. Bộ mask tạo lại được mô tả trong lịch sử
không hiện diện; kiểm kê trước chạy của nó ở `outputs/segmentation/mask_regeneration_source_before.json`.

## Python và phụ thuộc

Dùng **Python 3.10.11 64-bit**, cấu hình ở `.python-version`. Hai bộ phiên bản
được giữ riêng để tiếp tục dùng các thư viện đã kiểm chứng trước khi sắp xếp:

| Môi trường | Thư viện chính | Công cụ |
|---|---|---|
| `.venv/` | NumPy 1.26.4, Pillow 12.3.0, OpenCV headless 4.11.0.86, ONNX Runtime 1.23.2 | GrabCut, editor/sync/review overlay, toàn bộ validation, đổi tên ảnh |
| `.venv-image-tools/` | NumPy 2.2.6, Pillow 11.3.0, ONNX Runtime 1.23.2, certifi 2026.7.22 | Cắt/duyệt ảnh, tạo lại mask U²-Net |

Cấu hình runtime và phụ thuộc gián tiếp được ghim ở
[requirements.txt](requirements.txt) và [requirements_image_tools.txt](requirements_image_tools.txt).
Tkinter/Tcl/Tk đi kèm Python, không cài bằng pip. Trên máy hiện tại không cần cài
lại; các lệnh sau dành cho máy mới với Python 3.10.11:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
python3 -m venv .venv-image-tools
.venv-image-tools/bin/python -m pip install --only-binary=:all: -r requirements_image_tools.txt
```

Không chuyển nguyên thư mục venv khi đổi máy/đường dẫn dự án; tạo lại tại đích.
Bản wheel có SHA-256 dùng để cài lại offline trên macOS Intel/Python 3.10 và
kiểm kê đầy đủ nằm trong [báo cáo môi trường](docs/python_environments.md).

## Chạy công cụ

Mở Terminal tại **thư mục gốc BTL**, nơi có `README.md`, `tools/`, `data/` và `docs/`.
Các lệnh dưới chỉ hiện hướng dẫn, không chạy xử lý dữ liệu:

```sh
.venv-image-tools/bin/python tools/image_processing/auto_crop.py --help
.venv/bin/python tools/image_processing/rename_images.py --help
.venv-image-tools/bin/python tools/image_processing/review_images.py --help

.venv/bin/python tools/segmentation/run_grabcut.py --help
.venv/bin/python tools/segmentation/review_overlays.py --help
.venv/bin/python tools/segmentation/edit_masks.py --help
.venv/bin/python tools/segmentation/sync_overlays.py --help
.venv-image-tools/bin/python tools/segmentation/regenerate_masks.py --help

.venv/bin/python tools/validation/audit_images.py --help
.venv/bin/python tools/validation/verify_grabcut_results.py --help
.venv/bin/python tools/validation/verify_regenerated_masks.py --help
```

`auto_crop.py` và `review_images.py` cũng tự chọn `.venv-image-tools/` khi được
khởi chạy bằng Python khác. `rename_images.py` chỉ cần thư viện chuẩn; dùng
`.venv/` cho nhất quán. Hướng dẫn Windows cho nhóm công cụ ảnh nằm trong
[image_tools.md](docs/guides/image_tools.md).

Các ví dụ có xử lý ảnh, `--setup`, `--resume` hoặc `--apply` được giải thích trong
từng hướng dẫn. `--resume` kiểm tra cấu hình, hash mã và phiên bản thư viện;
kết quả cũ có thể bị từ chối nếu các giá trị đã khác. Không sửa config để ép tiếp tục.

## Kiểm thử và tiến độ sắp xếp

Chạy từ root bằng đúng môi trường của từng nhóm:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-image-tools/bin/python -B -m unittest discover -s tests/image_processing -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests/validation -v
```

- [Kế hoạch sắp xếp và quy trình khôi phục](docs/migration_plan.md).
- [Bước chuyển mã nguồn và kết quả kiểm thử](docs/source_migration.md).
- [Bước chuyển tài liệu và kiểm tra liên kết](docs/documentation_migration.md).

Hiện đã chuyển mã nguồn, tài liệu, ba thư mục ảnh và kết quả GrabCut.
Xem [bước chuyển kết quả, toàn vẹn và resume](docs/results_migration.md).
Xem [bước chuyển dữ liệu và kiểm tra trạng thái](docs/data_migration.md).

Đã chuẩn hóa môi trường Python; xem [kiểm tra môi trường và sao lưu](docs/python_environments.md).
