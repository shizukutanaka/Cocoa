"""Repo-wide guard: every outbound HTTP call must pass timeout=.

requests.get/post/... and urllib's urlopen default to NO timeout, so a slow
or hung peer makes the call block forever — the calling thread (or the whole
process, for a sync call on the event-loop thread) wedges with no recovery.
This is one of the most-cited production traps on Qiita/Zenn.

Cocoa makes external calls to Stripe, VRChat, Grafana, and translation APIs;
a single missing timeout there is a denial-of-service waiting to happen. This
test parses every .py under main/, finds every `requests.<verb>(...)` and
`urlopen(...)` call, and fails if any omits timeout=.

It deliberately matches only `requests.<verb>` (module attribute) and
urlopen — NOT arbitrary `.get()` like a dict's `self._requests.get(id)`,
which is unrelated to HTTP.
"""
import ast
import pathlib
import unittest

_HTTP_VERBS = {"get", "post", "put", "delete", "patch", "head", "options", "request"}


class TestOutboundHttpCallsHaveTimeout(unittest.TestCase):

    def test_every_requests_and_urlopen_call_sets_timeout(self):
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
                is_http = False
                # requests.<verb>(...) — module attribute, not dict.get()
                if (isinstance(f, ast.Attribute) and f.attr in _HTTP_VERBS
                        and isinstance(f.value, ast.Name) and f.value.id == "requests"):
                    is_http = True
                # urlopen(...) / urllib.request.urlopen(...)
                if isinstance(f, ast.Name) and f.id == "urlopen":
                    is_http = True
                if isinstance(f, ast.Attribute) and f.attr == "urlopen":
                    is_http = True
                if not is_http:
                    continue
                if not any(kw.arg == "timeout" for kw in node.keywords):
                    rel = py.relative_to(root)
                    offenders.append(f"{rel}:{node.lineno} ({ast.unparse(f)})")
        self.assertEqual(
            offenders,
            [],
            "Every requests.<verb>()/urlopen() call must pass timeout= to "
            "avoid blocking forever on a hung peer. Offenders:\n  "
            + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
