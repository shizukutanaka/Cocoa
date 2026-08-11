"""Acceptance tests for health_monitor.py.

Spec: docs/SPEC_HEALTH_MONITOR.md (REQ-HM-01..02)
Runnable without pytest:  python3 -m unittest tests.test_health_monitor -v
"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from health_monitor import (
    HealthCheckResult,
    HealthMonitor,
    HealthStatus,
    get_health_monitor,
    initialize_health_monitoring,
)


class TestHealthCheckResultTimestamp(unittest.TestCase):
    """REQ-HM-01: timestamps use UTC (not deprecated utcnow)."""

    def test_result_timestamp_ends_with_utc_offset(self):
        result = HealthCheckResult(
            component="test", status=HealthStatus.HEALTHY, message="ok"
        )
        self.assertTrue(
            result.timestamp.endswith("+00:00"),
            f"Expected UTC offset in timestamp, got: {result.timestamp!r}"
        )

    def test_run_all_checks_timestamp_is_utc(self):
        monitor = HealthMonitor()
        report = monitor.run_all_checks()
        ts = report["timestamp"]
        self.assertTrue(ts.endswith("+00:00"), f"Non-UTC timestamp: {ts!r}")

    def test_get_liveness_timestamp_is_utc(self):
        monitor = HealthMonitor()
        result = monitor.get_liveness()
        ts = result["timestamp"]
        self.assertTrue(ts.endswith("+00:00"), f"Non-UTC timestamp: {ts!r}")

    def test_get_readiness_timestamp_is_utc(self):
        monitor = HealthMonitor()
        result = monitor.get_readiness()
        ts = result["timestamp"]
        self.assertTrue(ts.endswith("+00:00"), f"Non-UTC timestamp: {ts!r}")


class TestRegisterCheck(unittest.TestCase):
    """REQ-HM-02: register_check validates callable."""

    def test_register_non_callable_raises_type_error(self):
        monitor = HealthMonitor()
        with self.assertRaises(TypeError):
            monitor.register_check("bad_check", "not_a_function")

    def test_register_none_raises_type_error(self):
        monitor = HealthMonitor()
        with self.assertRaises(TypeError):
            monitor.register_check("bad_check", None)

    def test_register_callable_succeeds(self):
        monitor = HealthMonitor()

        def my_check():
            return HealthCheckResult(
                component="custom", status=HealthStatus.HEALTHY, message="ok"
            )

        monitor.register_check("custom_check", my_check)
        self.assertIn("custom_check", monitor.checks)

    def test_registered_check_runs_in_all_checks(self):
        monitor = HealthMonitor()

        def always_healthy():
            return HealthCheckResult(
                component="always_healthy", status=HealthStatus.HEALTHY, message="ok"
            )

        monitor.register_check("always_healthy", always_healthy)
        report = monitor.run_all_checks()
        self.assertIn("always_healthy", report["checks"])
        self.assertEqual(report["checks"]["always_healthy"]["status"], "healthy")

    def test_lambda_check_accepted(self):
        monitor = HealthMonitor()
        monitor.register_check(
            "lambda_check",
            lambda: HealthCheckResult(
                component="lambda_check", status=HealthStatus.HEALTHY, message="ok"
            )
        )
        result = monitor.run_check("lambda_check")
        self.assertIsNotNone(result)
        self.assertEqual(result.status, HealthStatus.HEALTHY)


class TestRunCheck(unittest.TestCase):
    def test_run_unknown_check_returns_none(self):
        monitor = HealthMonitor()
        result = monitor.run_check("nonexistent_check")
        self.assertIsNone(result)

    def test_run_check_sets_response_time(self):
        monitor = HealthMonitor()

        def slow_check():
            return HealthCheckResult(
                component="slow", status=HealthStatus.HEALTHY, message="ok"
            )

        monitor.register_check("slow", slow_check)
        result = monitor.run_check("slow")
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.response_time_ms, 0)


class TestGetLiveness(unittest.TestCase):
    def test_liveness_returns_alive_true(self):
        monitor = HealthMonitor()
        result = monitor.get_liveness()
        self.assertTrue(result["alive"])

    def test_liveness_has_uptime_seconds(self):
        monitor = HealthMonitor()
        # Windows' monotonic clock ticks at ~15.6ms, so a 10ms sleep can leave
        # uptime at exactly 0.0 and flake. Sleep past one tick.
        time.sleep(0.05)
        result = monitor.get_liveness()
        self.assertGreater(result["uptime_seconds"], 0)

    def test_liveness_has_timestamp(self):
        monitor = HealthMonitor()
        result = monitor.get_liveness()
        self.assertIn("timestamp", result)


class TestGetReadiness(unittest.TestCase):
    def test_readiness_has_ready_key(self):
        monitor = HealthMonitor()
        result = monitor.get_readiness()
        self.assertIn("ready", result)

    def test_readiness_has_checks_key(self):
        monitor = HealthMonitor()
        result = monitor.get_readiness()
        self.assertIn("checks", result)

    def test_readiness_has_timestamp(self):
        monitor = HealthMonitor()
        result = monitor.get_readiness()
        self.assertIn("timestamp", result)


class TestRunAllChecks(unittest.TestCase):
    def test_run_all_checks_returns_status(self):
        monitor = HealthMonitor()
        report = monitor.run_all_checks()
        self.assertIn("status", report)
        self.assertIn(report["status"], ["healthy", "degraded", "unhealthy", "critical"])

    def test_run_all_checks_has_summary(self):
        monitor = HealthMonitor()
        report = monitor.run_all_checks()
        self.assertIn("summary", report)
        summary = report["summary"]
        self.assertIn("total_checks", summary)
        self.assertIn("status_counts", summary)

    def test_critical_check_makes_overall_critical(self):
        monitor = HealthMonitor()

        def critical_check():
            return HealthCheckResult(
                component="critical_one", status=HealthStatus.CRITICAL, message="down"
            )

        monitor.register_check("critical_one", critical_check)
        report = monitor.run_all_checks()
        self.assertEqual(report["status"], "critical")

    def test_global_instance_returns_health_monitor(self):
        monitor = get_health_monitor()
        self.assertIsInstance(monitor, HealthMonitor)

    def test_initialize_returns_new_instance(self):
        monitor = initialize_health_monitoring({"custom": True})
        self.assertIsInstance(monitor, HealthMonitor)


class TestStatusPropagation(unittest.TestCase):
    """Enum-based status comparison — verifies the fix to .value string comparison."""

    def _monitor_with_results(self, *statuses):
        monitor = HealthMonitor.__new__(HealthMonitor)
        monitor.checks = {}
        monitor.last_results = {}
        monitor.startup_time = time.time()
        for i, status in enumerate(statuses):
            s = status
            monitor.checks[f"check_{i}"] = lambda s=s, i=i: HealthCheckResult(
                component=f"check_{i}", status=s, message="test"
            )
        return monitor

    def test_degraded_overrides_healthy(self):
        m = self._monitor_with_results(HealthStatus.HEALTHY, HealthStatus.DEGRADED)
        self.assertEqual(m.run_all_checks()["status"], "degraded")

    def test_unhealthy_overrides_degraded(self):
        m = self._monitor_with_results(HealthStatus.DEGRADED, HealthStatus.UNHEALTHY)
        self.assertEqual(m.run_all_checks()["status"], "unhealthy")

    def test_critical_overrides_all(self):
        m = self._monitor_with_results(
            HealthStatus.UNHEALTHY, HealthStatus.CRITICAL, HealthStatus.DEGRADED
        )
        self.assertEqual(m.run_all_checks()["status"], "critical")

    def test_critical_not_downgraded_by_unhealthy(self):
        m = self._monitor_with_results(HealthStatus.CRITICAL, HealthStatus.UNHEALTHY)
        self.assertEqual(m.run_all_checks()["status"], "critical")

    def test_enum_not_string(self):
        """Status enum members must not equal their .value strings."""
        self.assertNotEqual(HealthStatus.CRITICAL, "critical")
        self.assertEqual(HealthStatus.CRITICAL, HealthStatus.CRITICAL)


class TestMonotonicClock(unittest.TestCase):
    """Health monitor durations must use time.monotonic(), not time.time().

    Qiita/Zenn anti-pattern: time.time() is wall-clock — NTP, manual time
    adjustment, or DST transitions can move it backward mid-measurement,
    producing negative durations (or wildly wrong uptime). time.monotonic()
    only ever moves forward and is the canonical Python choice for elapsed
    time and uptime.

    These tests prove the source uses monotonic by patching it.
    """

    def test_response_time_uses_monotonic(self):
        from unittest.mock import patch
        monitor = HealthMonitor()
        # Provide a check that completes "instantly"; monotonic supplies
        # the start/end timestamps. If the source still used time.time(),
        # patching monotonic would have no effect → response_time_ms ≈ 0.
        monitor.register_check("dummy", lambda: HealthCheckResult(
            component="dummy", status=HealthStatus.HEALTHY, message="ok",
        ))
        # First call -> start, second -> end ⇒ duration = 0.5 s ⇒ 500 ms.
        with patch("health_monitor.time.monotonic", side_effect=[100.0, 100.5]):
            result = monitor.run_check("dummy")
        self.assertEqual(result.response_time_ms, 500.0)

    def test_uptime_uses_monotonic(self):
        from unittest.mock import patch
        # get_liveness() reads uptime; if both startup_time and uptime use
        # monotonic, patching monotonic gives a deterministic uptime
        # regardless of wall-clock state.
        with patch("health_monitor.time.monotonic", side_effect=[1000.0, 1042.0]):
            monitor = HealthMonitor()  # consumes 1000.0 for startup
            liveness = monitor.get_liveness()  # consumes 1042.0 for uptime
        self.assertAlmostEqual(liveness["uptime_seconds"], 42.0, places=1)


class TestGetHealthMonitorSingletonRaceSafe(unittest.TestCase):
    """get_health_monitor() must return exactly ONE instance across threads.

    Without double-checked locking, two threads both seeing _health_monitor
    is None each construct an instance — one of which is then discarded.
    For HealthMonitor that's tolerable (just wasted checks); for siblings
    like get_enhanced_performance_monitor() the discarded instance leaks a
    daemon thread. We use HealthMonitor here as the easiest singleton to
    reset between tests.
    """

    def setUp(self):
        import health_monitor as hm
        # Snapshot and reset the singleton so concurrent first-callers race.
        self._saved = hm._health_monitor
        hm._health_monitor = None

    def tearDown(self):
        import health_monitor as hm
        hm._health_monitor = self._saved

    def test_concurrent_first_call_returns_single_instance(self):
        import health_monitor as hm
        import threading

        results = []
        barrier = threading.Barrier(8)

        def worker():
            barrier.wait()  # release all threads simultaneously
            results.append(hm.get_health_monitor())

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 8)
        first = results[0]
        for r in results[1:]:
            self.assertIs(r, first,
                "All threads must see the same singleton instance")


class TestBackupPathResolution(unittest.TestCase):
    """Regression: the file_permissions check hardcoded a 'backups' directory
    that nothing in the project actually creates.

    main/config.py's BackupConfig.path defaults to 'data/backups' (env
    BACKUP_PATH), so on a correctly configured checkout the hardcoded
    'backups' never existed and _check_file_permissions reported UNHEALTHY
    unconditionally -- which propagated to run_all_checks() and made
    GET /health always answer "unhealthy". A health endpoint that is always
    unhealthy carries no signal, so this is a real defect, not cosmetics.
    """

    def setUp(self):
        self._saved_env = os.environ.get("BACKUP_PATH")

    def tearDown(self):
        if self._saved_env is None:
            os.environ.pop("BACKUP_PATH", None)
        else:
            os.environ["BACKUP_PATH"] = self._saved_env

    def test_default_backup_path_matches_config_default(self):
        os.environ.pop("BACKUP_PATH", None)
        monitor = HealthMonitor()
        self.assertEqual(monitor._backup_path(), "data/backups")

    def test_env_var_overrides_default(self):
        os.environ["BACKUP_PATH"] = "custom/bk"
        monitor = HealthMonitor()
        self.assertEqual(monitor._backup_path(), "custom/bk")

    def test_explicit_config_wins_over_env(self):
        os.environ["BACKUP_PATH"] = "from/env"
        monitor = HealthMonitor(config={"backup_dir": "from/config"})
        self.assertEqual(monitor._backup_path(), "from/config")

    def test_file_permissions_healthy_when_configured_dirs_exist(self):
        """With every configured directory present the check must pass.

        Before the fix this asserted-healthy case failed because the check
        looked for 'backups' rather than the configured backup directory.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for sub in ("config", "logs", "data", "data/backups"):
                (root / sub).mkdir(parents=True, exist_ok=True)

            cwd = os.getcwd()
            os.chdir(root)
            try:
                os.environ.pop("BACKUP_PATH", None)
                monitor = HealthMonitor()
                result = monitor._check_file_permissions()
            finally:
                os.chdir(cwd)

        self.assertEqual(
            result.status, HealthStatus.HEALTHY,
            f"expected HEALTHY, got {result.status} ({result.message})"
        )
        self.assertIn("data/backups", result.details["checked_paths"])

    def test_file_permissions_still_flags_a_genuinely_missing_dir(self):
        """The fix must not defang the check: a real absence is still UNHEALTHY."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for sub in ("config", "logs", "data"):  # data/backups deliberately absent
                (root / sub).mkdir(parents=True, exist_ok=True)

            cwd = os.getcwd()
            os.chdir(root)
            try:
                os.environ.pop("BACKUP_PATH", None)
                monitor = HealthMonitor()
                result = monitor._check_file_permissions()
            finally:
                os.chdir(cwd)

        self.assertEqual(result.status, HealthStatus.UNHEALTHY)
        self.assertIn("data/backups", result.message)


class TestDisasterRecoveryBackupDirAgreement(unittest.TestCase):
    """The recovery manager and the health check must resolve the SAME dir.

    They disagreed before ('backups' vs config's 'data/backups'), so the
    manager created one directory while the health check demanded another.
    """

    def test_manager_default_matches_health_monitor_default(self):
        saved = os.environ.get("BACKUP_PATH")
        os.environ.pop("BACKUP_PATH", None)
        try:
            from disaster_recovery import DisasterRecoveryManager

            with tempfile.TemporaryDirectory() as td:
                cwd = os.getcwd()
                os.chdir(td)
                try:
                    manager = DisasterRecoveryManager()
                    monitor = HealthMonitor()
                    self.assertEqual(
                        str(manager.backup_dir).replace("\\", "/"),
                        monitor._backup_path(),
                    )
                    self.assertTrue(
                        manager.backup_dir.exists(),
                        "manager should create the backup dir it advertises",
                    )
                finally:
                    os.chdir(cwd)
        finally:
            if saved is not None:
                os.environ["BACKUP_PATH"] = saved


if __name__ == "__main__":
    unittest.main(verbosity=2)
