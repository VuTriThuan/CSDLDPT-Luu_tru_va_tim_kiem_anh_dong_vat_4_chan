# Mô tả đặc điểm giống và khác nhau của ảnh động vật bốn chân

## 1. Bộ dữ liệu và phạm vi quan sát

Bộ ảnh được chọn là các tệp ảnh **hiện còn trong** `data/cropped_images_576x384/`. Theo hướng dẫn của dự án, công cụ cắt ghi ảnh vào thư mục này; công cụ duyệt chuyển ảnh bị loại sang `data/rejected_crops/`. Thư mục `data/source_images/` chứa ảnh nguồn chưa lọc. Tại thời điểm kiểm kê, ba thư mục lần lượt có **812 ảnh**, **485 ảnh đã chuyển ra**, và **1.297 ảnh nguồn** (1.295 JPEG, 2 PNG). Không gộp ba tập này. Trong thư mục được chọn còn có 2 CSV, 2 JSON và 1 tệp khóa; chúng không được tính là ảnh.

Kiểm kê trực tiếp toàn bộ 812 tệp ảnh bằng cách đọc và giải mã ảnh cho thấy: **812/812 tệp mở được; 812/812 là JPEG, 576 × 384 pixel, tỉ lệ khung 3:2; không phát hiện tệp ảnh lỗi**. Đây là kích thước *ảnh số*, không cho biết kích thước thật của con vật. Tên tệp được quy về 22 **nhóm nhãn** theo bảng dưới đây; các biến thể chữ hoa, gạch nối và tên giống chó/mèo được cộng đúng vào nhãn tương ứng. Nhãn “Hươu, nai (họ Cervidae)” gộp nhiều dạng động vật trong cùng một họ. Vì vậy, 22 nhóm nhãn **không đồng nghĩa với 22 loài riêng biệt**. Mọi số đếm thực tế khớp cột `so_anh` của `data/cropped_images_576x384/thong_ke_loai_dong_vat.csv` (chênh lệch 0 ở cả 22 dòng).

| Nhóm nhãn | Số ảnh thực tế | Nhóm nhãn | Số ảnh thực tế |
|---|---:|---|---:|
| Gấu trúc lớn | 16 | Bò nhà | 42 |
| Trâu nước | 7 | Lạc đà hai bướu | 71 |
| Lạc đà một bướu | 72 | Sói xám | 9 |
| Chó nhà | 69 | Dê nhà | 10 |
| Hươu, nai (họ Cervidae) | 24 | Lừa nhà | 10 |
| Ngựa nhà | 17 | Ngựa vằn đồng bằng | 279 |
| Mèo nhà | 5 | Chuột lang nước | 26 |
| Lợn đất | 2 | Cừu nhà | 43 |
| Sư tử | 8 | Báo hoa mai | 2 |
| Hổ | 53 | Gấu đen Bắc Mỹ | 10 |
| Gấu nâu | 14 | Cáo đỏ | 23 |
| **Tổng** | **812** | **Số nhóm nhãn** | **22** |

**Cách quan sát.** Đã duyệt bảng ảnh thu nhỏ của **cả 812 ảnh** để sàng lọc khác biệt rõ ràng; chọn **104 ảnh** rải theo thứ tự tên tệp trong từng nhóm để xem thu nhỏ cỡ lớn hơn (5 ảnh/nhóm có ít nhất 5 ảnh; toàn bộ 2 ảnh ở mỗi nhóm lợn đất và báo hoa mai); và mở **24 tệp ở độ phân giải đầy đủ** để kiểm tra chi tiết, gồm các trường hợp nghi vấn. Danh sách chính xác của 104 ảnh mẫu ở phụ lục. Nhận xét thị giác bên dưới dựa trên mẫu này và các ảnh được dẫn cụ thể; việc duyệt 812 thumbnail không thay thế kiểm tra từng ảnh ở độ phân giải đầy đủ.

