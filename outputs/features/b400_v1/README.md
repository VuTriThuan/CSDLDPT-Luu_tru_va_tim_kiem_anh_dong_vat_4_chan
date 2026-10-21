# Đầu ra yêu cầu 3 — B400 v1

Kết quả thực tế: **812 ảnh / 812 mask / 812 vector B400 thành công, 0 thất bại**.
Đã đối chiếu 812 vector từ SQLite; 552 vector có quy ước ô màu/profile trống
kèm validity, 260 vector có đủ mọi phép đo hợp lệ.

Sinh bằng `tools/features/cli.py extract`, tách khỏi NPZ 176 chiều yêu cầu 2.
Xem [báo cáo triển khai](../../../docs/reports/b400_implementation.md) về công thức,
quy ước thiếu, schema và số liệu thực tế. Ảnh/mask/manifest nguồn chỉ được đọc.

| Tệp | Nội dung |
|---|---|
| `features.sqlite3` | CSDL thực tế: ảnh/mask/revision, phiên bản bộ thuộc tính, scaler, run, trạng thái, raw/normalized/validity |
| `input_validation.json` | Đối chiếu mọi ảnh/mask/manifest/kiểm kê, hash, trạng thái và lý do lỗi |
| `feature_set.json` | Cấu hình đầy đủ, 400 tên/thứ tự, phiên bản khối, hash mã và runtime |
| `normalizer.json` | Mean/scale/count, quy tắc biến đổi, trọng số, tập fit và checksum; dùng lại cho truy vấn |
| `extraction_records.json` | Từng tên/hash/đường dẫn/trạng thái; quality gồm support, occupancy, validity reasons |
| `status.csv` | Kiểm kê từng ảnh: kiểm tra đầu vào/trích xuất/lỗi, số chiều hợp lệ và số quy ước |
| `vectors.npz` | filenames, feature_names, raw/normalized (N×400 float32), validity (N×400 bool), hashes và ID phiên bản |
| `summary.json` | Kết quả thực tế, số thành công/thất bại, phép đo có quy ước và thời gian |
| `verification.json` | Đọc lại CSDL, kiểm tra tên/hash/vector/NPZ, integrity/FK và tái hiện scaler |
| `delivery_checks.json` | Số dòng các bảng, shape/dtype/norm vector và kiểm tra liên kết tài liệu |
| `requirement2_verification.log` | Đối chiếu lại đầu ra 176 chiều và báo cáo yêu cầu 2 |
| `extraction.log` | Tiến trình và kết quả lần chạy trích xuất |
| `tests.log`, `regression_*.log` | Kiểm thử mới và hồi quy |

Một vector trích xuất thành công có thể chứa phép đo được quy ước vì vùng trống
hoặc đại lượng không xác định. Không coi raw=0 là phép đo hợp lệ khi validity=false.
`quality.conventions` là metadata ngoài B400. Nhãn/tên không là giá trị đặc trưng.

```sh
.venv/bin/python -B tools/features/cli.py status
.venv/bin/python -B tools/features/cli.py verify
.venv/bin/python -B tools/features/cli.py get --filename Equus_asinus_0587.jpg --run-id ID
```

Dùng ID từ `status`. SQLite giữ các lần chạy/scaler cũ; các tệp xuất bên cạnh
chỉ biểu diễn lần mới nhất. Chạy lại cùng đầu vào không sinh bản ghi trùng;
nguồn đổi tạo run/scaler riêng. CLI từ chối dùng lại thư mục khi mã/cấu hình/
runtime thay đổi. `verify` yêu cầu hiện trạng đầu vào khớp lần chạy đang xuất.
`validate` cập nhật báo cáo đầu vào, vì vậy sau khi nguồn thay đổi cần chạy lại
extract trước khi verify toàn bộ đầu ra. File `.b400.lock` phục vụ khóa ghi.

Đọc phụ trợ không dùng pickle:

```python
import numpy as np
with np.load('outputs/features/b400_v1/vectors.npz', allow_pickle=False) as data:
    raw = data['raw']
    normalized = data['normalized']
    validity = data['validity']
```

CSDL là đầu ra chính; NPZ/CSV phục vụ kiểm tra và trao đổi, không thay thế CSDL.
