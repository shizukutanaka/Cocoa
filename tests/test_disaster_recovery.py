"""Acceptance tests for disaster_recovery.py.

Spec: docs/SPEC_DISASTER_RECOVERY.md (REQ-DR-01..02)
Runnable without pytest:  python3 -m unittest tests.test_disaster_recovery -v
"""
import sys
import tempfile
import unittest
from datetime import timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from disaster_recovery import (
    BackupMetadata,
    BackupStatus,
    DisasterRecoveryManager,
    initialize_disaster_recovery,
)


def _make_manager(tmpdir):
    return DisasterRecoveryManager({
        'backup_dir': str(tmpdir / 'backups'),
        'data_dir': str(tmpdir / 'data'),
        'config_dir': str(tmpdir / 'config'),
    })


class TestInitialization(unittest.TestCase):
    """REQ-DR-01: __init__ must initialize backup_metadata, metadata_file, and call _load_metadata."""

    def test_constructor_does_not_raise(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(Path(td))
            self.assertIsNotNone(mgr)

    def test_backup_metadata_initialized_as_list(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(Path(td))
            self.assertIsInstance(mgr.backup_metadata, list)

    def test_backup_metadata_empty_on_fresh_instance(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(Path(td))
            self.assertEqual(mgr.backup_metadata, [])

    def test_metadata_file_attribute_exists(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(Path(td))
            self.assertIsInstance(mgr.metadata_file, Path)

    def test_list_backups_does_not_raise_on_fresh_instance(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(Path(td))
            result = mgr.list_backups()
            self.assertEqual(result, [])

    def test_get_recovery_status_does_not_raise(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(Path(td))
            status = mgr.get_recovery_status()
            self.assertIsInstance(status, dict)

    def test_retention_policy_initialized(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(Path(td))
            self.assertIn('daily', mgr.retention_policy)
            self.assertIn('yearly', mgr.retention_policy)


class TestUtcTimestamps(unittest.TestCase):
    """REQ-DR-02: all timestamps must be UTC-aware."""

    def test_get_recovery_status_timestamp_is_utc(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(Path(td))
            status = mgr.get_recovery_status()
            ts = status["timestamp"]
            self.assertTrue(ts.endswith("+00:00"), f"Non-UTC timestamp: {ts!r}")

    def test_get_earliest_retention_date_is_utc_aware(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(Path(td))
            dt = mgr._get_earliest_retention_date()
            self.assertIsNotNone(dt.tzinfo)
            self.assertEqual(dt.tzinfo, timezone.utc)


class TestListBackups(unittest.TestCase):
    def test_list_backups_empty_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(Path(td))
            result = mgr.list_backups()
            self.assertIsInstance(result, list)

    def test_list_backups_verified_only_filters(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(Path(td))
            # Manually add fake metadata
            from datetime import datetime
            mgr.backup_metadata.append(BackupMetadata(
                backup_id="b1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                status=BackupStatus.VERIFIED,
                size_bytes=100,
                checksum="abc",
                verification_passed=True,
            ))
            mgr.backup_metadata.append(BackupMetadata(
                backup_id="b2",
                timestamp=datetime.now(timezone.utc).isoformat(),
                status=BackupStatus.COMPLETED,
                size_bytes=50,
                checksum="def",
                verification_passed=False,
            ))
            verified = mgr.list_backups(verified_only=True)
            self.assertEqual(len(verified), 1)
            self.assertEqual(verified[0].backup_id, "b1")

    def test_list_backups_all_returns_all(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(Path(td))
            from datetime import datetime
            mgr.backup_metadata.append(BackupMetadata(
                backup_id="b1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                status=BackupStatus.COMPLETED,
                size_bytes=100,
                checksum="abc",
                verification_passed=False,
            ))
            result = mgr.list_backups()
            self.assertEqual(len(result), 1)


class TestGetRecoveryStatus(unittest.TestCase):
    def test_status_has_required_keys(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(Path(td))
            status = mgr.get_recovery_status()
            for key in ("total_backups", "verified_backups", "total_size_bytes", "latest_backup"):
                self.assertIn(key, status)

    def test_status_latest_backup_is_none_when_empty(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(Path(td))
            status = mgr.get_recovery_status()
            self.assertIsNone(status["latest_backup"])

    def test_status_counts_correct(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(Path(td))
            from datetime import datetime
            mgr.backup_metadata.append(BackupMetadata(
                backup_id="x1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                status=BackupStatus.VERIFIED,
                size_bytes=1024,
                checksum="aaa",
                verification_passed=True,
            ))
            status = mgr.get_recovery_status()
            self.assertEqual(status["total_backups"], 1)
            self.assertEqual(status["verified_backups"], 1)
            self.assertEqual(status["total_size_bytes"], 1024)


class TestGlobalInstance(unittest.TestCase):
    def setUp(self):
        import disaster_recovery
        disaster_recovery._recovery_manager = None

    def test_initialize_disaster_recovery_returns_manager(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = initialize_disaster_recovery({
                'backup_dir': str(Path(td) / 'b'),
                'data_dir': str(Path(td) / 'd'),
                'config_dir': str(Path(td) / 'c'),
            })
            self.assertIsInstance(mgr, DisasterRecoveryManager)


if __name__ == "__main__":
    unittest.main(verbosity=2)
