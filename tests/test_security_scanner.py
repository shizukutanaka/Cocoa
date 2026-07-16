"""Acceptance tests for scripts/security_scanner.py.

Spec: docs/SPEC_SECURITY_SCANNER.md (REQ-SS-01..04)
Runnable without pytest:  python3 -m unittest tests.test_security_scanner -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from security_scanner import SecurityScanner


class TestParseVersion(unittest.TestCase):
    def test_three_part(self):
        self.assertEqual(SecurityScanner._parse_version("2.3.0"), (2, 3, 0))

    def test_two_part(self):
        self.assertEqual(SecurityScanner._parse_version("1.4"), (1, 4))

    def test_single_part(self):
        self.assertEqual(SecurityScanner._parse_version("41"), (41,))

    def test_strips_non_numeric_suffix(self):
        self.assertEqual(SecurityScanner._parse_version("2.3.0rc1"), (2, 3, 0))

    def test_pre_release_suffix(self):
        self.assertEqual(SecurityScanner._parse_version("1.0.0b2"), (1, 0, 0))

    def test_empty_string(self):
        self.assertEqual(SecurityScanner._parse_version(""), ())

    def test_non_numeric(self):
        self.assertEqual(SecurityScanner._parse_version("abc"), ())

    def test_ordering(self):
        self.assertLess(
            SecurityScanner._parse_version("2.2.9"),
            SecurityScanner._parse_version("2.3.0"),
        )


class TestIsVersionVulnerable(unittest.TestCase):
    def test_below_threshold_is_vulnerable(self):
        self.assertTrue(SecurityScanner._is_version_vulnerable("2.2.0", "<2.3.0"))

    def test_equal_threshold_is_safe(self):
        self.assertFalse(SecurityScanner._is_version_vulnerable("2.3.0", "<2.3.0"))

    def test_above_threshold_is_safe(self):
        self.assertFalse(SecurityScanner._is_version_vulnerable("2.4.0", "<2.3.0"))

    def test_patch_below_is_vulnerable(self):
        self.assertTrue(SecurityScanner._is_version_vulnerable("2.2.9", "<2.3.0"))

    def test_major_below_is_vulnerable(self):
        self.assertTrue(SecurityScanner._is_version_vulnerable("40.0.0", "<41.0.0"))

    def test_non_lt_constraint_is_not_vulnerable(self):
        # Only "<X" constraints are supported; anything else => not flagged
        self.assertFalse(SecurityScanner._is_version_vulnerable("1.0.0", ">=2.0.0"))

    def test_unparseable_installed_is_not_vulnerable(self):
        self.assertFalse(SecurityScanner._is_version_vulnerable("latest", "<2.3.0"))

    def test_unparseable_constraint_is_not_vulnerable(self):
        self.assertFalse(SecurityScanner._is_version_vulnerable("2.0.0", "<"))


class TestScanAllTimestamp(unittest.TestCase):
    def test_timestamp_is_utc(self):
        with tempfile.TemporaryDirectory() as td:
            scanner = SecurityScanner(base_dir=Path(td))
            results = scanner.scan_all()
            ts = results["timestamp"]
            self.assertTrue(ts.endswith("+00:00"), f"Non-UTC timestamp: {ts!r}")

    def test_scan_all_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            scanner = SecurityScanner(base_dir=Path(td))
            results = scanner.scan_all()
            self.assertIsInstance(results, dict)
            self.assertIn("checks", results)
            self.assertIn("summary", results)


class TestCheckDependencies(unittest.TestCase):
    def _scanner_with_requirements(self, td, lines):
        base = Path(td)
        (base / "requirements.txt").write_text("\n".join(lines), encoding="utf-8")
        return SecurityScanner(base_dir=base)

    def test_missing_requirements_returns_warning(self):
        with tempfile.TemporaryDirectory() as td:
            scanner = SecurityScanner(base_dir=Path(td))
            result = scanner.check_dependencies()
            self.assertEqual(result["status"], "warning")

    def test_vulnerable_pinned_package_detected(self):
        with tempfile.TemporaryDirectory() as td:
            scanner = self._scanner_with_requirements(td, ["Flask==2.2.0"])
            result = scanner.check_dependencies()
            self.assertEqual(result["status"], "fail")
            self.assertEqual(len(result["vulnerable_packages"]), 1)
            self.assertEqual(result["vulnerable_packages"][0]["package"], "Flask")

    def test_safe_pinned_package_not_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            scanner = self._scanner_with_requirements(td, ["Flask==2.3.0"])
            result = scanner.check_dependencies()
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["vulnerable_packages"], [])

    def test_newer_pinned_package_not_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            scanner = self._scanner_with_requirements(td, ["cryptography==42.0.1"])
            result = scanner.check_dependencies()
            self.assertEqual(result["status"], "pass")

    def test_old_cryptography_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            scanner = self._scanner_with_requirements(td, ["cryptography==40.0.0"])
            result = scanner.check_dependencies()
            self.assertEqual(result["status"], "fail")

    def test_multiple_packages_mixed(self):
        with tempfile.TemporaryDirectory() as td:
            scanner = self._scanner_with_requirements(td, [
                "Flask==2.2.0",        # vulnerable
                "Werkzeug==2.3.5",     # safe
                "SQLAlchemy==1.3.0",   # vulnerable
                "# a comment",
                "",
            ])
            result = scanner.check_dependencies()
            self.assertEqual(result["status"], "fail")
            flagged = {p["package"] for p in result["vulnerable_packages"]}
            self.assertEqual(flagged, {"Flask", "SQLAlchemy"})

    def test_unpinned_package_not_flagged_as_vulnerable(self):
        # No "==" pin => cannot determine version => not flagged as vulnerable
        with tempfile.TemporaryDirectory() as td:
            scanner = self._scanner_with_requirements(td, ["Flask>=2.0.0"])
            result = scanner.check_dependencies()
            self.assertEqual(result["vulnerable_packages"], [])
            self.assertEqual(result["status"], "pass")


class TestScannerConstruction(unittest.TestCase):
    def test_constructor_with_base_dir(self):
        with tempfile.TemporaryDirectory() as td:
            scanner = SecurityScanner(base_dir=Path(td))
            self.assertEqual(scanner.base_dir, Path(td))

    def test_lists_initialized_empty(self):
        with tempfile.TemporaryDirectory() as td:
            scanner = SecurityScanner(base_dir=Path(td))
            self.assertEqual(scanner.issues, [])
            self.assertEqual(scanner.warnings, [])
            self.assertEqual(scanner.info, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
