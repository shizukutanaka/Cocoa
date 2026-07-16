"""Acceptance tests for services/shared/config.py.

Spec: docs/SPEC_SERVICES_CONFIG.md (REQ-SC-01..02)
Runnable without pytest:  python3 -m unittest tests.test_services_config -v
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# NOTE: there are two modules named "config" in this repo
# (main/config.py and services/shared/config.py). To avoid the module-name
# collision when the full suite runs, load the services config explicitly from
# its path under a unique module name instead of a bare `import config`.
_SVC_CONFIG_PATH = PROJECT_ROOT / "services" / "shared" / "config.py"
_spec = importlib.util.spec_from_file_location("cocoa_services_shared_config", _SVC_CONFIG_PATH)
svc_config = importlib.util.module_from_spec(_spec)
sys.modules["cocoa_services_shared_config"] = svc_config
_spec.loader.exec_module(svc_config)

CocoaConfig = svc_config.CocoaConfig
ConfigManager = svc_config.ConfigManager
ServiceConfig = svc_config.ServiceConfig
get_config = svc_config.get_config
reset_config = svc_config.reset_config


class _EnvGuard:
    """Context manager that sets env vars and restores them afterwards."""

    def __init__(self, **env):
        self._env = env
        self._saved = {}

    def __enter__(self):
        for k, v in self._env.items():
            self._saved[k] = os.environ.get(k)
            os.environ[k] = v
        return self

    def __exit__(self, *exc):
        for k, old in self._saved.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old


class TestDataclasses(unittest.TestCase):
    def test_service_config_minimal(self):
        sc = ServiceConfig(name="x", port=8000)
        self.assertEqual(sc.host, "0.0.0.0")
        self.assertFalse(sc.debug)
        self.assertEqual(sc.log_level, "INFO")

    def test_service_config_full(self):
        sc = ServiceConfig(name="y", port=9, host="127.0.0.1", debug=True,
                           database_url="sqlite://", log_level="DEBUG")
        self.assertEqual(sc.host, "127.0.0.1")
        self.assertTrue(sc.debug)

    def test_cocoa_config_construction(self):
        cc = CocoaConfig(
            environment="test",
            services={},
            security={},
            database={},
            ai={},
            collaboration={},
        )
        self.assertEqual(cc.environment, "test")


class TestConfigManagerLoad(unittest.TestCase):
    def test_creates_default_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "config.json")
            cm = ConfigManager(config_path=path)
            cfg = cm.load_config()
            self.assertIsInstance(cfg, CocoaConfig)
            self.assertTrue(Path(path).exists())

    def test_creates_default_in_nested_path(self):
        """REQ-SC-02: nested parent dirs must be created."""
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "a" / "b" / "c" / "config.json")
            cm = ConfigManager(config_path=path)
            cfg = cm.load_config()
            self.assertIsInstance(cfg, CocoaConfig)
            self.assertTrue(Path(path).exists())

    def test_default_has_expected_services(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "config.json")
            cm = ConfigManager(config_path=path)
            cfg = cm.load_config()
            self.assertIn("api-gateway", cfg.services)
            self.assertIn("avatar-service", cfg.services)

    def test_reload_uses_existing_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "config.json")
            cm1 = ConfigManager(config_path=path)
            cm1.load_config()
            # Second manager reads the file written by the first
            cm2 = ConfigManager(config_path=path)
            cfg = cm2.load_config()
            self.assertIn("api-gateway", cfg.services)


class TestEnvOverrides(unittest.TestCase):
    """REQ-SC-01: env override keys normalize hyphens to underscores."""

    def test_port_override_for_hyphenated_service(self):
        with tempfile.TemporaryDirectory() as td, _EnvGuard(API_GATEWAY_PORT="9999"):
            path = str(Path(td) / "config.json")
            cm = ConfigManager(config_path=path)
            cfg = cm.load_config()
            self.assertEqual(cfg.services["api-gateway"].port, 9999)

    def test_host_override_for_hyphenated_service(self):
        with tempfile.TemporaryDirectory() as td, _EnvGuard(AVATAR_SERVICE_HOST="10.0.0.5"):
            path = str(Path(td) / "config.json")
            cm = ConfigManager(config_path=path)
            cfg = cm.load_config()
            self.assertEqual(cfg.services["avatar-service"].host, "10.0.0.5")

    def test_debug_override_parsed_as_bool(self):
        with tempfile.TemporaryDirectory() as td, _EnvGuard(AVATAR_SERVICE_DEBUG="true"):
            path = str(Path(td) / "config.json")
            cm = ConfigManager(config_path=path)
            cfg = cm.load_config()
            self.assertIs(cfg.services["avatar-service"].debug, True)

    def test_no_override_keeps_default_port(self):
        # Ensure the override env var is absent
        with tempfile.TemporaryDirectory() as td, _EnvGuard():
            os.environ.pop("API_GATEWAY_PORT", None)
            path = str(Path(td) / "config.json")
            cm = ConfigManager(config_path=path)
            cfg = cm.load_config()
            self.assertEqual(cfg.services["api-gateway"].port, 8000)


class TestGetServiceConfig(unittest.TestCase):
    def test_returns_service_config(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "config.json")
            cm = ConfigManager(config_path=path)
            cm.load_config()
            sc = cm.get_service_config("api-gateway")
            self.assertIsInstance(sc, ServiceConfig)
            self.assertEqual(sc.name, "api-gateway")

    def test_lazy_loads_if_not_loaded(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "config.json")
            cm = ConfigManager(config_path=path)
            # No explicit load_config call
            sc = cm.get_service_config("avatar-service")
            self.assertEqual(sc.name, "avatar-service")

    def test_unknown_service_raises_keyerror(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "config.json")
            cm = ConfigManager(config_path=path)
            cm.load_config()
            with self.assertRaises(KeyError):
                cm.get_service_config("nonexistent-service")


class TestGlobalConfig(unittest.TestCase):
    def setUp(self):
        reset_config()

    def tearDown(self):
        reset_config()

    def test_reset_config_clears_instance(self):
        reset_config()
        self.assertIsNone(svc_config._config_manager)

    def test_get_config_creates_manager(self):
        # get_config() uses the default path; just verify it returns a CocoaConfig
        # within a temp cwd to avoid polluting the repo.
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as td:
            try:
                os.chdir(td)
                reset_config()
                cfg = get_config()
                self.assertIsInstance(cfg, CocoaConfig)
            finally:
                os.chdir(cwd)
                reset_config()


if __name__ == "__main__":
    unittest.main(verbosity=2)
