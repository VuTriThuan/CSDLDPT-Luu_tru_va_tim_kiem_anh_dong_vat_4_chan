# Yêu cầu 2 — Phân tích toàn bộ dữ liệu và chọn bộ thuộc tính tìm kiếm

## 1. Phạm vi và kết quả xử lý

Lần chạy mới xử lý tự động **toàn bộ 812 ảnh** hiện có trong
`data/cropped_images_576x384/`, không chọn ảnh đầu/giữa/cuối, không giới hạn ở
các cặp so sánh. Không gộp `source_images/` hoặc `rejected_crops/`.
Yêu cầu 1 vẫn dùng **104 ảnh đại diện** để mô tả giống/khác tại
[animal_comparison.md](animal_comparison.md). Phạm vi xử lý bằng chương trình
không đồng nghĩa với phạm vi quan sát thị giác.

Tách hai công đoạn độc lập:

1. **Kiểm tra kỹ thuật:** liệt kê tệp, đọc bytes, SHA-256, giải mã đầy đủ bằng
   Pillow; ghi định dạng thực, kích thước, mode và số frame. Lỗi hoặc bỏ qua có
   tên tệp và lý do riêng. Định dạng lấy từ bộ giải mã, không suy từ đuôi tệp.
2. **Tính đặc trưng:** chỉ chuyển ảnh giải mã được sang RGB và đo theo mục 2.
   Lỗi chuyển màu/tính toán không đổi một ảnh đọc được thành lỗi giải mã.
   Ảnh nhiều frame được ghi bỏ qua bước đặc trưng; không âm thầm lấy một frame.

<!-- dataset-results:start -->
| Kiểm tra | Kết quả lần chạy mới |
|---|---:|
| Tổng tệp trong thư mục | 816 |
| Tệp ảnh đầu vào | 812 |
| Tên tệp ảnh duy nhất, gồm cả tên cơ sở | 812 |
| Giải mã thành công / lỗi / bỏ qua ảnh | 812 / 0 / 0 |
| Tính đặc trưng thành công / lỗi / bỏ qua ảnh | 812 / 0 / 0 |
| Định dạng thực JPEG, mode RGB | 812 |
| Kích thước 576 × 384, tỉ lệ 3:2 | 812 |
| Nhóm nhãn theo tên tệp | 22 |
| Tệp không phải ảnh, đã ghi lý do bỏ qua | 4 |
<!-- dataset-results:end -->

Bốn tệp không tính là ảnh: `bao_cao_cat.csv`, `.tool_anh.lock`,
`_cat_tu_dong.json`, `_cat_tu_dong.truoc-cap-nhat.json`.
`image_processing.csv` có một dòng cho mỗi tệp, bao gồm cả các tệp này;
`technical_status` và `feature_status` dùng `success`, `failed`, `skipped`,
kèm `technical_error` và `feature_error`. Mọi ảnh của lần chạy này thành công
ở cả hai công đoạn. Không sửa, lật, cắt hoặc ghi lại ảnh gốc.

Nhãn được chuẩn hóa chữ thường, gạch nối thành gạch dưới, bỏ hậu tố số;
`Canis_lupus_familiaris`/tên giống chó gộp vào `canis_familiaris`, tên giống mèo
vào `felis_catus`. Đây là nhóm theo tên tệp, không phải xác minh phân loại
sinh học. Cervidae là cấp họ; không gọi toàn tập là 22 loài.

