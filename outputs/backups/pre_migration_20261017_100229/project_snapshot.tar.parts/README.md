# Các phần của project_snapshot.tar

Tệp gốc: `outputs/backups/pre_migration_20261017_100229/project_snapshot.tar`.

- Kích thước gốc: 4,471,776,768 byte.
- SHA-256 gốc: `2917b8e027a090fdb7564ac71336e4a82e7ce6e1dc9e038658a2c468e37bdbf7`.
- Số phần: 89, từ `part-00001` đến `part-00089`.
- Mỗi phần tối đa 48 MiB; ghép theo thứ tự tên tăng dần.

Sau khi clone hoặc tải ZIP đầy đủ, mở Terminal ở thư mục gốc dự án và chạy:

```sh
BACKUP_FILE="outputs/backups/pre_migration_20261017_100229/project_snapshot.tar"
(set -C; cat "$BACKUP_FILE".parts/part-* > "$BACKUP_FILE")
shasum -a 256 "$BACKUP_FILE"
```

Đối chiếu kết quả với SHA-256 ở trên. `set -C` ngăn ghi đè tệp đã tồn tại.
Tải đủ các phần trước khi ghép. Hướng dẫn đầy đủ nằm trong
`outputs/backups/README.md`.
