# Báo cáo chuyển mã nguồn BTL

> Lưu ý cập nhật 23/10/2026: thư mục `tests/` đã được gỡ khỏi nhánh hiện tại. Các đường dẫn và lệnh kiểm thử bên dưới là bản ghi lịch sử tại thời điểm tài liệu được viết; log kết quả vẫn được giữ.

> Ghi nhận sau bước chuyển dữ liệu: các đường dẫn dữ liệu trong báo cáo giai đoạn này
> mô tả mốc trước khi đổi tên. Vị trí hiện tại và chuyển đổi state được ghi trong
> [data_migration.md](data_migration.md); các phụ lục kiểm kê lịch sử giữ nguyên.

Ngày thực hiện: **17/10/2026, UTC+07:00**.

Đã hoàn thành riêng giai đoạn mã nguồn: chuyển **13 tệp Python**, cập nhật import,
định vị root, các lệnh gọi và kiểm thử. Dữ liệu/kết quả vẫn ở tên và vị trí cũ.
Không chuyển môi trường Python, requirements, manifest, lịch sử chỉnh mask hoặc cache cũ.
Không chạy xử lý hàng loạt dữ liệu thật.

## Tệp đã chuyển

| Vị trí cũ | Vị trí mới |
|---|---|
| `bo_tool_anh_576x384/cat_tu_dong.py` | `tools/image_processing/auto_crop.py` |
| `bo_tool_anh_576x384/doi_ten_anh.py` | `tools/image_processing/rename_images.py` |
| `bo_tool_anh_576x384/duyet_anh.py` | `tools/image_processing/review_images.py` |
| `bo_tool_anh_576x384/tool_common.py` | `tools/image_processing/tool_common.py` |
| `reports/yeu_cau_2/check_grabcut.py` | `tools/segmentation/run_grabcut.py` |
| `reports/yeu_cau_2/chinh_mask.py` | `tools/segmentation/edit_masks.py` |
| `reports/yeu_cau_2/dong_bo_overlays.py` | `tools/segmentation/sync_overlays.py` |
| `reports/yeu_cau_2/duyet_overlays.py` | `tools/segmentation/review_overlays.py` |
| `reports/yeu_cau_2/tao_lai_mask_can_sua.py` | `tools/segmentation/regenerate_masks.py` |
| `reports/yeu_cau_2/audit_images.py` | `tools/validation/audit_images.py` |
| `reports/yeu_cau_2/verify_grabcut_results.py` | `tools/validation/verify_grabcut_results.py` |
| `reports/yeu_cau_2/verify_mask_moi_can_sua.py` | `tools/validation/verify_regenerated_masks.py` |
| `bo_tool_anh_576x384/tests/test_compatibility.py` | `tests/image_processing/test_compatibility.py` |

Không để wrapper tại các tên cũ. Các thư mục cũ vẫn tồn tại để giữ tài liệu,
requirements, môi trường Python, bytecode và kết quả. Không xóa tệp kiểm thử vốn đã
bị xóa trước giai đoạn này, không tái tạo mã nguồn từ `.pyc`.

Tệp bổ sung:

- `tools/project_paths.py`: định vị root từ vị trí của chính module; giữ các hằng
  trỏ tới `data/`, `reports/yeu_cau_2/`, `grabcut_output/` và thư mục môi trường cũ.
- `__init__.py` ở `tools/`, ba nhóm công cụ, `tests/` và hai nhóm kiểm thử để import
  được theo tên package đầy đủ.
- `tests/validation/test_source_migration.py`: kiểm thử vị trí, CLI, thuật toán,
  import và luồng kết quả/lịch sử trên dữ liệu tạm.

## Cách định vị tài nguyên