<!-- label-results:start -->
| Nhãn | Đầu vào | Giải mã thành công | Đặc trưng thành công |
|---|---:|---:|---:|
| `ailuropoda_melanoleuca` | 16 | 16 | 16 |
| `bos_taurus` | 42 | 42 | 42 |
| `bubalus_bubalis` | 7 | 7 | 7 |
| `camelus_bactrianus` | 71 | 71 | 71 |
| `camelus_dromedarius` | 72 | 72 | 72 |
| `canis_familiaris` | 69 | 69 | 69 |
| `canis_lupus` | 9 | 9 | 9 |
| `capra_hircus` | 10 | 10 | 10 |
| `cervidae` | 24 | 24 | 24 |
| `equus_asinus` | 10 | 10 | 10 |
| `equus_caballus` | 17 | 17 | 17 |
| `equus_quagga` | 279 | 279 | 279 |
| `felis_catus` | 5 | 5 | 5 |
| `hydrochoerus_hydrochaeris` | 26 | 26 | 26 |
| `orycteropus_afer` | 2 | 2 | 2 |
| `ovis_aries` | 43 | 43 | 43 |
| `panthera_leo` | 8 | 8 | 8 |
| `panthera_pardus` | 2 | 2 | 2 |
| `panthera_tigris` | 53 | 53 | 53 |
| `ursus_americanus` | 10 | 10 | 10 |
| `ursus_arctos` | 14 | 14 | 14 |
| `vulpes_vulpes` | 23 | 23 | 23 |
<!-- label-results:end -->

Các cột lỗi/bỏ qua theo từng nhãn đều bằng 0 trong
[label_counts.csv](../../outputs/inventory/label_counts.csv).
Mất cân bằng rõ về số lượng: nhãn ngựa vằn có 279 ảnh; lợn đất và báo hoa mai
mỗi nhãn có 2 ảnh. Trung bình toàn tập có trọng số theo số ảnh, vì vậy kèm cả
thống kê riêng theo nhãn, không dùng trung bình toàn tập để đại diện mọi nhóm.

## 2. Những thuộc tính đã tính từ ảnh thật

Tất cả phép đo hiện hành dùng **toàn khung, gồm cả nền** tại kích thước gốc.
Không dùng mask GrabCut lịch sử để giả định tiền cảnh đã đúng. Không resize,
xoay EXIF hoặc biến đổi ICC; Pillow chuyển sang RGB uint8, sau đó OpenCV
chuyển HSV/Lab/xám. Cả bộ hiện tại là RGB cùng kích thước nên không có thay đổi
hình học khi đo. Cấu hình, phiên bản và SHA-256 mã nằm trong
[analysis_environment.json](../../outputs/inventory/analysis_environment.json).

### 2.1. Histogram màu đã trích xuất

Đã tính **812 vector màu toàn khung, mỗi vector 176 chiều**, lưu float32 trong
[full_frame_color_features.npz](../../outputs/inventory/full_frame_color_features.npz).
Đây là `full_frame_color_histograms_v1`, **không phải B400** và không được
đồng nhất với khối tiền cảnh có cùng số bin trong thiết kế B400.

| Khối thực hiện | Cách tính | Số chiều | Chỉ số Python, cuối không bao gồm |
|---|---|---:|---|
| HSV toàn khung | H16, S8, V8 | 32 | `[0:32]` |
| Lab toàn khung | a8, b8; không thêm L | 16 | `[32:48]` |
| HSV theo lưới | 2 hàng × 4 cột; mỗi ô H8, S4, V4 | 128 | `[48:176]` |
| Tổng | Nối theo thứ tự trên, ô theo hàng rồi cột | 176 | `[0:176]` |

H nằm trong [0,180), S/V/a/b uint8 trong [0,256). Histogram H dùng trọng số
S/255; các histogram khác đếm pixel. Mỗi histogram con chia tổng L1;
không có trọng số hue thì giữ vector hue bằng 0. Chưa làm trơn vòng hue,
biến đổi căn histogram, fit scaler hoặc L2 chung. Lưới chia bằng
`numpy.array_split`; các ô của tập hiện tại đều có kích thước bằng nhau.
Tên từng chiều và tên ảnh được lưu cùng ma trận, đọc NPZ với `allow_pickle=False`.
Tên tệp và nhãn chỉ là metadata, không là thành phần của vector.

### 2.2. Thống kê màu, mức xám và kết cấu toàn khung

