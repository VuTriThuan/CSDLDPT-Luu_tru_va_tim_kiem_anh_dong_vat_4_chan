# Báo cáo đổi tên thư mục dữ liệu

> Lưu ý cập nhật 23/10/2026: thư mục `tests/` đã được gỡ khỏi nhánh hiện tại. Các đường dẫn và lệnh kiểm thử bên dưới là bản ghi lịch sử tại thời điểm tài liệu được viết; log kết quả vẫn được giữ.

Ngày thực hiện: **17/10/2026, UTC+07:00**. Chỉ đổi tên ba thư mục ảnh và cập nhật
đường dẫn cần thiết. Không đổi tên từng ảnh, không cắt/lật/ghi lại ảnh của bộ thật,
không chuyển bộ kết quả phân đoạn hoặc hai môi trường Python.

## Vị trí mới và đối chiếu bước 1

| Thư mục trước chuyển | Thư mục hiện tại | Số ảnh |
|---|---|---:|
| `data/anh-chua-loc/` | [data/source_images/](../data/source_images/) | 1.297 |
| `data/anh-da-cat-576x384/` | [data/cropped_images_576x384/](../data/cropped_images_576x384/) | 812 |
| `data/anh-da-cat-576x384-da-xoa/` | [data/rejected_crops/](../data/rejected_crops/) | 485 |
| **Tổng** | | **2.594** |

Đã đối chiếu đủ tập tên và SHA-256 từng ảnh với
[baseline_inventory.json của bước 1](migration_audit/baseline_inventory.json), cả
trước và sau chuyển. Tên, nội dung, size, mtime và mode của mọi ảnh giữ nguyên.
Không chuẩn hóa chữ hoa/gạch nối hoặc đánh lại số của basename trong bước này.
Không tạo symlink hoặc bản ảnh trùng tại ba tên thư mục cũ.
Liên kết tài liệu/mã/ảnh hiện tại được kiểm tra trong
[link_verification.json](data_migration_audit/link_verification.json); các kết quả
phân đoạn được đối chiếu riêng tại
[processing_results_verification.json](data_migration_audit/processing_results_verification.json).

Chi tiết từng ảnh cũ/mới/hash:
[image_inventory.json](data_migration_audit/image_inventory.json).
Kết quả đối chiếu:
[data_verification.json](data_migration_audit/data_verification.json).

## Trạng thái đã chuyển đổi

**Chỉ chuyển đổi nội dung một tệp:**
`data/cropped_images_576x384/_cat_tu_dong.json`.

| Trường | Giá trị cũ | Giá trị hiện tại |
|---|---|---|
| `source` | `/Users/trithuan/Desktop/CSDLDPT/BTL/data/anh-chua-loc` | `/Users/trithuan/Desktop/CSDLDPT/BTL/data/source_images` |
| `source_relative` | `../anh-chua-loc` | `../source_images` |

Giữ `version=1` và nguyên **1.297 bản ghi `images`**, gồm tên nguồn/đầu ra,
signature, checksum, bbox, config, cảnh báo, số lần lật, thời điểm và trạng thái.
Vẫn có 665 bản ghi `saved`, 632 `deleted`; không sửa 189 khác biệt có sẵn giữa
trạng thái và vị trí vật lý.

Các tệp khác:

- `_cat_tu_dong.truoc-cap-nhat.json` đi cùng thư mục sang vị trí mới, **không sửa byte**.
  Nó vẫn là snapshot trước cập nhật, gồm 1.300 bản ghi/tên lịch sử.
- `bao_cao_cat.csv` đi cùng thư mục, **không sửa byte**: các cột chứa basename và
  trạng thái, không chứa đường dẫn thư mục cần thay.
- `.tool_anh.lock` đi cùng thư mục, không đổi tên hoặc tạo khóa song song.
- Manifest, `run_config.json`, snapshot, log, record chỉnh mask và ZIP trong
  `reports/yeu_cau_2/` giữ nguyên byte/vị trí. Đường dẫn cũ bên trong bằng chứng
  lịch sử không được thay hàng loạt.

Đã băm và đọc lại từ bản sao lưu **414 tệp trạng thái/phụ trợ** ngay trước chuyển.
Sau chuyển, **413 tệp không chuyển đổi khớp SHA-256**; tệp hiện hành chỉ khác hai
trường nêu trên. Danh sách từng tệp, hash trước/sau và trường đã đổi:
[state_conversions.json](data_migration_audit/state_conversions.json).

