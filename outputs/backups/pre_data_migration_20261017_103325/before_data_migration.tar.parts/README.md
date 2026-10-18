# Các phần của before_data_migration.tar

Tệp gốc: `outputs/backups/pre_data_migration_20261017_103325/before_data_migration.tar`.

- Kích thước gốc: 129,361,920 byte.
- SHA-256 gốc: `1ce1d4b0e34dc3a5d5eff5e6d79fc68a9c0aaa4788158606d71ca651234cc8ed`.
- Số phần: 3, từ `part-00001` đến `part-00003`.
- Mỗi phần tối đa 48 MiB; ghép theo thứ tự tên tăng dần.

Sau khi clone hoặc tải ZIP đầy đủ, mở Terminal ở thư mục gốc dự án và chạy:

```sh
BACKUP_FILE="outputs/backups/pre_data_migration_20261017_103325/before_data_migration.tar"
(set -C; cat "$BACKUP_FILE".parts/part-* > "$BACKUP_FILE")
shasum -a 256 "$BACKUP_FILE"
```

Đối chiếu kết quả với SHA-256 ở trên. `set -C` ngăn ghi đè tệp đã tồn tại.
Tải đủ các phần trước khi ghép. Hướng dẫn đầy đủ nằm trong
`outputs/backups/README.md`.
