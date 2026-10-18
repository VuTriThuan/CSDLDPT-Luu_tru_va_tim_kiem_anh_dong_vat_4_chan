# Kế hoạch chuẩn bị sắp xếp dự án BTL

Ngày kiểm kê: **17/10/2026, giờ Việt Nam (UTC+07:00)**. Thư mục gốc:
`/Users/trithuan/Desktop/CSDLDPT/BTL`.

**Phạm vi: chỉ chuẩn bị. Chưa di chuyển, đổi tên, sửa mã, sửa manifest hoặc chạy lại xử lý ảnh.**
Chỉ thêm tài liệu kiểm kê trong `docs/` và bản sao lưu trong `outputs/backups/`.
Các bước chuyển cấu trúc và lệnh hoàn tác bên dưới là hướng dẫn cho lần thực hiện sau.

Trạng thái xác minh bản sao lưu: **ĐÃ XÁC MINH — archive, khôi phục mẫu và cây gốc đều đạt**.

## 1. Mốc nguyên trạng và kiểm kê

Mốc kiểm kê được lấy trước khi tạo hai thư mục mới `docs/` và `outputs/`.
Bản sao lưu chứa toàn bộ các mục thuộc mốc đó, gồm `.git`, `.DS_Store`, tệp khóa,
hai `.venv`, dữ liệu, kết quả và hồ sơ chỉnh sửa. Không chỉ sao lưu tệp được Git theo dõi.
Các tài liệu chuẩn bị được tạo sau mốc này nằm ngoài nội dung `project_snapshot.tar`;
chúng được lưu bên cạnh archive để dùng khi khôi phục.

| Nhóm | Số lượng tệp thông thường | Nội dung |
|---|---:|---|
| Ảnh nguồn | 1.297 | `data/anh-chua-loc/` |
| Ảnh cắt đang dùng | 812 | `data/anh-da-cat-576x384/` |
| Ảnh cắt đã loại | 485 | `data/anh-da-cat-576x384-da-xoa/` |
| Mask hiện hành | 812 | `reports/yeu_cau_2/grabcut_output/masks/` |
| Overlay hiện hành | 812 | `reports/yeu_cau_2/grabcut_output/overlays/`, hiện đều ở thư mục này |
| Bảng ảnh nhanh | 102 | `quicklooks/batch_*.jpg` |
| Lịch sử chỉnh mask | 1.496 | 374 phiên; mỗi phiên có bốn tệp |
| Sao lưu đồng bộ overlay | 4 | Bốn ZIP; tổng cộng 508 thành viên đã đọc và băm riêng |
| Manifest hiện hành | 1 | 812 hàng, 24 cột |
| Mã Python | 13 | 12 tệp công cụ/kiểm tra kết quả và một tệp kiểm thử compatibility |
| Tài liệu/requirements | 7 | Sáu Markdown và một `requirements.txt` |
| Cache Python của mã dự án | 13 | Giữ trong sao lưu, không dùng làm mã nguồn |
| Trạng thái cắt | 4 | Hai JSON, một CSV, một tệp khóa |
| Trạng thái/tệp phụ khác | 26 | JSON, CSV, log, khóa và `.DS_Store` ngoài nhóm trên |
| Hai môi trường Python | 14.854 | Tệp package/runtime, chưa tính symlink |
| Git | 3.526 | Toàn bộ lịch sử, index, refs, hooks và cấu hình |
| **Tổng** | **24.264** | **4.371.659.726 byte nội dung tệp, khoảng 4,07 GiB** |

Có thêm **2.281 thư mục và 6 symlink**, tổng cộng **26.551 mục**.
`du` báo khoảng **4,12 GiB được cấp phát**; khác dung lượng nội dung do block và metadata.

Phụ lục đầy đủ, không rút gọn `.git` hoặc các môi trường:

- [Cây nguyên trạng](migration_audit/original_tree.txt).
- [Kiểm kê JSON](migration_audit/baseline_inventory.json): tên, loại, dung lượng,
  mode, UID/GID, mtime nanosecond, SHA-256 và SHA-256 của extended attributes.
- [Kiểm kê CSV](migration_audit/baseline_inventory.csv).
- [SHA-256 mọi tệp nguyên trạng](migration_audit/baseline_sha256.txt).
- [Danh sách ảnh, mask, overlay, manifest, lịch sử và tài liệu kèm SHA-256](migration_audit/asset_sha256.csv).
- [SHA-256 thành viên của bốn ZIP lịch sử](migration_audit/zip_member_sha256.csv).
- [Tổng hợp kiểm kê](migration_audit/audit_summary.json).

Git đang có **1.436 mục sửa, 24 mục xóa, 1.682 tệp chưa theo dõi** ở mốc ban đầu.
Danh sách chính xác: [git_status_before.txt](migration_audit/git_status_before.txt)
và bản phân cách NUL [git_status_before.nul](migration_audit/git_status_before.nul).
Các mục đang bị xóa không được tái tạo. Lịch sử và index của chúng vẫn có trong `.git` đã sao lưu.

### Những khác biệt đã có trước khi chuẩn bị

1. `_cat_tu_dong.json` có 1.297 bản ghi: 665 `saved`, 632 `deleted`.
   Vị trí thực tế là 812 ảnh đang dùng và 485 ảnh đã loại. Có **189 bản ghi lệch vị trí**:
   168 ảnh ghi `deleted` nhưng nằm trong thư mục đang dùng, 21 ảnh ghi `saved` nhưng nằm
   trong thư mục đã loại. Chi tiết: [crop_state_discrepancies.csv](migration_audit/crop_state_discrepancies.csv).
   Không sửa trạng thái, không chuyển ảnh để làm khớp trong bước này. Khi chuyển cấu trúc,
   giữ cả giá trị cũ và vị trí thực tế; mọi quyết định hòa giải phải là thay đổi riêng có nhật ký.
2. `_cat_tu_dong.truoc-cap-nhat.json` có 1.300 bản ghi và tên ảnh lịch sử; đây không phải
   trạng thái hiện hành. Không lấy nó để ghi đè trạng thái 1.297 ảnh.
3. Manifest hiện tại có **812 `success`, 812 `da_duyet`, 812 `dat`**.
   Cả **2.436 đối chiếu SHA-256** của ảnh nguồn cắt, mask và overlay đều khớp mốc kiểm kê.
   `verification.json`, `manual_visual_review.json`, `full_processing_summary.json` và một số
   đoạn hướng dẫn mô tả các thời điểm cũ (`chua_duyet`); giữ chúng như bằng chứng lịch sử.
4. `README_MASK_MOI_CAN_SUA.md` mô tả 317 mask mới, nhưng thư mục
   `reports/yeu_cau_2/mask_moi_can_sua/` **không hiện diện**. Có mã tạo/kiểm tra và ảnh chụp
   kiểm kê trước lần chạy; không coi văn bản mô tả là bằng chứng các tệp kết quả đang tồn tại.
