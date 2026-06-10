# main/template_library.py
"""
Template Library Module for Cocoa
多様なアバター・動画テンプレートライブラリ
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime, timezone

from integrated_security import get_security_manager
from template_filters import (
    sanitize_template_id,
    validate_avatar_template,
    validate_video_template,
)

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class AvatarTemplate:
    """アバターテンプレート"""
    template_id: str
    name: str
    description: str
    category: str
    style: str
    thumbnail_path: Optional[str] = None
    config: Dict = None
    tags: List[str] = None
    is_premium: bool = False
    created_at: datetime = None
    usage_count: int = 0

    def __post_init__(self):
        if self.config is None:
            self.config = {}
        if self.tags is None:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

@dataclass
class VideoTemplate:
    """動画テンプレート"""
    template_id: str
    name: str
    description: str
    category: str
    script_template: str
    avatar_config: Dict = None
    video_settings: Dict = None
    background_music: Optional[str] = None
    thumbnail_path: Optional[str] = None
    tags: List[str] = None
    is_premium: bool = False
    created_at: datetime = None
    usage_count: int = 0

    def __post_init__(self):
        if self.avatar_config is None:
            self.avatar_config = {}
        if self.video_settings is None:
            self.video_settings = {"resolution": "1080p", "fps": 30}
        if self.tags is None:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

class TemplateCategory:
    """テンプレートカテゴリ"""
    # アバターテンプレートカテゴリ
    BUSINESS = "business"
    CASUAL = "casual"
    CREATIVE = "creative"
    EDUCATION = "education"
    ENTERTAINMENT = "entertainment"
    CORPORATE = "corporate"
    PERSONAL = "personal"

    # 動画テンプレートカテゴリ
    PRESENTATION = "presentation"
    TUTORIAL = "tutorial"
    MARKETING = "marketing"
    TRAINING = "training"
    ANNOUNCEMENT = "announcement"
    STORYTELLING = "storytelling"

class TemplateLibrary:
    """
    テンプレートライブラリ
    多様なアバター・動画テンプレートを提供
    """

    def __init__(self):
        self.security_manager = get_security_manager()

        # ディレクトリ設定
        self.templates_dir = Path("data/templates")
        self.avatar_templates_dir = self.templates_dir / "avatars"
        self.video_templates_dir = self.templates_dir / "videos"
        self.thumbnails_dir = self.templates_dir / "thumbnails"

        # テンプレートストレージ
        self.avatar_templates: Dict[str, AvatarTemplate] = {}
        self.video_templates: Dict[str, VideoTemplate] = {}

        # カテゴリ定義
        self.avatar_categories = {
            TemplateCategory.BUSINESS: "ビジネス・プロフェッショナル",
            TemplateCategory.CASUAL: "カジュアル・日常",
            TemplateCategory.CREATIVE: "クリエイティブ・アーティスティック",
            TemplateCategory.EDUCATION: "教育・学習",
            TemplateCategory.ENTERTAINMENT: "エンターテイメント",
            TemplateCategory.CORPORATE: "コーポレート・企業",
            TemplateCategory.PERSONAL: "パーソナル・個人"
        }

        self.video_categories = {
            TemplateCategory.PRESENTATION: "プレゼンテーション",
            TemplateCategory.TUTORIAL: "チュートリアル",
            TemplateCategory.MARKETING: "マーケティング",
            TemplateCategory.TRAINING: "トレーニング",
            TemplateCategory.ANNOUNCEMENT: "アナウンス",
            TemplateCategory.STORYTELLING: "ストーリーテリング"
        }

        logger.info("Template Library initialized")

    async def initialize(self):
        """初期化"""
        # ディレクトリ作成
        for dir_path in [self.avatar_templates_dir, self.video_templates_dir, self.thumbnails_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # デフォルトテンプレート読み込み
        await self.load_templates()

        # デフォルトテンプレートが存在しない場合は作成
        if not self.avatar_templates:
            await self.create_default_avatar_templates()

        if not self.video_templates:
            await self.create_default_video_templates()

    async def load_templates(self):
        """テンプレートを読み込み"""
        # アバターテンプレート読み込み
        for template_file in self.avatar_templates_dir.glob("*.json"):
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    schema = validate_avatar_template(data)
                    if not schema["valid"]:
                        logger.warning(f"Skipping invalid avatar template {template_file}: {schema['errors']}")
                        continue
                    template = AvatarTemplate(**data)
                    self.avatar_templates[template.template_id] = template
            except Exception as e:
                logger.error(f"Failed to load avatar template {template_file}: {e}")

        # 動画テンプレート読み込み
        for template_file in self.video_templates_dir.glob("*.json"):
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    schema = validate_video_template(data)
                    if not schema["valid"]:
                        logger.warning(f"Skipping invalid video template {template_file}: {schema['errors']}")
                        continue
                    template = VideoTemplate(**data)
                    self.video_templates[template.template_id] = template
            except Exception as e:
                logger.error(f"Failed to load video template {template_file}: {e}")

        logger.info(f"Loaded {len(self.avatar_templates)} avatar templates and {len(self.video_templates)} video templates")

    async def create_default_avatar_templates(self):
        """デフォルトのアバターテンプレートを作成"""
        default_templates = [
            # ビジネスカテゴリ - 拡張
            AvatarTemplate(
                template_id="business_executive",
                name="ビジネスエグゼクティブ",
                description="プロフェッショナルなビジネスシーン向けアバター",
                category=TemplateCategory.BUSINESS,
                style="professional",
                config={
                    "age": "35-45",
                    "gender": "neutral",
                    "expression": "confident",
                    "clothing": "business_suit"
                },
                tags=["business", "professional", "corporate", "executive"]
            ),
            AvatarTemplate(
                template_id="business_casual",
                name="ビジネスカジュアル",
                description="柔軟なビジネス環境向けアバター",
                category=TemplateCategory.BUSINESS,
                style="professional",
                config={
                    "age": "25-35",
                    "gender": "neutral",
                    "expression": "friendly",
                    "clothing": "smart_casual"
                },
                tags=["business", "casual", "professional", "modern"]
            ),
            AvatarTemplate(
                template_id="business_consultant",
                name="ビジネスコンサルタント",
                description="戦略立案・アドバイスの専門家向け",
                category=TemplateCategory.BUSINESS,
                style="professional",
                config={
                    "age": "40-55",
                    "gender": "neutral",
                    "expression": "analytical",
                    "clothing": "business_formal"
                },
                tags=["business", "consultant", "strategic", "advisor"]
            ),
            AvatarTemplate(
                template_id="business_sales",
                name="営業担当",
                description="顧客対応・セールス向けアバター",
                category=TemplateCategory.BUSINESS,
                style="professional",
                config={
                    "age": "28-42",
                    "gender": "neutral",
                    "expression": "persuasive",
                    "clothing": "business_smart"
                },
                tags=["business", "sales", "customer", "persuasive"]
            ),
            AvatarTemplate(
                template_id="business_tech",
                name="テクノロジー専門家",
                description="IT・技術説明向けアバター",
                category=TemplateCategory.BUSINESS,
                style="professional",
                config={
                    "age": "30-45",
                    "gender": "neutral",
                    "expression": "technical",
                    "clothing": "tech_casual"
                },
                tags=["business", "technology", "technical", "innovation"]
            ),

            # カジュアルカテゴリ - 拡張
            AvatarTemplate(
                template_id="casual_young",
                name="カジュアル若者",
                description="日常の友人・家族向けアバター",
                category=TemplateCategory.CASUAL,
                style="casual",
                config={
                    "age": "18-25",
                    "gender": "neutral",
                    "expression": "happy",
                    "clothing": "casual"
                },
                tags=["casual", "young", "friendly", "everyday"]
            ),
            AvatarTemplate(
                template_id="casual_creative",
                name="クリエイティブカジュアル",
                description="アーティストやクリエイター向けアバター",
                category=TemplateCategory.CASUAL,
                style="casual",
                config={
                    "age": "20-35",
                    "gender": "neutral",
                    "expression": "creative",
                    "clothing": "artistic"
                },
                tags=["creative", "artistic", "casual", "young"]
            ),
            AvatarTemplate(
                template_id="casual_friends",
                name="友人・仲間",
                description="友人との会話向けリラックスしたアバター",
                category=TemplateCategory.CASUAL,
                style="casual",
                config={
                    "age": "22-35",
                    "gender": "neutral",
                    "expression": "relaxed",
                    "clothing": "casual_comfortable"
                },
                tags=["casual", "friends", "relaxed", "social"]
            ),
            AvatarTemplate(
                template_id="casual_traveler",
                name="旅行者",
                description="旅行・冒険向け明るいアバター",
                category=TemplateCategory.CASUAL,
                style="casual",
                config={
                    "age": "25-40",
                    "gender": "neutral",
                    "expression": "adventurous",
                    "clothing": "travel_casual"
                },
                tags=["casual", "travel", "adventure", "outdoor"]
            ),
            AvatarTemplate(
                template_id="casual_gamer",
                name="ゲーマー",
                description="ゲーム・エンタメ向けカジュアルアバター",
                category=TemplateCategory.CASUAL,
                style="casual",
                config={
                    "age": "16-30",
                    "gender": "neutral",
                    "expression": "excited",
                    "clothing": "gamer_casual"
                },
                tags=["casual", "gaming", "entertainment", "youth"]
            ),

            # 教育カテゴリ - 拡張
            AvatarTemplate(
                template_id="education_teacher",
                name="教育者",
                description="教師や講師向けプロフェッショナルアバター",
                category=TemplateCategory.EDUCATION,
                style="professional",
                config={
                    "age": "30-50",
                    "gender": "neutral",
                    "expression": "wise",
                    "clothing": "educational"
                },
                tags=["education", "teacher", "professional", "wise"]
            ),
            AvatarTemplate(
                template_id="education_student",
                name="学生",
                description="学習者向けフレンドリーなアバター",
                category=TemplateCategory.EDUCATION,
                style="casual",
                config={
                    "age": "18-25",
                    "gender": "neutral",
                    "expression": "curious",
                    "clothing": "student"
                },
                tags=["education", "student", "learning", "curious"]
            ),
            AvatarTemplate(
                template_id="education_researcher",
                name="研究者",
                description="学術研究・発表向けアバター",
                category=TemplateCategory.EDUCATION,
                style="professional",
                config={
                    "age": "35-55",
                    "gender": "neutral",
                    "expression": "intellectual",
                    "clothing": "academic"
                },
                tags=["education", "research", "academic", "intellectual"]
            ),
            AvatarTemplate(
                template_id="education_trainer",
                name="トレーナー",
                description="スキル研修・トレーニング向け",
                category=TemplateCategory.EDUCATION,
                style="professional",
                config={
                    "age": "35-50",
                    "gender": "neutral",
                    "expression": "supportive",
                    "clothing": "trainer"
                },
                tags=["education", "training", "skill", "supportive"]
            ),
            AvatarTemplate(
                template_id="education_motivator",
                name="モチベーター",
                description="モチベーション向上・コーチング向け",
                category=TemplateCategory.EDUCATION,
                style="energetic",
                config={
                    "age": "30-45",
                    "gender": "neutral",
                    "expression": "motivating",
                    "clothing": "motivational"
                },
                tags=["education", "motivation", "coaching", "energetic"]
            ),

            # エンターテイメントカテゴリ - 拡張
            AvatarTemplate(
                template_id="entertainment_host",
                name="番組司会者",
                description="エンターテイメント番組向けアバター",
                category=TemplateCategory.ENTERTAINMENT,
                style="entertainment",
                config={
                    "age": "25-40",
                    "gender": "neutral",
                    "expression": "energetic",
                    "clothing": "show_host"
                },
                tags=["entertainment", "host", "energetic", "show"]
            ),
            AvatarTemplate(
                template_id="entertainment_artist",
                name="アーティスト",
                description="ミュージシャンやパフォーマー向けアバター",
                category=TemplateCategory.ENTERTAINMENT,
                style="creative",
                config={
                    "age": "20-35",
                    "gender": "neutral",
                    "expression": "artistic",
                    "clothing": "performance"
                },
                tags=["entertainment", "artist", "performance", "creative"]
            ),
            AvatarTemplate(
                template_id="entertainment_comedian",
                name="コメディアン",
                description="コメディ・ユーモア向けアバター",
                category=TemplateCategory.ENTERTAINMENT,
                style="entertainment",
                config={
                    "age": "25-45",
                    "gender": "neutral",
                    "expression": "humorous",
                    "clothing": "comedy"
                },
                tags=["entertainment", "comedy", "humor", "funny"]
            ),
            AvatarTemplate(
                template_id="entertainment_storyteller",
                name="語り部",
                description="物語・ストーリーテリング向け",
                category=TemplateCategory.ENTERTAINMENT,
                style="narrative",
                config={
                    "age": "35-60",
                    "gender": "neutral",
                    "expression": "engaging",
                    "clothing": "storyteller"
                },
                tags=["entertainment", "storytelling", "narrative", "engaging"]
            ),
            AvatarTemplate(
                template_id="entertainment_interviewer",
                name="インタビュアー",
                description="インタビュー・対談向けアバター",
                category=TemplateCategory.ENTERTAINMENT,
                style="professional",
                config={
                    "age": "30-50",
                    "gender": "neutral",
                    "expression": "interested",
                    "clothing": "interviewer"
                },
                tags=["entertainment", "interview", "conversation", "interested"]
            ),

            # コーポレートカテゴリ - 拡張
            AvatarTemplate(
                template_id="corporate_ceo",
                name="CEO/経営者",
                description="経営層向け威厳あるアバター",
                category=TemplateCategory.CORPORATE,
                style="corporate",
                config={
                    "age": "45-60",
                    "gender": "neutral",
                    "expression": "authoritative",
                    "clothing": "executive"
                },
                tags=["corporate", "ceo", "executive", "authoritative"]
            ),
            AvatarTemplate(
                template_id="corporate_team",
                name="チームメンバー",
                description="企業チーム向け協調性のあるアバター",
                category=TemplateCategory.CORPORATE,
                style="corporate",
                config={
                    "age": "25-40",
                    "gender": "neutral",
                    "expression": "collaborative",
                    "clothing": "team_uniform"
                },
                tags=["corporate", "team", "collaborative", "professional"]
            ),
            AvatarTemplate(
                template_id="corporate_hr",
                name="人事担当",
                description="採用・人材育成向けアバター",
                category=TemplateCategory.CORPORATE,
                style="corporate",
                config={
                    "age": "30-45",
                    "gender": "neutral",
                    "expression": "approachable",
                    "clothing": "hr_professional"
                },
                tags=["corporate", "hr", "recruitment", "approachable"]
            ),
            AvatarTemplate(
                template_id="corporate_marketing",
                name="マーケティング",
                description="ブランド・マーケティング向け",
                category=TemplateCategory.CORPORATE,
                style="corporate",
                config={
                    "age": "28-42",
                    "gender": "neutral",
                    "expression": "creative",
                    "clothing": "marketing"
                },
                tags=["corporate", "marketing", "brand", "creative"]
            ),
            AvatarTemplate(
                template_id="corporate_support",
                name="カスタマーサポート",
                description="顧客対応・サポート向け",
                category=TemplateCategory.CORPORATE,
                style="corporate",
                config={
                    "age": "25-40",
                    "gender": "neutral",
                    "expression": "helpful",
                    "clothing": "support"
                },
                tags=["corporate", "support", "customer", "helpful"]
            ),

            # パーソナルカテゴリ - 新規追加
            AvatarTemplate(
                template_id="personal_family",
                name="家族向け",
                description="家族との会話向け温かいアバター",
                category=TemplateCategory.PERSONAL,
                style="warm",
                config={
                    "age": "30-50",
                    "gender": "neutral",
                    "expression": "loving",
                    "clothing": "casual_home"
                },
                tags=["personal", "family", "warm", "loving"]
            ),
            AvatarTemplate(
                template_id="personal_mentor",
                name="メンター",
                description="指導・アドバイス向けアバター",
                category=TemplateCategory.PERSONAL,
                style="wise",
                config={
                    "age": "45-65",
                    "gender": "neutral",
                    "expression": "guiding",
                    "clothing": "mentor_casual"
                },
                tags=["personal", "mentor", "guidance", "wise"]
            ),
            AvatarTemplate(
                template_id="personal_therapist",
                name="セラピスト",
                description="カウンセリング・療法向け穏やかなアバター",
                category=TemplateCategory.PERSONAL,
                style="calm",
                config={
                    "age": "35-55",
                    "gender": "neutral",
                    "expression": "empathetic",
                    "clothing": "therapist"
                },
                tags=["personal", "therapy", "calm", "empathetic"]
            ),
            AvatarTemplate(
                template_id="personal_coach",
                name="ライフコーチ",
                description="人生相談・コーチング向けアバター",
                category=TemplateCategory.PERSONAL,
                style="motivational",
                config={
                    "age": "35-50",
                    "gender": "neutral",
                    "expression": "encouraging",
                    "clothing": "coach_casual"
                },
                tags=["personal", "coaching", "motivational", "encouraging"]
            ),
            AvatarTemplate(
                template_id="personal_friend",
                name="親友",
                description="親友のような気さくなアバター",
                category=TemplateCategory.PERSONAL,
                style="friendly",
                config={
                    "age": "25-40",
                    "gender": "neutral",
                    "expression": "friendly",
                    "clothing": "friend_casual"
                },
                tags=["personal", "friend", "casual", "friendly"]
            ),

            # 医療・ヘルスケアカテゴリ - 新規追加
            AvatarTemplate(
                template_id="healthcare_doctor",
                name="医師",
                description="医療相談・診断向けプロフェッショナルアバター",
                category="healthcare",
                style="professional",
                config={
                    "age": "35-55",
                    "gender": "neutral",
                    "expression": "trustworthy",
                    "clothing": "medical"
                },
                tags=["healthcare", "doctor", "medical", "trustworthy"]
            ),
            AvatarTemplate(
                template_id="healthcare_nurse",
                name="看護師",
                description="ケア・健康管理向け優しいアバター",
                category="healthcare",
                style="caring",
                config={
                    "age": "25-45",
                    "gender": "neutral",
                    "expression": "caring",
                    "clothing": "nursing"
                },
                tags=["healthcare", "nurse", "caring", "compassionate"]
            ),
            AvatarTemplate(
                template_id="healthcare_therapist",
                name="理学療法士",
                description="リハビリ・運動指導向けアバター",
                category="healthcare",
                style="supportive",
                config={
                    "age": "30-50",
                    "gender": "neutral",
                    "expression": "encouraging",
                    "clothing": "therapy"
                },
                tags=["healthcare", "therapy", "rehabilitation", "supportive"]
            ),
            AvatarTemplate(
                template_id="healthcare_nutritionist",
                name="栄養士",
                description="栄養・食事指導向けアバター",
                category="healthcare",
                style="informative",
                config={
                    "age": "30-48",
                    "gender": "neutral",
                    "expression": "knowledgeable",
                    "clothing": "nutritionist"
                },
                tags=["healthcare", "nutrition", "diet", "knowledgeable"]
            ),

            # フィットネス・スポーツカテゴリ - 新規追加
            AvatarTemplate(
                template_id="fitness_trainer",
                name="フィットネストレーナー",
                description="トレーニング指導向けエネルギッシュなアバター",
                category="fitness",
                style="energetic",
                config={
                    "age": "25-40",
                    "gender": "neutral",
                    "expression": "motivating",
                    "clothing": "fitness"
                },
                tags=["fitness", "trainer", "motivation", "energetic"]
            ),
            AvatarTemplate(
                template_id="fitness_yoga",
                name="ヨガインストラクター",
                description="ヨガ・瞑想指導向け穏やかなアバター",
                category="fitness",
                style="calm",
                config={
                    "age": "30-50",
                    "gender": "neutral",
                    "expression": "peaceful",
                    "clothing": "yoga"
                },
                tags=["fitness", "yoga", "meditation", "calm"]
            ),

            # テクノロジーカテゴリ - 新規追加
            AvatarTemplate(
                template_id="tech_expert",
                name="テクノロジーエキスパート",
                description="技術解説・デモ向けアバター",
                category="technology",
                style="technical",
                config={
                    "age": "28-45",
                    "gender": "neutral",
                    "expression": "expert",
                    "clothing": "tech"
                },
                tags=["technology", "expert", "technical", "innovation"]
            ),
            AvatarTemplate(
                template_id="tech_gamer",
                name="ゲーム実況者",
                description="ゲーム実況・レビュー向けアバター",
                category="technology",
                style="entertainment",
                config={
                    "age": "20-35",
                    "gender": "neutral",
                    "expression": "excited",
                    "clothing": "gamer"
                },
                tags=["technology", "gaming", "entertainment", "excited"]
            ),

            # 国際・多文化カテゴリ - 新規追加
            AvatarTemplate(
                template_id="international_translator",
                name="翻訳者",
                description="多言語対応・翻訳向けアバター",
                category="international",
                style="professional",
                config={
                    "age": "30-50",
                    "gender": "neutral",
                    "expression": "clear",
                    "clothing": "translator"
                },
                tags=["international", "translator", "multilingual", "clear"]
            ),
            AvatarTemplate(
                template_id="international_cultural",
                name="文化案内人",
                description="文化紹介・国際交流向けアバター",
                category="international",
                style="welcoming",
                config={
                    "age": "35-55",
                    "gender": "neutral",
                    "expression": "welcoming",
                    "clothing": "cultural"
                },
                tags=["international", "cultural", "welcoming", "inclusive"]
            ),

            # 50個以上のアバターを追加（簡略化のため一部省略）
            # 実際にはさらに多くのバリエーションを追加可能
        ]

        for template in default_templates:
            await self.save_avatar_template(template)

    async def create_default_video_templates(self):
        """デフォルトの動画テンプレートを作成"""
        default_templates = [
            # プレゼンテーション
            VideoTemplate(
                template_id="presentation_business",
                name="ビジネスプレゼンテーション",
                description="プロフェッショナルなビジネスプレゼンテーション動画",
                category=TemplateCategory.PRESENTATION,
                script_template="""皆様、こんにちは。私は[会社名]の[役職]です。本日は[トピック]についてお話しします。

