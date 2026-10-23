# Đầu ra phân tích yêu cầu 2

Đầu ra hiện hành được tạo bằng `tools/validation/audit_images.py` trên toàn bộ
`data/cropped_images_576x384/`. Không thay đổi ảnh nguồn. Mỗi lần chạy ghi đè các
tệp hiện hành dưới đây; đầu vào và thư mục đầu ra không được chồng lấp.

| Tệp | Nội dung |
|---|---|
| `image_inventory.json` | Số tệp/ảnh, metadata kỹ thuật, trạng thái hai bước, nhãn và lỗi/bỏ qua. |
| `image_processing.csv` | Một dòng mỗi tệp; tên, hash ảnh, nhãn, metadata, trạng thái giải mã và đặc trưng. Bao gồm cả tệp không phải ảnh. |
| `label_counts.csv` | Đầu vào/thành công/lỗi/bỏ qua theo từng nhãn và công đoạn. |
| `feature_metrics.csv` | Một dòng mỗi ảnh tính đặc trưng thành công; 10 phép đo vô hướng, tên tệp và nhãn. |
| `feature_statistics.csv` | count/mean/std/min/Q1/median/Q3/max cho toàn tập (`__all__`) và từng nhãn. |
| `feature_summary.json` | Thống kê như CSV, phạm vi toàn khung và trạng thái B400 còn là thiết kế. |
| `full_frame_color_features.npz` | Histogram màu toàn khung float32 176 chiều; `filenames`, `feature_names`, `features` cùng thứ tự. |
| `analysis_environment.json` | Thời điểm UTC, Python/thư viện, SHA-256 mã và cấu hình tính toán. |

Tên tệp trong manifest là đường dẫn tương đối từ thư mục đầu vào; nhãn chỉ là
metadata được chuẩn hóa từ tên. Tên cơ sở trùng được báo riêng, không ghi đè hàng
vector. `technical_status` và `feature_status` độc lập; mỗi trạng thái khác
`success` có trường lý do đi kèm. Histogram và các phép đo dùng toàn cảnh, gồm
cả nền, chưa phải mô tả tiền cảnh B400.

Đọc ma trận không dùng pickle:

```python
import numpy as np
with np.load('outputs/inventory/full_frame_color_features.npz', allow_pickle=False) as data:
    filenames = data['filenames']
    columns = data['feature_names']
    features = data['features']
```

Danh sách xử lý tự động hiện hành là `image_processing.csv`; tên này không hàm ý quan sát thị giác. Ba tệp mẫu lịch sử và script xác minh độc lập đã được gỡ khỏi nhánh tinh gọn.

Chạy công cụ `tools/validation/audit_images.py` theo [hướng dẫn yêu cầu 2](../../docs/reports/search_feature_design.md) khi cần tạo lại kiểm kê và các phép đo toàn bộ ảnh. Chạy lại sẽ ghi đầu ra mới; các số liệu trong báo cáo cần được cập nhật nếu thay dữ liệu.