5. `test_check_grabcut.py` đang bị xóa theo Git; các tên `test_chinh_mask` và
   `test_dong_bo_overlays` chỉ còn xuất hiện ở bytecode. Không có mã nguồn các kiểm thử đó
   trong cây hiện tại. Bytecode vẫn được sao lưu, không được coi là bộ kiểm thử có thể chạy.

## 2. Cây đích dự kiến

```text
BTL/
├── readme.md
├── .git/                         # giữ nguyên định dạng nội bộ Git
├── .venv/                        # giữ vị trí môi trường gốc trong đợt chuyển
├── docs/
│   ├── migration_plan.md
│   ├── migration_audit/           # phụ lục chuẩn bị hiện tại
│   ├── animal_similarities_and_differences.md
│   ├── requirement_2_attributes.md
│   ├── image_processing_guide.md
│   ├── grabcut_guide.md
│   └── revised_masks_guide.md
├── data/
│   ├── source_images/
│   ├── cropped_images_576x384/
│   │   ├── crop_state.json
│   │   ├── crop_state_before_update.json
│   │   ├── crop_report.csv
│   │   ├── image_tools.lock
│   │   └── <lowercase_snake_case>.jpg
│   └── deleted_cropped_images_576x384/
├── tools/
│   ├── image_processing/
│   │   ├── .venv/                # tạo lại tại đích, không di chuyển venv cũ
│   │   ├── requirements.txt
│   │   ├── tool_common.py
│   │   ├── auto_crop.py
│   │   ├── rename_images.py
│   │   └── review_images.py
│   └── segmentation/
│       ├── audit_images.py
│       ├── run_grabcut.py
│       ├── edit_masks.py
│       ├── sync_overlays.py
│       ├── review_overlays.py
│       └── regenerate_flagged_masks.py
├── tests/
│   ├── image_processing/test_compatibility.py
│   └── segmentation/
│       ├── verify_grabcut_results.py
│       └── verify_revised_masks.py
└── outputs/
    ├── backups/pre_migration_20261017_100229/
    ├── requirement_2/             # CSV/JSON kiểm kê và nguồn gốc báo cáo
    ├── cache/                    # bytecode cũ được giữ để truy nguyên
    ├── system_metadata/          # bản giữ các .DS_Store, đổi tên rõ nguồn
    ├── revised_masks/            # chỉ là đích dự kiến, hiện chưa có kết quả
    └── grabcut/
        ├── manifest.csv
        ├── run_config.json
        ├── run.lock
        ├── masks/<image_stem>_mask.png
        ├── overlays/<image_stem>_overlay.png
        │   ├── accepted/         # chỉ tạo khi cần; không tự phân loại lại 812 ảnh
        │   ├── needs_revision/
        │   └── redo/
        ├── quicklooks/
        ├── manual_edits/<normalized_edit_id>/
        │   ├── mask_before.png
        │   ├── overlay_before.png
        │   ├── scribbles.png
        │   └── record.json
        ├── overlay_sync_backups/
        ├── provenance/           # sẽ thêm khi chuyển: cấu hình/manifest cũ, ledger
        └── <các JSON, CSV và log hiện có>
```

Cây trên là bản thiết kế, không phải cây đã được thực hiện. Chưa tạo các thư mục
nghiệp vụ đích ngoài `docs/` và `outputs/backups/` dùng cho chuẩn bị.

## 3. Bảng ánh xạ tên và quy tắc

**Bảng đầy đủ, từng mục một, gồm đủ 26.551 mục nguyên trạng:**
[path_mapping.csv](migration_audit/path_mapping.csv).
Các cột gồm `current_path`, `target_path`, loại, nhóm, hành động, SHA-256 cũ và ghi chú.
Mọi ảnh và mọi hồ sơ chỉnh sửa đều có dòng riêng; không chỉ dùng wildcard để đại diện.
[mapping_validation.json](migration_audit/mapping_validation.json) ghi kết quả kiểm tra
đủ mục và **0 đích trùng nhau**, kể cả sau NFC và so sánh không phân biệt hoa/thường.

Bảng dưới là phần tra cứu cho các thư mục, mã và tệp điều khiển. Khi thực hiện,
dùng CSV đầy đủ làm đầu vào chính thức; phụ lục đó là một phần của kế hoạch này.

