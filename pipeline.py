"""FILE CHẠY CHÍNH — điều phối phần tiền xử lý của người phụ trách dữ liệu.

Thứ tự đọc code: tien_xu_ly/buoc_00_cau_hinh.py → buoc_01 → ... → buoc_06.
Chạy: python pipeline.py
Nguồn mặc định: data/raw/events/. Kết quả: data/processed/.
Chỉ đọc raw, không sao chép hoặc sửa các JSON gốc.
Mỗi file JSON được làm sạch và giải phóng trước khi đọc file kế tiếp.
"""

import argparse
from dataclasses import replace
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from tien_xu_ly.buoc_00_cau_hinh import PipelineConfig, setup_logger
from tien_xu_ly.buoc_00_bao_ve_dau_ra import LOG_NAME, publish_outputs, validate_output_paths
from tien_xu_ly.buoc_01_doc_du_lieu import (
    check_raw_structure, filter_passes, load_raw_events, scan_and_propose_matches,
    validate_json_filenames, verify_input_source, verify_source_unchanged,
)
from tien_xu_ly.buoc_02_lam_sach import QualityMetrics, extract_coordinates_and_clean
from tien_xu_ly.buoc_03_chuan_hoa import normalize_and_add_derived_features, sort_and_finalize
from tien_xu_ly.buoc_04_kiem_dinh import ValidationReport, validate_dataset, validate_match_selection
from tien_xu_ly.buoc_05_ve_du_lieu import generate_pitch_visualizations
from tien_xu_ly.buoc_06_xuat_ket_qua import export_artifacts


def run_pipeline(
    config: PipelineConfig, logger: logging.Logger | None = None,
) -> tuple[pd.DataFrame, ValidationReport]:
    validate_json_filenames(config.json_files)
    if config.target_match_ids is not None and (
        not config.target_match_ids or any(type(mid) is not int or mid <= 0 for mid in config.target_match_ids)
        or len(config.target_match_ids) != len(set(config.target_match_ids))
    ):
        raise ValueError("Mã trận phải là số nguyên dương, không lặp; dùng None hoặc --matches -1 để lấy tất cả.")
    if type(config.min_match_passes) is not int or config.min_match_passes < 1 or not 0 <= config.min_balance_ratio <= 1:
        raise ValueError("Ngưỡng chọn trận không hợp lệ.")
    processed = validate_output_paths(config)
    processed.mkdir(parents=True, exist_ok=True)
    # Tạo thư mục ngẫu nhiên, độc quyền, cùng ổ đĩa với đích để os.replace.
    # Mọi file được ghi ở đây, kể cả log; lỗi ghi không làm hỏng kết quả cũ.
    with TemporaryDirectory(prefix=".pipeline-", dir=processed) as temporary:
        staged_config = replace(config, output_dir=temporary)
        staged_config.processed_dir.mkdir()
        final, validation, verify_meta = _run_staged_pipeline(staged_config, logger)
        publish_outputs(config, staged_config.processed_dir, processed)
        verify_source_unchanged(verify_meta)
    return final, validation


