# Đầu ra hiện hành — B400

Đã tính lại ngày 21/10/2026: **812 ảnh / 812 mask hợp lệ;
812 vector thành công, 0 thất bại**, không có tên tệp lỗi.
Giữ đường dẫn `outputs/features/b400_v1/` để các đường dẫn dự án tiếp tục hoạt
động; vector/scaler công thức cũ không tương đương bộ hiện hành.

S2e (`S2_axis_ratio`, chỉ số 159) là trục chính nối hai tâm pixel đường bao xa
nhất chia bề rộng bao hình theo phương vuông góc, đo mask nguồn trước resize.
Không PCA; hòa đường kính chọn cặp nhỏ nhất theo tọa độ `(x,y)`, trục suy biến
raw=0/validity=false. S3 `[160:208]` là 48 bit: occupancy >15% cho 1, đúng
15% cho 0. Canvas riêng 256×192, lưới 6×8, ô vuông 32×32; bbox toàn tiền cảnh
co đều nearest-neighbor và đệm 0 giữa. Các khối khác giữ nguyên canvas/công thức.
Bit 0 có thể là ô trống hoặc có ≤15% tiền cảnh; S3 sau chuẩn hóa có thể khác 0/1.
Occupancy và biến đổi hình học lưu trong quality.s3; số đo trục ở quality.s2e.
Canvas/lưới là lựa chọn nhóm giữ 48 chiều; chưa đối chiếu PDF bài giảng và
chưa làm chuẩn hóa xoay/trục chính dài 192. Chưa đánh giá chất lượng tìm kiếm.

| Tệp | Nội dung |
|---|---|
| `features.sqlite3` | Đầu ra chính: raw/normalized/validity, metadata, config, scaler, run và trạng thái |
| `feature_set.json` | Công thức, revision S2/S3, hash mã/runtime và 400 tên chiều |
| `normalizer.json` | Scaler fit mới, checksum và quy tắc truy vấn dùng lại |
| `vectors.npz` | N×400 float32 raw/normalized, validity, tên/hash và ID; allow_pickle=False |
| `input_validation.json` | Kiểm kê thực tế và hash ảnh/mask/manifest/CSV |
| `extraction_records.json`, `status.csv` | Mọi tên tệp, trạng thái/lý do, metadata occupancy/trục |
| `summary.json`, `verification.json` | Kết quả chạy và đọc lại mọi vector SQLite, integrity/FK, kiểm scaler |
| `delivery_checks.json` | Kiểm độc lập S2e/S3, so 351 chiều giữ nguyên, hash tệp được bảo vệ và liên kết |
| `extraction.log` | Nhật ký trích xuất bộ B400 hiện hành |

552 vector có quy ước thiếu ô màu/profile, phân biệt bằng validity;
260 vector có mọi phép đo hợp lệ. Nhãn/tên chỉ là metadata.
CSDL hiện hành chỉ có một cấu hình, một scaler và một run theo công thức mới.

```sh
.venv/bin/python -B tools/features/cli.py extract --rebuild
.venv/bin/python -B tools/features/cli.py verify
.venv/bin/python -B tools/features/cli.py status
.venv/bin/python -B tools/features/cli.py get --filename Equus_asinus_0587.jpg --run-id ID
```

Lấy ID từ status. `--rebuild` dựng sạch trong thư mục tạm, kiểm chứng trước
hoán đổi nguyên tử, giữ nguyên bộ cũ khi lỗi và dọn thư mục tạm. Không bàn giao
thư mục B400 thứ hai. Khóa `.b400_v1.lock` nằm ở thư mục cha. `extract` thường
chỉ tiếp tục khi cùng cấu hình/mã/runtime; chạy lại partial thay scaler/vector
trong một transaction để tránh lỗi khóa ngoại hoặc trộn scaler. Ảnh/mask đổi
hợp lệ tạo run riêng nếu cùng công thức. `validate` ghi lại audit, nên sau khi
đổi nguồn cần extract trước verify. Chi tiết tại
[báo cáo triển khai](../../../docs/reports/b400_implementation.md).

Nhánh tinh gọn đã gỡ log unit test/hồi quy và mã `tests/`. Các số kiểm thử trong báo cáo là lịch sử; `summary.json`, `verification.json`, `delivery_checks.json`, NPZ, SQLite và metadata hiện hành vẫn được giữ nguyên.