## Mã và tài liệu

`tools/project_paths.py` có các vị trí mới và bộ phân giải alias có phạm vi: chỉ
đổi tiền tố thư mục dữ liệu cũ trong đúng root dự án/bản sao được chỉ định.
Không thay chuỗi tùy ý ở đường dẫn ngoài dự án.

- Công cụ cắt dùng `source_images/`, đầu ra mặc định là thư mục anh em
  `cropped_images_576x384/`. `load_state()` nhận được `source_relative` cũ hoặc
  đường dẫn tuyệt đối cũ cùng dự án; vẫn từ chối nguồn không liên quan. Đọc state
  không ghi tệp; khi công cụ xử lý bản sao, state được ghi portable như trước.
- Công cụ đổi tên dùng đủ ba thư mục mới. Xem trước vẫn không ghi; nếu người dùng
  chủ động thực hiện đổi tên sau này, state được ghi với nguồn/đường dẫn tương đối
  hiện tại. Trong lần chuyển này chỉ chạy apply trên bản sao nhỏ.
- Công cụ duyệt chuyển ảnh từ thư mục mặc định vào `rejected_crops/`.
  Thư mục tùy chọn khác vẫn dùng hậu tố `-da-xoa` như trước. Các thao tác lật,
  commit, rollback và undo giữ cách xử lý ảnh cũ.
- Mặc định nguồn của GrabCut, tạo lại mask và kiểm kê ảnh trỏ sang thư mục cắt mới.
  Verifier mask tạo lại có thể phân giải khóa đường dẫn cũ trong snapshot bằng
  alias, giữ nguyên tệp snapshot.

Đã cập nhật README, hướng dẫn và các liên kết ảnh trong hai báo cáo. Ngoài đổi
đường dẫn, không đổi phân tích/số liệu của các báo cáo. Các hồ sơ giai đoạn trước
được thêm ghi chú rằng chúng mô tả mốc lịch sử; phụ lục đã băm giữ nguyên.

Chạy từ root BTL như trước, tên script không đổi:

```sh
python3 tools/image_processing/auto_crop.py --help
python3 tools/image_processing/rename_images.py --help
python3 tools/image_processing/review_images.py --help
```

## Kiểm tra trên bản sao nhỏ

**30 kiểm thử đạt:** 16 compatibility, 7 kiểm thử dữ liệu bổ sung và 7 kiểm thử
chuyển mã/validation. Các lệnh chạy:

```sh
PYTHONDONTWRITEBYTECODE=1 bo_tool_anh_576x384/.venv/bin/python -B -m unittest discover -s tests/image_processing -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests/validation -v
```

Kiểm thử dữ liệu dùng các tệp được sao chép vào thư mục tạm, gồm đủ bốn trường hợp:
saved ở thư mục đang dùng, deleted ở thư mục bị loại, deleted nhưng đang dùng và
saved nhưng đã loại. Không chạy công cụ xử lý trên ba thư mục thật.

- State có `../anh-chua-loc` hoặc đường dẫn tuyệt đối cũ cùng bản sao được đọc lại;
  nguồn khác vẫn bị từ chối.
- Chạy tiếp trên bốn bản ghi không gọi mô hình, không cắt lại ảnh, không thay quyết
  định xóa/lật hoặc tự sửa các lệch trạng thái. Đầu ra mặc định đi đúng thư mục mới.
- Lật → loại → undo → undo khôi phục nguyên byte; ảnh loại đi vào `rejected_crops/`.
- Preview đổi tên không ghi. Apply đổi tên trên bản sao giữ các hash ảnh, cập nhật
  state portable; công cụ cắt sau đó nhận lại tiến độ, không tái cắt.
- Thực sự chạy U²-Net trên **một ảnh sao chép** bằng mô hình cục bộ, tạo JPEG
  576 × 384 đúng vị trí mới; chạy lại giữ hash kết quả. Chặn tải mạng trong kiểm thử.
- Các kiểm tra AST tiếp tục bảo vệ thuật toán xử lý ảnh/lưu history; thay đổi được
  giới hạn ở định vị dữ liệu, đọc state legacy và đường dẫn nhận ảnh bị loại.

Log và kết quả máy đọc được:
[test_results.json](data_migration_audit/test_results.json),
[image_tests.log](data_migration_audit/image_tests.log),
[validation_tests.log](data_migration_audit/validation_tests.log).