`feature_metrics.csv` có **812 dòng ảnh**, mỗi dòng có tên tệp, nhãn và các
phép đo sau. Đây là thông tin mô tả ảnh và mức biến thiên, chưa phải bộ mô tả
họa tiết lông riêng biệt hoặc chỉ số chất lượng được gán nhãn.

| Trường | Định nghĩa và ý nghĩa |
|---|---|
| `saturation_mean`, `value_mean` | Trung bình S/255, V/255: độ bão hòa và mức V của cả cảnh. |
| `gray_mean`, `gray_std` | Mean và độ lệch chuẩn tổng thể của ảnh xám OpenCV/255; phản ánh mức sáng và tương phản tổng thể. |
| `dark_fraction`, `bright_fraction` | Tỉ lệ pixel xám uint8 <64 hoặc ≥192; ngưỡng mô tả cố định, chưa tối ưu theo nhãn. |
| `gray_entropy_bits` | −Σp log₂p trên histogram xám 256 mức, bỏ bin rỗng; không giữ vị trí pixel. |
| `sobel_mean` | Mean của √(Gx²+Gy²), Sobel ksize=3 trên xám/255, không chia hệ số kernel; có thể lớn hơn 1. |
| `sobel_strong_fraction` | Tỉ lệ pixel có độ lớn Sobel >0,5; không phải tỉ lệ sọc hoặc chân. |
| `laplacian_variance` | Phương sai tổng thể Laplacian ksize=3 trên xám/255; phản ánh biến thiên tần số cao, không tự kết luận ảnh nét hay mờ. |

Sobel/Laplacian dùng `BORDER_REFLECT_101`. Histogram/gradient gồm cả vật,
cỏ, hàng rào, đất, bóng và nhiễu JPEG. Không suy màu lông, số bướu, chiều dài
tai/chân hoặc mức chiếm khung của động vật từ các chỉ số toàn ảnh này.

## 3. Kết quả đo trên toàn bộ ảnh xử lý thành công

Mỗi ảnh có trọng số bằng nhau khi tổng hợp. Bảng dưới làm tròn 6 chữ số;
JSON/CSV giữ giá trị đầy đủ. Độ lệch chuẩn dùng mẫu số N; phân vị dùng nội suy
tuyến tính. Cả 10 trường đều có 812 quan sát hợp lệ.

<!-- metric-results:start -->
| Trường | Trung bình | Độ lệch chuẩn giữa ảnh | Nhỏ nhất | Trung vị | Lớn nhất |
|---|---:|---:|---:|---:|---:|
| `saturation_mean` | 0.320669 | 0.118058 | 0.024203 | 0.317258 | 0.735186 |
| `value_mean` | 0.556891 | 0.110914 | 0.221953 | 0.555156 | 0.864668 |
| `gray_mean` | 0.499781 | 0.099260 | 0.180287 | 0.502535 | 0.779976 |
| `gray_std` | 0.198729 | 0.042441 | 0.060357 | 0.198808 | 0.335180 |
| `dark_fraction` | 0.161718 | 0.122945 | 0.000000 | 0.129211 | 0.836864 |
| `bright_fraction` | 0.144306 | 0.139224 | 0.000000 | 0.098755 | 0.805868 |
| `gray_entropy_bits` | 7.367510 | 0.355751 | 4.995234 | 7.418311 | 7.920031 |
| `sobel_mean` | 0.366150 | 0.135437 | 0.059591 | 0.348903 | 1.047524 |
| `sobel_strong_fraction` | 0.231824 | 0.123092 | 0.002025 | 0.213756 | 0.759155 |
| `laplacian_variance` | 0.241623 | 0.204816 | 0.002353 | 0.184383 | 1.516544 |
<!-- metric-results:end -->

Các khoảng biến thiên cho thấy điều kiện màu, sáng và cấu trúc cạnh của cảnh
không đồng nhất dù kích thước ảnh đã đồng nhất. Đây là lý do giữ nhiều nhóm
thuộc tính và xử lý nền ở thiết kế tiếp theo; các số đo chưa chứng minh khả năng
tách nhãn của một thuộc tính. Thống kê mean/std/min/Q1/median/Q3/max cho toàn
tập và từng nhãn có tại
[feature_summary.json](../../outputs/inventory/feature_summary.json) và
[feature_statistics.csv](../../outputs/inventory/feature_statistics.csv).

