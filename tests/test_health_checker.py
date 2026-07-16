"""Acceptance tests for scripts/health_checker.py.

Spec: docs/SPEC_HEALTH_CHECKER.md (REQ-HC-01..02)
Runnable without pytest:  python3 -m unittest tests.test_health_checker -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from health_checker import CocoaHealthChecker


def _msgs(entries):
    return [e.get("message", "") for e in entries]


class TestConstruction(unittest.TestCase):
    def test_constructor_does_not_raise(self):
        with tempfile.TemporaryDirectory() as td:
            checker = CocoaHealthChecker(Path(td))
            self.assertIsNotNone(checker)

    def test_lists_initialized_empty(self):
        with tempfile.TemporaryDirectory() as td:
            checker = CocoaHealthChecker(Path(td))
            self.assertEqual(checker.issues, [])
            self.assertEqual(checker.warnings, [])
            self.assertEqual(checker.passed_checks, [])


class TestCheckProjectStructure(unittest.TestCase):
    def test_missing_dirs_recorded_as_issues(self):
        with tempfile.TemporaryDirectory() as td:
            checker = CocoaHealthChecker(Path(td))
            checker._check_project_structure()
            # All required dirs/files absent => issues recorded
            self.assertTrue(len(checker.issues) > 0)
            self.assertEqual(checker.passed_checks, [])

    def test_present_dirs_recorded_as_passed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for d in ("main", "docs", "tests", "config", "locales", "scripts"):
                (root / d).mkdir()
            (root / "README.md").write_text("# readme")
            (root / "requirements.txt").write_text("")
            checker = CocoaHealthChecker(root)
            checker._check_project_structure()
            self.assertEqual(checker.issues, [])
            self.assertEqual(len(checker.passed_checks), 8)  # 6 dirs + 2 files


class TestCheckLanguageFiles(unittest.TestCase):
    """REQ-HC-01: 2-letter xx.json files in main/ must be detected."""

    def _setup(self, td, main_files=(), locales_count=0):
        root = Path(td)
        (root / "main").mkdir()
        (root / "locales").mkdir()
        for name in main_files:
            (root / "main" / name).write_text("{}")
        for i in range(locales_count):
            (root / "locales" / f"l{i}.json").write_text("{}")
        return root

    def test_detects_two_letter_lang_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._setup(td, main_files=("ja.json", "en.json"), locales_count=2)
            checker = CocoaHealthChecker(root)
            checker._check_language_files()
            main_warnings = [w for w in checker.warnings if "main" in w.get("message", "")]
            self.assertEqual(len(main_warnings), 1)
            self.assertEqual(len(main_warnings[0]["files"]), 2)

    def test_single_letter_json_not_treated_as_lang(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._setup(td, main_files=("x.json",), locales_count=2)
            checker = CocoaHealthChecker(root)
            checker._check_language_files()
            main_warnings = [w for w in checker.warnings if "main" in w.get("message", "")]
            self.assertEqual(main_warnings, [])

    def test_no_main_lang_files_no_warning(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._setup(td, main_files=("data_config.json",), locales_count=2)
            checker = CocoaHealthChecker(root)
            checker._check_language_files()
            main_warnings = [w for w in checker.warnings if "main" in w.get("message", "")]
            self.assertEqual(main_warnings, [])

    def test_sufficient_locales_recorded_as_passed(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._setup(td, locales_count=3)
            checker = CocoaHealthChecker(root)
            checker._check_language_files()
            self.assertTrue(any("言語ファイル" in c for c in checker.passed_checks))

    def test_too_few_locales_warns(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._setup(td, locales_count=1)
            checker = CocoaHealthChecker(root)
            checker._check_language_files()
            low_warnings = [w for w in checker.warnings if w.get("severity") == "low"]
            self.assertTrue(len(low_warnings) >= 1)

    def test_missing_locales_dir_is_issue(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "main").mkdir()
            checker = CocoaHealthChecker(root)
            checker._check_language_files()
            self.assertTrue(len(checker.issues) >= 1)


class TestCheckDocumentation(unittest.TestCase):
    def test_missing_readme_is_issue(self):
        with tempfile.TemporaryDirectory() as td:
            checker = CocoaHealthChecker(Path(td))
            checker._check_documentation()
            self.assertTrue(any("README" in i["message"] for i in checker.issues))

    def test_present_readme_is_passed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("# x")
            checker = CocoaHealthChecker(root)
            checker._check_documentation()
            self.assertTrue(any("README" in c for c in checker.passed_checks))


class TestCheckDependencies(unittest.TestCase):
    def test_missing_requirements_warns(self):
        with tempfile.TemporaryDirectory() as td:
            checker = CocoaHealthChecker(Path(td))
            checker._check_dependencies()
            self.assertTrue(any("requirements.txt" in w["message"] for w in checker.warnings))

    def test_present_requirements_passed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "requirements.txt").write_text("flask\nrequests\n")
            checker = CocoaHealthChecker(root)
            checker._check_dependencies()
            self.assertTrue(any("requirements.txt" in c for c in checker.passed_checks))


class TestNoBareExcept(unittest.TestCase):
    """REQ-HC-02: source must not contain bare except:."""

    def test_no_bare_except_in_source(self):
        src = (PROJECT_ROOT / "scripts" / "health_checker.py").read_text(encoding="utf-8")
        # A bare except is "except:" with no exception type before the colon.
        import re
        bare = re.findall(r"\bexcept\s*:", src)
        self.assertEqual(bare, [], "Found bare except: in health_checker.py")


if __name__ == "__main__":
    unittest.main(verbosity=2)
