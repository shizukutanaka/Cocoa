import os
import importlib.util
import traceback
from types import ModuleType
from typing import List, Any

PLUGINS_DIR = "plugins"

def load_plugins(plugins_dir: str = PLUGINS_DIR) -> List[ModuleType]:
    """
    指定ディレクトリからプラグインを動的ロード
    :param plugins_dir: プラグインディレクトリのパス
    :return: 読み込まれたプラグインモジュールのリスト
    """
    plugins = []
    if not os.path.isdir(plugins_dir):
        print(f"[WARN] プラグインディレクトリが存在しません: {plugins_dir}")
        return plugins
    for fname in os.listdir(plugins_dir):
        if fname.endswith(".py"):
            path = os.path.join(plugins_dir, fname)
            spec = importlib.util.spec_from_file_location(fname[:-3], path)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                plugins.append(mod)
            except Exception as e:
                print(f"[WARN] プラグイン {fname} の読み込み失敗: {e}")
                traceback.print_exc()
    return plugins

def run_hook(plugins: List[ModuleType], hook_name: str, *args: Any, **kwargs: Any) -> None:
    """
    プラグインの特定フックを順次呼び出す
    :param plugins: プラグインモジュールのリスト
    :param hook_name: 呼び出す関数名
    :param args: フック関数への引数
    :param kwargs: フック関数へのキーワード引数
    """
    for plugin in plugins:
        if hasattr(plugin, hook_name):
            try:
                getattr(plugin, hook_name)(*args, **kwargs)
            except Exception as e:
                print(f"[WARN] プラグインhook {hook_name} 失敗: {e}")
                traceback.print_exc()

if __name__ == "__main__":
    plugins = load_plugins()
    run_hook(plugins, "on_startup")
