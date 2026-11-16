# Tiền xử lý dữ liệu đường chuyền Wyscout

Phần việc của người phụ trách dữ liệu: đọc nguồn, chọn trận, làm sạch, chuẩn hóa, kiểm định và xuất dữ liệu. Toàn bộ quy trình chính dùng file `.py`.

## 1. Đọc code theo thứ tự

Mỗi file dưới đây có ghi chú ở đầu file về đầu vào, đầu ra và nhiệm vụ.

| Thứ tự | File | Thực hiện |
|---|---|---|
| Chạy chính | `pipeline.py` | Gọi các bước bên dưới, xử lý lần lượt từng JSON |
| 00 | `tien_xu_ly/buoc_00_cau_hinh.py` | Đường dẫn, schema 21 cột, thứ tự hiệp và logger |
| 00A | `tien_xu_ly/buoc_00_bao_ve_dau_ra.py` | Chặn đầu ra trùng raw/hardlink/symlink; công bố từng file hoàn chỉnh bằng `os.replace` |
| 01 | `tien_xu_ly/buoc_01_doc_du_lieu.py` | Đọc JSON gốc, ghi SHA-256, kiểm tra cấu trúc/ID, lọc Pass; hỗ trợ thêm ZIP khi chỉ định |
| 02 | `tien_xu_ly/buoc_02_lam_sach.py` | Xử lý E1–E6, đếm dòng vào/loại/giữ theo nguồn và từng trận |
| 03 | `tien_xu_ly/buoc_03_chuan_hoa.py` | Chia tọa độ cho 100, tính dx/dy/độ dài, kiểm tra đủ trận, sắp xếp |
| 04 | `tien_xu_ly/buoc_04_kiem_dinh.py` | Kiểm tra schema, kiểu, null, ID, tọa độ, công thức, thời gian và tiêu chí chọn trận S14 |
| 05 | `tien_xu_ly/buoc_05_ve_du_lieu.py` | Vẽ điểm bắt đầu và mẫu vector, phân biệt kết quả chưa rõ |
| 06 | `tien_xu_ly/buoc_06_xuat_ket_qua.py` | Ghi CSV và báo cáo chất lượng từ bộ đếm thực tế |
| Đọc lại kết quả | `kiem_tra_du_lieu.py` | Chỉ đọc CSV, kiểm định lại và in mẫu dữ liệu |
| Kiểm thử | `tests/test_tien_xu_ly.py`, `tests/test_bao_ve_raw.py` | Tái hiện lỗi dữ liệu, báo cáo, đường dẫn, bộ nhớ, CLI và bảo vệ raw khi ghi kết quả |

Các module `buoc_*.py` được import theo quy trình; không cần chạy riêng từng module.

`kiem_tra_du_lieu.py` kiểm định schema và giá trị của CSV (S15). Tiêu chí chọn trận S14 và nguyên vẹn nguồn phải được xác minh khi chạy pipeline, vì CSV sạch không còn các dòng đã bị loại để tự kiểm tra nhật ký E2/E3.

## 2. Dữ liệu được lưu ở đâu

```text
ML_ck/
├── pipeline.py
├── kiem_tra_du_lieu.py
├── tien_xu_ly/                 # Các module 00–06
├── tests/
├── ban_nhap/                  # Notebook cũ chỉ để tham khảo
└── data/
    ├── raw/
    │   └── events/            # 7 JSON gốc đã giải nén; chỉ đọc
    │       ├── events_European_Championship.json
    │       └── ...
    └── processed/
        ├── passes_cleaned.csv
        ├── data_quality_report.md
        ├── pitch_pass_distribution.png
        ├── pitch_pass_directions.png
        └── pipeline_execution.log
```

Pipeline mặc định đọc trực tiếp các JSON trong `data/raw/events/` và ghi kết quả vào `data/processed/`. Không cần `D:\events.zip` hoặc thư mục `events (2)/`. Không tự sao chép, giải nén hoặc ghi đè raw.

SHA-256 của từng JSON được đọc được ghi trong báo cáo và so lại trước khi xuất, sau khi ghi tạm và sau khi công bố kết quả. Nếu phát hiện nguồn thay đổi trước khi công bố thì chương trình dừng, giữ các kết quả cũ. Việc so hash đối chiếu nội dung tại các thời điểm kiểm tra; không khóa thao tác sửa file từ chương trình khác. Raw giữ toàn bộ dữ liệu gốc; CSV mặc định chỉ chứa hai trận đã chọn.

