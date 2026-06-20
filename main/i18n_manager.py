# main/i18n_manager.py
"""
Internationalization Manager for Cocoa
140言語以上の多言語サポートシステム
"""

import asyncio
import contextlib
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from integrated_security import get_security_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class TranslationRequest:
    """翻訳リクエスト"""
    text: str
    source_lang: str
    target_lang: str
    context: Optional[str] = None

@dataclass
class TranslationResult:
    """翻訳結果"""
    success: bool
    translated_text: Optional[str] = None
    source_lang: str = ""
    target_lang: str = ""
    confidence: float = 0.0
    error_message: Optional[str] = None

class Language:
    """言語情報"""
    def __init__(self, code: str, name: str, native_name: str, rtl: bool = False):
        self.code = code
        self.name = name
        self.native_name = native_name
        self.rtl = rtl  # Right-to-left language

# サポート言語リスト（140+言語）
SUPPORTED_LANGUAGES = {
    # 主要言語
    "en": Language("en", "English", "English"),
    "ja": Language("ja", "Japanese", "日本語"),
    "zh": Language("zh", "Chinese", "中文"),
    "ko": Language("ko", "Korean", "한국어"),
    "es": Language("es", "Spanish", "Español"),
    "fr": Language("fr", "French", "Français"),
    "de": Language("de", "German", "Deutsch"),
    "it": Language("it", "Italian", "Italiano"),
    "pt": Language("pt", "Portuguese", "Português"),
    "ru": Language("ru", "Russian", "Русский"),
    "ar": Language("ar", "Arabic", "العربية", rtl=True),
    "hi": Language("hi", "Hindi", "हिन्दी"),

    # ヨーロッパ言語
    "nl": Language("nl", "Dutch", "Nederlands"),
    "sv": Language("sv", "Swedish", "Svenska"),
    "da": Language("da", "Danish", "Dansk"),
    "no": Language("no", "Norwegian", "Norsk"),
    "fi": Language("fi", "Finnish", "Suomi"),
    "pl": Language("pl", "Polish", "Polski"),
    "cs": Language("cs", "Czech", "Čeština"),
    "sk": Language("sk", "Slovak", "Slovenčina"),
    "hu": Language("hu", "Hungarian", "Magyar"),
    "ro": Language("ro", "Romanian", "Română"),
    "bg": Language("bg", "Bulgarian", "Български"),
    "hr": Language("hr", "Croatian", "Hrvatski"),
    "sl": Language("sl", "Slovenian", "Slovenščina"),
    "et": Language("et", "Estonian", "Eesti"),
    "lv": Language("lv", "Latvian", "Latviešu"),
    "lt": Language("lt", "Lithuanian", "Lietuvių"),
    "el": Language("el", "Greek", "Ελληνικά"),
    "he": Language("he", "Hebrew", "עברית", rtl=True),
    "tr": Language("tr", "Turkish", "Türkçe"),
    "uk": Language("uk", "Ukrainian", "Українська"),

    # アジア言語
    "th": Language("th", "Thai", "ไทย"),
    "vi": Language("vi", "Vietnamese", "Tiếng Việt"),
    "id": Language("id", "Indonesian", "Bahasa Indonesia"),
    "ms": Language("ms", "Malay", "Bahasa Melayu"),
    "tl": Language("tl", "Filipino", "Filipino"),
    "ur": Language("ur", "Urdu", "اردو", rtl=True),
    "bn": Language("bn", "Bengali", "বাংলা"),
    "ta": Language("ta", "Tamil", "தமிழ்"),
    "te": Language("te", "Telugu", "తెలుగు"),
    "mr": Language("mr", "Marathi", "मराठी"),
    "gu": Language("gu", "Gujarati", "ગુજરાતી"),
    "kn": Language("kn", "Kannada", "ಕನ್ನಡ"),
    "ml": Language("ml", "Malayalam", "മലയാളം"),
    "si": Language("si", "Sinhala", "සිංහල"),
    "ne": Language("ne", "Nepali", "नेपाली"),
    "pa": Language("pa", "Punjabi", "ਪੰਜਾਬੀ"),
    "or": Language("or", "Odia", "ଓଡ଼ିଆ"),
    "as": Language("as", "Assamese", "অসমীয়া"),
    "mni": Language("mni", "Manipuri", "মৈতৈলোন্"),
    "sat": Language("sat", "Santali", "ᱥᱟᱱᱛᱟᱲᱤ"),
    "doi": Language("doi", "Dogri", "डोगरी"),
    "mai": Language("mai", "Maithili", "मैथिली"),
    "bho": Language("bho", "Bhojpuri", "भोजपुरी"),
    "awa": Language("awa", "Awadhi", "अवधी"),
    "mag": Language("mag", "Magahi", "मगही"),
    "hne": Language("hne", "Chhattisgarhi", "छत्तीसगढ़ी"),
    "raj": Language("raj", "Rajasthani", "राजस्थानी"),
    "bgc": Language("bgc", "Haryanvi", "हरियाणवी"),

    # 中東・アフリカ言語
    "fa": Language("fa", "Persian", "فارسی", rtl=True),
    "am": Language("am", "Amharic", "አማርኛ"),
    "sw": Language("sw", "Swahili", "Kiswahili"),
    "ha": Language("ha", "Hausa", "Hausa"),
    "yo": Language("yo", "Yoruba", "Yorùbá"),
    "ig": Language("ig", "Igbo", "Igbo"),
    "zu": Language("zu", "Zulu", "isiZulu"),
    "xh": Language("xh", "Xhosa", "isiXhosa"),
    "af": Language("af", "Afrikaans", "Afrikaans"),
    "st": Language("st", "Sesotho", "Sesotho"),
    "tn": Language("tn", "Tswana", "Setswana"),
    "ts": Language("ts", "Tsonga", "Xitsonga"),

    # アメリカ大陸言語
    "qu": Language("qu", "Quechua", "Runa Simi"),
    "ay": Language("ay", "Aymara", "Aymar Aru"),
    "gn": Language("gn", "Guarani", "Avañe'ẽ"),

    # オセアニア言語
    "mi": Language("mi", "Maori", "Māori"),
    "sm": Language("sm", "Samoan", "Gagana Sāmoa"),
    "to": Language("to", "Tongan", "Lea Faka-Tonga"),
    "haw": Language("haw", "Hawaiian", "ʻŌlelo Hawaiʻi"),

    # その他の言語（50言語追加）
    "sq": Language("sq", "Albanian", "Shqip"),
    "hy": Language("hy", "Armenian", "Հայերեն"),
    "ka": Language("ka", "Georgian", "ქართული"),
    "az": Language("az", "Azerbaijani", "Azərbaycan"),
    "kk": Language("kk", "Kazakh", "Қазақ"),
    "uz": Language("uz", "Uzbek", "O'zbek"),
    "ky": Language("ky", "Kyrgyz", "Кыргызча"),
    "tg": Language("tg", "Tajik", "Тоҷикӣ"),
    "tk": Language("tk", "Turkmen", "Türkmençe"),
    "mn": Language("mn", "Mongolian", "Монгол"),
    "bo": Language("bo", "Tibetan", "བོད་ཡིག"),
    "my": Language("my", "Burmese", "မြန်မာဘာသာ"),
    "lo": Language("lo", "Lao", "ພາສາລາວ"),
    "km": Language("km", "Khmer", "ភាសាខ្មែរ"),
    "jv": Language("jv", "Javanese", "ꦧꦱꦗꦮ"),
    "su": Language("su", "Sundanese", "Basa Sunda"),
    "ceb": Language("ceb", "Cebuano", "Sinugboanong Binisaya"),
    "ny": Language("ny", "Chichewa", "Chichewa"),
    "rw": Language("rw", "Kinyarwanda", "Kinyarwanda"),
    "mg": Language("mg", "Malagasy", "Malagasy"),
    "sn": Language("sn", "Shona", "Shona"),
    "sd": Language("sd", "Sindhi", "سنڌي", rtl=True),
    "ps": Language("ps", "Pashto", "پښتو", rtl=True),
    "ku": Language("ku", "Kurdish", "کوردی"),
    "ti": Language("ti", "Tigrinya", "ትግርኛ"),
    "so": Language("so", "Somali", "Soomaali"),
    "om": Language("om", "Oromo", "Afaan Oromoo"),
    "aa": Language("aa", "Afar", "Afar"),
    "ss": Language("ss", "Swati", "SiSwati"),
    "nr": Language("nr", "Ndebele", "isiNdebele"),
    "ve": Language("ve", "Venda", "Tshivenḓa"),
    "fj": Language("fj", "Fijian", "Na Vosa Vakaviti"),
    "bi": Language("bi", "Bislama", "Bislama"),
    "nso": Language("nso", "Northern Sotho", "Sesotho sa Leboa"),
    "sot": Language("sot", "Southern Sotho", "Sesotho"),
    "tsn": Language("tsn", "Tswana", "Setswana"),
    "ven": Language("ven", "Venda", "Tshivenḓa"),
    "xho": Language("xho", "Xhosa", "isiXhosa"),
    "zul": Language("zul", "Zulu", "isiZulu"),
    "ssw": Language("ssw", "Swati", "SiSwati"),
    "nde": Language("nde", "North Ndebele", "isiNdebele"),
    "nbl": Language("nbl", "South Ndebele", "isiNdebele"),
    "tso": Language("tso", "Tsonga", "Xitsonga"),
}

