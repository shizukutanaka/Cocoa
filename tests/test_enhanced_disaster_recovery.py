"""Acceptance tests for enhanced_disaster_recovery.py.

Spec: docs/SPEC_ENHANCED_DISASTER_RECOVERY.md (REQ-EDR-01)
Runnable without pytest:  python3 -m unittest tests.test_enhanced_disaster_recovery -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from enhanced_disaster_recovery import (  # noqa: E402
    BackupConfig,
    BackupLocation,
    BackupMetadata,
    Enhanced321BackupManager,
    RecoveryStrategy,
    RPOConfig,
    RTOConfig,
    StorageType,
    TestType,
)


class TestEnums(unittest.TestCase):
    def test_storage_type_has_members(self):
        members = [e.value for e in StorageType]
        self.assertGreater(len(members), 0)

    def test_backup_location_has_members(self):
        members = [e.value for e in BackupLocation]
        self.assertGreater(len(members), 0)

    def test_recovery_strategy_has_members(self):
        members = [e.value for e in RecoveryStrategy]
        self.assertGreater(len(members), 0)

    def test_test_type_has_members(self):
        members = [e.value for e in TestType]
        self.assertGreater(len(members), 0)


class TestDataclasses(unittest.TestCase):
    def test_rpo_config_defaults(self):
        cfg = RPOConfig()
        self.assertEqual(cfg.target_minutes, 60)
        self.assertEqual(cfg.backup_interval_minutes, 30)

    def test_rto_config_defaults(self):
        cfg = RTOConfig()
        self.assertEqual(cfg.target_minutes, 240)

    def test_rpo_config_custom(self):
        cfg = RPOConfig(target_minutes=30, backup_interval_minutes=15)
        self.assertEqual(cfg.target_minutes, 30)

    def test_backup_config_construction(self):
        cfg = BackupConfig(
            path=Path("/tmp"),
            storage_type=StorageType.LOCAL_SSD,
        )
        self.assertEqual(cfg.storage_type, StorageType.LOCAL_SSD)
        self.assertTrue(cfg.encryption)

    def test_backup_metadata_construction(self):
        from datetime import datetime, timezone
        meta = BackupMetadata(
            backup_id="bk-001",
            timestamp=datetime.now(timezone.utc),
            location=BackupLocation.ONSITE_PRIMARY,
            storage_type=StorageType.LOCAL_SSD,
            size_bytes=1024,
            checksum_sha256="abc123",
            verified=True,
        )
        self.assertEqual(meta.backup_id, "bk-001")
        self.assertIsNotNone(meta.timestamp.tzinfo)


class TestEnhanced321BackupManagerInit(unittest.TestCase):
    def test_default_constructor_does_not_raise(self):
        with tempfile.TemporaryDirectory():
            mgr = Enhanced321BackupManager()
            self.assertIsNotNone(mgr)

    def test_custom_rpo_applied(self):
        rpo = RPOConfig(target_minutes=15)
        mgr = Enhanced321BackupManager(rpo_config=rpo)
        self.assertEqual(mgr.rpo.target_minutes, 15)

    def test_custom_rto_applied(self):
        rto = RTOConfig(target_minutes=120)
        mgr = Enhanced321BackupManager(rto_config=rto)
        self.assertEqual(mgr.rto.target_minutes, 120)

    def test_backup_locations_initialized(self):
        mgr = Enhanced321BackupManager()
        self.assertIsInstance(mgr.backup_locations, dict)
        self.assertGreater(len(mgr.backup_locations), 0)

    def test_metadata_dir_created(self):
        mgr = Enhanced321BackupManager()
        self.assertTrue(mgr.metadata_dir.exists())


class TestListBackups(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.original_metadata_dir = None

    def test_list_backups_empty_returns_list(self):
        mgr = Enhanced321BackupManager()
        mgr.metadata_dir = Path(self.tmpdir) / "meta"
        mgr.metadata_dir.mkdir(parents=True, exist_ok=True)
        result = mgr.list_backups()
        self.assertIsInstance(result, list)

    def test_list_backups_empty_dir(self):
        mgr = Enhanced321BackupManager()
        mgr.metadata_dir = Path(self.tmpdir) / "meta2"
        mgr.metadata_dir.mkdir(parents=True, exist_ok=True)
        result = mgr.list_backups()
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