### Ví dụ có tên tệp

Nhận xét thị giác chỉ áp dụng cho các ảnh liên kết bên dưới. Các phép đo đi kèm
được lấy từ `feature_metrics.csv`, không thay thế quan sát vùng cơ thể.

<!-- example-results:start -->
| Ảnh | Nhận xét từ ảnh minh họa | S trung bình | Entropy xám (bit) | Sobel trung bình |
|---|---|---:|---:|---:|
| [Equus_caballus_1014.jpg](../../data/cropped_images_576x384/Equus_caballus_1014.jpg) | Lông thân nâu khá liền; có cỏ và hàng rào ở nền. | 0.283905 | 7.195346 | 0.225057 |
| [equus-quagga_0779.jpg](../../data/cropped_images_576x384/equus-quagga_0779.jpg) | Sọc tối–sáng trên thân và chân; nền cây/cỏ cũng có kết cấu. | 0.376457 | 7.190094 | 0.319428 |
| [panthera-tigris_0250.jpg](../../data/cropped_images_576x384/panthera-tigris_0250.jpg) | Vệt đen dài trên nền lông vàng; nền đất/lá tạo cạnh phụ. | 0.404172 | 7.665076 | 0.539163 |
| [Panthera_pardus_0611.jpg](../../data/cropped_images_576x384/Panthera_pardus_0611.jpg) | Đốm/hoa văn cụm trên lông vàng; cỏ che một phần chân. | 0.509168 | 7.404850 | 0.645784 |
<!-- example-results:end -->

Ngựa và ngựa vằn minh họa việc dáng thân có nét gần nhưng họa tiết khác; hổ và
báo minh họa khác biệt vệt dài với đốm/cụm. Histogram không giữ hình dạng vệt;
Sobel tổng hợp không định vị cạnh thuộc lông hay nền. Vì vậy thiết kế chọn thêm
kết cấu có hướng, hình dạng tiền cảnh và bố cục màu. Đây là lập luận chọn thuộc
tính từ các ảnh cụ thể, chưa phải kết quả so khoảng cách hoặc thử nghiệm tìm kiếm.

## 4. Bộ thuộc tính được chọn: B400, đã triển khai ở yêu cầu 3

**Trạng thái hiện tại:** B400, chuẩn hóa và SQLite đã được triển khai trong
[tools/features/](../../tools/features/), đầu ra riêng tại
[outputs/features/b400_v1/](../../outputs/features/b400_v1/). Kết quả chạy thực tế
và quy ước chi tiết ở [báo cáo yêu cầu 3](b400_implementation.md).
Các kết quả 812×176 và thống kê mục 1–3 vẫn thuộc lần phân tích yêu cầu 2;
NPZ cũ được giữ nguyên, không đổi tên hoặc diễn giải thành B400.

B400 áp dụng cùng công thức cho mọi nhãn, gồm 4 nhóm: **màu 48 + kết cấu 100 +
hình dạng 124 + bố cục màu 128 = 400 chiều**.