まず、[概要]についてご説明いたします。

[主要ポイント1]について詳しくお話ししましょう。

次に、[主要ポイント2]についてです。

最後に、[結論]をお伝えいたします。

ご清聴ありがとうございました。""",
                avatar_config={
                    "style": "professional",
                    "expression": "confident",
                    "clothing": "business_suit"
                },
                video_settings={
                    "resolution": "1080p",
                    "fps": 30,
                    "background": "office"
                },
                tags=["presentation", "business", "professional"]
            ),

            # チュートリアル
            VideoTemplate(
                template_id="tutorial_software",
                name="ソフトウェアチュートリアル",
                description="ソフトウェアの使い方を説明するチュートリアル動画",
                category=TemplateCategory.TUTORIAL,
                script_template="""こんにちは！今日は[ソフトウェア名]の使い方をご紹介します。

まず、基本的な操作から始めましょう。

ステップ1: [操作1]を行います。

ステップ2: [操作2]を実行してください。

ステップ3: [操作3]を完了させます。

これで基本的な使い方が分かりましたね。

より詳細な機能については、[追加情報]をご覧ください。""",
                avatar_config={
                    "style": "casual",
                    "expression": "helpful",
                    "clothing": "casual"
                },
                video_settings={
                    "resolution": "720p",
                    "fps": 30,
                    "background": "clean"
                },
                tags=["tutorial", "software", "educational"]
            ),

            # マーケティング
            VideoTemplate(
                template_id="marketing_product",
                name="製品紹介",
                description="新製品を紹介するマーケティング動画",
                category=TemplateCategory.MARKETING,
                script_template="""こんにちは！今日は素晴らしい新製品をご紹介します。

