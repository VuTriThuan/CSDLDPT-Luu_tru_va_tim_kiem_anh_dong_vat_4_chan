# Môi trường Python trên Windows và macOS Intel

Chạy từ thư mục chứa `README.md`, `tools/`, `data/` và `outputs/`.
Dùng lại nguyên bộ `outputs/features/b400_v1/` có sẵn; tìm kiếm không trích xuất
lại CSDL và không fit scaler. Tạo venv mới trên từng máy; không sao chép venv
Mac sang Windows hoặc giữa hai đường dẫn.

## Phiên bản

| Thành phần | Chung `.venv/` | Công cụ ảnh `.venv-image-tools/` |
|---|---|---|
| CPython x86-64 | 3.10.11 | 3.10.11 |
| NumPy | 1.26.4 | 2.2.6 |
| Pillow | 12.3.0 | 11.3.0 |
| OpenCV headless | 4.11.0.86 (`cv2=4.11.0`) | Không cần |
| ONNX Runtime | 1.23.2 | 1.23.2 |
| certifi | Không cần | 2026.7.22 |
| Tkinter/Tcl/Tk trên Mac đã chạy | 8.6 | 8.6 |
| pyreadline3, chỉ Windows | 3.5.4 | 3.5.4 |

Các phụ thuộc gián tiếp khác giữ nguyên trong [requirements.txt](../requirements.txt)
và [requirements_image_tools.txt](../requirements_image_tools.txt). `pyreadline3`
được thêm bằng marker `sys_platform == "win32"` vì metadata wheel `humanfriendly`
yêu cầu nó với Python ≥3.8 trên Windows; không cài thêm trên Mac.
Wheel [pyreadline3 3.5.4](https://pypi.org/project/pyreadline3/3.5.4/) hỗ trợ Python ≥3.8.
Không thay các phiên bản đã ghim trước đó.

Môi trường chung chạy B400, tìm kiếm CLI/GUI, GrabCut, chỉnh/duyệt/đồng bộ mask,
validation và đổi tên ảnh. Môi trường ảnh chạy `auto_crop.py`, `review_images.py`,
`regenerate_masks.py`. Hai công cụ đầu tự chọn `.venv-image-tools/` nếu có;
`--setup` chỉ cài khi người dùng chủ động gọi. U²-Net cần model ngoài repo tại
`~/.cache/animal-crop/u2net.onnx`; GrabCut/B400/tìm kiếm không cần model này.

## Windows: cài bằng PowerShell

Dùng [Python 3.10.11](https://www.python.org/downloads/release/python-31011/)
bản x64 đầy đủ và chọn **tcl/tk and IDLE** trong installer. Tkinter là thành
phần của Python, không cài qua pip; xem [tài liệu installer](https://docs.python.org/3.10/using/windows.html#the-full-installer).
Phạm vi wheel đã kiểm tra là `win_amd64/cp310`; chưa kiểm tra Windows ARM64/32-bit.
Kiểm tra `py -3.10 --version` phải là `3.10.11`; launcher không tự đảm bảo đúng
patch nếu máy cài nhiều bản. Chạy kiểm tra đầu tiên bên dưới và chỉ tiếp tục khi đạt:

```powershell
py -3.10 -c "import struct, sys; assert sys.version_info[:3] == (3,10,11) and struct.calcsize('P') == 8; print(sys.executable)"
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r .\requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import cv2,numpy,PIL,tkinter; print(cv2.__version__,numpy.__version__,PIL.__version__,tkinter.TkVersion)"
# Mở cửa sổ nhỏ để xác nhận Tcl/Tk hoạt động; đóng nó rồi tiếp tục:
.\.venv\Scripts\python.exe -m tkinter

# Chỉ cần khi dùng công cụ cắt/duyệt ảnh hoặc U²-Net:
py -3.10 -m venv .venv-image-tools
.\.venv-image-tools\Scripts\python.exe -m pip install --only-binary=:all: -r .\requirements_image_tools.txt
.\.venv-image-tools\Scripts\python.exe -m pip check
```

Không cần activate venv hoặc đổi PowerShell ExecutionPolicy. Nếu kiểm tra
phiên bản/cài đặt báo lỗi, dừng tại lỗi đó; không thay requirements bằng phiên
bản mới hơn để ép chạy. Các wheel Windows của toàn bộ phiên bản ghim đã tải
được ngày 23/10/2026; đây là kiểm tra phân phối, chưa phải cài/chạy trên Windows.

## Windows: mở trạng thái, GUI và truy vấn

```powershell
.\.venv\Scripts\python.exe -B .\tools\features\cli.py status
.\.venv\Scripts\python.exe -B .\tools\features\cli.py verify
.\.venv\Scripts\python.exe -B .\tools\search\cli.py status
.\.venv\Scripts\python.exe -B .\tools\search\cli.py gui

.\.venv\Scripts\python.exe -B .\tools\search\cli.py query `
  --image .\data\cropped_images_576x384\Equus_asinus_0587.jpg `
  --mask .\outputs\segmentation\grabcut\masks\Equus_asinus_0587.jpg.png
.\.venv\Scripts\python.exe -B .\tools\search\cli.py query `
  --image .\data\cropped_images_576x384\equus-quagga_0663.jpg `
  --mask .\outputs\segmentation\grabcut\masks\equus-quagga_0663.jpg.png --include-self

# Thay đường dẫn và bbox bằng ảnh/vùng thật của bạn:
.\.venv\Scripts\python.exe -B .\tools\search\cli.py query --image 'C:\Anh\con vat.jpg' --bbox 10 10 500 300
```

BBox là X Y WIDTH HEIGHT, phải nằm trong kích thước ảnh; bỏ `--bbox` để tự tạo
mask, hoặc dùng `--mask` với PNG 0/255 đúng kích thước. GUI cho chọn ảnh, tô giữ/
loại, áp dụng GrabCut, hoàn tác, tìm 5 ảnh và xuất toàn bộ lượt vào `outputs/search/`.
Mặc định loại mọi tệp cùng hash ảnh truy vấn. `--include-self` vẫn xét riêng
`equus-quagga_0663.jpg` và `equus-quagga_0667.jpg`, không gộp hai tệp cùng hash.

## Windows: batch và score sau khi chuyển vị trí

```powershell
Copy-Item .\tools\search\query_manifest_template.csv .\outputs\search\new_queries.csv
# Điền CSV trước khi chạy; đường dẫn tương đối tính từ thư mục chứa CSV.
.\.venv\Scripts\python.exe -B .\tools\search\cli.py batch --manifest .\outputs\search\new_queries.csv

# Thay batch_ID bằng thư mục được lệnh batch vừa in ra.
$batchDir = '.\outputs\search\batch_ID'
.\.venv\Scripts\python.exe -B .\tools\search\cli.py score `
  --batch "$batchDir\batch.json" --judgments "$batchDir\judgments.csv" `
  --output-dir .\outputs\search\scored
```

Ví dụ một dòng kiểm tra chức năng trong CSV đặt tại `outputs/search/new_queries.csv`:

```csv
query_id,image,mask,label,group,purpose,x,y,width,height,strokes
donkey,../../data/cropped_images_576x384/Equus_asinus_0587.jpg,../segmentation/grabcut/masks/Equus_asinus_0587.jpg.png,Equus_asinus,donkey,functional_check,,,,,
```

Dùng `/` trong trường đường dẫn CSV để chia sẻ Mac/Windows. Với truy vấn độc
lập thật, điền `purpose=independent`; chỉ chấm `visual_relevant=0/1` sau khi
xem bằng mắt. Chưa chấm thì để trống. Không suy relevance từ nhãn hay việc
chạy thành công, không tính P@5 thị giác cho dữ liệu kiểm tra chức năng.

Khi chuyển batch, sao chép **toàn bộ thư mục** chứa `batch.json`, `judgments.csv`,
`queries/`. Batch mới lưu artifact POSIX tương đối, có hash và ID; score đối
chiếu bằng đường dẫn giao thức thay vì dấu phân cách hệ điều hành.
Đổi `$batchDir` tới vị trí mới rồi chấm, không sửa đường dẫn/hash/ID trong hồ sơ.
Đầu ra score phải ở trong `outputs/search/` của dự án đang chạy.

## macOS Intel

Chọn đúng Python 3.10.11 x86-64 trước khi tạo venv:

```sh
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
.venv/bin/python -m pip check
python3 -m venv .venv-image-tools
.venv-image-tools/bin/python -m pip install --only-binary=:all: -r requirements_image_tools.txt
.venv-image-tools/bin/python -m pip check

.venv/bin/python -B tools/features/cli.py status
.venv/bin/python -B tools/features/cli.py verify
.venv/bin/python -B tools/search/cli.py status
.venv/bin/python -B tools/search/cli.py gui
.venv/bin/python -B tools/search/cli.py query \
  --image data/cropped_images_576x384/Equus_asinus_0587.jpg \
  --mask outputs/segmentation/grabcut/masks/Equus_asinus_0587.jpg.png
.venv/bin/python -B tools/search/cli.py batch --manifest outputs/search/new_queries.csv
.venv/bin/python -B tools/search/cli.py score \
  --batch outputs/search/batch_ID/batch.json \
  --judgments outputs/search/batch_ID/judgments.csv --output-dir outputs/search/scored
```

## Tương thích B400, khóa và bảo toàn byte

`compatibility.py` tách fingerprint khỏi CLI. `compatibility.json` cho phép
chính xác một revision mã portable đã duyệt và bộ B400 cũ có ID
`35c929107f151144f09ce058e6859c808bd14f21acd25a28c7842f3b46792338`.
ID đó ràng buộc toàn bộ cấu hình, tên/thứ tự chiều, bốn hash mã gốc và runtime.
Mỗi lần nạp vẫn kiểm hash byte mã thực tế (cả CLI, I/O và module tương thích),
cấu hình descriptor, CPython x86-64 và đúng phiên bản Python/NumPy/OpenCV/Pillow
trong bảng. Chỉ các thay đổi khóa, đường dẫn, I/O và cách kiểm chứng được duyệt;
`b400.py`, `inputs.py`, `storage.py` giữ nguyên bytes. Mã khác, thứ tự chiều khác
hoặc runtime khác bị từ chối; không tự thêm vào allowlist, sửa metadata hay rebuild.
Trạng thái `legacy-io-compatible` mô tả cách đọc, không đổi provenance bộ cũ.

SQLite vẫn mở read-only, kiểm integrity/foreign keys, run/config/scaler và mọi
vector 400 chiều hữu hạn; scaler kiểm ID/checksum/quy tắc và sidecar. `verify`
đối chiếu thêm audit nguồn/mask/manifest/inventory, metadata và NPZ với SQLite.
Không fit lại scaler trong `verify`; chỉ in báo cáo ra console, không ghi
`verification.json` cũ. Raw → scaler frozen → vector chuẩn hóa vẫn so sánh chính
xác; trên Mac đo 324.800 phần tử có max absolute error=0, max ULP=0 ở cả chế độ
ma trận và từng vector. Chưa đo trên Windows, nên chưa nới ngưỡng. Nếu Windows
báo không tái hiện chuẩn hóa, phải đo chênh lệch ở môi trường đó trước khi duyệt
cách xử lý; không ghi lại vector/scaler hoặc bỏ kiểm tra. Hash byte/toàn vẹn tệp
và so sánh số thực là hai lớp riêng. Khoảng cách/xếp hạng giữ nguyên.

`.gitattributes` ép LF cho mã được băm. `data/`, `outputs/`, `reports/` dùng
`-text` để giữ nguyên cả JSON/CSV lịch sử có LF hoặc CRLF, và tệp nhị phân dùng
`binary`. Quy tắc tránh làm thay hash manifest/artifact khi `core.autocrlf=true`;
xem [tài liệu Git](https://git-scm.com/docs/gitattributes). Máy kiểm tra không có
`core.autocrlf/core.eol` tường minh và trước đó không có `.gitattributes`.
Đã thử checkout thực với `autocrlf=true` trong repo tạm: mã, CSV, JSON, JPEG giữ
đúng bytes. Không chạy `git add --renormalize` hoặc ghi lại toàn repo. Clone cũ đã
bị CRLF phải giữ riêng chỉnh sửa chưa commit rồi lấy lại đúng bytes từ bản gốc;
không sửa hash để ép nhận. Cần bàn giao cả `.gitattributes` cùng thay đổi mã.

`tools/file_lock.py` dùng `flock(LOCK_EX|LOCK_NB)` trên Mac và
[LockFileEx](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex)
qua `ctypes` trên Windows (exclusive, fail immediately, byte 0). Chỉ Win32 error
33 là tranh khóa; lỗi quyền/handle/hệ tệp giữ nguyên lỗi hệ điều hành. Đóng handle
hoặc kết thúc tiến trình nhả khóa; không dùng sự tồn tại của tệp làm khóa, không
xóa tệp lock. B400 dùng sibling `.b400_v1.lock`; mọi lần nạp SearchIndex/status/get
giữ cùng khóa đến khi đóng DB/NPZ, sau đó tìm kiếm dùng ma trận trong bộ nhớ.
Segmentation dùng chung `.run.lock`, công cụ ảnh dùng `.tool_anh.lock`.
Nếu đang bận, lệnh bị từ chối ngay; chạy lại sau khi tác vụ giữ khóa kết thúc.

Rebuild chủ động xây/kiểm chứng staging trước và đóng mọi handle của dự án.
Mac/Linux giữ exchange nguyên tử. Windows đổi bộ cũ sang sibling
`.b400_v1-previous`, rồi staging sang `b400_v1`; lỗi lần hai thì rollback.
Nếu rollback cũng lỗi, bộ cũ giữ trong sibling ngoài vùng tự dọn staging.
Lần mở tiếp theo dưới khóa phục hồi khi output vắng; nếu output đã tồn tại sau
lần đổi tên thứ hai thì dọn backup cũ. Thành công dọn staging/backup. Đây là **hai
bước đổi tên có khoảng trống**, không phải atomic exchange hay cam kết bền vững
khi mất điện. Đóng các chương trình SQLite/đọc tệp ngoài dự án trước rebuild;
chúng không tuân theo khóa và Windows có thể chặn rename. Dùng ổ cục bộ;
chưa kiểm chứng filesystem mạng. Không cần rebuild để dùng B400 bàn giao.

## Kiểm chứng ngày 23/10/2026

Máy thật: **macOS 13.7.6 Intel, CPython 3.10.11**, các phiên bản trong bảng;
`pip check` hai venv đạt. **Không có Windows thật: chưa có chức năng nào được
chứng minh chạy thực tế trên Windows.** Không cài hệ điều hành hay thay venv đang dùng.

| Kiểm tra | Bằng chứng thực hiện |
|---|---|
| Import/CLI | 7 CLI B400/search/segmentation mở `--help` khi cố ý chặn import `fcntl` |
| Bộ thật | Verify 812 ảnh + 812 mask; SQLite 812 vector × 400, hữu hạn, khớp NPZ/config/scaler; không refit |
| Khóa | Hai tiến trình Mac tranh khóa, từ chối ngay; kết thúc tiến trình giữ khóa thì dùng lại; exception/quyền/thiếu thư mục phân loại đúng |
| Win32 | Mock DLL kiểm cờ LockFileEx, mã 33 so với 5/6 và unlock; chưa gọi API trên Windows |
| Publish | Exchange Mac thật; mô phỏng hai rename Windows: thành công, lỗi lần 1/2, rollback lỗi và phục hồi sau gián đoạn |
| Staging nhỏ | Extract/verify thật trên **2 cặp fixture**, publish theo logic Windows, kiểm dọn và bảo toàn output khi staging lỗi; không rebuild 812 ảnh |
| Segmentation Mac | GrabCut/resume, phân loại overlay, sync apply/verify không symlink, MaskRepository tô/undo/refine/save trên fixture; pixel imread/imdecode khớp |
| Fingerprint | Từ chối mã thực tế, cấu hình/thứ tự chiều, runtime và scaler bị thay đổi trong fixture/mock |
| Truy vấn | Ảnh/mask CSDL loại tự khớp; include-self trả riêng zebra 0663 và 0667; mặc định loại cả 2 hash trùng |
| Ảnh ngoài | Hình minh họa sinh tạm, khác hash CSDL; GrabCut, tô giữ/loại, refine, top 5; chỉ kiểm chức năng |
| GUI Mac | Cửa sổ Tk 8.6 thật; widget/canvas events chọn ảnh, auto mask, tô, undo, refine, top 5, xem vector, export; hộp chọn tệp được stub, chưa duyệt tay |
| Batch | CLI/API dùng manifest tương đối trong đường dẫn có khoảng trắng/Tiếng Việt; sao chép cả batch, xóa bản gốc rồi score được; relevance để trống |
| Wheel Windows | Tải đủ 12 wheel mỗi môi trường (kể pyreadline3), kiểm Requires-Python và mọi Requires-Dist với marker Windows 3.10.11; chưa cài/import wheel trên Windows |
| Toàn vẹn | SHA-256 **6.037 tệp** data/outputs/reports trước/sau khớp, gồm B400 và NPZ 176 chiều; `main` giữ nguyên |

Script kiểm chứng, wheel và dữ liệu fixture nằm ngoài repo trong thư mục tạm;
không phục hồi `tests/`, backup hoặc hồ sơ di chuyển cũ. Không có dữ liệu chấm
thị giác mới, không công bố P@5. Giới hạn còn lại là thực thi Windows thật,
sai số số học Windows, thao tác GUI thủ công và filesystem ngoài ổ cục bộ.

Các tệp thay đổi trong lần bàn giao này (21 tệp, chưa commit/push):

| Vị trí | Tệp |
|---|---|
| Root | `.gitattributes`, `README.md`, `requirements.txt`, `requirements_image_tools.txt` |
| `docs/` | `python_environments.md` |
| `tools/` | `file_lock.py` |
| `tools/features/` | `cli.py`, `compatibility.py`, `compatibility.json`, `publication.py` |
| `tools/image_processing/` | `tool_common.py` |
| `tools/search/` | `cli.py`, `index.py`, `evaluation.py` |
| `tools/segmentation/` | `run_grabcut.py`, `edit_masks.py`, `regenerate_masks.py`, `sync_overlays.py` |
| `tools/validation/` | `verify_grabcut_results.py`, `verify_image_analysis.py`, `verify_regenerated_masks.py` |