| Hiện tại | Đích tiếng Anh | Hành động |
|---|---|---|
| `.DS_Store` | `outputs/system_metadata/root/ds_store.bin` | move_or_rename |
| `.git` | `.git` | keep_opaque |
| `.venv` | `.venv` | keep_environment |
| `README.md` | `readme.md` | move_or_rename |
| `bao_cao_giong_khac_dong_vat.md` | `docs/animal_similarities_and_differences.md` | move_or_rename |
| `bao_cao_yeu_cau_2_thuoc_tinh.md` | `docs/requirement_2_attributes.md` | move_or_rename |
| `bo_tool_anh_576x384` | `tools/image_processing` | move_or_rename |
| `bo_tool_anh_576x384/.DS_Store` | `outputs/system_metadata/bo_tool_anh_576x384/ds_store.bin` | move_or_rename |
| `bo_tool_anh_576x384/.venv` | `tools/image_processing/.venv` | rebuild_environment |
| `bo_tool_anh_576x384/HUONG_DAN.md` | `docs/image_processing_guide.md` | move_or_rename |
| `bo_tool_anh_576x384/__pycache__` | `outputs/cache/image_processing` | move_or_rename |
| `bo_tool_anh_576x384/cat_tu_dong.py` | `tools/image_processing/auto_crop.py` | move_or_rename |
| `bo_tool_anh_576x384/doi_ten_anh.py` | `tools/image_processing/rename_images.py` | move_or_rename |
| `bo_tool_anh_576x384/duyet_anh.py` | `tools/image_processing/review_images.py` | move_or_rename |
| `bo_tool_anh_576x384/requirements.txt` | `tools/image_processing/requirements.txt` | move_or_rename |
| `bo_tool_anh_576x384/tests` | `tests/image_processing` | move_or_rename |
| `bo_tool_anh_576x384/tests/test_compatibility.py` | `tests/image_processing/test_compatibility.py` | move_or_rename |
| `bo_tool_anh_576x384/tool_common.py` | `tools/image_processing/tool_common.py` | move_or_rename |
| `data` | `data` | keep |
| `data/.DS_Store` | `outputs/system_metadata/data/ds_store.bin` | move_or_rename |
| `data/anh-chua-loc` | `data/source_images` | move_or_rename |
| `data/anh-da-cat-576x384` | `data/cropped_images_576x384` | move_or_rename |
| `data/anh-da-cat-576x384/.tool_anh.lock` | `data/cropped_images_576x384/image_tools.lock` | move_or_rename |
| `data/anh-da-cat-576x384/_cat_tu_dong.json` | `data/cropped_images_576x384/crop_state.json` | move_or_rename |
| `data/anh-da-cat-576x384/_cat_tu_dong.truoc-cap-nhat.json` | `data/cropped_images_576x384/crop_state_before_update.json` | move_or_rename |
| `data/anh-da-cat-576x384/bao_cao_cat.csv` | `data/cropped_images_576x384/crop_report.csv` | move_or_rename |
| `data/anh-da-cat-576x384-da-xoa` | `data/deleted_cropped_images_576x384` | move_or_rename |
| `reports` | `outputs` | move_or_rename |
| `reports/.DS_Store` | `outputs/system_metadata/reports/ds_store.bin` | move_or_rename |
| `reports/yeu_cau_2` | `outputs/requirement_2` | move_or_rename |
| `reports/yeu_cau_2/.DS_Store` | `outputs/system_metadata/reports/yeu_cau_2/ds_store.bin` | move_or_rename |
| `reports/yeu_cau_2/README_GRABCUT.md` | `docs/grabcut_guide.md` | move_or_rename |
| `reports/yeu_cau_2/README_MASK_MOI_CAN_SUA.md` | `docs/revised_masks_guide.md` | move_or_rename |
| `reports/yeu_cau_2/anh_da_xem.csv` | `outputs/requirement_2/viewed_images.csv` | move_or_rename |
| `reports/yeu_cau_2/audit_images.py` | `tools/segmentation/audit_images.py` | move_or_rename |
| `reports/yeu_cau_2/check_grabcut.py` | `tools/segmentation/run_grabcut.py` | move_or_rename |
| `reports/yeu_cau_2/chinh_mask.py` | `tools/segmentation/edit_masks.py` | move_or_rename |
| `reports/yeu_cau_2/dong_bo_overlays.py` | `tools/segmentation/sync_overlays.py` | move_or_rename |
| `reports/yeu_cau_2/duyet_overlays.py` | `tools/segmentation/review_overlays.py` | move_or_rename |
| `reports/yeu_cau_2/grabcut_moi_truong.json` | `outputs/requirement_2/grabcut_environment.json` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/.DS_Store` | `outputs/system_metadata/reports/yeu_cau_2/grabcut_output/ds_store.bin` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/.run.lock` | `outputs/grabcut/run.lock` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/errors.csv` | `outputs/grabcut/errors.csv` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/full_processing_summary.json` | `outputs/grabcut/full_processing_summary.json` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/full_run.log` | `outputs/grabcut/full_run.log` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/manifest.csv` | `outputs/grabcut/manifest.csv` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/manual_edits` | `outputs/grabcut/manual_edits` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/manual_visual_review.json` | `outputs/grabcut/manual_visual_review.json` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/masks` | `outputs/grabcut/masks` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/overlay_sync_backups` | `outputs/grabcut/overlay_sync_backups` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/overlay_sync_report.json` | `outputs/grabcut/overlay_sync_report.json` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/overlay_sync_verification.json` | `outputs/grabcut/overlay_sync_verification.json` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/overlays` | `outputs/grabcut/overlays` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/quicklooks` | `outputs/grabcut/quicklooks` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/resume_verification.json` | `outputs/grabcut/resume_verification.json` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/resume_verification.log` | `outputs/grabcut/resume_verification.log` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/review_priority.csv` | `outputs/grabcut/review_priority.csv` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/run_config.json` | `outputs/grabcut/run_config.json` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/summary.json` | `outputs/grabcut/summary.json` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/verification.json` | `outputs/grabcut/verification.json` | move_or_rename |
| `reports/yeu_cau_2/grabcut_output/visual_review_notes.csv` | `outputs/grabcut/visual_review_notes.csv` | move_or_rename |
| `reports/yeu_cau_2/grabcut_so_do.csv` | `outputs/requirement_2/grabcut_diagram.csv` | move_or_rename |
| `reports/yeu_cau_2/grabcut_source_before.json` | `outputs/requirement_2/grabcut_source_before.json` | move_or_rename |
| `reports/yeu_cau_2/kiem_ke.json` | `outputs/requirement_2/image_inventory.json` | move_or_rename |
| `reports/yeu_cau_2/mask_moi_can_sua_truoc_khi_chay.json` | `outputs/requirement_2/revised_masks_source_before.json` | move_or_rename |
| `reports/yeu_cau_2/tao_lai_mask_can_sua.py` | `tools/segmentation/regenerate_flagged_masks.py` | move_or_rename |
| `reports/yeu_cau_2/verify_grabcut_results.py` | `tests/segmentation/verify_grabcut_results.py` | move_or_rename |
| `reports/yeu_cau_2/verify_mask_moi_can_sua.py` | `tests/segmentation/verify_revised_masks.py` | move_or_rename |


Các quy tắc bổ sung:

- Tên do dự án quản lý dùng tiếng Anh, ASCII, `lowercase_snake_case`; giữ phần mở rộng
  chữ thường. Tên phân loại khoa học Latin được giữ nghĩa và chuyển chữ thường;
  không đổi nhãn loài hoặc đánh lại số thứ tự. Hậu tố bản sao `(1)` thành `_copy_1`.
- Ví dụ `Canis_familiaris_0002.jpg` thành `canis_familiaris_0002.jpg`;
  `equus-quagga_0779.jpg` thành `equus_quagga_0779.jpg`.
  Ảnh trong `masks/<tên ảnh>.jpg.png` thành `<image_stem>_mask.png`;
  overlay tương ứng thành `<image_stem>_overlay.png`. Nội dung ảnh giữ nguyên byte.
- `đạt` → `accepted`, `cần sửa` → `needs_revision`, `làm lại` → `redo`.
  Các thư mục này hiện không có trong cây sống, nhưng có trong mã/hồ sơ lịch sử;
  xem [planned_reference_targets.csv](migration_audit/planned_reference_targets.csv).
- ID thư mục chỉnh sửa và tên ZIP được chuẩn hóa ký tự, không đổi thời điểm hoặc
  số định danh. Bốn tệp bên trong mỗi hồ sơ và nội dung ZIP lịch sử giữ nguyên byte.
- `.git`, `.venv` và tên nội bộ thư viện bên thứ ba là **ngoại lệ kỹ thuật rõ ràng**:
  không đổi `HEAD`, `METADATA`, tên package, ABI, script hệ thống hoặc symlink thành snake_case.
  Đổi chúng sẽ làm hỏng Git/Python. CSV ghi `keep_opaque`, `keep_environment` hoặc
  `rebuild_environment` cho từng mục; không có mục bị bỏ qua.