[製品名]は[製品の特徴]を備えた革新的な製品です。

主なメリット:
• [メリット1]
• [メリット2]
• [メリット3]

[使用例]のようにお使いいただけます。

今すぐ[製品名]を手に入れて、[ベネフィット]を体験してください！

詳細は[ウェブサイト]をご覧ください。""",
                avatar_config={
                    "style": "energetic",
                    "expression": "enthusiastic",
                    "clothing": "modern"
                },
                video_settings={
                    "resolution": "1080p",
                    "fps": 30,
                    "background": "dynamic"
                },
                tags=["marketing", "product", "sales"]
            ),

            # トレーニング
            VideoTemplate(
                template_id="training_safety",
                name="安全トレーニング",
                description="職場安全に関するトレーニング動画",
                category=TemplateCategory.TRAINING,
                script_template="""安全第一で業務を行っていくことが重要です。

本日のトレーニング内容:
1. [安全ルール1]
2. [安全ルール2]
3. [安全ルール3]

具体的な手順:
• 準備段階: [準備手順]
• 実行段階: [実行手順]
• 完了段階: [完了手順]

安全を守ることで、皆さんの安全と生産性の向上を図れます。

質問があれば、いつでもお尋ねください。""",
                avatar_config={
                    "style": "professional",
                    "expression": "serious",
                    "clothing": "safety_uniform"
                },
                video_settings={
                    "resolution": "1080p",
                    "fps": 30,
                    "background": "industrial"
                },
                tags=["training", "safety", "corporate"]
            ),

            # アナウンス
            VideoTemplate(
                template_id="announcement_company",
                name="企業アナウンス",
                description="重要な企業情報を伝えるアナウンス動画",
                category=TemplateCategory.ANNOUNCEMENT,
                script_template="""[会社名]より重要なお知らせです。