def _run_staged_pipeline(config: PipelineConfig, logger: logging.Logger | None):
    """Chạy các bước vào nơi tạm; đóng log trước khi chuyển file trên Windows."""
    input_path = Path(config.input_path).expanduser().resolve()
    owns_logger = logger is None
    if owns_logger:
        logger = setup_logger(config.processed_dir / LOG_NAME)
    else:
        # Giữ logger của người gọi, chỉ thêm handler cho log của lần chạy này.
        log_handler = logging.FileHandler(config.processed_dir / LOG_NAME, mode="x", encoding="utf-8")
        log_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
        logger.addHandler(log_handler)
    try:
        logger.info("Bắt đầu tiền xử lý | JSON %s | trận %s", config.json_files, config.target_match_ids)
        verify_meta = verify_input_source(str(input_path), config.json_files, logger)
        verify_meta["total_events"] = 0
        frames = []
        metrics = QualityMetrics()
        seen_ids: set[int] = set()
        for filename in config.json_files:
            events = load_raw_events(str(input_path), filename, logger)
            check_raw_structure(events, logger, seen_ids)
            verify_meta["total_events"] += len(events)
            passes = filter_passes(events, logger)
            del events
            # E13: không tích lũy Pass thô của các file đã đọc.
            cleaned, file_metrics = extract_coordinates_and_clean(passes, logger)
            del passes
            metrics.merge(file_metrics)
            if config.target_match_ids is not None:
                cleaned = cleaned[cleaned["match_id"].isin(config.target_match_ids)].copy()
            if not cleaned.empty:
                frames.append(cleaned)
            del cleaned, file_metrics
        del seen_ids
        if not frames:
            raise ValueError("Không có Pass hợp lệ cho các trận/JSON yêu cầu.")
        combined = pd.concat(frames, ignore_index=True)
        del frames
        features = normalize_and_add_derived_features(combined, logger)
        del combined
        final = sort_and_finalize(features, config.target_match_ids, logger)
        del features
        validation = validate_dataset(
            final, logger, min_rows=config.min_row_threshold, min_raw_cols=config.min_col_threshold,
        )
        validation.checks.update(validate_match_selection(
            final, metrics, config.target_match_ids, config.min_match_passes, config.min_balance_ratio,
        ))
        verify_source_unchanged(verify_meta)
        generate_pitch_visualizations(
            final, str(config.processed_dir / config.output_plot_dist),
            str(config.processed_dir / config.output_plot_dir), logger,
        )
        export_artifacts(final, metrics, validation, verify_meta, config, logger)
        verify_source_unchanged(verify_meta)
        logger.info("Hoàn thành kiểm định và ghi tạm: %s dòng × %s cột", *final.shape)
        return final, validation, verify_meta
    except Exception as error:
        logger.error("Tiền xử lý thất bại: %s", error)
        raise
    finally:
        if owns_logger:
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
                handler.close()
        else:
            logger.removeHandler(log_handler)
            log_handler.close()


def main() -> None:
    defaults = PipelineConfig()
    parser = argparse.ArgumentParser(description="Tiền xử lý dữ liệu đường chuyền Wyscout")
    parser.add_argument("--input-path", "--input-dir", "--zip-path", dest="input_path", default=defaults.input_path,
                        help="Thư mục JSON gốc (mặc định data/raw/events) hoặc ZIP tùy chọn; chỉ đọc")
    parser.add_argument("--json-file", nargs="+", default=defaults.json_files, help="Một hoặc nhiều JSON trong nguồn")
    parser.add_argument("--matches", nargs="+", type=int, default=defaults.target_match_ids,
                        help="Danh sách mã trận; dùng riêng -1 để lấy tất cả trận trong JSON đã chọn")
    parser.add_argument("--output-dir", default=defaults.output_dir, help="Thư mục chứa processed/; mặc định data/")
    parser.add_argument("--propose", action="store_true", help="Chỉ đề xuất trận trên các --json-file đã chọn")
    args = parser.parse_args()
    if -1 in args.matches and args.matches != [-1]:
        parser.error("--matches -1 phải dùng riêng, không ghép với mã trận khác.")
    config = PipelineConfig(
        input_path=args.input_path, json_files=args.json_file,
        target_match_ids=None if args.matches == [-1] else args.matches,
        output_dir=args.output_dir,
    )
    try:
        if args.propose:
            logger = setup_logger()
            candidates = scan_and_propose_matches(config.input_path, config.json_files, logger,
                                                  config.min_match_passes, config.min_balance_ratio)
            print(f"Tìm thấy {len(candidates)} trận phù hợp.")
        else:
            run_pipeline(config)
            print(f"Đã lưu kết quả tại: {config.processed_dir.resolve()}")
    except (AssertionError, ValueError, OSError) as error:
        parser.exit(1, f"Lỗi tiền xử lý: {error}\n")


if __name__ == "__main__":
    main()