| Điều kiện của đề | Mức kiểm tra và kết luận |
|---|---|
| Định dạng, kích thước, tệp mở được | **Tự động trên toàn bộ 812 ảnh:** đạt JPEG và 576 × 384; không có tệp lỗi. |
| Một động vật bốn chân trong ảnh | **Quan sát 812 thumbnail, 104 ảnh mẫu lớn và 24 tệp đầy đủ:** phần lớn có một chủ thể chính thuộc các nhóm động vật bốn chân. Thumbnail không đủ để xác nhận tuyệt đối rằng *mọi* ảnh chỉ có đúng một cá thể, không có con vật nhỏ bị che khuất, và thấy đủ bốn chân. Chưa tính được tỉ lệ đạt đáng tin cậy. |
| Đang đứng, chụp ngang | **Quan sát thị giác:** nhiều ảnh thể hiện thân nhìn nghiêng và con vật đứng. Có ảnh đầu hướng về máy hoặc cúi xuống, ảnh dáng đi/chân nhấc; do đó không thể khẳng định cả 812 ảnh đồng nhất tư thế và góc nhìn. |
| Gần giữa ảnh, hướng đầu/đuôi tương đối thống nhất, mức chiếm khung và tỉ lệ cơ thể tương đồng | **Quan sát thị giác:** ảnh đã được cắt cùng khung, chủ thể thường nổi bật gần giữa; nhưng vị trí, hướng đầu, diện tích chủ thể và tỉ lệ thân/chân nhìn thấy còn thay đổi. Chưa phân đoạn và đo khung bao từng con vật trên cả 812 ảnh nên không có ngưỡng số hoặc tỉ lệ đạt cho các tiêu chí này. |

Những ảnh **cần duyệt lại**, ghi theo đường dẫn trong tập được chọn:

- **Nghi nhãn lạc đà một bướu:** [0892](../../data/cropped_images_576x384/Camelus_dromedarius_0892.jpg), [0894](../../data/cropped_images_576x384/Camelus_dromedarius_0894.jpg), [0910](../../data/cropped_images_576x384/Camelus_dromedarius_0910.jpg), [0912](../../data/cropped_images_576x384/Camelus_dromedarius_0912.jpg). Cả bốn tệp khi mở ở kích thước đầy đủ đều cho thấy **hai bướu tách biệt trên đường lưng**, trái với tên nhãn trong tệp. Đây là nhận xét về nội dung ảnh, chưa tự sửa nhãn hoặc chuyển tệp.
- **Góc nhìn/hướng đầu:** [sói 0927](../../data/cropped_images_576x384/Canis_lupus_0927.jpg), [hươu nai 0623](../../data/cropped_images_576x384/cervidae_0623.jpg), [gấu đen 0649](../../data/cropped_images_576x384/ursus-americanus_0649.jpg), [bò 1254](../../data/cropped_images_576x384/Bos_taurus_1254.jpg), [hổ 0337](../../data/cropped_images_576x384/Panthera_tigris_0337.jpg): phần đầu quay gần về phía máy hơn so với ảnh ngang thuần túy. Đây là ứng viên rà soát mức “chụp ngang”, không mặc nhiên là ảnh sai.
- **Tư thế và đường bao thay đổi:** [ngựa vằn 0881](../../data/cropped_images_576x384/equus-quagga_0881.jpg), [cừu 0885](../../data/cropped_images_576x384/ovis-aries_0885.jpg), [dê 1005](../../data/cropped_images_576x384/Capra_hircus_1005.jpg), [bò 1277](../../data/cropped_images_576x384/Bos_taurus_1277.jpg) cúi đầu ăn; tư thế vẫn có thể là đứng nhưng đường bao đầu–cổ khác ảnh ngẩng đầu. [Cáo 0175](../../data/cropped_images_576x384/Vulpes_vulpes_0175.jpg) và [hươu nai 0623](../../data/cropped_images_576x384/cervidae_0623.jpg) có chủ thể trông nhỏ hơn tương đối trong khung so với một số ảnh cùng tập; cần đo khung bao nếu muốn kết luận định lượng.
- **Màu không đại diện cho nhóm:** [chó 0052](../../data/cropped_images_576x384/Canis_familiaris_0052.jpg) có lông nhuộm hồng. Đây không phải vi phạm điều kiện một con vật đang đứng, nhưng phải tránh dùng màu hồng như dấu hiệu tự nhiên của nhãn chó.

Danh sách này chỉ gồm các trường hợp thấy rõ hoặc đáng nghi trong quá trình quan sát; **không phải danh mục đầy đủ của mọi sai lệch tư thế hay hướng trên 812 ảnh**. Không xóa, lật, cắt hay ghi đè tệp ảnh nào.

## 2. Những điểm giống nhau

