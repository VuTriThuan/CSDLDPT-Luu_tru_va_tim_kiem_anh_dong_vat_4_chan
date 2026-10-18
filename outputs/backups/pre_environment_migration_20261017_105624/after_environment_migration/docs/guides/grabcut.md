# Tạo mask ứng viên để duyệt trên macOS

Mã nguồn ở `tools/segmentation/` và `tools/validation/`; ảnh ở
`data/cropped_images_576x384/`, kết quả lịch sử ở `outputs/segmentation/grabcut/`.
Chạy từ root BTL bằng `.venv/bin/python`. Bộ lịch sử vẫn đọc được, nhưng **không
resume bằng mã hiện tại** vì hash mã, đường dẫn nguồn và phiên bản thư viện đã
khác. Giữ nguyên `run_config.json`; không sửa hash hoặc bỏ kiểm tra toàn vẹn.
Xem [báo cáo chuyển kết quả](../results_migration.md).

Để bắt đầu an toàn, chọn một thư mục mới chưa tồn tại. Ví dụ dưới chỉ là hướng dẫn,
chưa được chạy trên bộ ảnh thật trong lần chuyển này:

```sh
# Bắt đầu bộ mới bằng 8 ảnh; đổi tên thư mục nếu ví dụ này đã được dùng.
.venv/bin/python tools/segmentation/run_grabcut.py --limit 8 --output-dir outputs/segmentation/grabcut_run_20261017_01

# Chỉ tiếp tục bộ mới đó khi mã, thư viện, nguồn và tham số vẫn như lần đầu.
.venv/bin/python tools/segmentation/run_grabcut.py --all --resume --output-dir outputs/segmentation/grabcut_run_20261017_01
```

Có thể nhấn **Ctrl+C** để ngắt rồi chạy lại cùng lệnh với `--resume`. Manifest được
ghi nguyên khối bằng thao tác thay tệp sau từng ảnh. Nếu tiến trình bị tắt đột ngột,
ảnh đang xử lý có thể phải chạy lại. Khi chạy tiếp, script so SHA-256 của ảnh nguồn,
mask và ảnh phủ, chỉ bỏ qua kết quả thành công còn nguyên vẹn; ảnh lỗi, thiếu hoặc
hỏng kết quả được chạy lại. Trạng thái duyệt của kết quả được dùng lại được giữ nguyên;
kết quả tạo lại quay về `chua_duyet`. Không chạy đồng thời hai tiến trình trên cùng
thư mục đầu ra. Không sửa CSV trong khi tiến trình đang chạy.

