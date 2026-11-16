"""BƯỚC 04 — Kiểm định bảng cuối và tiêu chí chọn mẫu (S14–S15).

Kiểm tra tên/thứ tự/kiểu cột, null, ID, số đội, giá trị tọa độ, cờ E1,
công thức chuẩn hóa/dẫn xuất, hiệp và thời gian. Không đếm cột bằng hằng số.
Bảng không đạt hoặc mẫu trận không đạt sẽ dừng, không xuất báo cáo PASS.
"""

from dataclasses import dataclass
import logging

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_float_dtype, is_integer_dtype

from .buoc_00_cau_hinh import (
    DERIVED_COLUMNS, FINAL_SCHEMA_COLUMNS, INT_COLUMNS, NORM_COORD_COLUMNS,
    PERIOD_ORDER, RAW_COORD_COLUMNS, RAW_INFO_COLUMNS, TEXT_COLUMNS,
)
from .buoc_02_lam_sach import QualityMetrics


def validate_match_selection(
    df: pd.DataFrame, metrics: QualityMetrics, target_match_ids: list[int] | None,
    min_passes: int = 800, min_ratio: float = 0.85,
) -> dict[str, bool]:
    """S14: áp dụng tiêu chí chọn mẫu cả khi người dùng tự nhập --matches.

    target_match_ids=None là chế độ xử lý toàn nguồn: vẫn làm sạch/kiểm định,
    nhưng không loại trận chỉ vì ít chuyền hoặc thiếu cân bằng.
    """
    if target_match_ids is None:
        return {}
    errors = []
    for match_id in target_match_ids:
        group = df[df["match_id"] == match_id]
        counts = group.groupby("team_id").size()
        audit = metrics.by_match.get(match_id)
        if group.empty or audit is None:
            errors.append(f"trận {match_id} không có dữ liệu hợp lệ")
            continue
        if len(counts) != 2:
            errors.append(f"trận {match_id} không có đúng hai đội")
        elif counts.min() / counts.max() < min_ratio:
            errors.append(f"trận {match_id}: tỷ lệ cân bằng {counts.min()/counts.max():.4f} < {min_ratio}")
        if len(group) < min_passes:
            errors.append(f"trận {match_id}: {len(group)} chuyền < {min_passes}")
        e2, e3 = audit["e2_dropped_incomplete_pos"], audit["e3_dropped_out_of_bounds"]
        if e2 or e3:
            errors.append(f"trận {match_id} có dòng bị loại E2={e2}, E3={e3}")
    if errors:
        raise ValueError("S14: mẫu trận không đạt: " + "; ".join(errors) + ". Dùng --propose để khảo sát trận phù hợp.")
    return {
        f"S14: mỗi trận chọn có ít nhất {min_passes} chuyền": True,
        f"S14: tỷ lệ cân bằng mỗi trận >= {min_ratio}": True,
        "S14: các trận chọn không có dòng bị loại E2/E3": True,
    }


@dataclass
class ValidationReport:
    row_count: int
    row_count_valid: bool
    raw_col_count: int
    raw_col_count_valid: bool
    total_col_count: int
    total_col_count_valid: bool
    null_counts: dict[str, int]
    no_nulls_valid: bool
    is_event_id_unique: bool
    coord_norm_valid: bool
    teams_per_match: dict[int, int]
    teams_per_match_valid: bool
    all_passed: bool
    checks: dict[str, bool]


