#!/usr/bin/env python3
"""
Cocoa Main Launcher
アバター管理システムのメインランチャー
"""
import os
import sys
from pathlib import Path

try:
    from tkinter import messagebox
except ImportError:  # tkinter が無いヘッドレス環境向けフォールバック
    messagebox = None

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class CocoaLauncher:
    """Cocoaアプリケーションランチャー"""

    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.main_dir = self.project_root / 'main'

    def launch_avatar_editor(self):
        """アバターエディタを起動"""
        editor_path = self.main_dir / 'avatar_preset_linker_gui.py'
        if not editor_path.exists():
            raise FileNotFoundError(f"Avatar editor not found: {editor_path}")

        # subprocessで起動（クロスプラットフォーム対応）
        import subprocess
        try:
            subprocess.Popen([
                sys.executable,
                str(editor_path)
            ], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            raise RuntimeError(f"Failed to launch avatar editor: {e}") from e

    def open_config_file(self):
        """設定ファイルをOSデフォルトエディタで開く"""
        config_path = self.project_root / 'config' / 'config.json'
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        import subprocess
        try:
            if sys.platform.startswith('win'):
                os.startfile(str(config_path))
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(config_path)])
            else:
                subprocess.Popen(['xdg-open', str(config_path)])
        except Exception as e:
            raise RuntimeError(f"Failed to open config file: {e}") from e

    def validate_config(self):
        """設定ファイルを検証"""
        try:
            from config_validator import ConfigValidator
        except ImportError as e:
            raise ImportError("ConfigValidator module not found") from e

        config_path = self.project_root / 'config' / 'config.json'
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        validator = ConfigValidator()
        return validator.validate(str(config_path))

    def run(self):
        """メインGUIを実行"""
        try:
            import tkinter as tk
            from tkinter import ttk
        except ImportError:
            print("Error: tkinter is required but not installed.")
            print("Please install tkinter: pip install tk")
            sys.exit(1)

        # 言語マネージャーの初期化を試行
        try:
            import asyncio as _asyncio
            from i18n_manager import get_i18n_manager
            i18n_manager = _asyncio.run(get_i18n_manager())
            _ = i18n_manager.translate
        except (ImportError, Exception):
            # フォールバック: シンプルな翻訳関数
            def _(key, default=''):
                return default if key.startswith(('error', 'config')) else key

        # GUI構築
        root = tk.Tk()
        root.title(_("title", "Cocoa Avatar Management System"))
        root.geometry("400x300")

        # メインコンテナ
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # タイトル
        title_label = ttk.Label(
            main_frame,
            text=_('app_name', 'Cocoa Avatar Management System'),
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 10))

        subtitle_label = ttk.Label(
            main_frame,
            text=_('app_description', 'Professional avatar preset management and optimization system'),
            font=("Arial", 10),
            wraplength=350
        )
        subtitle_label.pack(pady=(0, 20))

        # ボタンコンテナ
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 20))

        # アバターエディタ起動ボタン
        ttk.Button(
            button_frame,
            text=_('avatar_edit', 'Launch Avatar Editor'),
            command=self._launch_avatar_editor_handler,
            width=30
        ).pack(pady=5)

        # 設定ファイル編集ボタン
        ttk.Button(
            button_frame,
            text=_('config_edit', 'Edit Configuration'),
            command=self._open_config_handler,
            width=30
        ).pack(pady=5)

        # ヘルスチェック実行ボタン
        ttk.Button(
            button_frame,
            text=_('health_check', 'Run Health Check'),
            command=self._run_health_check_handler,
            width=30
        ).pack(pady=5)

        # APIサーバー起動ボタン
        ttk.Button(
            button_frame,
            text=_('api_server', 'Start API Server'),
            command=self._start_api_server_handler,
            width=30
        ).pack(pady=5)

        # Grafana監視起動ボタン
        ttk.Button(
            button_frame,
            text=_('grafana_monitoring', 'Start Grafana Monitoring'),
            command=self._start_grafana_monitoring_handler,
            width=30
        ).pack(pady=5)

        # 言語ファイル生成ボタン
        ttk.Button(
            button_frame,
            text=_('generate_languages', 'Generate Language Files'),
            command=self._generate_languages_handler,
            width=30
        ).pack(pady=5)

        # ステータスバー
        status_label = ttk.Label(
            main_frame,
            text="Ready",
            font=("Arial", 9),
            foreground="gray"
        )
        status_label.pack(side=tk.BOTTOM, pady=(10, 0))

        # バージョン情報
        version_label = ttk.Label(
            main_frame,
            text="Cocoa v2.0.0 - Production Ready",
            font=("Arial", 8),
            foreground="gray"
        )
        version_label.pack(side=tk.BOTTOM)

        # イベントハンドラーを設定
        self.root = root
        self.status_label = status_label
        self._ = _

        root.mainloop()

    def _launch_avatar_editor_handler(self):
        """アバターエディタ起動ハンドラ"""
        try:
            self.launch_avatar_editor()
            self._update_status("Avatar editor launched successfully", "green")
        except Exception as e:
            if messagebox is not None:
                messagebox.showerror(
                    self._("error", "Error"),
                    f"{self._('launch_failed', 'Failed to launch avatar editor')}:\n{str(e)}"
                )

    def _open_config_handler(self):
        """設定ファイルオープン・ハンドラ"""
        try:
            self.open_config_file()
            self._update_status("Configuration file opened", "green")
        except Exception as e:
            if messagebox is not None:
                messagebox.showerror(
                    self._("error", "Error"),
                    f"{self._('config_open_failed', 'Failed to open config file')}:\n{str(e)}"
                )

    def _run_health_check_handler(self):
        """ヘルスチェック実行ハンドラ"""
        try:
            from tkinter import messagebox

            from health_monitor import get_health_monitor

            # ヘルスチェック実行
            monitor = get_health_monitor()
            results = monitor.run_all_checks()

            # 結果を整形
            status = results.get("status", "unknown")
            checks = results.get("checks", {})

            # サマリーを作成
            summary_lines = [f"Overall Status: {status.upper()}"]
            summary_lines.append("")

            for check_name, check_result in checks.items():
                check_status = check_result.get("status", "unknown")
                check_message = check_result.get("message", "")
                summary_lines.append(f"{check_name}: {check_status.upper()}")
                if check_message:
                    summary_lines.append(f"  → {check_message}")

            summary = "\n".join(summary_lines)

            # ステータスに応じてメッセージボックスの種類を変更
            if status == "healthy":
                messagebox.showinfo(
                    self._("health_check_title", "Health Check Results"),
                    summary
                )
                self._update_status("Health check passed", "green")
            elif status == "degraded":
                messagebox.showwarning(
                    self._("health_check_title", "Health Check Results"),
                    summary
                )
                self._update_status("Health check shows degraded status", "orange")
            else:
                messagebox.showerror(
                    self._("health_check_title", "Health Check Results"),
                    summary
                )
                self._update_status("Health check failed", "red")

        except Exception as e:
            if messagebox is not None:
                messagebox.showerror(
                    self._("error", "Error"),
                    f"{self._('health_check_failed', 'Failed to run health check')}:\n{str(e)}"
                )
            self._update_status("Health check error", "red")

    def _start_api_server_handler(self):
        """APIサーバー起動ハンドラ"""
        try:
            import threading

            from api_server import start_api_server

            # 別スレッドでAPIサーバーを起動
            api_thread = threading.Thread(
                target=start_api_server,
                args=("127.0.0.1", 8000, False),
                daemon=True
            )
            api_thread.start()

            self._update_status("API server started on http://127.0.0.1:8000", "green")

            # ブラウザでAPIドキュメントを開く
            import webbrowser
            webbrowser.open("http://127.0.0.1:8000/docs")

        except Exception as e:
            if messagebox is not None:
                messagebox.showerror(
                    self._("error", "Error"),
                    f"{self._('api_start_failed', 'Failed to start API server')}:\n{str(e)}"
                )

    def _open_monitoring_handler(self):
        """監視ダッシュボードオープン・ハンドラ"""
        try:
            # ブラウザで監視ページを開く
            import webbrowser
            webbrowser.open("http://127.0.0.1:5173/monitoring")

            self._update_status("Monitoring dashboard opened", "green")
        except Exception as e:
            if messagebox is not None:
                messagebox.showerror(
                    self._("error", "Error"),
                    f"{self._('monitoring_open_failed', 'Failed to open monitoring dashboard')}:\n{str(e)}"
                )

    def _start_grafana_monitoring_handler(self):
        """Grafana監視起動ハンドラ"""
        try:
            from grafana_integration import setup_grafana_integration

            # Grafana統合をセットアップ
            success = setup_grafana_integration(
                grafana_url="http://localhost:3000",
                api_key=None  # 実際の環境では適切なAPIキーを設定
            )

            if success:
                self._update_status("Grafana monitoring started", "green")

                # ブラウザでGrafanaを開く
                import webbrowser
                webbrowser.open("http://localhost:3000/d/cocoa-system-monitoring")
            else:
                self._update_status("Failed to start Grafana monitoring", "red")

        except Exception as e:
            if messagebox is not None:
                messagebox.showerror(
                    self._("error", "Error"),
                    f"{self._('grafana_start_failed', 'Failed to start Grafana monitoring')}:\n{str(e)}"
                )

    def _generate_languages_handler(self):
        """言語ファイル生成ハンドラ"""
        try:
            from scripts.generate_languages_improved import main as generate_languages

            # 言語ファイル生成を実行
            success = generate_languages()

            if success:
                # 現在の言語ファイル数を確認
                from pathlib import Path
                locales_dir = Path("locales")
                json_files = list(locales_dir.glob("*.json"))
                count = len(json_files)

                message = f"言語ファイル生成完了。現在: {count}言語"
                self._update_status(message, "green")
                if messagebox is not None:
                    messagebox.showinfo("言語ファイル生成", message)
            else:
                self._update_status("言語ファイル生成に失敗", "red")

        except Exception as e:
            if messagebox is not None:
                messagebox.showerror(
                    self._("error", "Error"),
                    f"{self._('language_generation_failed', 'Failed to generate language files')}:\n{str(e)}"
                )

    def _update_status(self, message: str, color: str = "black"):
        """ステータスを更新"""
        if hasattr(self, 'status_label'):
            self.status_label.config(text=message, foreground=color)
            # 3秒後にデフォルトに戻す
            self.root.after(3000, lambda: self.status_label.config(text="Ready", foreground="gray"))


def main():
    """メインエントリーポイント"""
    launcher = CocoaLauncher()
    launcher.run()


if __name__ == "__main__":
    main()
