# Các phần của before_results_migration.tar

Tệp gốc: `outputs/backups/pre_results_migration_20261017_104419/before_results_migration.tar`.

- Kích thước gốc: 583,116,800 byte.
- SHA-256 gốc: `580a45d1daaa1ae603e8a6098f3802ad963c43d9410dc2097681c23ef17ae2bf`.
- Số phần: 12, từ `part-00001` đến `part-00012`.
- Mỗi phần tối đa 48 MiB; ghép theo thứ tự tên tăng dần.

Sau khi clone hoặc tải ZIP đầy đủ, mở Terminal ở thư mục gốc dự án và chạy:

```sh
python3 outputs/backups/restore_large_files.py
```

Công cụ ghép cả 5 tệp lớn, kiểm tra SHA-256 từng phần và tệp hoàn chỉnh,
đồng thời giữ nguyên mọi tệp đích đã tồn tại. Hướng dẫn đầy đủ nằm trong
`outputs/backups/README.md`.
