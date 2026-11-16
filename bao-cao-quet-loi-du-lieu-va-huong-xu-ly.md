# Báo cáo quét toàn bộ dữ liệu `events_1.zip` và hướng xử lý

> Cập nhật phần triển khai tiền xử lý ngày 16/11/2026: quy trình `.py` theo bước 00–06 đọc trực tiếp `data/raw/events/`, xuất vào `data/processed/`. Xem README.md và mục 11 ở cuối báo cáo. Các mục khảo sát bên dưới là bằng chứng của lần quét ZIP trước đây, không phải tuyên bố rằng lần đọc JSON hiện tại đã kiểm chứng MD5/CRC ZIP.

> Dành cho thành viên 1 (Tiền xử lý dữ liệu) · Đề tài: Phân cụm đường chuyền bóng đá bằng Grid-based Clustering
> Không có code. Mọi con số đều lấy từ lần quét thực tế; nhãn nguồn: **[D]** = đã kiểm tra trên dữ liệu, **[N]** = nguồn ngoài đã tra, **[G]** = đề xuất/suy luận cần nhóm xác nhận.

---

## 1. Kết luận nhanh

1. File `events_1.zip` **giống hệt từng byte** với `events.zip` bạn gửi trước đó (cùng mã MD5 `7c20e8647e7eda58d7838a0c7b1ec6ab`, cùng kích thước 77.323.413 byte) **[D]**. Vì vậy mọi kết quả kiểm tra trước đây vẫn đúng.
2. File không hỏng: kiểm tra CRC báo không có lỗi nén **[D]**.
3. Đã quét **cả 7 file, 3.251.294 sự kiện, 1.941 trận, 1.665.508 đường chuyền** **[D]**. Hai tổng số đầu khớp với con số công bố của bộ dữ liệu gốc (1.941 trận; 3.251.294 sự kiện) **[N]**, cho thấy dữ liệu đầy đủ.
4. **Cấu trúc dữ liệu rất sạch** (không thiếu trường, không trùng, không sai kiểu ở đường chuyền). Lỗi có ý nghĩa nằm ở **giá trị**, gồm 6 nhóm: điểm cuối giả (0,0), đường chuyền chỉ có 1 điểm, tọa độ ngoài khoảng, `playerId` bằng 0, đường chuyền thiếu thẻ kết quả, và trận lệch giữa hai đội. Chi tiết ở mục 4.
5. Lỗi **quan trọng nhất**: **8.540 đường chuyền (0,51%) có điểm cuối bằng đúng (0,0)**, xuất hiện ở cả 7 file. Nếu không xử lý, phân cụm 4D sẽ sinh cụm giả ở góc sân.

---

## 2. Cách quét

- Đọc từng file JSON trực tiếp từ zip, không giải nén ra đĩa.
- Với mọi sự kiện: kiểm tra tập trường, kiểu dữ liệu, ánh xạ tên-mã, `eventSec`, thứ tự thời gian, cấu trúc `positions` và `tags`, ID trùng, số đội mỗi trận.
- Với đường chuyền (Pass): số điểm vị trí, khoảng giá trị, điểm đầu/cuối (0,0), điểm đầu trùng điểm cuối, giá trị biên, thẻ kết quả, trùng nội dung, phân bố theo trận, hiệp, đội.
- Kiểm tra chéo giữa 7 file: ID sự kiện trùng, mã trận dùng chung.
- Kiểm tra hướng tấn công dựa trên vị trí các cú sút.
- Giới hạn của lần quét: xem mục 9.

---

## 3. Bảng tổng hợp 7 file **[D]**

