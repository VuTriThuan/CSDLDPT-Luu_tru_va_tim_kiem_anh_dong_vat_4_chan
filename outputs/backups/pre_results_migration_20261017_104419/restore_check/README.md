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
| [reports/yeu_cau_2/](reports/yeu_cau_2/) | JSON/CSV kiểm kê, snapshot và kết quả xử lý ở vị trí cũ |
| [reports/yeu_cau_2/grabcut_output/](reports/yeu_cau_2/grabcut_output/) | Mask, overlay, manifest, nhật ký và lịch sử chỉnh sửa |
| [bo_tool_anh_576x384/](bo_tool_anh_576x384/) | Môi trường công cụ ảnh, requirements và cache cũ |
| [outputs/backups/](outputs/backups/) | Bản sao lưu nguyên trạng đã xác minh |

Ba thư mục ảnh đã dùng tên mới như bảng trên; tên và nội dung từng ảnh giữ nguyên.
Kết quả phân đoạn và hai môi trường Python vẫn ở vị trí cũ. Thư mục
`reports/` ở root chứa kết quả xử lý; tài liệu phân tích nằm ở `docs/reports/`.

## Chạy công cụ

Mở Terminal tại **thư mục gốc BTL**, nơi có `README.md`, `tools/`, `data/` và `docs/`.
Các lệnh dưới chỉ hiện hướng dẫn, không chạy xử lý dữ liệu:

```sh
python3 tools/image_processing/auto_crop.py --help
python3 tools/image_processing/rename_images.py --help
python3 tools/image_processing/review_images.py --help

.venv/bin/python tools/segmentation/run_grabcut.py --help
.venv/bin/python tools/segmentation/review_overlays.py --help
.venv/bin/python tools/segmentation/edit_masks.py --help
.venv/bin/python tools/segmentation/sync_overlays.py --help
bo_tool_anh_576x384/.venv/bin/python tools/segmentation/regenerate_masks.py --help

.venv/bin/python tools/validation/audit_images.py --help
.venv/bin/python tools/validation/verify_grabcut_results.py --help
.venv/bin/python tools/validation/verify_regenerated_masks.py --help
```

`auto_crop.py` và `review_images.py` tự dùng môi trường trong
`bo_tool_anh_576x384/.venv/`; `rename_images.py` chỉ cần thư viện chuẩn. Môi trường
gốc `.venv/` có OpenCV để chạy GrabCut/editor/sync. Tạo lại mask bằng U²-Net dùng
môi trường công cụ ảnh theo lệnh trên. Hướng dẫn Windows nằm trong
[image_tools.md](docs/guides/image_tools.md).

Các ví dụ có xử lý ảnh, `--setup`, `--resume` hoặc `--apply` được giải thích trong
từng hướng dẫn. `--resume` kiểm tra cấu hình, hash mã và phiên bản thư viện;
kết quả cũ có thể bị từ chối nếu các giá trị đã khác. Không sửa config để ép tiếp tục.

## Kiểm thử và tiến độ sắp xếp

Chạy từ root bằng đúng môi trường của từng nhóm:

```sh
PYTHONDONTWRITEBYTECODE=1 bo_tool_anh_576x384/.venv/bin/python -B -m unittest discover -s tests/image_processing -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests/validation -v
```

- [Kế hoạch sắp xếp và quy trình khôi phục](docs/migration_plan.md).
- [Bước chuyển mã nguồn và kết quả kiểm thử](docs/source_migration.md).
- [Bước chuyển tài liệu và kiểm tra liên kết](docs/documentation_migration.md).

Hiện đã chuyển mã nguồn, tài liệu và đổi tên ba thư mục ảnh. Chưa chuyển kết quả xử lý.
Xem [bước chuyển dữ liệu và kiểm tra trạng thái](docs/data_migration.md).
