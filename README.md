# Lưu trữ và tìm kiếm ảnh động vật bốn chân

Dự án gồm công cụ chuẩn bị ảnh, tạo và duyệt mask, cùng báo cáo so sánh động vật
và phân tích dữ liệu để chọn bộ thuộc tính tìm kiếm. Yêu cầu 3 đã triển khai
B400 400 chiều, chuẩn hóa tái sử dụng và CSDL SQLite. Kết quả thực tế, kiểm thử
và các quy ước phép đo nằm trong [báo cáo yêu cầu 3](docs/reports/b400_implementation.md).
Chức năng tìm kiếm yêu cầu 4 chưa triển khai.

## Đọc tài liệu

| Tài liệu | Nội dung |
|---|---|
| [So sánh ảnh động vật](docs/reports/animal_comparison.md) | Yêu cầu 1: giống/khác bằng 104 ảnh đại diện và các cặp minh họa |
| [Thiết kế thuộc tính tìm kiếm](docs/reports/search_feature_design.md) | Yêu cầu 2: phân tích tự động 812 ảnh, kết quả đo thực tế và thiết kế B400 |
| [Triển khai B400 và CSDL](docs/reports/b400_implementation.md) | Yêu cầu 3: công thức, chuẩn hóa, SQLite, kết quả và tái lập |
| [Hướng dẫn công cụ ảnh](docs/guides/image_tools.md) | Cài môi trường, cắt ảnh, duyệt/lật/loại ảnh và kiểm thử |
| [Hướng dẫn GrabCut](docs/guides/grabcut.md) | Tạo mask, duyệt overlay, chỉnh mask và đồng bộ |
| [Hướng dẫn tạo lại mask](docs/guides/mask_regeneration.md) | Tạo mask U²-Net từ hàng đợi và kiểm tra kết quả lịch sử |

Báo cáo yêu cầu 2 dùng đầu ra mới trong `outputs/inventory/`. Một số kết quả hoặc
tệp trung gian được mô tả trong tài liệu lịch sử hiện không còn trên cây; xem
[báo cáo kiểm tra tài liệu](docs/documentation_migration.md) để biết phạm vi kiểm tra.

Đã xác minh sau sắp xếp: **38 kiểm thử đạt**, luồng xử lý trên dữ liệu riêng và
ba giao diện Tkinter đạt trên macOS Intel/Python 3.10.11. Ảnh, mask, overlay,
quicklook, manifest và lịch sử khớp SHA-256 bước 1. Cây bàn giao, lệnh chạy,
sao lưu/khôi phục và các giới hạn nằm trong
[migration_verification.md](docs/migration_verification.md).

## Phân tích dữ liệu yêu cầu 2

Lần chạy mới trên Mac Intel dùng Python 3.10.11, NumPy 1.26.4, Pillow 12.3.0
và OpenCV 4.11.0. Kết quả: **812 ảnh đầu vào; 812 giải mã thành công; 812 tính
đặc trưng thành công; 0 ảnh lỗi; 0 ảnh bị bỏ qua**. Tất cả là JPEG RGB,
576 × 384; 812 tên ảnh duy nhất, thuộc 22 nhóm nhãn theo tên tệp. Bốn tệp
không phải ảnh được ghi riêng, tổng manifest có 816 dòng tệp.

Hai bước kiểm tra kỹ thuật và tính đặc trưng có trạng thái/lý do riêng trong
[image_processing.csv](outputs/inventory/image_processing.csv). Mã duyệt toàn bộ
thư mục, không chọn mẫu và không sửa ảnh gốc. [label_counts.csv](outputs/inventory/label_counts.csv)
ghi số lượng từng nhãn, gồm cả thành công/lỗi/bỏ qua.

Đã tính từ ảnh thật: **812 vector màu toàn khung 176 chiều** (HSV 32 + Lab a/b 16 +
HSV lưới 2×4 là 128), cùng **10 phép đo mỗi ảnh** về bão hòa, sáng, tương phản,
pixel tối/sáng, entropy, Sobel và phương sai Laplacian. Trung bình S/255 toàn tập
là **0,320669**, entropy xám trung bình **7,367510 bit**. Các phép đo bao gồm nền;
không diễn giải chúng thành số đo màu lông hoặc hình dạng con vật.
Ví dụ `Equus_caballus_1014.jpg` và `equus-quagga_0779.jpg` có dáng thân tương tự
nhưng khác họa tiết; ảnh và số đo cụ thể nằm trong báo cáo.