- Đối với môi trường công cụ, `target_path` mô tả vị trí sau khi **tạo lại**; không phải
  lệnh `mv` 8.175 mục. Môi trường cũ được giữ trong snapshot và giữ trên cây cũ cho
  đến khi môi trường mới được kiểm tra. Cache cũ được lưu ở `outputs/cache/`, không
  được dùng để import mã đã đổi tên. Không xóa cache hoặc `.DS_Store` trong bước này.
- Chỉ chuyển đường dẫn/tên và cập nhật các trường tham chiếu cần thiết trong đợt sau.
  Các enum `saved`, `deleted`, `da_duyet`, `dat`, `chua_duyet`, `can_sua`, `lam_lai`
  là giá trị giao thức hiện có; không dịch cùng tên thư mục. Nếu muốn đổi enum,
  phải có chuyển đổi schema và kiểm thử riêng, không làm bằng replace toàn dự án.

## 4. Kiểm kê các đường dẫn và phụ thuộc

Đã phân tích **13 Python, 388 JSON, 7 CSV và 7 tệp tài liệu/requirements**;
không có lỗi đọc hoặc parse. Đã lưu **21.580 lần xuất hiện tham chiếu**, gồm chuỗi
Python qua AST, khóa và giá trị JSON, từng ô CSV, token và dòng trong hướng dẫn.
Không thực thi các script audit/verifier cũ vì một số script ghi lại kết quả.

- [path_references.csv](migration_audit/path_references.csv): tệp, dòng/selector/hàng/cột,
  giá trị, các ứng viên đường dẫn tồn tại và tình trạng phân giải.
- [path_reference_lines.csv](migration_audit/path_reference_lines.csv): toàn bộ dòng
  liên quan trong mã/hướng dẫn, gồm biểu thức ghép đường dẫn động.
- [reference_scan_summary.json](migration_audit/reference_scan_summary.json).
- [historical_path_aliases.csv](migration_audit/historical_path_aliases.csv): **11.833 ánh xạ
  có phạm vi** cho hồ sơ chỉnh sửa và các snapshot lịch sử; không sửa bằng chứng cũ.

16.349 tham chiếu có ít nhất một ứng viên tồn tại; 5.231 tham chiếu còn lại gồm
tên lịch sử, đường dẫn động, mẫu tài liệu, thư mục tùy chọn hoặc đường dẫn thiếu.
Đây không phải 5.231 tệp bị mất. Phân tích tĩnh không chứng minh được mọi biểu thức
runtime; kiểm thử ở bước chuyển phải đối chiếu các đường dẫn được tạo khi chạy.

| Nguồn tham chiếu | Điểm cần cập nhật khi chuyển |
|---|---|
| `tool_common.py` | `TOOL_DIR.parent` hiện chính là root; sau khi đặt trong `tools/image_processing/` phải tìm root bằng cấu hình/mốc rõ ràng. Cập nhật vị trí venv và requirements. |
| `auto_crop.py`, `review_images.py`, `rename_images.py` dự kiến | Cả ba hiện ghi/đọc `_cat_tu_dong.json`, `bao_cao_cat.csv`, tên thư mục nguồn/cắt/đã loại và `.tool_anh.lock`; phải đổi đồng bộ. |
| Crop-state JSON | `source` tuyệt đối, `source_relative` tính từ thư mục JSON, khóa `images`, giá trị `output`, `signature`, `source_sha256`, trạng thái xóa/lật. CSV dùng hai cột tên nguồn/đầu ra. |
| `check_grabcut.py`, `audit_images.py`, `tao_lai_mask_can_sua.py` | `ROOT = parents[2]`, `BASE = parent`, đầu ra nằm cạnh mã; sau khi tách `tools/`, `tests/`, `outputs/` không được tiếp tục suy ra đầu ra từ vị trí script. |
| Manifest/review CSV | `filename` ghép với thư mục nguồn; `mask_path`, `overlay_path`, `quicklook_path` tương đối với root của bộ kết quả; giữ đúng base khi đổi. |
| `run_config.json` và summary | `input_dir`/`output_dir` tuyệt đối; hash script và phiên bản thư viện là ràng buộc resume, không chỉ là thông tin mô tả. |
| Mask mới | `source_path`, `previous_mask_path`, `previous_overlay_path` tuyệt đối; cấu hình có `source_dir`, `previous_dir`, `queue_dir`, đường dẫn/hash mô hình. Bộ kết quả mới hiện vắng mặt. |
| Mask editor | Ghép overlay bằng `filename + '.png'`, phân loại bằng tên thư mục tiếng Việt, giữ đường dẫn manifest và history; cần thay bằng quy ước/lookup rõ ràng cho `_mask`/`_overlay`. |
| Overlay review/sync | `CATEGORIES`, đường dẫn `overlays/đạt/...`, nhận dạng chỉnh tay được chấp nhận, các basename trong manifest và quicklook phải cùng phiên bản quy ước. |
| Hồ sơ lịch sử | `overlay_before`, `overlay_after`, `mask_path`, `manifest_before`, `manifest_after`; đường dẫn lịch sử có thể không còn tồn tại. Giải qua alias có phạm vi theo bộ kết quả và phiên chỉnh sửa. |
| Snapshot JSON/ZIP | Khóa JSON có thể là tên ảnh hoặc đường dẫn từ root. ZIP chứa manifest/transaction và đường dẫn tương đối riêng; lưu nguyên bytes, không sửa nội dung archive cũ. |
| Tests và verifier | `sys.path`, `TOOL_DIR`, import tên module cũ, `BASE`, snapshot ở cạnh script, đường dẫn ảnh và nơi ghi JSON cần đổi. Verifier cũ có ghi kết quả khi chạy. |
| Markdown | Link tuyệt đối, lệnh chạy từ root hoặc từ thư mục công cụ, môi trường gọi Python, tên script, tên kết quả và các mô tả trạng thái theo thời điểm. |

### Hai môi trường Python và dữ liệu bên ngoài

Thông tin đầy đủ: [python_environments.json](migration_audit/python_environments.json),
[root_environment_packages.txt](migration_audit/root_environment_packages.txt) và
[image_processing_environment_packages.txt](migration_audit/image_processing_environment_packages.txt).
Đây là kiểm kê package đang cài, không phải lockfile có wheel/hash tái cài đặt.

| Mục | `.venv/` | `bo_tool_anh_576x384/.venv/` |
|---|---|---|
| Python | 3.10.11 | 3.10.11 |
| `numpy` | 1.26.4 | 2.2.6 |
| `pillow` | 12.3.0 | 11.3.0 |
| `onnxruntime` | 1.23.2 | 1.23.2 |
| OpenCV | `opencv-python-headless` 4.11.0.86 | Chưa cài |
| `certifi` | Chưa cài | 2026.7.22 |
| Interpreter symlink | Ra Python hệ thống trong `/Library/Frameworks/...` | Trỏ tuyệt đối qua `.venv/bin/python3` của root |

