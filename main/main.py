if __name__ == "__main__":
    import tkinter as tk
    from tkinter import ttk, messagebox
    import subprocess
    import sys

    # --- モードランチャーUI ---
    def launch_avatar_editor():
        # サブプロセスでアバター編集モードGUIを起動
        try:
            subprocess.Popen([sys.executable, 'avatar_preset_linker_gui.py'])
        except Exception as e:
            messagebox.showerror("Error", f"アバター編集モードの起動に失敗しました\n{e}")

    def launch_streaming_mode():
        # サブプロセスで配信（コメント読み）モードGUIを起動
        try:
            subprocess.Popen([sys.executable, 'comment_manager_gui.py'])
        except Exception as e:
            messagebox.showerror("Error", f"配信モードの起動に失敗しました\n{e}")

    root = tk.Tk()
    root.title("Satin/Cocoa レガシーランチャー")
    ttk.Label(root, text="【重要】このランチャーは今後廃止予定です。\nアバター編集は Cocoa、配信は Satin を直接起動してください。", font=("Arial", 12), foreground="red").pack(pady=8)
    ttk.Label(root, text="モードを選択してください", font=("Arial", 16)).pack(pady=8)
    ttk.Button(root, text="Cocoa (アバター編集ソフト)", command=launch_avatar_editor, width=30).pack(pady=6)
    ttk.Button(root, text="Satin (配信ソフト)", command=launch_streaming_mode, width=30).pack(pady=6)
    ttk.Label(root, text="\nSatin/Cocoa - VRChatアバター編集・配信分離ランチャー", font=("Arial", 10)).pack(side="bottom", pady=10)
    root.mainloop()
