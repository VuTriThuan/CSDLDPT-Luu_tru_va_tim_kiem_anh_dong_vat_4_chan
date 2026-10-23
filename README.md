# Lưu trữ và tìm kiếm ảnh động vật bốn chân

Dự án gồm công cụ chuẩn bị ảnh, tạo và duyệt mask, cùng báo cáo so sánh động vật
và phân tích dữ liệu để chọn bộ thuộc tính tìm kiếm. Yêu cầu 3 đã triển khai
B400 400 chiều, chuẩn hóa tái sử dụng và CSDL SQLite. Kết quả thực tế, kiểm thử
và các quy ước phép đo nằm trong [báo cáo yêu cầu 3](docs/reports/b400_implementation.md).
Yêu cầu 4 đã có tìm kiếm chính xác top 5, CLI, giao diện Tkinter sửa mask và
công cụ chấm theo lô; xem [báo cáo tìm kiếm](docs/reports/search_implementation.md).
Đã kiểm tra thêm các lượt tìm kiếm thực tế ngày 23/10, sửa thao tác bbox/mask và
thêm chẩn đoán từng lượt; xem [kiểm tra chất lượng](docs/reports/search_quality_audit.md).

## Mở demo trên Windows (PowerShell)

Cài **CPython 3.10.11 x64** với Tcl/Tk, mở PowerShell tại root dự án.
Tạo venv mới trên Windows; không sao chép venv từ Mac. Kiểm tra `py -3.10 --version`
phải ra `3.10.11`, rồi chạy:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r .\requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import tkinter; print(tkinter.TkVersion)"
.\.venv\Scripts\python.exe -B .\tools\features\cli.py verify
.\.venv\Scripts\python.exe -B .\tools\search\cli.py status
.\.venv\Scripts\python.exe -B .\tools\search\cli.py gui
```

Dùng ngay SQLite/scaler tại `outputs/features/b400_v1/`; không chạy `extract`
hoặc fit lại scaler để mở demo. Trong GUI chọn ảnh, kiểm tra mask, tô giữ/loại,
áp dụng GrabCut, hoàn tác nếu cần, rồi tìm và xuất kết quả.
Lệnh truy vấn, batch/score và môi trường công cụ ảnh riêng nằm trong
[hướng dẫn Windows/macOS](docs/python_environments.md).

**Phạm vi kiểm chứng ngày 23/10/2026:** đã chạy thật CLI, truy vấn, batch và GUI
trên macOS Intel; chưa có máy Windows thật. Đã tải wheel cho Windows x64/Python
3.10, đối chiếu đủ phụ thuộc theo marker Windows, mô phỏng nhánh khóa Win32 và
hai bước đổi tên/khôi phục. Đây chưa phải xác nhận chạy Windows thành công.
812 vector × 400 chiều đọc được; chuẩn hóa lại bằng scaler frozen khớp chính xác
(sai số lớn nhất 0); SHA-256 của 6.037 tệp dữ liệu/đầu ra/báo cáo giữ nguyên.
Chi tiết kiểm chứng và giới hạn ở cuối [hướng dẫn môi trường](docs/python_environments.md#kiểm-chứng-ngày-23102026).

## Đọc tài liệu

| Tài liệu | Nội dung |
|---|---|
| [So sánh ảnh động vật](docs/reports/animal_comparison.md) | Yêu cầu 1: giống/khác bằng 104 ảnh đại diện và các cặp minh họa |
| [Thiết kế thuộc tính tìm kiếm](docs/reports/search_feature_design.md) | Yêu cầu 2: phân tích tự động 812 ảnh, kết quả đo thực tế và thiết kế B400 |
| [Triển khai B400 và CSDL](docs/reports/b400_implementation.md) | Yêu cầu 3: công thức, chuẩn hóa, SQLite, kết quả và tái lập |
| [Tìm kiếm top 5](docs/reports/search_implementation.md) | Yêu cầu 4: kiến trúc, CLI/GUI, trung gian thực tế, công cụ đánh giá và kiểm thử |
| [Kiểm tra chất lượng mask và tìm kiếm](docs/reports/search_quality_audit.md) | Phân tích lượt thật, giới hạn B400, các sửa lỗi thao tác và lệnh diagnose |
| [Hướng dẫn công cụ ảnh](docs/guides/image_tools.md) | Cài môi trường, cắt ảnh, duyệt/lật/loại ảnh và kiểm thử |
| [Hướng dẫn GrabCut](docs/guides/grabcut.md) | Tạo mask, duyệt overlay, chỉnh mask và đồng bộ |
| [Hướng dẫn tạo lại mask](docs/guides/mask_regeneration.md) | Tạo mask U²-Net từ hàng đợi và kiểm tra kết quả lịch sử |

Báo cáo yêu cầu 2 dùng đầu ra hiện hành trong `outputs/inventory/`. Nhánh tinh gọn giữ dữ liệu hiện hành, mã xử lý, báo cáo và bằng chứng cuối. Bản sao lưu, hồ sơ di chuyển, dữ liệu thử và các kết quả trung gian đã được gỡ; các số liệu kiểm thử ghi trong báo cáo là lịch sử trước khi dọn.

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
Yêu cầu 1 giữ 104 ảnh đại diện để mô tả giống/khác. Đã triển khai tìm kiếm
yêu cầu 4; chưa có truy vấn độc lập và chấm mức phù hợp thị giác để kết luận
chất lượng truy hồi.

Chạy lại tại root dự án bằng môi trường `.venv/` nêu bên dưới:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tools/validation/audit_images.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tools/validation/verify_image_analysis.py
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

Dùng `.venv/` đúng phiên bản ghim, chạy bằng CPU. Ảnh, mask, manifest
và đầu ra 176 chiều chỉ được đọc. Lệnh `extract` kiểm tra toàn bộ đầu vào,
trích xuất, fit chuẩn hóa trên tập phát triển và nhập/cập nhật SQLite;
`verify` chỉ đọc CSDL và các sidecar, đối chiếu tên/hash/vector/NPZ và tái hiện
chuẩn hóa bằng scaler đã lưu; không fit lại hoặc ghi đè báo cáo xác minh cũ.

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tools/features/cli.py validate
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tools/features/cli.py extract --rebuild
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tools/features/cli.py verify
.venv/bin/python -B tools/features/cli.py status
```

