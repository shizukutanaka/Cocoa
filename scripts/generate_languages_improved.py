#!/usr/bin/env python3
"""
言語ファイル自動生成スクリプト - 改良版

英語の言語ファイルを基に、他の言語の翻訳ファイルを自動生成します。
目標は50言語対応の実現です。
"""

import json
from pathlib import Path
from typing import Dict, Any
import logging

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LanguageFileGenerator:
    """言語ファイル自動生成クラス - 改良版"""

    def __init__(self, locales_dir: str = "locales"):
        """言語ファイル生成クラスを初期化"""
        self.locales_dir = Path(locales_dir)
        self.locales_dir.mkdir(exist_ok=True)

        # 言語マッピング（言語コード -> 言語名）
        self.language_map = {
            'nl': 'オランダ語',
            'sv': 'スウェーデン語',
            'no': 'ノルウェー語',
            'da': 'デンマーク語',
            'fi': 'フィンランド語',
            'cs': 'チェコ語',
            'hu': 'ハンガリー語',
            'el': 'ギリシャ語',
            'he': 'ヘブライ語',
            'ms': 'マレー語',
            'tl': 'タガログ語',
            'bn': 'ベンガル語',
            'ur': 'ウルドゥー語',
            'fa': 'ペルシャ語',
            'uk': 'ウクライナ語',
            'bg': 'ブルガリア語',
            'hr': 'クロアチア語',
            'sk': 'スロバキア語',
            'sl': 'スロベニア語',
            'et': 'エストニア語',
            'lv': 'ラトビア語',
            'lt': 'リトアニア語',
            'mt': 'マルタ語',
            'is': 'アイスランド語',
            'ga': 'アイルランド語',
            'cy': 'ウェールズ語',
            'sq': 'アルバニア語',
            'mk': 'マケドニア語',
            'bs': 'ボスニア語',
            'me': 'モンテネグロ語',
            'sr': 'セルビア語',
            'hy': 'アルメニア語',
            'ka': 'ジョージア語',
            'az': 'アゼルバイジャン語',
            'kk': 'カザフ語',
            'uz': 'ウズベク語',
            'tk': 'トルクメン語',
            'ky': 'キルギス語',
            'tg': 'タジク語',
            'mn': 'モンゴル語',
            'ne': 'ネパール語',
            'si': 'シンハラ語',
            'dv': 'ディベヒ語',
            'lo': 'ラオス語',
            'km': 'クメール語',
            'my': 'ミャンマー語',
            'am': 'アムハラ語',
            'ti': 'ティグリニャ語',
            'sw': 'スワヒリ語',
            'zu': 'ズールー語',
            'xh': 'コーサ語',
            'af': 'アフリカーンス語',
            'yo': 'ヨルバ語',
            'ig': 'イボ語',
            'ha': 'ハウサ語'
        }

        # 優先度の高い言語から実装（既に実装済みのものを除く）
        self.priority_languages = [
            'nl', 'sv', 'no', 'da', 'fi', 'cs', 'hu', 'el', 'he', 'ms',
            'tl', 'bn', 'ur', 'fa', 'uk', 'bg', 'hr', 'sk', 'sl', 'et',
            'lv', 'lt', 'mt', 'is', 'ga', 'cy', 'sq', 'mk', 'bs', 'me',
            'sr', 'hy', 'ka', 'az', 'kk', 'uz', 'tk', 'ky', 'tg', 'mn'
        ]

    def load_english_template(self) -> Dict[str, Any]:
        """英語のテンプレートファイルを読み込み"""
        en_file = self.locales_dir / "en.json"
        if not en_file.exists():
            raise FileNotFoundError(f"英語テンプレートファイルが見つかりません: {en_file}")

        with open(en_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def create_language_file(self, lang_code: str, lang_name: str, template: Dict[str, Any]) -> bool:
        """指定言語の言語ファイルを作成"""
        try:
            # 既に存在する場合はスキップ
            lang_file = self.locales_dir / f"{lang_code}.json"
            if lang_file.exists():
                logger.info(f"言語ファイルが既に存在します: {lang_code}.json")
                return True

            # テンプレートを翻訳（改良された対応）
            translated_content = self._translate_content(template, lang_code, lang_name)

            # ファイルに書き込み
            with open(lang_file, 'w', encoding='utf-8') as f:
                json.dump(translated_content, f, ensure_ascii=False, indent=2)

            logger.info(f"言語ファイルを作成しました: {lang_code}.json ({lang_name})")
            return True

        except Exception as e:
            logger.error(f"言語ファイル作成エラー ({lang_code}): {e}")
            return False

    def _translate_content(self, content: Dict[str, Any], lang_code: str, lang_name: str) -> Dict[str, Any]:
        """コンテンツを翻訳（改良版）"""
        def translate_value(value: Any) -> Any:
            if isinstance(value, str):
                # 英語のテキストを対象言語に翻訳（改良された対応）
                return self._improved_translate(value, lang_code, lang_name)
            elif isinstance(value, dict):
                return {k: translate_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [translate_value(item) for item in value]
            else:
                return value

        return translate_value(content)

    def _improved_translate(self, text: str, lang_code: str, lang_name: str) -> str:
        """改良された翻訳関数（実際の翻訳サービスとの連携が必要）"""
        # これはプレースホルダー実装です
        # 実際の運用ではGoogle Translate APIやDeepLなどの翻訳サービスと連携してください

        # 一般的な単語の簡単な対応表（改良版）
        translations = {
            'en': text,  # 英語は変更なし
            'ja': self._translate_to_japanese(text),
            'zh': self._translate_to_chinese(text),
            'ko': self._translate_to_korean(text),
            'es': self._translate_to_spanish(text),
            'fr': self._translate_to_french(text),
            'de': self._translate_to_german(text),
            'it': self._translate_to_italian(text),
            'pt': self._translate_to_portuguese(text),
            'ru': self._translate_to_russian(text),
            'ar': self._translate_to_arabic(text),
            'hi': self._translate_to_hindi(text),
            'th': self._translate_to_thai(text),
            'vi': self._translate_to_vietnamese(text),
            'tr': self._translate_to_turkish(text),
            'nl': self._translate_to_dutch(text),
            'sv': self._translate_to_swedish(text),
            'pl': self._translate_to_polish(text)
        }

        # デフォルトとして英語を返す（実際の翻訳サービス実装が必要）
        return translations.get(lang_code, text)

    def _translate_to_dutch(self, text: str) -> str:
        """英語からオランダ語への翻訳"""
        translations = {
            "Avatar Management System": "Avatar Beheersysteem",
            "Professional avatar preset management and optimization system": "Professioneel avatar preset beheer en optimalisatie systeem",
            "Version": "Versie",
            "Home": "Startpagina",
            "Dashboard": "Dashboard",
            "Settings": "Instellingen",
            "Monitoring": "Monitoring",
            "Security": "Beveiliging",
            "Performance": "Prestaties",
            "Help": "Help",
            "About": "Over"
        }
        return translations.get(text, text)

    def _translate_to_swedish(self, text: str) -> str:
        """英語からスウェーデン語への翻訳"""
        translations = {
            "Avatar Management System": "Avatar Hanteringssystem",
            "Professional avatar preset management and optimization system": "Professionellt avatar förinställningshantering och optimeringssystem",
            "Version": "Version",
            "Home": "Hem",
            "Dashboard": "Instrumentpanel",
            "Settings": "Inställningar",
            "Monitoring": "Övervakning",
            "Security": "Säkerhet",
            "Performance": "Prestanda",
            "Help": "Hjälp",
            "About": "Om"
        }
        return translations.get(text, text)

    def _translate_to_polish(self, text: str) -> str:
        """英語からポーランド語への翻訳"""
        translations = {
            "Avatar Management System": "System Zarządzania Awatarami",
            "Professional avatar preset management and optimization system": "Profesjonalny system zarządzania i optymalizacji presetów awatarów",
            "Version": "Wersja",
            "Home": "Strona główna",
            "Dashboard": "Panel sterowania",
            "Settings": "Ustawienia",
            "Monitoring": "Monitorowanie",
            "Security": "Bezpieczeństwo",
            "Performance": "Wydajność",
            "Help": "Pomoc",
            "About": "O programie"
        }
        return translations.get(text, text)

    def _translate_to_japanese(self, text: str) -> str:
        """英語から日本語への翻訳"""
        translations = {
            "Avatar Management System": "アバター管理システム",
            "Professional avatar preset management and optimization system": "プロフェッショナルなアバターのプリセット管理と最適化システム",
            "Version": "バージョン",
            "Home": "ホーム",
            "Dashboard": "ダッシュボード",
            "Settings": "設定",
            "Monitoring": "監視",
            "Security": "セキュリティ",
            "Performance": "パフォーマンス",
            "Help": "ヘルプ",
            "About": "について"
        }
        return translations.get(text, text)

    def _translate_to_chinese(self, text: str) -> str:
        """英語から中国語への翻訳"""
        translations = {
            "Avatar Management System": "头像管理系统",
            "Professional avatar preset management and optimization system": "专业的头像预设管理和优化系统",
            "Version": "版本",
            "Home": "首页",
            "Dashboard": "仪表板",
            "Settings": "设置",
            "Monitoring": "监控",
            "Security": "安全",
            "Performance": "性能",
            "Help": "帮助",
            "About": "关于"
        }
        return translations.get(text, text)

    def _translate_to_korean(self, text: str) -> str:
        """英語から韓国語への翻訳"""
        translations = {
            "Avatar Management System": "아바타 관리 시스템",
            "Professional avatar preset management and optimization system": "전문적인 아바타 프리셋 관리 및 최적화 시스템",
            "Version": "버전",
            "Home": "홈",
            "Dashboard": "대시보드",
            "Settings": "설정",
            "Monitoring": "모니터링",
            "Security": "보안",
            "Performance": "성능",
            "Help": "도움말",
            "About": "정보"
        }
        return translations.get(text, text)

    def _translate_to_spanish(self, text: str) -> str:
        """英語からスペイン語への翻訳"""
        translations = {
            "Avatar Management System": "Sistema de Gestión de Avatares",
            "Professional avatar preset management and optimization system": "Sistema profesional de gestión y optimización de presets de avatar",
            "Version": "Versión",
            "Home": "Inicio",
            "Dashboard": "Panel de Control",
            "Settings": "Configuración",
            "Monitoring": "Monitoreo",
            "Security": "Seguridad",
            "Performance": "Rendimiento",
            "Help": "Ayuda",
            "About": "Acerca de"
        }
        return translations.get(text, text)

    def _translate_to_french(self, text: str) -> str:
        """英語からフランス語への翻訳"""
        translations = {
            "Avatar Management System": "Système de Gestion d'Avatars",
            "Professional avatar preset management and optimization system": "Système professionnel de gestion et d'optimisation des presets d'avatar",
            "Version": "Version",
            "Home": "Accueil",
            "Dashboard": "Tableau de Bord",
            "Settings": "Paramètres",
            "Monitoring": "Surveillance",
            "Security": "Sécurité",
            "Performance": "Performance",
            "Help": "Aide",
            "About": "À Propos"
        }
        return translations.get(text, text)

    def _translate_to_german(self, text: str) -> str:
        """英語からドイツ語への翻訳"""
        translations = {
            "Avatar Management System": "Avatar-Management-System",
            "Professional avatar preset management and optimization system": "Professionelles System zur Verwaltung und Optimierung von Avatar-Presets",
            "Version": "Version",
            "Home": "Startseite",
            "Dashboard": "Dashboard",
            "Settings": "Einstellungen",
            "Monitoring": "Überwachung",
            "Security": "Sicherheit",
            "Performance": "Leistung",
            "Help": "Hilfe",
            "About": "Über"
        }
        return translations.get(text, text)

    def _translate_to_italian(self, text: str) -> str:
        """英語からイタリア語への翻訳"""
        translations = {
            "Avatar Management System": "Sistema di Gestione Avatar",
            "Professional avatar preset management and optimization system": "Sistema professionale per la gestione e l'ottimizzazione dei preset avatar",
            "Version": "Versione",
            "Home": "Home",
            "Dashboard": "Cruscotto",
            "Settings": "Impostazioni",
            "Monitoring": "Monitoraggio",
            "Security": "Sicurezza",
            "Performance": "Prestazioni",
            "Help": "Aiuto",
            "About": "Informazioni"
        }
        return translations.get(text, text)

    def _translate_to_portuguese(self, text: str) -> str:
        """英語からポルトガル語への翻訳"""
        translations = {
            "Avatar Management System": "Sistema de Gestão de Avatares",
            "Professional avatar preset management and optimization system": "Sistema profissional de gestão e otimização de presets de avatar",
            "Version": "Versão",
            "Home": "Início",
            "Dashboard": "Painel de Controle",
            "Settings": "Configurações",
            "Monitoring": "Monitoramento",
            "Security": "Segurança",
            "Performance": "Desempenho",
            "Help": "Ajuda",
            "About": "Sobre"
        }
        return translations.get(text, text)

    def _translate_to_russian(self, text: str) -> str:
        """英語からロシア語への翻訳"""
        translations = {
            "Avatar Management System": "Система Управления Аватарами",
            "Professional avatar preset management and optimization system": "Профессиональная система управления и оптимизации пресетов аватаров",
            "Version": "Версия",
            "Home": "Главная",
            "Dashboard": "Панель управления",
            "Settings": "Настройки",
            "Monitoring": "Мониторинг",
            "Security": "Безопасность",
            "Performance": "Производительность",
            "Help": "Помощь",
            "About": "О программе"
        }
        return translations.get(text, text)

    def _translate_to_arabic(self, text: str) -> str:
        """英語からアラビア語への翻訳"""
        translations = {
            "Avatar Management System": "نظام إدارة الصور الرمزية",
            "Professional avatar preset management and optimization system": "نظام احترافي لإدارة وتحسين إعدادات الصور الرمزية",
            "Version": "الإصدار",
            "Home": "الرئيسية",
            "Dashboard": "لوحة التحكم",
            "Settings": "الإعدادات",
            "Monitoring": "المراقبة",
            "Security": "الأمان",
            "Performance": "الأداء",
            "Help": "المساعدة",
            "About": "حول"
        }
        return translations.get(text, text)

    def _translate_to_hindi(self, text: str) -> str:
        """英語からヒンディー語への翻訳"""
        translations = {
            "Avatar Management System": "अवतार प्रबंधन प्रणाली",
            "Professional avatar preset management and optimization system": "पेशेवर अवतार प्रीसेट प्रबंधन और अनुकूलन प्रणाली",
            "Version": "संस्करण",
            "Home": "होम",
            "Dashboard": "डैशबोर्ड",
            "Settings": "सेटिंग्स",
            "Monitoring": "निगरानी",
            "Security": "सुरक्षा",
            "Performance": "प्रदर्शन",
            "Help": "सहायता",
            "About": "के बारे में"
        }
        return translations.get(text, text)

    def _translate_to_thai(self, text: str) -> str:
        """英語からタイ語への翻訳"""
        translations = {
            "Avatar Management System": "ระบบจัดการอวาตาร์",
            "Professional avatar preset management and optimization system": "ระบบจัดการและปรับแต่งพรีเซ็ตอวาตาร์อย่างมืออาชีพ",
            "Version": "เวอร์ชัน",
            "Home": "หน้าแรก",
            "Dashboard": "แดชบอร์ด",
            "Settings": "การตั้งค่า",
            "Monitoring": "การตรวจสอบ",
            "Security": "ความปลอดภัย",
            "Performance": "ประสิทธิภาพ",
            "Help": "ช่วยเหลือ",
            "About": "เกี่ยวกับ"
        }
        return translations.get(text, text)

    def _translate_to_vietnamese(self, text: str) -> str:
        """英語からベトナム語への翻訳"""
        translations = {
            "Avatar Management System": "Hệ thống Quản lý Avatar",
            "Professional avatar preset management and optimization system": "Hệ thống quản lý và tối ưu hóa cài đặt trước avatar chuyên nghiệp",
            "Version": "Phiên bản",
            "Home": "Trang chủ",
            "Dashboard": "Bảng điều khiển",
            "Settings": "Cài đặt",
            "Monitoring": "Giám sát",
            "Security": "Bảo mật",
            "Performance": "Hiệu suất",
            "Help": "Trợ giúp",
            "About": "Giới thiệu"
        }
        return translations.get(text, text)

    def _translate_to_turkish(self, text: str) -> str:
        """英語からトルコ語への翻訳"""
        translations = {
            "Avatar Management System": "Avatar Yönetim Sistemi",
            "Professional avatar preset management and optimization system": "Profesyonel avatar ön ayar yönetimi ve optimizasyon sistemi",
            "Version": "Sürüm",
            "Home": "Ana Sayfa",
            "Dashboard": "Kontrol Paneli",
            "Settings": "Ayarlar",
            "Monitoring": "İzleme",
            "Security": "Güvenlik",
            "Performance": "Performans",
            "Help": "Yardım",
            "About": "Hakkında"
        }
        return translations.get(text, text)

    def generate_all_languages(self) -> int:
        """全ての言語ファイルを生成"""
        try:
            # 英語テンプレートを読み込み
            template = self.load_english_template()
            success_count = 0

            # 優先度の高い言語から生成
            for lang_code in self.priority_languages:
                # 既に実装済みの言語はスキップ
                if lang_code in ['en', 'ja', 'zh', 'ko', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ar', 'hi', 'th', 'vi', 'tr', 'nl', 'sv', 'pl']:
                    continue

                lang_name = self.language_map.get(lang_code, f"言語({lang_code})")

                if self.create_language_file(lang_code, lang_name, template):
                    success_count += 1

            logger.info(f"言語ファイル生成完了: {success_count}個の言語を追加")
            return success_count

        except Exception as e:
            logger.error(f"言語ファイル一括生成エラー: {e}")
            return 0

    def generate_missing_languages(self, target_count: int = 50) -> int:
        """不足している言語ファイルを生成"""
        try:
            current_files = list(self.locales_dir.glob("*.json"))
            current_count = len(current_files)

            if current_count >= target_count:
                logger.info(f"目標言語数({target_count})に既に到達しています。現在の言語数: {current_count}")
                return 0

            # 英語テンプレートを読み込み
            template = self.load_english_template()

            # 不足分の言語を生成
            needed_count = target_count - current_count
            generated_count = 0

            # 優先度の高い言語から追加
            for lang_code in self.priority_languages:
                if generated_count >= needed_count:
                    break

                # 既に存在する言語はスキップ
                if (self.locales_dir / f"{lang_code}.json").exists():
                    continue

                lang_name = self.language_map.get(lang_code, f"言語({lang_code})")

                if self.create_language_file(lang_code, lang_name, template):
                    generated_count += 1

            logger.info(f"不足言語ファイル生成完了: {generated_count}個の言語を追加")
            return generated_count

        except Exception as e:
            logger.error(f"不足言語ファイル生成エラー: {e}")
            return 0


def main():
    """メイン実行関数"""
    try:
        generator = LanguageFileGenerator()

        # まず不足言語を生成（目標50言語まで）
        generated = generator.generate_missing_languages(target_count=50)

        if generated > 0:
            logger.info(f"言語ファイル生成成功: {generated}個の言語を追加しました")
        else:
            logger.info("全ての言語ファイルが既に生成済みです")

        # 現在の言語ファイル数を確認
        locales_dir = Path("locales")
        json_files = list(locales_dir.glob("*.json"))
        logger.info(f"現在の言語ファイル数: {len(json_files)}")

        return True

    except Exception as e:
        logger.error(f"言語ファイル生成スクリプト実行エラー: {e}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