`pyvenv.cfg`, shebang `pip`, script activate và symlink có đường dẫn tuyệt đối.
Không di chuyển trực tiếp venv. Không gộp hai môi trường trong đợt chuyển cấu trúc.
Hai môi trường đã được sao lưu nguyên trạng, bao gồm symlink, không dereference.
Khôi phục trên cùng máy về đúng root có thể dùng lại chúng nếu Python nền còn đó;
khôi phục trên máy khác cần cài Python phù hợp và tạo lại môi trường.

Các phụ thuộc ngoài root được kiểm kê và băm tại
[external_dependencies.json](migration_audit/external_dependencies.json):

- `~/.cache/animal-crop/u2net.onnx`, 175.997.641 byte;
  SHA-256 `8d10d2f3bb75ae3b6d527c77944fc5e7dcd94b29809d47a739a7a728a912b491`.
- `/Users/trithuan/Downloads/feature_extractors.py` và `README.md`: tài liệu tham khảo
  tồn tại, nằm ngoài cây BTL. Mã GrabCut hiện không import trực tiếp từ Downloads.
- Python nền `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3`:
  đây là cài đặt hệ thống, không nằm trong snapshot dự án.

Các bản sao bổ sung của mô hình và hai tệp tham khảo được đặt cạnh snapshot,
trong `external_dependencies/`; không được chèn chúng vào cây nguồn hiện tại.
Không tuyên bố archive dự án chứa toàn bộ framework Python hoặc là bản sao lưu ổ đĩa.

## 5. Kiểm tra đặc biệt: chạy tiếp và lịch sử chỉnh mask

### GrabCut `--resume`

Trong `check_grabcut.py`, cấu hình được so sánh bằng **toàn bộ dictionary**.
`input_dir`, `script_sha256`, `opencv`, `numpy`, `pillow` và tham số đều phải giống.
`reusable()` chỉ bỏ qua hàng `success` có SHA-256 nguồn, mask, overlay khớp và
đường dẫn artifact hợp lệ. Khi chạy, chương trình vẫn ghi manifest, summary,
review CSV và tái tạo quicklook; vì vậy không dùng `--resume` trên dữ liệu thật
để “kiểm tra chỉ đọc” trong bước chuẩn bị.

Đã phát hiện ngay ở cấu trúc hiện tại:

- `run_config.json` ghi script SHA-256
  `711d4380c4fd19946fcec6f4a90a8e3add312b22e6e8b0ea986e95edd1da1e51`;
  mã hiện tại có SHA-256
  `8236ca57acaffc98516de4e0ae77a778f9cfaec0286239dc834bbf1bc21365b6`.
- Config ghi OpenCV **4.12.0**, NumPy **1.26.4**, Pillow **12.2.0**;
  không môi trường nào trong hai môi trường hiện tại khớp đủ các phiên bản này.
  Môi trường của công cụ còn thiếu OpenCV.
- `run_locked()` tạo lại `mask_path`, `overlay_path`, `quicklook_path` theo tên mặc định
  trước khi kiểm tra reuse. Nó có thể thay đường dẫn overlay đã phân loại, dù hash
  của một artifact lịch sử vẫn đúng. 812 overlay hiện ở thư mục phẳng nên chưa gặp
  riêng trường hợp này ở manifest hiện hành; phải kiểm thử trường hợp phân loại.
- `resume_verification.json` là kết quả của lần chạy trước, không chứng minh mã/môi trường
  hiện tại hoặc cây sau chuyển còn resume được.

Thiết kế cần làm trong đợt chuyển: lưu config gốc nguyên bytes trong provenance,
tạo schema cấu hình mới phân biệt vị trí dữ liệu với cấu hình thuật toán và nguồn gốc mã.
Adapter chỉ chấp nhận tập legacy/config cụ thể có SHA-256 đã ghi trong ledger;
phải kiểm chứng đầy đủ hash đầu vào/đầu ra và giữ nguyên trạng thái duyệt.
Không sửa duy nhất `script_sha256` hoặc bỏ kiểm tra config để ép resume qua.
Đối với tác vụ tính lại dùng thư viện/thuật toán khác, chọn bộ đầu ra mới.

### Cắt ảnh và mask mới

`cat_tu_dong.py` **không có cờ `--resume`**; tự tiếp tục dựa trên state, hash/signature,
config và output. `source_relative` được giải tương đối với thư mục chứa state và
được ưu tiên hơn `source`. Phải cập nhật cả hai, mọi khóa `images` và `output`, đồng
thời giữ nguyên signature, SHA, số lần lật, trạng thái đã xóa và cảnh báo. Không chạy
`--force`, `--repair-borders` hoặc công cụ rename hiện tại để thực hiện cuộc chuyển này.
189 khác biệt trạng thái/vị trí cần test sao cho lần tiếp tục không tự tái tạo ảnh đã loại.

`tao_lai_mask_can_sua.py --resume` cũng so sánh config đầy đủ, gồm đường dẫn/hash model,
hash script và phiên bản thư viện. Reuse còn đòi nguồn, mask cũ, overlay cũ và kết quả
mới đúng SHA. Không có bộ kết quả này trong cây hiện tại; chỉ kiểm thử bằng fixture/bản
sao riêng, không chạy lại 317 mask từ lời mô tả trong hướng dẫn.

### Lịch sử chỉnh mask

Có **374 `record.json`, tất cả `state=saved`**, không có `prepared`, `rolled_back` hoặc
`needs_recovery` tại mốc kiểm kê. Mỗi hồ sơ được giữ cùng `mask_before.png`,
`overlay_before.png`, `scribbles.png`. Cả bốn tệp của mọi phiên đều đã băm và sao lưu.

Khi lưu, editor tạo hồ sơ `prepared`, ghi overlay mới, mask mới, manifest rồi xóa
overlay ở vị trí cũ, sau đó chuyển `saved`. Khi lỗi, nó rollback và ghi trạng thái
khôi phục. Vì vậy không thể chỉ giữ `record.json` hoặc mask mới mà bỏ các ảnh trước sửa.
Manifest trong hồ sơ là snapshot từng hàng; nó không nhất thiết bằng manifest hiện tại
sau các lần đồng bộ. Đường dẫn overlay trước/sau trong hồ sơ cũng không nhất thiết
còn tồn tại trên cây sống. Không suy diễn trạng thái lỗi chỉ từ việc thiếu đường dẫn cũ.

Giữ nguyên bytes của record, snapshot cũ và ZIP. Khi chuyển, dùng
`historical_path_aliases.csv` có trường `evidence_file`/selector để hiểu tên cũ theo đúng
phạm vi. Ghi ledger liên kết đường dẫn hồ sơ cũ/mới, SHA record, SHA asset và config;
không “sửa lịch sử” bằng thay chuỗi trong `manifest_before`/`manifest_after`.
Cập nhật bộ đọc history/sync để hỗ trợ alias và tên thư mục mới trước khi chạy editor.

