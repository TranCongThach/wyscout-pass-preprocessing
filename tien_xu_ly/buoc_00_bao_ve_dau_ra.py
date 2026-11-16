"""BƯỚC 00A — Bảo vệ raw trước khi tạo log và công bố kết quả.

Đầu vào: cấu hình đường dẫn. Đầu ra: thư mục processed đã kiểm tra an toàn.
Pipeline ghi CSV, ảnh, báo cáo và log vào thư mục tạm riêng trước khi gọi
publish_outputs. os.replace thay từng tên file, không ghi xuyên hardlink.
Đọc sau buoc_00_cau_hinh.py, trước các bước đọc và làm sạch dữ liệu.
"""

import os
from pathlib import Path

from .buoc_00_cau_hinh import PipelineConfig

LOG_NAME = "pipeline_execution.log"


def output_names(config: PipelineConfig) -> list[str]:
    return [config.output_csv, config.output_report, config.output_plot_dist,
            config.output_plot_dir, LOG_NAME]


def validate_output_paths(config: PipelineConfig) -> Path:
    """Chỉ đọc đường dẫn; phải gọi trước mkdir, setup_logger hoặc ghi file."""
    names = output_names(config)
    if (any(not name or name in {".", ".."} or Path(name).name != name
            or os.path.isreserved(name) for name in names)
            or len({name.casefold() for name in names}) != len(names)):
        raise ValueError("Tên file đầu ra phải khác nhau và là tên trực tiếp trong processed/.")
    source = Path(config.input_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Không tìm thấy nguồn: {source}")
    processed = config.processed_dir.expanduser().resolve()
    if source.is_dir() and processed.is_relative_to(source):
        raise ValueError("Thư mục processed phải nằm ngoài thư mục JSON gốc.")
    # Bảo vệ cả JSON không được chọn; không chỉ các file trong --json-file.
    raw_files = ([path for path in source.iterdir()
                  if path.suffix.lower() == ".json" and path.is_file()]
                 if source.is_dir() else [source])
    for name in names:
        target = processed / name
        # Kiểm tra liên kết trước exists(): symlink đứt vẫn phải bị từ chối.
        if target.is_symlink() or target.is_junction():
            raise ValueError(f"File đầu ra không được là symlink/junction: {target}")
        if target.is_dir():
            raise ValueError(f"Đường dẫn file đầu ra đang là thư mục: {target}")
        if target.exists() and any(target.samefile(raw) for raw in raw_files):
            raise ValueError(f"File đầu ra trùng dữ liệu raw (hardlink/cùng file): {target}")
    return processed


def publish_outputs(config: PipelineConfig, staging_dir: Path, processed: Path) -> None:
    """Kiểm tra lại rồi thay từng file hoàn chỉnh; log phải được đóng trước đó.

    Mỗi os.replace là một lần thay file; cả bộ kết quả không phải một giao dịch.
    Không resolve tên file đích: thay mục tên, không mở đích của liên kết.
    """
    if validate_output_paths(config) != processed:
        raise ValueError("Thư mục đầu ra đã thay đổi trong khi xử lý.")
    names = output_names(config)
    for name in names:
        if not (staging_dir / name).is_file():
            raise ValueError(f"Thiếu file kết quả tạm: {name}")
    for name in names:
        os.replace(staging_dir / name, processed / name)
