import json
import locale
import os

# 100+言語対応のフォントマップ例（必要に応じて拡張）
FONT_MAP = {
    'ja': 'Yu Gothic UI', 'en': 'Arial', 'zh': 'Noto Sans SC', 'zh-tw': 'Microsoft JhengHei',
    'ko': 'Malgun Gothic', 'ru': 'Arial', 'ar': 'Noto Naskh Arabic', 'hi': 'Noto Sans Devanagari',
    'th': 'Tahoma', 'vi': 'Arial', 'es': 'Arial', 'fr': 'Arial', 'de': 'Arial', 'pt': 'Arial',
    'id': 'Arial', 'bn': 'Noto Sans Bengali', 'ur': 'Noto Nastaliq Urdu', # ...追加可
}
LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'locales')


def _normalize_lang(lang: str) -> str:
    """Normalize a locale code to lowercase BCP-47 style (underscore → hyphen).

    Examples: 'zh_TW' → 'zh-tw', 'PT_BR' → 'pt-br', 'en' → 'en'.
    """
    if not lang:
        return lang
    return lang.lower().replace('_', '-')


class I18N:
    _translation_cache: dict = {}

    def __init__(self, lang=None):
        self.lang = _normalize_lang(lang) if lang else self.detect_language()
        self.translations = self.load_translation(self.lang)
        # Font lookup: try exact lang, then language-only prefix, then 'Arial'
        lang_prefix = self.lang.split('-')[0]
        self.font = FONT_MAP.get(self.lang) or FONT_MAP.get(lang_prefix, 'Arial')

    def detect_language(self):
        lang = os.environ.get('SATIN_LANG')
        if lang:
            return _normalize_lang(lang)
        loc = locale.getdefaultlocale()[0]
        if loc:
            return _normalize_lang(loc)
        return 'en'

    def load_translation(self, lang: str) -> dict:
        """Load translations with a fallback chain: lang → lang-prefix → en → {}."""
        if lang in self._translation_cache:
            return self._translation_cache[lang]

        candidates = [lang]
        prefix = lang.split('-')[0]
        if prefix != lang:
            candidates.append(prefix)
        if 'en' not in candidates:
            candidates.append('en')

        for candidate in candidates:
            path = os.path.join(LOCALES_DIR, f'{candidate}.json')
            if not os.path.exists(path):
                continue
            try:
                with open(path, encoding='utf-8') as f:
                    data = json.load(f)
                self._translation_cache[lang] = data
                return data
            except Exception:
                continue

        self._translation_cache[lang] = {}
        return {}

    def t(self, key, default=None):
        """Return translation for *key*, or *default* if not found.

        When *default* is None (the default), falls back to *key* itself.
        An explicit ``default=""`` returns an empty string, not *key*.
        """
        result = self.translations.get(key)
        if result is not None:
            return result
        return key if default is None else default

    def get_font(self, size=12, weight="normal"):
        return (self.font, size, weight)

# --- Flask/Web用: 言語切替はリクエストやセッションから ---
# --- サンプルGUI統合例 ---
# if __name__ == "__main__":
#     i18n = I18N()
#     root = tk.Tk()
#     root.title(i18n.t("title", "Satin 多言語デモ"))
#     tk.Label(root, text=i18n.t("hello", "こんにちは!"), font=i18n.get_font(16)).pack(padx=20, pady=20)
#     tk.Label(root, text=i18n.t("desc", "このUIは自動で言語・フォントが切り替わります。"), font=i18n.get_font(12)).pack(pady=10)
#     root.mainloop()