Môi trường chung ở `.venv/` dùng bộ phiên bản trong `requirements.txt` tại root.
Trên máy mới, cài Python 3.10.11 có Tkinter và tạo lại tại đúng vị trí:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
.venv/bin/python -m pip check
```

Dùng `.venv/` chung cho nhóm GrabCut. Xem [kiểm kê môi trường](../python_environments.md)
để biết phiên bản cụ thể và cách cài offline bằng wheel có hash.

Mỗi thư mục đầu ra ghi phiên bản thư viện trong `run_config.json`. Nếu thay thư viện,
tham số hoặc mã script, chọn thư mục đầu ra mới để tránh trộn các lần chạy.

## Kích thước và thuật toán

Mặc định không resize: bộ ảnh hiện tại và mask/ảnh phủ đều **576 × 384**.
Tùy chọn `--max-side 384` thu nhỏ cạnh dài về tối đa 384, giữ tỉ lệ, nên ảnh
576 × 384 thành **384 × 256**; không phóng to ảnh nhỏ. Khi đổi kích thước cần chọn
thư mục đầu ra riêng, ví dụ:

```sh
.venv/bin/python tools/segmentation/run_grabcut.py --all --max-side 384 --output-dir outputs/segmentation/grabcut_384
```

Script dùng GrabCut khởi tạo hình chữ nhật cách biên 10 pixel, 5 vòng lặp,
opening/closing với kernel elip 5 × 5, mỗi phép 2 lần; các kích thước này tính trên
ảnh đang xử lý. Seed 0, một luồng OpenCV. Không còn phụ thuộc tệp trong Downloads.
Giữ cách tạo mask của hàm tham khảo nhưng bỏ fallback Otsu âm thầm và không thay
mask rỗng bằng toàn ảnh: lỗi được ghi CSV, mask rỗng được lưu và gắn cờ để duyệt.
Giá trị mask PNG là 0 (nền) hoặc 255 (tiền cảnh); ảnh phủ tô **đỏ phần nền bị loại**.

## Các tệp đầu ra

Tất cả kết quả mặc định nằm trong `outputs/segmentation/grabcut/`:

| Tệp/thư mục | Nội dung |
|---|---|
| `masks/<tên gốc gồm đuôi>.png` | Mask PNG, ví dụ `Equus_asinus_0587.jpg.png`; giữ đầy đủ tên nguồn tránh trùng stem. |
| `overlays/<tên gốc gồm đuôi>.png` | Ảnh phủ PNG cùng kích thước mask. |
| `manifest.csv` | Một dòng mỗi ảnh được chọn, gồm đường dẫn, kích thước nguồn/xử lý, pixel mask, tỉ lệ, trạng thái duyệt, kết luận duyệt, cờ và SHA-256. |
| `quicklooks/batch_001.jpg`, ... | Mỗi bảng tối đa 8 ảnh, mỗi dòng là nguồn / mask / ảnh phủ. Ảnh xem nhanh giữ tỉ lệ trong ô 288 × 192. |
| `review_priority.csv` | Các ảnh lỗi hoặc có cờ, kèm tên bảng xem nhanh để ưu tiên duyệt. |
| `errors.csv` | Nhật ký lỗi tích lũy: thời điểm UTC, tên ảnh, giai đoạn, thông báo. Không có lỗi thì chỉ có dòng tiêu đề. |
| `run_config.json` | Cấu hình, phiên bản thư viện và SHA-256 script; dùng kiểm tra khi resume. |
| `summary.json` | Tổng thành công/thất bại/chờ, số dùng lại, số gắn cờ, kích thước, thời gian lần chạy gần nhất. |
| `full_processing_summary.json` | Bản tổng kết giữ lại của lần xử lý toàn bộ, trước lần kiểm tra resume và bổ sung ghi chú thị giác. |
| `visual_review_notes.csv` | Ghi chú nghi vấn từ quan sát trực tiếp, kèm tên bảng xem nhanh; chưa phê duyệt mask. |
| `full_run.log` | Thanh tiến độ và thống kê lần chạy toàn bộ thực tế. |
| `verification.json` | Kết quả kiểm tra lại đầu ra và đối chiếu ảnh nguồn. |
| `resume_verification.json` | Kiểm tra thực tế việc dùng lại toàn bộ kết quả và giữ nguyên manifest, mask/ảnh phủ. |

## Duyệt và phân loại ảnh phủ

```sh
.venv/bin/python tools/segmentation/review_overlays.py
# Xem lại cả ảnh đã được phân loại:
.venv/bin/python tools/segmentation/review_overlays.py --all
```

Bấm **A** chuyển ảnh đang xem vào `overlays/accepted/`, **S** vào
`overlays/needs_revision/`, **D** vào `overlays/redo/`. Mũi tên trái/phải chuyển
ảnh; **U** hoàn tác thao tác gần nhất trong phiên, **Esc** thoát. Mặc định tool
chỉ duyệt ảnh nằm trực tiếp trong `overlays/`; `--all` còn cho phép xem lại và
đổi nhãn ảnh đã phân loại. Tool không ghi đè ảnh trùng tên.

Việc di chuyển ảnh không cập nhật `manifest.csv`. Chạy lệnh đồng bộ ở phần dưới
để cập nhật đường dẫn, `review_result` (`dat`, `can_sua`, `lam_lai`) và bảng xem nhanh. Sau khi phân loại, đồng bộ manifest trước khi resume một bộ chạy mới.
Resume giữ đường dẫn mask/overlay đã ghi và chỉ dùng lại khi SHA-256 khớp.
Bộ kết quả lịch sử vẫn bị từ chối vì cấu hình/mã khác, kể cả khi các ảnh còn nguyên.

## Chỉnh mask tương tác cho ảnh cần sửa

```sh
.venv/bin/python tools/segmentation/edit_masks.py
```

Tool mở lần lượt ảnh ở `outputs/segmentation/grabcut/overlays/needs_revision/` và tự ghép với ảnh
nguồn trong `data/cropped_images_576x384/` cùng mask trong `outputs/segmentation/grabcut/masks/`.
GrabCut dùng ảnh nguồn, không dùng ảnh phủ đã tô đỏ. Python cần Tkinter, NumPy,
Pillow và OpenCV. Cài đúng toàn bộ bộ phụ thuộc của `.venv` bằng:

```sh
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
```

Khung trái hiển thị ảnh gốc để tô hướng dẫn. Khung phải hiển thị ảnh phủ/kết quả.
Nếu ảnh phủ trong `cần sửa` đã khác mask cũ trong `masks/`, tool lấy mask khởi
đầu từ chính ảnh phủ hiện tại, nên khung phải khớp ảnh PNG đang xem trong VS Code.
Mask trong `masks/` chỉ đổi khi bấm **Lưu & chuyển đạt**.

1. Chọn **Giữ con vật (F)**, kéo chuột trái tô vài nét bên trong phần con vật
   cần giữ hoặc đang bị mất. Nét tô có màu xanh lá.
2. Chọn **Loại nền (B)** và tô vùng nền bị giữ nhầm. Nét tô có màu xanh dương.
   Điều chỉnh bán kính cọ để sửa chân, tai, đuôi; **E** tẩy nét hướng dẫn.
3. Bấm **Chạy GrabCut (G)**, xem kết quả bên phải bằng chế độ **Ảnh phủ**,
   **Con vật** hoặc **Mask**. Có thể tô thêm và chạy lại nhiều lần. **U** hoàn
   tác nét tô hoặc lần chạy; **Khôi phục ban đầu** trả về mask lúc mở ảnh.
4. Bấm **Lưu & chuyển đạt (S)** khi đã hài lòng. Tool lưu mask nhị phân mới
   vào `masks/`, tạo lại ảnh phủ trong `overlays/accepted/`, gỡ ảnh cũ khỏi `cần sửa/`
   và mở ảnh kế tiếp. Ảnh nguồn được giữ nguyên. Nút lưu chỉ bật sau khi đã
   chạy GrabCut với các nét tô hiện tại; từ chối ghi đè ảnh cùng tên trong `đạt`.

Dòng tương ứng trong `manifest.csv` được cập nhật `review_status=da_duyet`,
`review_result=dat`,
đường dẫn ảnh phủ mới, thông số mask và SHA-256. Thư mục `manual_edits/<lần lưu>/`
giữ mask/ảnh phủ trước khi sửa, `scribbles.png` và `record.json` chứa thông tin
trước/sau. Nếu lưu gặp lỗi, tool phục hồi các tệp đã thay đổi. Bảng quicklook,
báo cáo và script `verify_grabcut_results.py` là bản kiểm tra của lần tạo mask
ban đầu. Chạy lệnh đồng bộ bên dưới để cập nhật dữ liệu sau khi chỉnh tay.

Có thể chọn bộ dữ liệu khác bằng `--output-dir` và `--source-dir`.

## Đồng bộ sau khi chỉnh ảnh phủ thủ công

```sh
# Chỉ kiểm kê; chưa thay đổi dữ liệu.
.venv/bin/python tools/segmentation/sync_overlays.py --pixel-tolerance 1
# Cập nhật mask, manifest, toàn bộ quicklooks, review_priority và summary.
.venv/bin/python tools/segmentation/sync_overlays.py --apply --pixel-tolerance 1
# Kiểm tra lại cả mask, hash, thống kê và nội dung quicklook hiện tại.
.venv/bin/python tools/segmentation/sync_overlays.py --verify --pixel-tolerance 1
```

Khi người duyệt đã xác nhận thủ công toàn bộ ảnh còn `chua_duyet`, có thể cập nhật
trạng thái, bảng xem nhanh và thống kê bằng:

```sh
.venv/bin/python tools/segmentation/sync_overlays.py --apply --mark-pending-reviewed --pixel-tolerance 1
```

Tùy chọn này chỉ đổi các dòng `chua_duyet` thành `da_duyet`; các cờ cảnh báo
vẫn được giữ để theo dõi. Báo cáo đồng bộ ghi số trạng thái đã đổi.

Khi người duyệt xác nhận tất cả ảnh chưa có kết luận đều đạt, có thể ghi `dat`
cho riêng các ô `review_result` đang trống bằng:

```sh
.venv/bin/python tools/segmentation/sync_overlays.py --apply --mark-empty-results-passed --pixel-tolerance 1
```

Script lấy vùng giữ/loại từ ảnh phủ PNG bằng cách đối chiếu với ảnh nguồn và
công thức phủ đỏ; không chạy lại GrabCut, không sửa hoặc di chuyển ảnh phủ/ảnh
nguồn. Chỉ hỗ trợ kết quả giữ kích thước nguồn. Tìm ảnh trong `overlays/` cùng
các thư mục con và ngay thư mục đầu ra. Năm ảnh trước đây nằm trực tiếp trong
thư mục đầu ra đã được chuyển vào `overlays/` và cập nhật đường dẫn trong manifest. Ảnh trùng
tên, sai kích thước hoặc màu không nhận diện được khiến toàn bộ lần đồng bộ
dừng trước khi ghi. Giữ quyết định duyệt đã có trong manifest; ảnh ở thư mục
`accepted`, `needs_revision`, `redo` nhận kết luận `dat`, `can_sua`, `lam_lai` tương ứng.
Các ảnh có hồ sơ "Lưu & chuyển đạt" cũng nhận `dat`; các ảnh chỉ được đánh dấu
`da_duyet` mà chưa ghi kết luận để trống `review_result`. Không tự phê duyệt ảnh
chỉ vì đồng bộ thành công. Các cờ quan sát `visual_*` của mask đã đổi được gỡ;
các cờ diện tích/hình học được tính lại.
Nếu ảnh phủ hoặc mask đổi sau lần kết luận trước, kết luận cũ được xóa cho đến
khi có lần phân loại mới; hồ sơ "Lưu & chuyển đạt" chỉ được dùng khi mã SHA-256
của ảnh phủ vẫn khớp lần lưu đó.

Mặc định đối chiếu màu chính xác. `--pixel-tolerance 1` cho phép sai lệch tối đa
1 mức mỗi kênh khi chỉ một cách hiểu (ảnh gốc hoặc phủ đỏ) phù hợp; lần kiểm kê
hiện tại phát hiện 5 pixel như vậy ở `Equus_quagga_1056.jpg`. Thống kê sai lệch
nằm trong `overlay_sync_report.json`. Hash nguồn được ghi theo ảnh đang dùng
để đối chiếu, còn dữ liệu cũ được giữ trong bản sao lưu.

Trước khi ghi, script sao lưu tất cả tệp sẽ thay thế vào
`overlay_sync_backups/<thời điểm>_<mã>.zip`; nếu ghi lỗi sẽ hoàn tác các tệp đã
ghi. Không sửa ảnh bằng công cụ khác trong lúc đồng bộ. `verification.json`,
`resume_verification.json`, `full_processing_summary.json`
và `visual_review_notes.csv` vẫn là hồ sơ lịch sử của lần chạy ban đầu;
`overlay_sync_report.json` và lệnh `--verify` phản ánh dữ liệu hiện tại.

Đường dẫn mask/ảnh phủ/bảng xem nhanh trong CSV **tính từ thư mục đầu ra**.
`width,height` là kích thước xử lý và mask; `source_width,source_height` là kích thước
nguồn. `mask_ratio = mask_pixels / total_pixels` là thông số kiểm tra diện tích,
**không phải độ chính xác phân đoạn**. `status=success` chỉ có nghĩa tạo và lưu được
tệp; `review_status=chua_duyet` mới là trạng thái duyệt ban đầu.
`review_result` chỉ nhận `dat`, `can_sua`, `lam_lai`, hoặc trống nếu chưa có
kết luận được ghi lại. `review_status=da_duyet` không tự suy ra `review_result=dat`.

Cờ tự động gồm mask rỗng, diện tích <5% hoặc >85%, ít nhất 8 thành phần lớn,
mask gần lấp đầy hình chữ nhật bao, hoặc chạm nhiều vào biên chữ nhật khởi tạo.
Đây chỉ là heuristic ưu tiên xem; **không có cờ cũng không đồng nghĩa đạt yêu cầu**.
Cờ `visual_*` là nghi vấn từ việc xem trực tiếp: 8 ảnh mẫu, thêm 8 lạc đà ở
bảng 12 và ảnh chó `Canis_familiaris_0395.jpg` bị cờ diện tích nhỏ. Các ghi chú
chi tiết nằm trong `visual_review_notes.csv`. Chưa duyệt thị giác toàn bộ 812 ảnh.
Việc ghi nghi vấn này không phê duyệt mask; vẫn giữ `chua_duyet`.
Người duyệt có thể ghi kết luận vào `review_result` sau khi kiểm tra ảnh;
`review_status` ghi việc đã duyệt. Chỉ ghi `dat` sau khi đối chiếu ảnh nguồn,
đủ thân/bộ phận và nền.

Script chỉ đọc ảnh nguồn, không đổi tên/xóa/ghi đè nguồn; từ chối đầu ra trùng,
chứa hoặc nằm trong thư mục nguồn. Các mask thử nghiệm cũ 224 × 224, chức năng
so sánh cũ/mới và các bảng kết quả so sánh đã được gỡ. Các công cụ tạo, duyệt,
chỉnh mask và đồng bộ sử dụng kết quả trong `outputs/segmentation/grabcut/`.

## Kiểm tra chương trình

```sh
.venv/bin/python tools/validation/verify_grabcut_results.py
```

Script xác minh lịch sử có ghi `verification.json` và yêu cầu trạng thái lúc tạo mask (`chua_duyet`);
không dùng nó để ghi đè bằng chứng xác minh của bộ đã chỉnh/duyệt. Kết quả kiểm tra chỉ đọc
hiện tại nằm trong `docs/results_migration_audit/`. Script này dành cho lần chạy toàn bộ mặc định ở 576 × 384, đối chiếu ảnh nguồn
với `outputs/segmentation/grabcut/provenance/source_before.json` đã ghi trước lần chạy. Không có ground truth mask,
không tính IoU, độ chính xác phân đoạn hoặc độ chính xác truy hồi từ các tệp này.

## Kết quả thực tế ngày 16/10/2026

Đã chạy thử 8 ảnh mẫu ở kích thước 576 × 384, sau đó xử lý đủ **812/812
ảnh, 0 thất bại, 0 chờ**, gồm 8 kết quả dùng lại và 804 ảnh xử lý thêm. Có 812 mask
PNG, 812 ảnh phủ PNG cùng kích thước 576 × 384 và 102 bảng xem nhanh.

Sau khi gộp ghi chú quan sát, **22 ảnh được gắn cờ để ưu tiên xem**. Đây không phải
số mask sai được xác nhận hoặc ước lượng tỉ lệ lỗi của cả tập. Chỉ xem trực tiếp
17 ảnh trong lần sửa công cụ này (8 mẫu cũ, 8 lạc đà bổ sung và 1 ảnh chó bị cờ),
ghi nghi vấn cho 15 ảnh; chưa duyệt toàn tập. **Cả 812 vẫn là `chua_duyet`**.

Đã kiểm tra PNG nhị phân, kích thước, số pixel/tỉ lệ, SHA-256, từng pixel ảnh phủ
và khả năng mở 102 bảng. Đối chiếu với kiểm kê trước khi chạy cho thấy toàn bộ
816 tệp nguồn (gồm 812 ảnh) giữ nguyên tên, nội dung, kích thước tệp và mtime.
Chi tiết ở `outputs/segmentation/grabcut/verification.json`.

Lệnh đo tài nguyên `/usr/bin/time -l` bao ngoài lần chạy toàn bộ báo không được
phép đọc `sysctl kern.clockrate` trong sandbox sau khi chương trình đã hoàn tất;
dòng này trong `full_run.log` thuộc bộ đo tài nguyên. Tổng kết xử lý có 0 lỗi ảnh
và 0 lỗi bảng xem nhanh. Lần kiểm tra resume chạy trực tiếp bằng Python, không
dùng bộ đo này; kết quả được ghi riêng trong `resume_verification.json`.
Lần kiểm tra này trả mã 0, dùng lại đủ 812 ảnh, không xử lý lại ảnh nào, giữ nguyên
manifest và mtime của toàn bộ 1.624 mask/ảnh phủ; tạo lại đủ 102 bảng với cờ mới.
Bảy kiểm tra hồi quy về lỗi, ngắt/resume, sửa đầu ra hỏng, trạng thái duyệt,
giữ tỉ lệ và bảo vệ nguồn đã đạt tại thời điểm kiểm tra. Các file kiểm thử tự động
đã được gỡ khi dọn dự án.
