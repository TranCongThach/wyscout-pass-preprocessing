"""BƯỚC 03 — Chuẩn hóa, tạo đặc trưng và hoàn thiện bảng (S11–S14).

Đầu vào: bảng đã làm sạch. Đầu ra: đúng 21 cột, đủ tất cả trận được yêu cầu.
Chia tọa độ cho 100, giữ tọa độ gốc; tính dx_n, dy_n và length_n.
Sắp xếp theo trận → thứ tự hiệp → giây trong hiệp; không trộn thời gian hai hiệp.
length_n là độ dài trong hệ chuẩn hóa, không phải mét.
"""

import logging

import numpy as np
import pandas as pd

from .buoc_00_cau_hinh import FINAL_SCHEMA_COLUMNS, PERIOD_ORDER, RAW_COORD_COLUMNS


def normalize_and_add_derived_features(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    result = df.copy()
    for column in RAW_COORD_COLUMNS:
        result[f"{column}_n"] = (result[column] / 100.0).astype(float)
    result["dx_n"] = result["x_end_n"] - result["x_start_n"]
    result["dy_n"] = result["y_end_n"] - result["y_start_n"]
    result["length_n"] = np.hypot(result["dx_n"], result["dy_n"])
    logger.info("S11–S12: chuẩn hóa tọa độ và tạo dx_n, dy_n, length_n cho %s dòng", len(result))
    return result


def sort_and_finalize(
    df: pd.DataFrame, target_match_ids: list[int] | None, logger: logging.Logger,
) -> pd.DataFrame:
    """Không chấp nhận bàn giao thiếu một phần danh sách trận được yêu cầu."""
    if target_match_ids is not None:
        if not target_match_ids:
            raise ValueError("Danh sách trận rỗng; dùng None hoặc --matches -1 để lấy tất cả.")
        missing = set(target_match_ids) - set(df["match_id"])
        if missing:
            raise ValueError(f"Các trận không có dữ liệu hợp lệ trong nguồn đã chọn: {sorted(missing)}")
        result = df[df["match_id"].isin(target_match_ids)].copy()
    else:
        result = df.copy()
    if result.empty:
        raise ValueError("Không còn đường chuyền hợp lệ sau khi lọc và làm sạch.")
    invalid_periods = set(result["match_period"]) - set(PERIOD_ORDER)
    if invalid_periods:
        raise ValueError(f"Hiệp đấu không hợp lệ: {invalid_periods}")
    result["_period_order"] = result["match_period"].map(dict(zip(PERIOD_ORDER, range(5))))
    result = result.sort_values(
        ["match_id", "_period_order", "event_sec"], kind="stable",
    ).drop(columns="_period_order")
    result = result.loc[:, FINAL_SCHEMA_COLUMNS].reset_index(drop=True)
    logger.info("S13–S14: đủ phạm vi trận; bảng cuối %s dòng × %s cột", *result.shape)
    return result
