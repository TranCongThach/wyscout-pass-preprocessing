"""Kiểm thử lỗi đã phát hiện ở phần tiền xử lý; dùng unittest có sẵn trong Python.

Chạy từ thư mục dự án: python -m unittest discover -s tests -v
Fixture nhỏ được ghi trong thư mục tạm; không cần mạng hoặc sửa dữ liệu thật.
"""

import json
import logging
import math
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import weakref
import zipfile

import numpy as np
import pandas as pd
from matplotlib.colors import to_rgba

import pipeline
from tien_xu_ly.buoc_00_cau_hinh import FINAL_SCHEMA_COLUMNS, PipelineConfig
from tien_xu_ly.buoc_01_doc_du_lieu import (
    check_raw_structure, filter_passes, load_raw_events, scan_and_propose_matches,
    verify_input_source,
)
from tien_xu_ly.buoc_02_lam_sach import extract_coordinates_and_clean
from tien_xu_ly.buoc_03_chuan_hoa import sort_and_finalize
from tien_xu_ly.buoc_04_kiem_dinh import validate_dataset, validate_match_selection
from tien_xu_ly.buoc_05_ve_du_lieu import create_directions_figure, create_distribution_figure

LOGGER = logging.getLogger("test_preprocessing")
LOGGER.addHandler(logging.NullHandler())
ROOT = Path(__file__).resolve().parents[1]


def make_event(event_id=1, match_id=1, team_id=10):
    return {
        "id": event_id, "eventId": 8, "eventName": "Pass", "subEventId": 85,
        "subEventName": "Simple pass", "matchId": match_id, "teamId": team_id,
        "playerId": 3, "matchPeriod": "1H", "eventSec": event_id + .5,
        "positions": [{"x": 10, "y": 20}, {"x": 30, "y": 40}],
        "tags": [{"id": 1801}],
    }


def make_events(count=8, start=1, match_id=1):
    return [make_event(start + i, match_id, 10 if i % 2 == 0 else 20) for i in range(count)]


def make_frame(count=4):
    # Bảng kỳ vọng viết trực tiếp, độc lập với hàm chuẩn hóa cần kiểm định.
    return pd.DataFrame({
        "event_id": range(1, count + 1), "match_id": 1,
        "team_id": [10 if i % 2 == 0 else 20 for i in range(count)], "player_id": 3,
        "match_period": "1H", "event_sec": [i + .5 for i in range(count)],
        "sub_event_id": 85, "sub_event_name": "Simple pass",
        "x_start": 10, "y_start": 20, "x_end": 30, "y_end": 40,
        "pass_outcome": "accurate", "x_start_n": .1, "y_start_n": .2,
        "x_end_n": .3, "y_end_n": .4, "dx_n": .2, "dy_n": .2,
        "length_n": math.sqrt(.08), "end_unknown": False,
    })[FINAL_SCHEMA_COLUMNS]


def write_zip(path, files):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, events in files.items():
            archive.writestr(name, json.dumps(events))


def write_json_folder(path, files):
    path.mkdir(parents=True, exist_ok=True)
    for name, events in files.items():
        (path / name).write_text(json.dumps(events), encoding="utf-8")


def write_plot_stubs(data, distribution_path, directions_path, logger):
    # Khi bỏ qua render trong test, vẫn tạo đủ file cho bước công bố kết quả.
    for path in [distribution_path, directions_path]:
        Path(path).write_bytes(b"plot fixture")


