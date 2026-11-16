"""BƯỚC 00 — Cấu hình dùng chung, tên cột và nhật ký.

Đọc file này trước: xác định thư mục JSON gốc, các trận cần lấy và nơi xuất kết quả.
Đường dẫn mặc định dựa vào vị trí dự án, không cố định ổ D của một máy.
Chạy toàn bộ các bước bằng `python pipeline.py`, không chạy riêng module này.
"""

from dataclasses import dataclass, field
import logging
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
EXPECTED_ZIP_SIZE = 77_323_413
EXPECTED_ZIP_MD5 = "7c20e8647e7eda58d7838a0c7b1ec6ab"
PERIOD_ORDER = ["1H", "2H", "E1", "E2", "P"]

# 13 cột thông tin được trích từ JSON; không phải 13 trường độc lập trong JSON gốc.
RAW_INFO_COLUMNS = [
    "event_id", "match_id", "team_id", "player_id", "match_period", "event_sec",
    "sub_event_id", "sub_event_name", "x_start", "y_start", "x_end", "y_end",
    "pass_outcome",
]
RAW_COORD_COLUMNS = ["x_start", "y_start", "x_end", "y_end"]
NORM_COORD_COLUMNS = ["x_start_n", "y_start_n", "x_end_n", "y_end_n"]
DERIVED_COLUMNS = ["dx_n", "dy_n", "length_n"]
INT_COLUMNS = [
    "event_id", "match_id", "team_id", "player_id", "sub_event_id", *RAW_COORD_COLUMNS,
]
TEXT_COLUMNS = ["match_period", "sub_event_name", "pass_outcome"]
FINAL_SCHEMA_COLUMNS = [
    *RAW_INFO_COLUMNS, *NORM_COORD_COLUMNS, *DERIVED_COLUMNS, "end_unknown",
]


def default_input_path() -> str:
    """Luôn dùng raw trong dự án; không tự chuyển sang ZIP ở máy người viết."""
    return str(DEFAULT_DATA_DIR / "raw" / "events")


@dataclass
class PipelineConfig:
    input_path: str = field(default_factory=default_input_path)
    json_files: list[str] = field(
        default_factory=lambda: ["events_European_Championship.json"]
    )
    target_match_ids: list[int] | None = field(default_factory=lambda: [1694401, 1694416])
    output_dir: str = field(default_factory=lambda: str(DEFAULT_DATA_DIR))
    output_csv: str = "passes_cleaned.csv"
    output_report: str = "data_quality_report.md"
    output_plot_dist: str = "pitch_pass_distribution.png"
    output_plot_dir: str = "pitch_pass_directions.png"
    min_row_threshold: int = 500
    min_col_threshold: int = 10
    min_match_passes: int = 800
    min_balance_ratio: float = 0.85

    @property
    def processed_dir(self) -> Path:
        return Path(self.output_dir) / "processed"


def setup_logger(log_file: str | Path | None = None) -> logging.Logger:
    """Tạo thư mục trước khi ghi log; đóng handler cũ khi chạy lại trong Python."""
    logger = logging.getLogger("DataPipeline")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    logger.addHandler(stream)
    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, mode="w", encoding="utf-8")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