CSDL: [`outputs/features/b400_v1/features.sqlite3`](outputs/features/b400_v1/features.sqlite3).
Đọc một ảnh bằng `get --filename Equus_asinus_0587.jpg --run-id ID`, dùng ID từ
lệnh `status`. Các lệnh `init`, `status`, `get` phục vụ tạo/kiểm kê/đọc CSDL;
đọc luôn chỉ rõ lần chạy để tránh dùng nhầm scaler. Bản tương thích I/O hiện tại
dùng lại B400 đã lưu qua chính sách fingerprint tường minh, giữ nguyên ID cũ và
runtime ghim. Không cần rebuild cho thay đổi khóa/đường dẫn đã được duyệt.
`extract --rebuild` dành cho việc chủ động xây lại dữ liệu: dựng và xác minh staging
trước; macOS/Linux đổi chỗ nguyên tử, Windows đổi tên hai bước có backup/rollback
dưới khóa chung. Windows có khoảng trống giữa hai lần đổi tên, không nguyên tử.
Lỗi khôi phục giữ bộ cũ trong thư mục sibling `.b400_v1-previous`; lần mở tiếp theo
dưới khóa sẽ phục hồi. Xem giới hạn và chính sách byte/runtime trong hướng dẫn môi trường.

Các trường hợp ô trống, hue không bão hòa và phép đo không xác định có quy ước
rõ, kèm validity 400 phần tử và metadata ngoài vector. Thành công trích xuất
không có nghĩa mọi phép đo đều hợp lệ. Xem [báo cáo yêu cầu 3](docs/reports/b400_implementation.md)
và [danh mục đầu ra](outputs/features/b400_v1/README.md).

## Tìm kiếm top 5 — yêu cầu 4

Đọc một lần vector chuẩn hóa B400 từ SQLite của run hoàn tất trong summary;
không fit lại scaler. Mỗi truy vấn trích đủ hai phương án RGB/mask gốc và lật
ngang, dùng khoảng cách bình phương nhỏ hơn để xếp hạng. Nhãn chỉ dùng hiển
thị/đánh giá. Cả 812 tệp được xếp hạng riêng, kể cả hai tệp cùng SHA-256;
mặc định loại mọi tệp trùng hash ảnh truy vấn.
Kết quả và ảnh/mask truy vấn chỉ ghi vào `outputs/search/`.

