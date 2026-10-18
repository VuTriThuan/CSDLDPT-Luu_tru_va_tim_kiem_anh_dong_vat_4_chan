# Các phần của before_data_migration.tar

Tệp gốc: `outputs/backups/pre_data_migration_20261017_103325/before_data_migration.tar`.

- Kích thước gốc: 129,361,920 byte.
- SHA-256 gốc: `1ce1d4b0e34dc3a5d5eff5e6d79fc68a9c0aaa4788158606d71ca651234cc8ed`.
- Số phần: 3, từ `part-00001` đến `part-00003`.
- Mỗi phần tối đa 48 MiB; ghép theo thứ tự tên tăng dần.

Sau khi clone hoặc tải ZIP đầy đủ, mở Terminal ở thư mục gốc dự án và chạy:

```sh
python3 outputs/backups/restore_large_files.py
```

Công cụ ghép cả 5 tệp lớn, kiểm tra SHA-256 từng phần và tệp hoàn chỉnh,
đồng thời giữ nguyên mọi tệp đích đã tồn tại. Hướng dẫn đầy đủ nằm trong
`outputs/backups/README.md`.