Undo trong `duyet_overlays.py`, `duyet_anh.py` và nét tô chưa lưu của editor là bộ nhớ
của tiến trình. Snapshot lưu trạng thái trên đĩa, không lưu RAM/khóa kernel. Vì vậy
đóng phiên có thay đổi chưa lưu trước mọi lần chuyển thật; trong lần sao lưu này đã
lấy được độc quyền trên cả hai tệp khóa hiện hữu bằng chế độ chỉ đọc.

## 6. Dung lượng, cách tạo và xác minh bản sao lưu

Trước khi sao lưu, ổ chứa dự án còn khoảng **45 GiB**. Kiểm tra tự động yêu cầu đủ
**3 × tổng byte nội dung + 2 GiB dự phòng + 4 KiB/mục**, tương đương khoảng **14,32 GiB**.
Ngưỡng này dành chỗ cho archive, khôi phục thử/toàn bộ và bản sao bảo vệ riêng.
Nếu không đạt thì dừng trước khi tạo archive; không xóa dữ liệu hoặc bỏ môi trường để làm nhỏ backup.
Các số byte cụ thể ở [backup_verification.json](migration_audit/backup_verification.json).

Vị trí bản sao lưu bền trong workspace:

```text
/Users/trithuan/Desktop/CSDLDPT/BTL/outputs/backups/pre_migration_20261017_100229/
```

Archive chính: `project_snapshot.tar`, không nén để giảm thêm một bước xử lý và
cho phép đọc trực tiếp từng thành viên. Dùng BSD tar định dạng **PAX**, giữ mode,
symlink, timestamp có phần lẻ, ACL/extended attributes macOS. Không dereference symlink.
Đã chủ động chọn PAX sau khi kiểm tra phát hiện định dạng mặc định làm mất phần lẻ
mtime của hai thư mục; archive cuối phải qua kiểm tra lại với mốc gốc.

Tar nhận **danh sách chín mục top-level ban đầu**, gồm các mục ẩn, thay vì glob `*`
hoặc chỉ các tệp Git. Danh sách ở [original_top_level.txt](migration_audit/original_top_level.txt).
`docs/` và `outputs/` chưa tồn tại tại mốc đó nên không thể bị sao lưu đệ quy vào chính
archive. Không có exclusion đối với dữ liệu, kết quả, môi trường, trạng thái hoặc `.git`.

Quy trình kiểm chứng đã dùng:

1. Băm toàn bộ tệp gốc và ghi loại, mode, mtime, symlink, extended attributes.
   Giữ khóa độc quyền trên `.tool_anh.lock` và `.run.lock` bằng cách mở `rb`, không
   xóa/tạo/ghi lại tệp khóa. Khóa được hệ điều hành nhả khi xong.
2. Tạo tar PAX từ danh sách top-level ban đầu; ghi SHA-256 của toàn bộ archive vào
   `project_snapshot.tar.sha256`. AppleDouble do BSD tar sinh để giữ metadata được
   ghi riêng, không coi là dữ liệu nguồn mới hoặc bỏ lẫn tệp ẩn thật.
3. Đọc **toàn bộ** archive: kiểm tra đủ 26.551 mục, không trùng, SHA-256 của mọi tệp,
   kiểu, symlink, mode và mtime. Không chỉ kiểm tra xem tar có liệt kê được hay không.
4. Giải nén mẫu độc lập: ảnh nguồn/cắt/đã loại, mask, overlay, manifest, state, hồ sơ
   chỉnh sửa, ZIP lịch sử, mã/tài liệu, `.DS_Store`, Git HEAD/index, config/activate/pip
   và symlink Python của cả hai môi trường, tệp khóa. Đối chiếu SHA, mode, mtime,
   symlink và extended attributes của các mẫu. macOS tự điều chỉnh cờ `quarantine`
   khi giải nén; dùng `baseline_xattrs.json` và `restore_extended_attributes.py` để
   đặt lại giá trị gốc rồi kiểm chứng SHA thuộc tính. Khi giải nén bổ sung vào thư mục
   đã tồn tại, helper còn dùng inventory để khôi phục mtime thư mục; đã kiểm tra hai
   phiên chỉnh sửa đầy đủ, cả 8 tệp và 2 thư mục. Không ghi đè cây dự án.
5. Băm lại tất cả tệp gốc và so metadata với mốc trước sao lưu để phát hiện thay đổi
   trong lúc chụp. Chỉ đánh dấu backup đạt nếu cả kiểm tra nội dung archive, mẫu
   khôi phục và kiểm tra cây gốc đều đạt.

Kết quả thực tế và vị trí giải nén mẫu: [backup_verification.json](migration_audit/backup_verification.json).
Giá trị extended attributes gốc được mã hóa Base64 trong
[baseline_xattrs.json](migration_audit/baseline_xattrs.json), kèm helper phục hồi;
đây là phần bắt buộc của bộ backup để phục hồi chính xác metadata.
Toàn bộ **27.739 extended attributes** trong archive được đối chiếu SHA-256 riêng,
không có sai khác: [archive_xattrs_verification.json](migration_audit/archive_xattrs_verification.json).
Danh sách thành viên: [archive_members.txt](migration_audit/archive_members.txt).
Log tar có thể có `Failed to set default locale` do locale tiến trình; việc này không
thay thế kiểm tra hash hoặc được dùng để bỏ qua lỗi đọc/khôi phục.

**Thông số archive cuối:**

- Dung lượng: **4.471.776.768 byte**.
- SHA-256: `2917b8e027a090fdb7564ac71336e4a82e7ce6e1dc9e038658a2c468e37bdbf7`.
- Số mẫu đã khôi phục và xác minh: **30**.

Bản sao lưu này cùng ổ vật lý với dự án, bảo vệ thao tác chuyển cấu trúc; không bảo vệ
sự cố mất ổ. Trước lần chuyển thật, đặt thêm một bản đã kiểm tra hash ngoài cây BTL,
ưu tiên ổ khác. Không di chuyển hoặc xóa `outputs/backups/` theo bảng đổi tên dữ liệu.
Nếu sau chuẩn bị có thay đổi dữ liệu/mask/state, tạo và xác minh snapshot mới trước
khi chuyển; mốc này không được coi là snapshot của dữ liệu thay đổi về sau.

## 7. Thứ tự thực hiện cho đợt chuyển sau

**Chưa thực hiện bất kỳ bước chuyển nào dưới đây.**

