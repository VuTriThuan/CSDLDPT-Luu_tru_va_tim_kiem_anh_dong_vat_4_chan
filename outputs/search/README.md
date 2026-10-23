# Kết quả tìm kiếm và bằng chứng cuối

Nhánh tinh gọn giữ tám lượt truy vấn dùng trong báo cáo. Batch dữ liệu thử, kiểm tra di chuyển, bản xuất trùng và kết quả trung gian đã được gỡ. Các số 62/62 artifact hoặc số kiểm thử đạt là kết quả lịch sử trước khi dọn, không phải kiểm kê checkout hiện tại.

## Các lượt được giữ

| Minh họa | Kết quả |
|---|---|
| Ngựa, đầu vào của phân tích bốn nhóm | [20261023T005527_002900Z_39619666](20261023T005527_002900Z_39619666/result.json) |
| Bò, đầu vào của phân tích bốn nhóm | [20261023T012837_426171Z_19029e33](20261023T012837_426171Z_19029e33/result.json) |
| Chó, đầu vào của phân tích bốn nhóm | [20261023T013510_179045Z_e5ee7591](20261023T013510_179045Z_e5ee7591/result.json) |
| Cùng hash và tùy chọn include-self | [20261023T022920_325538Z_bb862978](20261023T022920_325538Z_bb862978/result.json) |
| Mask lạc đà trước/sau sửa | [Trước](20261023T014542_632499Z_e8f7fc8d/result.json), [sau](20261023T014716_706322Z_da9a4488/result.json) |
| Hai ví dụ mask chó | [0355](20261023T014953_653022Z_e870cbcc/result.json), [0470](20261023T014901_329947Z_fdf91295/result.json) |

Mỗi thư mục giữ nguyên ảnh truy vấn, mask, vector, top 5 và JSON đã lưu. Đường dẫn tuyệt đối trong JSON là thông tin nguồn lịch sử; ảnh truy vấn đóng gói nằm trong chính thư mục lượt chạy.

## Phân tích và kiểm chứng được giữ

- [Phân tích chín cấu hình bốn nhóm cuối](diagnostics/group_analysis/20261023T133848_225643Z_20473d/README.md): ngựa/bò/chó, 135 dòng top 5 và các giới hạn.
- [Phân tích độ nhạy mask](diagnostics/mask_audit/README.md).
- [Tổng kết kiểm chứng phép xếp hạng](diagnostics/search_audit/README.md) và JSON bằng chứng cuối.
- [Kiểm chứng hai batch trước khi gỡ dữ liệu thử](verification/completion_checks.json).
- [Tổng kết bàn giao trước khi dọn](verification/delivery_checks.json).
- [Kết quả kiểm tra GUI lịch sử](verification/gui_smoke.json).
- [Log audit cuối](verification/ranking_audit_final.log).

Chưa có tập truy vấn độc lập và chấm relevance đầy đủ để công bố P@5 thị giác. Các quan sát và thay đổi thứ hạng trong phân tích nhóm không chứng minh chất lượng truy hồi tăng.

## Tạo kết quả mới

Chạy CLI/GUI theo [hướng dẫn tìm kiếm](../../docs/reports/search_implementation.md). Tạo manifest mới từ [mẫu](../../tools/search/query_manifest_template.csv), điền các ảnh thật rồi chạy `batch`; chấm relevance 0/1 trước khi chạy `score`. Không tự suy relevance từ nhãn hoặc khoảng cách.