| Khối thiết kế | Thuộc tính và cách tính | Chiều | Giá trị thông tin và giới hạn |
|---|---|---:|---|
| C1 | Histogram tiền cảnh HSV H16/S8/V8; hue có trọng số saturation và xử lý vòng. | 32 | Tông màu, đen–trắng; không giữ vị trí, chịu ảnh hưởng ánh sáng. |
| C2 | Histogram a8/b8 của Lab uint8, trên tiền cảnh. | 16 | Bổ sung sắc độ vàng/nâu/xám; vẫn chịu cân bằng trắng. |
| T1 | LBP uniform P=8, R=1 và R=3, mỗi bán kính 10 bin. Chỉ lấy tâm có đủ lân cận trong mask. | 20 | Lông mịn/xù/cuộn; nhạy độ nét và cỡ họa tiết. |
| T2 | GLCM 64 mức, d={1,3}, góc {0°,45°,90°,135°}; energy, contrast, homogeneity, correlation. Chỉ đếm cặp có cả hai pixel trong mask, đối xứng rồi chuẩn hóa. | 32 | Độ thô/biến thiên mức xám; không dùng nền đặt 0 như cách bỏ nền. Correlation thiếu phương sai ghi raw=0, validity=false trong metadata. |
| T3 | Gabor f={0,08;0,16;0,24}, 4 hướng như T2, bandwidth={1,2}; mean/std biên độ, giữ riêng từng tổ hợp; hỗ trợ kernel `n_stds=2`. Tâm phải có đủ cửa sổ trong mask. | 48 | Hướng và cỡ vệt; hỗ trợ phân tích sọc/đốm, không tự nhận biết loài. |
| S1 | 7 Hu trên silhouette, signed-log: h=0 trả 0, còn lại −sign(h)log10(max(abs(h),10⁻¹²)). | 7 | Khối dáng chung; nhạy tư thế, che khuất và mask sai. |
| S2 | w/h bbox; extent A/(wh); solidity A/A_hull; circularity 4πA/P²; S2e=độ dài trục chính/trục phụ trên mask nguồn. Trục chính nối hai điểm đường bao xa nhất; trục phụ là bề rộng bao hình theo phương vuông góc. | 5 | Độ kéo dài, lấp đầy và lõm; không phải kích thước cơ thể thật. Không dùng PCA/covariance cho S2e. |
| S3 | 48 bit raw, ô nhận 1 khi occupancy >15%, đúng 15% nhận 0. Canvas riêng 256×192, lưới 6 hàng × 8 cột, ô vuông 32×32, đọc theo hàng. | 48 | Vị trí khối thân/khe chân thô; bit 0 gồm cả ô trống và ô có ≤15% tiền cảnh. Mất độ phủ liên tục, nhạy ngưỡng/tư thế/mask; không là bộ phận giải phẫu. |
| S4 | Biên trên và dưới, mỗi biên 32 dải ngang, tọa độ y/H; dải trống ghi raw=0, validity=false cùng occupancy ngoài vector. | 64 | Đường lưng và phần chân/bụng; đầu/cổ có thể tạo đỉnh giả, chưa là phép đếm bướu. |
| P | Lưới 2 hàng × 4 cột; mỗi ô tiền cảnh HSV H8/S4/V4. | 128 | Vị trí mảng màu; nhạy hướng đầu, bbox và lỗi mask. |

Các quyết định triển khai B400 v1 (chi tiết và cấu hình máy đọc được ở yêu cầu 3):

- Kế thừa manifest `success/da_duyet/dat` hiện hành, kiểm tra SHA-256/kích thước/
  mask nhị phân. Cờ chất lượng chỉ là metadata, không tự hủy quyết định duyệt.
- Bbox giữ mọi thành phần, co đẳng hướng vào canvas 288 × 192 cho các khối
  hiện hữu trừ S3, đệm giữa;
  mask nearest-neighbor. RGB nội suy tuyến tính có chuẩn hóa theo mask, tránh
  pha nền. Tỉ lệ bbox đo trước đệm, không suy bộ phận bị che.
- S3 lấy bbox nguồn riêng, hệ số `min(256/w,192/h)`, round kích thước về
  số nguyên gần nhất (hòa về số chẵn), ít nhất 1; nearest-neighbor, đệm 0 ở
  giữa với offset floor. Canvas 256×192 và lưới 6×8 do nhóm chọn để giữ 48
  chiều, không phải thông số do bài giảng quy định. Metadata lưu occupancy
  trước ngưỡng, số pixel mỗi ô, bbox, scale, kích thước và offset.
