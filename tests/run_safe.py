#!/usr/bin/env python3
"""Run the dependency-light Cocoa test subset.

These test modules import only the standard library plus pure Cocoa modules,
so they run in minimal environments where the full pytest suite cannot —
e.g. when pytest is not installed, or when the cryptography native binding,
torch, flask, etc. are unavailable.

    python3 tests/run_safe.py            # run all safe tests
    python3 tests/run_safe.py -v         # verbose

Exit code is 0 on success, 1 on any failure (CI-friendly).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Test modules that are safe to run without heavy/native dependencies.
SAFE_MODULES = [
    "tests.test_repairs",
    "tests.test_validation",
    "tests.test_preset_diff",
    "tests.test_vrchat_budget",
    "tests.test_preset_schema",
    "tests.test_template_filters",
    "tests.test_preset_history",
    "tests.test_preset_history_diff",
    "tests.test_batch_validator",
    "tests.test_i18n",
    "tests.test_avatar_parameters",
]


def build_suite() -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in SAFE_MODULES:
        suite.addTests(loader.loadTestsFromName(name))
    return suite


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    verbosity = 2 if ("-v" in argv or "--verbose" in argv) else 1
    result = unittest.TextTestRunner(verbosity=verbosity).run(build_suite())
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
