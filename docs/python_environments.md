# Môi trường Python và phụ thuộc — 17/10/2026

Đã kiểm kê hai môi trường, giữ môi trường chung ở `.venv/`, tạo mới
`.venv-image-tools/` tại root và gỡ `bo_tool_anh_576x384/.venv/` sau khi môi trường
thay thế và bản sao lưu được xác minh. Không di chuyển trực tiếp venv. Không
đổi phiên bản thư viện của môi trường chung, không xử lý hàng loạt dữ liệu thật.

## Phiên bản và quyết định dùng hai môi trường

Máy kiểm tra: **macOS 13.7.6 Intel x86_64, CPython 3.10.11 64-bit**.
Python nền: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3`.
`.python-version` ghi `3.10.11`; khi cài trên máy khác cần chọn đúng interpreter,
không giả định mọi lệnh `python3` đều trỏ tới phiên bản này.

| Thành phần | Chung `.venv/` | Ảnh `.venv-image-tools/` |
|---|---|---|
| Python | 3.10.11 | 3.10.11 |
| NumPy | 1.26.4 | 2.2.6 |
| Pillow | 12.3.0 | 11.3.0 |
| ONNX Runtime | 1.23.2 | 1.23.2 |
| opencv-python-headless | 4.11.0.86; `cv2.__version__=4.11.0` | Không cần cho nhóm ảnh |
| certifi | Không được các công cụ được chỉ định yêu cầu | 2026.7.22 |
| Tkinter/Tcl/Tk | 8.6, thư viện của Python | 8.6, thư viện của Python |
| pip / setuptools | 23.0.1 / 65.5.0 | 23.0.1 / 65.5.0 |

Hai bộ NumPy/Pillow được giữ theo môi trường đã kiểm chứng trước đây để tránh
đổi thư viện tính toán/render trong cùng bước chuẩn hóa. `.venv/` có cấu trúc
đúng và `pip check` đạt nên được giữ nguyên. Môi trường ảnh cũ có `home` và symlink
qua `.venv/bin/` của root; môi trường mới được tạo từ Python nền, không còn phụ
thuộc interpreter của venv khác. Pip/setuptools được ghi nhận như công cụ cài đặt;
hai requirements ghim các package runtime, không tự nâng pip lên bản mới nhất.
`.gitignore` bỏ qua hai venv tại root đối với tệp mới. Các tệp môi trường đã
được Git theo dõi vẫn có trạng thái theo dõi; việc gỡ môi trường cũ tạo các mục
xóa tương ứng trong Git, đúng phạm vi gỡ đã yêu cầu.

[requirements.txt](../requirements.txt) và
[requirements_image_tools.txt](../requirements_image_tools.txt) ghim cả thư viện
trực tiếp và bảy phụ thuộc gián tiếp đang dùng: `coloredlogs==15.0.1`,
`flatbuffers==25.12.19`, `humanfriendly==10.0`, `mpmath==1.3.0`,
`packaging==26.3`, `protobuf==7.36.2`, `sympy==1.14.0`.
Mỗi môi trường có 11 package runtime. Không cài rembg, PyTorch, numba hoặc
llvmlite cho các công cụ hiện có.

## Công cụ dùng môi trường nào

Các lệnh dưới chạy từ root BTL, chỉ hiện trợ giúp:

| Công cụ | Thư viện ngoài thư viện chuẩn thực sự dùng | Lệnh đã kiểm tra |
|---|---|---|
| Cắt ảnh | NumPy, Pillow, certifi; ONNX Runtime khi suy luận | `.venv-image-tools/bin/python tools/image_processing/auto_crop.py --help` |
| Đổi tên ảnh | Chỉ thư viện chuẩn | `.venv/bin/python tools/image_processing/rename_images.py --help` |
| Duyệt ảnh | Pillow, Tkinter cho giao diện | `.venv-image-tools/bin/python tools/image_processing/review_images.py --help` |
| GrabCut | NumPy, Pillow, OpenCV | `.venv/bin/python tools/segmentation/run_grabcut.py --help` |
| Duyệt overlay | Pillow, Tkinter | `.venv/bin/python tools/segmentation/review_overlays.py --help` |
| Chỉnh mask | NumPy, Pillow, OpenCV, Tkinter | `.venv/bin/python tools/segmentation/edit_masks.py --help` |
| Đồng bộ overlay | NumPy, Pillow, OpenCV qua module GrabCut | `.venv/bin/python tools/segmentation/sync_overlays.py --help` |
| Tạo lại mask | NumPy, Pillow, ONNX Runtime | `.venv-image-tools/bin/python tools/segmentation/regenerate_masks.py --help` |
| Kiểm kê ảnh | Pillow | `.venv/bin/python tools/validation/audit_images.py --help` |
| Xác minh GrabCut | NumPy, Pillow, OpenCV qua module GrabCut | `.venv/bin/python tools/validation/verify_grabcut_results.py --help` |
| Xác minh mask tạo lại | NumPy, Pillow, ONNX Runtime qua module tạo mask | `.venv/bin/python tools/validation/verify_regenerated_masks.py --help` |

`tools/project_paths.py`, `tool_common.py` và các `__init__.py` là module hỗ trợ,
không có CLI riêng. Bảng import tĩnh, kể cả import trong hàm, nằm ở
[dependency_matrix.json](environment_migration_audit/dependency_matrix.json).
ONNX Runtime trong môi trường chung cần cho verifier import module tạo lại mask;
certifi cần cho HTTPS và được import khi nạp công cụ cắt ảnh.

`auto_crop.py` và `review_images.py` tự chọn `.venv-image-tools/` khi chạy từ
Python khác. `--setup` đọc `requirements_image_tools.txt` ở root, kiểm tra
`pip check`, tạo môi trường từ `sys.base_prefix` để tránh symlink về một venv
đang gọi nó. Mã tạo mask/thuật toán và trạng thái dữ liệu được giữ nguyên;
chỉ sửa định tuyến môi trường, lệnh hướng dẫn và thông báo thiếu thư viện.

## Tạo lại môi trường tại đúng vị trí

Trên máy đang dùng không cần cài lại. Với máy mới có Python 3.10.11 và Tkinter:

```sh
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
.venv/bin/python -m pip check

