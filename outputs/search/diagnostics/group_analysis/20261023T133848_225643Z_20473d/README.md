# Phân tích bốn nhóm B400 — 23/10/2026

> Sau khi dọn, giữ nguyên toàn bộ kết quả cuối và ba lượt nguồn ngựa/bò/chó. Số lượt đủ điều kiện trong bảng là kiểm kê trước khi dọn; checkout tinh gọn không còn các lượt trung gian. Các giá trị phân tích đã lưu không được tính lại hoặc chỉnh sửa.

Chạy trên Mac Intel/Python 3.10.11 trong `.venv/`. Đây là phân tích các vector đã lưu, không đổi thuật toán mặc định, không trích xuất lại, fit scaler, chuẩn hóa lại nhóm hoặc sửa SQLite.

## Chọn mẫu trước khi xem kết quả

Quét các thư mục truy vấn trực tiếp trong `outputs/search/`, bỏ qua bản xuất và batch lồng nhau. Xét ba họ tên nguồn: ngựa (`ngua_`, `Equus_caballus_`), bò (`Bos_taurus_`), chó (`Canis_familiaris_`), không dùng nhãn để xếp hạng. Chọn query_id nhỏ nhất theo thứ tự từ điển của từng họ. Không lọc khoảng cách, kết quả đẹp hoặc chất lượng mask. Thiếu artifact ở một ca thuộc họ đã chọn gây lỗi, không âm thầm chuyển ca. Danh sách tất cả ca đủ điều kiện và hash artifact nằm trong `analysis.json`.

| Nhóm | Số lượt thuộc họ | Query được chọn | Ảnh nguồn |
|---|---:|---|---|
| horse | 2 | [20261023T005527_002900Z_39619666](../../../20261023T005527_002900Z_39619666/result.json) | ngua_576x384.jpg |
| cow | 6 | [20261023T012837_426171Z_19029e33](../../../20261023T012837_426171Z_19029e33/result.json) | Bos_taurus_001.jpg |
| dog | 7 | [20261023T013510_179045Z_e5ee7591](../../../20261023T013510_179045Z_e5ee7591/result.json) | Canis_familiaris_004.jpg |

Tất cả ba ảnh không trùng SHA-256 bytes ảnh nào trong corpus, nên không có agreement IoU với mask CSDL. Giữ nguyên mask và hai vector gốc/lật của từng query cho cả 9 cấu hình. Không coi các lượt do người dùng thử là tập truy vấn độc lập đã được thiết kế để đánh giá tổng quát.

## Khoảng cách và cách đọc thay đổi

Với tập tọa độ S, dùng **D_S(q,x) = min(Σ_S(q_gốc − x)², Σ_S(q_lật − x)²)**. Tính float64 từ các vector chuẩn hóa float32 đã lưu. `full` dùng [0:400]; `only_color` [0:48], `only_texture` [48:148], `only_shape` [148:272], `only_layout` [272:400]. `without_*` dùng hợp của ba đoạn còn lại.

Trọng số đã có trong vector; không nhân thêm 0,25, không L2 lại các đoạn, không chia theo số chiều hay validity. Chọn lại hướng thắng cho mỗi ứng viên trong từng cấu hình; không cộng các min hướng của từng nhóm. Giữ đúng self_match và duplicates từ result.json; ba ca này có chính sách lịch sử loại tự khớp và một đại diện/hash. Phá hòa giống tìm kiếm mặc định.

`rank_delta = rank_cấu_hình − rank_full`: âm là lên hạng. `distance_delta` là hiệu số học với D_full, nhưng các cấu hình có tập chiều/năng lượng khác nhau nên độ lớn không dùng kết luận tốt hơn. Khoảng cách không phải xác suất. Bỏ chiều tất yếu có thể làm D giảm; hướng thắng cũng có thể đổi.

## Kết quả và mức thay đổi

**[top5.csv](top5.csv)** ghi đủ 135 dòng (3 query × 9 cấu hình × 5), tên, khoảng cách, hướng, hạng trong full, delta hạng và delta khoảng cách. **[candidate_ranks.csv](candidate_ranks.csv)** theo dõi hợp Top 5 của cả chín cấu hình ở mọi cấu hình, kể cả khi ứng viên rớt khỏi Top 5. `analysis.json` chứa cùng dữ liệu và số vị trí đổi. Bảng dưới rút gọn Top 1 và số tệp Top 5 chung với full.

