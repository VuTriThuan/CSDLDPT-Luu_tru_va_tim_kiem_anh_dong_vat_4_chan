# Chuyển kết quả và kiểm kê — 17/10/2026

Đã chuyển **3.248 tệp** theo phạm vi yêu cầu. Không chạy xử lý hàng loạt, chỉnh
mask hoặc đồng bộ ghi lên dữ liệu thật. Các phép xử lý/ghi và kiểm tra resume dùng
ảnh sinh tạm hoặc bản sao dữ liệu nhỏ trong thư mục tạm; kiểm tra bộ thật chỉ đọc
nội dung và metadata.

## Ánh xạ thực tế

| Vị trí trước bước này | Vị trí hiện tại |
|---|---|
| `reports/yeu_cau_2/grabcut_output/` | `outputs/segmentation/grabcut/` — toàn bộ 3.242 tệp, kể cả tệp ẩn và khóa |
| `reports/yeu_cau_2/kiem_ke.json` | `outputs/inventory/image_inventory.json` |
| `reports/yeu_cau_2/anh_da_xem.csv` | `outputs/inventory/viewed_images.csv` |
| `reports/yeu_cau_2/grabcut_so_do.csv` | `outputs/inventory/grabcut_sample_statistics.csv` |
| `reports/yeu_cau_2/grabcut_moi_truong.json` | `outputs/inventory/grabcut_sample_environment.json` |
| `reports/yeu_cau_2/grabcut_source_before.json` | `outputs/segmentation/grabcut/provenance/source_before.json` |
| `reports/yeu_cau_2/mask_moi_can_sua_truoc_khi_chay.json` | `outputs/segmentation/mask_regeneration_source_before.json` |

Danh sách từng tệp/thư mục, gồm cả các mục giữ nguyên:
[path_mapping.csv](results_migration_audit/path_mapping.csv),
[path_mapping.json](results_migration_audit/path_mapping.json).
Cấu hình `run_config.json` vẫn nằm trong bộ GrabCut mà nó mô tả. Hồ sơ môi trường
mẫu 224 × 224 ở cạnh bảng số liệu mẫu trong `outputs/inventory/`, không trộn với
cấu hình chạy GrabCut toàn bộ 576 × 384.

Không tìm thấy bộ mask tạo lại khác ngoài các bản sao lưu/khôi phục. Tài liệu lịch
sử mô tả 317 mask nhưng tệp kết quả không hiện diện từ mốc chuẩn bị. Vì vậy không
tạo bộ kết quả rỗng hoặc chép mask GrabCut sang để thay thế. Đích cho lần tạo mới
là `outputs/segmentation/mask_regeneration/`, hiện chưa tạo. Kiểm kê trước chạy
đặt cạnh đích dự kiến để không khiến chương trình coi đầu ra mới là đã có dữ liệu.

```text
outputs/
├── inventory/
│   ├── image_inventory.json
│   ├── viewed_images.csv
│   ├── grabcut_sample_statistics.csv
│   └── grabcut_sample_environment.json
├── segmentation/
│   ├── mask_regeneration_source_before.json
│   └── grabcut/
│       ├── .run.lock, .DS_Store
│       ├── manifest.csv, run_config.json
│       ├── masks/                 # giữ nguyên 812 tên
│       ├── overlays/              # giữ nguyên 812 PNG phẳng
│       ├── quicklooks/            # giữ nguyên 102 tên
│       ├── manual_edits/          # giữ nguyên 374 ID, mỗi ID bốn tệp
│       ├── overlay_sync_backups/  # giữ nguyên bốn ZIP
│       ├── provenance/
│       │   ├── source_before.json
│       │   └── path_aliases.json  # hồ sơ bổ sung, không thay config lịch sử
│       └── <toàn bộ JSON, CSV và log khác trước đây>
└── backups/                       # giữ các bản sao lưu của từng giai đoạn
```

## Phân loại overlay và các đường dẫn lịch sử