**Điều kiện chung của tập ảnh.** Toàn bộ ảnh được chọn có cùng định dạng JPEG, kích thước 576 × 384 và khung ngang 3:2. Ở 812 thumbnail, chủ thể động vật nhìn chung nổi bật trước phông cảnh, giúp quan sát dáng thân và màu lông. Đây là mức chuẩn hóa về tệp và khung ảnh được xác nhận; tính đồng nhất về số cá thể, tư thế, góc nhìn, hướng và mức chiếm khung chỉ được nhận xét trong phạm vi mẫu và các ảnh nghi vấn nêu trên.

**Tương đồng thị giác cụ thể.** [Ngựa](../../data/cropped_images_576x384/Equus_caballus_1014.jpg), [lừa](../../data/cropped_images_576x384/Equus_asinus_0587.jpg) và [ngựa vằn](../../data/cropped_images_576x384/equus-quagga_0779.jpg) cùng có thân dài, bốn chân tương đối mảnh, cổ nhô khỏi thân, đầu và mõm kéo dài. [Chó dáng sói](../../data/cropped_images_576x384/Canis_familiaris_0410.jpg), [sói](../../data/cropped_images_576x384/Canis_lupus_0922.jpg) và [cáo](../../data/cropped_images_576x384/Vulpes_vulpes_0314.jpg) cùng có mõm nhọn và đuôi có lông; sắc nâu/xám ở một số ảnh dễ chồng lấn. [Hổ](../../data/cropped_images_576x384/panthera-tigris_0250.jpg) và [báo hoa mai](../../data/cropped_images_576x384/Panthera_pardus_0611.jpg) đều là ảnh thân mèo lớn, nền lông vàng/nâu với dấu đen. [Bò đen](../../data/cropped_images_576x384/Bos_taurus_1287.jpg) và [trâu](../../data/cropped_images_576x384/bubalus-bubalis_0639.jpg) đều có thân nặng, chân tương đối ngắn so với thân và mảng màu tối. [Gấu đen](../../data/cropped_images_576x384/ursus-americanus_0649.jpg) và một số [gấu nâu sẫm](../../data/cropped_images_576x384/Ursus_arctos_1206.jpg) cùng có đường bao thân tròn và lông sẫm. Các nét giống này là theo **cặp ảnh đã quan sát**, không phải quy luật đúng cho mọi tệp thuộc nhãn đó.

## 3. Những điểm khác nhau

**Giữa các nhóm.** Màu và sự phân bố màu tạo tín hiệu rõ khi nhìn thấy toàn thân: ngựa vằn có các sọc đen–trắng chạy qua thân và chân; hổ có sọc tối trên nền vàng/cam, bụng sáng; báo hoa mai có các đốm/hoa văn đen trên nền vàng. Sọc của hổ và ngựa vằn đều có tính lặp, nhưng khác màu nền, bề dày và vùng phân bố. Bò trong mẫu thường có mảng đen–trắng lớn hoặc nâu sẫm; trâu mẫu thiên xám/đen khá liền mảng; gấu trúc có mảng đen quanh mắt, tai, vai và chân trên nền trắng. Chỉ so màu trung bình của cả ảnh sẽ bỏ qua vị trí các mảng và dễ bị màu cỏ, đất, tuyết hoặc ánh sáng chi phối.

Về hình dạng, ngựa–lừa–ngựa vằn chia sẻ đường thân nhưng ảnh [lừa 0587](../../data/cropped_images_576x384/Equus_asinus_0587.jpg) lộ tai dài hơn ảnh [ngựa 1014](../../data/cropped_images_576x384/Equus_caballus_1014.jpg); sọc thân và chân là dấu hiệu mạnh của ảnh [ngựa vằn 0779](../../data/cropped_images_576x384/equus-quagga_0779.jpg). Ảnh [cáo 0314](../../data/cropped_images_576x384/Vulpes_vulpes_0314.jpg) có thân thon, chân nhỏ, đuôi xù và mõm nhọn; ảnh [sói 0922](../../data/cropped_images_576x384/Canis_lupus_0922.jpg) có thân và đầu trông nặng hơn, nhưng chó nhà biến thiên mạnh nên chỉ hình dáng không luôn tách được ba nhãn. Ảnh lạc đà [hai bướu 0303](../../data/cropped_images_576x384/Camelus_bactrianus_0303.jpg) và [một bướu 0434](../../data/cropped_images_576x384/Camelus_dromedarius_0434.jpg) có cổ dài, chân dài, nhưng khác ở số đỉnh bướu nhìn thấy trên đường lưng. Dấu hiệu này cũng giúp phát hiện bốn tệp dromedarius nghi sai nhãn ở mục 1.

