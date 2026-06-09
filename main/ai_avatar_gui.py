# main/ai_avatar_gui.py
"""
AI Avatar Generator GUI Module for Cocoa
AIアバター生成GUIコンポーネント
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import asyncio
import threading
from pathlib import Path
import json

from ai_avatar_generator import get_ai_avatar_generator, AvatarGenerationRequest, AvatarStyle
from video_creator import get_video_creator, VideoCreationRequest

class AIAvatarGeneratorGUI:
    """
    AIアバター生成GUI
    """

    def __init__(self, parent_frame):
        self.parent = parent_frame
        self.generator = None
        self.current_user_id = "default_user"  # 実際の運用では認証システムから取得

        # UI変数
        self.source_image_path = tk.StringVar()
        self.prompt_text = tk.StringVar(value="professional headshot, friendly expression")
        self.selected_style = tk.StringVar(value=AvatarStyle.REALISTIC)
        self.quality_var = tk.StringVar(value="high")

        # カスタマイズ変数
        self.age_var = tk.StringVar(value="30")
        self.gender_var = tk.StringVar(value="neutral")
        self.hair_color_var = tk.StringVar(value="natural")
        self.expression_var = tk.StringVar(value="friendly")

        self.setup_ui()

    def setup_ui(self):
        """UIコンポーネントのセットアップ"""
        # タブコントロール作成
        tab_control = ttk.Notebook(self.parent)
        tab_control.grid(row=0, column=0, sticky="nsew")

        # アバター生成タブ
        avatar_tab = ttk.Frame(tab_control)
        tab_control.add(avatar_tab, text="アバター生成")

        # 動画作成タブ
        video_tab = ttk.Frame(tab_control)
        tab_control.add(video_tab, text="動画作成")

        # アバター生成タブのセットアップ
        self.setup_avatar_generation_tab(avatar_tab)

        # 動画作成タブのセットアップ
        self.setup_video_creation_tab(video_tab)

    def setup_avatar_generation_tab(self, tab_frame):
        """アバター生成タブのセットアップ"""
        # メインコンテナ
        main_frame = ttk.Frame(tab_frame, padding="20")
        main_frame.grid(row=0, column=0, sticky="nsew")
        tab_frame.grid_rowconfigure(0, weight=1)
        tab_frame.grid_columnconfigure(0, weight=1)

        # タイトル
        title_label = ttk.Label(main_frame, text="AIアバター生成",
                               font=("Segoe UI", 14, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # 入力セクション
        input_frame = ttk.LabelFrame(main_frame, text="生成設定", padding="15")
        input_frame.grid(row=1, column=0, sticky="ew", pady=(0, 20))

        # ソース画像選択
        ttk.Label(input_frame, text="ソース画像 (オプション):").grid(
            row=0, column=0, sticky="w", pady=(0, 5))

        image_frame = ttk.Frame(input_frame)
        image_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        image_frame.grid_columnconfigure(0, weight=1)

        self.image_entry = ttk.Entry(image_frame, textvariable=self.source_image_path)
        self.image_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        browse_btn = ttk.Button(image_frame, text="参照", command=self.browse_image)
        browse_btn.grid(row=0, column=1)

        # プロンプト入力
        ttk.Label(input_frame, text="プロンプト:").grid(
            row=2, column=0, sticky="w", pady=(0, 5))

        self.prompt_entry = ttk.Entry(input_frame, textvariable=self.prompt_text, width=50)
        self.prompt_entry.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 15))

        # スタイル選択
        ttk.Label(input_frame, text="スタイル:").grid(
            row=4, column=0, sticky="w", pady=(0, 5))

        style_frame = ttk.Frame(input_frame)
        style_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 15))

        styles = AvatarStyle.get_available_styles()
        for i, style in enumerate(styles):
            ttk.Radiobutton(style_frame, text=style.title(),
                           variable=self.selected_style, value=style).grid(
                row=i//3, column=i%3, sticky="w", padx=(0, 20), pady=2)

        # 品質選択
        ttk.Label(input_frame, text="品質:").grid(
            row=6, column=0, sticky="w", pady=(0, 5))

        quality_frame = ttk.Frame(input_frame)
        quality_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 15))

        ttk.Radiobutton(quality_frame, text="高品質", variable=self.quality_var,
                       value="high").grid(row=0, column=0, sticky="w", padx=(0, 20))
        ttk.Radiobutton(quality_frame, text="標準", variable=self.quality_var,
                       value="standard").grid(row=0, column=1, sticky="w")

        # カスタマイズセクション
        custom_frame = ttk.LabelFrame(main_frame, text="詳細カスタマイズ", padding="15")
        custom_frame.grid(row=2, column=0, sticky="ew", pady=(0, 20))

        # 年齢
        ttk.Label(custom_frame, text="年齢:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(custom_frame, textvariable=self.age_var, width=10).grid(
            row=0, column=1, sticky="w", padx=(10, 20), pady=2)

        # 性別
        ttk.Label(custom_frame, text="性別:").grid(row=0, column=2, sticky="w", pady=2)
        gender_combo = ttk.Combobox(custom_frame, textvariable=self.gender_var,
                                   values=["neutral", "male", "female"], width=10)
        gender_combo.grid(row=0, column=3, sticky="w", padx=(10, 20), pady=2)

        # 髪色
        ttk.Label(custom_frame, text="髪色:").grid(row=1, column=0, sticky="w", pady=2)
        hair_combo = ttk.Combobox(custom_frame, textvariable=self.hair_color_var,
                                 values=["natural", "black", "brown", "blonde", "red", "gray"],
                                 width=10)
        hair_combo.grid(row=1, column=1, sticky="w", padx=(10, 20), pady=2)

        # 表情
        ttk.Label(custom_frame, text="表情:").grid(row=1, column=2, sticky="w", pady=2)
        expr_combo = ttk.Combobox(custom_frame, textvariable=self.expression_var,
                                 values=["friendly", "professional", "happy", "serious", "confident"],
                                 width=10)
        expr_combo.grid(row=1, column=3, sticky="w", padx=(10, 20), pady=2)

        # 生成ボタン
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, pady=(0, 20))

        self.generate_btn = ttk.Button(button_frame, text="アバター生成",
                                      command=self.start_generation,
                                      style='Primary.TButton')
        self.generate_btn.grid(row=0, column=0, padx=(0, 10))

        self.preview_btn = ttk.Button(button_frame, text="プレビュー",
                                    command=self.show_preview,
                                    state='disabled')
        self.preview_btn.grid(row=0, column=1, padx=(0, 10))

        self.save_btn = ttk.Button(button_frame, text="保存",
                                  command=self.save_avatar,
                                  state='disabled')
        self.save_btn.grid(row=0, column=2)

        # 進捗バー
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var,
                                           maximum=100, mode='determinate')
        self.progress_bar.grid(row=4, column=0, sticky="ew", pady=(0, 10))

        # ステータスラベル
        self.status_label = ttk.Label(main_frame, text="準備完了",
                                     foreground="blue")
        self.status_label.grid(row=5, column=0, sticky="w")

        # 結果表示エリア
        result_frame = ttk.LabelFrame(main_frame, text="生成結果", padding="15")
        result_frame.grid(row=6, column=0, sticky="nsew", pady=(20, 0))

        # 画像表示キャンバス
        self.canvas = tk.Canvas(result_frame, width=256, height=256,
                               bg='lightgray', relief='sunken')
        self.canvas.grid(row=0, column=0, pady=(0, 10))

        # メタデータ表示
        self.metadata_text = tk.Text(result_frame, height=6, width=50,
                                    state='disabled', wrap='word')
        self.metadata_text.grid(row=1, column=0, sticky="ew")

        # スクロールバー
        scrollbar = ttk.Scrollbar(result_frame, command=self.metadata_text.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.metadata_text.config(yscrollcommand=scrollbar.set)

        # レイアウト設定
        main_frame.grid_columnconfigure(0, weight=1)
        input_frame.grid_columnconfigure(1, weight=1)
        custom_frame.grid_columnconfigure(3, weight=1)
        result_frame.grid_columnconfigure(0, weight=1)

        # 初期化
        self.current_result = None
        asyncio.create_task(self.initialize_generator())

    def setup_video_creation_tab(self, tab_frame):
        """動画作成タブのセットアップ"""
        # メインコンテナ
        main_frame = ttk.Frame(tab_frame, padding="20")
        main_frame.grid(row=0, column=0, sticky="nsew")
        tab_frame.grid_rowconfigure(0, weight=1)
        tab_frame.grid_columnconfigure(0, weight=1)

        # タイトル
        title_label = ttk.Label(main_frame, text="AI動画作成",
                               font=("Segoe UI", 14, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # スクリプト入力セクション
        script_frame = ttk.LabelFrame(main_frame, text="スクリプト入力", padding="15")
        script_frame.grid(row=1, column=0, sticky="ew", pady=(0, 20))

        ttk.Label(script_frame, text="動画スクリプト:").grid(
            row=0, column=0, sticky="w", pady=(0, 5))

        # スクリプトテキストエリア
        self.script_text = tk.Text(script_frame, height=8, width=60, wrap='word')
        self.script_text.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.script_text.insert("1.0", "こんにちは！私はAIアバターです。今日は素晴らしい一日ですね。")

        # 設定セクション
        settings_frame = ttk.LabelFrame(main_frame, text="動画設定", padding="15")
        settings_frame.grid(row=2, column=0, sticky="ew", pady=(0, 20))

        # アバタースタイル
        ttk.Label(settings_frame, text="アバタースタイル:").grid(row=0, column=0, sticky="w", pady=2)
        self.video_avatar_style = tk.StringVar(value="professional")
        style_combo = ttk.Combobox(settings_frame, textvariable=self.video_avatar_style,
                                  values=AvatarStyle.get_available_styles(), width=15)
        style_combo.grid(row=0, column=1, sticky="w", padx=(10, 20), pady=2)

        # 音声設定
        ttk.Label(settings_frame, text="音声:").grid(row=0, column=2, sticky="w", pady=2)
        self.voice_type = tk.StringVar(value="female")
        voice_combo = ttk.Combobox(settings_frame, textvariable=self.voice_type,
                                  values=["female", "male"], width=10)
        voice_combo.grid(row=0, column=3, sticky="w", padx=(10, 20), pady=2)

        # 解像度
        ttk.Label(settings_frame, text="解像度:").grid(row=1, column=0, sticky="w", pady=2)
        self.resolution = tk.StringVar(value="1080p")
        res_combo = ttk.Combobox(settings_frame, textvariable=self.resolution,
                                values=["720p", "1080p"], width=10)
        res_combo.grid(row=1, column=1, sticky="w", padx=(10, 20), pady=2)

        # 背景音楽
        ttk.Label(settings_frame, text="背景音楽 (オプション):").grid(row=1, column=2, sticky="w", pady=2)
        self.bg_music_path = tk.StringVar()
        music_frame = ttk.Frame(settings_frame)
        music_frame.grid(row=1, column=3, sticky="ew", padx=(10, 0), pady=2)
        music_frame.grid_columnconfigure(0, weight=1)

        self.music_entry = ttk.Entry(music_frame, textvariable=self.bg_music_path)
        self.music_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(music_frame, text="参照", command=self.browse_music).grid(row=0, column=1)

        # 作成ボタン
        create_button_frame = ttk.Frame(main_frame)
        create_button_frame.grid(row=3, column=0, pady=(0, 20))

        self.create_video_btn = ttk.Button(create_button_frame, text="動画作成",
                                          command=self.start_video_creation,
                                          style='Primary.TButton')
        self.create_video_btn.grid(row=0, column=0, padx=(0, 10))

        self.video_preview_btn = ttk.Button(create_button_frame, text="動画プレビュー",
                                           command=self.preview_video,
                                           state='disabled')
        self.video_preview_btn.grid(row=0, column=1, padx=(0, 10))

        self.save_video_btn = ttk.Button(create_button_frame, text="動画保存",
                                        command=self.save_video,
                                        state='disabled')
        self.save_video_btn.grid(row=0, column=2)

        # 進捗バー
        self.video_progress_var = tk.DoubleVar()
        self.video_progress_bar = ttk.Progressbar(main_frame, variable=self.video_progress_var,
                                                 maximum=100, mode='determinate')
        self.video_progress_bar.grid(row=4, column=0, sticky="ew", pady=(0, 10))

        # ステータスラベル
        self.video_status_label = ttk.Label(main_frame, text="準備完了",
                                           foreground="blue")
        self.video_status_label.grid(row=5, column=0, sticky="w")

        # 結果表示エリア
        video_result_frame = ttk.LabelFrame(main_frame, text="作成結果", padding="15")
        video_result_frame.grid(row=6, column=0, sticky="nsew", pady=(20, 0))

        # サムネイル表示
        self.video_thumbnail_canvas = tk.Canvas(video_result_frame, width=320, height=180,
                                               bg='lightgray', relief='sunken')
        self.video_thumbnail_canvas.grid(row=0, column=0, pady=(0, 10))

        # 動画情報表示
        self.video_info_text = tk.Text(video_result_frame, height=6, width=50,
                                      state='disabled', wrap='word')
        self.video_info_text.grid(row=1, column=0, sticky="ew")

        # スクロールバー
        video_scrollbar = ttk.Scrollbar(video_result_frame, command=self.video_info_text.yview)
        video_scrollbar.grid(row=1, column=1, sticky="ns")
        self.video_info_text.config(yscrollcommand=video_scrollbar.set)

        # レイアウト設定
        main_frame.grid_columnconfigure(0, weight=1)
        script_frame.grid_columnconfigure(0, weight=1)
        settings_frame.grid_columnconfigure(3, weight=1)
        video_result_frame.grid_columnconfigure(0, weight=1)

        # 初期化
        self.current_video_result = None

        # 動画作成器の初期化
        self.video_creator = None
        asyncio.create_task(self.initialize_video_creator())

    async def initialize_video_creator(self):
        """動画作成器を初期化"""
        try:
            self.video_creator = await get_video_creator()
        except Exception as e:
            self.video_status_label.config(text=f"動画作成器初期化エラー: {str(e)}", foreground="red")

    def browse_music(self):
        """背景音楽ファイルを選択"""
        filetypes = [
            ('音声ファイル', '*.mp3 *.wav *.m4a *.aac'),
            ('すべてのファイル', '*.*')
        ]

        filename = filedialog.askopenfilename(
            title="背景音楽を選択",
            filetypes=filetypes
        )

        if filename:
            self.bg_music_path.set(filename)

    def start_video_creation(self):
        """動画作成を開始"""
        if not self.video_creator:
            messagebox.showerror("エラー", "動画作成器が初期化されていません")
            return

        script = self.script_text.get("1.0", tk.END).strip()
        if not script:
            messagebox.showerror("エラー", "スクリプトを入力してください")
            return

        # UIを無効化
        self.create_video_btn.config(state='disabled')
        self.video_progress_var.set(0)
        self.video_status_label.config(text="動画作成中...", foreground="orange")

        # 非同期で動画作成を実行
        threading.Thread(target=self._run_video_creation, daemon=True).start()

    def _run_video_creation(self):
        """動画作成処理を実行（別スレッド）"""
        async def create():
            try:
                # リクエスト作成
                request = VideoCreationRequest(
                    user_id=self.current_user_id,
                    script=self.script_text.get("1.0", tk.END).strip(),
                    avatar_style=self.video_avatar_style.get(),
                    voice_settings={
                        "voice": self.voice_type.get(),
                        "speed": 1.0,
                        "pitch": 0.0
                    },
                    video_settings={
                        "resolution": self.resolution.get(),
                        "fps": 30
                    },
                    background_music=self.bg_music_path.get() or None
                )

                # 進捗更新
                self.root.after(0, lambda: self.video_progress_var.set(25))
                self.root.after(0, lambda: self.video_status_label.config(
                    text="アバターを生成中...", foreground="orange"))

                # 動画作成実行
                result = await self.video_creator.create_video(request)

                # UI更新
                self.root.after(0, lambda: self._handle_video_creation_result(result))

            except Exception as e:
                err = str(e)
                self.root.after(0, lambda: self._handle_video_creation_error(err))

        # イベントループ実行
        asyncio.run(create())

    def _handle_video_creation_result(self, result):
        """動画作成結果を処理"""
        self.current_video_result = result

        if result.success:
            self.video_progress_var.set(100)
            self.video_status_label.config(text="動画作成完了", foreground="green")

            # サムネイル表示
            self._display_video_thumbnail(result.thumbnail_path)

            # 動画情報表示
            self._display_video_info(result.metadata)

            # ボタン有効化
            self.video_preview_btn.config(state='normal')
            self.save_video_btn.config(state='normal')

            messagebox.showinfo("成功", "動画の作成が完了しました！")

        else:
            self.video_progress_var.set(0)
            self.video_status_label.config(text=f"作成失敗: {result.error_message}", foreground="red")
            self.create_video_btn.config(state='normal')
            messagebox.showerror("作成エラー", f"動画作成に失敗しました:\n{result.error_message}")

    def _handle_video_creation_error(self, error_msg):
        """動画作成エラーを処理"""
        self.video_progress_var.set(0)
        self.video_status_label.config(text=f"エラー: {error_msg}", foreground="red")
        self.create_video_btn.config(state='normal')
        messagebox.showerror("エラー", f"予期しないエラーが発生しました:\n{error_msg}")

    def _display_video_thumbnail(self, thumbnail_path):
        """動画サムネイルを表示"""
        try:
            from PIL import Image, ImageTk

            if thumbnail_path and Path(thumbnail_path).exists():
                # サムネイル画像読み込み
                image = Image.open(thumbnail_path)
                image.thumbnail((320, 180))

                # Tkinter用に変換
                photo = ImageTk.PhotoImage(image)

                # キャンバスに表示
                self.video_thumbnail_canvas.delete("all")
                self.video_thumbnail_canvas.create_image(160, 90, image=photo)
                self.video_thumbnail_canvas.image = photo  # 参照保持
            else:
                # デフォルト表示
                self.video_thumbnail_canvas.delete("all")
                self.video_thumbnail_canvas.create_text(160, 90, text="サムネイルなし")

        except Exception as e:
            self.video_thumbnail_canvas.delete("all")
            self.video_thumbnail_canvas.create_text(160, 90, text=f"表示エラー:\n{str(e)}")

    def _display_video_info(self, metadata):
        """動画情報を表示"""
        self.video_info_text.config(state='normal')
        self.video_info_text.delete(1.0, tk.END)

        if metadata:
            info_str = f"""動画情報:
解像度: {metadata.get('video_settings', {}).get('resolution', '不明')}
作成時間: {metadata.get('creation_time', 0):.2f}秒
文数: {metadata.get('sentences_count', 0)}
アバタースタイル: {metadata.get('avatar_style', '不明')}
音声設定: {metadata.get('voice_settings', {}).get('voice', '不明')}

作成日時: {metadata.get('created_at', '不明')}"""
            self.video_info_text.insert(tk.END, info_str)

        self.video_info_text.config(state='disabled')

    def preview_video(self):
        """動画をプレビュー"""
        if not self.current_video_result or not self.current_video_result.video_path:
            return

        try:
            import subprocess
            import platform

            video_path = self.current_video_result.video_path

            if platform.system() == "Windows":
                os.startfile(video_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", video_path])
            else:  # Linux
                subprocess.run(["xdg-open", video_path])

        except Exception as e:
            messagebox.showerror("プレビューエラー", f"動画を開けませんでした:\n{str(e)}")

    def save_video(self):
        """動画を保存"""
        if not self.current_video_result:
            return

        try:
            # 保存先を選択
            filetypes = [('MP4ファイル', '*.mp4'), ('すべてのファイル', '*.*')]
            save_path = filedialog.asksaveasfilename(
                title="動画を保存",
                defaultextension=".mp4",
                filetypes=filetypes,
                initialfile=f"ai_avatar_video_{self.video_avatar_style.get()}.mp4"
            )

            if save_path:
                import shutil
                shutil.copy2(self.current_video_result.video_path, save_path)
                messagebox.showinfo("保存完了", f"動画を保存しました:\n{save_path}")

        except Exception as e:
            messagebox.showerror("保存エラー", f"保存に失敗しました:\n{str(e)}")

    async def initialize_generator(self):
        """AI生成器を初期化"""
        try:
            self.status_label.config(text="AIモデルを初期化中...", foreground="orange")
            self.generate_btn.config(state='disabled')

            self.generator = await get_ai_avatar_generator()

            self.status_label.config(text="準備完了", foreground="green")
            self.generate_btn.config(state='normal')

        except Exception as e:
            self.status_label.config(text=f"初期化エラー: {str(e)}", foreground="red")
            messagebox.showerror("初期化エラー", f"AIモデルの初期化に失敗しました:\n{str(e)}")

    def browse_image(self):
        """画像ファイルを選択"""
        filetypes = [
            ('画像ファイル', '*.jpg *.jpeg *.png *.bmp *.tiff'),
            ('すべてのファイル', '*.*')
        ]

        filename = filedialog.askopenfilename(
            title="ソース画像を選択",
            filetypes=filetypes
        )

        if filename:
            self.source_image_path.set(filename)

    def start_generation(self):
        """アバター生成を開始"""
        if not self.generator:
            messagebox.showerror("エラー", "AI生成器が初期化されていません")
            return

        # UIを無効化
        self.generate_btn.config(state='disabled')
        self.progress_var.set(0)
        self.status_label.config(text="生成中...", foreground="orange")

        # 非同期で生成を実行
        threading.Thread(target=self._run_generation, daemon=True).start()

    def _run_generation(self):
        """生成処理を実行（別スレッド）"""
        async def generate():
            try:
                # リクエスト作成
                customizations = {
                    "age": self.age_var.get(),
                    "gender": self.gender_var.get(),
                    "hair_color": self.hair_color_var.get(),
                    "expression": self.expression_var.get()
                }

                request = AvatarGenerationRequest(
                    user_id=self.current_user_id,
                    source_image_path=self.source_image_path.get() or None,
                    prompt=self.prompt_text.get(),
                    style=self.selected_style.get(),
                    quality=self.quality_var.get(),
                    customizations=customizations
                )

                # 進捗更新
                self.root.after(0, lambda: self.progress_var.set(25))
                self.root.after(0, lambda: self.status_label.config(
                    text="AIモデルで処理中...", foreground="orange"))

                # 生成実行
                result = await self.generator.generate_avatar(request)

                # UI更新
                self.root.after(0, lambda: self._handle_generation_result(result))

            except Exception as e:
                err = str(e)
                self.root.after(0, lambda: self._handle_generation_error(err))

        # イベントループ実行
        asyncio.run(generate())

    def _handle_generation_result(self, result):
        """生成結果を処理"""
        self.current_result = result

        if result.success:
            self.progress_var.set(100)
            self.status_label.config(text="生成完了", foreground="green")

            # 画像表示
            self._display_image(result.avatar_path)

            # メタデータ表示
            self._display_metadata(result.metadata)

            # ボタン有効化
            self.preview_btn.config(state='normal')
            self.save_btn.config(state='normal')

            messagebox.showinfo("成功", "アバターの生成が完了しました！")

        else:
            self.progress_var.set(0)
            self.status_label.config(text=f"生成失敗: {result.error_message}", foreground="red")
            self.generate_btn.config(state='normal')
            messagebox.showerror("生成エラー", f"アバター生成に失敗しました:\n{result.error_message}")

    def _handle_generation_error(self, error_msg):
        """生成エラーを処理"""
        self.progress_var.set(0)
        self.status_label.config(text=f"エラー: {error_msg}", foreground="red")
        self.generate_btn.config(state='normal')
        messagebox.showerror("エラー", f"予期しないエラーが発生しました:\n{error_msg}")

    def _display_image(self, image_path):
        """画像を表示"""
        try:
            from PIL import Image, ImageTk

            # 画像読み込み
            image = Image.open(image_path)
            image.thumbnail((256, 256))

            # Tkinter用に変換
            photo = ImageTk.PhotoImage(image)

            # キャンバスに表示
            self.canvas.delete("all")
            self.canvas.create_image(128, 128, image=photo)
            self.canvas.image = photo  # 参照保持

        except Exception as e:
            self.canvas.delete("all")
            self.canvas.create_text(128, 128, text=f"画像表示エラー:\n{str(e)}")

    def _display_metadata(self, metadata):
        """メタデータを表示"""
        self.metadata_text.config(state='normal')
        self.metadata_text.delete(1.0, tk.END)

        if metadata:
            metadata_str = json.dumps(metadata, indent=2, ensure_ascii=False)
            self.metadata_text.insert(tk.END, metadata_str)

        self.metadata_text.config(state='disabled')

    def show_preview(self):
        """プレビューを表示"""
        if self.current_result and self.current_result.thumbnail_path:
            try:
                import subprocess
                import platform

                if platform.system() == "Windows":
                    os.startfile(self.current_result.thumbnail_path)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", self.current_result.thumbnail_path])
                else:  # Linux
                    subprocess.run(["xdg-open", self.current_result.thumbnail_path])

            except Exception as e:
                messagebox.showerror("プレビューエラー", f"プレビューを開けませんでした:\n{str(e)}")

    def save_avatar(self):
        """アバターを保存"""
        if not self.current_result:
            return

        try:
            # 保存先を選択
            filetypes = [('PNGファイル', '*.png'), ('すべてのファイル', '*.*')]
            save_path = filedialog.asksaveasfilename(
                title="アバターを保存",
                defaultextension=".png",
                filetypes=filetypes,
                initialfile=f"ai_avatar_{self.selected_style.get()}.png"
            )

            if save_path:
                import shutil
                shutil.copy2(self.current_result.avatar_path, save_path)
                messagebox.showinfo("保存完了", f"アバターを保存しました:\n{save_path}")

        except Exception as e:
            messagebox.showerror("保存エラー", f"保存に失敗しました:\n{str(e)}")

    def set_user_id(self, user_id: str):
        """ユーザーIDを設定"""
        self.current_user_id = user_id
