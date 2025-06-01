# avatar_parameter_editor.py
# アバターパラメータ編集パネル（カテゴリ・サブカテゴリ選択式/10万パラメータ対応）

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QComboBox, QColorDialog, QPushButton, QLineEdit, QScrollArea, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from .parameters import CATEGORIES, SUBCATEGORIES, AVATAR_PARAMETERS
import json

PAGE_SIZE = 50

class AvatarParameterEditor(QWidget):
    """
    10万パラメータをカテゴリ・サブカテゴリで絞り込み編集できるパネル
    ページング・検索・保存/読込・リセット・進捗表示付き
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._widgets = {}
        self.selected_category = CATEGORIES[0]
        self.selected_subcategory = SUBCATEGORIES[0]
        self.page = 0
        self.search_text = ''
        self.setup_ui()
        self.update_parameter_list()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        # カテゴリ選択
        cat_layout = QHBoxLayout()
        cat_label = QLabel("カテゴリ:")
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(CATEGORIES)
        self.cat_combo.currentTextChanged.connect(self.on_category_changed)
        cat_layout.addWidget(cat_label)
        cat_layout.addWidget(self.cat_combo)
        layout.addLayout(cat_layout)
        # サブカテゴリ選択
        sub_layout = QHBoxLayout()
        sub_label = QLabel("サブカテゴリ:")
        self.sub_combo = QComboBox()
        self.sub_combo.addItems(SUBCATEGORIES)
        self.sub_combo.currentTextChanged.connect(self.on_subcategory_changed)
        sub_layout.addWidget(sub_label)
        sub_layout.addWidget(self.sub_combo)
        layout.addLayout(sub_layout)
        # 検索
        search_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("パラメータ名で検索...")
        self.search_box.textChanged.connect(self.on_search_changed)
        search_layout.addWidget(QLabel("検索:"))
        search_layout.addWidget(self.search_box)
        layout.addLayout(search_layout)
        # ページング
        paging_layout = QHBoxLayout()
        self.prev_btn = QPushButton("< 前へ")
        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn = QPushButton("次へ >")
        self.next_btn.clicked.connect(self.next_page)
        self.page_label = QLabel("")
        paging_layout.addWidget(self.prev_btn)
        paging_layout.addWidget(self.page_label)
        paging_layout.addWidget(self.next_btn)
        layout.addLayout(paging_layout)
        # スクロールエリア
        self.scroll = QScrollArea()
        self.param_area = QWidget()
        self.param_layout = QVBoxLayout(self.param_area)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.param_area)
        layout.addWidget(self.scroll)
        # 操作ボタン
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_parameters)
        self.load_btn = QPushButton("読込")
        self.load_btn.clicked.connect(self.load_parameters)
        self.reset_btn = QPushButton("リセット")
        self.reset_btn.clicked.connect(self.reset_parameters)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.load_btn)
        btn_layout.addWidget(self.reset_btn)
        layout.addLayout(btn_layout)
        layout.addStretch()

    def on_category_changed(self, text):
        self.selected_category = text
        self.page = 0
        self.update_parameter_list()

    def on_subcategory_changed(self, text):
        self.selected_subcategory = text
        self.page = 0
        self.update_parameter_list()

    def on_search_changed(self, text):
        self.search_text = text
        self.page = 0
        self.update_parameter_list()

    def prev_page(self):
        if self.page > 0:
            self.page -= 1
            self.update_parameter_list()

    def next_page(self):
        self.page += 1
        self.update_parameter_list()

    def update_parameter_list(self):
        # 既存ウィジェット削除
        for i in reversed(range(self.param_layout.count())):
            widget = self.param_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        # フィルタ
        filtered = [p for p in AVATAR_PARAMETERS if p['key'].startswith(f"{self.selected_category}_{self.selected_subcategory}")]
        if self.search_text:
            filtered = [p for p in filtered if self.search_text.lower() in p['label'].lower() or self.search_text.lower() in p['key'].lower()]
        total = len(filtered)
        start = self.page * PAGE_SIZE
        end = min(start + PAGE_SIZE, total)
        page_params = filtered[start:end]
        self._widgets = {}
        for param in page_params:
            h = QHBoxLayout()
            label = QLabel(param['label'])
            h.addWidget(label)
            w = None
            if param['type'] == 'slider':
                w = QSlider(Qt.Horizontal)
                w.setMinimum(param['min'])
                w.setMaximum(param['max'])
                w.setValue(param['default'])
                w.setTickInterval(1)
                h.addWidget(w)
            elif param['type'] == 'color':
                w = QPushButton()
                w.setText(str(param.get('default', '#ffffff')))
                w.setStyleSheet(f"background-color: {w.text()};")
                w.clicked.connect(lambda _, key=param['key']: self.pick_color(key))
                h.addWidget(w)
            self._widgets[param['key']] = w
            self.param_layout.addLayout(h)
        # ページ情報
        self.page_label.setText(f"{start+1} - {end} / {total}")
        self.prev_btn.setEnabled(self.page > 0)
        self.next_btn.setEnabled(end < total)

    def pick_color(self, key):
        btn = self._widgets[key]
        color = QColorDialog.getColor(QColor(btn.text()), self)
        if color.isValid():
            btn.setText(color.name())
            btn.setStyleSheet(f"background-color: {color.name()};")

    def get_parameters(self):
        params = {}
        for param in AVATAR_PARAMETERS:
            key = param['key']
            w = self._widgets.get(key)
            if w is None:
                continue
            if param['type'] == 'slider':
                params[key] = w.value()
            elif param['type'] == 'color':
                params[key] = w.text()
        return params

    def set_parameters(self, params):
        for param in AVATAR_PARAMETERS:
            key = param['key']
            w = self._widgets.get(key)
            if w is None:
                continue
            if key in params:
                if param['type'] == 'slider':
                    w.setValue(int(params[key]))
                elif param['type'] == 'color':
                    w.setText(str(params[key]))
                    w.setStyleSheet(f"background-color: {params[key]};")

    def save_parameters(self):
        params = self.get_parameters()
        try:
            with open('avatar_parameters_export.json', 'w', encoding='utf-8') as f:
                json.dump(params, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "保存", "パラメータを avatar_parameters_export.json に保存しました。")
        except Exception as e:
            QMessageBox.warning(self, "保存失敗", str(e))

    def load_parameters(self):
        try:
            with open('avatar_parameters_export.json', 'r', encoding='utf-8') as f:
                params = json.load(f)
            self.set_parameters(params)
            QMessageBox.information(self, "読込", "パラメータを読込ました。")
        except Exception as e:
            QMessageBox.warning(self, "読込失敗", str(e))

    def reset_parameters(self):
        self.update_parameter_list()
        QMessageBox.information(self, "リセット", "表示中のパラメータをデフォルト値に戻しました。")