def validate_dataset(
    df: pd.DataFrame, logger: logging.Logger, min_rows: int = 500, min_raw_cols: int = 10,
) -> ValidationReport:
    if list(df.columns) != FINAL_SCHEMA_COLUMNS:
        missing = sorted(set(FINAL_SCHEMA_COLUMNS) - set(df.columns))
        extra = sorted(set(df.columns) - set(FINAL_SCHEMA_COLUMNS))
        raise AssertionError(f"Schema sai tên/thứ tự 21 cột. Thiếu: {missing}; thừa: {extra}.")
    if min_rows < 0 or min_raw_cols < 0:
        raise ValueError("Ngưỡng kiểm định phải không âm.")
    bad_types = [c for c in INT_COLUMNS if not is_integer_dtype(df[c].dtype)]
    bad_types += [c for c in ["event_sec", *NORM_COORD_COLUMNS, *DERIVED_COLUMNS]
                  if not is_float_dtype(df[c].dtype)]
    if not is_bool_dtype(df["end_unknown"].dtype):
        bad_types.append("end_unknown")
    bad_types += [c for c in TEXT_COLUMNS if not df[c].map(
        lambda value: isinstance(value, str) and bool(value.strip())
    ).all()]
    if bad_types:
        raise AssertionError(f"Kiểu dữ liệu/chuỗi không hợp lệ tại: {bad_types}")

    null_counts = {c: int(n) for c, n in df.isna().sum().items()}
    raw_count = sum(c in df.columns for c in RAW_INFO_COLUMNS)
    teams = {int(k): int(v) for k, v in df.groupby("match_id")["team_id"].nunique().items()}
    raw = df[RAW_COORD_COLUMNS].to_numpy(dtype=float, na_value=np.nan)
    norm = df[NORM_COORD_COLUMNS].to_numpy(dtype=float, na_value=np.nan)
    derived = df[DERIVED_COLUMNS].to_numpy(dtype=float, na_value=np.nan)
    seconds = df["event_sec"].to_numpy(dtype=float, na_value=np.nan)
    deltas = norm[:, 2:] - norm[:, :2]
    expected_derived = np.column_stack((deltas, np.hypot(deltas[:, 0], deltas[:, 1])))
    period_indices = df["match_period"].map(dict(zip(PERIOD_ORDER, range(5))))
    chronology = pd.MultiIndex.from_arrays([df["match_id"], period_indices, df["event_sec"]])
    id_columns = ["event_id", "match_id", "team_id", "sub_event_id"]

    checks = {
        f"Số dòng > {min_rows}": len(df) > min_rows,
        f"Số cột thông tin trích xuất > {min_raw_cols}": raw_count > min_raw_cols,
        "Đúng tên, thứ tự và kiểu 21 cột": True,
        "Không có null": sum(null_counts.values()) == 0,
        "event_id duy nhất": bool(df["event_id"].is_unique),
        "ID hợp lệ, player_id=0 được giữ": bool(
            (df[id_columns] > 0).all().all() and (df["player_id"] >= 0).all()
        ),
        "Tọa độ gốc nguyên trong [0,100]": bool(np.isfinite(raw).all() and ((0 <= raw) & (raw <= 100)).all()),
        "Bốn tọa độ chuẩn hóa trong [0,1]": bool(np.isfinite(norm).all() and ((0 <= norm) & (norm <= 1)).all()),
        "Chuẩn hóa đúng bằng tọa độ gốc / 100": bool(np.allclose(norm, raw / 100, rtol=0, atol=1e-12)),
        "dx_n, dy_n, length_n đúng công thức": bool(
            np.isfinite(derived).all() and np.allclose(derived, expected_derived, rtol=0, atol=1e-12)
            and (df["length_n"] >= 0).all()
        ),
        "end_unknown khớp điểm cuối (0,0)": bool(df["end_unknown"].eq(df["x_end"].eq(0) & df["y_end"].eq(0)).all()),
        "Nhãn kết quả đúng tập giá trị": bool(df["pass_outcome"].isin(["accurate", "not_accurate", "unknown"]).all()),
        "Hiệp hợp lệ; giây hữu hạn, không âm": bool(period_indices.notna().all() and np.isfinite(seconds).all() and (seconds >= 0).all()),
        "Thứ tự trận → hiệp → giây": bool(chronology.is_monotonic_increasing),
        "Đúng hai đội mỗi trận": bool(teams) and all(n == 2 for n in teams.values()),
    }
    for name, passed in checks.items():
        logger.info("S15: %s — %s", name, "PASS" if passed else "FAIL")
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise AssertionError("Kiểm định thất bại: " + "; ".join(failed))
    return ValidationReport(
        row_count=len(df), row_count_valid=len(df) > min_rows,
        raw_col_count=raw_count, raw_col_count_valid=raw_count > min_raw_cols,
        total_col_count=df.shape[1], total_col_count_valid=True,
        null_counts=null_counts, no_nulls_valid=True, is_event_id_unique=True,
        coord_norm_valid=True, teams_per_match=teams, teams_per_match_valid=True,
        all_passed=True, checks=checks,
    )
