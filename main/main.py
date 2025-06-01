if __name__ == "__main__":
    import tkinter as tk
    from tkinter import ttk, messagebox
    import subprocess
    import sys
    import os

    def launch_avatar_editor():
        # avatar_preset_linker_gui.py が存在する場合のみ起動
        if not os.path.exists('avatar_preset_linker_gui.py'):
            messagebox.showerror("エラー", "avatar_preset_linker_gui.py が見つかりません")
            return
        try:
            subprocess.Popen([sys.executable, 'avatar_preset_linker_gui.py'])
        except Exception as e:
            messagebox.showerror("エラー", f"アバター編集モードの起動に失敗しました\n{e}")

    root = tk.Tk()
    root.title("Cocoa MVP ランチャー")
    ttk.Label(root, text="Cocoa - アバター編集 (MVP)", font=("Arial", 14)).pack(pady=10)
    ttk.Button(root, text="アバター編集を起動", command=launch_avatar_editor, width=30).pack(pady=20)
    ttk.Label(root, text="Powered by Cocoa (MVP)", font=("Arial", 10)).pack(side="bottom", pady=10)
    root.mainloop()