Trước khi tạo log, pipeline kiểm tra cả CSV, báo cáo, hai ảnh và log: chặn hardlink/cùng file với mọi JSON trong thư mục nguồn (kể cả JSON không được chọn), symlink ở file đầu ra và thư mục `processed` dẫn vào raw. Với nguồn ZIP, chính file ZIP cũng được bảo vệ. Tên đầu ra phải khác nhau kể cả chữ hoa/thường.

Mọi kết quả, kể cả log, được ghi vào thư mục tạm riêng trong `processed`, sau đó đóng log, kiểm tra lại đích rồi dùng `os.replace()` thay từng file. Thay tên file giúp không ghi xuyên vào raw qua hardlink. Lỗi trong khi đọc, kiểm định hoặc ghi tạm sẽ dọn thư mục tạm và giữ nguyên kết quả cũ; lỗi được báo qua màn hình. Mỗi lần thay một file là nguyên tử, cả bộ năm file không phải một giao dịch: nếu lỗi hệ thống xảy ra giữa các lần thay thì kết quả có thể thuộc hai lần chạy. Chạy lại pipeline thành công để có bộ kết quả đồng nhất.

## 3. Thiết lập và chạy

Dùng Python 3.13. Môi trường `.venv` hiện có có thể chạy trực tiếp:

```powershell
cd D:\ML_ck
.\.venv\Scripts\python.exe pipeline.py
.\.venv\Scripts\python.exe kiem_tra_du_lieu.py
```

Trên máy mới, tạo môi trường và cài các thư viện phục vụ tiền xử lý:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe pipeline.py
```

Khi chuyển dự án sang máy khác, giữ các JSON trong `data/raw/events/`. Code tính đường dẫn mặc định từ vị trí dự án, không phụ thuộc thư mục đang đứng hoặc ổ D. Nếu cần nguồn khác, dùng `--input-path` (tên tương đương `--input-dir`).

Vẫn có thể đọc ZIP bằng `--zip-path "duong_dan/events.zip"`; đây là tên tương đương của `--input-path`. Chương trình chỉ đọc ZIP đó, không tự sao chép sang raw. Chỉ trong chế độ ZIP mới kiểm tra và báo MD5/CRC của ZIP. Với nguồn JSON, báo cáo không ghi giả rằng ZIP đã được kiểm chứng.

Mặc định đọc `events_European_Championship.json`, chọn hai trận `1694401` và `1694416`. Kết quả đã đối chiếu: **1.782 dòng, 21 cột, 9 cờ end_unknown, 0 null, không trùng event_id**.

## 4. Các lệnh cho người tiền xử lý

```powershell
# Khảo sát các trận đủ số chuyền và cân bằng trong file Euro mặc định
.\.venv\Scripts\python.exe pipeline.py --propose

# Khảo sát đúng JSON được chỉ định
.\.venv\Scripts\python.exe pipeline.py --propose --json-file events_World_Cup.json

# Chọn trận cụ thể; kiểm tra đủ mã và áp lại tiêu chí chọn mẫu S14
.\.venv\Scripts\python.exe pipeline.py --matches 1694401 1694416

# Xử lý toàn nguồn: vẫn làm sạch, không áp điều kiện chọn mẫu cân bằng
.\.venv\Scripts\python.exe pipeline.py --matches -1

# Đổi nơi lưu processed/; nguồn raw vẫn được giữ tại vị trí đầu vào
.\.venv\Scripts\python.exe pipeline.py --output-dir "data_thu_nghiem"