```sh
.venv/bin/python -B tools/search/cli.py status
.venv/bin/python -B tools/search/cli.py query \
  --image data/cropped_images_576x384/Equus_asinus_0587.jpg \
  --mask outputs/segmentation/grabcut/masks/Equus_asinus_0587.jpg.png
.venv/bin/python -B tools/search/cli.py gui
# Tạo manifest mới, điền các ảnh thật trước khi chạy batch:
cp tools/search/query_manifest_template.csv outputs/search/new_queries.csv
# Sau khi điền CSV:
.venv/bin/python -B tools/search/cli.py batch --manifest outputs/search/new_queries.csv
```

Ảnh mới có thể dùng `query --image /path/new.jpg --bbox X Y WIDTH HEIGHT` hoặc
nạp mask PNG 0/255 qua CLI `--mask`. GUI có nút **Chọn ảnh khác** để bắt đầu lượt mới;
giao diện tự tạo mask khi chọn ảnh, cho tô giữ/loại, hoàn tác, xem
mask/overlay, top 5, đóng góp bốn nhóm, vector theo khối, validity và xuất toàn
bộ lượt truy vấn. Tích **Hiện cả ảnh trùng truy vấn** để xem các bản trùng của
chính ảnh đang tìm. Tác vụ nặng chạy trên một worker, widget cập nhật ở luồng Tk.
Nếu dùng CLI `--include-self` với `equus-quagga_0663.jpg`, hai tệp trùng bytes
`0663` và `0667` đều có thể hiện trong top 5; mặc định cả hai bị loại khi ảnh
truy vấn có cùng SHA-256.

Kết quả thực tế ngày 22/10/2026: nạp **812 tệp**, bốn
truy vấn kiểm tra theo lô thành công, **110 kiểm thử đạt** (35 tìm kiếm + 75 hồi
quy), và kiểm tra tự động trên cửa sổ Tkinter thật đạt. Chưa duyệt giao diện thủ
công. SHA-256 của **6.118 tệp được bảo vệ** được đối chiếu; dữ liệu và đầu ra yêu
cầu 1–3 không thay đổi. Không thêm phụ thuộc.

Để đánh giá độc lập, sao chép mẫu CSV ở
[`tools/search/query_manifest_template.csv`](tools/search/query_manifest_template.csv),
điền ảnh mới, mask (nếu có), nhãn/group và `purpose=independent`; chạy `batch`,
chấm `visual_relevant` bằng 0/1 trong `judgments.csv`, rồi chạy `score` theo
[hướng dẫn và định nghĩa P@5](docs/reports/search_implementation.md).
P@5 thị giác đang để trống vì chưa có dữ liệu/chấm độc lập; cùng nhãn là phép
đối chiếu riêng. Bằng chứng: [`outputs/search/`](outputs/search/README.md).

Đã hoàn thiện kiểm chứng yêu cầu 4 ngày 23/10: audit đọc đúng chính sách từng
lượt; batch mới lưu artifact tương đối và chấm được sau khi di chuyển; đã chạy
phân tích riêng/bỏ lần lượt bốn nhóm trên cùng vector ngựa, bò, chó.
**58 kiểm thử tìm kiếm/phân tích + 30 hồi quy B400 đạt**; audit cuối kiểm tra
**62/62 artifact** (gồm bản sao kiểm chứng, 50 artifact trước khi tạo bản sao).
Xem [kết quả, mask, thứ hạng và giới hạn kết luận](outputs/search/diagnostics/group_analysis/20261023T133848_225643Z_20473d/README.md).

Sau khi clone, tạo `.venv/` tại vị trí mới theo phần Python bên dưới. Với một batch mới đã tạo, thay `batch_ID` bằng thư mục batch thực tế rồi chấm:

