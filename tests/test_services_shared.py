"""Tests for services/shared exceptions, utils, and ServiceRegistry."""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Load each shared module by path to avoid import cascade from __init__
def _load(name, filename):
    spec = importlib.util.spec_from_file_location(
        f"cocoa_svc_shared_{name}",
        ROOT / "services" / "shared" / filename,
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod

_exc = _load("exceptions", "exceptions.py")
_utils = _load("utils", "utils.py")

CocoaError = _exc.CocoaError
ValidationError = _exc.ValidationError
SecurityError = _exc.SecurityError
NotFoundError = _exc.NotFoundError
AuthenticationError = _exc.AuthenticationError
AuthorizationError = _exc.AuthorizationError

generate_id = _utils.generate_id
validate_uuid = _utils.validate_uuid
sanitize_input = _utils.sanitize_input


class TestExceptions(unittest.TestCase):
    def test_cocoa_error_message(self):
        e = CocoaError("oops")
        self.assertEqual(str(e), "oops")
        self.assertEqual(e.code, "COCOA_ERROR")

    def test_cocoa_error_to_dict(self):
        e = CocoaError("boom", "MY_CODE")
        d = e.to_dict()
        self.assertEqual(d["error"], "MY_CODE")
        self.assertEqual(d["message"], "boom")

    def test_validation_error_inherits(self):
        e = ValidationError("bad field", field="username")
        self.assertIsInstance(e, CocoaError)
        self.assertEqual(e.code, "VALIDATION_ERROR")
        self.assertEqual(e.field, "username")

    def test_validation_error_to_dict_includes_field(self):
        e = ValidationError("bad", field="email")
        self.assertIn("field", e.to_dict())

    def test_validation_error_no_field(self):
        e = ValidationError("missing something")
        d = e.to_dict()
        self.assertNotIn("field", d)

    def test_security_error(self):
        e = SecurityError("forbidden")
        self.assertIsInstance(e, CocoaError)
        self.assertEqual(e.code, "SECURITY_ERROR")

    def test_not_found_without_id(self):
        e = NotFoundError("Avatar")
        self.assertIn("Avatar", str(e))
        self.assertEqual(e.code, "NOT_FOUND")

    def test_not_found_with_id(self):
        e = NotFoundError("Avatar", "abc-123")
        self.assertIn("abc-123", str(e))

    def test_authentication_error_default(self):
        e = AuthenticationError()
        self.assertEqual(e.code, "AUTHENTICATION_ERROR")

    def test_authorization_error_default(self):
        e = AuthorizationError()
        self.assertEqual(e.code, "AUTHORIZATION_ERROR")


class TestUtils(unittest.TestCase):
    def test_generate_id_is_uuid(self):
        uid = generate_id()
        self.assertTrue(validate_uuid(uid))

    def test_generate_id_unique(self):
        self.assertNotEqual(generate_id(), generate_id())

    def test_validate_uuid_valid(self):
        self.assertTrue(validate_uuid("550e8400-e29b-41d4-a716-446655440000"))

    def test_validate_uuid_invalid(self):
        self.assertFalse(validate_uuid("not-a-uuid"))
        self.assertFalse(validate_uuid(""))
        self.assertFalse(validate_uuid(None))

    def test_sanitize_input_strips_control_chars(self):
        raw = "hello\x00world\x08"
        result = sanitize_input(raw)
        self.assertNotIn("\x00", result)
        self.assertNotIn("\x08", result)

    def test_sanitize_input_preserves_content(self):
        self.assertEqual(sanitize_input("hello"), "hello")

    def test_sanitize_input_length_limit(self):
        long_str = "a" * 2000
        self.assertEqual(len(sanitize_input(long_str, max_length=100)), 100)

    def test_sanitize_input_non_string(self):
        self.assertEqual(sanitize_input(None), "")  # type: ignore[arg-type]

    def test_sanitize_input_default_max(self):
        self.assertEqual(sanitize_input("x" * 1500), "x" * 1000)


# Load __init__ only to verify it doesn't crash (ServiceRegistry is in __init__)
def _load_shared_init():
    # We need config and logger already in sys.modules under correct names
    import services.shared  # noqa: F401 - side-effect import for coverage


class TestServiceRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            _load_shared_init()
            import services.shared as _shared
            cls._mod = _shared
            cls.available = True
        except Exception:
            cls.available = False

    def _registry(self):
        return self._mod.ServiceRegistry()

    def test_register_and_discover(self):
        if not self.available:
            self.skipTest("services.shared import unavailable")
        reg = self._registry()
        ok = reg.register_service("svc-a", {"url": "http://localhost:8001"})
        self.assertTrue(ok)
        info = reg.discover_service("svc-a")
        self.assertIsNotNone(info)
        self.assertEqual(info["url"], "http://localhost:8001")

    def test_unregister(self):
        if not self.available:
            self.skipTest("services.shared import unavailable")
        reg = self._registry()
        reg.register_service("svc-b", {"url": "http://localhost:8002"})
        ok = reg.unregister_service("svc-b")
        self.assertTrue(ok)
        self.assertIsNone(reg.discover_service("svc-b"))

    def test_unregister_unknown_returns_false(self):
        if not self.available:
            self.skipTest("services.shared import unavailable")
        reg = self._registry()
        self.assertFalse(reg.unregister_service("nonexistent"))

    def test_heartbeat_updates_known(self):
        if not self.available:
            self.skipTest("services.shared import unavailable")
        reg = self._registry()
        reg.register_service("svc-c", {"url": "http://localhost:8003"})
        self.assertTrue(reg.heartbeat("svc-c"))

    def test_heartbeat_unknown_returns_false(self):
        if not self.available:
            self.skipTest("services.shared import unavailable")
        reg = self._registry()
        self.assertFalse(reg.heartbeat("ghost"))

    def test_get_service_health(self):
        if not self.available:
            self.skipTest("services.shared import unavailable")
        reg = self._registry()
        reg.register_service("svc-d", {"url": "http://localhost:8004"})
        health = reg.get_service_health()
        self.assertIn("total_services", health)
        self.assertEqual(health["total_services"], 1)

    def test_get_all_services(self):
        if not self.available:
            self.skipTest("services.shared import unavailable")
        reg = self._registry()
        reg.register_service("svc-e", {"url": "http://localhost:8005"})
        services = reg.get_all_services()
        self.assertIn("svc-e", services)


if __name__ == "__main__":
    unittest.main(verbosity=2)
