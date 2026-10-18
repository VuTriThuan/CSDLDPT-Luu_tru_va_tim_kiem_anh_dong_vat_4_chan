# Bản sao lưu của dự án

Toàn bộ dữ liệu của **3,469 tệp gốc** đã được đưa lên nhánh `main` và
có thể duyệt trong tab **Code**. Có **3,464 tệp** lưu nguyên dạng;
**5 tệp lớn** được chia thành **125 phần**, mỗi phần tối đa **48 MiB**.
Nội dung các bản sao lưu gốc được giữ nguyên.

## Các thư mục

- [pre_data_migration_20261017_103325/](pre_data_migration_20261017_103325/)
- [pre_environment_migration_20261017_105624/](pre_environment_migration_20261017_105624/)
- [pre_migration_20261017_100229/](pre_migration_20261017_100229/)
- [pre_results_migration_20261017_104419/](pre_results_migration_20261017_104419/)
- [pre_verification_20261017_111334/](pre_verification_20261017_111334/)

[inventory.csv](inventory.csv) ghi đường dẫn, kích thước, SHA-256 và cách lưu
của toàn bộ tệp gốc. `git` là tệp nguyên dạng; `git-parts` là tệp cần ghép.
Các tệp cache và metadata nằm trong snapshot cũng được giữ nguyên.

## Các tệp được chia phần

| Tệp gốc | Thư mục chứa các phần | Số phần |
|---|---|---:|
| `pre_data_migration_20261017_103325/before_data_migration.tar` | [before_data_migration.tar.parts/](pre_data_migration_20261017_103325/before_data_migration.tar.parts/) | 3 |
| `pre_environment_migration_20261017_105624/before_environment_migration.tar` | [before_environment_migration.tar.parts/](pre_environment_migration_20261017_105624/before_environment_migration.tar.parts/) | 17 |
| `pre_migration_20261017_100229/external_dependencies/u2net.onnx` | [u2net.onnx.parts/](pre_migration_20261017_100229/external_dependencies/u2net.onnx.parts/) | 4 |
| `pre_migration_20261017_100229/project_snapshot.tar` | [project_snapshot.tar.parts/](pre_migration_20261017_100229/project_snapshot.tar.parts/) | 89 |
| `pre_results_migration_20261017_104419/before_results_migration.tar` | [before_results_migration.tar.parts/](pre_results_migration_20261017_104419/before_results_migration.tar.parts/) | 12 |

## Khôi phục sau khi clone hoặc tải ZIP

Mở Terminal tại thư mục gốc dự án:

```sh
python3 outputs/backups/restore_large_files.py
```

Cần Python 3.10 trở lên, chỉ dùng thư viện chuẩn. Công cụ đọc
[parts-manifest.json](parts-manifest.json), kiểm tra SHA-256 từng phần và
từng tệp hoàn chỉnh, rồi tạo lại 5 tệp lớn tại đúng đường dẫn gốc. Cần thêm
khoảng **5,8 GiB** dung lượng trống để ghép đầy đủ. Các phần gốc vẫn được giữ lại.

Nếu tệp đích đã tồn tại và đúng SHA-256, công cụ bỏ qua. Nếu khác nội dung,
công cụ báo lỗi và giữ nguyên tệp đang có. Chỉ kiểm tra các phần mà không ghi
tệp khôi phục:

```sh
python3 outputs/backups/restore_large_files.py --verify-only
```

Sau khi ghép xong, dùng các hướng dẫn khôi phục snapshot trong
[migration_verification.md](../../docs/migration_verification.md).

## Bản đóng gói trên Release

[Release outputs-backups-20261018](https://github.com/VuTriThuan/CSDLDPT-Luu_tru_va_tim_kiem_anh_dong_vat_4_chan/releases/tag/outputs-backups-20261018) vẫn có bản đóng gói
14 phần và `SHA256SUMS` để tải riêng. Đây là lựa chọn bổ sung; dữ liệu cũng đã
có đầy đủ trong nhánh `main` theo cấu trúc nêu trên.
