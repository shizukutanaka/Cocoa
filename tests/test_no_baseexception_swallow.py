"""Repo-wide guard: no handler may silently swallow KeyboardInterrupt / SystemExit.

`except BaseException:` and bare `except:` catch KeyboardInterrupt and
SystemExit (which subclass BaseException, not Exception). Swallowing them means
Ctrl+C can't stop the process and sys.exit() can be silently defeated — the
classic Qiita/Zenn "too-broad except" pitfall.

Some import guards legitimately need BaseException: a broken native binding
(e.g. cryptography / bcrypt PyO3 bindings) can raise pyo3 PanicException, which
is NOT an Exception, so `except Exception` would let the whole import crash.
The correct pattern, per the same best-practice articles, is to re-raise the
interrupt signals explicitly:

    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:
        FLAG = False

This test therefore operates at the `try` level: a non-re-raising
BaseException/bare handler is an offense UNLESS the same try statement has a
handler that catches KeyboardInterrupt/SystemExit (or BaseException) and
re-raises, or the offending handler itself re-raises.
"""
import ast
import pathlib
import unittest


def _handler_reraises(handler: ast.ExceptHandler) -> bool:
    return any(isinstance(n, ast.Raise) for n in ast.walk(handler))


def _catches_interrupts(handler: ast.ExceptHandler) -> bool:
    t = handler.type
    names = []
    if isinstance(t, ast.Name):
        names = [t.id]
    elif isinstance(t, ast.Tuple):
        names = [e.id for e in t.elts if isinstance(e, ast.Name)]
    return any(n in ("KeyboardInterrupt", "SystemExit", "BaseException") for n in names)


def _is_base_or_bare(handler: ast.ExceptHandler) -> bool:
    t = handler.type
    if t is None:
        return True
    if isinstance(t, ast.Name) and t.id == "BaseException":
        return True
    if isinstance(t, ast.Tuple):
        return any(isinstance(e, ast.Name) and e.id == "BaseException" for e in t.elts)
    return False


class TestNoBaseExceptionSwallowing(unittest.TestCase):

    def test_no_try_swallows_interrupt_signals(self):
        root = pathlib.Path("main")
        offenders = []
        for py in root.rglob("*.py"):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Try):
                    continue
                # Does any sibling handler re-raise the interrupt signals?
                guarded = any(
                    _catches_interrupts(h) and _handler_reraises(h)
                    for h in node.handlers
                )
                for h in node.handlers:
                    if _is_base_or_bare(h) and not _handler_reraises(h) and not guarded:
                        rel = py.relative_to(root)
                        label = "bare except" if h.type is None else "BaseException"
                        offenders.append(f"{rel}:{h.lineno} ({label})")
        self.assertEqual(
            offenders,
            [],
            "A try must not swallow KeyboardInterrupt/SystemExit. Use "
            "`except Exception:`, re-raise, or add an `except "
            "(KeyboardInterrupt, SystemExit): raise` guard before the broad "
            "handler. Offenders:\n  " + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
