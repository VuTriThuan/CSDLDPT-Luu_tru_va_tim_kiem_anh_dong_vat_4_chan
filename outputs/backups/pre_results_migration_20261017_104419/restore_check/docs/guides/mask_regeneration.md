# Mask mới cho thư mục cần sửa

Mã nguồn hiện ở `tools/segmentation/` và `tools/validation/`, dữ liệu/kết quả vẫn
dùng các thư mục ảnh mới; kết quả vẫn ở vị trí cũ. Thư mục kết quả `mask_moi_can_sua/` đang vắng mặt tại lần chuyển mã;
phần kết quả bên dưới mô tả lần chạy lịch sử. Xem [báo cáo chuyển mã](../source_migration.md).

Chương trình `regenerate_masks.py` lấy danh sách ảnh phủ PNG trong
`grabcut_output/overlays/cần sửa/`, ghép tên với manifest cũ và chạy U²-Net trên
**ảnh gốc** trong `data/cropped_images_576x384/`. Không đưa ảnh đã tô đỏ vào mô hình.

Kết quả nằm riêng tại `reports/yeu_cau_2/mask_moi_can_sua/`:

- `masks/<tên gốc>.png`: mask nhị phân 0/255, kích thước gốc 576 × 384.
- `overlays/cần sửa/<tên gốc>.png`: ảnh phủ mới; màu đỏ là phần nền bị loại.
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

Các mask/ảnh phủ đã chỉnh tay hoặc đã phân loại trong `grabcut_output/` được giữ
lại. Tệp `mask_moi_can_sua_truoc_khi_chay.json` cạnh thư mục kết quả ghi kiểm kê
nội dung và mtime của ảnh nguồn cùng kết quả cũ để đối chiếu sau lần chạy.

Công việc đã được chạy trực tiếp trong phiên làm việc. Chỉ khi cần chạy tiếp mới
bị ngắt, dùng lệnh sau từ thư mục `BTL`:

```sh
bo_tool_anh_576x384/.venv/bin/python tools/segmentation/regenerate_masks.py --resume
```

`--resume` kiểm tra nguồn, mask/ảnh phủ cũ và kết quả mới bằng SHA-256 trước khi
bỏ qua. Đổi mô hình, mã hoặc tham số thì chọn `--output-dir` khác. Có thể dùng
`--limit 8` với một thư mục đầu ra mới để chạy thử.

Muốn chỉnh tiếp một mask mới bằng công cụ đã có, mở bộ kết quả mới:

```sh
.venv/bin/python tools/segmentation/edit_masks.py --output-dir reports/yeu_cau_2/mask_moi_can_sua
```

Công cụ này chỉ chuyển mask vào `overlays/đạt/` khi người dùng chủ động lưu sau
khi chỉnh và duyệt. Không chạy chương trình batch cùng lúc với công cụ chỉnh mask.

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
