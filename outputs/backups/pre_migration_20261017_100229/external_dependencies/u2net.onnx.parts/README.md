# Các phần của u2net.onnx

Tệp gốc: `outputs/backups/pre_migration_20261017_100229/external_dependencies/u2net.onnx`.

- Kích thước gốc: 175,997,641 byte.
- SHA-256 gốc: `8d10d2f3bb75ae3b6d527c77944fc5e7dcd94b29809d47a739a7a728a912b491`.
- Số phần: 4, từ `part-00001` đến `part-00004`.
- Mỗi phần tối đa 48 MiB; ghép theo thứ tự tên tăng dần.

Sau khi clone hoặc tải ZIP đầy đủ, mở Terminal ở thư mục gốc dự án và chạy:

```sh
BACKUP_FILE="outputs/backups/pre_migration_20261017_100229/external_dependencies/u2net.onnx"
(set -C; cat "$BACKUP_FILE".parts/part-* > "$BACKUP_FILE")
shasum -a 256 "$BACKUP_FILE"
```

Đối chiếu kết quả với SHA-256 ở trên. `set -C` ngăn ghi đè tệp đã tồn tại.
Tải đủ các phần trước khi ghép. Hướng dẫn đầy đủ nằm trong
`outputs/backups/README.md`.
