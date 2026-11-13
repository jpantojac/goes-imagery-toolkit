import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import tempfile
import shutil

# Asegurar que 'app' esté en el sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
APP_DIR = os.path.join(PROJECT_ROOT, "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import main


class TestDownloadConcurrency(unittest.TestCase):
    """
    Test suite for multi-threaded concurrent download engine,
    local caching logic, and asynchronous pipeline overlap.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_build_download_tasks(self):
        """Verifies task generation produces the correct Cartesian product across channels and timestamps."""
        with patch.object(main, 'channels', ['01', '09', '13']):
            tasks = main._build_download_tasks(
                dates=['20261112'],
                hours=['02'],
                minutes=['10', '20']
            )
            # 1 date * 1 hour * 2 minutes * 3 channels = 6 tasks
            self.assertEqual(len(tasks), 6)
            for ch, date, hour, minute, dsat, out_dir in tasks:
                self.assertIn(ch, ['01', '09', '13'])
                self.assertEqual(date, '20261112')
                self.assertEqual(hour, '02')
                self.assertIn(minute, ['10', '20'])
                self.assertTrue(out_dir.endswith(os.sep))

    def test_download_channel_slot_cache_hit(self):
        """Verifies that pre-existing local NetCDF files bypass S3 download entirely."""
        out_dir = os.path.join(self.test_dir, "316") + os.sep
        os.makedirs(out_dir, exist_ok=True)
        # Mock file matching: s{YYYY}{julian}{hour}{minute} and C{ch}
        cached_filename = "OR_ABI-L1b-RadF-M6C01_G19_s20263160210205_e20263160219513_c20263160219537.nc"
        cached_path = os.path.join(out_dir, cached_filename)
        with open(cached_path, 'w') as f:
            f.write("mock netcdf data")

        with patch.object(main, 'GOES', MagicMock()) as mock_goes:
            result = main._download_channel_slot(
                ch='01',
                date='20261112',
                hour='02',
                minute='10',
                dsat='goes19',
                output_dir=out_dir
            )
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0], cached_path)
            # GOES.download should NOT be called on cache hit
            mock_goes.download.assert_not_called()

    def test_download_channel_slot_remote_success(self):
        """Verifies remote S3 download invocation when file is not cached locally."""
        out_dir = os.path.join(self.test_dir, "316") + os.sep
        os.makedirs(out_dir, exist_ok=True)
        mock_file = os.path.join(out_dir, "OR_ABI-L1b-RadF-M6C09_G19_s20263160210205.nc")

        mock_goes = MagicMock()
        mock_goes.download.return_value = [mock_file]

        with patch.object(main, 'GOES', mock_goes):
            result = main._download_channel_slot(
                ch='09',
                date='20261112',
                hour='02',
                minute='10',
                dsat='goes19',
                output_dir=out_dir
            )
            self.assertEqual(result, [mock_file])
            mock_goes.download.assert_called_once()
            call_kwargs = mock_goes.download.call_args[1]
            self.assertEqual(call_kwargs['channel'], ['09'])
            self.assertEqual(call_kwargs['show_download_progress'], False)

    def test_download_and_pipeline_concurrent_overlap(self):
        """Verifies concurrent download dispatches on_file_ready callbacks as tasks finish."""
        processed_files = []

        def mock_worker_slot(ch, date, hour, minute, dsat, out_dir):
            mock_path = f"/mock/path/OR_C{int(ch):02d}_{date}_{hour}{minute}.nc"
            return [mock_path]

        with patch.object(main, 'channels', ['01', '09', '13']):
            with patch.object(main, '_download_channel_slot', side_effect=mock_worker_slot):
                with patch.object(main, '_cfg_get', side_effect=lambda sec, *k, default=None: (
                    4 if 'max_download_workers' in k else True if 'enable_pipeline_overlap' in k else default
                )):
                    files = main.download_and_pipeline(
                        dates=['20261112'],
                        hours=['02'],
                        minutes=['10'],
                        on_file_ready=lambda f: processed_files.append(f)
                    )

                    self.assertEqual(len(files), 3)
                    self.assertEqual(len(processed_files), 3)
                    self.assertEqual(set(files), set(processed_files))

    def test_download_and_pipeline_handles_worker_exception(self):
        """Verifies that an error in one channel download does not crash other channels."""
        def mock_worker_slot(ch, date, hour, minute, dsat, out_dir):
            if ch == '09':
                raise RuntimeError("Simulated S3 connection timeout")
            return [f"/mock/path/OR_C{int(ch):02d}.nc"]

        with patch.object(main, 'channels', ['01', '09', '13']):
            with patch.object(main, '_download_channel_slot', side_effect=mock_worker_slot):
                files = main.download_and_pipeline(
                    dates=['20261112'],
                    hours=['02'],
                    minutes=['10']
                )
                # Channels 01 and 13 should succeed even though 09 failed
                self.assertEqual(len(files), 2)
                self.assertTrue(any('C01' in f for f in files))
                self.assertTrue(any('C13' in f for f in files))

    def test_download_legacy_wrapper(self):
        """Verifies legacy download() signature forwards properly to download_and_pipeline."""
        with patch.object(main, 'download_and_pipeline', return_value=['/mock/file.nc']) as mock_dl:
            res = main.download(['20261112'], ['02'], ['10'])
            self.assertEqual(res, ['/mock/file.nc'])
            mock_dl.assert_called_once_with(['20261112'], ['02'], ['10'], on_file_ready=None)


if __name__ == '__main__':
    unittest.main()

