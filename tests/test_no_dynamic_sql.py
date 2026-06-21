"""Repo-wide guard: no SQL string in execute() may be dynamically built.

The single most important rule for SQLite safety is to pass values via `?`
placeholders, never to interpolate them into the SQL text. f-strings,
str.format(), %-formatting, and + concatenation all reopen the door to SQL
injection — the canonical Qiita/Zenn database security trap.

The codebase currently uses placeholders everywhere. This test parses every
.py under main/, finds every .execute()/.executemany()/.executescript() call,
and fails if the SQL argument (first positional arg) is constructed with any
of those dynamic-string mechanisms. It converts "currently clean" into
"provably stays clean".

A constant string with NO interpolation (plain str or an f-string with no
{placeholders}) is allowed — those cannot carry user data into the SQL.
"""
import ast
import pathlib
import unittest


def _dynamic_sql_reason(node: ast.AST):
    """Return a human reason if `node` is a dynamically-built string, else None."""
    if isinstance(node, ast.JoinedStr):  # f-string
        if any(isinstance(v, ast.FormattedValue) for v in node.values):
            return "f-string interpolation"
        return None  # f-string with no placeholders — effectively constant
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Mod):
            return "%-formatting"
        if isinstance(node.op, ast.Add):
            return "+ string concatenation"
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "format":
            return ".format()"
    return None


class TestNoDynamicSqlInExecute(unittest.TestCase):

    def test_no_interpolated_sql_in_execute_calls(self):
        root = pathlib.Path("main")
        offenders = []
        for py in root.rglob("*.py"):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                f = node.func
                if not (isinstance(f, ast.Attribute)
                        and f.attr in ("execute", "executemany", "executescript")):
                    continue
                if not node.args:
                    continue
                reason = _dynamic_sql_reason(node.args[0])
                if reason:
                    rel = py.relative_to(root)
                    offenders.append(f"{rel}:{node.lineno} ({reason})")
        self.assertEqual(
            offenders,
            [],
            "SQL passed to execute() must use ? placeholders, never a "
            "dynamically-built string. Offenders:\n  " + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
