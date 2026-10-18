# Các phần của u2net.onnx

Tệp gốc: `outputs/backups/pre_migration_20261017_100229/external_dependencies/u2net.onnx`.

- Kích thước gốc: 175,997,641 byte.
- SHA-256 gốc: `8d10d2f3bb75ae3b6d527c77944fc5e7dcd94b29809d47a739a7a728a912b491`.
- Số phần: 4, từ `part-00001` đến `part-00004`.
- Mỗi phần tối đa 48 MiB; ghép theo thứ tự tên tăng dần.

Sau khi clone hoặc tải ZIP đầy đủ, mở Terminal ở thư mục gốc dự án và chạy:

```sh
python3 outputs/backups/restore_large_files.py
```

Công cụ ghép cả 5 tệp lớn, kiểm tra SHA-256 từng phần và tệp hoàn chỉnh,
đồng thời giữ nguyên mọi tệp đích đã tồn tại. Hướng dẫn đầy đủ nằm trong
`outputs/backups/README.md`.
