import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json

LINKS_FILE = "avatar_preset_links.json"

class AvatarPresetLinkerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("アバターとプリセットの紐付け管理")
        self.avatar_path = tk.StringVar()
        self.preset_path = tk.StringVar()
        self.status = None
        self.links_list = None
        self.links = {}
        self.create_widgets()
        self.load_links()

    def create_widgets(self):
        # UI部品の生成（再生成時も対応）
        for widget in self.root.winfo_children():
            widget.destroy()
        ttk.Label(self.root, text="アバターファイル:").grid(row=0, column=0, sticky='e')
        ttk.Entry(self.root, textvariable=self.avatar_path, width=40).grid(row=0, column=1)
        ttk.Button(self.root, text="選択", command=self.browse_avatar).grid(row=0, column=2)
        ttk.Label(self.root, text="プリセットファイル:").grid(row=1, column=0, sticky='e')
        ttk.Entry(self.root, textvariable=self.preset_path, width=40).grid(row=1, column=1)
        ttk.Button(self.root, text="選択", command=self.browse_preset).grid(row=1, column=2)
        ttk.Button(self.root, text="紐付け", command=self.link).grid(row=2, column=1, pady=8)
        self.status = ttk.Label(self.root, text="", foreground="blue")
        self.status.grid(row=3, column=0, columnspan=3)
        ttk.Label(self.root, text="現在のリンク一覧:").grid(row=4, column=0, columnspan=3, pady=(10,0))
        self.links_list = tk.Listbox(self.root, width=80, height=6)
        self.links_list.grid(row=5, column=0, columnspan=3, padx=10, pady=2)

    def browse_avatar(self):
        f = filedialog.askopenfilename(title="アバターファイル選択", filetypes=[("Avatar Files", "*.vrm *.fbx *.glb *.gltf")])
        if f:
            self.avatar_path.set(f)

    def browse_preset(self):
        f = filedialog.askopenfilename(title="プリセットファイル選択", filetypes=[("Preset Files", "*.json")])
        if f:
            self.preset_path.set(f)

    def link(self):
        avatar = self.avatar_path.get()
        preset = self.preset_path.get()
        if not avatar or not os.path.isfile(avatar):
            messagebox.showerror("エラー", "有効なアバターファイルを選択してください")
            return
        if not preset or not os.path.isfile(preset):
            messagebox.showerror("エラー", "有効なプリセットファイルを選択してください")
            return
        self.links[os.path.abspath(avatar)] = os.path.abspath(preset)
        self.save_links()
        self.status.config(text=f"紐付け完了: {os.path.basename(avatar)} <-> {os.path.basename(preset)}", foreground="green")
        self.load_links()

    def load_links(self):
        # リンク情報のロードと表示
        if os.path.exists(LINKS_FILE):
            try:
                with open(LINKS_FILE, encoding='utf-8') as f:
                    self.links = json.load(f)
            except Exception:
                self.links = {}
        else:
            self.links = {}
        self.links_list.delete(0, tk.END)
        for avatar, preset in self.links.items():
            self.links_list.insert(tk.END, f"{avatar} <-> {preset}")

    def save_links(self):
        # リンク情報の保存
        try:
            with open(LINKS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.links, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("保存エラー", f"リンク情報の保存に失敗しました\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AvatarPresetLinkerGUI(root)
    root.mainloop()
