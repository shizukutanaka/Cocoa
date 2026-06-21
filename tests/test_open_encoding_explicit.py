"""Repo-wide guard: every text-mode open() under main/ must specify encoding=.

Without encoding=, open() falls back to the platform's locale encoding —
cp932 on Japanese Windows, mac-roman in some macOS setups — instead of
UTF-8. A UTF-8 JSON config with Japanese characters then raises
UnicodeDecodeError on load, which is one of the most-cited cross-platform
Python traps on Qiita / Zenn.

This test parses every .py under main/, finds top-level open() calls in
text mode (no 'b' in mode string), and fails if any one of them omits
encoding=. Binary mode is exempt — encoding is irrelevant there.

NOTE: Methods like Path.open() / Image.open() / tarfile.open() are NOT
covered: only the bare builtin open(). The bare builtin is what hits the
locale default; Path.open() also defaults to locale but is much rarer
here. The set of "true open() calls" is what this guard protects.
"""
import ast
import pathlib
import unittest


class TestOpenEncodingExplicit(unittest.TestCase):

    def test_every_text_mode_open_specifies_encoding(self):
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
                if not (isinstance(f, ast.Name) and f.id == "open"):
                    continue
                # Detect binary mode → encoding is irrelevant.
                mode = None
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    mode = node.args[1].value
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = kw.value.value
                if isinstance(mode, str) and "b" in mode:
                    continue
                has_enc = any(kw.arg == "encoding" for kw in node.keywords)
                if not has_enc:
                    rel = py.relative_to(root)
                    offenders.append(f"{rel}:{node.lineno}")
        self.assertEqual(
            offenders,
            [],
            "Every text-mode open() under main/ must pass encoding= "
            "(usually 'utf-8'). Offenders:\n  " + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
