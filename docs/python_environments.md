# Môi trường Python và cách cài đặt

Hướng dẫn hiện hành cho Mac Intel. Hồ sơ chuyển môi trường, wheel sao lưu và các script kiểm thử lịch sử đã được gỡ khỏi nhánh tinh gọn. Không sao chép trực tiếp venv từ vị trí cũ.

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

Hai bộ NumPy/Pillow giữ theo môi trường đã sử dụng để tránh làm thay đổi kết quả tính toán. Các phụ thuộc được ghim trong [requirements.txt](../requirements.txt) và [requirements_image_tools.txt](../requirements_image_tools.txt); không tự nâng cấp thư viện khi dùng SQLite B400 đã tính.

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


`tools/project_paths.py`, `tool_common.py` và các `__init__.py` là module hỗ trợ. `auto_crop.py` và `review_images.py` tự chọn `.venv-image-tools/`; tùy chọn `--setup` đọc requirements tại root. Nhóm B400/tìm kiếm dùng `.venv/`.

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
chạy trên macOS Intel/Python 3.10.11; các bản wheel đã dùng trước đây dành cho nền tảng đó. Dependency marker của `humanfriendly` có thể yêu cầu thêm `pyreadline3`
trên Windows; requirements hiện ghim đầy đủ tập package được kiểm kê trên Mac,
không phải lock đã xác minh cho Windows. Nhóm GrabCut/segmentation hiện còn
import `fcntl`, nên không xác nhận hỗ trợ Windows cho nhóm này.

## Chạy B400 và tìm kiếm

```sh
.venv/bin/python -B tools/features/cli.py status
.venv/bin/python -B tools/search/cli.py status
.venv/bin/python -B tools/search/cli.py gui
```

Index kiểm tra phiên bản Python/thư viện và hash mã với cấu hình B400 đã lưu. Nếu không khớp, sửa môi trường cho đúng; không sửa hash để bỏ qua kiểm tra và không fit lại scaler khi truy vấn.

Model U²-Net của nhóm cắt ảnh/tạo lại mask dùng cache ngoài dự án tại `~/.cache/animal-crop/u2net.onnx`. Nhánh tinh gọn không chứa bản sao model hay wheel cài đặt offline trong `outputs/backups/`. Tìm kiếm GrabCut/B400 không cần model U²-Net để mở index và chạy truy vấn.
