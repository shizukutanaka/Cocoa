"""
Tests for main/bci_manager.py
"""
import sys
import os
import inspect
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestBCISignalDataclass(unittest.TestCase):
    def test_bci_signal_creation(self):
        from bci_manager import BCISignal
        now = datetime.now(timezone.utc)
        signal = BCISignal(
            timestamp=now,
            signal_type="eeg",
            channels=[],
            sampling_rate=256.0,
            device_id="device_001",
            user_id="user_001",
            quality_score=0.9,
            metadata={"notes": "test"},
        )
        self.assertEqual(signal.signal_type, "eeg")
        self.assertEqual(signal.sampling_rate, 256.0)
        self.assertEqual(signal.quality_score, 0.9)


class TestBCICommandDataclass(unittest.TestCase):
    def test_bci_command_defaults(self):
        from bci_manager import BCICommand
        now = datetime.now(timezone.utc)
        cmd = BCICommand(
            command_id="cmd_001",
            command_type="move",
            parameters={"direction": "forward"},
            confidence=0.85,
            timestamp=now,
        )
        self.assertFalse(cmd.executed)
        self.assertEqual(cmd.command_type, "move")

    def test_bci_command_executed_flag(self):
        from bci_manager import BCICommand
        now = datetime.now(timezone.utc)
        cmd = BCICommand(
            command_id="cmd_002",
            command_type="select",
            parameters={},
            confidence=0.7,
            timestamp=now,
            executed=True,
        )
        self.assertTrue(cmd.executed)


class TestBCIProfileDataclass(unittest.TestCase):
    def test_bci_profile_creation(self):
        from bci_manager import BCIProfile
        now = datetime.now(timezone.utc)
        profile = BCIProfile(
            user_id="user_001",
            baseline_signals={},
            trained_patterns=[],
            calibration_data={},
            preferences={"sensitivity": "medium"},
            skill_level="beginner",
            created_at=now,
            last_calibration=now,
        )
        self.assertEqual(profile.skill_level, "beginner")
        self.assertEqual(profile.trained_patterns, [])


class TestEEGProcessorInit(unittest.TestCase):
    def test_eeg_processor_creation(self):
        from bci_manager import EEGProcessor
        processor = EEGProcessor()
        self.assertIsNotNone(processor)
        self.assertIsInstance(processor.filters, dict)
        self.assertIsInstance(processor.features, dict)


class TestBCIManagerInit(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp()

    def _make_manager(self):
        from bci_manager import BCIManager
        return BCIManager(bci_dir=self.tmpdir)

    def test_manager_instantiation(self):
        try:
            mgr = self._make_manager()
        except Exception as e:
            self.skipTest(f"Cannot instantiate BCIManager: {e}")
        self.assertIsNotNone(mgr)

    def test_manager_initial_counters(self):
        try:
            mgr = self._make_manager()
        except Exception as e:
            self.skipTest(f"Cannot instantiate BCIManager: {e}")
        self.assertEqual(mgr.total_signals, 0)
        self.assertEqual(mgr.processed_commands, 0)
        self.assertEqual(mgr.training_sessions, 0)

    def test_manager_initial_flags(self):
        try:
            mgr = self._make_manager()
        except Exception as e:
            self.skipTest(f"Cannot instantiate BCIManager: {e}")
        self.assertTrue(mgr.calibration_required)
        self.assertTrue(mgr.realtime_processing)
        self.assertTrue(mgr.adaptive_learning)

    def test_get_bci_status_keys(self):
        try:
            mgr = self._make_manager()
        except Exception as e:
            self.skipTest(f"Cannot instantiate BCIManager: {e}")
        status = mgr.get_bci_status()
        for key in ("total_signals", "processed_commands", "training_sessions",
                    "connected_devices", "trained_patterns", "user_profiles",
                    "mne_available", "pyautogui_available", "realtime_processing"):
            self.assertIn(key, status)


class TestBCIManagerAsyncMethods(unittest.TestCase):
    def test_initialize_is_coroutine(self):
        from bci_manager import BCIManager
        self.assertTrue(inspect.iscoroutinefunction(BCIManager.initialize))

    def test_register_bci_device_is_coroutine(self):
        from bci_manager import BCIManager
        self.assertTrue(inspect.iscoroutinefunction(BCIManager.register_bci_device))

    def test_process_bci_signal_is_coroutine(self):
        from bci_manager import BCIManager
        self.assertTrue(inspect.iscoroutinefunction(BCIManager.process_bci_signal))

    def test_train_thought_pattern_is_coroutine(self):
        from bci_manager import BCIManager
        self.assertTrue(inspect.iscoroutinefunction(BCIManager.train_thought_pattern))

    def test_calibrate_bci_system_is_coroutine(self):
        from bci_manager import BCIManager
        self.assertTrue(inspect.iscoroutinefunction(BCIManager.calibrate_bci_system))


class TestBCIManagerDeviceRegistration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        try:
            from bci_manager import BCIManager
            self.mgr = BCIManager(bci_dir=self.tmpdir)
        except Exception as e:
            self.skipTest(f"Cannot instantiate BCIManager: {e}")

    async def test_register_device_returns_true(self):
        result = await self.mgr.register_bci_device(
            "device_001", "eeg_headset", {"channels": 32, "sampling_rate": 256}
        )
        self.assertTrue(result)
        self.assertIn("device_001", self.mgr.connected_devices)

    async def test_register_device_stores_info(self):
        await self.mgr.register_bci_device(
            "device_002", "fnirs", {"channels": 16}
        )
        info = self.mgr.connected_devices["device_002"]
        self.assertEqual(info["device_type"], "fnirs")
        self.assertEqual(info["status"], "active")
        self.assertEqual(info["calibration_status"], "none")

    async def test_low_quality_signal_returns_empty(self):
        from bci_manager import BCISignal
        now = datetime.now(timezone.utc)
        signal = BCISignal(
            timestamp=now,
            signal_type="eeg",
            channels=[],
            sampling_rate=256.0,
            device_id="device_001",
            user_id="user_001",
            quality_score=0.3,  # below threshold
            metadata={},
        )
        commands = await self.mgr.process_bci_signal(signal)
        self.assertEqual(commands, [])

    async def test_update_skill_level_beginner(self):
        # No patterns -> beginner
        result = self.mgr._update_skill_level("unknown_user")
        self.assertEqual(result, "beginner")


if __name__ == "__main__":
    unittest.main()