| Query | Cấu hình | Top 1 | D_S | Chung Top 5 với full |
|---|---|---|---:|---:|
| horse | full | Ursus_arctos_1192.jpg | 0.271056 | 5/5 |
| horse | only_color | Vulpes_vulpes_0021.jpg | 0.008396 | 0/5 |
| horse | only_texture | Camelus_bactrianus_0327.jpg | 0.056475 | 0/5 |
| horse | only_shape | Ursus_arctos_1192.jpg | 0.108068 | 1/5 |
| horse | only_layout | Camelus_dromedarius_0894.jpg | 0.024156 | 0/5 |
| horse | without_color | Ursus_arctos_1192.jpg | 0.241742 | 3/5 |
| horse | without_texture | Ursus_arctos_1192.jpg | 0.191688 | 3/5 |
| horse | without_shape | Camelus_dromedarius_0894.jpg | 0.111452 | 0/5 |
| horse | without_layout | Ursus_arctos_1192.jpg | 0.216752 | 3/5 |
| cow | full | Panthera_tigris_0377.jpg | 0.380346 | 5/5 |
| cow | only_color | Camelus_bactrianus_0443.jpg | 0.003900 | 0/5 |
| cow | only_texture | Hydrochoerus_hydrochaeris_1126.jpg | 0.002127 | 0/5 |
| cow | only_shape | Bos_taurus_1261.jpg | 0.137233 | 0/5 |
| cow | only_layout | Ursus_arctos_1209.jpg | 0.038689 | 0/5 |
| cow | without_color | Panthera_tigris_0377.jpg | 0.347935 | 3/5 |
| cow | without_texture | Bos_taurus_1268.jpg | 0.327291 | 1/5 |
| cow | without_shape | Camelus_bactrianus_0443.jpg | 0.065946 | 0/5 |
| cow | without_layout | Panthera_tigris_0377.jpg | 0.266590 | 4/5 |
| dog | full | cervidae_0616.jpg | 0.446182 | 5/5 |
| dog | only_color | Canis_lupus_0921.jpg | 0.020078 | 0/5 |
| dog | only_texture | Capra_hircus_1001.jpg | 0.003889 | 2/5 |
| dog | only_shape | Canis_lupus_familiaris_doberman_0956.jpg | 0.123923 | 1/5 |
| dog | only_layout | canis-lupus-familiaris_0680.jpg | 0.038940 | 0/5 |
| dog | without_color | Canis_lupus_familiaris_labrador_retriever_0978.jpg | 0.342300 | 3/5 |
| dog | without_texture | cervidae_0616.jpg | 0.364153 | 3/5 |
| dog | without_shape | Canis_lupus_0921.jpg | 0.125730 | 1/5 |
| dog | without_layout | cervidae_0616.jpg | 0.315542 | 3/5 |

Bỏ shape làm số kết quả Top 5 chung với full còn **0/5 ngựa, 0/5 bò, 1/5 chó**. Bỏ màu còn **3/5 ở cả ba ca**. Đây là bằng chứng nhóm làm thay đổi thứ hạng, chưa phải bằng chứng shape hay màu cải thiện phù hợp thị giác.

## Mask và quan sát thị giác có ghi nguồn

| Query | Tiền cảnh | Tình trạng quan sát trên ảnh/mask đã lưu |
|---|---:|---|
| Ngựa | 73,51% | Mask giữ phần lớn mặt đất dưới con vật, bbox [0,26,576,358] chạm biên; biểu diễn đang đo cả nền. Không loại ca xấu này. |
| Bò | 25,65% | Mask thiếu phần dưới chân trong cỏ; không có cờ heuristic vẫn cần xem ảnh. |
| Chó | 35,86% | Giữ phần lớn thân/đuôi; 11 thành phần và chạm biên là dấu hiệu cần xem lại. |

Ảnh đối chiếu: [ngựa](horse.png), [bò](cow.png), [chó](dog.png). Mỗi bảng gồm RGB, overlay, mask và đủ Top 5 của chín cấu hình. Tên đầy đủ xem CSV vì nhãn preview được rút gọn.

Đã xem trực tiếp cả ba bảng ảnh và ghi **12 cặp tham chiếu**, gồm các ứng viên có liên hệ về dáng/màu/họa tiết và các phản ví dụ. [reviewed_candidate_ranks.csv](reviewed_candidate_ranks.csv) ghi 108 dòng = 12 cặp × 9 cấu hình, với hạng, D_S và nhận xét. Người quan sát là trợ lý, được ghi `assistant_visual_inspection_exploratory`; không mạo nhận đánh giá độc lập bởi nhóm/người dùng. Các cặp được chọn sau khi xem kết quả nên có thiên lệch lựa chọn.

Rubric quan sát riêng từng thuộc tính: 0 = khác rõ/không thấy liên hệ; 1 = giống một phần; 2 = gần ở thuộc tính đang xét. Dáng xét thân, chân, cổ/đầu, tư thế; màu xét lông chủ thể, không dùng nền; texture xét độ dài/độ trơn của lông và họa tiết nhìn thấy. Không suy mức liên quan từ tên loài. Không gộp ba số này thành relevance nhị phân: `visual_relevant` còn trống để nhóm chấm theo mục tiêu thống nhất. Đây là mô tả có kiểm tra hình ảnh, không phải P@5 hay độ chính xác truy hồi.