| Tài nguyên | Đường dẫn vẫn dùng |
|---|---|
| Ảnh nguồn cắt tự động | `data/anh-chua-loc/` |
| Ảnh cắt đang dùng/nguồn phân đoạn | `data/anh-da-cat-576x384/` |
| Ảnh cắt đã loại | `data/anh-da-cat-576x384-da-xoa/` |
| Crop state và CSV | `_cat_tu_dong.json`, `_cat_tu_dong.truoc-cap-nhat.json`, `bao_cao_cat.csv` trong thư mục ảnh cắt |
| Khóa cắt/duyệt | `data/anh-da-cat-576x384/.tool_anh.lock` |
| Bộ kết quả GrabCut | `reports/yeu_cau_2/grabcut_output/` |
| Khóa tạo/chỉnh/đồng bộ mask | `reports/yeu_cau_2/grabcut_output/.run.lock` |
| Manifest, hồ sơ chỉnh sửa | `manifest.csv`, `manual_edits/`, `overlay_sync_backups/` trong bộ kết quả cũ |
| Các thư mục phân loại overlay | `overlays/đạt/`, `overlays/cần sửa/`, `overlays/làm lại/` |
| Snapshot kiểm kê và kết quả audit | `reports/yeu_cau_2/` |
| Đầu ra mask tạo lại mặc định | `reports/yeu_cau_2/mask_moi_can_sua/`, hiện chưa tồn tại |
| Mô hình | `~/.cache/animal-crop/u2net.onnx` |

Import nội bộ dùng `tools.image_processing.*` hoặc `tools.segmentation.*`.
Các script có bootstrap cho phép gọi trực tiếp bằng đường dẫn tuyệt đối từ cwd khác;
giá trị mặc định vẫn lấy từ root BTL. Đường dẫn người dùng truyền qua tham số tương
đối vẫn được hiểu theo cwd như trước.

`audit_images.py` được đưa vào `main()` để import không đọc toàn bộ ảnh hoặc tạo
báo cáo. Vòng kiểm kê, chọn mẫu và dựng bảng ảnh giữ nguyên cách tính.
Ba công cụ validation có parser `--help` và tham số đường dẫn, nên có thể kiểm tra
hoặc chạy với bản sao/thư mục tạm. Chúng vẫn ghi kết quả khi được thực sự thực thi;
`--help` chỉ hiện hướng dẫn.

## Lệnh chạy mới

Các lệnh trong bảng dùng từ **thư mục gốc BTL**. Thêm `--help` để xem tham số;
các lệnh không có `--help` có thể ghi state/kết quả hoặc mở GUI theo chức năng vốn có.
Trong giai đoạn chuyển mã này chỉ chạy `--help` với vị trí thật và xử lý ảnh giả lập
trong thư mục tạm.

| Chức năng | Lệnh mới |
|---|---|
| Cắt ảnh | `python3 tools/image_processing/auto_crop.py` |
| Xem trước đổi tên ảnh | `python3 tools/image_processing/rename_images.py` |
| Duyệt ảnh cắt | `python3 tools/image_processing/review_images.py` |
| Tạo mask GrabCut | `.venv/bin/python tools/segmentation/run_grabcut.py` |
| Duyệt overlay | `.venv/bin/python tools/segmentation/review_overlays.py` |
| Chỉnh mask | `.venv/bin/python tools/segmentation/edit_masks.py` |
| Audit đồng bộ overlay | `.venv/bin/python tools/segmentation/sync_overlays.py` |
| Tạo lại mask | `bo_tool_anh_576x384/.venv/bin/python tools/segmentation/regenerate_masks.py` |
| Kiểm kê ảnh và tạo bảng mẫu | `.venv/bin/python tools/validation/audit_images.py` |
| Xác minh kết quả GrabCut lịch sử | `.venv/bin/python tools/validation/verify_grabcut_results.py` |
| Xác minh bộ mask tạo lại | `.venv/bin/python tools/validation/verify_regenerated_masks.py` |

`auto_crop.py` và `review_images.py` vẫn tự khởi động môi trường khi cần.
`rename_images.py` chỉ cần thư viện chuẩn.
Môi trường và `requirements.txt` tiếp tục ở `bo_tool_anh_576x384/`;
`--setup` vẫn cài vào môi trường ở vị trí đó và **không được chạy trong lần chuyển này**.
Không tạo `.venv` mới dưới `tools/`.