| File | Sự kiện | Trận | Đường chuyền | Điểm cuối (0,0) | Điểm đầu = điểm cuối | Tọa độ ngoài 0–100 | Chỉ 1 điểm vị trí | `playerId`=0 | Thiếu thẻ kết quả |
|---|---|---|---|---|---|---|---|---|---|
| England | 643.150 | 380 | 328.657 | 1.755 (0,53%) | 178 | 0 | 0 | 6 | 0 |
| European_Championship | 78.140 | 51 | 43.695 | 195 (0,45%) | 20 | 0 | 0 | 0 | 0 |
| France | 632.807 | 380 | 319.198 | 1.666 (0,52%) | 173 | 0 | 0 | 6 | 0 |
| Germany | 519.407 | 306 | 261.462 | 1.180 (0,45%) | 128 | **2** | 0 | 4 | 0 |
| Italy | 647.372 | 380 | 337.317 | 1.722 (0,51%) | 132 | 0 | 0 | 6 | 0 |
| Spain | 628.659 | 380 | 318.722 | 1.779 (0,56%) | 147 | 0 | 0 | 9 | 0 |
| World_Cup | 101.759 | 64 | 56.457 | 243 (0,43%) | 34 | **2** | **2** | 0 | **2** |
| **Tổng** | **3.251.294** | **1.941** | **1.665.508** | **8.540 (0,51%)** | **812** | **4** | **2** | **31** | **2** |

Số chuyền mỗi trận (nhỏ nhất / trung vị / lớn nhất) **[D]**:

| File | Nhỏ nhất | Trung vị | Lớn nhất |
|---|---|---|---|
| England | 520 | 859,5 | 1.324 |
| European_Championship | 609 | 832 | 1.291 |
| France | 561 | 841 | 1.203 |
| Germany | 622 | 852,5 | 1.135 |
| Italy | 599 | 879 | 1.306 |
| Spain | 534 | 836 | 1.124 |
| World_Cup | 630 | 870,5 | 1.339 |

Trận có số chuyền thấp nhất toàn bộ dữ liệu là 520 (England), vẫn vượt ngưỡng ">500 dòng".

---

## 4. Danh mục lỗi và cách xử lý