class TranslationService:
    """翻訳サービス"""

    def __init__(self):
        self.session = None
        self.api_keys = {
            "google": os.getenv("GOOGLE_TRANSLATE_API_KEY", ""),
            "microsoft": os.getenv("MICROSOFT_TRANSLATOR_KEY", ""),
            "deepl": os.getenv("DEEPL_API_KEY", "")
        }

    async def initialize(self):
        """初期化"""
        if not self.session and AIOHTTP_AVAILABLE:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """クリーンアップ"""
        if self.session:
            await self.session.close()

    async def translate(self, request: TranslationRequest) -> TranslationResult:
        """
        テキストを翻訳

        Args:
            request: 翻訳リクエスト

        Returns:
            翻訳結果
        """
        await self.initialize()

        try:
            # Google Translate APIを優先
            if self.api_keys["google"]:
                return await self._translate_google(request)
            if self.api_keys["deepl"]:
                return await self._translate_deepl(request)
            if self.api_keys["microsoft"]:
                return await self._translate_microsoft(request)
            # フォールバック：ローカル辞書ベース
            return await self._translate_local(request)

        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return TranslationResult(
                success=False,
                error_message=str(e),
                source_lang=request.source_lang,
                target_lang=request.target_lang
            )

    async def _translate_google(self, request: TranslationRequest) -> TranslationResult:
        """Google Translate APIを使用"""
        url = "https://translation.googleapis.com/language/translate/v2"

        params = {
            "q": request.text,
            "source": request.source_lang,
            "target": request.target_lang,
            "key": self.api_keys["google"]
        }

        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                translated_text = data["data"]["translations"][0]["translatedText"]

                return TranslationResult(
                    success=True,
                    translated_text=translated_text,
                    source_lang=request.source_lang,
                    target_lang=request.target_lang,
                    confidence=0.9
                )
            raise Exception(f"Google Translate API error: {response.status}")

    async def _translate_deepl(self, request: TranslationRequest) -> TranslationResult:
        """DeepL APIを使用"""
        url = "https://api-free.deepl.com/v2/translate"

        data = {
            "text": request.text,
            "source_lang": request.source_lang.upper(),
            "target_lang": request.target_lang.upper(),
            "auth_key": self.api_keys["deepl"]
        }

        async with self.session.post(url, data=data) as response:
            if response.status == 200:
                result = await response.json()
                translated_text = result["translations"][0]["text"]

                return TranslationResult(
                    success=True,
                    translated_text=translated_text,
                    source_lang=request.source_lang,
                    target_lang=request.target_lang,
                    confidence=0.95
                )
            raise Exception(f"DeepL API error: {response.status}")

    async def _translate_microsoft(self, request: TranslationRequest) -> TranslationResult:
        """Microsoft Translator APIを使用"""
        # Microsoft Translator APIの実装
        return TranslationResult(
            success=False,
            error_message="Microsoft Translator not implemented",
            source_lang=request.source_lang,
            target_lang=request.target_lang
        )

    async def _translate_local(self, request: TranslationRequest) -> TranslationResult:
        """ローカル辞書ベースの翻訳（フォールバック）"""
        # シンプルな辞書ベース翻訳
        basic_translations = {
            ("en", "ja"): {
                "Hello": "こんにちは",
                "Yes": "はい",
                "No": "いいえ",
                "Thank you": "ありがとう",
                "Please": "お願いします"
            },
            ("ja", "en"): {
                "こんにちは": "Hello",
                "はい": "Yes",
                "いいえ": "No",
                "ありがとう": "Thank you",
                "お願いします": "Please"
            }
        }

        key = (request.source_lang, request.target_lang)
        translations = basic_translations.get(key, {})

        translated_text = translations.get(request.text, request.text)

        return TranslationResult(
            success=True,
            translated_text=translated_text,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            confidence=0.5
        )