Các cấu trúc nhỏ cần được đọc theo ảnh: sừng cong nổi bật ở [trâu 0639](../../data/cropped_images_576x384/bubalus-bubalis_0639.jpg); sừng ở [dê 1011](../../data/cropped_images_576x384/Capra_hircus_1011.jpg); gạc phân nhánh ở [hươu nai 0568](../../data/cropped_images_576x384/cervidae_0568.jpg); bờm ở [sư tử đực 1155](../../data/cropped_images_576x384/Panthera_leo_1155.jpg), nhưng không hiện diện ở [ảnh sư tử 1157](../../data/cropped_images_576x384/Panthera_leo_1157.jpg). Lông trong ảnh [cừu 0187](../../data/cropped_images_576x384/ovis-aries_0187.jpg) có bề mặt xù/cuộn rõ, khác bề mặt lông trơn hơn ở [dê 1005](../../data/cropped_images_576x384/Capra_hircus_1005.jpg). Lông gấu nâu trong [1177](../../data/cropped_images_576x384/Ursus_arctos_1177.jpg) trông dài/xù hơn lông đen tương đối mịn trong [gấu đen 0649](../../data/cropped_images_576x384/ursus-americanus_0649.jpg), song màu và độ xù đều đổi theo cá thể, cảnh và ánh sáng.

**Trong cùng nhóm.** Chó [0052](../../data/cropped_images_576x384/Canis_familiaris_0052.jpg) màu hồng, lông xù và dáng poodle; chó [Doberman 0953](../../data/cropped_images_576x384/Canis_lupus_familiaris_doberman_0953.jpg) đen–nâu, lông ngắn, thân thon. Bò [1254](../../data/cropped_images_576x384/Bos_taurus_1254.jpg) nhiều mảng đen–trắng trong khi [1287](../../data/cropped_images_576x384/Bos_taurus_1287.jpg) gần như nâu sẫm. Nhóm Cervidae chứa [0568](../../data/cropped_images_576x384/cervidae_0568.jpg) có gạc lớn, nền xám và [0633](../../data/cropped_images_576x384/cervidae_0633.jpg) thân nâu có đốm trắng, không thấy gạc trong ảnh. Ngựa [1024](../../data/cropped_images_576x384/Equus_caballus_1024.jpg) có mảng lông trắng–nâu lớn, có thể gây nhầm về màu với bò dù đường đầu, bờm, chân và móng khác. Tư thế cúi đầu, bước đi, độ che khuất chân, ánh sáng gắt/yếu, và nền tuyết/cỏ/đất hoặc bối cảnh chuồng trại cũng gây biến thiên ngay trong cùng nhóm. Những khác biệt này là đặc điểm **của ảnh**, không được diễn giải thành kích thước thực hay thuộc tính cố định của toàn nhóm.

## 4. Bảng cặp ảnh minh họa

Mỗi tệp dưới đây thuộc `data/cropped_images_576x384/`; các đường dẫn liên kết trỏ đến **ảnh thực tế**. Dòng nhiều ảnh là so sánh trực tiếp nhiều nhóm.

