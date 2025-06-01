if __name__ == "__main__":
    import tkinter as tk
    from tkinter import ttk, messagebox
    import subprocess
    import sys
    import os
    import json
    import locale
    import webbrowser

    # 多言語ロード
    def get_lang():
        lang = locale.getdefaultlocale()[0]
        if lang and lang.startswith('ja'):
            return 'ja'
        return 'en'

    def load_locale():
        lang = get_lang()
        locfile = os.path.join(os.path.dirname(__file__), '../locales/ja.json' if lang=='ja' else '../locales/en.json')
        try:
            with open(locfile, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    L = load_locale()
    def _(key, default=''):
        return L.get(key, default)

    def launch_avatar_editor():
        if not os.path.exists('avatar_preset_linker_gui.py'):
            messagebox.showerror(_("error", "エラー"), "avatar_preset_linker_gui.py not found" if get_lang()=='en' else "avatar_preset_linker_gui.py が見つかりません")
            return
        try:
            subprocess.Popen([sys.executable, 'avatar_preset_linker_gui.py'])
        except Exception as e:
            messagebox.showerror(_("error", "エラー"), str(e))

    def open_config():
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../config/config.json'))
        try:
            if sys.platform.startswith('win'):
                os.startfile(config_path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', config_path])
            else:
                subprocess.Popen(['xdg-open', config_path])
        except Exception as e:
            messagebox.showerror(_("error", "エラー"), str(e))

    root = tk.Tk()
    root.title(_("title", "Cocoa MVP Launcher"))
    ttk.Label(root, text=_('desc', 'Cocoa - Avatar Editor (MVP)'), font=("Arial", 14)).pack(pady=10)
    ttk.Button(root, text=_('avatar_edit', 'Launch Avatar Editor'), command=launch_avatar_editor, width=30).pack(pady=10)
    ttk.Button(root, text=_('config_edit', 'Edit Config File'), command=open_config, width=30).pack(pady=10)
    ttk.Label(root, text="Powered by Cocoa (MVP)", font=("Arial", 10)).pack(side="bottom", pady=10)
    root.mainloop()
