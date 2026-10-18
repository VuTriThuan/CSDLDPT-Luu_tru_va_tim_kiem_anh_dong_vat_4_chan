# Hai tool xử lý bộ ảnh động vật bốn chân

Nhật ký hiện hành vẫn tên `_cat_tu_dong.json`. Bộ đọc nhận cả đường dẫn nguồn cũ
trong nhật ký; quyết định lật/loại được giữ nguyên. Với thư mục mặc định, D chuyển
ảnh vào `data/rejected_crops/`; với thư mục tùy chọn khác, dùng hậu tố `-da-xoa` như trước.
Xem [báo cáo chuyển dữ liệu](../data_migration.md) về chuyển đổi state và các khác biệt sẵn có.

## 1. Đặt file và cài thư viện trên macOS hoặc Windows

Mã nguồn đã chuyển vào `tools/image_processing/`; ba thư mục ảnh dùng tên mới
`source_images/`, `cropped_images_576x384/`, `rejected_crops/`. Requirements và môi trường
Python vẫn ở vị trí cũ; chạy các ví dụ từ thư mục gốc BTL.

Chép dự án vào `Desktop/CSDLDPT/BTL` trên cả hai máy. Giữ cấu trúc:

```text
BTL/
  tools/
    __init__.py
    project_paths.py
    image_processing/
      __init__.py
      auto_crop.py
      rename_images.py
      review_images.py
      tool_common.py
  bo_tool_anh_576x384/
    requirements.txt
    .venv/                 # môi trường hiện có trên macOS
    .venv-windows/         # chỉ có nếu đã setup trên Windows
  tests/image_processing/
    test_compatibility.py
  data/
    source_images/
    cropped_images_576x384/
    rejected_crops/
```

Tool tìm `data` theo vị trí thư mục chứa mã, nên dùng được cả Desktop thông thường
và Desktop nằm trong OneDrive. Không phụ thuộc tên tài khoản hay thư mục đang mở Terminal.
Yêu cầu Python 3.10–3.13, macOS 13+ (Intel/Apple Silicon) hoặc Windows 10/11 x64.
Tool duyệt cần Tkinter. Trên Windows, nên dùng Python 3.13 64-bit.
Chức năng cài đặt và khởi chạy đã tích hợp trong hai file Python; không cần file `.bat`.

### macOS

Mở Terminal, chạy từng lệnh:

```bash
cd ~/Desktop/CSDLDPT/BTL
python3 tools/image_processing/auto_crop.py --setup
python3 tools/image_processing/auto_crop.py --limit 30
python3 tools/image_processing/review_images.py
```

Chỉ chạy `--setup` một lần khi mới cài hoặc khi cần cài lại thư viện. Tool tự tạo
và dùng `bo_tool_anh_576x384/.venv`, không cần kích hoạt môi trường ảo mỗi lần mở Terminal.
Nếu thiếu Tkinter, kiểm tra `python3 -m tkinter`. Dùng bản Python macOS từ
https://www.python.org/downloads/macos/ có Tkinter rồi tạo lại môi trường bằng bản Python đó.
Nếu pip không có wheel phù hợp, kiểm tra `python3 --version`, `uname -m` và phiên bản macOS.
Không bỏ `--only-binary` để cố build thư viện trên máy cũ.

### Windows

1. Cài Python **3.13 64-bit** từ https://www.python.org/downloads/windows/.
   Giữ các thành phần **Python Launcher** và **Tcl/Tk and IDLE** khi cài.
2. Mở PowerShell trong `Desktop\CSDLDPT\BTL`.
3. Chạy lệnh cài đặt một lần, rồi mở tool cắt hoặc duyệt bằng các lệnh sau.

```powershell
py -3.13 tools/image_processing/auto_crop.py --setup
py -3.13 tools/image_processing/auto_crop.py --limit 30
py -3.13 tools/image_processing/review_images.py
```

`--setup` tự tạo `bo_tool_anh_576x384/.venv-windows` và cài thư viện. Các lần chạy sau, hai tool tự dùng
môi trường này, không cần bật `activate` hoặc thay đổi chính sách PowerShell.
Có thể dùng `python3 tools/image_processing/review_images.py --setup` để cài đặt cùng môi trường đó.
Đóng tool duyệt trước khi chạy cắt vào cùng thư mục.

Các ví dụ `python ...` ở phần dưới có thể dùng với `python3` trên Mac hoặc
`py -3.13` trên Windows. Nếu máy đã nhận lệnh `python`, có thể dùng trực tiếp.
Chạy `--setup` riêng, không ghép với `--limit`, `--folder` hay các tùy chọn xử lý ảnh.

Nếu Desktop nằm trong OneDrive, mở Terminal/PowerShell tại thư mục thực tế của dự án.

Không dùng lại `.venv` từ máy Mac trên Windows hoặc `.venv-windows` từ Windows trên Mac.
Nếu chuyển máy, có thể bỏ qua cả hai thư mục môi trường ảo và `__pycache__` khi chép;
giữ đầy đủ các file `.py`, `requirements.txt` và thư mục `data`, rồi chạy lại `--setup`
trên máy mới. Cài thư viện cần kết nối Internet.