1. Ngừng batch/editor/review, lưu thay đổi còn trong RAM; kiểm tra khóa, băm lại mốc,
   kiểm tra dung lượng cho cả backup, staging và rollback. Kiểm tra lại SHA archive.
   Nếu snapshot không đạt hoặc dữ liệu đã đổi, dừng và tạo bản mới; chưa đổi tên.
2. Sao chép backup/metadata/quy trình khôi phục ra vị trí an toàn ngoài root. Dựng
   một bản phục hồi thử riêng và chạy `verify_snapshot.py` trước khi sửa cấu trúc.
   Thực hiện chuyển trên staging, giữ nguyên cây đang dùng cho đến khi đạt kiểm tra.
3. Chốt `path_mapping.csv`, aliases và ledger nguồn/đích; kiểm tra đủ đường dẫn,
   va chạm hoa/thường, NFC, tên đang tồn tại và trùng kiểu file/thư mục. Với đổi tên
   chỉ khác hoa/thường trên APFS, dùng tên trung gian duy nhất ở staging.
4. Tách cấu hình đường dẫn chung và bổ sung adapter tương thích state/config/history.
   Cập nhật imports/module tên mới, root discovery, CLI, tests, tài liệu. Cập nhật
   thống nhất tên khóa để mọi công cụ dùng chung **một khóa vật lý** cho mỗi bộ dữ liệu;
   không để phiên bản cũ và mới khóa hai file khác nhau.
5. Tạo lại môi trường công cụ tại đích từ package manifest đã ghi; kiểm tra import,
   Tkinter/ONNX/OpenCV và phiên bản cần thiết bằng môi trường đúng. Giữ venv gốc riêng.
   Không cài/thay thư viện trong môi trường đang chứa mốc đối chiếu để ép config khớp.
6. Chuyển bản staging theo CSV, giữ byte và mtime của ảnh/mask/overlay. Cập nhật state
   hiện hành, manifest và review CSV bằng biến đổi có schema, giữ đủ cột và thứ tự
   hàng có ý nghĩa. Đổi `filename` và các đường dẫn đồng bộ với tên artifact mới.
   Ghi SHA metadata trước/sau vào ledger; SHA ảnh phải giữ nguyên.
7. Đưa nguyên bytes bằng chứng cũ vào vị trí đích/nguồn gốc đã chốt; ghi aliases,
   config legacy và migration ledger. Không giải nén rồi sửa/repack bốn ZIP lịch sử.
   Không tự tạo lại kết quả `mask_moi_can_sua` đang thiếu, không tự phân loại ảnh.
8. Chạy các kiểm tra ở mục 8 trên staging, gồm kiểm thử tiếp tục có ngắt, phân loại
   và phục hồi chỉnh mask. Chỉ khi đạt hết mới đổi cây đang dùng sang cây đích.
9. Sau chuyển, kiểm kê/băm lại, so với ledger, mở các công cụ từ root và từ cwd khác;
   giữ cây trước chuyển cùng archive cho đến khi người dùng hoàn tất đối chiếu.
   Không xóa bản cũ, cache cũ hay snapshot trong cùng đợt chuyển này.

## 8. Điều kiện kiểm tra khi chuyển

| Kiểm tra | Tiêu chí đạt |
|---|---|
| Đủ dữ liệu | 1.297 nguồn, 812 cắt đang dùng, 485 đã loại; không gộp tệp cùng hash, không đánh lại số. Mọi dòng ánh xạ có đích đúng. |
| Toàn vẹn | SHA-256 ảnh nguồn, ảnh cắt, mask, overlay, quicklook và nội dung history/ZIP giữ nguyên. Metadata được phép đổi phải có ledger trước/sau. |
| Tên/đường dẫn | Đủ 26.551 dòng baseline hoặc hành động rebuild có bằng chứng; không trùng NFC/casefold; mọi tham chiếu hiện hành giải đúng base, không thoát root. |
| Manifest | 812 tên duy nhất, 812 hàng success; 812 trạng thái `da_duyet`/`dat` được giữ; 2.436 hash khớp, mọi artifact/quicklook tồn tại. Không mất cột tùy chọn. |
| Ảnh/mask | Đọc được ảnh; mask PNG nhị phân 0/255, kích thước và thống kê khớp. Các sai khác overlay ngoại lệ đã có trước được báo riêng, không tái tạo ảnh để che sai khác. |
| Crop state | Giữ 1.297 khóa, SHA/signature, output, trạng thái lật/xóa; báo riêng đúng 189 khác biệt vốn có. Không tái sinh hoặc xóa ảnh vì tự hòa giải state. |
| Resume GrabCut | Trên bản sao staging, legacy adapter chấp nhận đúng provenance; `--all --resume` reuse 812, attempted 0, failed 0; hash 1.624 mask/overlay không đổi. Theo dõi metadata/quicklook có thể được ghi lại. |
| Trường hợp resume xấu | Fixture nguồn/artifact bị sửa hoặc thiếu phải bị phát hiện; cấu hình thuật toán thay đổi phải bị từ chối hoặc sang output mới; subset không được làm rơi hàng cũ. |
| Resume đã phân loại | Fixture overlay nằm trong accepted/needs_revision/redo phải dùng đường dẫn manifest hiện hành, không bị ép về overlay phẳng hoặc tái tính mask đã chỉnh tay. |
| Crop tiếp tục | Fixture saved/deleted/flipped và 189 trường hợp lệch vị trí được xử lý theo chính sách đã chốt; không dùng `--force`; hash ảnh đã duyệt giữ nguyên. |
| Mask mới | Fixture riêng kiểm tra hash nguồn, mask/overlay cũ/mới, model và config; ngắt và tiếp tục không mất hàng. Không tạo bộ 317 ảnh vào dữ liệu thật. |
| Lịch sử/editor | Đủ 374 × 4 tệp, state saved, record/ZIP giữ nguyên hash; đọc được alias before/after, scribbles; thử save/rollback/recovery trên bản sao và xác minh manifest nhất quán. |
| Overlay sync | Đọc được record cũ qua alias và nhận dạng accepted; chế độ chỉ audit không thay byte. Không dùng `--apply` để tự điều chỉnh kết quả trong lúc kiểm tra di chuyển. |
| Khóa/GUI/import | Tiến trình thứ hai bị chặn trên cùng bộ dữ liệu; đóng tiến trình thì nhả khóa. Các CLI/GUI/import chạy được với tên mới và cwd khác. |
| Tests | Chạy compatibility hiện có sau cập nhật import. Viết bổ sung kiểm thử cần thiết cho adapter/history vì mã nguồn các test editor/sync cũ không còn; không tuyên bố chạy được từ `.pyc`. |
| Hoàn tác | Phục hồi vào thư mục trống, verify đủ tệp/metadata/symlink, giữ đúng 24 mục bị xóa trong worktree; `git status` khớp baseline khi loại các tài liệu chuẩn bị mới. |