class CleaningTests(unittest.TestCase):
    def test_pass_name_id_mismatch_is_not_silently_discarded(self):
        for updates in [{"eventId": 7}, {"eventId": "8"}, {"eventName": "Foul"}]:
            with self.subTest(updates=updates), self.assertRaisesRegex(ValueError, "S4"):
                filter_passes([{**make_event(), **updates}], LOGGER)

    def test_pass_filter_precedes_subtype_cast_and_accepts_empty_input(self):
        offside = make_event()
        offside.update(eventName="Offside", eventId=6, subEventId="")
        passes = filter_passes([offside, make_event(2)], LOGGER)
        clean, _ = extract_coordinates_and_clean(passes, LOGGER)
        self.assertEqual(clean.event_id.tolist(), [2])
        self.assertEqual(filter_passes([], LOGGER), [])
        empty, _ = extract_coordinates_and_clean([], LOGGER)
        self.assertIn("x_start", empty.columns)

    def test_requires_exactly_two_complete_positions(self):
        for positions in [[], [{"x": 1, "y": 2}], [{"x": 1, "y": 2}] * 3,
                          [None, {"x": 1, "y": 2}], [{"x": 1}, {"x": 2, "y": 3}]]:
            with self.subTest(positions=positions):
                event = make_event()
                event["positions"] = positions
                clean, metrics = extract_coordinates_and_clean([event], LOGGER)
                self.assertTrue(clean.empty)
                self.assertEqual(metrics.e2_dropped_incomplete_pos, 1)

    def test_coordinates_are_checked_before_integer_conversion(self):
        for value in [-.9, 100.9, 50.5, -1, 101, float("nan"), float("inf"), "30", True]:
            with self.subTest(value=value):
                event = make_event()
                event["positions"][0]["x"] = value
                clean, metrics = extract_coordinates_and_clean([event], LOGGER)
                self.assertTrue(clean.empty)
                self.assertEqual(metrics.e3_dropped_out_of_bounds, 1)

    def test_flags_and_unknowns_are_retained_without_inventing_values(self):
        event = make_event()
        event.update(playerId=0, tags=[], positions=[{"x": 0, "y": 0}] * 2)
        clean, metrics = extract_coordinates_and_clean([event], LOGGER)
        self.assertEqual(len(clean), 1)
        self.assertTrue(clean.end_unknown.iloc[0])
        self.assertEqual(clean.player_id.iloc[0], 0)
        self.assertEqual(clean.pass_outcome.iloc[0], "unknown")
        self.assertEqual(metrics.e4_zero_length_passes, 1)
        self.assertEqual(metrics.e6_unknown_input, 1)
        self.assertEqual(metrics.e6_outcome_unknown, 1)

    def test_conflicting_outcome_tags_stop_processing(self):
        event = make_event()
        event["tags"] = [{"id": 1801}, {"id": 1802}]
        with self.assertRaisesRegex(ValueError, "1801.*1802"):
            extract_coordinates_and_clean([event], LOGGER)

    def test_invalid_metadata_is_not_silently_cast(self):
        for field, value in [("eventSec", -1.), ("eventSec", float("inf")),
                             ("matchPeriod", "BAD"), ("subEventId", ""), ("playerId", 3.5)]:
            with self.subTest(field=field):
                event = make_event()
                event[field] = value
                with self.assertRaises(ValueError):
                    extract_coordinates_and_clean([event], LOGGER)

    def test_boundary_coordinates_zero_and_one_hundred_are_valid(self):
        event = make_event()
        event["positions"] = [{"x": 0, "y": 100}, {"x": 100, "y": 0}]
        clean, metrics = extract_coordinates_and_clean([event], LOGGER)
        self.assertEqual(len(clean), 1)
        self.assertEqual(metrics.boundary_coordinates_count, 1)


class ValidationTests(unittest.TestCase):
    def test_valid_contract_and_strict_row_threshold(self):
        self.assertTrue(validate_dataset(make_frame(), LOGGER, min_rows=0).all_passed)
        with self.assertRaises(AssertionError):
            validate_dataset(make_frame(500), LOGGER)
        self.assertTrue(validate_dataset(make_frame(501), LOGGER).all_passed)

    def test_schema_checks_names_order_and_types(self):
        original = make_frame()
        cases = [
            original.rename(columns={"sub_event_id": "not_in_contract"}),
            original[original.columns[::-1]], original.assign(extra=1),
            original.assign(event_id=original.event_id.astype(float)),
            original.assign(end_unknown="False"), original.assign(x_start=10.5),
        ]
        for index, data in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(AssertionError):
                validate_dataset(data, LOGGER, min_rows=0)

    def test_invalid_values_and_inconsistent_features_fail(self):
        for column, value in [
            ("event_sec", -1.), ("event_sec", float("inf")), ("event_sec", np.nan),
            ("match_period", "BAD"), ("x_start", -1), ("x_start_n", .7),
            ("x_end_n", 1.1), ("dx_n", 42.), ("dy_n", -42.), ("length_n", -5.),
            ("end_unknown", True), ("pass_outcome", "made_up"), ("player_id", -1),
        ]:
            with self.subTest(column=column, value=value), self.assertRaises(AssertionError):
                validate_dataset(make_frame().assign(**{column: value}), LOGGER, min_rows=0)

    def test_duplicate_ids_wrong_team_count_and_wrong_chronology_fail(self):
        duplicate = make_frame()
        duplicate.loc[1, "event_id"] = duplicate.loc[0, "event_id"]
        for data in [duplicate, make_frame().assign(team_id=10), make_frame().iloc[::-1]]:
            with self.subTest(case=data.index.tolist()), self.assertRaises(AssertionError):
                validate_dataset(data, LOGGER, min_rows=0)

    def test_partial_match_request_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "999"):
            sort_and_finalize(make_frame(), [1, 999], LOGGER)
        with self.assertRaises(ValueError):
            sort_and_finalize(make_frame(), [], LOGGER)

    def test_sorting_uses_period_before_seconds(self):
        data = make_frame()
        data.loc[0, ["match_period", "event_sec"]] = ["2H", 0.]
        sorted_data = sort_and_finalize(data, [1], LOGGER)
        self.assertEqual(sorted_data.match_period.tolist(), ["1H", "1H", "1H", "2H"])