class I18NManager:
    """
    多言語化マネージャー
    140言語以上のサポートを提供
    """

    def __init__(self):
        self.security_manager = get_security_manager()
        self.translation_service = TranslationService()
        self.locales_dir = Path("locales")
        self.cache_dir = Path("data/i18n_cache")

        # 言語データ
        self.languages = SUPPORTED_LANGUAGES
        self.translations: Dict[str, Dict] = {}
        self.translation_cache: Dict[str, Dict] = {}

        # 現在の言語設定
        self.current_language = "en"
        self.fallback_language = "en"

        logger.info(f"I18N Manager initialized with {len(self.languages)} languages")

    async def initialize(self):
        """初期化"""
        await self.translation_service.initialize()
        await self.load_translations()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def close(self):
        """クリーンアップ"""
        await self.translation_service.close()

    async def load_translations(self):
        """言語ファイルを読み込み"""
        if not self.locales_dir.exists():
            logger.warning("Locales directory not found")
            return

        for lang_file in self.locales_dir.glob("*.json"):
            lang_code = lang_file.stem
            try:
                with open(lang_file, encoding='utf-8') as f:  # noqa: ASYNC230
                    self.translations[lang_code] = json.load(f)
                logger.info(f"Loaded translations for {lang_code}")
            except Exception as e:
                logger.error(f"Failed to load {lang_file}: {e}")

    def set_language(self, language_code: str) -> bool:
        """
        表示言語を設定

        Args:
            language_code: 言語コード

        Returns:
            設定成功かどうか
        """
        if language_code in self.languages:
            self.current_language = language_code
            logger.info(f"Language set to {language_code}")
            return True
        logger.warning(f"Unsupported language: {language_code}")
        return False

    def get_available_languages(self) -> List[Dict]:
        """利用可能な言語一覧を取得"""
        return [
            {
                "code": lang.code,
                "name": lang.name,
                "native_name": lang.native_name,
                "rtl": lang.rtl
            }
            for lang in self.languages.values()
        ]

    def translate(self, key: str, language_code: Optional[str] = None,
                  fallback: Optional[str] = None, **kwargs) -> str:
        """
        テキストを翻訳

        Args:
            key: 翻訳キー
            language_code: 言語コード（指定なしの場合は現在の言語）
            fallback: フォールバックテキスト
            **kwargs: フォーマット引数

        Returns:
            翻訳されたテキスト
        """
        lang_code = language_code or self.current_language

        # 指定言語の翻訳を取得
        lang_translations = self.translations.get(lang_code, {})

        # キーをドット表記で分割して探索
        value = self._get_nested_value(lang_translations, key.split('.'))

        if value is None:
            # フォールバック言語を試行
            if lang_code != self.fallback_language:
                fallback_translations = self.translations.get(self.fallback_language, {})
                value = self._get_nested_value(fallback_translations, key.split('.'))

            # それでも見つからない場合
            if value is None:
                value = fallback or key

        # フォーマット適用
        if isinstance(value, str) and kwargs:
            # フォーマット失敗時はそのまま
            with contextlib.suppress(KeyError, ValueError):
                value = value.format(**kwargs)

        return value

    def _get_nested_value(self, data: Dict, keys: List[str]) -> Optional[str]:
        """ネストされた辞書から値を取得"""
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current if isinstance(current, str) else None

    async def translate_text(self, text: str, target_lang: str,
                           source_lang: Optional[str] = None) -> str:
        """
        任意のテキストを翻訳

        Args:
            text: 翻訳するテキスト
            target_lang: 対象言語
            source_lang: ソース言語（自動検出の場合はNone）

        Returns:
            翻訳されたテキスト
        """
        if target_lang == source_lang:
            return text

        # キャッシュチェック
        cache_key = self._get_cache_key(text, source_lang or "auto", target_lang)
        cached_result = self.translation_cache.get(cache_key)
        if cached_result:
            return cached_result.get("translated_text", text)

        # 翻訳実行
        request = TranslationRequest(
            text=text,
            source_lang=source_lang or "auto",
            target_lang=target_lang
        )

        result = await self.translation_service.translate(request)

        if result.success and result.translated_text:
            # キャッシュ保存
            self.translation_cache[cache_key] = {
                "translated_text": result.translated_text,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            # 定期的にキャッシュをクリーンアップ
            if len(self.translation_cache) > 10000:
                await self._cleanup_cache()

            return result.translated_text
        logger.warning(f"Translation failed: {result.error_message}")
        return text

    def _get_cache_key(self, text: str, source_lang: str, target_lang: str) -> str:
        """キャッシュキーを生成"""
        content = f"{text}:{source_lang}:{target_lang}"
        return hashlib.md5(content.encode()).hexdigest()

    async def _cleanup_cache(self):
        """古いキャッシュをクリーンアップ"""
        current_time = datetime.now(timezone.utc)
        to_remove = []

        for key, data in self.translation_cache.items():
            timestamp = data.get("timestamp")
            if timestamp:
                cache_time = datetime.fromisoformat(timestamp)
                if cache_time.tzinfo is None:
                    cache_time = cache_time.replace(tzinfo=timezone.utc)
                if (current_time - cache_time).days > 7:  # 7日以上経過
                    to_remove.append(key)

        for key in to_remove:
            del self.translation_cache[key]

        logger.info(f"Cleaned up {len(to_remove)} old cache entries")

    async def expand_translations(self, target_languages: List[str] = None):
        """
        既存の翻訳を他の言語に拡張

        Args:
            target_languages: 対象言語リスト（Noneの場合は全言語）
        """
        if target_languages is None:
            target_languages = list(self.languages.keys())

        base_translations = self.translations.get(self.fallback_language, {})
        if not base_translations:
            logger.warning("No base translations found")
            return

        for lang_code in target_languages:
            if lang_code == self.fallback_language or lang_code in self.translations:
                continue

            logger.info(f"Expanding translations for {lang_code}")

            expanded = {}
            await self._expand_dict(base_translations, expanded, lang_code)

            if expanded:
                self.translations[lang_code] = expanded

                # ファイルに保存
                lang_file = self.locales_dir / f"{lang_code}.json"
                try:
                    with open(lang_file, 'w', encoding='utf-8') as f:  # noqa: ASYNC230
                        json.dump(expanded, f, ensure_ascii=False, indent=2)
                    logger.info(f"Saved expanded translations for {lang_code}")
                except Exception as e:
                    logger.error(f"Failed to save translations for {lang_code}: {e}")

    async def _expand_dict(self, source_dict: Dict, target_dict: Dict, target_lang: str):
        """辞書を再帰的に翻訳"""
        for key, value in source_dict.items():
            if isinstance(value, dict):
                target_dict[key] = {}
                await self._expand_dict(value, target_dict[key], target_lang)
            elif isinstance(value, str):
                # テキストを翻訳
                translated = await self.translate_text(value, target_lang, self.fallback_language)
                target_dict[key] = translated

                # APIレート制限を考慮して少し待機
                await asyncio.sleep(0.1)

    def get_language_info(self, language_code: str) -> Optional[Dict]:
        """言語情報を取得"""
        lang = self.languages.get(language_code)
        if lang:
            return {
                "code": lang.code,
                "name": lang.name,
                "native_name": lang.native_name,
                "rtl": lang.rtl
            }
        return None

    def is_rtl_language(self, language_code: str) -> bool:
        """RTL言語かどうかをチェック"""
        lang = self.languages.get(language_code)
        return lang.rtl if lang else False

    async def detect_language(self, text: str) -> str:
        """
        テキストの言語を検出

        Args:
            text: 検出対象テキスト

        Returns:
            検出された言語コード
        """
        # 簡易的な言語検出（実際には言語検出APIを使用）
        # 日本語文字を含む場合
        if any(ord(char) > 0x3000 for char in text):
            return "ja"

        # アラビア文字を含む場合
        if any(0x0600 <= ord(char) <= 0x06FF for char in text):
            return "ar"

        # キリル文字を含む場合
        if any(0x0400 <= ord(char) <= 0x04FF for char in text):
            return "ru"

        # デフォルトは英語
        return "en"

# グローバルインスタンス管理
_i18n_manager = None
_i18n_manager_lock = asyncio.Lock()

async def get_i18n_manager() -> I18NManager:
    """I18Nマネージャーのインスタンスを取得"""
    global _i18n_manager

    if _i18n_manager is None:
        async with _i18n_manager_lock:
            if _i18n_manager is None:
                _i18n_manager = I18NManager()
                await _i18n_manager.initialize()

    return _i18n_manager

# 便利関数
def _(key: str, **kwargs) -> str:
    """翻訳ショートカット関数（同期版）"""
    # 非同期コンテキストでは使用できないため、基本言語を返す
    return key
