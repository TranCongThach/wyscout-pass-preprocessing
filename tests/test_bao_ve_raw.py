"""Kiểm thử bảo vệ raw khi xuất kết quả; chỉ tạo dữ liệu trong thư mục tạm.

Chạy: python -m unittest discover -s tests -p test_bao_ve_raw.py -v
Bao phủ liên kết file, log, lỗi ghi giữa chừng và chạy lại kết quả.
"""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

import pipeline
from tien_xu_ly.buoc_00_cau_hinh import PipelineConfig
from test_tien_xu_ly import LOGGER, make_events, write_json_folder, write_zip


def output_names(config):
    return [config.output_csv, config.output_report, config.output_plot_dist,
            config.output_plot_dir, "pipeline_execution.log"]


def draw_stub(data, distribution_path, directions_path, logger):
    # Các bài cũ đã kiểm tra PNG thật; ở đây chỉ cần mô phỏng hai file được ghi.
    for name in [distribution_path, directions_path]:
        Path(name).write_bytes(b"temporary image")


def fixture(root, zipped=False):
    source = root / ("events.zip" if zipped else "raw")
    if zipped:
        write_zip(source, {"one.json": make_events(4)})
        raw_file = source
    else:
        write_json_folder(source, {"one.json": make_events(4)})
        raw_file = source / "one.json"
    config = PipelineConfig(input_path=str(source), json_files=["one.json"],
                            target_match_ids=None, output_dir=str(root / "output"),
                            min_row_threshold=0)
    config.processed_dir.mkdir(parents=True)
    return config, raw_file