- S2e đo tâm pixel nguồn `(x=cột,y=hàng)`, gốc trên trái, y tăng xuống;
  độ dài Euclid tính bằng pixel, không cộng 1. Convex hull giữ cả phần rời;
  hai điểm xa nhất xác định trục chính. Bề rộng là max−min phép chiếu toàn
  đường bao theo phương vuông góc. Nếu hòa khoảng cách bình phương nguyên,
  sắp hai đầu theo `(x,y)`, chọn cặp nhỏ nhất theo thứ tự từ điển. Một điểm
  hoặc hình thẳng hàng không có tỉ lệ hợp lệ: raw=0, validity=false, lý do
  và số đo trục nằm trong metadata. Không gán tỉ lệ giả.
- LBP chỉ lấy tâm đủ các pixel nội suy; GLCM chỉ đếm cặp tiền cảnh; Gabor chỉ
  lấy tâm đủ toàn bộ cửa sổ. Gabor thiết kế cũ 3×4×2 chỉ có 24 giá trị: thêm
  hai bandwidth cố định `{1,2}` cho 48, không lặp giá trị hoặc thêm chiều khác.
- Không suy hướng từ nhãn: lưu hướng đầu vào; yêu cầu 4 dùng cùng công thức
  cho truy vấn gốc và lật ngang rồi lấy khoảng cách nhỏ nhất cho mọi ảnh.
  Chưa triển khai so khớp ở yêu cầu 3.
- Histogram L1 rồi căn từng bin. T2/T3/S1/S2/S3/S4 (gồm bit S3) z-score theo chiều trên các
  quan sát hợp lệ của tập phát triển hiện hành. L2 từng khối con, L2 từng nhóm,
  trọng số mỗi nhóm 1/4 (hệ số nhân 1/2), nối và L2 cuối. Lưu đầy đủ scaler,
  khối/thứ tự/phiên bản và hash cấu hình để truy vấn dùng lại, không fit lại.
  S3 raw nhị phân nhưng sau z-score/L2 có thể không còn là 0 hoặc 1.
- Ô trống, hue tổng saturation bằng 0, correlation thiếu phương sai, vùng
  kết cấu thiếu hỗ trợ hoặc mẫu số không xác định ghi raw=0 và validity=false
  cùng lý do ngoài 400 chiều. Fit bỏ giá trị quy ước; sau biến đổi đặt chiều
  không hợp lệ về 0. Mask rỗng/toàn trắng, sai hash hoặc sai kích thước thất bại
  và không có vector. Tai, sừng, bướu chưa được định vị/đo riêng.

Các số bin, tần số, lưới và kích thước canvas là tham số thiết kế ban đầu,
chưa được chọn bằng thử nghiệm chất lượng truy hồi. B400 còn phải kiểm chứng
trên các cặp khác nhãn giống màu và cùng nhãn khác giống/màu ở yêu cầu sau.

Ngày 21/10/2026 đã tính lại B400 theo hai công thức trên, vẫn giữ tên và đường
dẫn `outputs/features/b400_v1/` để không phá đường dẫn dự án. Vector và scaler
cũ không tương đương bộ hiện hành; toàn bộ đầu ra đã được thay sau kiểm thử,
trích xuất và kiểm chứng SQLite, không trộn hai công thức. Số liệu chạy mới
ở [b400_implementation.md](b400_implementation.md); bộ 176 chiều mục 1–3 giữ nguyên.
Không tìm thấy PDF bài giảng trong repo, **chưa đối chiếu được bản PDF**;
dùng định nghĩa được giao: ngưỡng trên 15%, hai điểm xa nhất và trục phụ vuông
góc bao đủ hình. Bài giảng còn đề cập chuẩn hóa xoay/trục chính dài 192;
nhiệm vụ này chỉ sửa S2e/S3, không thực hiện hoặc tuyên bố đủ quy trình slide.
Không có báo cáo Word/PDF của nhóm trong repo để sửa trực tiếp. Khi đưa sang
báo cáo nhóm, cập nhật bảng chọn đặc trưng S2/S3, tiền xử lý canvas, miền giá
trị, chuẩn hóa, cấu hình/scaler và bảng kết quả ở yêu cầu 3.

