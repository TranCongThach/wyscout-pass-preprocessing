"""BƯỚC 06 — Xuất CSV đã kiểm định và báo cáo chất lượng tiền xử lý (S16).

Đầu ra nằm trong data/processed/. Nguồn mặc định là các JSON tại data/raw/events/.
Ghi SHA-256 của đúng các file đã đọc; chỉ ghi MD5/CRC nếu thật sự đọc ZIP.
Số bị loại của phạm vi chọn lấy từ bộ đếm trước làm sạch, không ghi cứng 0.
Báo cáo mô tả nguồn, từng quy tắc và schema; không chứa nhiệm vụ mô hình.
"""

from datetime import datetime, timedelta, timezone
import logging

import pandas as pd

from .buoc_00_cau_hinh import NORM_COORD_COLUMNS, PipelineConfig
from .buoc_02_lam_sach import QualityMetrics
from .buoc_04_kiem_dinh import ValidationReport


def export_artifacts(
    df: pd.DataFrame, metrics: QualityMetrics, val_report: ValidationReport,
    verify_meta: dict, config: PipelineConfig, logger: logging.Logger,
) -> None:
    """Chỉ được gọi sau khi tất cả kiểm định đạt; mọi thống kê lấy từ lần chạy này."""
    if not val_report.all_passed:
        raise ValueError("Không xuất kết quả khi kiểm định chưa đạt.")
    if not verify_meta["unchanged"]:
        raise ValueError("Chưa xác minh nguồn giữ nguyên sau khi đọc.")
    selected = metrics.for_matches(config.target_match_ids)
    for audit in [metrics, selected]:
        if audit.total_passes_input != (
            audit.e2_dropped_incomplete_pos + audit.e3_dropped_out_of_bounds + audit.valid_passes_retained
        ):
            raise AssertionError("Nhật ký không cân bằng: dòng vào != dòng loại + dòng giữ.")
    if selected.valid_passes_retained != len(df):
        raise AssertionError("Số dòng bàn giao không khớp nhật ký của phạm vi chọn.")
    config.processed_dir.mkdir(parents=True, exist_ok=True)
    csv_path = config.processed_dir / config.output_csv
    rules = [
        ("S4", "Pass đầu vào", "total_passes_input"),
        ("S5 / E2", "Loại: không đúng hai điểm hoặc thiếu tọa độ", "e2_dropped_incomplete_pos"),
        ("S6 / E3", "Loại: tọa độ không biểu diễn số nguyên trong [0,100]", "e3_dropped_out_of_bounds"),
        ("Sau S5–S6", "Pass hợp lệ còn lại", "valid_passes_retained"),
        ("S7 / E1", "Giữ và gắn cờ điểm cuối (0,0)", "e1_flagged_end_unknown"),
        ("S8 / E6", "Thiếu thẻ kết quả trên Pass đầu vào", "e6_unknown_input"),
        ("S8", "Chính xác trên các dòng giữ lại", "e6_outcome_accurate"),
        ("S8", "Không chính xác trên các dòng giữ lại", "e6_outcome_not_accurate"),
        ("S8", "Chưa rõ kết quả trên các dòng giữ lại", "e6_outcome_unknown"),
        ("S9 / E5", "Giữ player_id=0", "e5_unknown_player_id"),
        ("S10 / E4", "Giữ điểm đầu trùng điểm cuối", "e4_zero_length_passes"),
        ("S11 / E8", "Dòng có tọa độ 0 hoặc 100", "boundary_coordinates_count"),
    ]
    audit_rows = "\n".join(
        f"| {step} | {description} | {getattr(metrics, name):,} | {getattr(selected, name):,} |"
        for step, description, name in rules
    )
    check_rows = "\n".join(
        f"| {name} | {'PASS' if passed else 'FAIL'} |" for name, passed in val_report.checks.items()
    )
    coord_rows = "\n".join(
        f"| {c} | {df[c].min():.2f} | {df[c].max():.2f} |" for c in NORM_COORD_COLUMNS
    )
    match_rows = []
    for match_id, group in df.groupby("match_id"):
        teams = group.groupby("team_id").size()
        counts = "; ".join(f"{team}: {count:,}" for team, count in teams.items())
        match_rows.append(f"| {match_id} | {len(group):,} | {counts} | {teams.min() / teams.max():.4f} |")
    schema_rows = "\n".join(f"| {c} | {df[c].dtype} | {int(df[c].isna().sum())} |" for c in df)
    norm_min = df[NORM_COORD_COLUMNS].min().min()
    norm_max = df[NORM_COORD_COLUMNS].max().max()
    timestamp = datetime.now(timezone(timedelta(hours=7))).isoformat(timespec="seconds")
    source_names = ", ".join(config.json_files)
    file_rows = "\n".join(
        f"| {entry['name']} | {entry['size_bytes']:,} | `{entry['sha256']}` |"
        for entry in verify_meta["files"]
    )
    zip_meta = verify_meta["zip_meta"]
    if zip_meta is None:
        archive_note = (
            "Nguồn là thư mục JSON đã giải nén. Không áp dụng kích thước/MD5/CRC của ZIP; "
            "không kết luận ZIP tham chiếu đã được kiểm chứng trong lần chạy này."
        )
    else:
        archive_note = (
            f"ZIP: {zip_meta['actual_size']:,} byte; MD5 `{zip_meta['actual_md5']}`; CRC ĐẠT. "
            f"So với tham chiếu: kích thước {'KHỚP' if zip_meta['size_matched'] else 'KHÁC'}, "
            f"MD5 {'KHỚP' if zip_meta['md5_matched'] else 'KHÁC'}. "
            f"SHA-256 ZIP: `{verify_meta['archive_sha256']}`."
        )
    selection_note = (
        f"Chọn mẫu: mỗi trận ≥ {config.min_match_passes} chuyền, tỷ lệ ít/nhiều ≥ "
        f"{config.min_balance_ratio}, không có dòng bị loại E2/E3. Đã kiểm tra lại cả khi nhập --matches."
        if config.target_match_ids is not None else
        "Chế độ toàn nguồn (--matches -1): làm sạch mọi trận; không áp dụng điều kiện chọn mẫu cân bằng."
    )
    report = f"""# Báo cáo chất lượng dữ liệu tiền xử lý

Vai trò: thành viên phụ trách tiền xử lý dữ liệu Wyscout.  
Thời gian: {timestamp} (UTC+07:00).  
Phạm vi yêu cầu: {config.target_match_ids if config.target_match_ids is not None else 'tất cả trận trong các JSON đã chọn'}.  
Kết quả: **{len(df):,} dòng × {df.shape[1]} cột**, {val_report.raw_col_count} cột thông tin trích xuất.

## 1. Nguồn dữ liệu thực sự đã đọc

| Thuộc tính | Giá trị |
|---|---|
| Nguồn được đọc | `{verify_meta['input_path']}` |
| Loại nguồn | {verify_meta['source_kind']} |
| JSON được xử lý lần lượt | `{source_names}` |
| Số sự kiện trước khi lọc Pass | {verify_meta['total_events']:,} |
| So SHA-256 trước/sau khi đọc | ĐẠT — nội dung nguồn không thay đổi |
| Trường bắt buộc và ID trong/giữa các file đọc | ĐẠT |

| JSON đã đọc | Kích thước (byte) | SHA-256 |
|---|---:|---|
{file_rows}

{archive_note}

Pipeline chỉ đọc nguồn; không sao chép, giải nén thêm hoặc ghi đè dữ liệu gốc.
CSV chứa phạm vi được yêu cầu, không mặc nhiên chứa toàn bộ các giải trong thư mục raw.

{selection_note}

## 2. Nhật ký làm sạch trước và sau khi chọn trận

| Bước | Xử lý | Toàn bộ JSON đã đọc | Phạm vi trận chọn |
|---|---|---:|---:|
{audit_rows}

Đối chiếu phạm vi chọn: **{selected.total_passes_input:,} vào − {selected.e2_dropped_incomplete_pos:,} E2 − {selected.e3_dropped_out_of_bounds:,} E3 = {len(df):,} dòng bàn giao**.
E1/E4/E5 là số dòng giữ lại có đặc điểm tương ứng, không phải số dòng bị xóa.

## 3. Kiểm định bảng cuối

| Kiểm tra | Kết quả |
|---|---|
{check_rows}

| Cột tọa độ chuẩn hóa | Min | Max |
|---|---:|---:|
{coord_rows}

Min/Max của **cả bốn cột**: {norm_min:.2f} / {norm_max:.2f}.

## 4. Phân bố dữ liệu bàn giao

| Trận | Số chuyền sạch | Số chuyền theo team_id | Tỷ lệ ít/nhiều |
|---|---:|---|---:|
{chr(10).join(match_rows)}

| Cột bàn giao | Kiểu dữ liệu | Số null |
|---|---|---:|
{schema_rows}

## 5. Ghi chú đọc dữ liệu

- Tọa độ gốc 0–100 và tọa độ chuẩn hóa 0–1 đều được giữ; giá trị đúng 0 hoặc 1 là hợp lệ.
- `end_unknown=True` đánh dấu điểm cuối (0,0) nghi ngờ chưa rõ; đây là quy ước xử lý dựa trên dấu hiệu dữ liệu, chưa phải xác nhận chính thức của nhà cung cấp.
- Có **{selected.e1_flagged_end_unknown:,} dòng** mang cờ; còn **{len(df) - selected.e1_flagged_end_unknown:,} dòng** khi loại cờ để đọc thông tin điểm cuối.
- `dx_n`, `dy_n`, `length_n` dùng hệ chuẩn hóa, không phải mét; không diễn giải điểm cuối/độ dài của dòng mang cờ E1 như vị trí thật.
- `player_id=0` nghĩa là chưa rõ cầu thủ; `pass_outcome=unknown` nghĩa là thiếu thẻ 1801/1802. Không đổi chúng thành cầu thủ thật hoặc chuyền hỏng.
- Thời gian `event_sec` tính lại từ đầu mỗi hiệp. Bảng được sắp theo trận, hiệp rồi giây.
- Báo cáo và hình ảnh này mô tả chất lượng/phân bố dữ liệu tiền xử lý.
"""
    report_path = config.processed_dir / config.output_report
    df.to_csv(csv_path, index=False, encoding="utf-8")
    report_path.write_text(report, encoding="utf-8")
    logger.info("S16: đã xuất %s và %s", csv_path, report_path)
