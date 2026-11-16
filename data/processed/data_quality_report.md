# Báo cáo chất lượng dữ liệu tiền xử lý

Vai trò: thành viên phụ trách tiền xử lý dữ liệu Wyscout.  
Thời gian: 2026-11-16T23:08:28+07:00 (UTC+07:00).  
Phạm vi yêu cầu: [1694401, 1694416].  
Kết quả: **1,782 dòng × 21 cột**, 13 cột thông tin trích xuất.

## 1. Nguồn dữ liệu thực sự đã đọc

| Thuộc tính | Giá trị |
|---|---|
| Nguồn được đọc | `D:\ML_ck\data\raw\events` |
| Loại nguồn | directory |
| JSON được xử lý lần lượt | `events_European_Championship.json` |
| Số sự kiện trước khi lọc Pass | 78,140 |
| So SHA-256 trước/sau khi đọc | ĐẠT — nội dung nguồn không thay đổi |
| Trường bắt buộc và ID trong/giữa các file đọc | ĐẠT |

| JSON đã đọc | Kích thước (byte) | SHA-256 |
|---|---:|---|
| events_European_Championship.json | 22,954,338 | `2ebf16ab36601fe910d1fd6e42aab9c241ffd577bc89ce51826fe780c449a4ef` |

Nguồn là thư mục JSON đã giải nén. Không áp dụng kích thước/MD5/CRC của ZIP; không kết luận ZIP tham chiếu đã được kiểm chứng trong lần chạy này.

Pipeline chỉ đọc nguồn; không sao chép, giải nén thêm hoặc ghi đè dữ liệu gốc.
CSV chứa phạm vi được yêu cầu, không mặc nhiên chứa toàn bộ các giải trong thư mục raw.

Chọn mẫu: mỗi trận ≥ 800 chuyền, tỷ lệ ít/nhiều ≥ 0.85, không có dòng bị loại E2/E3. Đã kiểm tra lại cả khi nhập --matches.

## 2. Nhật ký làm sạch trước và sau khi chọn trận

| Bước | Xử lý | Toàn bộ JSON đã đọc | Phạm vi trận chọn |
|---|---|---:|---:|
| S4 | Pass đầu vào | 43,695 | 1,782 |
| S5 / E2 | Loại: không đúng hai điểm hoặc thiếu tọa độ | 0 | 0 |
| S6 / E3 | Loại: tọa độ không biểu diễn số nguyên trong [0,100] | 0 | 0 |
| Sau S5–S6 | Pass hợp lệ còn lại | 43,695 | 1,782 |
| S7 / E1 | Giữ và gắn cờ điểm cuối (0,0) | 195 | 9 |
| S8 / E6 | Thiếu thẻ kết quả trên Pass đầu vào | 0 | 0 |
| S8 | Chính xác trên các dòng giữ lại | 36,925 | 1,502 |
| S8 | Không chính xác trên các dòng giữ lại | 6,770 | 280 |
| S8 | Chưa rõ kết quả trên các dòng giữ lại | 0 | 0 |
| S9 / E5 | Giữ player_id=0 | 0 | 0 |
| S10 / E4 | Giữ điểm đầu trùng điểm cuối | 20 | 0 |
| S11 / E8 | Dòng có tọa độ 0 hoặc 100 | 1,186 | 47 |

Đối chiếu phạm vi chọn: **1,782 vào − 0 E2 − 0 E3 = 1,782 dòng bàn giao**.
E1/E4/E5 là số dòng giữ lại có đặc điểm tương ứng, không phải số dòng bị xóa.

## 3. Kiểm định bảng cuối

| Kiểm tra | Kết quả |
|---|---|
| Số dòng > 500 | PASS |
| Số cột thông tin trích xuất > 10 | PASS |
| Đúng tên, thứ tự và kiểu 21 cột | PASS |
| Không có null | PASS |
| event_id duy nhất | PASS |
| ID hợp lệ, player_id=0 được giữ | PASS |
| Tọa độ gốc nguyên trong [0,100] | PASS |
| Bốn tọa độ chuẩn hóa trong [0,1] | PASS |
| Chuẩn hóa đúng bằng tọa độ gốc / 100 | PASS |
| dx_n, dy_n, length_n đúng công thức | PASS |
| end_unknown khớp điểm cuối (0,0) | PASS |
| Nhãn kết quả đúng tập giá trị | PASS |
| Hiệp hợp lệ; giây hữu hạn, không âm | PASS |
| Thứ tự trận → hiệp → giây | PASS |
| Đúng hai đội mỗi trận | PASS |
| S14: mỗi trận chọn có ít nhất 800 chuyền | PASS |
| S14: tỷ lệ cân bằng mỗi trận >= 0.85 | PASS |
| S14: các trận chọn không có dòng bị loại E2/E3 | PASS |

| Cột tọa độ chuẩn hóa | Min | Max |
|---|---:|---:|
| x_start_n | 0.02 | 1.00 |
| y_start_n | 0.02 | 0.99 |
| x_end_n | 0.00 | 1.00 |
| y_end_n | 0.00 | 1.00 |

Min/Max của **cả bốn cột**: 0.00 / 1.00.

## 4. Phân bố dữ liệu bàn giao

| Trận | Số chuyền sạch | Số chuyền theo team_id | Tỷ lệ ít/nhiều |
|---|---:|---|---:|
| 1694401 | 923 | 10682: 475; 14358: 448 | 0.9432 |
| 1694416 | 859 | 3757: 418; 7047: 441 | 0.9478 |

| Cột bàn giao | Kiểu dữ liệu | Số null |
|---|---|---:|
| event_id | int64 | 0 |
| match_id | int64 | 0 |
| team_id | int64 | 0 |
| player_id | int64 | 0 |
| match_period | str | 0 |
| event_sec | float64 | 0 |
| sub_event_id | int64 | 0 |
| sub_event_name | str | 0 |
| x_start | int64 | 0 |
| y_start | int64 | 0 |
| x_end | int64 | 0 |
| y_end | int64 | 0 |
| pass_outcome | str | 0 |
| x_start_n | float64 | 0 |
| y_start_n | float64 | 0 |
| x_end_n | float64 | 0 |
| y_end_n | float64 | 0 |
| dx_n | float64 | 0 |
| dy_n | float64 | 0 |
| length_n | float64 | 0 |
| end_unknown | bool | 0 |

## 5. Ghi chú đọc dữ liệu

- Tọa độ gốc 0–100 và tọa độ chuẩn hóa 0–1 đều được giữ; giá trị đúng 0 hoặc 1 là hợp lệ.
- `end_unknown=True` đánh dấu điểm cuối (0,0) nghi ngờ chưa rõ; đây là quy ước xử lý dựa trên dấu hiệu dữ liệu, chưa phải xác nhận chính thức của nhà cung cấp.
- Có **9 dòng** mang cờ; còn **1,773 dòng** khi loại cờ để đọc thông tin điểm cuối.
- `dx_n`, `dy_n`, `length_n` dùng hệ chuẩn hóa, không phải mét; không diễn giải điểm cuối/độ dài của dòng mang cờ E1 như vị trí thật.
- `player_id=0` nghĩa là chưa rõ cầu thủ; `pass_outcome=unknown` nghĩa là thiếu thẻ 1801/1802. Không đổi chúng thành cầu thủ thật hoặc chuyền hỏng.
- Thời gian `event_sec` tính lại từ đầu mỗi hiệp. Bảng được sắp theo trận, hiệp rồi giây.
- Báo cáo và hình ảnh này mô tả chất lượng/phân bố dữ liệu tiền xử lý.
