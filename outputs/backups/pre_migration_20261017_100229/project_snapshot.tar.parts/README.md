# Các phần của project_snapshot.tar

Tệp gốc: `outputs/backups/pre_migration_20261017_100229/project_snapshot.tar`.

- Kích thước gốc: 4,471,776,768 byte.
- SHA-256 gốc: `2917b8e027a090fdb7564ac71336e4a82e7ce6e1dc9e038658a2c468e37bdbf7`.
- Số phần: 89, từ `part-00001` đến `part-00089`.
- Mỗi phần tối đa 48 MiB; ghép theo thứ tự tên tăng dần.

Sau khi clone hoặc tải ZIP đầy đủ, mở Terminal ở thư mục gốc dự án và chạy:

```sh
python3 outputs/backups/restore_large_files.py
```

Công cụ ghép cả 5 tệp lớn, kiểm tra SHA-256 từng phần và tệp hoàn chỉnh,
đồng thời giữ nguyên mọi tệp đích đã tồn tại. Hướng dẫn đầy đủ nằm trong
`outputs/backups/README.md`.
