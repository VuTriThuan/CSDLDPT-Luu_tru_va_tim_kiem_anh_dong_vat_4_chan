# Xác minh và bàn giao sau sắp xếp — 17/10/2026

**Đạt các kiểm tra kỹ thuật trong phạm vi dưới đây.** 38 kiểm thử hiện có đạt;
luồng một ảnh thử đi qua cắt, đổi tên, duyệt, tạo mask, chỉnh/lưu, đồng bộ và
resume. Ba cửa sổ Tkinter đã được kiểm tra trên bản sao thử riêng. Không chạy
batch ghi lên dữ liệu thật, không sửa hash/cấu hình lịch sử và không xóa thư mục
cũ còn hồ sơ cần giữ.

Phụ lục kiểm tra ở [migration_verification_audit/](migration_verification_audit/).
Các lệnh được chạy bằng Python **3.10.11 64-bit trên macOS 13.7.6 Intel**.

## Cây bàn giao

```text
BTL/
├── .git/                          # lịch sử/index hiện hành
├── .gitignore, .python-version
├── .venv/                         # môi trường chung
├── .venv-image-tools/              # nhóm cắt/duyệt ảnh và U2Net
├── README.md
├── requirements.txt
├── requirements_image_tools.txt
├── docs/
│   ├── migration_plan.md
│   ├── migration_verification.md
│   ├── python_environments.md
│   ├── reports/
│   │   ├── animal_comparison.md
│   │   └── search_feature_design.md
│   ├── guides/
│   │   ├── image_tools.md
│   │   ├── grabcut.md
│   │   └── mask_regeneration.md
│   └── <các báo cáo giai đoạn và *_audit/>
├── data/
│   ├── source_images/             # 1.297 ảnh
│   ├── cropped_images_576x384/     # 812 ảnh + JSON/CSV/khóa hiện có
│   └── rejected_crops/            # 485 ảnh
├── tools/
│   ├── project_paths.py
│   ├── image_processing/          # auto_crop, rename_images, review_images, tool_common
│   ├── segmentation/              # run_grabcut, edit_masks, review_overlays,
│   │                              # sync_overlays, regenerate_masks
│   └── validation/                # audit_images, verify_grabcut_results,
│                                  # verify_regenerated_masks
├── tests/
│   ├── image_processing/
│   └── validation/
├── outputs/
│   ├── inventory/                 # bốn JSON/CSV đã chuyển
│   ├── segmentation/
│   │   ├── mask_regeneration_source_before.json
│   │   └── grabcut/
│   │       ├── manifest.csv, run_config.json, .run.lock
│   │       ├── masks/             # 812 PNG
│   │       ├── overlays/          # 812 PNG phẳng, giữ nguyên tên
│   │       ├── quicklooks/        # 102 JPG
│   │       ├── manual_edits/      # 374 phiên × bốn tệp
│   │       ├── overlay_sync_backups/ # bốn ZIP
│   │       ├── provenance/        # source_before.json, path_aliases.json
│   │       └── <các CSV, JSON, log và metadata gốc>
│   ├── validation/migration_20261017_111334/ # dữ liệu thử riêng của bước này
│   └── backups/                   # snapshot, wheel và bản khôi phục thử
├── bo_tool_anh_576x384/            # giữ tám tệp lịch sử; không còn venv
└── reports/                       # giữ chín tệp metadata/bytecode lịch sử
```

Tệp `__init__.py`, metadata ẩn và các tên trạng thái hiện hành được giữ theo quy
ước kỹ thuật. Danh sách đầy đủ cây trên ổ đĩa sẽ ở
[final_tree.txt](migration_verification_audit/final_tree.txt); bảng đối chiếu từng
mục từ bước 1 ở [baseline_accounting.json](migration_verification_audit/baseline_accounting.json).