| Ảnh minh họa | Đặc điểm giống | Đặc điểm khác | Dễ gây nhầm | Hữu ích cho tìm kiếm |
|---|---|---|---|---|
| [Ngựa 1014](../../data/cropped_images_576x384/Equus_caballus_1014.jpg), [lừa 0587](../../data/cropped_images_576x384/Equus_asinus_0587.jpg), [ngựa vằn 0779](../../data/cropped_images_576x384/equus-quagga_0779.jpg) | Thân dài, chân mảnh, đầu kéo dài. | Tai lừa lộ dài; ngựa có bờm/đuôi lông; ngựa vằn có sọc dọc thân và chân. | Ngựa nâu và lừa nâu giống màu/dáng; ngựa vằn khi ảnh nhỏ còn chủ yếu là đường bao ngựa. | Kết hợp đường bao tai–đầu–chân với họa tiết sọc theo vùng thân/chân. |
| [Chó 0410](../../data/cropped_images_576x384/Canis_familiaris_0410.jpg), [sói 0922](../../data/cropped_images_576x384/Canis_lupus_0922.jpg), [cáo 0314](../../data/cropped_images_576x384/Vulpes_vulpes_0314.jpg) | Mõm nhọn, tai dựng, đuôi có lông, tông nâu/xám. | Trong ba ảnh này, cáo thon và đuôi xù dài; sói trông thân/đầu nặng hơn; chó có mảng lông đen–vàng đặc trưng ảnh. | Chó dáng sói có thể gần sói; màu nâu/xám không đủ để tách. | Tỉ lệ đầu–thân, hình đuôi và phân bố màu vùng lưng/mõm. |
| [Hổ 0250](../../data/cropped_images_576x384/panthera-tigris_0250.jpg), [báo 0611](../../data/cropped_images_576x384/Panthera_pardus_0611.jpg) | Thân mèo lớn, lông vàng/nâu với vệt đen. | Hổ có sọc dài; báo có đốm/hoa văn dạng cụm rải trên thân. | Màu vàng và kết cấu đen ở kích thước nhỏ gần nhau. | Hướng, kích thước và cách lặp của vệt đen; phân bố trên thân. |
| [Gấu đen 0649](../../data/cropped_images_576x384/ursus-americanus_0649.jpg), [gấu nâu 1177](../../data/cropped_images_576x384/Ursus_arctos_1177.jpg), [gấu nâu 1206](../../data/cropped_images_576x384/Ursus_arctos_1206.jpg), [gấu trúc 1218](../../data/cropped_images_576x384/Ailuropoda_melanoleuca_1218.jpg) | Thân tròn, chân chắc, tai tròn, lông dày. | 0649 rất tối; 1177 nâu và xù; 1206 nâu sẫm; gấu trúc có các mảng đen–trắng rõ quanh vai, chân và đầu. | 1206 và gấu đen dễ lẫn nếu chỉ dùng độ tối; gấu trúc khác màu nhưng cùng dạng thân gấu. | Kết hợp màu theo vùng với kết cấu lông và đường bao đầu–vai. |
| [Lạc đà hai bướu 0303](../../data/cropped_images_576x384/Camelus_bactrianus_0303.jpg), [lạc đà một bướu 0434](../../data/cropped_images_576x384/Camelus_dromedarius_0434.jpg) | Cổ và chân dài, thân màu nâu/vàng. | Đường lưng 0303 có hai đỉnh bướu, 0434 có một đỉnh. | Màu lông và nền tương tự; bướu có thể bị góc nhìn che. | Đường bao lưng và số đỉnh bướu khi nhìn thấy. |
| [Bò 1287](../../data/cropped_images_576x384/Bos_taurus_1287.jpg), [trâu 0639](../../data/cropped_images_576x384/bubalus-bubalis_0639.jpg), [dê 1011](../../data/cropped_images_576x384/Capra_hircus_1011.jpg), [cừu 0909](../../data/cropped_images_576x384/ovis-aries_0909.jpg), [hươu nai 0568](../../data/cropped_images_576x384/cervidae_0568.jpg) | Bốn chân, thân ngang; một số ảnh cùng tông nâu/xám. | Trâu có sừng cong rộng; dê có sừng nhỏ hơn và dáng gọn; cừu có lông cuộn; hươu nai 0568 có gạc phân nhánh; bò 1287 có thân nặng và sừng ngắn trong ảnh. | Màu nâu/xám, nền cỏ/đất và dáng nghiêng có thể gần nhau. | Hình sừng/gạc, kết cấu lông, tỉ lệ cổ–chân–thân và đường bao đầu. |
| **Cùng nhãn chó:** [0052](../../data/cropped_images_576x384/Canis_familiaris_0052.jpg), [Doberman 0953](../../data/cropped_images_576x384/Canis_lupus_familiaris_doberman_0953.jpg) | Đều là một con chó đứng. | Lông nhuộm hồng/xù so với lông ngắn đen–nâu; đường thân và đuôi khác. | Khoảng cách màu lớn dù cùng nhãn. | Cần đặc trưng hình dạng bổ sung cho màu; không coi màu hồng là dấu hiệu nhãn. |
| **Cùng nhãn Cervidae:** [0568](../../data/cropped_images_576x384/cervidae_0568.jpg), [0633](../../data/cropped_images_576x384/cervidae_0633.jpg) | Chân mảnh, thân động vật móng guốc. | 0568 lớn trong khung, xám và có gạc; 0633 nâu có đốm trắng, không thấy gạc. | Biến thiên nội nhóm lớn vì nhãn ở cấp họ và góc/cá thể khác nhau. | Đặc trưng có/không thấy gạc, đốm và hình đầu; tránh ép cả nhóm về một màu. |
| **Cùng nhãn bò:** [1254](../../data/cropped_images_576x384/Bos_taurus_1254.jpg), [1287](../../data/cropped_images_576x384/Bos_taurus_1287.jpg); [ngựa 1024](../../data/cropped_images_576x384/Equus_caballus_1024.jpg) | 1254 và 1024 đều có mảng đen–trắng; hai ảnh bò cùng dáng thân nặng. | 1287 nâu sẫm; ngựa 1024 có đầu dài, bờm, chân/đuôi khác bò. | Màu mảng làm hai nhóm khác nhau trông giống; hai bò cùng nhãn lại khác màu. | Đặt hình dạng và vị trí mảng màu cùng nhau. |