[日付]付で、以下の内容についてお知らせいたします。

[アナウンス内容の概要]

詳細は以下の通りです:
• [詳細1]
• [詳細2]
• [詳細3]

この変更により、[影響]が予想されます。

ご質問やご不明点があれば、[連絡先]までお問い合わせください。

よろしくお願いいたします。""",
                avatar_config={
                    "style": "corporate",
                    "expression": "formal",
                    "clothing": "corporate"
                },
                video_settings={
                    "resolution": "1080p",
                    "fps": 30,
                    "background": "corporate"
                },
                tags=["announcement", "corporate", "formal"]
            ),

            # ストーリーテリング
            VideoTemplate(
                template_id="storytelling_brand",
                name="ブランドストーリー",
                description="ブランドの物語を伝えるストーリーテリング動画",
                category=TemplateCategory.STORYTELLING,
                script_template="""かつて、[背景設定]がありました。

そこに[主人公/ブランド]が現れました。

[挑戦/問題]に直面した時、[解決策]を見つけ出しました。

その結果、[成果/変化]が生まれました。

今、[ブランド/製品]は[現在の状況]です。

私たちの物語は、これからも続きます。

あなたの物語も、ぜひ私たちと一緒に。""",
                avatar_config={
                    "style": "narrative",
                    "expression": "emotional",
                    "clothing": "storytelling"
                },
                video_settings={
                    "resolution": "1080p",
                    "fps": 30,
                    "background": "cinematic"
                },
                tags=["storytelling", "brand", "narrative"]
            )
        ]

        for template in default_templates:
            await self.save_video_template(template)

    async def save_avatar_template(self, template: AvatarTemplate):
        """アバターテンプレートを保存"""
        self.avatar_templates[template.template_id] = template

        template_file = self.avatar_templates_dir / f"{sanitize_template_id(template.template_id)}.json"
        try:
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "template_id": template.template_id,
                    "name": template.name,
                    "description": template.description,
                    "category": template.category,
                    "style": template.style,
                    "thumbnail_path": template.thumbnail_path,
                    "config": template.config,
                    "tags": template.tags,
                    "is_premium": template.is_premium,
                    "created_at": template.created_at.isoformat(),
                    "usage_count": template.usage_count
                }, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved avatar template: {template.template_id}")

        except Exception as e:
            logger.error(f"Failed to save avatar template {template.template_id}: {e}")

    async def save_video_template(self, template: VideoTemplate):
        """動画テンプレートを保存"""
        self.video_templates[template.template_id] = template

        template_file = self.video_templates_dir / f"{sanitize_template_id(template.template_id)}.json"
        try:
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "template_id": template.template_id,
                    "name": template.name,
                    "description": template.description,
                    "category": template.category,
                    "script_template": template.script_template,
                    "avatar_config": template.avatar_config,
                    "video_settings": template.video_settings,
                    "background_music": template.background_music,
                    "thumbnail_path": template.thumbnail_path,
                    "tags": template.tags,
                    "is_premium": template.is_premium,
                    "created_at": template.created_at.isoformat(),
                    "usage_count": template.usage_count
                }, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved video template: {template.template_id}")

        except Exception as e:
            logger.error(f"Failed to save video template {template.template_id}: {e}")

    def get_avatar_templates(self, category: Optional[str] = None,
                           tags: Optional[List[str]] = None,
                           premium_only: bool = False) -> List[AvatarTemplate]:
        """アバターテンプレートを取得"""
        templates = list(self.avatar_templates.values())

        if category:
            templates = [t for t in templates if t.category == category]

        if tags:
            templates = [t for t in templates if any(tag in t.tags for tag in tags)]

        if premium_only:
            templates = [t for t in templates if t.is_premium]

        return sorted(templates, key=lambda x: x.usage_count, reverse=True)

    def get_video_templates(self, category: Optional[str] = None,
                          tags: Optional[List[str]] = None,
                          premium_only: bool = False) -> List[VideoTemplate]:
        """動画テンプレートを取得"""
        templates = list(self.video_templates.values())

        if category:
            templates = [t for t in templates if t.category == category]

        if tags:
            templates = [t for t in templates if any(tag in t.tags for tag in tags)]

        if premium_only:
            templates = [t for t in templates if t.is_premium]

        return sorted(templates, key=lambda x: x.usage_count, reverse=True)

    def get_avatar_categories(self) -> Dict[str, str]:
        """アバターカテゴリを取得"""
        return self.avatar_categories

    def get_video_categories(self) -> Dict[str, str]:
        """動画カテゴリを取得"""
        return self.video_categories

    async def increment_usage(self, template_id: str, template_type: str = "avatar"):
        """テンプレートの使用回数を増やす"""
        if template_type == "avatar" and template_id in self.avatar_templates:
            self.avatar_templates[template_id].usage_count += 1
            await self.save_avatar_template(self.avatar_templates[template_id])
        elif template_type == "video" and template_id in self.video_templates:
            self.video_templates[template_id].usage_count += 1
            await self.save_video_template(self.video_templates[template_id])

    async def create_custom_template(self, base_template_id: str,
                                   customizations: Dict,
                                   template_type: str = "avatar") -> Optional[Union[AvatarTemplate, VideoTemplate]]:
        """カスタムテンプレートを作成"""
        if template_type == "avatar":
            base_template = self.avatar_templates.get(base_template_id)
            if not base_template:
                return None

            # カスタマイズを適用
            custom_config = base_template.config.copy()
            custom_config.update(customizations.get("config", {}))

            custom_template = AvatarTemplate(
                template_id=f"custom_{base_template_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                name=customizations.get("name", f"{base_template.name} (カスタム)"),
                description=customizations.get("description", base_template.description),
                category=customizations.get("category", base_template.category),
                style=customizations.get("style", base_template.style),
                config=custom_config,
                tags=customizations.get("tags", base_template.tags.copy()),
                is_premium=False
            )

            await self.save_avatar_template(custom_template)
            return custom_template

        if template_type == "video":
            base_template = self.video_templates.get(base_template_id)
            if not base_template:
                return None

            # カスタマイズを適用
            custom_avatar_config = base_template.avatar_config.copy()
            custom_avatar_config.update(customizations.get("avatar_config", {}))

            custom_video_settings = base_template.video_settings.copy()
            custom_video_settings.update(customizations.get("video_settings", {}))

            custom_template = VideoTemplate(
                template_id=f"custom_{base_template_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                name=customizations.get("name", f"{base_template.name} (カスタム)"),
                description=customizations.get("description", base_template.description),
                category=customizations.get("category", base_template.category),
                script_template=customizations.get("script_template", base_template.script_template),
                avatar_config=custom_avatar_config,
                video_settings=custom_video_settings,
                background_music=customizations.get("background_music", base_template.background_music),
                tags=customizations.get("tags", base_template.tags.copy()),
                is_premium=False
            )

            await self.save_video_template(custom_template)
            return custom_template

        return None

    async def delete_template(self, template_id: str, template_type: str = "avatar") -> bool:
        """テンプレートを削除"""
        if template_type == "avatar" and template_id in self.avatar_templates:
            template = self.avatar_templates[template_id]

            # ファイル削除
            template_file = self.avatar_templates_dir / f"{sanitize_template_id(template_id)}.json"
            if template_file.exists():
                template_file.unlink()

            # サムネイル削除
            if template.thumbnail_path and Path(template.thumbnail_path).exists():
                Path(template.thumbnail_path).unlink()

            del self.avatar_templates[template_id]
            logger.info(f"Deleted avatar template: {template_id}")
            return True

        if template_type == "video" and template_id in self.video_templates:
            template = self.video_templates[template_id]

            # ファイル削除
            template_file = self.video_templates_dir / f"{sanitize_template_id(template_id)}.json"
            if template_file.exists():
                template_file.unlink()

            # サムネイル削除
            if template.thumbnail_path and Path(template.thumbnail_path).exists():
                Path(template.thumbnail_path).unlink()

            del self.video_templates[template_id]
            logger.info(f"Deleted video template: {template_id}")
            return True

        return False

    def search_templates(self, query: str, template_type: str = "avatar") -> List[Union[AvatarTemplate, VideoTemplate]]:
        """テンプレートを検索"""
        query_lower = query.lower()

        if template_type == "avatar":
            templates = list(self.avatar_templates.values())
        else:
            templates = list(self.video_templates.values())

        results = []
        for template in templates:
            # 名前、説明、タグで検索
            searchable_text = f"{template.name} {template.description} {' '.join(template.tags)}".lower()

            if query_lower in searchable_text:
                results.append(template)

        return sorted(results, key=lambda x: x.usage_count, reverse=True)

# グローバルインスタンス管理
_template_library = None

async def get_template_library() -> TemplateLibrary:
    """テンプレートライブラリのインスタンスを取得"""
    global _template_library

    if _template_library is None:
        _template_library = TemplateLibrary()
        await _template_library.initialize()

    return _template_library