Ví dụ dạng module từ root:

```sh
.venv/bin/python -m tools.segmentation.run_grabcut --help
.venv/bin/python -m tools.segmentation.edit_masks --help
.venv/bin/python -m tools.validation.audit_images --help
```

Từ cwd bất kỳ, dùng đường dẫn tuyệt đối tới Python và script:

```sh
/Users/trithuan/Desktop/CSDLDPT/BTL/.venv/bin/python \
  /Users/trithuan/Desktop/CSDLDPT/BTL/tools/segmentation/run_grabcut.py --help
```

Validation có thể nhận đường dẫn riêng:

```sh
.venv/bin/python tools/validation/audit_images.py --help
.venv/bin/python tools/validation/verify_grabcut_results.py --help
.venv/bin/python tools/validation/verify_regenerated_masks.py --help
```

Lệnh đầu hỗ trợ `--input-dir`, `--output-dir`; lệnh thứ hai hỗ trợ `--source-dir`,
`--output-dir`, `--inventory`; lệnh cuối hỗ trợ `--output-dir`, `--previous-dir`,
`--inventory`, `--project-root`. Mặc định đều trỏ về dữ liệu/snapshot cũ.

## Kiểm tra đã thực hiện

**23 kiểm thử đạt: 16 compatibility hiện có và 7 kiểm thử chuyển mã bổ sung.**

```sh
PYTHONDONTWRITEBYTECODE=1 bo_tool_anh_576x384/.venv/bin/python -B \
  -m unittest discover -s tests/image_processing -v

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B \
  -m unittest discover -s tests/validation -v
```

Dùng hai lệnh vì hai môi trường có bộ thư viện khác nhau; không gộp hoặc cài thêm
thư viện vào môi trường trong giai đoạn này.

Các kiểm tra bổ sung bao gồm:

- 11 entry point × hai cách gọi: `--help` trực tiếp từ cwd tạm và dạng module từ root,
  tổng cộng **22 lần gọi thành công**. Không mở cửa sổ Tkinter.
- Kiểm tra root, đầu vào, đầu ra, hàng đợi và vị trí snapshot mặc định.
- Import auditor không quét ảnh hoặc ghi báo cáo.
- Đối chiếu AST các hàm/lớp xử lý với bản mã trước chuyển: giữ nguyên thuật toán,
  giao thức state, khóa, resume, lưu/rollback/history. Chỉ chuẩn hóa chuỗi hướng dẫn
  đã đổi tên khi so sánh. Kiểm kê ảnh được đối chiếu riêng sau khi bọc vào `main()`.
- Tạo GrabCut trên một ảnh giả lập 576 × 384; chạy resume cùng cấu hình: reuse một,
  attempted bằng không, mask/overlay không đổi; verifier xác minh được bộ kết quả tạm.
  Artifact bị sửa trong fixture bị phát hiện.
- Editor trên fixture lưu đủ bốn tệp history và `state=saved`; sync nhận diện lịch sử
  ở tên thư mục tiếng Việt cũ; audit sync không thay đổi byte. Duyệt/undo overlay đạt.
- Auditor ghi kết quả vào đúng output tạm được chỉ định.
- Kiểm tra cú pháp/whitespace của toàn bộ mã mới và xác nhận đủ 13 đường dẫn mới,
  13 đường dẫn mã cũ không còn.
- Đối chiếu SHA-256, size, mtime, mode và symlink của **20.716 tệp/symlink**:
  2.599 trong dữ liệu, 3.257 trong báo cáo/kết quả và 14.860 trong hai môi trường,
  gồm state và cache, với mốc ngay trước chuyển. Chỉ hai README trong `reports/` được
  sửa nội dung hướng dẫn có chủ đích; không sửa artifact nghiệp vụ.