## 5. Tác động đến chọn đặc trưng ở bước tiếp theo

Ảnh đã cùng kích thước nên có thể so sánh đặc trưng trên lưới không gian thống nhất, nhưng nền, tư thế và mức chiếm khung vẫn gây nhiễu. **Màu sắc** nên được mô tả theo các vùng cơ thể hoặc lưới không gian thay vì chỉ một màu trung bình; cần xét trường hợp cùng nhãn khác màu (chó, bò, Cervidae) và khác nhãn cùng tông (bò–trâu, chó–sói). **Kết cấu** giúp tách sọc dài của hổ/ngựa vằn, đốm của báo/hươu non và lông cuộn của cừu, nhưng phải xét hướng, độ nét, ánh sáng và kích thước hiển thị. **Hình dạng** và đường bao hỗ trợ tai lừa, đuôi cáo, sừng/gạc, bờm và số bướu; tính hữu ích giảm khi đầu cúi, chi bị che hoặc góc chụp đổi. **Phân bố không gian** của mảng màu/họa tiết (sọc trên thân và chân, mảng gấu trúc, đốm trên lưng) giúp tránh nhầm do nền tương tự. Bốn ảnh lạc đà nghi sai nhãn cần được người làm dữ liệu rà trước khi dùng làm mẫu đại diện hoặc đánh giá hệ thống. Phần này chỉ phân tích ảnh và định hướng đặc trưng; không đưa kết quả tìm kiếm, độ chính xác hay giá trị vector giả định.

### Phụ lục: 104 ảnh mẫu quan sát cỡ lớn hơn

Mọi tên tệp dưới đây nằm trong `data/cropped_images_576x384/`. Mẫu được chọn theo các vị trí trải đều trong danh sách tên tệp của từng nhãn; hai nhãn có 2 ảnh được lấy đủ 2.

- **Ailuropoda melanoleuca** (5): `Ailuropoda_melanoleuca_1211.jpg`, `Ailuropoda_melanoleuca_1218.jpg`, `Ailuropoda_melanoleuca_1226.jpg`, `Ailuropoda_melanoleuca_1240.jpg`, `Ailuropoda_melanoleuca_1252.jpg`.

- **Bos taurus** (5): `Bos_taurus_1254.jpg`, `Bos_taurus_1264.jpg`, `Bos_taurus_1275.jpg`, `Bos_taurus_1287.jpg`, `Bos_taurus_1297.jpg`.

- **Bubalus bubalis** (5): `bubalus-bubalis_0634.jpg`, `bubalus-bubalis_0639.jpg`, `bubalus-bubalis_0640.jpg`, `bubalus-bubalis_0643.jpg`, `bubalus-bubalis_0645.jpg`.

- **Camelus bactrianus** (5): `Camelus_bactrianus_0008.jpg`, `Camelus_bactrianus_0176.jpg`, `Camelus_bactrianus_0303.jpg`, `Camelus_bactrianus_0398.jpg`, `Camelus_bactrianus_0504.jpg`.

- **Camelus dromedarius** (5): `Camelus_dromedarius_0002.jpg`, `Camelus_dromedarius_0163.jpg`, `Camelus_dromedarius_0316.jpg`, `Camelus_dromedarius_0434.jpg`, `Camelus_dromedarius_0912.jpg`.