## Kiểm thử và luồng dữ liệu riêng

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-image-tools/bin/python -B -m unittest discover -s tests/image_processing -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests/validation -v
```

Kết quả: **24/24 công cụ ảnh, 14/14 validation**, không có test bị bỏ qua.
[image_tests.log](migration_verification_audit/image_tests.log),
[validation_tests.log](migration_verification_audit/validation_tests.log).
11 công cụ import được; 22 lệnh trợ giúp trực tiếp/module và hai lượt tự chuyển
từ Python chung sang môi trường ảnh đạt. Cả hai môi trường `pip check` đạt và
đúng các phiên bản đã ghim. Xem [smoke_checks.json](migration_verification_audit/smoke_checks.json)
và [environment_verification.json](migration_verification_audit/environment_verification.json).

Dữ liệu thử nằm riêng tại
`outputs/validation/migration_20261017_111334/`, lấy một bản sao của
`Ailuropoda_melanoleuca_1211.jpg`. Chỉ tên ảnh trên bản sao thử được đổi thành
`Ailuropoda_melanoleuca_0001.jpg`. Model cục bộ được kiểm tra SHA-256/MD5, chặn
download trong phép thử cắt ảnh.

| Luồng | Kết quả quan sát |
|---|---|
| Cắt ảnh | U2Net thực sự suy luận, tạo JPG 576 × 384. SHA-256 ảnh cắt thử trùng ảnh cắt 1211 của bước 1; chỉ chứng minh cho một mẫu này. |
| Cắt tiếp | Chạy lại bỏ qua ảnh đã xử lý, giữ hash/mtime ảnh. Giữ quyết định lật và loại của công cụ duyệt. |
| Đổi tên | Preview không ghi; apply đồng bộ ảnh nguồn, ảnh cắt và state, giữ nguyên tập hash ảnh. CLI được gọi với các hằng đường dẫn chuyển sang fixture vì công cụ không có tham số chọn bộ dữ liệu. |
| Duyệt ảnh | Lật, chuyển vào `rejected_crops`, hoàn tác cả hai; nội dung ảnh trở lại nguyên bytes. |
| GrabCut | Tạo mask, overlay, quicklook, manifest; resume bộ mới dùng lại một ảnh. Mask phẳng bị làm hỏng trên một bản sao khác được phát hiện và tạo lại. |
| Phân loại overlay | Chuyển `needs_revision`, hoàn tác, phân loại lại; đồng bộ manifest tìm được đường dẫn mới. |
| Mở/chỉnh mask | Nạp từ repository, tô giữ/loại, chạy GrabCut thật; **708 pixel đổi** ở phép thử API. Hoàn tác kết quả và áp dụng lại thành công. |
| Lưu và khôi phục lỗi | Tiêm lỗi ghi manifest trên fixture: mask/overlay/manifest phục hồi đúng bytes; giữ record `rolled_back`. Lưu lại thành công tạo record `saved` và đủ ba PNG lịch sử. |
| Đồng bộ | `--apply` tương đương trên API cập nhật dẫn xuất của bản thử; lượt verify chỉ đọc giữ nguyên toàn bộ bytes và xác minh quicklook. |
| Resume sau chỉnh | Dùng lại mask/overlay đã chỉnh tại `overlays/accepted/`, giữ quyết định `dat` và lịch sử, không xử lý lại. |
| Tạo lại mask | U2Net tạo bộ riêng `regenerated_masks/`; resume dùng lại một ảnh. Bộ cũ và nguồn của fixture không đổi. |

Chi tiết: [image_workflow.json](migration_verification_audit/image_workflow.json),
[mask_workflow.json](migration_verification_audit/mask_workflow.json),
[regeneration_workflow.json](migration_verification_audit/regeneration_workflow.json).

GUI được mở bằng interpreter đúng nhóm: editor và overlay dùng `.venv/`, duyệt
ảnh dùng `.venv-image-tools/`. Đã render canvas, tạo nét tô bằng sự kiện chuột
mô phỏng, chờ GrabCut bất đồng bộ, bấm nút lưu, kiểm tra mask/overlay/record;
editor GUI đổi thêm **518 pixel trên bản sao GUI**. Cửa sổ duyệt ảnh thực hiện
lật/xóa/hoàn tác; cửa sổ overlay thực hiện phân loại/hoàn tác.
[gui_verification.json](migration_verification_audit/gui_verification.json) và
[gui_check.log](migration_verification_audit/gui_check.log).
Probe đầu gọi thao tác duyệt quá nhanh nên bị ngưỡng chống lặp 0,35 giây bỏ qua;
đã sửa khoảng chờ của probe lên 0,45 giây và chạy lại đạt. Không sửa công cụ để
bỏ ngưỡng; log đầu giữ tại [gui_check_initial.log](migration_verification_audit/gui_check_initial.log).

## Danh sách và SHA-256 so với bước 1

Đã phân loại **đủ 26.551 mục / 24.264 tệp thông thường** của kiểm kê ban đầu:

| Trạng thái | Số mục |
|---|---:|
| Giữ nguyên tại vị trí cũ, cùng SHA-256 | 7.475 |
| Chuyển vị trí, giữ nguyên SHA-256 | 5.845 |
| Đổi nội dung có hồ sơ chuyển đổi: mã, tài liệu, README, state | 20 |
| Môi trường ảnh cũ đã gỡ, có trong backup xác minh | 8.175 |
| Metadata Git có thể thay đổi khi làm việc | 3.822 |
| Thư mục còn tồn tại ở vị trí đích | 1.211 |
| Symlink đang dùng giữ nguyên đích | 3 |
| **Mất/thay đổi chưa giải thích** | **0** |

Git được tách khỏi ràng buộc hash tĩnh vì index/refs/lịch sử làm việc đã thay đổi;
`git fsck --no-dangling --no-progress` trả **0**, không có lỗi.
[git_fsck.log](migration_verification_audit/git_fsck.log).
Các tệp Git ở mốc 1 vẫn có trong snapshot đầy đủ. Không phục hồi các mục đã bị
xóa trước khi bắt đầu sắp xếp.

| Nhóm dữ liệu và kết quả | Đối chiếu |
|---|---|
| Ảnh nguồn / ảnh cắt / ảnh loại | 1.297 / 812 / 485; tất cả tên và SHA-256 khớp bước 1 |
| Mask / overlay | 812 / 812; tên và SHA-256 khớp |
| Quicklook | 102; tên/hash khớp, đường dẫn tồn tại, chỉ số batch và kích thước bảng khớp nhóm hàng manifest |
| Manifest | 812 hàng, 24 cột; cùng bytes; 2.436 đối chiếu hash nguồn/mask/overlay khớp |
| Lịch sử chỉnh sửa | 374 phiên, 1.496 tệp; cùng ID/cấu trúc/hash; PNG và JSON đọc được |
| ZIP lịch sử | Bốn ZIP cùng hash; đọc và băm đủ 508 thành viên |
| State cắt | 1.297 bản ghi ảnh giữ nguyên; chỉ hai trường `source`, `source_relative` đã đổi đúng như bước dữ liệu |

[asset_sha256.csv](migration_verification_audit/asset_sha256.csv) ghi tên cũ,
tên hiện tại và cả hai hash; [baseline_verification.json](migration_verification_audit/baseline_verification.json)
ghi tổng hợp. SHA-256 manifest vẫn là:

`efa7ab0214002502425acb50de383a7d0e61f99cb13f10964b2f607dfab06b67`.

Kiểm tra sâu đủ 812 cặp: mask nhị phân đúng kích thước, số pixel/tỉ lệ khớp
manifest. Overlay khớp nguồn/mask với dung sai tối đa một mức mỗi kênh; chỉ có
năm pixel không khớp tuyệt đối ở `Equus_quagga_1056.jpg`, đúng hiện trạng đã ghi
trước sắp xếp. Đã đọc thêm 1.224 ảnh quicklook/lịch sử.
[artifact_content_verification.json](migration_verification_audit/artifact_content_verification.json).

Đối chiếu trước/sau riêng bước xác minh: **5.848 tệp dữ liệu, kết quả, state**
giữ nguyên cả nội dung và mtime; không xuất hiện tệp lạ trong các bộ thật.
Môi trường chung khớp bước 1; 8.182 mục của môi trường ảnh tạo lại khớp kiểm kê
sau bước môi trường. Năm seal audit trước vẫn đúng.

## Manifest và lịch sử: các khác biệt cần biết

Manifest hiện hành tìm đúng toàn bộ mask, overlay, 102 quicklook; không có PNG
mask/overlay hoặc JPG quicklook không được manifest nhắc tới. Tên ảnh trong cả
374 hồ sơ chỉnh sửa đều ghép được với manifest. Hash mask/overlay hiện tại khớp
`manifest_after` của đủ **374/374 hồ sơ**; `mask_before.png` cũng khớp hash trong
`manifest_before` của 374/374 hồ sơ.

Có **30/374** `overlay_before.png` khác `manifest_before.overlay_sha256`.
Cả ảnh trước chỉnh lẫn record đều nguyên bytes so bước 1. Đây là sai khác của
hồ sơ lịch sử, phù hợp với việc công cụ hỗ trợ mở overlay đã chỉnh ngoài trước
khi đồng bộ, nhưng không xác nhận lại được thao tác từng ca. Giữ nguyên cả hai
giá trị; không sửa hash để làm khớp. Xem
[historical_overlay_hash_differences.json](migration_verification_audit/historical_overlay_hash_differences.json)
và [history_relationships.json](migration_verification_audit/history_relationships.json).
Đường dẫn `overlay_before`/`overlay_after` trong record mô tả thời điểm lưu;
không yêu cầu các vị trí cũ vẫn hiện diện trong bộ hiện hành.

Các khác biệt đã có và tiếp tục giữ nguyên:

- State ghi 665 `saved`, 632 `deleted`, nhưng có 189 bản ghi lệch vị trí ảnh
  thực tế (168/21); không hòa giải hoặc cắt lại ảnh thật trong bước này.
- Kiểm kê trước chạy GrabCut có hai mục khác hiện tại; kiểm kê trước tạo lại
  mask có 1.239/3.931 mục khác. Chúng là mốc trước các xử lý lịch sử, không phải
  kiểm kê bước 1. Chi tiết ở [historical_inventory_checks.json](results_migration_audit/historical_inventory_checks.json).
- Bộ 317 mask được hướng dẫn lịch sử mô tả vẫn không hiện diện. Bộ một ảnh
  được tạo để thử nằm trong `outputs/validation/`, không thay thế bộ lịch sử.
- Sáu bảng `contact_*.jpg` trong `viewed_images.csv` và CSV thống kê loài từng
  được nhắc trong báo cáo đã vắng mặt trước bước 1; không tạo hiện vật giả.

## Đường dẫn cũ và thư mục giữ lại

[legacy_path_matches.json](migration_verification_audit/legacy_path_matches.json)
liệt kê từng dòng còn tham chiếu cũ, có phân loại. Trong mã chạy, các tham chiếu
cũ nằm ở alias có phạm vi trong `tools/project_paths.py` và bộ đọc record chỉnh
mask tiếng Việt của `sync_overlays.py`. Trong tests, chúng là dữ liệu tương
thích hoặc ánh xạ vào snapshot. Hướng dẫn hiện hành dùng mã/data/output/venv mới;
không có lệnh hiện hành trỏ vào vị trí đã bỏ.

Các đường dẫn cũ còn trong JSON/log/config/CSV và record của bộ thật là bằng
chứng lịch sử, không bị viết lại. Tài liệu giai đoạn và quy trình khôi phục vẫn
nhắc tên cũ theo thời điểm. Nội dung `.git`, venv của thư viện bên thứ ba, binary,
backup và audit đã niêm phong được kiểm tra bằng kiểm kê/hash, tách khỏi quét
đường dẫn của mã dự án. [reference_verification.json](migration_verification_audit/reference_verification.json)
ghi phạm vi và kết quả phân loại; kiểm tra liên kết tài liệu/mã/ảnh nằm ở
[link_verification.json](migration_verification_audit/link_verification.json).

**Không xóa thư mục cũ nào trong bước này:** `bo_tool_anh_576x384/` còn tám tệp,
`reports/` còn chín tệp; tổng 201.403 byte. Chúng chứa requirements, metadata và
bytecode lịch sử, kể cả dấu vết của kiểm thử không còn source. Không có venv
trong chúng, nhưng cũng không có thư mục rỗng đủ điều kiện xóa. Từng tệp đều
khớp bước 1 và có trong backup. Danh mục/quyết định giữ ở
[legacy_directories.json](migration_verification_audit/legacy_directories.json).

## Lệnh chạy chính

Chạy từ root bằng môi trường đúng. Các lệnh `--help` chỉ đọc đã được kiểm tra
trong README. Các lệnh làm việc dưới đây là bàn giao, chưa chạy trên bộ thật
trong bước xác minh:

```sh
# Cắt tiếp ảnh chưa xử lý, giữ tiến độ cũ; không thêm --force.
.venv-image-tools/bin/python tools/image_processing/auto_crop.py
# Xem trước đổi tên, chưa dùng --apply.
.venv/bin/python tools/image_processing/rename_images.py
.venv-image-tools/bin/python tools/image_processing/review_images.py

