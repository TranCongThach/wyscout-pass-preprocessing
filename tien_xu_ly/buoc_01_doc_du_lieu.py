"""BƯỚC 01 — Kiểm tra nguồn, đọc JSON, kiểm tra cấu trúc và lọc Pass (S1–S4).

Đầu vào: thư mục data/raw/events (hoặc ZIP tùy chọn). Đầu ra: sự kiện Pass.
Chỉ đọc dữ liệu gốc; ghi SHA-256 trước/sau, không sao chép hoặc ghi đè raw.
Luôn lọc Pass trước khi kiểm tra kiểu subEventId: Offside có thể có chuỗi rỗng.
Hàm đề xuất trận là bước khảo sát dữ liệu tùy chọn, dùng cùng quy tắc làm sạch.
"""

from dataclasses import dataclass
import hashlib
import json
import logging
from pathlib import Path
import zipfile

from .buoc_00_cau_hinh import EXPECTED_ZIP_MD5, EXPECTED_ZIP_SIZE
from .buoc_02_lam_sach import extract_coordinates_and_clean

EXPECTED_RAW_FIELDS = {
    "id", "eventId", "eventName", "subEventId", "subEventName", "matchId",
    "teamId", "playerId", "matchPeriod", "eventSec", "positions", "tags",
}