- **Canis lupus** (5): `Canis_lupus_0914.jpg`, `Canis_lupus_0920.jpg`, `Canis_lupus_0922.jpg`, `Canis_lupus_0925.jpg`, `Canis_lupus_0927.jpg`.

- **Canis lupus familiaris** (5): `Canis_familiaris_0024.jpg`, `Canis_familiaris_0400.jpg`, `Canis_lupus_familiaris_doberman_0953.jpg`, `Canis_lupus_familiaris_labrador_retriever_0978.jpg`, `canis-lupus-familiaris_0688.jpg`.

- **Capra hircus** (5): `Capra_hircus_1000.jpg`, `Capra_hircus_1002.jpg`, `Capra_hircus_1005.jpg`, `Capra_hircus_1011.jpg`, `Capra_hircus_1013.jpg`.

- **Cervidae** (5): `cervidae_0566.jpg`, `cervidae_0584.jpg`, `cervidae_0610.jpg`, `cervidae_0623.jpg`, `cervidae_0633.jpg`.

- **Equus asinus** (5): `Equus_asinus_0046.jpg`, `Equus_asinus_0165.jpg`, `Equus_asinus_0533.jpg`, `Equus_asinus_0570.jpg`, `Equus_asinus_0587.jpg`.

- **Equus caballus** (5): `Equus_caballus_1014.jpg`, `Equus_caballus_1018.jpg`, `Equus_caballus_1023.jpg`, `Equus_caballus_1028.jpg`, `Equus_caballus_1033.jpg`.

- **Equus quagga** (5): `Equus_quagga_1034.jpg`, `equus-quagga_0282.jpg`, `equus-quagga_0669.jpg`, `equus-quagga_0779.jpg`, `equus-quagga_0881.jpg`.

- **Felis catus** (5): `Felis_catus_abyssinian_1085.jpg`, `Felis_catus_bengal_1101.jpg`, `Felis_catus_persian_1109.jpg`, `Felis_catus_scottish_fold_1111.jpg`, `Felis_catus_scottish_fold_1113.jpg`.

- **Hydrochoerus hydrochaeris** (5): `Hydrochoerus_hydrochaeris_1116.jpg`, `Hydrochoerus_hydrochaeris_1126.jpg`, `Hydrochoerus_hydrochaeris_1134.jpg`, `Hydrochoerus_hydrochaeris_1146.jpg`, `Hydrochoerus_hydrochaeris_1154.jpg`.

- **Orycteropus afer** (2): `Orycteropus_afer_0039.jpg`, `Orycteropus_afer_0158.jpg`.

- **Ovis aries** (5): `ovis-aries_0005.jpg`, `ovis-aries_0082.jpg`, `ovis-aries_0187.jpg`, `ovis-aries_0885.jpg`, `ovis-aries_0909.jpg`.

- **Panthera leo** (5): `Panthera_leo_1155.jpg`, `Panthera_leo_1157.jpg`, `Panthera_leo_1160.jpg`, `Panthera_leo_1161.jpg`, `Panthera_leo_1164.jpg`.

- **Panthera pardus** (2): `Panthera_pardus_0494.jpg`, `Panthera_pardus_0611.jpg`.

- **Panthera tigris** (5): `Panthera_tigris_0337.jpg`, `panthera-tigris_0048.jpg`, `panthera-tigris_0153.jpg`, `panthera-tigris_0250.jpg`, `panthera-tigris_0331.jpg`.

- **Ursus americanus** (5): `ursus-americanus_0646.jpg`, `ursus-americanus_0649.jpg`, `ursus-americanus_0651.jpg`, `ursus-americanus_0657.jpg`, `ursus-americanus_0661.jpg`.

- **Ursus arctos** (5): `Ursus_arctos_1167.jpg`, `Ursus_arctos_1177.jpg`, `Ursus_arctos_1192.jpg`, `Ursus_arctos_1206.jpg`, `Ursus_arctos_1209.jpg`.

- **Vulpes vulpes** (5): `Vulpes_vulpes_0007.jpg`, `Vulpes_vulpes_0119.jpg`, `Vulpes_vulpes_0175.jpg`, `Vulpes_vulpes_0266.jpg`, `Vulpes_vulpes_0314.jpg`.