class RawOutputSafetyTests(unittest.TestCase):
    def test_each_output_hardlink_to_raw_is_rejected_before_logger(self):
        for zipped in [False, True]:
            for name in output_names(PipelineConfig()):
                with self.subTest(zipped=zipped, output=name), tempfile.TemporaryDirectory() as temporary:
                    config, raw_file = fixture(Path(temporary), zipped)
                    original = raw_file.read_bytes()
                    target = config.processed_dir / name
                    os.link(raw_file, target)
                    with patch.object(pipeline, "setup_logger") as setup, \
                         patch.object(pipeline, "load_raw_events") as load:
                        with self.assertRaises(ValueError):
                            pipeline.run_pipeline(config)
                        setup.assert_not_called()
                        load.assert_not_called()
                    self.assertEqual(raw_file.read_bytes(), original)
                    self.assertTrue(target.samefile(raw_file))

    def test_hardlink_to_unselected_json_is_also_protected(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, raw_file = fixture(Path(temporary))
            unused = raw_file.parent / "not_selected.json"
            unused.write_bytes(b"original unselected raw")
            os.link(unused, config.processed_dir / config.output_csv)
            with patch.object(pipeline, "setup_logger") as setup:
                with self.assertRaises(ValueError):
                    pipeline.run_pipeline(config)
                setup.assert_not_called()
            self.assertEqual(unused.read_bytes(), b"original unselected raw")

    def test_existing_and_dangling_output_symlinks_are_rejected(self):
        for dangling in [False, True]:
            with self.subTest(dangling=dangling), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                config, raw_file = fixture(root)
                original = raw_file.read_bytes()
                destination = root / "does_not_exist.json" if dangling else raw_file
                target = config.processed_dir / "pipeline_execution.log"
                try:
                    target.symlink_to(destination)
                except OSError as error:
                    self.skipTest(f"Không có quyền tạo symlink: {error}")
                with patch.object(pipeline, "setup_logger") as setup:
                    with self.assertRaises(ValueError):
                        pipeline.run_pipeline(config)
                    setup.assert_not_called()
                self.assertTrue(target.is_symlink())
                self.assertEqual(raw_file.read_bytes(), original)
                if dangling:
                    self.assertFalse(destination.exists())

    def test_processed_symlink_into_raw_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, raw_file = fixture(Path(temporary))
            config.processed_dir.rmdir()
            try:
                config.processed_dir.symlink_to(raw_file.parent, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"Không có quyền tạo symlink thư mục: {error}")
            original = raw_file.read_bytes()
            with self.assertRaises(ValueError):
                pipeline.run_pipeline(config, LOGGER)
            self.assertEqual(raw_file.read_bytes(), original)
            self.assertEqual(sorted(p.name for p in raw_file.parent.iterdir()), ["one.json"])

    def test_output_names_cannot_collide_by_case_on_windows(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, raw_file = fixture(Path(temporary))
            config.output_report = config.output_csv.upper()
            original = raw_file.read_bytes()
            with self.assertRaises(ValueError):
                pipeline.run_pipeline(config, LOGGER)
            self.assertEqual(raw_file.read_bytes(), original)
            self.assertFalse(list(config.processed_dir.iterdir()))

    def test_partial_image_or_csv_write_preserves_previous_results_and_cleans_temp(self):
        for failed_writer in ["image", "csv"]:
            with self.subTest(writer=failed_writer), tempfile.TemporaryDirectory() as temporary:
                config, raw_file = fixture(Path(temporary))
                original = raw_file.read_bytes()
                previous = {name: f"previous {name}".encode() for name in output_names(config)}
                for name, contents in previous.items():
                    (config.processed_dir / name).write_bytes(contents)

                def fail_after_write(data, path, *args, **kwargs):
                    Path(path).write_bytes(b"unfinished output")
                    raise OSError("simulated write failure")

                draw = fail_after_write if failed_writer == "image" else draw_stub
                with patch.object(pipeline, "generate_pitch_visualizations", side_effect=draw):
                    if failed_writer == "csv":
                        with patch.object(pd.DataFrame, "to_csv", autospec=True,
                                          side_effect=fail_after_write):
                            with self.assertRaisesRegex(OSError, "simulated"):
                                pipeline.run_pipeline(config)
                    else:
                        with self.assertRaisesRegex(OSError, "simulated"):
                            pipeline.run_pipeline(config)
                self.assertEqual(raw_file.read_bytes(), original)
                self.assertEqual({p.name: p.read_bytes() for p in config.processed_dir.iterdir()}, previous)

    def test_late_hardlink_cannot_write_through_to_raw(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, raw_file = fixture(Path(temporary))
            original = raw_file.read_bytes()
            target = config.processed_dir / config.output_csv
            real_export = pipeline.export_artifacts

            def export_then_link(*args, **kwargs):
                real_export(*args, **kwargs)
                os.link(raw_file, target)

            with patch.object(pipeline, "generate_pitch_visualizations", side_effect=draw_stub), \
                 patch.object(pipeline, "export_artifacts", side_effect=export_then_link):
                try:
                    pipeline.run_pipeline(config, LOGGER)
                except ValueError:
                    # Có thể chặn lại trước khi publish; os.replace cũng an toàn nếu cho phép.
                    pass
            self.assertEqual(raw_file.read_bytes(), original)
            self.assertTrue(target.samefile(raw_file) or target.read_bytes().startswith(b"event_id,"))

    def test_hardlink_inserted_at_replace_is_replaced_without_changing_raw(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, raw_file = fixture(Path(temporary))
            original = raw_file.read_bytes()
            target = config.processed_dir / config.output_csv
            target.write_bytes(b"previous CSV")
            real_replace = os.replace
            injected = False

            def replace_after_link(source, destination, *args, **kwargs):
                nonlocal injected
                if Path(destination) == target:
                    # Chèn liên kết sau preflight, ngay trước thay file thực sự.
                    target.unlink()
                    os.link(raw_file, target)
                    injected = True
                return real_replace(source, destination, *args, **kwargs)

            with patch.object(pipeline, "generate_pitch_visualizations", side_effect=draw_stub), \
                 patch("tien_xu_ly.buoc_00_bao_ve_dau_ra.os.replace", side_effect=replace_after_link):
                data, report = pipeline.run_pipeline(config, LOGGER)
            self.assertTrue(injected)
            self.assertTrue(report.all_passed)
            self.assertEqual(data.shape, (4, 21))
            self.assertEqual(raw_file.read_bytes(), original)
            self.assertFalse(target.samefile(raw_file))
            self.assertEqual(pd.read_csv(target).shape, (4, 21))
            self.assertEqual(sorted(p.name for p in config.processed_dir.iterdir()),
                             sorted(output_names(config)))

    def test_raw_change_during_export_blocks_publish_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, raw_file = fixture(Path(temporary))
            previous = {name: f"previous {name}".encode() for name in output_names(config)}
            for name, contents in previous.items():
                (config.processed_dir / name).write_bytes(contents)
            real_export = pipeline.export_artifacts

            def export_then_change_raw(*args, **kwargs):
                real_export(*args, **kwargs)
                # Mô phỏng chương trình khác thay nguồn sau lần kiểm tra trước xuất.
                raw_file.write_bytes(b"[]")

            with patch.object(pipeline, "generate_pitch_visualizations", side_effect=draw_stub), \
                 patch.object(pipeline, "export_artifacts", side_effect=export_then_change_raw):
                with self.assertRaisesRegex(ValueError, "đã thay đổi"):
                    pipeline.run_pipeline(config, LOGGER)
            self.assertEqual(raw_file.read_bytes(), b"[]")
            self.assertEqual({p.name: p.read_bytes() for p in config.processed_dir.iterdir()}, previous)

    def test_normal_rerun_preserves_raw_and_replaces_complete_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, raw_file = fixture(Path(temporary))
            original = raw_file.read_bytes()
            with patch.object(pipeline, "generate_pitch_visualizations", side_effect=draw_stub):
                for _ in range(2):
                    data, report = pipeline.run_pipeline(config)
                    self.assertTrue(report.all_passed)
                    self.assertEqual(data.shape, (4, 21))
                    self.assertEqual(pd.read_csv(config.processed_dir / config.output_csv).shape, (4, 21))
                    self.assertEqual(sorted(p.name for p in config.processed_dir.iterdir()),
                                     sorted(output_names(config)))
                    self.assertEqual(raw_file.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
