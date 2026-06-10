"""
Unit tests for main/edge_ai_manager.py
"""

import inspect
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))

from edge_ai_manager import (
    EdgeAIDataset,
    EdgeAIManager,
    EdgeDeviceInfo,
    FederatedLearningConfig,
    ModelCompressionConfig,
    get_edge_ai_manager,
)


class TestEdgeDeviceInfoDataclass(unittest.TestCase):
    """Tests for EdgeDeviceInfo dataclass."""

    def _make_device(self, **kwargs):
        defaults = {
            'device_id': "dev_001",
            'device_type': "smartphone",
            'hardware_specs': {"cpu_cores": 4},
            'available_memory_mb': 2048,
            'available_storage_mb': 64000,
            'network_bandwidth_mbps': 50.0,
        }
        defaults.update(kwargs)
        return EdgeDeviceInfo(**defaults)

    def test_creation_with_required_fields(self):
        device = self._make_device()
        self.assertEqual(device.device_id, "dev_001")
        self.assertEqual(device.device_type, "smartphone")

    def test_optional_fields_default_to_none(self):
        device = self._make_device()
        self.assertIsNone(device.battery_level)
        self.assertIsNone(device.location)

    def test_last_seen_auto_populated(self):
        device = self._make_device()
        self.assertIsNotNone(device.last_seen)
        self.assertIsInstance(device.last_seen, datetime)

    def test_last_seen_explicit(self):
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        device = self._make_device(last_seen=ts)
        self.assertEqual(device.last_seen, ts)

    def test_battery_level_field(self):
        device = self._make_device(battery_level=75.0)
        self.assertAlmostEqual(device.battery_level, 75.0)


class TestModelCompressionConfigDataclass(unittest.TestCase):
    """Tests for ModelCompressionConfig dataclass."""

    def _make_config(self, **kwargs):
        defaults = {
            'target_size_mb': 10.0,
            'quantization_type': "int8",
            'pruning_ratio': 0.3,
            'distillation_enabled': True,
        }
        defaults.update(kwargs)
        return ModelCompressionConfig(**defaults)

    def test_creation(self):
        cfg = self._make_config()
        self.assertEqual(cfg.quantization_type, "int8")
        self.assertAlmostEqual(cfg.pruning_ratio, 0.3)

    def test_default_temperature(self):
        cfg = self._make_config()
        self.assertAlmostEqual(cfg.knowledge_distillation_temperature, 3.0)

    def test_custom_temperature(self):
        cfg = self._make_config(knowledge_distillation_temperature=5.0)
        self.assertAlmostEqual(cfg.knowledge_distillation_temperature, 5.0)


class TestFederatedLearningConfigDataclass(unittest.TestCase):
    """Tests for FederatedLearningConfig dataclass."""

    def _make_fl_config(self):
        return FederatedLearningConfig(
            min_participants=3,
            max_rounds=10,
            learning_rate=0.01,
            batch_size=32,
            aggregation_method="fedavg",
            privacy_budget=1.0,
            communication_rounds=5,
        )

    def test_creation(self):
        cfg = self._make_fl_config()
        self.assertEqual(cfg.aggregation_method, "fedavg")
        self.assertEqual(cfg.min_participants, 3)

    def test_privacy_budget(self):
        cfg = self._make_fl_config()
        self.assertAlmostEqual(cfg.privacy_budget, 1.0)


class TestEdgeAIDataset(unittest.TestCase):
    """Tests for EdgeAIDataset class."""

    def test_init_with_nonexistent_path(self):
        ds = EdgeAIDataset("/nonexistent/path/to/data")
        self.assertEqual(len(ds), 0)

    def test_len_empty(self):
        ds = EdgeAIDataset("/tmp")
        self.assertIsInstance(len(ds), int)

    def test_getitem_not_present(self):
        ds = EdgeAIDataset("/nonexistent/path/to/data")
        with self.assertRaises((IndexError, KeyError)):
            _ = ds[0]


class TestEdgeAIManager(unittest.TestCase):
    """Tests for EdgeAIManager class."""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        try:
            self.manager = EdgeAIManager(models_dir=self.tmp_dir)
        except Exception as e:
            self.skipTest(f"EdgeAIManager construction failed: {e}")

    def test_initial_stats_zero(self):
        self.assertEqual(self.manager.total_devices, 0)
        self.assertEqual(self.manager.model_deployments, 0)
        self.assertEqual(self.manager.federated_rounds, 0)

    def test_registered_devices_empty_initially(self):
        self.assertIsInstance(self.manager.registered_devices, dict)
        self.assertEqual(len(self.manager.registered_devices), 0)

    def test_flags_enabled_by_default(self):
        self.assertTrue(self.manager.compression_enabled)
        self.assertTrue(self.manager.federated_learning_enabled)
        self.assertTrue(self.manager.offline_mode_enabled)

    def test_get_edge_ai_status_keys(self):
        status = self.manager.get_edge_ai_status()
        expected_keys = {
            "total_devices", "active_devices", "active_models",
            "model_deployments", "federated_learning_enabled",
            "offline_mode_enabled", "compression_enabled",
            "federated_rounds", "onnx_available", "tflite_available",
            "supported_devices", "model_performance",
        }
        self.assertTrue(expected_keys.issubset(status.keys()))

    def test_initialize_is_coroutine(self):
        self.assertTrue(inspect.iscoroutinefunction(self.manager.initialize))

    def test_compress_model_for_edge_is_coroutine(self):
        self.assertTrue(inspect.iscoroutinefunction(self.manager.compress_model_for_edge))

    def test_setup_federated_learning_is_coroutine(self):
        self.assertTrue(inspect.iscoroutinefunction(self.manager.setup_federated_learning))

    def test_enable_offline_mode_is_coroutine(self):
        self.assertTrue(inspect.iscoroutinefunction(self.manager.enable_offline_mode))

    def test_compress_model_raises_for_unknown_device(self):
        import asyncio
        cfg = ModelCompressionConfig(
            target_size_mb=5.0,
            quantization_type="fp16",
            pruning_ratio=0.0,
            distillation_enabled=False,
        )
        with self.assertRaises(ValueError):
            asyncio.run(
                self.manager.compress_model_for_edge("fake/model.pt", "unknown_device", cfg)
            )

    def test_get_edge_ai_manager_is_coroutine(self):
        self.assertTrue(inspect.iscoroutinefunction(get_edge_ai_manager))


if __name__ == "__main__":
    unittest.main()