python3 -m venv .venv-image-tools
.venv-image-tools/bin/python -m pip install --only-binary=:all: -r requirements_image_tools.txt
.venv-image-tools/bin/python -m pip check
```

Không sao chép/đổi tên venv sang vị trí khác để dùng trực tiếp. Không tạo lại đè
lên môi trường đang chạy; dừng các công cụ và giữ bản sao đã xác minh trước.
Tkinter là thành phần của Python/Tcl/Tk, không có dòng pip requirements tương ứng.
Kiểm tra import bằng `python3 -c "import tkinter; print(tkinter.TkVersion)"`.

Trên Windows, nhóm công cụ ảnh dùng `.venv-image-tools\Scripts\python.exe` và
tạo môi trường tại root bằng Python trên máy Windows. Các kiểm tra ở đây chỉ
chạy trên macOS Intel/Python 3.10.11; wheel/lock offline dưới đây dành cho nền
tảng đó. Dependency marker của `humanfriendly` có thể yêu cầu thêm `pyreadline3`
trên Windows; requirements hiện ghim đầy đủ tập package được kiểm kê trên Mac,
không phải lock đã xác minh cho Windows. Nhóm GrabCut/segmentation hiện còn
import `fcntl`, nên không xác nhận hỗ trợ Windows cho nhóm này.

### Cài lại offline có kiểm tra hash

Đã tìm được 14 wheel trong cache pip, giữ nguyên bytes, kiểm tra tag tương thích
và lưu tại:

`outputs/backups/pre_environment_migration_20261017_105624/wheels/`

Mỗi wheel có SHA-256 trong `wheels.sha256`. Hai lock chứa chính xác các phiên bản
trên và hash wheel tương ứng, dùng `--require-hashes`; không sửa nội dung wheel.
Môi trường ảnh mới đã được cài hoàn toàn offline bằng lock này.
Lock chung cũng đã giải phụ thuộc thành công bằng `pip install --dry-run
--ignore-installed --no-index --require-hashes`, không cài đè môi trường chung;
xem [shared_lock_resolution.json](environment_migration_audit/shared_lock_resolution.json).

```sh
# Sau khi tạo venv mới ở đúng vị trí bằng Python nền:
.venv/bin/python -m pip install --no-index --find-links outputs/backups/pre_environment_migration_20261017_105624/wheels --only-binary=:all: --require-hashes -r outputs/backups/pre_environment_migration_20261017_105624/wheels/shared_macos_cp310.lock
.venv-image-tools/bin/python -m pip install --no-index --find-links outputs/backups/pre_environment_migration_20261017_105624/wheels --only-binary=:all: --require-hashes -r outputs/backups/pre_environment_migration_20261017_105624/wheels/image_tools_macos_cp310.lock
```

Metadata nguồn cache, tên/tag, kích thước và hash ở
[cached_wheels.json](environment_migration_audit/cached_wheels.json),
[wheelhouse.json](environment_migration_audit/wheelhouse.json).
Không tải package hay model mới. Model U²-Net vẫn ở
`~/.cache/animal-crop/u2net.onnx`, SHA-256
`8d10d2f3bb75ae3b6d527c77944fc5e7dcd94b29809d47a739a7a728a912b491`.

## Kiểm tra và điều kiện gỡ môi trường cũ

- `pip check` đạt cho cả hai môi trường; toàn bộ phiên bản package của môi
  trường ảnh mới khớp môi trường cũ, gồm cả pip/setuptools.
- 11 công cụ import được bằng interpreter trong bảng, 22 lệnh `--help` trực
  tiếp/module đạt; lệnh trực tiếp còn được chạy từ thư mục tạm ngoài dự án.
  Hai lệnh cắt/duyệt khởi chạy từ Python chung cũng tự chọn môi trường ảnh mới.
- 38 kiểm thử đạt: 24 công cụ ảnh, 14 validation. Kiểm tra tạo venv từ bên trong
  venv dùng Python nền đã đạt; hồi quy AST vẫn bảo vệ thuật toán.
- Cắt ảnh trên bản sao nhỏ và tạo lại mask trên một ảnh sinh tạm bằng
  `.venv-image-tools/` đạt. Resume bộ tạm dùng lại đúng một ảnh, không xử lý lại.
  Không ghi vào ảnh, manifest, lịch sử hoặc trạng thái thật.
- Đã khôi phục đầy đủ 8.175 mục của môi trường ảnh cũ từ archive vào thư mục
  tạm, kiểm tra hash và import thành công NumPy/Pillow/ONNX Runtime/certifi từ
  chính cây khôi phục. Thư mục tạm được gỡ sau kiểm tra.
- Sau các điều kiện trên mới gỡ `bo_tool_anh_576x384/.venv/`; giữ requirements,
  cache và các mục khác của thư mục cũ. Môi trường chung không bị gỡ hay tạo lại.
  Chạy lại các kiểm tra trợ giúp sau khi gỡ để loại trừ phụ thuộc vào vị trí cũ.

Kết quả chi tiết: [smoke_checks.json](environment_migration_audit/smoke_checks.json),
[image_tests.log](environment_migration_audit/image_tests.log),
[validation_tests.log](environment_migration_audit/validation_tests.log),
[image_inference_check.json](environment_migration_audit/image_inference_check.json),
[legacy_restore_verification.json](environment_migration_audit/legacy_restore_verification.json),
[legacy_environment_removal.json](environment_migration_audit/legacy_environment_removal.json).
GUI chưa mở cửa sổ trong bước này; đã kiểm tra import Tkinter và trợ giúp.
Đối chiếu sau bước này xác nhận **8.279 mục của môi trường chung** giữ nguyên,
**5.848 tệp dữ liệu/kết quả/trạng thái** giữ nguyên tên, nội dung và mtime.
Bốn seal audit giai đoạn trước và hai báo cáo phân tích vẫn khớp. Kết quả ở
[verification.json](environment_migration_audit/verification.json); kiểm thử ảnh
sau khi gỡ môi trường cũ ở [post_removal_image_tests.log](environment_migration_audit/post_removal_image_tests.log).

## Sao lưu và cách khôi phục

Trước thay đổi còn 36.690.673.664 byte trống; mức cần cho snapshot, khôi phục và
dự phòng là 2.781.745.844 byte. Archive **814.602.240 byte**:

`outputs/backups/pre_environment_migration_20261017_105624/before_environment_migration.tar`

SHA-256 `931073a20bb94d476197b522a789b4952db2c86e5e81e2c2b71a6a8715c7b02e`.
Chứa nguyên cả hai môi trường cũ (kể cả symlink, tệp ẩn), mã, tests, docs, README
và thư mục công cụ ảnh cũ. Đã đọc/đối chiếu **15.018 tệp trong 16.639 mục**,
khôi phục thử 12 mục trước khi thay đổi và khôi phục đầy đủ môi trường ảnh như
nêu trên. Kiểm kê mode, mtime, xattr và SHA-256 nằm ở `snapshot_inventory.json`
cạnh archive. Bản sao toàn dự án ban đầu cũng được băm lại và vẫn đúng SHA-256.
Xem [preflight.json](environment_migration_audit/preflight.json).

Để khôi phục môi trường ảnh đang dùng, dừng công cụ, giữ thư mục lỗi ở nơi sao
lưu riêng, tạo **mới tại `.venv-image-tools/`** bằng Python nền và cài từ lock
offline ở trên, rồi chạy `pip check`, import và các lệnh trợ giúp trong bảng.
Không đổi `run_config.json` hoặc hash lịch sử để ép resume.

Nếu cần hoàn tác về đúng môi trường/vị trí cũ, dừng công cụ; kiểm tra hash archive,
trích vào thư mục staging trống rồi đối chiếu `snapshot_inventory.json`. Khôi phục
`bo_tool_anh_576x384/.venv/` về chính đường dẫn gốc và mã định tuyến cũ
`tools/image_processing/tool_common.py` cùng hướng dẫn từ archive. Các shebang
cũ chỉ có nghĩa khi đường dẫn BTL và Python nền còn đúng như mốc sao lưu.
Môi trường chung hiện không đổi, không cần phục hồi nó cho hoàn tác riêng bước
này. Đọc/khôi phục thử mà chưa thay cây đang dùng bằng:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B docs/environment_migration_audit/restore_legacy_check.py
```

Các config/kiểm kê lịch sử, tên ảnh, kết quả và các khác biệt trạng thái đã nêu
trong các giai đoạn trước được giữ nguyên. Đã dừng sau bước môi trường Python.
