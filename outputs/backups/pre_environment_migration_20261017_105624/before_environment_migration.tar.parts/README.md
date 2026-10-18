# Các phần của before_environment_migration.tar

Tệp gốc: `outputs/backups/pre_environment_migration_20261017_105624/before_environment_migration.tar`.

- Kích thước gốc: 814,602,240 byte.
- SHA-256 gốc: `931073a20bb94d476197b522a789b4952db2c86e5e81e2c2b71a6a8715c7b02e`.
- Số phần: 17, từ `part-00001` đến `part-00017`.
- Mỗi phần tối đa 48 MiB; ghép theo thứ tự tên tăng dần.

Sau khi clone hoặc tải ZIP đầy đủ, mở Terminal ở thư mục gốc dự án và chạy:

```sh
python3 outputs/backups/restore_large_files.py
```

Công cụ ghép cả 5 tệp lớn, kiểm tra SHA-256 từng phần và tệp hoàn chỉnh,
đồng thời giữ nguyên mọi tệp đích đã tồn tại. Hướng dẫn đầy đủ nằm trong
`outputs/backups/README.md`.
