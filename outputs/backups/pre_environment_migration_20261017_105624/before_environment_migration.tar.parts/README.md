# Các phần của before_environment_migration.tar

Tệp gốc: `outputs/backups/pre_environment_migration_20261017_105624/before_environment_migration.tar`.

- Kích thước gốc: 814,602,240 byte.
- SHA-256 gốc: `931073a20bb94d476197b522a789b4952db2c86e5e81e2c2b71a6a8715c7b02e`.
- Số phần: 17, từ `part-00001` đến `part-00017`.
- Mỗi phần tối đa 48 MiB; ghép theo thứ tự tên tăng dần.

Sau khi clone hoặc tải ZIP đầy đủ, mở Terminal ở thư mục gốc dự án và chạy:

```sh
BACKUP_FILE="outputs/backups/pre_environment_migration_20261017_105624/before_environment_migration.tar"
(set -C; cat "$BACKUP_FILE".parts/part-* > "$BACKUP_FILE")
shasum -a 256 "$BACKUP_FILE"
```

Đối chiếu kết quả với SHA-256 ở trên. `set -C` ngăn ghi đè tệp đã tồn tại.
Tải đủ các phần trước khi ghép. Hướng dẫn đầy đủ nằm trong
`outputs/backups/README.md`.
