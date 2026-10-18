# Mask mới cho thư mục cần sửa

Mã nguồn ở `tools/segmentation/` và `tools/validation/`. Thư mục kết quả lịch sử
`mask_moi_can_sua/` không hiện diện; không có bộ 317 mask để chuyển hoặc resume.
Các số liệu lịch sử bên dưới được giữ nguyên và không xác nhận kết quả đang tồn tại.
Dùng `.venv-image-tools/bin/python` với `requirements_image_tools.txt` ở root;
bộ chỉnh/xác minh dùng `.venv/bin/python`. Xem [môi trường Python](../python_environments.md).
Đích cho lần tạo mới là `outputs/segmentation/mask_regeneration/`, tách khỏi GrabCut.
Xem [báo cáo chuyển kết quả](../results_migration.md).

Chương trình `regenerate_masks.py` lấy danh sách ảnh phủ PNG trong
`outputs/segmentation/grabcut/overlays/needs_revision/`, ghép tên với manifest cũ và chạy U²-Net trên
**ảnh gốc** trong `data/cropped_images_576x384/`. Không đưa ảnh đã tô đỏ vào mô hình.

Kết quả nằm riêng tại `outputs/segmentation/mask_regeneration/`:

- `masks/<tên gốc>.png`: mask nhị phân 0/255, kích thước gốc 576 × 384.
- `overlays/needs_revision/<tên gốc>.png`: ảnh phủ mới; màu đỏ là phần nền bị loại.
- `quicklooks/batch_*.jpg`: mỗi bảng tối đa 8 ảnh, gồm **ảnh gốc / ảnh phủ cũ /
  mask mới / ảnh phủ mới**. Ảnh thu nhỏ trong bảng giữ đúng tỉ lệ.
- `manifest.csv`: nguồn, đường dẫn, kích thước, pixel/tỉ lệ mask, dấu vết kết quả cũ,
  trạng thái xử lý, trạng thái duyệt và SHA-256.
- `review_priority.csv`: ảnh lỗi hoặc có cờ để ưu tiên xem.
- `errors.csv`, `summary.json`, `run_config.json`, `full_run.log`: nhật ký và cấu hình.

Mô hình có đầu vào 320 × 320. Ảnh 576 × 384 được thu nhỏ thành 320 × 213 rồi
thêm viền để đủ kích thước đầu vào. Sau suy luận, bỏ viền và trả bản đồ đầu ra về
576 × 384, rồi lấy ngưỡng 0,5 thành mask. Không ép ảnh 3:2 thành hình vuông,
không cắt lại ảnh nguồn; không dùng opening làm mất các bộ phận mảnh.
Mô hình cục bộ ở `~/.cache/animal-crop/u2net.onnx`; SHA-256 và phiên bản thư viện
được lưu trong cấu hình. Chương trình không tải mô hình hoặc cài thư viện tự động.

Mask mới đều có `review_status=chua_duyet`; không tự chuyển ảnh sang `đạt`.
`status=success` chỉ xác nhận đã tạo được tệp. Các cờ về diện tích quá nhỏ/lớn,
chạm mép hoặc thay đổi nhiều so với mask trước chỉ giúp ưu tiên xem. Đặc biệt,
`changed_pixel_fraction` là mức khác biệt giữa hai mask, không phải độ chính xác
phân đoạn hoặc bằng chứng mask nào đúng hơn. Không trích xuất vector 400 chiều.

Các mask/ảnh phủ đã chỉnh tay hoặc đã phân loại trong `outputs/segmentation/grabcut/` được giữ
lại. Tệp `outputs/segmentation/mask_regeneration_source_before.json` cạnh đích kết quả ghi kiểm kê
nội dung và mtime của ảnh nguồn cùng kết quả cũ để đối chiếu sau lần chạy.

Không có hàng đợi cần sửa trong cây hiện tại (812 overlay đang ở thư mục phẳng).
Chỉ tạo lần chạy mới sau khi người duyệt phân loại vào `overlays/needs_revision/`
và đồng bộ manifest. Dùng đầu ra mới chưa tồn tại; không dùng `--resume` cho lần đầu:

```sh
.venv-image-tools/bin/python tools/segmentation/regenerate_masks.py --output-dir outputs/segmentation/mask_regeneration
```

Với lần chạy mới đã được tạo bằng đúng mã/thư viện/tham số, có thể tiếp tục cùng
lệnh với `--resume`. Kiểm kê lịch sử được giữ nguyên cả hash và mtime; nó có thể
báo các thay đổi đã có trước lần sắp xếp này. Hãy ghi một kiểm kê mới cho lần chạy
mới, không ghi đè kiểm kê lịch sử.

Sau khi có bộ mới, mở chỉnh bằng:

```sh
.venv/bin/python tools/segmentation/edit_masks.py --output-dir outputs/segmentation/mask_regeneration
```

Chỉ chuyển sang `overlays/accepted/` khi người dùng chủ động lưu sau khi chỉnh
và duyệt. Công cụ xác minh ở `tools/validation/verify_regenerated_masks.py` nhận
`--output-dir`, `--previous-dir`, `--inventory`. Với lần chạy mới, truyền kiểm kê
được chụp ngay trước chính lần chạy đó; mặc định vẫn trỏ tới hồ sơ lịch sử được giữ
nguyên. Không chạy batch cùng lúc với công cụ chỉnh mask.

## Kết quả lần chạy này

Đã tạo xong **317/317 mask, 0 lỗi**, gồm 8 ảnh thử và 309 ảnh tạo thêm.
Mask và ảnh phủ đều 576 × 384. Có 40 bảng so sánh theo đợt và một bảng tổng quan
`comparison_overview.jpg` với tám nhóm động vật để mở xem nhanh.

Đã xác minh nhị phân PNG, kích thước, số pixel, ảnh phủ, SHA-256 và các bảng ảnh;
3.931 tệp ảnh nguồn/kết quả cũ giữ nguyên nội dung, kích thước và mtime. Chi tiết
trong `verification.json`. Không có lỗi được ghi trong `errors.csv`.

Có 114 ảnh được gắn cờ ưu tiên xem; con số này không phải số mask sai được xác
nhận. Đã xem trực tiếp 16 ảnh trong lần chạy, ghi rõ hai ca còn vấn đề trong
`observations.md` và `visual_review_notes.csv`. Tất cả 317 vẫn là `chua_duyet`.

Bộ mới đã mở thử bằng `MaskRepository` của công cụ chỉnh mask. Đã bổ sung việc
ghi các cột thống kê tùy chọn khi lưu manifest từ phương pháp mới, giữ các cột
truy vết riêng; cả 7 kiểm tra của công cụ chỉnh mask đều đạt trên ảnh tạm.
