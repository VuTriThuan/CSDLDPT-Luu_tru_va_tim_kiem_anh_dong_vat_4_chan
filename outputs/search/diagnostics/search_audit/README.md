# Kiểm tra độc lập phép tìm kiếm B400

Phạm vi: tính toán vector, scaler đã đóng băng, bình phương khoảng cách L2, xử lý gốc/lật, và độ nhạy với mask. Không dùng nhãn để quyết định mức liên quan hay công bố độ chính xác. Các tệp yêu cầu 1–3 được đọc nguyên trạng.

Chạy lại từ root repo:

```sh
.venv/bin/python -B outputs/search/diagnostics/search_audit/audit.py
```

Chi tiết từng phép đo nằm trong `evidence.json`.

## Những gì đã xác minh

- 22/22 lượt truy vấn ngày 23/10/2026 tái tạo chính xác tên kết quả, khoảng cách và lựa chọn gốc/lật từ SQLite cùng `vectors.npz` đã lưu.
- 44/44 vector gốc/lật tái tạo chính xác khi biến đổi lại raw vector bằng scaler frozen. Với 4 ca kiểm tra sâu, trích xuất lại từ `query_rgb.png` và `mask.png` cũng khớp chính xác vector gốc đã lưu.
- 812 vector trong SQLite có norm mỗi nhóm gần 0.5; đây là trọng số năng lượng 25% cho màu, texture, hình dạng và bố cục theo cấu hình đã đóng băng.
- `tools/search/index.py:58` tính đúng tổng bình phương sai khác, lấy min(gốc,lật) cho từng ứng viên, loại self match theo SHA-256, và gộp trùng sau khi xếp hạng.
- `tools/features/b400.py:395` áp dụng đúng chuẩn hóa histogram căn bậc hai, zscore liên tục, missing=0, L2 từng subblock và nhóm. Không thấy lỗi refit scaler hoặc thêm trọng số ở bước tìm kiếm.

## Bằng chứng mask thay đổi kết quả

Vì các ca dưới đây có cùng SHA-256 ảnh nguồn trong corpus, phép đo drift tách được ảnh hưởng của mask. Mask corpus là mốc so sánh kỹ thuật; đây không phải khẳng định mask corpus luôn đúng về thị giác.

| Ảnh / lượt | IoU mask với mask corpus | d² vector query so với vector cùng ảnh trong corpus | Top 1 d² |
| --- | ---: | ---: | ---: |
| Camelus_bactrianus_0057 / 08:45:42 (GMT+7) | 0.4252 | 0.8988 | 0.4454 |
| Cùng ảnh / 08:47:16 (GMT+7) | 0.9182 | 0.1600 | 0.2177 |
| Canis_familiaris_0355 / 08:49:53 (GMT+7) | 0.6093 | 0.4621 | 0.3242 |
| Canis_familiaris_0470 / 08:49:01 (GMT+7) | 1.0000 | 0.0000 | 0.3433 |

Với Camelus_0057, tỉ lệ foreground đổi từ 50.3% xuống 22.1%, vector dịch chuyển rõ rệt và danh sách top 5 thay đổi. Điều này phù hợp việc mask quyết định silhouette, vùng màu, texture và bố cục được đo. Việc một ảnh khác nhãn xuất hiện không tự chứng minh kết quả kém; cần xem trực tiếp dáng, màu và họa tiết.

## Giới hạn của phép đo hình dạng và cân bằng các nhóm

- `tools/features/b400.py:101` lấy bbox của tất cả foreground. Một mảng nền bị giữ ở xa có thể mở rộng bbox, đổi tỉ lệ và vị trí toàn bộ con vật trên canvas, làm thay đổi nhiều nhóm đặc trưng cùng lúc.
- S2e đo đường kính hull và bề rộng chiếu vuông góc trên mask nguồn theo đúng công thức đã quy định; không phát hiện lỗi chuyển sang PCA hay đo nhầm ảnh đã resize. S2e vẫn nhạy với điểm foreground ở xa.
- S3 (`tools/features/b400.py:68`) là 48 bit occupancy trên lưới 6×8, ngưỡng nghiêm ngặt >15%. Nó mất chi tiết trong mỗi ô, chưa bất biến với tư thế/xoay, và có thể nhảy giá trị khi occupancy qua ngưỡng. Đo thực tế với Dog0355: giãn mask 1 pixel đổi 2,813 pixel, IoU với mask ban đầu 0.9423, đổi 1 bit S3 và làm d² vector tăng 0.03544; riêng S3 đóng 0.03022. Đây là độ nhạy của biểu diễn frozen, không phải sai số tính L2.
- Các profile hình dạng ở cột trống và ô bố cục trống được gán missing=0 sau chuẩn hóa. Đây là quy tắc fixed-vector đã quy định; không có tái cân bằng validity theo từng cặp. Corpus có S4 hợp lệ từ 28–64 chiều và P từ 64–128 chiều.
- Norm nhóm bằng nhau không bảo đảm độ nhạy thị giác bằng nhau. Với query Dog0355, trung vị d² tới 812 ứng viên ở từng nhóm (dùng bản gốc) là màu 0.07252, texture 0.30777, hình dạng 0.47542, bố cục 0.12600. Histogram không âm có phân bố góc khác nhóm đã zscore có giá trị âm. Vì vậy preset hiện tại thường phân biệt mạnh bằng silhouette/texture hơn mức người dùng suy ra từ con số 25%.

## Hướng xử lý trong phạm vi hiện tại

Ưu tiên sửa vùng foreground trước khi tìm kiếm; xem overlay cả con vật và nền, chọn bbox sát nhưng đủ tai/chân/đuôi, rồi dùng nét giữ/loại nếu cần. Các ví dụ lấy từ corpus nên cho phép nạp lại đúng mask đã dùng khi tạo index để tránh so sánh hai lần phân đoạn khác nhau ngoài ý muốn. Trạng thái mask và đóng góp nhóm nên hiển thị rõ trong kết quả. Nếu muốn thay đổi cân bằng dáng/màu/họa tiết, cần coi đó là một chế độ truy hồi khác có đánh giá thị giác riêng; bằng chứng ở đây không chứng minh bộ trọng số mới tốt hơn.