## Giới hạn trạng thái cũ đã được ghi nhận

1. **189 lệch trạng thái/vị trí** vẫn giữ nguyên. Không dùng migration để quyết định
   lại ảnh nào được giữ/loại. Công cụ cắt hiện giữ các bản ghi saved/deleted khi
   nguồn/config khớp, nên kiểm thử chứng minh các trường hợp này không tự bị cắt lại.
2. Snapshot `_cat_tu_dong.truoc-cap-nhat.json` có 1.300 bản ghi/tên cũ, không tương
   đương state hiện hành 1.297 bản ghi. Không tự dùng nó làm state hiện hành hoặc
   đổi tên các khóa để ép khớp; muốn khôi phục snapshot đó phải dùng bộ dữ liệu
   tương ứng trong backup.
3. **GrabCut `--resume` với bộ kết quả thật cũ vẫn có thể từ chối.** Config gốc còn
   đường dẫn cũ, hash mã và phiên bản thư viện cũ; hash/phiên bản đã lệch từ trước
   bước này. Không sửa config để ép qua ràng buộc. Bộ reader dùng nguồn mặc định
   mới, nhưng adapter tương thích config resume của phân đoạn là công việc riêng.
4. Verifier lịch sử GrabCut đối chiếu cả state/metadata nguồn ở mốc cũ và yêu cầu
   `chua_duyet`. JSON state hiện hành đã đổi đường dẫn, trạng thái hiện tại là
   `da_duyet/dat`, nên không tuyên bố verifier đó xác minh được nguyên snapshot cũ.
   Bằng chứng ảnh không đổi ở bước này là đối chiếu từng ảnh với kiểm kê bước 1.
5. Bộ mask tạo lại/hàng đợi cần sửa vẫn vắng mặt như trước; alias chỉ giúp giải
   đường dẫn lịch sử, không tái tạo kết quả hoặc thay giá trị hash snapshot.

## Sao lưu và hoàn tác riêng bước dữ liệu

Bản sao lưu đầy đủ nguyên trạng bước 1 vẫn ở
`outputs/backups/pre_migration_20261017_100229/project_snapshot.tar`.
Trước đổi dữ liệu đã băm lại archive và xác nhận đúng SHA-256 đã ghi ở bước 1.

Có thêm snapshot ngay trước bước này chứa mã, tests, docs và toàn bộ state/phụ trợ
hiện tại; **không chứa thêm bản sao ảnh**, vì ảnh được bảo vệ bởi archive đầy đủ và
kiểm kê SHA-256. Đường dẫn, SHA archive và phạm vi:
[preflight.json](data_migration_audit/preflight.json).
Snapshot chứa các bản gốc của cả state hiện hành lẫn state lịch sử trước chuyển.

Nếu cần hoàn tác riêng bước này, đóng tất cả công cụ trước và giữ một bản ngoài
cây đang dùng của snapshot cùng kiểm kê. Chỉ thực hiện khi không có thay đổi mới
hoặc đã sao lưu riêng các thay đổi phát sinh:

1. Kiểm tra SHA-256 snapshot theo `preflight.json` và tệp `.tar.sha256` cạnh archive.
   Giải nén vào thư mục trống, đọc/đối chiếu state và tài liệu trước khi thay cây.
2. Đổi ba thư mục dữ liệu mới trở lại tên cũ theo
   [directory_mapping.json](data_migration_audit/directory_mapping.json), không đổi
   tên từng ảnh; dừng nếu đích đã tồn tại.
3. Khôi phục `_cat_tu_dong.json` gốc từ snapshot vào thư mục cắt cũ. Khôi phục mã,
   tests và tài liệu trước bước này từ cây giải nén; giữ phiên bản hiện tại riêng
   trước khi chép lại. Không ghi đè chỉnh sửa phát sinh sau bước này.
4. Đối chiếu đủ 2.594 ảnh với `image_inventory.json` theo các đường dẫn cũ; đối
   chiếu state theo `state_before.json`. Không chạy batch để kiểm tra khôi phục.

Quy trình khôi phục toàn dự án nằm trong [migration_plan.md](migration_plan.md).
**Dừng sau đổi tên thư mục dữ liệu.** Chưa chuyển `reports/yeu_cau_2/`, mask,
overlay, quicklook, manifest, lịch sử hoặc môi trường Python sang cấu trúc đích khác.
