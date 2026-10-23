# Đầu ra yêu cầu 4

Tất cả truy vấn và xuất kết quả nằm riêng ở đây; dữ liệu yêu cầu 1–3 chỉ đọc.
Hướng dẫn, kiến trúc, công thức và giới hạn:
[báo cáo yêu cầu 4](../../docs/reports/search_implementation.md).

- [Lượt CLI đầu tiên](functional_checks/20261022T153956_195301Z_7ea40f22/result.json): ảnh CSDL, loại tự khớp; có ảnh/mask/overlay, preview, vector gốc/lật và top 5.
- [Manifest chức năng](functional_queries.csv): bốn query bằng ảnh CSDL/ảnh resize dẫn xuất; không phải tập đánh giá độc lập.
- [Batch thực tế](functional_checks/batch_20261022T154444_232219Z_9268a9/batch.json): 4/4 thành công, dùng một run/scaler.
- [Bảng chấm](functional_checks/batch_20261022T154444_232219Z_9268a9/judgments.csv): 20 kết quả, relevance còn trống.
- [Báo cáo batch](functional_checks/batch_20261022T154444_232219Z_9268a9/evaluation.json): P@5 thị giác và cùng nhãn đều null; purpose=functional_check bị loại khỏi đánh giá độc lập.
- [GUI thực tế](20261022T154301_028176Z_c4760f84/result.json) và [bản xuất](gui_exports/20261022T154301_028176Z_c4760f84/result.json): dùng ảnh CSDL, không đánh giá chất lượng.
- [Kiểm thử tìm kiếm](verification/tests_search.log), [B400](verification/regression_features.log), [validation](verification/regression_validation.log), [công cụ ảnh](verification/regression_image_processing.log): 35 + 30 + 21 + 24 = 110 kiểm thử đạt.
- [GUI smoke](verification/gui_smoke.json): 16 nhóm kiểm tra tự động trên cửa sổ Tk thật, gồm chọn ảnh tự tạo mask, tô sửa, tùy chọn hiện ảnh trùng truy vấn và tìm top 5; chưa duyệt GUI thủ công.
- [SHA-256 trước triển khai](verification/protected_before.json), [kiểm chứng bàn giao](verification/delivery_checks.json): 6.118 tệp được bảo vệ và các bộ artifact thực tế.

Thư mục `functional_inputs/` chỉ chứa ảnh/mask resize được tạo riêng để kiểm tra
kích thước 864×576. Không đưa các ảnh này vào tập truy vấn độc lập. Hash theo bytes
nên ảnh resize không tự bị loại như ảnh nguồn có hash khác.

Không có điểm độ chính xác truy hồi từ dữ liệu giả lập hoặc relevance tự gán.
Fixture có đáp án biết trước chỉ dùng trong unit test tạm thời.

Kiểm tra bổ sung 23/10: [phân tích nguyên nhân](../../docs/reports/search_quality_audit.md),
[bằng chứng xếp hạng](diagnostics/search_audit/README.md),
[ảnh so sánh mask và morphology](diagnostics/mask_audit/README.md).
Kiểm thử sau sửa: [48 tìm kiếm/chẩn đoán](verification/tests_search_quality_audit.log),
[30 B400](verification/regression_features_quality_audit.log). Các thí nghiệm này
giải thích độ nhạy của pipeline, không thay thế chấm tương đồng thị giác.


Bổ sung hoàn thiện kiểm thử/đánh giá yêu cầu 4 ngày 23/10:

- [Audit chính sách từng lượt](diagnostics/search_audit/README.md): 50/50 artifact trước thí nghiệm mới, 62/62 ở lần cuối tính cả batch/bản sao, 0 không khớp. Bằng chứng cũ giữ nguyên.
- [Thí nghiệm bốn nhóm](diagnostics/group_analysis/20261023T133848_225643Z_20473d/README.md): 9 cấu hình trên cùng vector ngựa/bò/chó, 135 dòng Top 5, hạng/delta của hợp ứng viên, 12 cặp quan sát thị giác thăm dò, mask và ảnh đối chiếu. Không có kết luận cải thiện relevance.
- [Kiểm chứng batch di chuyển](verification/completion_checks.json): batch cũ và mới đều chấm tại bản sao, khớp tổng hợp, nguồn và hồ sơ sao chép nguyên bytes.
- [58 kiểm thử tìm kiếm/phân tích](verification/tests_search_completion.log), [30 hồi quy B400](verification/regression_features_completion.log), [SHA-256 trước sửa](verification/completion_before.json): 5.989 tệp bảo vệ không thay đổi.
- [Cách chấm sau clone](../../docs/reports/search_implementation.md#chấm-batch-sau-khi-clone-hoặc-di-chuyển): giữ toàn bộ batch, chỉ sửa relevance/notes; không cần đường dẫn máy cũ hoặc extract lại.