## 5. Giới hạn và hồ sơ tái lập

- Đọc được, cùng kích thước và có vector màu không xác nhận mọi ảnh có đúng
  một cá thể đứng ngang, đủ bốn chân hoặc nhãn sinh học đúng.
- Các thống kê hiện hành gồm cả nền, không là số đo màu lông/hình dạng con vật.
  Yêu cầu 3 đo silhouette theo mask; chưa định vị mốc tai/chân/bướu hoặc
  đánh giá chất lượng phân đoạn bằng ground truth.
- Nhãn theo tên tệp được giữ nguyên, gồm quyết định giữ nhãn một bướu cho
  `Camelus_dromedarius_0892.jpg`, `0894.jpg`, `0910.jpg`, `0912.jpg`; không dùng
  các chỉ số toàn khung để tự đổi nhãn. Kiểm tra tên duy nhất không đồng nghĩa
  kiểm tra ảnh trùng nội dung hoặc gần trùng.
- Không có kết quả xếp hạng, P@K, mAP, IoU, trọng số tối ưu hoặc phép đo thời
  gian truy vấn. Yêu cầu 3 đã có CSDL đặc trưng; chức năng tìm kiếm yêu cầu 4 chưa triển khai.

Chạy từ root dự án trên Mac Intel, dùng môi trường `.venv/` hiện có:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tools/validation/audit_images.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tools/validation/verify_image_analysis.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest tests.validation.test_audit_images -v
```

Có thể truyền `--input-dir` và `--output-dir`; hai thư mục không được chồng lấp.
Chương trình xử lý toàn bộ ảnh ở đầu vào được chỉ định, không gắn cứng số lượng
812. Mã thoát 1 nếu không có ảnh, có lỗi/bỏ qua ảnh hoặc tên cơ sở trùng; đầu ra
vẫn giữ chi tiết để kiểm tra. Lỗi cấu hình/đường dẫn dùng mã thoát 2.
Nếu đổi bộ dữ liệu, cần chạy lại và cập nhật số liệu báo cáo theo đầu ra mới.

| Tệp hiện hành | Nội dung |
|---|---|
| [audit_images.py](../../tools/validation/audit_images.py) | Kiểm kê và đo mọi ảnh, không sửa ảnh gốc. |
| [verify_image_analysis.py](../../tools/validation/verify_image_analysis.py) | Đối chiếu tệp nguồn, hash, trạng thái, nhãn, CSV/JSON/ma trận và các bảng số liệu trong báo cáo. |
| [image_inventory.json](../../outputs/inventory/image_inventory.json) | Số lượng tệp/ảnh, giải mã, tính đặc trưng, tên duy nhất, từng nhãn và các tệp lỗi/bỏ qua. |
| [image_processing.csv](../../outputs/inventory/image_processing.csv) | Từng tên tệp, SHA-256 ảnh, metadata kỹ thuật và trạng thái hai công đoạn. |
| [label_counts.csv](../../outputs/inventory/label_counts.csv) | Số đầu vào/thành công/lỗi/bỏ qua của từng nhãn. |
| [feature_metrics.csv](../../outputs/inventory/feature_metrics.csv) | Các phép đo vô hướng theo từng ảnh thành công. |
| [full_frame_color_features.npz](../../outputs/inventory/full_frame_color_features.npz) | Tên ảnh, tên chiều và 812×176 giá trị histogram màu toàn khung đã tính. |
| [feature_summary.json](../../outputs/inventory/feature_summary.json), [feature_statistics.csv](../../outputs/inventory/feature_statistics.csv) | Tổng hợp toàn tập và theo nhãn từ các dòng ảnh thành công. |
| [analysis_environment.json](../../outputs/inventory/analysis_environment.json) | Phiên bản môi trường, hash mã, thời điểm UTC và cấu hình phép đo. |

Các đầu ra mẫu cũ được giữ riêng về mặt hồ sơ tại
[ghi chú kiểm kê](../../outputs/inventory/README.md); không dùng làm kết quả hiện hành.