| Mã | Lỗi / bất thường | Phạm vi và số lượng **[D]** | Ảnh hưởng | Cách xử lý đề xuất **[G]** |
|---|---|---|---|---|
| **E1** | **Điểm cuối bằng đúng (0,0)** | 8.540 đường chuyền ở cả 7 file (0,43–0,56% mỗi file; tối đa 1,9% trong một trận) | Rất có thể là giá trị giữ chỗ cho điểm cuối không rõ: ở Euro và World_Cup (đã kiểm tra riêng hai file này) không có điểm nào ở (0,1), (1,0), (1,1); ở Euro, 87% là Cross và 97% có thẻ không chính xác (tỷ lệ chính xác chung ~85%); World_Cup có kết quả tương tự (84% Cross, 97% không chính xác). Đưa vào 4D tạo cụm giả ở góc sân; xóa lặng lẽ làm tỷ lệ chuyền chính xác bị lệch lên | **Không xóa. Gắn cờ `end_unknown`.** 2D (điểm đầu): dùng tất cả dòng. 4D: loại dòng có cờ khi chạy và ghi số dòng bị loại |
| **E2** | Đường chuyền chỉ có 1 điểm vị trí | 2, đều ở World_Cup | Không dựng được vector (đầu, cuối) | Loại bỏ; ghi số dòng |
| **E3** | Tọa độ ngoài khoảng 0–100 (giá trị 101) | 4 đường chuyền: 2 ở Germany (trận 2516920, sự kiện 225765702 và 225765704), 2 ở World_Cup (trận 2057974, sự kiện 259750995 và 259750997). Mỗi cặp dùng chung một điểm sai (điểm cuối của chuyền này là điểm đầu của chuyền kế tiếp) | Tọa độ sai làm lệch chuẩn hóa về [0,1] | Loại bỏ cả hai dòng của mỗi cặp. Không cắt về 100 vì không có căn cứ giá trị đúng |
| **E4** | Điểm đầu trùng điểm cuối (độ dài 0) | 812 đường chuyền | Góc chuyền không xác định; độ dài 0 | Giữ lại. Để trống góc cho các dòng này |
| **E5** | `playerId` = 0 trên đường chuyền | 31 ở League (England 6, France 6, Germany 4, Italy 6, Spain 9); **0 ở Euro và World_Cup** | Không biết cầu thủ chuyền | Giữ dòng; coi 0 là "không xác định", loại khỏi thống kê theo cầu thủ |
| **E6** | Đường chuyền thiếu thẻ kết quả (không có 1801 lẫn 1802) | 2 ở World_Cup | Không biết chính xác hay không | Nhãn kết quả "không xác định"; không ép về giá trị nào |
| **E7** | Trận lệch: đội chuyền ít hơn dưới 35% đội chuyền nhiều | 107 trong 1.941 trận (England 41, Germany 18, France 11, Spain 11, Italy 15, World_Cup 7, Euro 4) | Chọn nhầm trận lệch thì một đội gần như vắng mặt khi so sánh hai đội | Chọn trận theo tỷ lệ cân bằng (mục 7) |
| **E8** | Giá trị biên: có tọa độ bằng đúng 0 hoặc 100 | Hàng nghìn đường chuyền mỗi file (ví dụ Euro: 648 có tọa độ 100, 538 có tọa độ 0) | Đây là giá trị hợp lệ (biên sân). Sau khi chia 100 sẽ có giá trị đúng 1,0, làm lỗi chỉ số ô nếu cách chia ô không xử lý biên | Giữ lại. **Báo B** gộp giá trị 1,0 vào ô cuối |
| **E9** | `subEventId` lẫn kiểu: một số là chuỗi rỗng | Chỉ ở sự kiện Offside (ví dụ England 1.558, Euro 189), **không** ở đường chuyền | Gây lỗi kiểu dữ liệu nếu đọc cả file vào bảng rồi ép kiểu trước khi lọc | **Lọc Pass trước, rồi mới ép kiểu** |
| **E10** | `matchPeriod` có giá trị `P` (loạt sút luân lưu) | 71 sự kiện ở Euro, 76 ở World_Cup; **không có đường chuyền** nào | Gây lỗi khi sắp xếp nếu bảng thứ tự hiệp chỉ có 4 giá trị và còn sự kiện `P` | Bảng thứ tự hiệp gồm cả `1H, 2H, E1, E2, P`, hoặc chỉ sắp xếp sau khi đã lọc Pass |
| **E11** | `eventSec` tính lại từ đầu mỗi hiệp; lẫn kiểu số nguyên và số thực | Mọi file (ví dụ England 7 giá trị nguyên) | Sắp xếp chỉ theo `eventSec` sẽ trộn hiệp | Sắp xếp theo trận, rồi hiệp, rồi `eventSec`; ép về số thực |
| **E12** | Tập thẻ trên đường chuyền khác nhau giữa các file | Thẻ 102 không có ở World_Cup; 502 và 504 chỉ ở Germany; 201 chỉ ở Italy và Spain | Nếu tạo cột từ các thẻ này thì bảng của các file không cùng cấu trúc; ý nghĩa các thẻ này chưa xác nhận | Chỉ dùng thẻ 1801/1802 (đã xác nhận **[N]**); không diễn giải thẻ khác |
| **E13** | File giải VĐQG rất lớn | Mỗi file giải VĐQG khoảng 150–190 MB khi giải nén (zip tổng khoảng 956 MB giải nén) | Khi mình đọc lần lượt các file lớn trong **một** tiến trình trên môi trường khoảng 4 GB RAM thì tiến trình bị dừng; tách mỗi file một tiến trình thì chạy ổn (mỗi file khoảng 10–13 giây). Nguyên nhân bộ nhớ là suy luận **[G]** | Đọc từng file một, giải phóng bộ nhớ sau mỗi file. Với phạm vi 1–2 trận chỉ cần file Euro hoặc World_Cup |

---

## 5. Các hạng mục đã kiểm tra và KHÔNG thấy lỗi **[D]**