```sh
SEARCH_BATCH_DIR=outputs/search/batch_ID
.venv/bin/python -B tools/search/cli.py score \
  --batch "$SEARCH_BATCH_DIR/batch.json" \
  --judgments "$SEARCH_BATCH_DIR/judgments.csv" \
  --output-dir outputs/search/scored
# Tái lập phân tích từ ba lượt ngựa/bò/chó được giữ:
.venv/bin/python -B -m tools.search.group_analysis
```

Khi chuyển một batch, sao chép **toàn bộ thư mục** gồm `batch.json`,
`judgments.csv` và `queries/`; chỉ sửa `visual_relevant`/`notes` trong bảng chấm.
Các đường dẫn ảnh của batch mới tính từ thư mục chứa `batch.json`. Batch lịch sử
được ánh xạ sang artifact trong chính batch đang mở, không sửa hồ sơ cũ.
Chi tiết kiểm tra đường dẫn/ID và cách đọc ảnh lịch sử nằm trong
[hướng dẫn chấm](docs/reports/search_implementation.md#chấm-batch-sau-khi-clone-hoặc-di-chuyển).

## Cấu trúc hiện tại

| Vị trí | Vai trò |
|---|---|
| [docs/reports/](docs/reports/) | Báo cáo yêu cầu 1–4 |
| [docs/guides/](docs/guides/) | Ba hướng dẫn sử dụng |
| [tools/image_processing/](tools/image_processing/) | Cắt ảnh, xem trước đổi tên, duyệt ảnh |
| [tools/segmentation/](tools/segmentation/) | Tạo, duyệt, chỉnh và đồng bộ mask/overlay |
| [tools/validation/](tools/validation/) | Kiểm kê ảnh và xác minh kết quả |
| [tools/features/](tools/features/) | B400, kiểm tra đầu vào, chuẩn hóa, SQLite và CLI yêu cầu 3 |
| [tools/search/](tools/search/) | Đọc run B400 cố định, truy vấn/GrabCut, top 5, CLI/Tkinter và đánh giá theo lô |
| [outputs/features/b400_v1/](outputs/features/b400_v1/) | CSDL thực tế, scaler, vector và báo cáo kiểm tra yêu cầu 3 |
| [outputs/search/](outputs/search/) | Lượt truy vấn, ảnh/mask riêng, vector gốc/lật, bảng chấm và bằng chứng kiểm thử lịch sử |
| [data/source_images/](data/source_images/) | Ảnh nguồn |
| [data/cropped_images_576x384/](data/cropped_images_576x384/) | Ảnh cắt đang dùng |
| [data/rejected_crops/](data/rejected_crops/) | Ảnh cắt đã loại khi duyệt |
| [outputs/inventory/](outputs/inventory/) | Trạng thái từng tệp, thống kê và đặc trưng toàn khung của yêu cầu 2; xem ghi chú hồ sơ cũ |
| [outputs/segmentation/grabcut/](outputs/segmentation/grabcut/) | Mask, overlay, manifest, nhật ký và lịch sử chỉnh sửa |

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
Cách cài Windows, phiên bản đã chạy trên macOS Intel, kiểm tra wheel Windows và
phạm vi tương thích nằm trong [hướng dẫn môi trường](docs/python_environments.md).

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
khi mở hàng đợi `needs_revision/` để chỉnh hoặc tạo lại mask.

## Phạm vi bản tinh gọn

- Giữ nguyên mã trong `tools/`, ba thư mục ảnh, kiểm kê yêu cầu 2, mask/manifest và B400 hiện hành.
- Giữ tám lượt truy vấn dùng trong báo cáo, phân tích bốn nhóm cuối, so sánh mask và các bản tổng kết kiểm chứng cuối trong [outputs/search/](outputs/search/README.md).
- Đã gỡ `tests/`, bản sao lưu lớn, hồ sơ di chuyển cũ, batch kiểm tra chức năng/di chuyển, bản xuất trùng và các log/kết quả trung gian.
- Các kết quả 62/62 artifact hoặc số kiểm thử đạt là số đo trước khi dọn, không phải số artifact hiện còn. Một số liên kết chứng cứ lịch sử trỏ về commit gốc trên GitHub.

Hướng dẫn cài đặt hiện hành ở [môi trường Python](docs/python_environments.md). Dùng các lệnh xử lý và đánh giá trong phần tương ứng để tạo kết quả mới.