**B400 = màu tiền cảnh 48 + kết cấu 100 + hình dạng 124 + bố cục màu 128**
được triển khai riêng tại `tools/features/`; vector thô, chuẩn hóa và SQLite
ở `outputs/features/b400_v1/`. NPZ 176 chiều yêu cầu 2 giữ nguyên.
Yêu cầu 1 giữ 104 ảnh đại diện để mô tả giống/khác. Chưa đánh giá chất lượng
truy hồi hoặc triển khai tìm kiếm yêu cầu 4.

Chạy lại tại root dự án bằng môi trường `.venv/` nêu bên dưới:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tools/validation/audit_images.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tools/validation/verify_image_analysis.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest tests.validation.test_audit_images -v
```

Lệnh đầu ghi lại JSON/CSV/NPZ hiện hành; lệnh sau đối chiếu tên, số lượng, nhãn,
hash ảnh, thống kê và bảng báo cáo. Xem [báo cáo yêu cầu 2](docs/reports/search_feature_design.md)
và [danh mục đầu ra](outputs/inventory/README.md) để biết định nghĩa, giới hạn và
cách đọc vector. Khi đổi tập đầu vào, cập nhật báo cáo theo kết quả chạy mới.

## Trích xuất B400 và quản trị CSDL — yêu cầu 3

Kết quả thực tế: **812 ảnh / 812 mask hợp lệ; 812 vector B400 thành công,
0 thất bại; 75 kiểm thử đạt** (30 B400/SQLite + 45 hồi quy), tính lại ngày
21/10/2026 sau kiểm kê toàn bộ đầu vào. Đã đọc lại toàn bộ vector từ SQLite để đối chiếu.
552 vector có quy ước cho ô màu/profile trống, kèm validity và lý do riêng.

S2e tại chỉ số 159 là `S2_axis_ratio`: độ dài nối hai điểm đường bao xa nhất
chia bề rộng bao hình theo phương vuông góc, đo tâm pixel trên mask nguồn
trước resize; hòa khoảng cách chọn cặp nhỏ nhất theo `(x,y)`; trục suy biến
ghi raw=0, validity=false. S3 `[160:208]` là 48 bit raw theo hàng, nhận 1 khi
occupancy **>15%**, đúng 15% nhận 0. S3 có canvas riêng 256×192, ô vuông
32×32 trong lưới 6×8; bbox toàn tiền cảnh co đều, nearest-neighbor, đệm giữa.
Các khối khác giữ canvas 288×192 và công thức cũ. Bit 0 có thể có ≤15% tiền
cảnh; occupancy/biến đổi hình học lưu metadata. S3 sau z-score/L2 có thể khác 0/1.

Giữ tên B400 và thư mục `b400_v1/` để đường dẫn tiếp tục hoạt động; nội dung
đã được tính lại, vector/scaler cũ **không tương đương** bộ hiện hành. Hash
công thức/tên chiều đã đổi và scaler được fit mới. Canvas/lưới S3 do nhóm chọn
để giữ 48 chiều, không do bài giảng quy định. Repo không có PDF bài giảng nên
chưa đối chiếu được PDF; chưa làm chuẩn hóa xoay/trục chính dài 192 trong slide.
Lưới nhị phân mất thông tin độ phủ, nhạy ngưỡng và mask; chưa đánh giá để
khẳng định chất lượng tìm kiếm tăng. Các đoạn cần chuyển vào báo cáo nhóm
được chỉ rõ trong [báo cáo triển khai](docs/reports/b400_implementation.md).

Dùng `.venv/` hiện có, không thêm phụ thuộc, chạy bằng CPU. Ảnh, mask, manifest
và đầu ra 176 chiều chỉ được đọc. Lệnh `extract` kiểm tra toàn bộ đầu vào,
trích xuất, fit chuẩn hóa trên tập phát triển và nhập/cập nhật SQLite;
`verify` đọc lại CSDL, đối chiếu tên/hash/vector/NPZ và tái hiện chuẩn hóa.

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests/features -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tools/features/cli.py validate
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tools/features/cli.py extract --rebuild
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tools/features/cli.py verify
.venv/bin/python -B tools/features/cli.py status
```