- Mọi sự kiện đều có đủ 12 trường như nhau; không trường nào thiếu.
- `id`, `matchId`, `teamId`, `playerId`, `eventId` luôn là số nguyên; `positions` luôn gồm các cặp `x`, `y` nguyên, không có giá trị rỗng; `tags` đúng cấu trúc, không có thẻ trùng trong một sự kiện.
- Mỗi tên sự kiện ứng với đúng một `eventId`; tên loại phụ ứng với đúng một mã loại phụ. Mọi đường chuyền có `eventId` = 8.
- Không có `id` sự kiện trùng trong từng file và giữa 7 file; không có đường chuyền trùng nội dung; không có mã trận dùng chung giữa các file.
- Mỗi trận có đúng 2 đội; không cầu thủ nào thuộc 2 đội trong cùng một trận.
- Các sự kiện trong file đã theo đúng thứ tự (hiệp rồi thời gian) trong từng trận, 0 vi phạm; các sự kiện của cùng một trận nằm liền nhau.
- Mọi trận đều có đường chuyền ở cả hai hiệp; không có đội nào dưới 121 đường chuyền trong một trận (nhỏ nhất toàn bộ: 121, ở France).
- Không có đường chuyền mang cả hai thẻ 1801 và 1802.
- Không có `eventSec` âm hay rỗng.
- Hướng tấn công đã chuẩn hóa: vị trí sút trung bình 83,4–85,2 ở mọi file. Số nhóm (đội, trận, hiệp) có vị trí sút trung bình dưới 50: England 0/1.483, Euro 0/217, France 1/1.507, Germany 1/1.209, Italy 1/1.504, Spain 0, World_Cup 1/264. Đây là kiểm tra trên **cú sút**, chưa phải trên đường chuyền.

---

## 6. Quy trình xử lý đề xuất (theo thứ tự) **[G]**

| Bước | Việc | Số liệu để đối chiếu |
|---|---|---|
| S1 | Kiểm tra file: so kích thước và mã MD5 của file zip của nhóm với `events_1.zip` này | 77.323.413 byte; MD5 `7c20e8647e7eda58d7838a0c7b1ec6ab` |
| S2 | Đọc **từng file JSON một** trực tiếp từ zip; không đọc nhiều file lớn cùng lúc | Số sự kiện theo bảng mục 3 |
| S3 | Kiểm tra cấu trúc: đủ 12 trường; `id` không trùng | 0 trùng |
| S4 | Lọc Pass (`eventName` = Pass, `eventId` = 8), **trước khi** ép kiểu | Số chuyền theo bảng mục 3 |
| S5 | Loại dòng không có đúng 2 điểm vị trí (E2) | World_Cup: 2 |
| S6 | Loại dòng có tọa độ ngoài 0–100 (E3) | Germany: 2; World_Cup: 2 |
| S7 | Gắn cờ `end_unknown` cho dòng có điểm cuối đúng (0,0) (E1); không xóa | Theo bảng mục 3 |
| S8 | Giải mã kết quả: 1801 = chính xác, 1802 = không chính xác, không có thẻ = không xác định (E6) | Chỉ World_Cup có 2 dòng không xác định |
| S9 | Đánh dấu `playerId` = 0 là không xác định (E5) | 31 dòng ở League; 0 ở Euro và World_Cup |
| S10 | Giữ dòng điểm đầu trùng điểm cuối; để trống góc (E4) | 812 dòng |
| S11 | Chuẩn hóa: chia 100 để về [0,1]; giữ cột tọa độ gốc; báo B về giá trị 1,0 (E8) | Giá trị nhỏ nhất ≥ 0, lớn nhất = 1,0 |
| S12 | Tạo cột dẫn xuất: `dx_n`, `dy_n`, `length_n` | Dòng điểm đầu trùng điểm cuối có `length_n` = 0 |
| S13 | Sắp xếp theo trận, rồi hiệp (`1H`, `2H`, `E1`, `E2`, `P`), rồi `eventSec` (E10, E11) | Không có `event_id` trùng |
| S14 | Chọn trận theo tiêu chí mục 7 | Mỗi trận ≥ 800 chuyền, hai đội cân bằng, không dòng bị loại ở S5–S6 |
| S15 | In **nhật ký chất lượng**: số dòng vào, số dòng loại ở từng quy tắc (S5, S6), số dòng gắn cờ (S7), số dòng không xác định (S8, S9), số dòng ra; kiểm tra số dòng >500 và số cột >10 | Bảng nhật ký dùng được cho slide 3 |