### Chuyển dữ liệu giữa hai máy

Chép cả `data`, gồm ảnh gốc, kết quả, ảnh đã xóa và `_cat_tu_dong.json`.
Nhật ký mới dùng đường dẫn tương đối và SHA-256 của ảnh gốc để giữ tiến độ,
quyết định xóa/lật ngay cả khi đường dẫn tuyệt đối hoặc thời gian sửa file thay đổi.
Giữ nguyên cấu trúc tương đối giữa thư mục ảnh gốc và thư mục kết quả.

Nhật ký hiện có trong dự án đã được cập nhật sang dạng này. Với bản nhật ký cũ khác,
chạy tool cắt phiên bản mới trên máy cũ trước khi chép để bổ sung thông tin chuyển máy.
Không dùng `--force` khi muốn giữ kết quả đã duyệt.
Bản nhật ký gốc trước lần cập nhật này được giữ tại `_cat_tu_dong.truoc-cap-nhat.json`.

## 2. Tool 1: tự tìm vùng con vật và cắt 576 × 384

Cắt thử tối đa 30 ảnh chưa xử lý:

```bash
python tools/image_processing/auto_crop.py --limit 30
```

Duyệt kết quả mẫu bằng tool 2. Sau khi đóng cửa sổ duyệt, cắt tiếp tất cả ảnh:

```bash
python tools/image_processing/auto_crop.py
```

Kết quả JPG nằm ở `BTL/data/cropped_images_576x384`.
Lần đầu mô hình U²-Net tải về khoảng 176 MB từ bản ONNX của dự án rembg.
Các lần sau dùng lại tệp đã tải. Ảnh được xử lý tại máy, không gửi lên dịch vụ.
Tool giữ nguyên ảnh gốc và nền tự nhiên trong vùng cắt. Khung cắt luôn nằm trong
ảnh gốc nên không thêm viền trắng. Nó thu phóng cùng hệ số hai chiều, giữ hình dáng,
đưa tâm khung bao con vật vào gần giữa khung 576 × 384; mức chiếm khung mặc định 85%.
Nếu ảnh gốc không đủ rộng hoặc cao, khoảng trống quanh con vật sẽ ít hơn; trường hợp
không thể giữ trọn chủ thể ở tỉ lệ 3:2 sẽ được ghi cảnh báo để duyệt lại.
Mô hình tìm chủ thể nổi bật, KHÔNG nhận dạng tên loài, không đảm bảo ảnh có đúng
một con đang đứng, chụp ngang hoặc đầu hướng trái. Bạn kiểm tra các điều kiện này khi duyệt.
Phần tai/chân/đuôi có thể bị mô hình bỏ sót; khoảng trống quanh chủ thể giúp giảm rủi ro.
Không mô hình nào đảm bảo cắt đúng toàn bộ ảnh. Đây là lý do cần tool duyệt.

Nếu muốn mô hình nhỏ hơn, thử riêng với đầu ra khác:

```bash
python tools/image_processing/auto_crop.py --model u2netp --limit 30 --output "data/anh-thu-u2netp"
python tools/image_processing/review_images.py --folder "data/anh-thu-u2netp"
```

U²-NetP khoảng 5 MB, chất lượng vùng chủ thể có thể khác. Không có số đo thời gian
trên từng máy; CPU, kích thước nguồn và mô hình ảnh hưởng tốc độ.
Có thể thêm `--threads 1` nếu muốn giảm tải CPU.

Các tùy chọn khác:

```bash
python tools/image_processing/auto_crop.py --recursive
python tools/image_processing/auto_crop.py --input "data/source_images" --output "data/ket-qua-khac"
```

`--recursive` đọc cả thư mục con. Tên file trùng nhau được thêm hậu tố để không
ghi đè ảnh khác. JPG/PNG/WEBP/BMP/TIFF được hỗ trợ; HEIC cần đổi sang JPG trước.
`Ctrl+C` dừng; chạy lại cùng lệnh sẽ tiếp tục. Tool lưu trạng thái sau từng ảnh
trong `_cat_tu_dong.json`; giữ file này để tiếp tục và liên kết với tool 2.
`bao_cao_cat.csv` liệt kê ảnh lỗi, cảnh báo sát mép, nhiều vùng chủ thể và ảnh phóng lớn.
Ảnh không định vị được sẽ không tạo JPG giả; xem cột lỗi và cắt thủ công từ ảnh gốc
bằng tool khoanh chuột đã có. Không xóa ảnh gốc khi mô hình báo lỗi.
Ảnh đã lưu nhưng được xóa trong tool 2 sẽ không tự xuất lại khi chạy cùng cấu hình.
`--force` sẽ tạo lại từ ảnh gốc, gồm cả ảnh đã xóa/lật; chỉ dùng khi muốn bỏ kết quả duyệt.
Để sửa viền trắng ở các ảnh đã cắt trước đây mà không tải/chạy lại mô hình, dùng:

```bash
python tools/image_processing/auto_crop.py --repair-borders
```

Lệnh này tạo lại các ảnh còn trong thư mục kết quả bằng khung bao chủ thể đã lưu,
giữ hướng lật và không khôi phục ảnh đã xóa. Ảnh thiếu đầu ra hoặc ảnh gốc đã đổi
sẽ được bỏ qua và liệt kê trên màn hình.
Không chạy hai tool cùng lúc trên cùng thư mục. Tool có khóa để tránh ghi đè tiến độ.

## 3. Tool 2: duyệt và sửa kết quả

```bash
python tools/image_processing/review_images.py
```

| Phím | Thao tác |
|---|---|
| D | Xóa ảnh hiện tại khỏi bộ ảnh, chuyển ngay sang ảnh tiếp |
| A | Lật ngang trái/phải và lưu ngay tại chỗ |
| ← / → | Ảnh trước / sau |
| U | Hoàn tác thao tác gần đây trong phiên hiện tại |
| Esc | Thoát |

Ở đây “quay ngược” là LẬT NGANG để đổi hướng đầu con vật; không xoay 180 độ.
Ảnh xóa được chuyển vào thư mục `rejected_crops` cùng cấp, nên có thể
khôi phục sau khi đóng tool. U hỗ trợ tối đa 50 thao tác gần nhất trong phiên.
A lưu lại JPG chất lượng 95. Lật nhiều lần vẫn có tái nén; dùng U để khôi phục
chính xác bytes của ảnh trước thao tác nếu lật nhầm.
Tool duyệt trực tiếp mọi ảnh ở thư mục được chọn, không duyệt thư mục con.
Nó cập nhật nhật ký và CSV của tool 1 nếu có, bảo toàn quyết định xóa khi chạy cắt lại.
Không có tự động xác định bên đầu/đuôi; bạn bấm A khi con vật đang hướng phải.

## 4. Kiểm tra trước khi đưa vào bộ dữ liệu

- Đúng một con vật, đang đứng, ảnh chụp ngang.
- Đủ cơ thể; không mất chân, tai, sừng, đuôi hoặc vòi.
- Đầu hướng trái, con vật nằm gần tâm và chiếm khung tương đối đồng đều.
- Ảnh rõ, màu sắc tự nhiên; không bị kéo méo.
- JPG có kích thước 576 × 384. Nếu dữ liệu cũ khác kích thước, xử lý lại từ nguồn.

Tool xử lý vùng chủ thể. Bộ dữ liệu đạt đề bài vẫn cần bạn duyệt tư thế và chất lượng.

## Nguồn mô hình và tương thích

- U²-Net: https://github.com/xuebinqin/U-2-Net
- Bản ONNX và thông số tiền xử lý: https://github.com/danielgatis/rembg/tree/main/rembg/sessions
- ONNX Runtime 1.23.2 có wheel cho Windows x64, macOS Intel/Apple Silicon, Python 3.10–3.13:
  https://pypi.org/project/onnxruntime/1.23.2/
- Khóa thư mục dùng `fcntl.flock` trên macOS và `msvcrt.locking` trên Windows:
  https://docs.python.org/3/library/msvcrt.html

Tool tải mô hình qua HTTPS và kiểm tra checksum đã công bố. Không cần cài rembg,
PyTorch, OpenCV, numba hoặc llvmlite. File mô hình không kèm trong gói ZIP.

## Phạm vi kiểm tra bản giao

Đã chạy bộ kiểm tra trên macOS: khóa giữa hai tiến trình, nhả khóa khi lỗi,
chuyển thư mục và thay đổi thời gian sửa file mà vẫn giữ xóa/lật, nhận ra nội dung
ảnh gốc đã đổi, tên ảnh tiếng Việt, tên trùng chữ hoa/thường và xóa/lật/hoàn tác.
Nhánh `msvcrt` được kiểm tra bằng mô phỏng API Windows. Đã chạy mô hình U²-Net
thật trên một bản sao ảnh, xác nhận kết quả 576 × 384 và chạy lại không cắt lại.

Đã kiểm tra khởi động lại bằng môi trường ảo, chuyển nguyên tham số và mã thoát,
và gọi cài đặt trước khi tải các thư viện xử lý ảnh.
Chưa chạy trực tiếp cài đặt, khóa hoặc giao diện trên máy Windows thật.
Cắt thử 30 ảnh trên máy Windows trước khi xử lý cả bộ dữ liệu.
Để chạy bộ kiểm tra, đứng tại thư mục gốc BTL. Trên Mac:

```text
bo_tool_anh_576x384/.venv/bin/python -B -m unittest discover -s tests/image_processing -v
```

Trên Windows (PowerShell):

```powershell
.\bo_tool_anh_576x384\.venv-windows\Scripts\python.exe -m unittest discover -s tests/image_processing -v
```