Mã duyệt, chỉnh, tạo lại mask, đồng bộ và xác minh dùng các thư mục
`accepted`, `needs_revision`, `redo` thay cho `đạt`, `cần sửa`, `làm lại`.
Các giá trị giao thức `review_status`, `review_result` như `da_duyet`, `dat`,
`can_sua`, `lam_lai` giữ nguyên ý nghĩa và cách lưu.

Ở bộ thật không có thư mục phân loại; 812 `overlay_path` đều có dạng
`overlays/<tên ảnh gốc>.png`. Chuyển nguyên cây giữ các đường dẫn tương đối đúng,
nên **0 hàng manifest cần chuyển đổi**, không ghi lại CSV. Không tự đưa 812 ảnh
vào `accepted` từ giá trị `dat`. Thư mục phân loại được tạo khi công cụ duyệt cần
đến; luồng phân loại/hoàn tác/đồng bộ cả ba loại đã kiểm tra trên ảnh tạm.

Không sửa bất kỳ `manual_edits/*/record.json`, PNG lịch sử, ZIP/thành viên ZIP,
log, tổng kết hoặc cấu hình cũ. `sync_overlays.accepted_manual_edits()` nhận cả
`overlays/đạt/…` trong hồ sơ cũ và `overlays/accepted/…` trong hồ sơ mới; chỉ dùng
quyết định cũ khi SHA-256 overlay khớp giá trị đã ghi. Các ảnh trước chỉnh sửa vẫn
đọc tại `manual_edits/<ID>/mask_before.png`, `overlay_before.png`, `scribbles.png`.
Đường dẫn trước/sau trong `record.json` mô tả thời điểm lưu, không khẳng định tệp
ở đường dẫn trước chỉnh sửa vẫn còn trong cây hiện tại.

`tools/project_paths.py` và [path_aliases.json](../outputs/segmentation/grabcut/provenance/path_aliases.json)
ghi ánh xạ đọc từ vị trí cũ sang vị trí hiện tại. Bộ xác minh mask tạo lại dùng
`resolve_project_reference()` để tìm tệp qua các ánh xạ giới hạn trong dự án;
không đổi đường dẫn tuyệt đối thuộc dự án khác, không sửa hash đã lưu. README,
hướng dẫn và liên kết trong hai báo cáo đã cập nhật theo vị trí mới.

## Toàn vẹn và những giới hạn lịch sử

[verification.json](results_migration_audit/verification.json) và
[asset_sha256.csv](results_migration_audit/asset_sha256.csv) đối chiếu với cả bản
sao trước bước này và mốc SHA-256 ở bước chuẩn bị:

| Nhóm | Kết quả |
|---|---|
| Ảnh nguồn / ảnh cắt / ảnh loại | 1.297 / 812 / 485, tổng 2.594 hash khớp bước 1 |
| Mask / overlay | 812 / 812, hash và tên giữ nguyên, PNG 576 × 384 đọc được |
| Quicklook | 102, hash giữ nguyên, đọc được |
| Lịch sử chỉnh mask | 1.496 tệp trong 374 phiên, hash và cấu trúc giữ nguyên |
| ZIP đồng bộ | Bốn ZIP giữ nguyên; đọc và đối chiếu đủ 508 thành viên |
| Manifest | 812 hàng, 24 cột, giữ nguyên bytes; 2.436 đối chiếu hash nguồn/mask/overlay khớp |
| Tệp ở cây `reports/` trước bước này | 3.257/3.257 giữ nguyên bytes, mode và mtime tệp; 3.248 đã chuyển, chín giữ vị trí |

SHA-256 manifest:
`efa7ab0214002502425acb50de383a7d0e61f99cb13f10964b2f607dfab06b67`.
SHA-256 cấu hình chạy cũ:
`5f7726ac9952a7cf7fbb3d7288d0fc7ced7e9765ad50bb9cfc440faa3ac47f66`.