### Số dòng còn lại sau S5–S6 nếu xử lý cả file **[D]**

| File | Đường chuyền ban đầu | Bị loại | Còn lại | Gắn cờ `end_unknown` |
|---|---|---|---|---|
| England | 328.657 | 0 | 328.657 | 1.755 |
| European_Championship | 43.695 | 0 | 43.695 | 195 |
| France | 319.198 | 0 | 319.198 | 1.666 |
| Germany | 261.462 | 2 | 261.460 | 1.180 |
| Italy | 337.317 | 0 | 337.317 | 1.722 |
| Spain | 318.722 | 0 | 318.722 | 1.779 |
| World_Cup | 56.457 | 4 | 56.453 | 243 |
| **Tổng** | **1.665.508** | **6** | **1.665.502** | **8.540** |

---

## 7. Chọn trận cho phạm vi 1–2 trận **[G]**

Tiêu chí: không có dòng bị loại ở S5–S6, tổng chuyền ≥ 800, tỷ lệ chuyền giữa hai đội ≥ 0,85 (đội ít chia đội nhiều). Các trận thỏa mãn đã tính ở lần kiểm tra trước **[D]**:

| File | Mã trận | Tổng chuyền | Mỗi đội |
|---|---|---|---|
| European_Championship | 1694416 | 859 | 418 / 441 |
| European_Championship | 1694401 | 923 | 448 / 475 |
| World_Cup | 2057992 | 856 | 427 / 429 |
| World_Cup | 2058009 | 1.026 | 497 / 529 |

Hai trận Euro 1694416 và 1694401 đã được chạy thử toàn bộ quy trình: ra 1.782 dòng, 21 cột, 9 dòng gắn cờ `end_unknown`, không có giá trị rỗng **[D]**. Hai file Euro và World_Cup không có đường chuyền nào có `playerId` = 0, nên các trận trên không dính E5.

---

## 8. Việc cần làm cùng nhóm

1. **So khớp file với nhóm trưởng:** file phân công ghi `events(1).zip`. Hãy hỏi nhóm trưởng kích thước và mã MD5 của file đó; nếu trùng với bảng ở S1 thì cùng một dữ liệu. Mình không có file `events(1).zip` nên chưa so sánh được.
2. **Chốt cách xử lý E1** với nhóm (đặc biệt B và C), vì ảnh hưởng đến phân cụm 4D.
3. **Báo B về giá trị biên 1,0** (E8) khi bàn giao DataFrame.
4. Vẽ hình trên 2 trận đã chọn để xác nhận hướng tấn công và trục y (chưa xác nhận trên đường chuyền).

---

## 9. Giới hạn của lần quét và các điểm chưa kiểm chứng

- Quét bằng đoạn mã riêng của mình để kiểm chứng dữ liệu; **không phải notebook của nhóm**.
- Lần đầu quét trong một tiến trình duy nhất thì bị dừng khi đến file lớn; mình chạy lại từng file riêng và tất cả 7 file đều quét xong. Kết quả trong báo cáo đến từ lần chạy thứ hai.
- "(0,0) là giá trị giữ chỗ" là **suy luận từ quy luật trong dữ liệu**, chưa có tài liệu chính thức xác nhận.
- Ý nghĩa của các thẻ ngoài 1801/1802 (kể cả 102, 201, 502, 504) **chưa xác nhận**.
- Chưa xác nhận hướng tấn công và trục y trên đường chuyền bằng hình vẽ.
- Chưa kiểm tra các lỗi ngữ nghĩa sâu hơn (ví dụ điểm đầu của chuyền có khớp điểm cuối của sự kiện liền trước hay không), vì quy mô và ý nghĩa của kiểm tra này chưa rõ.
- Tên đội, tên cầu thủ không có trong zip; chưa xác nhận đầy đủ các file mô tả trên trang gốc.

