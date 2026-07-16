"""Repo-wide guard: every singleton getter must use double-checked locking.

Pattern: a function get_X() that uses 'global _X' and an 'if _X is None'
check is a singleton init. Without a lock, two simultaneous callers can
both see `_X is None`, both construct an instance, and both side effects
(opening connections, starting daemon threads, registering handlers) run
twice. The classic fix is double-checked locking:

    def get_X():
        global _X
        if _X is None:           # fast path, no lock
            with _X_lock:        # serialize
                if _X is None:   # second check — someone else may have created it
                    _X = X()
        return _X

(For 'async def' getters, use asyncio.Lock + 'async with'.)

This guard finds every get_X function with the singleton shape and fails
if the construction site is not wrapped in a With/AsyncWith block that
contains its own None check. Backed by a Qiita/Zenn classic database of
threading bugs.
"""
import ast
import pathlib
import unittest


def _is_none_check_for(test: ast.expr, name: str) -> bool:
    """True if `test` is `<name> is None`."""
    if not isinstance(test, ast.Compare):
        return False
    if not (len(test.ops) == 1 and isinstance(test.ops[0], ast.Is)):
        return False
    if not (isinstance(test.left, ast.Name) and test.left.id == name):
        return False
    return (isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value is None)


def _has_inner_check_in_with(func: ast.AST, name: str) -> bool:
    """True if any With/AsyncWith inside `func` contains `if <name> is None`."""
    for node in ast.walk(func):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for inner in ast.walk(node):
                if isinstance(inner, ast.If) and _is_none_check_for(inner.test, name):
                    return True
    return False


class TestSingletonGettersUseDoubleCheckedLocking(unittest.TestCase):

    def test_every_get_X_uses_dcl(self):
        root = pathlib.Path("main")
        offenders = []
        for py in root.rglob("*.py"):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            for func in ast.walk(tree):
                if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not func.name.startswith("get_"):
                    continue
                globals_set = set()
                for c in ast.walk(func):
                    if isinstance(c, ast.Global):
                        globals_set.update(c.names)
                if not globals_set:
                    continue
                # Find outer None-check for each global; verify there is also
                # an inner check inside a With/AsyncWith block.
                for name in globals_set:
                    has_outer = any(
                        isinstance(s, ast.If) and _is_none_check_for(s.test, name)
                        for s in ast.walk(func)
                    )
                    if not has_outer:
                        continue
                    if not _has_inner_check_in_with(func, name):
                        rel = py.relative_to(root)
                        offenders.append(
                            f"{rel}:{func.lineno}: {func.name}() — singleton "
                            f"init for `{name}` lacks double-checked locking "
                            f"(wrap inside `with <lock>:` / `async with <lock>:` "
                            f"and re-check `if {name} is None:` there)"
                        )
        self.assertEqual(
            offenders,
            [],
            "Singleton getters must use double-checked locking:\n  "
            + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