| Query / ứng viên được xem | Dáng / màu / texture (0–2) | Full → chỉ màu / chỉ texture / chỉ shape / chỉ layout | Bỏ màu / texture / shape / layout |
|---|---|---|---|
| horse / Ursus_arctos_1192.jpg | 0/0/0 | 1 → 96 / 27 / 1 / 42 | 1 / 1 / 11 / 1 |
| horse / Panthera_leo_1156.jpg | 1/1/2 | 59 → 2 / 101 / 316 / 31 | 87 / 130 / 19 / 76 |
| horse / Camelus_dromedarius_0896.jpg | 1/1/1 | 248 → 4 / 35 / 711 / 367 | 308 / 540 / 55 / 261 |
| horse / Capra_hircus_1004.jpg | 1/0/1 | 90 → 11 / 8 / 505 / 36 | 123 / 287 / 2 / 125 |
| cow / Panthera_tigris_0377.jpg | 1/0/0 | 1 → 63 / 48 / 17 / 178 | 1 / 4 / 30 / 1 |
| cow / Bos_taurus_1261.jpg | 2/0/2 | 117 → 625 / 379 / 1 / 691 | 77 / 44 / 474 / 56 |
| cow / Equus_caballus_1031.jpg | 1/2/2 | 5 → 25 / 73 / 144 / 11 | 8 / 30 / 8 / 11 |
| cow / Bos_taurus_1268.jpg | 2/0/2 | 39 → 69 / 405 / 6 / 147 | 45 / 1 / 268 / 37 |
| dog / Canis_lupus_familiaris_golden_retriever_0971.jpg | 2/2/2 | 5 → 81 / 5 / 65 / 28 | 6 / 13 / 8 / 6 |
| dog / Canis_lupus_familiaris_labrador_retriever_0978.jpg | 2/2/1 | 2 → 124 / 47 / 17 / 15 | 1 / 2 / 18 / 3 |
| dog / Canis_lupus_familiaris_doberman_0956.jpg | 1/0/0 | 100 → 530 / 428 / 1 / 625 | 78 / 42 / 469 / 59 |
| dog / Capra_hircus_1001.jpg | 1/2/1 | 4 → 34 / 1 / 110 / 12 | 8 / 11 / 2 / 7 |

Ví dụ bò: Bos_taurus_1261 có dáng thân/bụng/chân gần query nhưng lông khoang khác màu, từ hạng 117 lên 1 khi chỉ shape. Ngựa nâu Equus_caballus_1031 khác nhãn bò nhưng có thân nhìn ngang và lông nâu ngắn trơn tương đồng; full hạng 5, chỉ shape hạng 144. Với chó, golden_retriever_0971 giống cả dáng, màu kem và lông dài, full hạng 5, chỉ shape hạng 65; doberman_0956 lên hạng 1 chỉ shape dù khác màu/lông rõ. Quan sát này cho thấy thứ hạng có thể thay đổi theo tiêu chí đang giữ, không cho phép kết luận cấu hình nào tốt nhất.

Chưa có chấm nhị phân đầy đủ trên hợp ứng viên, nhiều người chấm, tập giữ lại độc lập hay ước lượng bất định. Vì vậy **không kết luận một nhóm cải thiện độ phù hợp thị giác**, không tối ưu weights từ ba ví dụ và không đổi chính sách mặc định.

## Tái lập

Chạy tại root repo sau khi tạo `.venv/` theo README, không cần đường dẫn Downloads gốc:

```sh
.venv/bin/python -B -m tools.search.group_analysis
.venv/bin/python -B -m unittest tests.search.test_group_analysis -v
```

Mỗi lần tạo thư mục mới dưới `outputs/search/diagnostics/group_analysis/`, giữ nguyên các lượt truy vấn. Mã chỉ đọc SQLite, cấu hình/scaler và artifact đã lưu, kiểm tra ID/hash, chuẩn hóa raw bằng scaler frozen, đối chiếu baseline và tính phép chiếu. Nếu bổ sung truy vấn có query_id sớm hơn hoặc đổi artifact, danh sách chọn có thể đổi; dùng `analysis.json` kèm hash để xác định đúng snapshot. Bảng quan sát thị giác là hồ sơ quan sát riêng, không tự sinh lại bằng nhãn hoặc công thức.

Các thư mục chạy trước trong cùng thư mục cha là trung gian của lần sửa công cụ; bản được báo cáo là thư mục chứa README này.