---

## 10. Tài liệu tham khảo

[1] L. Pappalardo, P. Cintia, A. Rossi, E. Massucco, P. Ferragina, D. Pedreschi, F. Giannotti, "A public data set of spatio-temporal match events in soccer competitions", *Scientific Data* 6, 236 (2019). https://www.nature.com/articles/s41597-019-0247-7. *Đã tra thông tin thư mục; chưa đọc toàn văn.*

[2] L. Pappalardo, E. Massucco, "Soccer match event dataset", figshare, 2019. https://doi.org/10.6084/m9.figshare.c.4415000. *Đã tra; chưa xác nhận giấy phép trên trang gốc.*

[3] Bài báo dùng bộ dữ liệu này, ghi nhận 1.941 trận và 3.251.294 sự kiện. https://www.scitepress.org/Papers/2021/107114/107114.pdf. *Chỉ đọc đoạn trích; dùng làm đối chiếu tổng số.*

[4] Wyscout Data Glossary, "Pass" (thuộc tính Successful: tagId 1801 là có, 1802 là không). https://dataglossary.wyscout.com/pass. *Đã tra đoạn trích.*

---

## 11. Triển khai riêng phần tiền xử lý bằng .py (16/11/2026)

- File chạy: `pipeline.py`. Đọc code theo thứ tự `tien_xu_ly/buoc_00_cau_hinh.py` đến `buoc_06_xuat_ket_qua.py`; mỗi file có ghi chú nhiệm vụ/đầu vào/đầu ra.
- `kiem_tra_du_lieu.py` dùng để xem và kiểm định lại CSV. Notebook cũ được giữ trong `ban_nhap/` để tham khảo, không thuộc quy trình chạy hiện tại.
- Dữ liệu tập trung tại `data/`: JSON gốc nằm trong `raw/events/`; `processed/` chứa CSV, báo cáo chất lượng, hình dữ liệu và log. Pipeline chỉ đọc raw; ghi SHA-256 từng file và đối chiếu lại sau xử lý, không phụ thuộc ZIP ngoài dự án.
- S5 yêu cầu đúng hai điểm; S6 kiểm tra tọa độ trước khi ép kiểu. Metadata không hợp lệ hoặc hai thẻ kết quả mâu thuẫn sẽ dừng để kiểm tra, không tự sửa thành thông tin khác.
- S14 kiểm tra đủ tất cả mã trận yêu cầu; khi chọn mẫu thủ công cũng bắt buộc mỗi trận ≥800 chuyền, tỷ lệ cân bằng ≥0,85 và không có dòng bị loại E2/E3. `--matches -1` xử lý toàn nguồn, không áp điều kiện cân bằng của chọn mẫu. S15 kiểm tra tên/thứ tự/kiểu cột, công thức chuẩn hóa/dẫn xuất, thời gian, cờ E1 và các tiêu chí chất lượng.
- Nhật ký ghi số dòng vào/loại/giữ theo toàn nguồn và từng trận. Thống kê thiếu kết quả trên Pass đầu vào được phân biệt với trên các dòng giữ lại.
- E13 được thực hiện bằng cách làm sạch từng JSON và bỏ tham chiếu tới Pass thô trước khi đọc JSON tiếp theo; chỉ giữ bảng cần bàn giao, ID và bộ đếm.
- Phạm vi triển khai ở đây kết thúc tại dữ liệu sạch, báo cáo và hình mô tả dữ liệu. Không triển khai thuật toán hoặc chỉ số đánh giá mô hình.

Lệnh chạy và kiểm tra: xem README.md. Báo cáo của lần chạy mới nhất: `data/processed/data_quality_report.md`. Có thể chỉ định ZIP qua `--zip-path`; khi đó mới kiểm tra MD5/CRC ZIP và ghi rõ nguồn thực tế trong báo cáo.