Chuẩn bị hiện tại đã kiểm kê/hash/đọc archive và thử khôi phục mẫu; **chưa chạy**
GUI, batch, `--resume`, `--force`, `--repair-borders`, sync `--apply` hoặc các verifier
nghiệp vụ có ghi JSON trên dữ liệu thật. Không coi các kiểm tra dự kiến ở bảng này là đã đạt.

## 9. Hoàn tác cụ thể

Hoàn tác phải dùng snapshot đầy đủ; `git reset`, `git checkout` hoặc copy chồng lên cây
đã chuyển không thể khôi phục đúng các tệp chưa commit, tệp chưa theo dõi và các mục
đã xóa. Không xóa cây đang có trước khi giải nén, kiểm tra và giữ được một bản riêng.

Các lệnh sau **chỉ để thực hiện khi cần hoàn tác**, chưa chạy trong bước chuẩn bị.
Dùng Terminal, đóng mọi công cụ BTL trước. Các thư mục sibling dưới `CSDLDPT` cần
quyền ghi của tài khoản sử dụng; trong môi trường sandbox phải xin quyền tương ứng.

```sh
PROJECT=/Users/trithuan/Desktop/CSDLDPT/BTL
PARENT=/Users/trithuan/Desktop/CSDLDPT
BACKUP="$PROJECT/outputs/backups/pre_migration_20261017_100229"
STAMP=$(date +%Y%m%d_%H%M%S)
SAFE="$PARENT/btl_recovery_$STAMP"
STAGING="$PARENT/btl_restore_$STAMP"
QUARANTINE="$PARENT/btl_before_rollback_$STAMP"
cd "$PARENT"
df -k "$PARENT"
```

Dừng nếu dung lượng khả dụng không đủ **2 × dung lượng archive + 2 GiB**, cộng dung
lượng phụ thuộc bên ngoài nếu định sao chép chúng. Cần chỗ cho một bản archive độc lập
và cây giải nén; không dựa vào APFS clone hoặc dung lượng “có thể dọn” để tính đủ.
Nếu timestamp/path đã tồn tại, chọn timestamp khác, không ghi đè.

```sh
mkdir "$SAFE"
mkdir "$STAGING"
cp -p "$BACKUP/project_snapshot.tar" "$SAFE/"
cp -p "$BACKUP/project_snapshot.tar.sha256" "$SAFE/"
cp -p "$BACKUP/baseline_inventory.json" "$SAFE/"
cp -p "$BACKUP/baseline_sha256.txt" "$SAFE/"
cp -p "$BACKUP/baseline_xattrs.json" "$SAFE/"
cp -p "$PROJECT/docs/migration_audit/restore_extended_attributes.py" "$SAFE/"
cp -p "$PROJECT/docs/migration_audit/verify_snapshot.py" "$SAFE/"
cp -p "$PROJECT/docs/migration_audit/git_status_before.nul" "$SAFE/"
cp -p "$PROJECT/docs/migration_plan.md" "$SAFE/"
cd "$SAFE"
shasum -a 256 -c project_snapshot.tar.sha256
```

Chỉ tiếp tục nếu `shasum` báo `OK`. Đối chiếu thêm hash hiển thị ở mục 6 với
`backup_verification.json`. Nếu backup ở ngoài cây hoặc đã có trong `SAFE`, dùng vị trí
đã xác minh đó; không sao chép từ archive đang nghi hỏng.

```sh
tar -xpf "$SAFE/project_snapshot.tar" -C "$STAGING"
python3 -B "$SAFE/restore_extended_attributes.py" \
  --root "$STAGING" \
  --attributes "$SAFE/baseline_xattrs.json" \
  --inventory "$SAFE/baseline_inventory.json"
python3 -B "$SAFE/verify_snapshot.py" \
  --root "$STAGING" \
  --inventory "$SAFE/baseline_inventory.json"
```

Phải có exit code 0 và `verified: true`. Script kiểm tra đủ tập đường dẫn, kiểu,
SHA-256, mode, mtime và đích symlink; tar macOS phục hồi ACL/extended attributes.
Trên macOS, verifier còn kiểm tra SHA của từng extended attribute đã có ở mốc gốc.
Nếu chuyển sang hệ điều hành khác, không tuyên bố metadata macOS được giữ đầy đủ.
Không chạy Python trong venv từ staging để kết luận môi trường đã portable: symlink và
shebang của nó được thiết kế cho root ban đầu.

Khi cây staging đạt, giữ cây hiện tại làm phương án quay lại rồi thay root:

```sh
cd "$PARENT"
mv "$PROJECT" "$QUARANTINE"
mv "$STAGING" "$PROJECT"
python3 -B "$SAFE/verify_snapshot.py" \
  --root "$PROJECT" \
  --inventory "$SAFE/baseline_inventory.json"
```

Nếu lệnh `mv` thứ hai thất bại, đưa `QUARANTINE` trở lại `PROJECT` ngay, không xóa
thư mục nào. Sau khôi phục, root BTL có đúng cây trước chuẩn bị; `docs/` và `outputs/`
chuẩn bị không có trong snapshot nên còn ở `QUARANTINE`/`SAFE`, không mất theo root mới.

```sh
GIT_OPTIONAL_LOCKS=0 git -C "$PROJECT" status --porcelain=v1 -z --untracked-files=all > "$SAFE/git_status_restored.nul"
cmp "$SAFE/git_status_before.nul" "$SAFE/git_status_restored.nul"
"$PROJECT/.venv/bin/python" -B -c 'import sys; print(sys.version, sys.prefix)'
"$PROJECT/bo_tool_anh_576x384/.venv/bin/python" -B -c 'import sys; print(sys.version, sys.prefix)'
```

`cmp` phải khớp; tệp đang xóa vẫn đang xóa, tệp sửa/chưa theo dõi vẫn giữ byte gốc.
Nếu Python nền không còn đúng vị trí, giữ nguyên bản phục hồi, cài lại Python phù hợp
hoặc dựng venv mới từ manifest package; không sửa symlink hàng loạt hoặc chạy batch.
Nếu model ngoài root bị mất, lấy bản trong `external_dependencies/u2net.onnx` của backup
đã giữ ở cây quarantine/vị trí an toàn, kiểm tra SHA ở mục 4 trước khi đặt lại cache.
Giữ `SAFE` và `QUARANTINE` đến khi xác minh xong; không có bước tự động xóa chúng.

## 10. Điểm dừng của lần làm việc này

Hoàn tất khi có đủ kiểm kê/ánh xạ, kế hoạch, snapshot và báo cáo xác minh thực tế.
**Chưa bắt đầu chuyển dự án.** Các vấn đề sẵn có về state, resume, môi trường và kết quả
vắng mặt đã được ghi nhận, không được tự sửa trong bước chuẩn bị.