class IntegrationTests(unittest.TestCase):
    def test_batch_reports_losses_and_preserves_zip_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.zip"
            events = make_events()
            bad_coord = make_event(9)
            bad_coord["positions"][1]["y"] = 101
            bad_pos = make_event(10)
            bad_pos.update(positions=[{"x": 1, "y": 2}], tags=[])
            write_zip(source, {"one.json": events + [bad_coord, bad_pos],
                               "two.json": make_events(4, start=100, match_id=2)})
            original = source.read_bytes()
            config = PipelineConfig(input_path=str(source), json_files=["one.json", "two.json"],
                                    target_match_ids=None, output_dir=str(root / "new" / "data"),
                                    min_row_threshold=0)
            data, report = pipeline.run_pipeline(config)
            self.assertTrue(report.all_passed)
            self.assertEqual(data.shape, (12, 21))
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse((Path(config.output_dir) / "raw").exists())
            self.assertTrue((config.processed_dir / "pipeline_execution.log").is_file())
            text = (config.processed_dir / config.output_report).read_text(encoding="utf-8")
            self.assertIn("14 vào − 1 E2 − 1 E3 = 12 dòng", text)
            self.assertIn("Số dòng > 0", text)
            self.assertIn("Thiếu thẻ kết quả trên Pass đầu vào | 1 | 1", text)
            self.assertIn("Chưa rõ kết quả trên các dòng giữ lại | 0 | 0", text)
            loaded = pd.read_csv(config.processed_dir / config.output_csv)
            pd.testing.assert_frame_equal(data, loaded, check_exact=False, atol=1e-12, rtol=0)
            self.assertIn("CRC ĐẠT", text)
            self.assertIn("Chế độ toàn nguồn", text)
            with patch.object(pipeline, "generate_pitch_visualizations", side_effect=write_plot_stubs):
                pipeline.run_pipeline(config, LOGGER)

    def test_raw_event_objects_are_released_before_next_file(self):
        class TrackedEvent(dict):
            pass
        references = []
        def loader(_zip, name, _logger):
            self.assertTrue(all(reference() is None for reference in references))
            event = TrackedEvent(make_event(1 if name == "one.json" else 2,
                                            team_id=10 if name == "one.json" else 20))
            references.append(weakref.ref(event))
            return [event]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.zip"
            write_zip(source, {"one.json": [], "two.json": []})
            config = PipelineConfig(input_path=str(source), json_files=["one.json", "two.json"],
                                    target_match_ids=[1], output_dir=str(root / "out"), min_row_threshold=0,
                                    min_match_passes=1)
            with patch.object(pipeline, "load_raw_events", side_effect=loader), \
                 patch.object(pipeline, "generate_pitch_visualizations"), \
                 patch.object(pipeline, "export_artifacts"), \
                 patch.object(pipeline, "publish_outputs"):
                data, _ = pipeline.run_pipeline(config, LOGGER)
            self.assertEqual(len(data), 2)
            self.assertTrue(all(reference() is None for reference in references))

    def test_duplicate_ids_across_files_are_rejected(self):
        seen = set()
        check_raw_structure([make_event()], LOGGER, seen)
        with self.assertRaisesRegex(ValueError, "Trùng"):
            check_raw_structure([make_event()], LOGGER, seen)

    def test_proposal_rejects_matches_with_discarded_coordinates(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "input.zip"
            events = make_events()
            events[0]["positions"][0]["x"] = 101
            write_zip(source, {"one.json": events})
            self.assertEqual(scan_and_propose_matches(str(source), ["one.json"], LOGGER, min_passes=2), [])
            with self.assertRaisesRegex(ValueError, "missing.json"):
                scan_and_propose_matches(str(source), ["missing.json"], LOGGER)

    def test_cli_proposal_honors_requested_json_from_another_working_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "input.zip"
            write_zip(source, {"custom.json": make_events(802)})
            process = subprocess.run([
                sys.executable, "-B", "-X", "utf8", str(ROOT / "pipeline.py"), "--propose",
                "--zip-path", str(source), "--json-file", "custom.json",
            ], cwd=temporary, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("[Candidate] custom.json", process.stdout)
            self.assertNotIn("events_European_Championship.json", process.stdout)

    def test_cli_writes_processed_without_copying_or_modifying_raw(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "input.zip"
            write_zip(source, {"custom.json": make_events(802)})
            original = source.read_bytes()
            process = subprocess.run([
                sys.executable, "-B", "-X", "utf8", str(ROOT / "pipeline.py"),
                "--zip-path", str(source), "--json-file", "custom.json", "--matches", "1",
                "--output-dir", "relative_output/data",
            ], cwd=temporary, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(process.returncode, 0, process.stderr)
            output = Path(temporary) / "relative_output/data"
            self.assertFalse((output / "raw").exists())
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(pd.read_csv(output / "processed/passes_cleaned.csv").shape, (802, 21))


class DirectoryInputTests(unittest.TestCase):
    def test_reads_local_json_and_records_real_source_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "data/raw/events"
            write_json_folder(source, {"one.json": make_events(800)})
            original = (source / "one.json").read_bytes()
            config = PipelineConfig(input_path=str(source), json_files=["one.json"],
                                    target_match_ids=[1], output_dir=str(root / "data"))
            with patch.object(pipeline, "generate_pitch_visualizations", side_effect=write_plot_stubs), \
                 patch("tien_xu_ly.buoc_01_doc_du_lieu.verify_raw_file", side_effect=AssertionError("Không được tìm ZIP")):
                data, validation = pipeline.run_pipeline(config, LOGGER)
            self.assertEqual(data.shape, (800, 21))
            self.assertEqual((source / "one.json").read_bytes(), original)
            self.assertEqual(sorted(p.name for p in source.iterdir()), ["one.json"])
            text = (config.processed_dir / config.output_report).read_text(encoding="utf-8")
            self.assertIn(str(source.resolve()), text)
            self.assertIn("Không áp dụng kích thước/MD5/CRC", text)
            self.assertIn("SHA-256", text)
            self.assertIn("S14: mỗi trận chọn có ít nhất 800", text)
            self.assertTrue(validation.all_passed)

    def test_missing_invalid_and_duplicate_source_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            for names in [["missing.json"], ["../outside.json"], ["one.json", "one.json"], []]:
                with self.subTest(names=names), self.assertRaises(ValueError):
                    verify_input_source(temporary, names, LOGGER)

    def test_broken_zip_reports_clear_input_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "broken.zip"
            source.write_bytes(b"not a zip")
            with self.assertRaisesRegex(ValueError, "ZIP hợp lệ"):
                verify_input_source(str(source), ["one.json"], LOGGER)

    def test_changed_source_aborts_before_overwriting_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "raw/events"
            write_json_folder(source, {"one.json": make_events(800)})
            config = PipelineConfig(input_path=str(source), json_files=["one.json"],
                                    target_match_ids=[1], output_dir=str(root / "output"))
            config.processed_dir.mkdir(parents=True)
            previous = config.processed_dir / config.output_csv
            previous.write_bytes(b"previous successful output")
            def load_and_change(*args):
                events = load_raw_events(*args)
                (source / "one.json").write_text("[]", encoding="utf-8")
                return events
            with patch.object(pipeline, "load_raw_events", side_effect=load_and_change), \
                 patch.object(pipeline, "generate_pitch_visualizations") as draw:
                with self.assertRaisesRegex(ValueError, "đã thay đổi"):
                    pipeline.run_pipeline(config, LOGGER)
                draw.assert_not_called()
            self.assertEqual(previous.read_bytes(), b"previous successful output")

    def test_default_commands_work_in_copied_project_from_other_cwd(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "copied_project"
            project.mkdir()
            for name in ["pipeline.py", "kiem_tra_du_lieu.py"]:
                shutil.copy2(ROOT / name, project / name)
            shutil.copytree(ROOT / "tien_xu_ly", project / "tien_xu_ly",
                            ignore=shutil.ignore_patterns("__pycache__"))
            source = project / "data/raw/events"
            events = make_events(800, match_id=1694401) + make_events(800, start=1001, match_id=1694416)
            write_json_folder(source, {"events_European_Championship.json": events})
            original = (source / "events_European_Championship.json").read_bytes()
            for script in ["pipeline.py", "kiem_tra_du_lieu.py"]:
                process = subprocess.run([sys.executable, "-B", "-X", "utf8", str(project / script)],
                                         cwd=root, capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
            self.assertEqual(pd.read_csv(project / "data/processed/passes_cleaned.csv").shape, (1600, 21))
            self.assertEqual((source / "events_European_Championship.json").read_bytes(), original)
            self.assertFalse((project / "du_lieu_tien_xu_ly").exists())
            self.assertFalse(list(project.rglob("*.zip")))

    def test_output_cannot_write_into_source_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "events"
            write_json_folder(source, {"one.json": make_events(800)})
            config = PipelineConfig(input_path=str(source), json_files=["one.json"],
                                    target_match_ids=[1], output_dir=str(source))
            with self.assertRaisesRegex(ValueError, "nằm ngoài"):
                pipeline.run_pipeline(config, LOGGER)
            self.assertFalse((source / "processed").exists())


class MatchSelectionTests(unittest.TestCase):
    def test_manual_samples_enforce_count_balance_and_no_discarded_rows(self):
        _, metrics = extract_coordinates_and_clean(make_events(800), LOGGER)
        valid = make_frame(800)
        self.assertTrue(validate_match_selection(valid, metrics, [1]))
        cases = [
            (make_frame(799), metrics, "799 chuyền"),
            (valid.assign(team_id=[10] * 700 + [20] * 100), metrics, "cân bằng"),
        ]
        for field, label in [("positions", "E2=1"), ("coordinate", "E3=1")]:
            bad = make_event(801)
            if field == "positions":
                bad["positions"] = []
            else:
                bad["positions"][0]["x"] = 101
            _, bad_metrics = extract_coordinates_and_clean(make_events(800) + [bad], LOGGER)
            cases.append((valid, bad_metrics, label))
        for data, audit, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                validate_match_selection(data, audit, [1])

    def test_balance_boundary_and_batch_mode(self):
        _, metrics = extract_coordinates_and_clean(make_events(1480), LOGGER)
        data = make_frame(1480).assign(team_id=[10] * 680 + [20] * 800)
        self.assertTrue(validate_match_selection(data, metrics, [1]))
        with self.assertRaisesRegex(ValueError, "cân bằng"):
            validate_match_selection(data.assign(team_id=[10] * 679 + [20] * 801), metrics, [1])
        self.assertEqual(validate_match_selection(make_frame(4), metrics, None), {})

    def test_cli_rejects_ineligible_manual_match_without_exporting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "raw"
            write_json_folder(source, {"one.json": make_events(600)})
            output = root / "result"
            process = subprocess.run([
                sys.executable, "-B", "-X", "utf8", str(ROOT / "pipeline.py"),
                "--input-path", str(source), "--json-file", "one.json", "--matches", "1",
                "--output-dir", str(output),
            ], capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("S14", process.stderr)
            self.assertFalse((output / "processed/passes_cleaned.csv").exists())


class PlotTests(unittest.TestCase):
    def test_unknown_outcome_is_visible_and_not_colored_as_inaccurate(self):
        data = make_frame(2).assign(pass_outcome="unknown")
        figure = create_distribution_figure(data)
        axes = figure.axes[0]
        self.assertEqual(sum(len(c.get_offsets()) for c in axes.collections[1:]), 2)
        self.assertIn("Chưa rõ", axes.get_legend_handles_labels()[1][0])
        figure.clear()
        figure = create_directions_figure(data)
        arrows = [t.arrow_patch for t in figure.axes[0].texts if t.arrow_patch is not None]
        self.assertEqual(len(arrows), 2)
        for arrow in arrows:
            self.assertEqual(arrow.get_edgecolor()[:3], to_rgba("#d1d5db")[:3])
        figure.clear()

    def test_end_unknown_only_draws_start_marker(self):
        data = make_frame(2).assign(x_end=0, y_end=0, end_unknown=True)
        figure = create_directions_figure(data)
        self.assertFalse(any(t.arrow_patch is not None for t in figure.axes[0].texts))
        self.assertIn("Điểm cuối nghi ngờ", figure.axes[0].get_legend_handles_labels()[1][0])
        figure.clear()


if __name__ == "__main__":
    unittest.main()
