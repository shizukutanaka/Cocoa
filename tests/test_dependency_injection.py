"""Acceptance tests for dependency_injection.py.

Spec: docs/SPEC_DEPENDENCY_INJECTION.md (REQ-DI-01..04)
Runnable without pytest:  python3 -m unittest tests.test_dependency_injection -v
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

import dependency_injection as di  # noqa: E402
from dependency_injection import Container, Dependency, Scope, inject, init_container  # noqa: E402


class _SimpleService:
    def __init__(self):
        self.id = id(self)


class _ServiceWithArgs:
    def __init__(self, host: str, port: int = 8080):
        self.host = host
        self.port = port


class TestDependencyResolve(unittest.TestCase):
    def test_singleton_returns_same_instance(self):
        dep = Dependency(_SimpleService, scope=Scope.SINGLETON)
        a = dep.get_instance()
        b = dep.get_instance()
        self.assertIs(a, b)

    def test_transient_returns_new_instance(self):
        dep = Dependency(_SimpleService, scope=Scope.TRANSIENT)
        a = dep.get_instance()
        b = dep.get_instance()
        self.assertIsNot(a, b)

    def test_resolve_dependencies_with_raw_values(self):
        # GAP-1: raw values in dependencies must not cause AttributeError
        dep = Dependency(
            _ServiceWithArgs,
            scope=Scope.TRANSIENT,
            dependencies={"host": "localhost", "port": 9090}
        )
        resolved = dep.resolve_dependencies()
        self.assertEqual(resolved["host"], "localhost")
        self.assertEqual(resolved["port"], 9090)

    def test_resolve_dependencies_with_dependency_object(self):
        inner = Dependency(lambda: "injected_value", scope=Scope.TRANSIENT)
        outer = Dependency(
            lambda val: val,
            scope=Scope.TRANSIENT,
            dependencies={"val": inner}
        )
        resolved = outer.resolve_dependencies()
        self.assertEqual(resolved["val"], "injected_value")

    def test_resolve_mixed_raw_and_dependency(self):
        inner = Dependency(lambda: "from_dep", scope=Scope.TRANSIENT)
        dep = Dependency(
            lambda a, b: (a, b),
            scope=Scope.TRANSIENT,
            dependencies={"a": "raw_string", "b": inner}
        )
        resolved = dep.resolve_dependencies()
        self.assertEqual(resolved["a"], "raw_string")
        self.assertEqual(resolved["b"], "from_dep")


class TestContainer(unittest.TestCase):
    def setUp(self):
        self.container = Container()

    def test_register_and_resolve_class(self):
        self.container.register(_SimpleService, scope=Scope.TRANSIENT)
        instance = self.container.resolve(_SimpleService)
        self.assertIsInstance(instance, _SimpleService)

    def test_register_with_raw_kwargs_no_crash(self):
        # GAP-1 regression: raw kwarg values must not cause AttributeError
        self.container.register(
            _ServiceWithArgs,
            factory=_ServiceWithArgs,
            scope=Scope.TRANSIENT,
            host="testhost",
            port=1234
        )
        svc = self.container.resolve(_ServiceWithArgs)
        self.assertEqual(svc.host, "testhost")
        self.assertEqual(svc.port, 1234)

    def test_singleton_scope(self):
        self.container.register(_SimpleService, scope=Scope.SINGLETON)
        a = self.container.resolve(_SimpleService)
        b = self.container.resolve(_SimpleService)
        self.assertIs(a, b)

    def test_transient_scope(self):
        self.container.register(_SimpleService, scope=Scope.TRANSIENT)
        a = self.container.resolve(_SimpleService)
        b = self.container.resolve(_SimpleService)
        self.assertIsNot(a, b)

    def test_resolve_unregistered_raises(self):
        with self.assertRaises(ValueError):
            self.container.resolve("UnregisteredService")

    def test_request_scoped_get_set_clear(self):
        self.container.set_request_scoped("user_id", 42)
        self.assertEqual(self.container.get_request_scoped("user_id"), 42)
        self.container.clear_request_scoped()
        self.assertIsNone(self.container.get_request_scoped("user_id"))

    def test_register_string_key_requires_factory(self):
        with self.assertRaises(ValueError):
            self.container.register("MyService")


class TestInjectDecorator(unittest.TestCase):
    def setUp(self):
        init_container()
        di.get_container().register(_SimpleService, scope=Scope.SINGLETON)

    def test_sync_decorator_preserves_name(self):
        # GAP-2: @wraps must preserve __name__
        @inject(_SimpleService)
        def my_handler(**kwargs):
            """My doc."""
            return kwargs

        self.assertEqual(my_handler.__name__, "my_handler")
        self.assertEqual(my_handler.__doc__, "My doc.")

    def test_sync_decorator_injects_dependency(self):
        @inject(_SimpleService)
        def handler(_SimpleService=None, **kwargs):
            return _SimpleService

        result = handler()
        self.assertIsInstance(result, _SimpleService)


if __name__ == "__main__":
    unittest.main(verbosity=2)
