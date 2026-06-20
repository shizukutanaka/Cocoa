"""Tests for main/main.py — CocoaLauncher non-GUI methods."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "main"))

from main import CocoaLauncher


class TestCocoaLauncherInit(unittest.TestCase):

    def test_project_root_is_path(self):
        launcher = CocoaLauncher()
        self.assertIsInstance(launcher.project_root, Path)

    def test_main_dir_is_inside_project_root(self):
        launcher = CocoaLauncher()
        self.assertEqual(launcher.main_dir, launcher.project_root / "main")

    def test_main_dir_name_is_main(self):
        launcher = CocoaLauncher()
        self.assertEqual(launcher.main_dir.name, "main")


class TestLaunchAvatarEditor(unittest.TestCase):

    def _launcher(self):
        return CocoaLauncher()

    def test_raises_file_not_found_when_editor_missing(self):
        launcher = self._launcher()
        with patch.object(Path, "exists", return_value=False), \
             self.assertRaises(FileNotFoundError):
            launcher.launch_avatar_editor()

    def test_calls_popen_when_editor_exists(self):
        launcher = self._launcher()
        with patch.object(Path, "exists", return_value=True), \
             patch("subprocess.Popen") as mock_popen:
            launcher.launch_avatar_editor()
            mock_popen.assert_called_once()

    def test_popen_uses_current_python(self):
        launcher = self._launcher()
        with patch.object(Path, "exists", return_value=True), \
             patch("subprocess.Popen") as mock_popen:
            launcher.launch_avatar_editor()
            args = mock_popen.call_args[0][0]
            self.assertEqual(args[0], sys.executable)

    def test_popen_error_raises_runtime_error(self):
        launcher = self._launcher()
        with patch.object(Path, "exists", return_value=True), \
             patch("subprocess.Popen", side_effect=OSError("no process")), \
             self.assertRaises(RuntimeError):
            launcher.launch_avatar_editor()


class TestOpenConfigFile(unittest.TestCase):

    def _launcher(self):
        return CocoaLauncher()

    def test_raises_file_not_found_when_config_missing(self):
        launcher = self._launcher()
        with patch.object(Path, "exists", return_value=False), \
             self.assertRaises(FileNotFoundError):
            launcher.open_config_file()

    def test_calls_xdg_open_on_linux(self):
        launcher = self._launcher()
        with patch.object(Path, "exists", return_value=True), \
             patch("sys.platform", "linux"), \
             patch("subprocess.Popen") as mock_popen:
            launcher.open_config_file()
            args = mock_popen.call_args[0][0]
            self.assertEqual(args[0], "xdg-open")

    def test_calls_open_on_macos(self):
        launcher = self._launcher()
        with patch.object(Path, "exists", return_value=True), \
             patch("sys.platform", "darwin"), \
             patch("subprocess.Popen") as mock_popen:
            launcher.open_config_file()
            args = mock_popen.call_args[0][0]
            self.assertEqual(args[0], "open")

    def test_popen_error_raises_runtime_error(self):
        launcher = self._launcher()
        with patch.object(Path, "exists", return_value=True), \
             patch("sys.platform", "linux"), \
             patch("subprocess.Popen", side_effect=OSError("fail")), \
             self.assertRaises(RuntimeError):
            launcher.open_config_file()


class TestValidateConfig(unittest.TestCase):

    def _launcher(self):
        return CocoaLauncher()

    def test_raises_file_not_found_when_config_missing(self):
        launcher = self._launcher()
        with patch.object(Path, "exists", return_value=False), \
             self.assertRaises(FileNotFoundError):
            launcher.validate_config()

    def test_calls_config_validator_when_config_exists(self):
        launcher = self._launcher()
        mock_validator = MagicMock()
        mock_validator.validate.return_value = {"valid": True}
        with patch.object(Path, "exists", return_value=True), \
             patch("main.ConfigValidator", return_value=mock_validator, create=True), \
             patch.dict("sys.modules", {"config_validator": MagicMock(
                 ConfigValidator=MagicMock(return_value=mock_validator)
             )}):
            result = launcher.validate_config()
            self.assertIsNotNone(result)


class TestGetI18nManagerCalledWithAsyncioRun(unittest.TestCase):
    """main.run() must call asyncio.run(get_i18n_manager()) not get_i18n_manager().

    Bug: get_i18n_manager is async def. Calling it without await returns a coroutine
    object; accessing .translate on that raises AttributeError. The fix wraps the
    call with asyncio.run() so the caller gets the real I18NManager instance.
    """

    def test_run_uses_asyncio_run_for_i18n_manager(self):
        """Verify the run() method calls asyncio.run() with get_i18n_manager."""
        import ast
        import pathlib
        src = pathlib.Path('main/main.py').read_text()
        tree = ast.parse(src)

        calls_asyncio_run = False
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and
                    isinstance(node.func, ast.Attribute) and
                    node.func.attr == 'run' and
                    len(node.args) == 1):
                arg = node.args[0]
                if (isinstance(arg, ast.Call) and
                        isinstance(arg.func, ast.Name) and
                        arg.func.id == 'get_i18n_manager'):
                    calls_asyncio_run = True
                    break

        self.assertTrue(
            calls_asyncio_run,
            "main.py must call asyncio.run(get_i18n_manager()) not bare get_i18n_manager()"
        )


if __name__ == "__main__":
    unittest.main()