Kết quả máy đọc được: [test_results.json](source_migration_audit/test_results.json),
[protected_files_verification.json](source_migration_audit/protected_files_verification.json),
[source_changes.json](source_migration_audit/source_changes.json).

## Vấn đề còn lại

Không còn lỗi kiểm thử do việc chuyển mã. Các vấn đề vốn có được giữ nguyên:

1. `--resume` trên **kết quả thật cũ** vẫn có thể bị từ chối vì `run_config.json`
   so sánh toàn bộ cấu hình, SHA mã và phiên bản thư viện. Hash đã khác ngay trước
   chuyển và nay mã có import/đường dẫn mới. Không sửa config/manifest hoặc nới kiểm tra
   để ép chạy tiếp. Kiểm thử resume đạt với bộ kết quả tạm tạo bằng mã hiện tại.
2. Crop-state vẫn có **189 mục lệch vị trí thực tế**; không chỉnh state, không tái cắt
   và không tự hòa giải bằng cách di chuyển ảnh.
3. Bộ kết quả `mask_moi_can_sua/` và hàng đợi `grabcut_output/overlays/cần sửa/`
   hiện không có. Các lệnh regenerate/editor cần hàng đợi phù hợp hoặc đường dẫn
   đầu vào khác khi sử dụng sau này. Không tái tạo 317 kết quả từ mô tả lịch sử.
4. `verify_grabcut_results.py` là verifier của lần tạo mask gốc, vẫn yêu cầu
   `review_status=chua_duyet` và overlay khớp quy tắc gốc. Dữ liệu hiện hành có
   `da_duyet/dat` và một số overlay ngoại lệ đã được ghi trước đây; verifier lịch sử
   không phải kiểm tra chung cho mọi trạng thái sau chỉnh sửa. Chưa chạy verifier này
   trên dữ liệu thật và không sửa điều kiện kiểm chứng trong đợt chuyển mã.
5. Môi trường gốc có OpenCV nhưng thiếu `certifi`; môi trường công cụ có `certifi`
   nhưng thiếu OpenCV. Dùng đúng môi trường theo bảng lệnh. Chưa mở GUI tương tác,
   chưa chạy ONNX với mô hình thật và chưa kiểm thử trên Windows thực.

## Bản sao lưu và điểm dừng

Đã băm lại archive nguyên trạng trước khi chuyển, khớp SHA-256:

```text
outputs/backups/pre_migration_20261017_100229/project_snapshot.tar
2917b8e027a090fdb7564ac71336e4a82e7ce6e1dc9e038658a2c468e37bdbf7
```

Có thêm [source_before.tar](source_migration_audit/source_before.tar), gồm 13 tệp mã
và các hướng dẫn/cấu hình cần giữ trước bước này; đã đọc/băm từng tệp từ archive.
[source_before.sha256](source_migration_audit/source_before.sha256) xác minh archive nhỏ.
Bản trước sửa của báo cáo thuộc tính ở `source_migration_audit/documentation_before/`.
Ánh xạ thực tế: [source_mapping.json](source_migration_audit/source_mapping.json).

Nếu chỉ hoàn tác mã: đóng công cụ, xác minh `source_before.tar`, giải nén vào thư mục
trống, đối chiếu với `source_changes.json` rồi chép lại đúng các đường dẫn mã/hướng dẫn
cũ. Giữ mã mới trong một bản riêng trước khi bỏ khỏi `tools/`/`tests/`; nếu có chỉnh sửa
sau giai đoạn này thì không ghi đè chúng. Archive nhỏ không chứa ảnh, kết quả hoặc venv.
Quy trình khôi phục toàn dự án vẫn nằm trong [migration_plan.md](migration_plan.md).

**Dừng sau bước mã nguồn.** Chưa thực hiện chuyển/đổi tên dữ liệu, kết quả, tài liệu,
môi trường hoặc triển khai adapter cho schema resume/history mới trong cây đích cuối.
