"""Repo-wide check that deprecated asyncio.get_event_loop() is not used.

asyncio.get_event_loop() is deprecated since Python 3.10: when called
outside a running event loop it implicitly creates a fresh one (with
DeprecationWarning) and is expected to be removed in a future release.
Inside an async function the correct replacement is
asyncio.get_running_loop() (or, for elapsed-time measurement,
time.monotonic()).

This test enforces the convention so regressions don't slip in. The
intentional fallback in redis_cache_manager.py (which uses
get_event_loop() from sync code to discover whether a loop is already
running) is exempted by name.
"""
import pathlib
import unittest


# Files that legitimately need asyncio.get_event_loop() — typically sync
# code paths that probe for an existing loop.
ALLOWED_FILES = {
    "redis_cache_manager.py",
}


class TestNoDeprecatedGetEventLoop(unittest.TestCase):

    def test_no_get_event_loop_in_main_modules(self):
        root = pathlib.Path("main")
        offenders = []
        for py in root.rglob("*.py"):
            if py.name in ALLOWED_FILES:
                continue
            text = py.read_text(encoding="utf-8", errors="ignore")
            for lineno, line in enumerate(text.splitlines(), 1):
                if "asyncio.get_event_loop()" in line:
                    offenders.append(f"{py.relative_to(root)}:{lineno}: {line.strip()}")
        self.assertEqual(
            offenders,
            [],
            "Use asyncio.get_running_loop() or time.monotonic() instead of "
            "the deprecated asyncio.get_event_loop().\nOffenders:\n  "
            + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