Các kiểm kê **trước các lần xử lý lịch sử** không phải mốc chuẩn bị chuyển dự án:

- `provenance/source_before.json`: hai mục khác cây hiện tại — ảnh
  `Equus_quagga_1056.jpg` và `_cat_tu_dong.json`.
- `mask_regeneration_source_before.json`: 1.239/3.931 mục khác cây hiện tại sau
  khi tra vị trí mới. Đây là bằng chứng các thời điểm cũ, không phải 1.239 tệp bị
  thay đổi bởi bước chuyển này: toàn bộ tệp kết quả hiện có vẫn khớp bước 1.
- Sáu bảng `contact_*.jpg` mà 84 dòng `viewed_images.csv` nhắc tới đã được xóa
  từ trước mốc chuẩn bị, như báo cáo phân tích đã ghi. Không tạo lại bảng để giả
  định chúng là hiện vật lịch sử.

Chi tiết sai khác: [historical_inventory_checks.json](results_migration_audit/historical_inventory_checks.json).
Không sửa các kiểm kê để làm cho chúng báo đạt. `verify_grabcut_results.py` còn
yêu cầu trạng thái lúc tạo mask (`chua_duyet`), trong khi manifest hiện hành có
812 `da_duyet`/`dat`; công cụ này ghi `verification.json` khi thành công. Không
chạy nó để ghi đè bộ thật đã chỉnh sửa. Kiểm tra chỉ đọc của bước chuyển nằm
riêng trong phụ lục này. Chênh lệch 189 trạng thái cắt ảnh đã ghi ở bước dữ liệu
cũng được giữ nguyên.

## Resume và cách bắt đầu một bộ mới

Mã vẫn so sánh cấu hình đầy đủ, SHA-256 script và các artifact. Sửa lỗi resume đặt
lại đường dẫn mask/overlay trước khi kiểm tra hash: bộ chạy mới giữ đường dẫn đã
ghi trong manifest, kể cả khi overlay đã phân loại và đồng bộ. Không nới điều
kiện hash, không thay thuật toán tạo mask. Bảng quicklook vẫn tính đường dẫn theo
đợt; kết quả thiếu/hỏng vẫn phải xử lý lại theo quy tắc cũ.

Bản sao metadata thật của bộ lịch sử đã bị từ chối đúng với mã trả về **2**:
`Resume configuration/code differs. Choose a new --output-dir`.
Với `.venv/bin/python`, cấu hình khác ở đường dẫn nguồn, SHA-256 script, OpenCV
(4.12.0 → 4.11.0), Pillow (12.2.0 → 12.3.0).
[resume_compatibility.json](results_migration_audit/resume_compatibility.json) ghi giá trị cụ thể.
Giữ nguyên hash lịch sử; không dùng alias đọc đường dẫn để bỏ kiểm tra cấu hình.

Các lệnh sau là hướng dẫn cho lần xử lý riêng, **chưa chạy trên bộ ảnh thật**:

```sh
# Từ root; chọn tên chưa tồn tại nếu ví dụ đã được dùng.
.venv/bin/python tools/segmentation/run_grabcut.py --limit 8 --output-dir outputs/segmentation/grabcut_run_20261017_01
# Chỉ resume chính bộ mới, khi mã/thư viện/nguồn/tham số không đổi.
.venv/bin/python tools/segmentation/run_grabcut.py --all --resume --output-dir outputs/segmentation/grabcut_run_20261017_01
```

Nếu muốn tái hiện lần chạy lịch sử, khôi phục snapshot chuẩn bị vào cây riêng
và dùng mã, nguồn, đường dẫn và phiên bản thư viện đúng thời điểm đó; các môi
trường Python có thể cần dựng lại. Không ép resume lên bộ lịch sử bằng mã mới.

## Sao lưu và khôi phục

Trước khi chuyển, còn 38.473.953.280 byte trống; ngưỡng dành cho snapshot, khôi
phục và dự phòng là 2.257.936.698 byte. Archive mới **583.116.800 byte**:

`outputs/backups/pre_results_migration_20261017_104419/before_results_migration.tar`

SHA-256: `580a45d1daaa1ae603e8a6098f3802ad963c43d9410dc2097681c23ef17ae2bf`.
Archive chứa nguyên cây `reports/`, mã, tests, tài liệu và README trước bước này,
gồm tệp ẩn, khóa, cấu hình, manifest và mọi lịch sử. Ảnh dữ liệu và hai môi trường
không đổi trong bước này; bản sao đầy đủ ban đầu vẫn ở
`outputs/backups/pre_migration_20261017_100229/project_snapshot.tar`.

Đã đối chiếu mọi thành viên của snapshot mới, khôi phục thử 12 tệp trước khi
chuyển, rồi khôi phục và kiểm tra toàn bộ **3.779 mục / 3.380 tệp** vào
`outputs/backups/pre_results_migration_20261017_104419/restore_check/`.
Bytes, mode, mtime nanosecond và mọi extended attribute gốc khớp. macOS thêm
`com.apple.provenance` vào ba mục mới tạo; ghi rõ riêng trong
[restore_verification.json](results_migration_audit/restore_verification.json), không coi chúng là thuộc tính gốc.
Xem [preflight.json](results_migration_audit/preflight.json) và
[cây trước bước này](results_migration_audit/tree_before.txt).

Quy trình hoàn tác cụ thể trong phần cập nhật mới nhất của
[migration_plan.md](migration_plan.md). Giữ bản sao lưu và thư mục giữ lại khi
hoàn tác, không xóa chúng trong bước chuyển này.

## Kiểm thử và các mục chưa chuyển

**37 kiểm thử đạt**: 23 kiểm thử công cụ ảnh, 14 kiểm thử chuyển mã/kết quả.
[validation_tests.log](results_migration_audit/validation_tests.log),
[image_tests.log](results_migration_audit/image_tests.log).
Bao gồm 22 lượt CLI help trực tiếp/module, hồi quy AST thuật toán, tạo
GrabCut và U²-Net trên một ảnh sinh tạm, resume bộ mới, giữ đường dẫn phân loại,
phát hiện hash nguồn/mask/overlay sai, từ chối đường dẫn không an toàn, ba loại
overlay, hoàn tác, lịch sử cũ/mới, đồng bộ chỉ trên bản tạm. Nhóm kiểm thử ảnh còn
kiểm tra cắt/đổi tên/duyệt/resume trên bản sao nhỏ của ảnh thật, gồm một lần cắt
U²-Net bằng model đã có. Không tải model.
Ba kiểm tra cuối về hash/đường dẫn symlink, hồi quy thuật toán và resume đường
dẫn phân loại cũng đạt sau khi bổ sung chặn đường dẫn thoát cây kết quả;
xem [final_resume_checks.log](results_migration_audit/final_resume_checks.log).
Đã kiểm tra 249 liên kết nội bộ, 53 tham chiếu lệnh gọi mã và giải mã 40 ảnh
liên kết duy nhất, không có lỗi. Nội dung phân tích/số liệu hai báo cáo và phần
kết quả lịch sử trong hai hướng dẫn được đối chiếu với snapshot trước bước này;
chỉ đổi đường dẫn. Seal của ba phụ lục giai đoạn trước vẫn khớp. Xem
[content_preservation.json](results_migration_audit/content_preservation.json) và
[link_verification.json](results_migration_audit/link_verification.json).

`reports/` chỉ còn hai `.DS_Store` và bảy `.pyc` trong
`reports/yeu_cau_2/__pycache__/`; giữ vị trí vì không thuộc phạm vi chuyển kết quả
nghiệp vụ. `data/`, hai môi trường Python, requirements và các bản sao lưu cũ giữ
nguyên. Bộ mask tạo lại vắng mặt như đã nêu. Đã dừng sau bước kết quả/kiểm kê.
