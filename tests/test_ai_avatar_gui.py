"""Tests for main/ai_avatar_gui.py — structural / AST checks."""
import ast
import pathlib
import unittest


class TestBackgroundTasksRetained(unittest.TestCase):
    """asyncio.create_task() results in ai_avatar_gui.py must be stored.

    Bug: discarding the create_task() return value means the task has no
    strong reference; Python's event loop holds tasks in a WeakSet, so the
    task can be garbage-collected mid-execution, silently aborting init.
    Fix: self._background_tasks.append(asyncio.create_task(...))
    """

    _src = pathlib.Path("main/ai_avatar_gui.py").read_text()
    _tree = ast.parse(_src)

    def _count_bare_create_task_calls(self):
        """Return number of create_task() calls whose result is not stored."""
        bare = 0
        for node in ast.walk(self._tree):
            if not isinstance(node, ast.Expr):
                continue
            val = node.value
            if not isinstance(val, ast.Call):
                continue
            func = val.func
            called = (
                (isinstance(func, ast.Attribute) and func.attr == "create_task")
                or (isinstance(func, ast.Name) and func.id == "create_task")
            )
            if called:
                bare += 1
        return bare

    def test_no_bare_create_task_calls(self):
        self.assertEqual(
            self._count_bare_create_task_calls(),
            0,
            "All asyncio.create_task() results must be stored (no bare expression-statements)",
        )

    def test_background_tasks_list_initialised(self):
        """__init__ must set self._background_tasks = []."""
        found = False
        for node in ast.walk(self._tree):
            # Handle both plain assignment and annotated assignment (x: list = [])
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            for target in targets:
                if (
                    isinstance(target, ast.Attribute)
                    and target.attr == "_background_tasks"
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    found = True
        self.assertTrue(found, "AIAvatarGeneratorGUI.__init__ must initialise self._background_tasks")


if __name__ == "__main__":
    unittest.main()
