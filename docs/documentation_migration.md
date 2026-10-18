# Báo cáo chuyển tài liệu BTL

> Ghi nhận sau bước chuyển dữ liệu: các đường dẫn dữ liệu trong báo cáo giai đoạn này
> mô tả mốc trước khi đổi tên. Vị trí hiện tại và chuyển đổi state được ghi trong
> [data_migration.md](data_migration.md); các phụ lục kiểm kê lịch sử giữ nguyên.

Ngày thực hiện: **17/10/2026, UTC+07:00**. Chỉ thực hiện giai đoạn tài liệu theo
phạm vi bổ sung của người dùng; dữ liệu và kết quả xử lý chưa chuyển hoặc đổi tên.

## Tệp đã chuyển

| Vị trí trước bước này | Vị trí hiện tại |
|---|---|
| `bao_cao_giong_khac_dong_vat.md` | [docs/reports/animal_comparison.md](reports/animal_comparison.md) |
| `bao_cao_yeu_cau_2_thuoc_tinh.md` | [docs/reports/search_feature_design.md](reports/search_feature_design.md) |
| `bo_tool_anh_576x384/HUONG_DAN.md` | [docs/guides/image_tools.md](guides/image_tools.md) |
| `reports/yeu_cau_2/README_GRABCUT.md` | [docs/guides/grabcut.md](guides/grabcut.md) |
| `reports/yeu_cau_2/README_MASK_MOI_CAN_SUA.md` | [docs/guides/mask_regeneration.md](guides/mask_regeneration.md) |

Không để bản tài liệu trùng ở vị trí cũ. Các thư mục cũ vẫn giữ requirements,
môi trường Python, cache, snapshot và kết quả xử lý như trước.

[README.md ở root](../README.md) đã có mục lục năm tài liệu, giải thích các nhóm mã,
vị trí dữ liệu/kết quả và môi trường, cùng lệnh gọi từ thư mục gốc BTL.
[migration_plan.md](migration_plan.md) được cập nhật tên đích của năm tài liệu và
ghi nhận giai đoạn này. Các phụ lục kiểm kê ban đầu và hồ sơ chuyển mã được giữ
nguyên để truy nguyên; ánh xạ bổ sung hiện tại ở
[document_mapping.json](documentation_migration_audit/document_mapping.json).

## Nội dung được giữ nguyên

- Hai báo cáo phân tích **chỉ thay đích liên kết**. Đã so sánh chính xác toàn bộ văn bản
  sau khi chuẩn hóa đích liên kết với bản trước chuyển: câu chữ, bảng, số liệu,
  công thức, danh sách ảnh, kết luận và các giới hạn lịch sử không đổi.
- Ba hướng dẫn được đổi các liên kết theo vị trí mới. Riêng hướng dẫn ảnh còn sửa
  lệnh unittest và câu chỉ dẫn cwd về root BTL; hướng dẫn GrabCut chỉ rõ interpreter
  cài OpenCV và cách chọn môi trường riêng. Phiên bản thư viện và số liệu các lần
  chạy cũ được giữ nguyên. Hướng dẫn tạo lại mask chỉ thay đích liên kết.
- Không biến số liệu quan sát cũ thành kiểm kê mới. Chẳng hạn các mô tả về 317 mask,
  kết quả duyệt và việc đã chạy mô hình trong các hướng dẫn vẫn thuộc lần chạy lịch sử.

Chi tiết đối chiếu: [content_preservation.json](documentation_migration_audit/content_preservation.json)
và [document_changes.diff](documentation_migration_audit/document_changes.diff).

## Liên kết và lệnh chạy

Liên kết trong các báo cáo hiện được tính từ `docs/reports/`, ví dụ ảnh dùng
`../../data/anh-da-cat-576x384/...`, mã dùng `../../tools/...` và artifact dùng
`../../reports/yeu_cau_2/...`. Liên kết giữa hai báo cáo dùng tên mới trong cùng thư mục.
Các hướng dẫn dùng `../source_migration.md` khi trỏ tới hồ sơ chuyển mã.

**Lệnh trong hướng dẫn vẫn chạy từ root BTL**, không đổi cwd sang `docs/guides/`.
Mã giữ vị trí đã hoàn thành ở bước chuyển mã:

```sh
python3 tools/image_processing/auto_crop.py --help
python3 tools/image_processing/review_images.py --help
.venv/bin/python tools/segmentation/run_grabcut.py --help
.venv/bin/python tools/segmentation/edit_masks.py --help
bo_tool_anh_576x384/.venv/bin/python tools/segmentation/regenerate_masks.py --help
.venv/bin/python tools/validation/audit_images.py --help
```