# Bộ GrabCut mới; chọn tên chưa tồn tại nếu ví dụ này đã được dùng.
.venv/bin/python tools/segmentation/run_grabcut.py --limit 8 --output-dir outputs/segmentation/grabcut_run_new
.venv/bin/python tools/segmentation/run_grabcut.py --all --resume --output-dir outputs/segmentation/grabcut_run_new

.venv/bin/python tools/segmentation/review_overlays.py
.venv/bin/python tools/segmentation/sync_overlays.py --pixel-tolerance 1
.venv/bin/python tools/segmentation/edit_masks.py
.venv-image-tools/bin/python tools/segmentation/regenerate_masks.py --help
```

Hiện 812 overlay thật còn ở thư mục phẳng. Phân loại vào `needs_revision/` rồi
đồng bộ manifest trước khi mở hàng đợi chỉnh mask hoặc tạo lại mask. Lệnh đồng
bộ trên là audit mặc định; ghi dẫn xuất cần `--apply` theo hướng dẫn GrabCut.
`verify_grabcut_results.py` và `verify_regenerated_masks.py` là verifier theo mốc
tạo mask, có ghi `verification.json` khi thành công; không dùng chúng để ghi đè
bằng chứng của bộ lịch sử đã chỉnh. Bộ kiểm tra chỉ đọc của lần bàn giao là
`docs/migration_verification_audit/check_baseline.py`, `check_artifacts.py`.

Resume của bộ mới được kiểm chứng. Resume bộ GrabCut lịch sử bị từ chối đúng
với mã **2** vì đường dẫn nguồn/hash mã/phiên bản khác cấu hình đã lưu. Không
nới kiểm tra hoặc sửa config cũ. Muốn xử lý bằng mã hiện tại, chọn đầu ra mới
như trên. Resume của crop và U2Net đã kiểm tra trên dữ liệu thử riêng.

## Sao lưu và khôi phục

Đã băm lại **bảy archive**, đọc/khôi phục thử **13 tệp** từ snapshot đầy đủ,
kiểm tra ba bản sao phụ thuộc ngoài dự án và 14 wheel. Năm seal audit trước
khớp. [backup_verification.json](migration_verification_audit/backup_verification.json)
ghi vị trí, dung lượng, SHA-256 và các mẫu đã phục hồi.

| Bản sao | Vị trí và phạm vi |
|---|---|
| Đầy đủ trước bước 1 | `outputs/backups/pre_migration_20261017_100229/project_snapshot.tar` — ảnh, kết quả, history, hai venv cũ, tệp ẩn và Git |
| Trước đổi tên data | `outputs/backups/pre_data_migration_20261017_103325/before_data_migration.tar` — code/docs/state, đi cùng snapshot đầy đủ cho ảnh |
| Trước chuyển kết quả | `outputs/backups/pre_results_migration_20261017_104419/before_results_migration.tar` — nguyên kết quả/history và code/docs |
| Trước tạo lại môi trường | `outputs/backups/pre_environment_migration_20261017_105624/before_environment_migration.tar` — hai venv cũ và code/docs; wheel/lock nằm cạnh archive |
| Trước xác minh | `outputs/backups/pre_verification_20261017_111334/project_controls_before.tar` — code/tests/docs/config và các tệp thư mục cũ; không phải bản sao ảnh/venv |
| Trước chuyển source/docs | `docs/source_migration_audit/source_before.tar`, `docs/documentation_migration_audit/documents_before.tar` |

Snapshot đầy đủ có SHA-256:
`2917b8e027a090fdb7564ac71336e4a82e7ce6e1dc9e038658a2c468e37bdbf7`.
Để khôi phục đúng mốc ban đầu, dừng công cụ và trích vào thư mục riêng mới,
đối chiếu trước khi thay cây đang dùng:

```sh
shasum -a 256 outputs/backups/pre_migration_20261017_100229/project_snapshot.tar
mkdir outputs/restore_step_1_20261017_01
tar -xpf outputs/backups/pre_migration_20261017_100229/project_snapshot.tar -C outputs/restore_step_1_20261017_01
python3 -B docs/migration_audit/restore_extended_attributes.py --root outputs/restore_step_1_20261017_01 --attributes docs/migration_audit/baseline_xattrs.json --inventory docs/migration_audit/baseline_inventory.json
python3 -B docs/migration_audit/verify_snapshot.py --root outputs/restore_step_1_20261017_01 --inventory docs/migration_audit/baseline_inventory.json --archive outputs/backups/pre_migration_20261017_100229/project_snapshot.tar --archive-sha256 2917b8e027a090fdb7564ac71336e4a82e7ce6e1dc9e038658a2c468e37bdbf7
```

Chọn tên staging chưa tồn tại và đủ dung lượng (snapshot 4.471.776.768 byte,
cộng khoảng 4,1 GiB để trích). Sau kiểm tra đạt, giữ cây hiện tại ở thư mục giữ
lại trước khi thay thế; không ghép state từ các mốc khác nhau. Hoàn tác riêng
bước kết quả ở [migration_plan.md](migration_plan.md); tạo lại môi trường tại
đúng vị trí bằng wheel/lock có hash ở [python_environments.md](python_environments.md).
Python nền phải được cài trên máy; venv và shebang cũ cần đúng đường dẫn gốc.
Model U2Net có bản sao tại
`outputs/backups/pre_migration_20261017_100229/external_dependencies/u2net.onnx`.

## Những phần chưa được xác nhận

- Chưa chạy trên Windows, Linux, Apple Silicon hoặc phiên bản Python khác.
  Nhóm segmentation còn phụ thuộc `fcntl`; bộ wheel offline chỉ xác minh cho
  macOS Intel/Python 3.10.11.
- GUI dùng sự kiện chuột/callback tự động trên Mac; chưa đánh giá bàn phím/chuột
  vật lý, màn hình DPI khác, làm việc nhiều giờ hoặc nguồn dữ liệu khác.
- Chưa kiểm thử mọi tổ hợp lỗi sau chỉnh sửa, mất điện/SIGKILL và khôi phục lỗi
  đồng thời nhiều tệp. Đã thử lỗi ghi manifest/rollback và mask phẳng hỏng; không
  khẳng định tự phục hồi được mọi hỏng hóc của bộ đã chỉnh/phân loại.
- Luồng cuối chưa chạy các nhánh `--force`, `--recursive`, `--repair-borders`,
  resize `--max-side` và tùy chọn đồng bộ tự đánh dấu `--mark-*`. Chưa thử cài
  mới từ Internet; môi trường ảnh đã cài offline, lock chung đã giải phụ thuộc
  bằng dry-run ở bước môi trường.
- Không chạy lại toàn bộ 1.297 ảnh hoặc tạo lại 812 mask. Chưa đánh giá chất
  lượng tư thế, chất lượng từng mask, IoU, độ chính xác phân đoạn/tìm kiếm.
- Không thể thực thi các kiểm thử lịch sử chỉ còn bytecode. Không có bộ 317
  mask lịch sử để xác minh, không tái tạo các bảng/CSV đã vắng từ trước.
- Năm URL HTTP trong tài liệu được liệt kê, chưa truy cập để xác nhận nội dung
  bên ngoài; kiểm tra liên kết của bước này áp dụng cho tài liệu/mã/ảnh cục bộ.
- Không xác nhận resume bộ lịch sử bằng mã mới; việc từ chối là hành vi đã kiểm
  chứng. Các sai khác state/kiểm kê và 30 hash overlay trước chỉnh vẫn cần giữ
  ngữ cảnh lịch sử nếu có một đợt hòa giải dữ liệu riêng sau này.
