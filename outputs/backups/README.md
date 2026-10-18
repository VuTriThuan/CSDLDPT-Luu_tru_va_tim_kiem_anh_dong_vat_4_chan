# Bản sao lưu của dự án

Thư mục này có thể duyệt trực tiếp trong tab **Code** trên GitHub.
Các bản sao lưu gốc giữ nguyên nội dung theo thời điểm tạo.

## Nội dung trên nhánh main

- [pre_data_migration_20261017_103325/](pre_data_migration_20261017_103325/)
- [pre_environment_migration_20261017_105624/](pre_environment_migration_20261017_105624/)
- [pre_migration_20261017_100229/](pre_migration_20261017_100229/)
- [pre_results_migration_20261017_104419/](pre_results_migration_20261017_104419/)
- [pre_verification_20261017_111334/](pre_verification_20261017_111334/)

Nhánh `main` chứa **3,453 tệp gốc** không vượt 100 MiB, gồm tài liệu,
kiểm kê, checksum, wheel cài đặt và dữ liệu khôi phục thử.
[inventory.csv](inventory.csv) ghi đường dẫn, kích thước, SHA-256 và nơi lưu
của toàn bộ **3,458 tệp gốc** được công bố. Cache Python và `.DS_Store`
không được đưa vào Git; bản đóng gói trên Release vẫn giữ bản sao lưu đầy đủ.

## Năm tệp lớn tải từ Release

GitHub chặn tệp lớn hơn 100 MiB trong Git thông thường. Các tệp dưới đây nằm
trong [Release outputs-backups-20261018](https://github.com/VuTriThuan/CSDLDPT-Luu_tru_va_tim_kiem_anh_dong_vat_4_chan/releases/tag/outputs-backups-20261018),
không nằm trong bản clone hoặc ZIP của nhánh `main`.

| Đường dẫn tương đối trong outputs/backups/ | Kích thước (MiB) |
|---|---:|
| `pre_data_migration_20261017_103325/before_data_migration.tar` | 123.37 |
| `pre_environment_migration_20261017_105624/before_environment_migration.tar` | 776.87 |
| `pre_migration_20261017_100229/external_dependencies/u2net.onnx` | 167.84 |
| `pre_migration_20261017_100229/project_snapshot.tar` | 4,264.62 |
| `pre_results_migration_20261017_104419/before_results_migration.tar` | 556.10 |

## Tải và khôi phục đầy đủ

1. Mở [Release](https://github.com/VuTriThuan/CSDLDPT-Luu_tru_va_tim_kiem_anh_dong_vat_4_chan/releases/tag/outputs-backups-20261018), mở **Assets** và tải đủ
   14 phần `outputs-backups.tar.part-aa` đến `outputs-backups.tar.part-an`,
   cùng tệp `SHA256SUMS`, vào một thư mục.
2. Mở Terminal tại thư mục gốc dự án, thay đường dẫn tải xuống trong lệnh sau:

```sh
BACKUP_DOWNLOADS="/duong/dan/thu_muc_da_tai"
(cd "$BACKUP_DOWNLOADS" && shasum -a 256 -c SHA256SUMS)
```

3. Khi cả 14 phần đều báo `OK`, ghép và giải nén để khôi phục đúng đường dẫn:

```sh
cat "$BACKUP_DOWNLOADS"/outputs-backups.tar.part-* | tar -xf -
```

Lệnh giải nén ghi các tệp vào `outputs/backups/` trong dự án hiện tại và
có thể ghi đè tệp cùng đường dẫn. Sau đó có thể dùng các hướng dẫn khôi phục
trong [migration_verification.md](../../docs/migration_verification.md).