Trong lần làm việc này chỉ thực thi **11 lệnh `--help` trong README**, tất cả đạt;
không thực thi các lệnh batch, cài thư viện, `--resume`, `--apply` hoặc mở GUI.
Các ví dụ PowerShell được kiểm tra đích script và vị trí môi trường trên văn bản,
không được tuyên bố đã chạy trên Windows.

Hai liên kết nguồn tham khảo vốn trỏ tuyệt đối tới Downloads được đổi sang **bản sao
nguyên byte có sẵn** dưới `outputs/backups/pre_migration_20261017_100229/external_dependencies/`:
`feature_extractors.py` và `reference_readme.md`. Đã đối chiếu chúng với tệp gốc bằng
SHA-256; không thay nguồn tham khảo bằng mã triển khai của dự án.
[reference_redirects.json](documentation_migration_audit/reference_redirects.json) ghi hash và đích cũ/mới.

Đã kiểm tra các tài liệu đang dùng: README, ba hồ sơ kế hoạch/chuyển bước và năm
tài liệu vừa chuyển. Kết quả chi tiết:

- [link_verification.json](documentation_migration_audit/link_verification.json): tổng hợp kiểm tra liên kết.
- [local_links.json](documentation_migration_audit/local_links.json): từng đích liên kết tài liệu, mã, ảnh và thư mục.
- [linked_images.json](documentation_migration_audit/linked_images.json): **40 ảnh duy nhất**, tương ứng **111 lần dẫn ảnh**; đọc/giải mã được toàn bộ, có SHA-256.
- [command_references.json](documentation_migration_audit/command_references.json): kiểm tra đường dẫn script trong lệnh theo root BTL.
- [readme_command_checks.json](documentation_migration_audit/readme_command_checks.json): kết quả 11 lệnh `--help`.

Các liên kết HTTP giữ nguyên; không kiểm tra tình trạng máy chủ ngoài qua mạng trong
lần chuyển tài liệu này. Danh sách liên kết HTTP có cú pháp Markdown ở
[external_links.json](documentation_migration_audit/external_links.json).

## Tham chiếu lịch sử còn thiếu

Trong `animal_comparison.md` có nhắc bằng inline code tới
`data/anh-da-cat-576x384/thong_ke_loai_dong_vat.csv`, nhưng tệp này **đã vắng mặt trước
khi chuyển tài liệu**. Đây không phải liên kết mới bị hỏng do đổi vị trí. Không tạo
tệp CSV thay thế, không sửa số đếm hoặc xóa nhận xét lịch sử để che việc thiếu tệp.

Các thiếu vắng đã ghi ở bước trước vẫn giữ nguyên: thư mục kết quả `mask_moi_can_sua/`,
hàng đợi overlay cần sửa và một số ảnh bảng trung gian đã được lược bỏ. Bản hướng dẫn
đã phân biệt kết quả lịch sử với tình trạng hiện tại; không tạo lại ảnh hoặc mask.

## Sao lưu, xác minh phạm vi và điểm dừng

Trước khi chuyển đã tạo và đọc lại
[documents_before.tar](documentation_migration_audit/documents_before.tar), gồm năm
tài liệu gốc, README và kế hoạch ngay trước bước này. SHA-256 archive ở
[documents_before.tar.sha256](documentation_migration_audit/documents_before.tar.sha256).
Archive nguyên trạng toàn dự án đã xác minh từ bước chuẩn bị vẫn được giữ nguyên.

[protected_files_verification.json](documentation_migration_audit/protected_files_verification.json)
ghi đối chiếu SHA-256, size, mtime, mode và symlink của **20.746 tệp/symlink** ngoài
phạm vi sửa tài liệu, gồm mã, kiểm thử, ảnh, state, manifest, lịch sử chỉnh mask,
kết quả, cache và hai môi trường. Không chạy lại kiểm thử xử lý ảnh vì bước này
không sửa mã; đã kiểm tra các lệnh `--help`, liên kết và bảo toàn nội dung tài liệu.

Để hoàn tác riêng giai đoạn tài liệu, đóng trình sửa đang giữ các tệp này; xác minh
archive nhỏ, giải nén nó vào thư mục trống rồi so với ánh xạ và hash trước/sau. Giữ một
bản các tài liệu mới trước khi khôi phục về tên cũ; không ghi đè thay đổi phát sinh
sau bước này và không động tới `data/` hoặc kết quả. Quy trình khôi phục toàn dự án
vẫn nằm trong kế hoạch.

**Dừng tại giai đoạn tài liệu.** Chưa đổi tên `data/`, ảnh, state hoặc chuyển kết quả
xử lý; chưa di chuyển môi trường Python, chưa thay đổi thuật toán hay schema resume.
