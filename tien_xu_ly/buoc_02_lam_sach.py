"""BƯỚC 02 — Làm sạch Pass và ghi bộ đếm toàn nguồn/theo từng trận (S5–S10).

Đầu vào: Pass từ bước 01. Đầu ra: 13 cột thông tin + cờ end_unknown và nhật ký.
E2: yêu cầu ĐÚNG hai điểm. E3: tọa độ phải biểu diễn số nguyên trong [0,100].
E1/E4/E5: giữ dòng điểm cuối (0,0), độ dài 0 và playerId=0; ghi cờ/bộ đếm.
E6: thiếu thẻ kết quả → unknown; hai thẻ kết quả mâu thuẫn → dừng để kiểm tra.
"""

from dataclasses import dataclass, field
import logging
import math
from numbers import Real

import pandas as pd

from .buoc_00_cau_hinh import PERIOD_ORDER, RAW_INFO_COLUMNS

METRIC_NAMES = (
    "total_passes_input", "e2_dropped_incomplete_pos", "e3_dropped_out_of_bounds",
    "valid_passes_retained", "e1_flagged_end_unknown", "e4_zero_length_passes",
    "e5_unknown_player_id", "e6_outcome_accurate", "e6_outcome_not_accurate",
    "e6_outcome_unknown", "boundary_coordinates_count", "e6_unknown_input",
)


@dataclass
class QualityMetrics:
    total_passes_input: int = 0
    e2_dropped_incomplete_pos: int = 0
    e3_dropped_out_of_bounds: int = 0
    valid_passes_retained: int = 0
    e1_flagged_end_unknown: int = 0
    e4_zero_length_passes: int = 0
    e5_unknown_player_id: int = 0
    e6_outcome_accurate: int = 0
    e6_outcome_not_accurate: int = 0
    e6_outcome_unknown: int = 0
    boundary_coordinates_count: int = 0
    e6_unknown_input: int = 0
    by_match: dict[int, dict[str, int]] = field(default_factory=dict)

    def count(self, name: str, match_id: int, amount: int = 1) -> None:
        """Cập nhật đồng thời tổng nguồn và đúng trận của dòng đang xử lý."""
        setattr(self, name, getattr(self, name) + amount)
        if match_id not in self.by_match:
            self.by_match[match_id] = dict.fromkeys(METRIC_NAMES, 0)
        counters = self.by_match[match_id]
        counters[name] += amount

    def merge(self, other: "QualityMetrics") -> None:
        """Cộng nhật ký các file sau khi đã giải phóng dữ liệu thô của từng file."""
        for match_id, counters in other.by_match.items():
            for name, amount in counters.items():
                self.count(name, match_id, amount)

    def for_matches(self, match_ids: list[int] | None) -> "QualityMetrics":
        """Lấy cả số dòng vào và số bị loại của phạm vi chọn, không đếm từ CSV sạch."""
        selected = QualityMetrics()
        wanted = self.by_match if match_ids is None else dict.fromkeys(match_ids)
        for match_id in wanted:
            for name, amount in self.by_match.get(match_id, {}).items():
                selected.count(name, match_id, amount)
        return selected


def _require_int(value: object, name: str, event_id: object, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"Pass {event_id}: {name} phải là số nguyên >= {minimum}, nhận {value!r}.")
    return value


def _decode_outcome(event: dict) -> str:
    tags = event["tags"]
    if not isinstance(tags, list) or any(
        not isinstance(t, dict) or type(t.get("id")) is not int for t in tags
    ):
        raise ValueError(f"Pass {event['id']}: tags sai cấu trúc.")
    ids = {t["id"] for t in tags}
    if {1801, 1802}.issubset(ids):
        raise ValueError(f"Pass {event['id']}: có cả hai thẻ kết quả 1801 và 1802.")
    if 1801 in ids:
        return "accurate"
    if 1802 in ids:
        return "not_accurate"
    return "unknown"


def extract_coordinates_and_clean(
    passes: list[dict], logger: logging.Logger,
) -> tuple[pd.DataFrame, QualityMetrics]:
    metrics = QualityMetrics()
    records = []
    for event in passes:
        event_id = _require_int(event["id"], "id", event.get("id"), 1)
        match_id = _require_int(event["matchId"], "matchId", event_id, 1)
        team_id = _require_int(event["teamId"], "teamId", event_id, 1)
        player_id = _require_int(event["playerId"], "playerId", event_id)
        sub_id = _require_int(event["subEventId"], "subEventId", event_id, 1)
        period, seconds = event["matchPeriod"], event["eventSec"]
        if period not in PERIOD_ORDER:
            raise ValueError(f"Pass {event_id}: matchPeriod không hợp lệ: {period!r}.")
        if isinstance(seconds, bool) or not isinstance(seconds, Real) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError(f"Pass {event_id}: eventSec phải hữu hạn và không âm.")
        if not isinstance(event["subEventName"], str) or not event["subEventName"].strip():
            raise ValueError(f"Pass {event_id}: subEventName bị thiếu hoặc sai kiểu.")
        outcome = _decode_outcome(event)
        metrics.count("total_passes_input", match_id)
        if outcome == "unknown":
            metrics.count("e6_unknown_input", match_id)

        # S5: đủ hai dict chứa cả x/y, không tự bỏ qua điểm thứ ba.
        positions = event["positions"]
        if not isinstance(positions, list) or len(positions) != 2 or any(
            not isinstance(pos, dict) or pos.get("x") is None or pos.get("y") is None
            for pos in positions
        ):
            metrics.count("e2_dropped_incomplete_pos", match_id)
            continue
        coordinates = [positions[0]["x"], positions[0]["y"], positions[1]["x"], positions[1]["y"]]
        # S6: kiểm tra TRƯỚC int(), tránh biến -0.9/100.9 thành 0/100.
        if any(
            isinstance(c, bool) or not isinstance(c, Real) or not math.isfinite(c)
            or not 0 <= c <= 100 or int(c) != c for c in coordinates
        ):
            metrics.count("e3_dropped_out_of_bounds", match_id)
            continue
        x0, y0, x1, y1 = map(int, coordinates)
        end_unknown = x1 == 0 and y1 == 0
        for name, condition in (
            ("e1_flagged_end_unknown", end_unknown),
            ("e4_zero_length_passes", x0 == x1 and y0 == y1),
            ("e5_unknown_player_id", player_id == 0),
            ("boundary_coordinates_count", any(c in (0, 100) for c in coordinates)),
        ):
            if condition:
                metrics.count(name, match_id)
        metrics.count(f"e6_outcome_{outcome}", match_id)
        metrics.count("valid_passes_retained", match_id)
        records.append({
            "event_id": event_id, "match_id": match_id, "team_id": team_id,
            "player_id": player_id, "match_period": period, "event_sec": float(seconds),
            "sub_event_id": sub_id, "sub_event_name": event["subEventName"],
            "x_start": x0, "y_start": y0, "x_end": x1, "y_end": y1,
            "pass_outcome": outcome, "end_unknown": end_unknown,
        })
    logger.info("S5–S10: vào %s | loại E2 %s | loại E3 %s | giữ %s | cờ E1 %s",
                metrics.total_passes_input, metrics.e2_dropped_incomplete_pos,
                metrics.e3_dropped_out_of_bounds, metrics.valid_passes_retained,
                metrics.e1_flagged_end_unknown)
    # Kể cả không có dòng giữ lại vẫn trả đúng tên cột để bước sau báo lỗi rõ ràng.
    return pd.DataFrame.from_records(records, columns=[*RAW_INFO_COLUMNS, "end_unknown"]), metrics