def verify_raw_file(
    zip_path: str, logger: logging.Logger,
    expected_size: int = EXPECTED_ZIP_SIZE, expected_md5: str = EXPECTED_ZIP_MD5,
) -> dict:
    """Kiểm tra tồn tại, MD5 và CRC; khác bản tham chiếu được ghi rõ trong báo cáo."""
    path = Path(zip_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy ZIP: {path}. Hãy dùng --zip-path.")
    with path.open("rb") as source:
        actual_md5 = hashlib.file_digest(source, "md5").hexdigest()
    try:
        with zipfile.ZipFile(path) as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                raise ValueError(f"Lỗi CRC trong ZIP: {bad_member}")
    except zipfile.BadZipFile as error:
        raise ValueError(f"Nguồn không phải ZIP hợp lệ: {path}") from error
    actual_size = path.stat().st_size
    meta = {
        "zip_path": str(path), "actual_size": actual_size,
        "expected_size": expected_size, "size_matched": actual_size == expected_size,
        "actual_md5": actual_md5, "expected_md5": expected_md5,
        "md5_matched": actual_md5 == expected_md5.lower(), "crc_valid": True,
    }
    logger.info("S1: ZIP %s | %s byte | MD5 %s | CRC đạt", path, actual_size, actual_md5)
    if not (meta["size_matched"] and meta["md5_matched"]):
        logger.warning("ZIP khác bản tham chiếu; báo cáo sẽ ghi số liệu của nguồn thực tế.")
    return meta


def validate_json_filenames(json_filenames: list[str]) -> None:
    if not json_filenames or len(json_filenames) != len(set(json_filenames)):
        raise ValueError("Cần danh sách JSON không rỗng và không lặp tên.")
    for name in json_filenames:
        if not name or Path(name).name != name or not name.endswith(".json"):
            raise ValueError(f"Tên JSON phải là tên file .json trực tiếp trong nguồn: {name!r}")


def _json_path(source: Path, filename: str) -> Path:
    path = (source / filename).resolve()
    if not path.is_relative_to(source) or not path.is_file():
        raise ValueError(f"Không tìm thấy JSON hợp lệ {filename!r} trong {source}")
    return path


def verify_input_source(input_path: str, json_filenames: list[str], logger: logging.Logger) -> dict:
    """S1: xác minh đúng các file sẽ đọc; chỉ kiểm tra MD5/CRC khi đầu vào là ZIP."""
    validate_json_filenames(json_filenames)
    source = Path(input_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Không tìm thấy nguồn: {source}. Hãy kiểm tra --input-path.")
    metadata = {"input_path": str(source), "source_kind": "directory" if source.is_dir() else "zip",
                "files": [], "zip_meta": None, "unchanged": False}
    if source.is_dir():
        for name in json_filenames:
            path = _json_path(source, name)
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            metadata["files"].append({"name": name, "size_bytes": path.stat().st_size, "sha256": digest})
    else:
        metadata["zip_meta"] = verify_raw_file(str(source), logger)
        with source.open("rb") as stream:
            metadata["archive_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
        with zipfile.ZipFile(source) as archive:
            for name in json_filenames:
                if name not in archive.namelist():
                    raise ValueError(f"Không có {name!r} trong ZIP: {source}")
                with archive.open(name) as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                metadata["files"].append({"name": name, "size_bytes": archive.getinfo(name).file_size,
                                          "sha256": digest})
    logger.info("S1: nguồn %s | %s | %s JSON đã ghi SHA-256", metadata["source_kind"], source, len(json_filenames))
    return metadata


def verify_source_unchanged(metadata: dict) -> None:
    """Dừng trước khi xuất nếu nguồn đã thay đổi so với lúc bắt đầu đọc."""
    source = Path(metadata["input_path"])
    if metadata["source_kind"] == "zip":
        with source.open("rb") as stream:
            unchanged = hashlib.file_digest(stream, "sha256").hexdigest() == metadata["archive_sha256"]
    else:
        unchanged = True
        for entry in metadata["files"]:
            with _json_path(source, entry["name"]).open("rb") as stream:
                unchanged = unchanged and hashlib.file_digest(stream, "sha256").hexdigest() == entry["sha256"]
    if not unchanged:
        raise ValueError("Nguồn dữ liệu đã thay đổi trong khi xử lý; không xuất kết quả.")
    metadata["unchanged"] = True


def load_raw_events(input_path: str, json_filename: str, logger: logging.Logger) -> list[dict]:
    """S2: đọc đúng một JSON từ thư mục hoặc ZIP, không ghi vào nguồn."""
    validate_json_filenames([json_filename])
    path = Path(input_path).expanduser().resolve()
    if path.is_dir():
        with _json_path(path, json_filename).open("rb") as source:
            events = json.load(source)
    else:
        with zipfile.ZipFile(path) as archive:
            if json_filename not in archive.namelist():
                raise ValueError(f"Không có {json_filename!r} trong ZIP: {archive.namelist()}")
            with archive.open(json_filename) as source:
                events = json.load(source)
    if not isinstance(events, list):
        raise ValueError(f"{json_filename}: JSON gốc phải là danh sách sự kiện.")
    logger.info("S2: %s — %s sự kiện", json_filename, len(events))
    return events


def check_raw_structure(
    events: list[dict], logger: logging.Logger, seen_event_ids: set[int] | None = None,
) -> dict:
    """Kiểm tra trường bắt buộc và ID; có thể kiểm tra trùng giữa nhiều file."""
    seen = seen_event_ids if seen_event_ids is not None else set()
    for index, event in enumerate(events):
        if not isinstance(event, dict) or not EXPECTED_RAW_FIELDS.issubset(event):
            raise ValueError(f"S3: Sự kiện vị trí {index} thiếu cấu trúc 12 trường Wyscout.")
        event_id = event["id"]
        if type(event_id) is not int or event_id <= 0:
            raise ValueError(f"S3: ID sự kiện không hợp lệ ở vị trí {index}: {event_id!r}")
        if event_id in seen:
            raise ValueError(f"S3: Trùng event_id={event_id} trong hoặc giữa các file.")
        seen.add(event_id)
    logger.info("S3: %s sự kiện đủ trường, không trùng ID", len(events))
    return {"total_events": len(events), "missing_fields_count": 0, "duplicate_ids": 0}


def filter_passes(events: list[dict], logger: logging.Logger) -> list[dict]:
    """E9: lọc đúng cả tên Pass và eventId=8 trước khi ép kiểu."""
    for event in events:
        if (event.get("eventName") == "Pass") != (event.get("eventId") == 8):
            raise ValueError(f"S4: Pass/eventId=8 không khớp tại sự kiện {event.get('id')}; không tự bỏ qua.")
    passes = [e for e in events if e.get("eventName") == "Pass" and e.get("eventId") == 8]
    logger.info("S4: %s sự kiện → %s Pass", len(events), len(passes))
    return passes


@dataclass
class CandidateMatch:
    file_name: str
    match_id: int
    total_passes: int
    team_counts: list[int]
    balance_ratio: float
    e2_count: int
    e3_count: int


def scan_and_propose_matches(
    input_path: str, json_filenames: list[str], logger: logging.Logger,
    min_passes: int = 800, min_ratio: float = 0.85,
) -> list[CandidateMatch]:
    """Khảo sát: đủ hai đội, đủ số chuyền, cân bằng và không bị loại bởi E2/E3."""
    if min_passes < 1 or not 0 <= min_ratio <= 1:
        raise ValueError("Ngưỡng khảo sát không hợp lệ.")
    metadata = verify_input_source(input_path, json_filenames, logger)
    candidates = []
    seen_ids: set[int] = set()
    for filename in json_filenames:
        events = load_raw_events(input_path, filename, logger)
        check_raw_structure(events, logger, seen_ids)
        passes = filter_passes(events, logger)
        del events
        cleaned, metrics = extract_coordinates_and_clean(passes, logger)
        del passes
        for match_id, group in cleaned.groupby("match_id"):
            counts = group.groupby("team_id").size().tolist()
            audit = metrics.by_match[int(match_id)]
            if audit["e2_dropped_incomplete_pos"] or audit["e3_dropped_out_of_bounds"]:
                continue
            if len(counts) != 2 or len(group) < min_passes:
                continue
            ratio = min(counts) / max(counts)
            if ratio >= min_ratio:
                candidate = CandidateMatch(filename, int(match_id), len(group), counts, ratio, 0, 0)
                candidates.append(candidate)
                logger.info("[Candidate] %s | trận %s | %s chuyền | cân bằng %.4f",
                            filename, match_id, len(group), ratio)
        del cleaned, metrics
    verify_source_unchanged(metadata)
    return candidates
