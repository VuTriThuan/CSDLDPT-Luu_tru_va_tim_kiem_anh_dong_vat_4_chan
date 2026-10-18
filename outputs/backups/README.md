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

Mở Terminal tại thư mục gốc dự án. Ví dụ ghép bản sao lưu dữ liệu:

```sh
BACKUP_FILE="outputs/backups/pre_data_migration_20261017_103325/before_data_migration.tar"
(set -C; cat "$BACKUP_FILE".parts/part-* > "$BACKUP_FILE")
shasum -a 256 "$BACKUP_FILE"
```

Đối chiếu SHA-256 với giá trị trong README của thư mục `.parts/` tương ứng
hoặc [parts-manifest.json](parts-manifest.json). Lặp lại với 4 đường dẫn tệp
còn lại trong bảng trên bằng cách đổi `BACKUP_FILE`.

`set -C` ngăn ghi đè nếu tệp đích đã tồn tại. Tải đủ các phần trước khi ghép;
nếu thiếu phần hoặc checksum không khớp, tệp ghép chưa hợp lệ.
Cần thêm khoảng **5,8 GiB** dung lượng trống để ghép đầy đủ.
Các phần gốc vẫn được giữ lại.

Sau khi ghép xong, dùng các hướng dẫn khôi phục snapshot trong
[migration_verification.md](../../docs/migration_verification.md).

## Bản đóng gói trên Release

[Release outputs-backups-20261018](https://github.com/VuTriThuan/CSDLDPT-Luu_tru_va_tim_kiem_anh_dong_vat_4_chan/releases/tag/outputs-backups-20261018) vẫn có bản đóng gói
14 phần và `SHA256SUMS` để tải riêng. Đây là lựa chọn bổ sung; dữ liệu cũng đã
có đầy đủ trong nhánh `main` theo cấu trúc nêu trên.