CSDL: [`outputs/features/b400_v1/features.sqlite3`](outputs/features/b400_v1/features.sqlite3).
Đọc một ảnh bằng `get --filename Equus_asinus_0587.jpg --run-id ID`, dùng ID từ
lệnh `status`. Các lệnh `init`, `status`, `get` phục vụ tạo/kiểm kê/đọc CSDL;
đọc luôn chỉ rõ lần chạy để tránh dùng nhầm scaler. `extract` chạy lại cùng đầu
vào cập nhật cùng bản ghi; nguồn thay đổi tạo lần chạy/scaler riêng. Nếu mã,
thư viện hoặc cấu hình thay đổi, dùng `extract --rebuild`: dựng sạch trong thư
mục tạm, kiểm chứng toàn bộ rồi hoán đổi nguyên tử tại đường dẫn hiện hành.
Lỗi giữ nguyên đầu ra cũ; không trộn vector/scaler hoặc bàn giao thư mục mới.

Các trường hợp ô trống, hue không bão hòa và phép đo không xác định có quy ước
rõ, kèm validity 400 phần tử và metadata ngoài vector. Thành công trích xuất
không có nghĩa mọi phép đo đều hợp lệ. Xem [báo cáo yêu cầu 3](docs/reports/b400_implementation.md)
và [danh mục đầu ra](outputs/features/b400_v1/README.md).

## Cấu trúc hiện tại

| Vị trí | Vai trò |
|---|---|
| [docs/reports/](docs/reports/) | Báo cáo yêu cầu 1–3 |
| [docs/guides/](docs/guides/) | Ba hướng dẫn sử dụng |
| [tools/image_processing/](tools/image_processing/) | Cắt ảnh, xem trước đổi tên, duyệt ảnh |
| [tools/segmentation/](tools/segmentation/) | Tạo, duyệt, chỉnh và đồng bộ mask/overlay |
| [tools/validation/](tools/validation/) | Kiểm kê ảnh và xác minh kết quả |
| [tools/features/](tools/features/) | B400, kiểm tra đầu vào, chuẩn hóa, SQLite và CLI yêu cầu 3 |
| [outputs/features/b400_v1/](outputs/features/b400_v1/) | CSDL thực tế, scaler, vector và báo cáo kiểm tra yêu cầu 3 |
| [tests/](tests/) | Kiểm thử công cụ ảnh, chuyển mã, validation và B400/SQLite |
| [data/source_images/](data/source_images/) | Ảnh nguồn |
| [data/cropped_images_576x384/](data/cropped_images_576x384/) | Ảnh cắt đang dùng |
| [data/rejected_crops/](data/rejected_crops/) | Ảnh cắt đã loại khi duyệt |
| [outputs/inventory/](outputs/inventory/) | Trạng thái từng tệp, thống kê và đặc trưng toàn khung của yêu cầu 2; xem ghi chú hồ sơ cũ |
| [outputs/segmentation/grabcut/](outputs/segmentation/grabcut/) | Mask, overlay, manifest, nhật ký và lịch sử chỉnh sửa |
| [bo_tool_anh_576x384/](bo_tool_anh_576x384/) | Requirements và cache lịch sử; không còn môi trường đang dùng |
| [outputs/backups/](outputs/backups/) | Toàn bộ bản sao lưu; tệp lớn chia phần, kèm hướng dẫn ghép lại |

**Bản sao lưu:** toàn bộ dữ liệu của 3.469 tệp gốc đã có trong `outputs/backups/` trên nhánh `main`. Trong đó 5 tệp lớn được chia thành 125 phần, mỗi phần tối đa 48 MiB. Sau khi clone hoặc tải ZIP, ghép các phần bằng lệnh `cat` và kiểm tra SHA-256 theo hướng dẫn. Xem [hướng dẫn đầy đủ](outputs/backups/README.md).

Ba thư mục ảnh đã dùng tên mới như bảng trên; tên và nội dung từng ảnh giữ nguyên.
Kết quả GrabCut nằm ở `outputs/segmentation/grabcut/`; cấu hình chạy nằm trong bộ kết quả,
kiểm kê nguồn trước chạy ở `provenance/source_before.json`. Hai môi trường hiện dùng là `.venv/` và `.venv-image-tools/` ở root.
`reports/` chỉ còn cache cũ và metadata hệ thống. Bộ mask tạo lại được mô tả trong lịch sử
không hiện diện; kiểm kê trước chạy của nó ở `outputs/segmentation/mask_regeneration_source_before.json`.

## Python và phụ thuộc

Dùng **Python 3.10.11 64-bit**, cấu hình ở `.python-version`. Hai bộ phiên bản
được giữ riêng để tiếp tục dùng các thư viện đã kiểm chứng trước khi sắp xếp:

