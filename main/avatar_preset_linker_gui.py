import os
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
from pathlib import Path
from ai_avatar_gui import AIAvatarGeneratorGUI

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
LINKS_FILE = BASE_DIR / "avatar_preset_links.json"

class AvatarPresetLinkerGUI:
    # Design System Constants (Atlassian-inspired)
    SPACING = {
        'xs': 4,
        'sm': 8,
        'md': 16,
        'lg': 24,
        'xl': 32
    }

    COLORS = {
        'primary': '#0052CC',
        'success': '#00875A',
        'error': '#DE350B',
        'warning': '#FF8B00',
        'text_primary': '#172B4D',
        'text_secondary': '#5E6C84',
        'bg_neutral': '#F4F5F7',
        'border': '#DFE1E6'
    }

    def __init__(self, root):
        self.root = root
        self.root.title("アバターとプリセットの紐付け管理")
        self.root.minsize(700, 550)

        # Configure style
        self.setup_styles()

        self.avatar_path = tk.StringVar()
        self.preset_path = tk.StringVar()
        self.status = None
        self.links_list = None
        self.links = {}
        self.create_widgets()
        self.load_links()

        # Keyboard shortcuts
        self.root.bind('<Control-n>', lambda e: self.link())
        self.root.bind('<Delete>', lambda e: self.delete_selected_link())
        self.root.bind('<Control-l>', lambda e: self.load_links())

    def setup_styles(self):
        """Configure ttk styles based on design system"""
        style = ttk.Style()

        # Button styles
        style.configure('Primary.TButton',
                       padding=(self.SPACING['md'], self.SPACING['sm']))
        style.configure('Secondary.TButton',
                       padding=(self.SPACING['sm'], self.SPACING['xs']))

        # Label styles
        style.configure('Heading.TLabel',
                       font=('Segoe UI', 10, 'bold'),
                       foreground=self.COLORS['text_primary'])
        style.configure('Body.TLabel',
                       font=('Segoe UI', 9),
                       foreground=self.COLORS['text_secondary'])

        # Frame styles
        style.configure('Card.TFrame',
                       background=self.COLORS['bg_neutral'],
                       relief='flat')

    def create_widgets(self):
        """Create UI components with tabs for different functionalities"""
        for widget in self.root.winfo_children():
            widget.destroy()

        # Create tabbed interface
        tab_control = ttk.Notebook(self.root)
        tab_control.grid(row=0, column=0, sticky='nsew')

        # Tab 1: Preset Linker (existing functionality)
        preset_tab = ttk.Frame(tab_control, padding=self.SPACING['lg'])
        tab_control.add(preset_tab, text="プリセット管理")

        # Tab 2: AI Avatar Generator (new functionality)
        avatar_tab = ttk.Frame(tab_control)
        tab_control.add(avatar_tab, text="AIアバター生成")

        # Configure grid weights
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Setup preset linker tab
        self.setup_preset_linker_tab(preset_tab)

        # Setup AI avatar generator tab
        self.setup_ai_avatar_tab(avatar_tab)

    def setup_preset_linker_tab(self, parent):
        """Setup the preset linker tab with existing functionality"""
        # Main container with padding
        main_container = ttk.Frame(parent, padding=self.SPACING['lg'])
        main_container.grid(row=0, column=0, sticky='nsew')
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # File Selection Section
        file_frame = ttk.LabelFrame(main_container, text="ファイル選択", padding=self.SPACING['md'])
        file_frame.grid(row=0, column=0, sticky='ew', pady=(0, self.SPACING['md']))

        # Avatar file row
        ttk.Label(file_frame, text="アバターファイル:", style='Body.TLabel').grid(
            row=0, column=0, sticky='w', pady=(0, self.SPACING['sm']))

        avatar_row = ttk.Frame(file_frame)
        avatar_row.grid(row=1, column=0, sticky='ew', pady=(0, self.SPACING['md']))
        avatar_row.grid_columnconfigure(0, weight=1)

        self.avatar_entry = ttk.Entry(avatar_row, textvariable=self.avatar_path)
        self.avatar_entry.grid(row=0, column=0, sticky='ew', padx=(0, self.SPACING['sm']))

        ttk.Button(avatar_row, text="選択...", command=self.browse_avatar, style='Secondary.TButton').grid(
            row=0, column=1)
        ttk.Button(avatar_row, text="クリア", command=lambda: self.avatar_path.set(''),
                  style='Secondary.TButton').grid(row=0, column=2, padx=(self.SPACING['xs'], 0))

        # Preset file row
        ttk.Label(file_frame, text="プリセットファイル:", style='Body.TLabel').grid(
            row=2, column=0, sticky='w', pady=(0, self.SPACING['sm']))

        preset_row = ttk.Frame(file_frame)
        preset_row.grid(row=3, column=0, sticky='ew')
        preset_row.grid_columnconfigure(0, weight=1)

        self.preset_entry = ttk.Entry(preset_row, textvariable=self.preset_path)
        self.preset_entry.grid(row=0, column=0, sticky='ew', padx=(0, self.SPACING['sm']))

        ttk.Button(preset_row, text="選択...", command=self.browse_preset, style='Secondary.TButton').grid(
            row=0, column=1)
        ttk.Button(preset_row, text="クリア", command=lambda: self.preset_path.set(''),
                  style='Secondary.TButton').grid(row=0, column=2, padx=(self.SPACING['xs'], 0))

        file_frame.grid_columnconfigure(0, weight=1)

        # Action Section
        action_frame = ttk.Frame(main_container)
        action_frame.grid(row=1, column=0, sticky='ew', pady=(0, self.SPACING['md']))

        ttk.Button(action_frame, text="紐付けを追加 (Ctrl+N)", command=self.link,
                  style='Primary.TButton').pack(side='left', padx=(0, self.SPACING['sm']))

        self.status = ttk.Label(action_frame, text="", font=('Segoe UI', 9))
        self.status.pack(side='left', fill='x', expand=True)

        # Links List Section
        links_frame = ttk.LabelFrame(main_container, text="現在のリンク一覧", padding=self.SPACING['md'])
        links_frame.grid(row=2, column=0, sticky='nsew')
        links_frame.grid_rowconfigure(0, weight=1)
        links_frame.grid_columnconfigure(0, weight=1)

        # Listbox with scrollbar
        list_container = ttk.Frame(links_frame)
        list_container.grid(row=0, column=0, sticky='nsew')
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)

        scrollbar = ttk.Scrollbar(list_container, orient='vertical')
        scrollbar.grid(row=0, column=1, sticky='ns')

        self.links_list = tk.Listbox(list_container, yscrollcommand=scrollbar.set,
                                     font=('Consolas', 9), height=10,
                                     selectmode='single', activestyle='dotbox')
        self.links_list.grid(row=0, column=0, sticky='nsew')
        scrollbar.config(command=self.links_list.yview)

        # Action buttons for list
        button_row = ttk.Frame(links_frame)
        button_row.grid(row=1, column=0, sticky='ew', pady=(self.SPACING['sm'], 0))

        ttk.Button(button_row, text="削除 (Delete)", command=self.delete_selected_link,
                  style='Secondary.TButton').pack(side='left', padx=(0, self.SPACING['xs']))
        ttk.Button(button_row, text="パスをコピー", command=self.copy_selected_paths,
                  style='Secondary.TButton').pack(side='left', padx=(0, self.SPACING['xs']))
        ttk.Button(button_row, text="更新 (Ctrl+L)", command=self.load_links,
                  style='Secondary.TButton').pack(side='left')

        # Help text
        help_text = ttk.Label(links_frame,
                             text="💡 ヒント: リンクを選択して Delete キーで削除、Ctrl+N で新規追加",
                             style='Body.TLabel', foreground=self.COLORS['text_secondary'])
        help_text.grid(row=2, column=0, sticky='w', pady=(self.SPACING['sm'], 0))

        main_container.grid_rowconfigure(2, weight=1)
        main_container.grid_columnconfigure(0, weight=1)

    def setup_ai_avatar_tab(self, parent):
        """Setup the AI avatar generator tab"""
        # Initialize AI Avatar Generator GUI
        self.ai_avatar_gui = AIAvatarGeneratorGUI(parent)

    def browse_avatar(self):
        try:
            f = filedialog.askopenfilename(
                title="アバターファイル選択",
                filetypes=[
                    ("Avatar Files", "*.vrm *.fbx *.glb *.gltf"),
                    ("All Files", "*.*")
                ]
            )
            if f:
                # ファイルサイズチェック (100MB上限)
                if os.path.getsize(f) > 100 * 1024 * 1024:
                    messagebox.showerror("エラー", "ファイルサイズが100MBを超えています")
                    return
                self.avatar_path.set(f)
        except OSError as e:
            messagebox.showerror("エラー", f"ファイルアクセスエラー: {str(e)}")
        except Exception as e:
            messagebox.showerror("エラー", f"予期しないエラー: {str(e)}")

    def browse_preset(self):
        try:
            f = filedialog.askopenfilename(
                title="プリセットファイル選択",
                filetypes=[
                    ("Preset Files", "*.json"),
                    ("All Files", "*.*")
                ]
            )
            if f:
                # ファイルサイズチェック (10MB上限)
                if os.path.getsize(f) > 10 * 1024 * 1024:
                    messagebox.showerror("エラー", "ファイルサイズが10MBを超えています")
                    return
                # JSON形式チェック
                try:
                    with open(f, 'r', encoding='utf-8') as test_f:
                        json.load(test_f)
                except json.JSONDecodeError:
                    if not messagebox.askyesno("警告", "有効なJSON形式ではありません。続行しますか?"):
                        return
                self.preset_path.set(f)
        except OSError as e:
            messagebox.showerror("エラー", f"ファイルアクセスエラー: {str(e)}")
        except Exception as e:
            messagebox.showerror("エラー", f"予期しないエラー: {str(e)}")

    def link(self):
        """Add new avatar-preset link with enhanced feedback"""
        avatar = self.avatar_path.get()
        preset = self.preset_path.get()

        # 入力検証
        if not avatar or not avatar.strip():
            self.show_status("アバターファイルを選択してください", 'error')
            self.avatar_entry.focus_set()
            return
        if not preset or not preset.strip():
            self.show_status("プリセットファイルを選択してください", 'error')
            self.preset_entry.focus_set()
            return

        # ファイル存在確認
        if not os.path.isfile(avatar):
            self.show_status("アバターファイルが見つかりません", 'error')
            return
        if not os.path.isfile(preset):
            self.show_status("プリセットファイルが見つかりません", 'error')
            return

        # ファイルアクセス権限確認
        try:
            with open(avatar, 'rb') as f:
                pass
            with open(preset, 'rb') as f:
                pass
        except PermissionError:
            self.show_status("ファイルへのアクセス権限がありません", 'error')
            return
        except Exception as e:
            self.show_status(f"ファイルアクセスエラー: {str(e)}", 'error')
            return

        # 紐付け実行
        try:
            self.links[os.path.abspath(avatar)] = os.path.abspath(preset)
            self.save_links()
            self.show_status(
                f"✓ 紐付け完了: {os.path.basename(avatar)} ↔ {os.path.basename(preset)}",
                'success'
            )
            self.avatar_path.set('')
            self.preset_path.set('')
            self.load_links()
        except Exception as e:
            messagebox.showerror("エラー", f"紐付け処理に失敗しました: {str(e)}")
            self.show_status("紐付け失敗", 'error')

    def delete_selected_link(self):
        """Delete selected link from the list"""
        selection = self.links_list.curselection()
        if not selection:
            self.show_status("削除するリンクを選択してください", 'warning')
            return

        idx = selection[0]
        link_text = self.links_list.get(idx)

        # Extract avatar path from display text
        avatar_path = link_text.split(' <-> ')[0]

        # Confirm deletion
        if messagebox.askyesno("確認", f"このリンクを削除しますか?\n\n{os.path.basename(avatar_path)}"):
            try:
                if avatar_path in self.links:
                    del self.links[avatar_path]
                    self.save_links()
                    self.show_status("✓ リンクを削除しました", 'success')
                    self.load_links()
            except Exception as e:
                self.show_status(f"削除に失敗しました: {str(e)}", 'error')

    def copy_selected_paths(self):
        """Copy selected link paths to clipboard"""
        selection = self.links_list.curselection()
        if not selection:
            self.show_status("コピーするリンクを選択してください", 'warning')
            return

        idx = selection[0]
        link_text = self.links_list.get(idx)

        self.root.clipboard_clear()
        self.root.clipboard_append(link_text)
        self.show_status("✓ パスをクリップボードにコピーしました", 'success')

    def show_status(self, message, status_type='info'):
        """Show status message with appropriate color"""
        colors = {
            'success': self.COLORS['success'],
            'error': self.COLORS['error'],
            'warning': self.COLORS['warning'],
            'info': self.COLORS['primary']
        }
        self.status.config(text=message, foreground=colors.get(status_type, self.COLORS['text_primary']))

    def load_links(self):
        """リンク情報のロードと表示 - 強化版エラーハンドリング"""
        if not LINKS_FILE.exists():
            self.links = {}
            self.links_list.delete(0, tk.END)
            return

        try:
            # ファイルサイズチェック (1MB上限)
            if LINKS_FILE.stat().st_size > 1024 * 1024:
                messagebox.showerror("エラー", "リンクファイルのサイズが大きすぎます")
                self.links = {}
                return

            with LINKS_FILE.open(encoding='utf-8') as f:
                data = json.load(f)

            # データ型検証
            if not isinstance(data, dict):
                messagebox.showwarning("警告", "リンクファイルの形式が正しくありません。空の状態で初期化します。")
                self.links = {}
            else:
                # 各エントリの検証
                valid_links = {}
                for k, v in data.items():
                    if isinstance(k, str) and isinstance(v, str):
                        valid_links[str(k)] = str(v)
                self.links = valid_links

        except json.JSONDecodeError as e:
            messagebox.showerror("エラー", f"リンクファイルのJSON解析に失敗しました:\n{str(e)}")
            self.links = {}
        except PermissionError:
            messagebox.showerror("エラー", "リンクファイルへのアクセス権限がありません")
            self.links = {}
        except OSError as e:
            messagebox.showerror("エラー", f"ファイル読み込みエラー:\n{str(e)}")
            self.links = {}
        except Exception as e:
            messagebox.showerror("エラー", f"予期しないエラー:\n{str(e)}")
            self.links = {}

        # リストボックス更新
        try:
            self.links_list.delete(0, tk.END)
            for avatar, preset in self.links.items():
                display_text = f"{avatar} <-> {preset}"
                # 表示長制限
                if len(display_text) > 200:
                    display_text = display_text[:197] + "..."
                self.links_list.insert(tk.END, display_text)
        except Exception as e:
            messagebox.showerror("エラー", f"リスト表示エラー:\n{str(e)}")

    def save_links(self):
        """リンク情報の保存 - トランザクション保護"""
        temp_file = LINKS_FILE.with_suffix('.tmp')
        backup_file = LINKS_FILE.with_suffix('.bak')

        try:
            # 親ディレクトリ確認
            LINKS_FILE.parent.mkdir(parents=True, exist_ok=True)

            # 一時ファイルに書き込み
            with temp_file.open('w', encoding='utf-8') as f:
                json.dump(self.links, f, ensure_ascii=False, indent=2)

            # 既存ファイルのバックアップ
            if LINKS_FILE.exists():
                if backup_file.exists():
                    backup_file.unlink()
                LINKS_FILE.rename(backup_file)

            # 一時ファイルを正式ファイルに移動
            temp_file.rename(LINKS_FILE)

        except PermissionError:
            messagebox.showerror("保存エラー", "ファイルへの書き込み権限がありません")
            # クリーンアップ
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except (OSError, PermissionError) as cleanup_err:
                    logger.warning(f"Failed to clean up temp file: {cleanup_err}")
            raise
        except OSError as e:
            messagebox.showerror("保存エラー", f"ファイル保存エラー:\n{str(e)}")
            # クリーンアップ
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except (OSError, PermissionError) as cleanup_err:
                    logger.warning(f"Failed to clean up temp file: {cleanup_err}")
            raise
        except Exception as e:
            messagebox.showerror("保存エラー", f"予期しないエラー:\n{str(e)}")
            # クリーンアップ
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except (OSError, PermissionError) as cleanup_err:
                    logger.warning(f"Failed to clean up temp file: {cleanup_err}")
            raise

if __name__ == "__main__":
    root = tk.Tk()
    app = AvatarPresetLinkerGUI(root)
    root.mainloop()