# Đọc lại CSV của một lần chạy khác
.\.venv\Scripts\python.exe kiem_tra_du_lieu.py --csv-path "data_thu_nghiem/processed/passes_cleaned.csv"
```

`--json-file` nhận một hoặc nhiều tên JSON trực tiếp trong nguồn. `--matches -1` phải dùng riêng. Đường dẫn tương đối do bạn nhập được tính từ thư mục đang chạy lệnh; đường dẫn mặc định được tính từ vị trí dự án.

Khi chọn mẫu bằng `--matches`, **mỗi trận** phải có ≥800 chuyền sạch, đúng hai đội, tỷ lệ chuyền ít/nhiều ≥0,85 và không có dòng bị loại E2/E3. Cả `--propose` lẫn `--matches` đều áp dụng các tiêu chí này. Trận không đạt sẽ báo lỗi, không âm thầm bị loại khỏi danh sách. `--matches -1` là chế độ xử lý toàn nguồn, không yêu cầu mọi trận phải cân bằng; mọi kiểm định dữ liệu vẫn được thực hiện.

## 5. Quy tắc làm sạch và kiểm định

- Lọc đúng `eventName='Pass'` và `eventId=8` trước khi kiểm tra kiểu loại sự kiện phụ (E9).
- Nếu tên Pass và mã 8 không khớp, dừng để kiểm tra thay vì âm thầm bỏ dòng.
- Chỉ nhận đúng hai điểm có x/y; dòng thiếu hoặc thừa điểm được đếm và loại (E2).
- Tọa độ phải biểu diễn số nguyên 0–100. Kiểm tra trước khi ép `int`; không cắt tọa độ sai về biên (E3).
- Giữ điểm cuối (0,0), gắn `end_unknown=True` (E1). Đây là dấu hiệu nghi ngờ điểm cuối chưa rõ, chưa có xác nhận chính thức rằng mọi (0,0) đều là giá trị giữ chỗ.
- Giữ đường chuyền độ dài 0 (E4) và cầu thủ `player_id=0` (E5).
- Thẻ 1801 → `accurate`; 1802 → `not_accurate`; không có cả hai → `unknown`. Nếu mang đồng thời hai thẻ thì dừng để kiểm tra (E6/E12).
- Chia tọa độ cho 100, giữ giá trị biên đúng 0/1 và cả tọa độ gốc (E8).
- Sắp theo trận → hiệp `1H, 2H, E1, E2, P` → giây trong hiệp (E10/E11).
- Kiểm tra đủ các trận yêu cầu và tiêu chí chọn mẫu, kể cả khi nhập mã thủ công (S14/E7).
- Đọc và làm sạch từng JSON, giải phóng đối tượng thô trước khi đọc file tiếp theo. Chỉ giữ bảng cần bàn giao, bộ đếm và ID phục vụ kiểm tra trùng (E13).
- Bảng cuối phải >500 dòng, >10 cột thông tin trích xuất, đúng tên/thứ tự/kiểu 21 cột, không null, không trùng ID, đủ hai đội mỗi trận, đúng công thức chuẩn hóa/dẫn xuất và cờ chất lượng.

Báo cáo ghi riêng số dòng đầu vào, số bị loại E2/E3 và số giữ lại của **toàn nguồn đã đọc** và **phạm vi trận chọn**. Thiếu kết quả trên dữ liệu thô và trên dữ liệu giữ lại cũng được phân biệt.

## 6. Schema dữ liệu bàn giao

| Nhóm | Các cột | Kiểu/ý nghĩa |
|---|---|---|
| Định danh | `event_id`, `match_id`, `team_id`, `player_id`, `sub_event_id` | Số nguyên; player_id=0 là chưa rõ cầu thủ |
| Hiệp/thời gian | `match_period`, `event_sec` | Hiệp hợp lệ; giây hữu hạn, không âm, tính lại mỗi hiệp |
| Loại chuyền | `sub_event_name` | Tên loại chuyền |
| Tọa độ gốc | `x_start`, `y_start`, `x_end`, `y_end` | Số nguyên 0–100 |
| Kết quả | `pass_outcome` | accurate / not_accurate / unknown |
| Tọa độ chuẩn hóa | `x_start_n`, `y_start_n`, `x_end_n`, `y_end_n` | Số thực 0–1 |
| Dẫn xuất | `dx_n`, `dy_n`, `length_n` | Hiệu tọa độ và độ dài trong hệ chuẩn hóa, không phải mét |
| Chất lượng | `end_unknown` | Boolean, khớp điểm cuối (0,0) |

13 cột thông tin được trích từ JSON, cộng 4 tọa độ chuẩn hóa, 3 dẫn xuất và 1 cờ = 21 cột.
Không diễn giải điểm cuối/độ dài trên dòng `end_unknown=True` như thông tin vị trí thật. Hai trận mặc định còn 1.773 dòng nếu bỏ cờ khi đọc thông tin điểm cuối.

## 7. Chạy kiểm thử

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

Kiểm thử dùng dữ liệu nhỏ trong thư mục tạm. Kết quả trên dữ liệu thật được kiểm chứng riêng bằng pipeline và `kiem_tra_du_lieu.py`.

`bao-cao-quet-loi-du-lieu-va-huong-xu-ly.md` là báo cáo khảo sát nguồn và kế hoạch S1–S15. Kết quả của lần chạy hiện tại nằm trong `data/processed/data_quality_report.md`. Kiểm thử có cả trường hợp chạy dự án ở vị trí khác, nguồn JSON trực tiếp, ZIP tùy chọn, nguyên vẹn raw, thiếu trận và mẫu trận không hợp lệ.

Notebook cũ được chuyển vào `ban_nhap/`, giữ nguyên như bản nháp trước khi tách module. Đường dẫn và output cũ trong đó không đại diện cho quy trình hiện tại. Dùng các lệnh `.py` ở trên để chạy hoặc kiểm tra dữ liệu.
