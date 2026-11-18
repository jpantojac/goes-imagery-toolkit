"""
Unit tests for Storage Retention & Disk Pruning Engine (libs/retention.py).
"""
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from app.libs.retention import (
    parse_file_datetime,
    get_disk_status,
    purge_input_files,
    purge_output_files,
    emergency_disk_cleanup,
    prune_empty_directories,
    run_retention_cycle
)


class TestRetentionEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_retention_")
        self.input_dir = os.path.join(self.test_dir, "input")
        self.output_dir = os.path.join(self.test_dir, "output")
        self.latest_dir = os.path.join(self.test_dir, "latest")
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.latest_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_parse_file_datetime_noaa(self):
        fname = "OR_ABI-L1b-RadF-M6C13_G19_s20263221200214_e20263221209534_c20263221209589.nc"
        dt = parse_file_datetime(fname)
        # Year 2026, Julian day 322 = Nov 18, 2026, 12:00 UTC
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 11)
        self.assertEqual(dt.day, 18)
        self.assertEqual(dt.hour, 12)
        self.assertEqual(dt.minute, 0)

    def test_parse_file_datetime_output(self):
        fname = "202611181200.png"
        dt = parse_file_datetime(fname)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 11)
        self.assertEqual(dt.day, 18)
        self.assertEqual(dt.hour, 12)
        self.assertEqual(dt.minute, 0)

    def test_parse_file_datetime_fallback(self):
        dummy_file = os.path.join(self.test_dir, "arbitrary_name.bin")
        with open(dummy_file, "w") as f:
            f.write("content")
        dt = parse_file_datetime(dummy_file)
        now = datetime.now(timezone.utc)
        self.assertAlmostEqual(dt.timestamp(), now.timestamp(), delta=10)

    def test_purge_input_files(self):
        # Create an old file (> 24 hours ago, e.g. Julian day 320)
        day320_dir = os.path.join(self.input_dir, "320")
        os.makedirs(day320_dir, exist_ok=True)
        old_file = os.path.join(day320_dir, "OR_ABI-L1b-RadF-M6C13_G19_s20263201200000_e20263201209000_c0.nc")
        with open(old_file, "wb") as f:
            f.write(b"0" * 1024)

        # Create a fresh file (< 1 hour ago)
        now_dt = datetime.now(timezone.utc)
        now_j = now_dt.strftime("%j")
        day_now_dir = os.path.join(self.input_dir, str(now_j))
        os.makedirs(day_now_dir, exist_ok=True)
        fresh_file = os.path.join(
            day_now_dir,
            f"OR_ABI-L1b-RadF-M6C13_G19_s{now_dt.year}{now_j}{now_dt.strftime('%H%M')}00_e0_c0.nc"
        )
        with open(fresh_file, "wb") as f:
            f.write(b"1" * 1024)

        # Purge with 24h retention
        del_count, bytes_freed = purge_input_files(self.input_dir, retention_hours=24.0, dry_run=False)
        self.assertEqual(del_count, 1)
        self.assertEqual(bytes_freed, 1024)
        self.assertFalse(os.path.exists(old_file))
        self.assertTrue(os.path.exists(fresh_file))

    def test_purge_input_files_custom_hours(self):
        # Test custom retention like 3 hours
        now_dt = datetime.now(timezone.utc)
        t_4h_ago = now_dt - timedelta(hours=4)
        j_4h = t_4h_ago.strftime("%j")
        d_dir = os.path.join(self.input_dir, j_4h)
        os.makedirs(d_dir, exist_ok=True)
        file_4h = os.path.join(
            d_dir,
            f"OR_ABI-L1b-RadF-M6C13_G19_s{t_4h_ago.year}{j_4h}{t_4h_ago.strftime('%H%M')}00_e0_c0.nc"
        )
        with open(file_4h, "wb") as f:
            f.write(b"x" * 500)

        # Retention set to 3 hours -> file_4h should be deleted
        del_count, bytes_freed = purge_input_files(self.input_dir, retention_hours=3.0, dry_run=False)
        self.assertEqual(del_count, 1)
        self.assertEqual(bytes_freed, 500)
        self.assertFalse(os.path.exists(file_4h))

    def test_purge_output_files(self):
        ch_dir = os.path.join(self.output_dir, "200", "C13")
        os.makedirs(ch_dir, exist_ok=True)
        # File from 40 days ago
        old_png = os.path.join(ch_dir, "202609011200.png")
        with open(old_png, "wb") as f:
            f.write(b"pngdata")

        # File from today
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        new_png = os.path.join(ch_dir, f"{today_str}.png")
        with open(new_png, "wb") as f:
            f.write(b"pngdata_fresh")

        del_count, bytes_freed = purge_output_files(self.output_dir, retention_days=30.0, dry_run=False)
        self.assertEqual(del_count, 1)
        self.assertFalse(os.path.exists(old_png))
        self.assertTrue(os.path.exists(new_png))

    def test_dry_run_does_not_delete(self):
        day_dir = os.path.join(self.input_dir, "100")
        os.makedirs(day_dir, exist_ok=True)
        old_file = os.path.join(day_dir, "OR_ABI-L1b-RadF-M6C13_G19_s20261001200000_e0_c0.nc")
        with open(old_file, "wb") as f:
            f.write(b"content")

        del_count, bytes_freed = purge_input_files(self.input_dir, retention_hours=24.0, dry_run=True)
        self.assertEqual(del_count, 1)
        self.assertEqual(bytes_freed, len(b"content"))
        # Must still exist on disk
        self.assertTrue(os.path.exists(old_file))

    def test_prune_empty_directories(self):
        empty_sub = os.path.join(self.input_dir, "empty_day", "empty_sub")
        os.makedirs(empty_sub, exist_ok=True)
        non_empty = os.path.join(self.input_dir, "non_empty")
        os.makedirs(non_empty, exist_ok=True)
        with open(os.path.join(non_empty, "keep.txt"), "w") as f:
            f.write("stay")

        pruned = prune_empty_directories(self.input_dir, dry_run=False)
        self.assertEqual(pruned, 2)
        self.assertFalse(os.path.exists(empty_sub))
        self.assertTrue(os.path.exists(non_empty))

    @patch("app.libs.retention.get_disk_status")
    def test_emergency_disk_cleanup(self, mock_disk):
        # Mock high disk usage: 95% used, 2.0 GB free
        mock_disk.side_effect = [
            (95.0, 2.0, 40.0),  # First check: triggers emergency
            (80.0, 8.0, 40.0)   # Second check: below threshold
        ]

        day_dir = os.path.join(self.input_dir, "322")
        os.makedirs(day_dir, exist_ok=True)
        f1 = os.path.join(day_dir, "OR_ABI-L1b-RadF-M6C13_G19_s20263221000000_e0_c0.nc")
        with open(f1, "wb") as f:
            f.write(b"emergency_bytes")

        del_count, freed = emergency_disk_cleanup(
            self.test_dir, self.input_dir, threshold_percent=85.0, min_free_gb=5.0, dry_run=False
        )
        self.assertEqual(del_count, 1)
        self.assertFalse(os.path.exists(f1))

    def test_run_retention_cycle_integration(self):
        # Setup config dict
        cfg = {
            "paths": {
                "input": "input",
                "output": "output",
                "latest": "latest"
            },
            "retention": {
                "enabled": True,
                "raw_retention_hours": 24.0,
                "output_retention_days": 30.0,
                "disk_threshold_percent": 99.0,
                "min_free_disk_gb": 0.1,
                "clean_empty_folders": True
            }
        }

        # Create an expired raw file
        day_dir = os.path.join(self.input_dir, "300")
        os.makedirs(day_dir, exist_ok=True)
        old_file = os.path.join(day_dir, "OR_ABI-L1b-RadF-M6C13_G19_s20263001200000_e0_c0.nc")
        with open(old_file, "wb") as f:
            f.write(b"x" * 2048)

        # Run full cycle
        stats = run_retention_cycle(base_path=self.test_dir, config=cfg)
        self.assertEqual(stats["raw_deleted"], 1)
        self.assertEqual(stats["dirs_pruned"], 1)  # day_dir 300 should be pruned
        self.assertFalse(os.path.exists(old_file))
        self.assertFalse(os.path.exists(day_dir))


if __name__ == "__main__":
    unittest.main()