| Môi trường | Thư viện chính | Công cụ |
|---|---|---|
| `.venv/` | NumPy 1.26.4, Pillow 12.3.0, OpenCV headless 4.11.0.86, ONNX Runtime 1.23.2 | GrabCut, editor/sync/review overlay, toàn bộ validation, đổi tên ảnh |
| `.venv-image-tools/` | NumPy 2.2.6, Pillow 11.3.0, ONNX Runtime 1.23.2, certifi 2026.7.22 | Cắt/duyệt ảnh, tạo lại mask U²-Net |

Cấu hình runtime và phụ thuộc gián tiếp được ghim ở
[requirements.txt](requirements.txt) và [requirements_image_tools.txt](requirements_image_tools.txt).
Tkinter/Tcl/Tk đi kèm Python, không cài bằng pip. Trên máy hiện tại không cần cài
lại; các lệnh sau dành cho máy mới với Python 3.10.11:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
python3 -m venv .venv-image-tools
.venv-image-tools/bin/python -m pip install --only-binary=:all: -r requirements_image_tools.txt
```

Không chuyển nguyên thư mục venv khi đổi máy/đường dẫn dự án; tạo lại tại đích.
Bản wheel có SHA-256 dùng để cài lại offline trên macOS Intel/Python 3.10 và
kiểm kê đầy đủ nằm trong [báo cáo môi trường](docs/python_environments.md).

## Chạy công cụ

Mở Terminal tại **thư mục gốc BTL**, nơi có `README.md`, `tools/`, `data/` và `docs/`.
Các lệnh dưới chỉ hiện hướng dẫn, không chạy xử lý dữ liệu:

```sh
.venv-image-tools/bin/python tools/image_processing/auto_crop.py --help
.venv/bin/python tools/image_processing/rename_images.py --help
.venv-image-tools/bin/python tools/image_processing/review_images.py --help

.venv/bin/python tools/segmentation/run_grabcut.py --help
.venv/bin/python tools/segmentation/review_overlays.py --help
.venv/bin/python tools/segmentation/edit_masks.py --help
.venv/bin/python tools/segmentation/sync_overlays.py --help
.venv-image-tools/bin/python tools/segmentation/regenerate_masks.py --help

.venv/bin/python tools/validation/audit_images.py --help
.venv/bin/python tools/validation/verify_grabcut_results.py --help
.venv/bin/python tools/validation/verify_regenerated_masks.py --help
```

`auto_crop.py` và `review_images.py` cũng tự chọn `.venv-image-tools/` khi được
khởi chạy bằng Python khác. `rename_images.py` chỉ cần thư viện chuẩn; dùng
`.venv/` cho nhất quán. Hướng dẫn Windows cho nhóm công cụ ảnh nằm trong
[image_tools.md](docs/guides/image_tools.md).

Các ví dụ có xử lý ảnh, `--setup`, `--resume` hoặc `--apply` được giải thích trong
từng hướng dẫn. `--resume` kiểm tra cấu hình, hash mã và phiên bản thư viện;
kết quả cũ có thể bị từ chối nếu các giá trị đã khác. Không sửa config để ép tiếp tục.
Hiện bộ GrabCut lịch sử bị từ chối resume đúng quy tắc; lần xử lý mới dùng một
`--output-dir` mới. Overlay thật đang ở thư mục phẳng: phân loại rồi đồng bộ trước
khi mở hàng đợi `needs_revision/` để chỉnh hoặc tạo lại mask. Hai thư mục cũ ở
root còn 17 tệp lịch sử cần giữ nên được giữ nguyên, không có venv trong đó.

## Kiểm thử và tiến độ sắp xếp

Chạy từ root bằng đúng môi trường của từng nhóm:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-image-tools/bin/python -B -m unittest discover -s tests/image_processing -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests/validation -v
```

- [Kế hoạch sắp xếp và quy trình khôi phục](docs/migration_plan.md).
- [Bước chuyển mã nguồn và kết quả kiểm thử](docs/source_migration.md).
- [Bước chuyển tài liệu và kiểm tra liên kết](docs/documentation_migration.md).

Hiện đã chuyển mã nguồn, tài liệu, ba thư mục ảnh và kết quả GrabCut.
Xem [bước chuyển kết quả, toàn vẹn và resume](docs/results_migration.md).
Xem [bước chuyển dữ liệu và kiểm tra trạng thái](docs/data_migration.md).

Đã chuẩn hóa môi trường Python; xem [kiểm tra môi trường và sao lưu](docs/python_environments.md).
Đã kiểm tra bàn giao toàn dự án; xem [kết quả xác minh cuối](docs/migration_verification.md).
