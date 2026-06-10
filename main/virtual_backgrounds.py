# main/virtual_backgrounds.py
"""
Virtual Backgrounds Module for Cocoa
仮想背景統合システム
"""

import logging
import json
import shutil
from pathlib import Path

try:
    import aiofiles
    AIOFILES_AVAILABLE = True
except ImportError:
    aiofiles = None
    AIOFILES_AVAILABLE = False
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timezone
try:
    from PIL import Image, ImageEnhance, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    ImageEnhance = None
    ImageFilter = None

from integrated_security import get_security_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class BackgroundTemplate:
    """背景テンプレート"""
    template_id: str
    name: str
    description: str
    category: str  # 'office', 'studio', 'outdoor', 'abstract', 'brand'
    image_path: str
    thumbnail_path: Optional[str] = None
    tags: List[str] = None
    is_premium: bool = False
    settings: Dict[str, Any] = None
    created_at: datetime = None
    usage_count: int = 0

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.settings is None:
            self.settings = {}
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

@dataclass
class BackgroundConfig:
    """背景設定"""
    background_id: str
    template_id: Optional[str] = None
    custom_image_path: Optional[str] = None
    overlay_settings: Dict[str, Any] = None
    effects: List[Dict[str, Any]] = None
    branding: Dict[str, Any] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.overlay_settings is None:
            self.overlay_settings = {}
        if self.effects is None:
            self.effects = []
        if self.branding is None:
            self.branding = {}
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

class BackgroundProcessor:
    """
    背景処理クラス
    画像処理と背景適用を行う
    """

    def __init__(self):
        self.supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
        self.max_image_size = (4096, 4096)  # 最大画像サイズ
        self.thumbnail_size = (300, 200)

    async def apply_background(self, foreground_image: "Any",
                             background_config: BackgroundConfig,
                             output_size: Tuple[int, int] = (1920, 1080)) -> "Any":
        """
        背景を適用

        Args:
            foreground_image: 前景画像（アバターなど）
            background_config: 背景設定
            output_size: 出力サイズ

        Returns:
            背景適用後の画像
        """
        try:
            # 背景画像取得
            background_image = await self._load_background_image(background_config)

            # 背景画像をリサイズ
            background_image = background_image.resize(output_size, Image.LANCZOS)

            # 前景画像のリサイズと位置調整
            foreground_image = self._fit_foreground(foreground_image, output_size)

            # 背景適用
            result_image = self._composite_images(background_image, foreground_image, background_config)

            # エフェクト適用
            result_image = await self._apply_effects(result_image, background_config.effects)

            # ブランディング適用
            result_image = await self._apply_branding(result_image, background_config.branding)

            return result_image

        except Exception as e:
            logger.error(f"Background application failed: {e}")
            raise

    async def _load_background_image(self, config: BackgroundConfig) -> "Any":
        """背景画像を読み込み"""
        if config.template_id:
            # テンプレートから読み込み
            template_path = Path("data/backgrounds/templates") / f"{config.template_id}.png"
            if template_path.exists():
                return Image.open(template_path).convert('RGB')

        if config.custom_image_path and Path(config.custom_image_path).exists():
            # カスタム画像から読み込み
            return Image.open(config.custom_image_path).convert('RGB')

        # デフォルト背景
        return self._create_default_background()

    def _create_default_background(self) -> "Any":
        """デフォルト背景を作成"""
        # グラデーション背景
        width, height = 1920, 1080
        image = Image.new('RGB', (width, height), '#f0f0f0')

        # シンプルなグラデーション
        for y in range(height):
            r = int(240 + (255 - 240) * (y / height))
            g = int(240 + (255 - 240) * (y / height))
            b = int(240 + (255 - 240) * (y / height))
            for x in range(width):
                image.putpixel((x, y), (r, g, b))

        return image

    def _fit_foreground(self, foreground: "Any", output_size: Tuple[int, int]) -> "Any":
        """前景画像をフィット"""
        # アバター画像の場合、適切なサイズにリサイズ
        fg_width, fg_height = foreground.size
        out_width, out_height = output_size

        # アバターは画面の1/3程度のサイズに
        max_avatar_size = min(out_width // 3, out_height // 2)

        if fg_width > fg_height:
            new_width = max_avatar_size
            new_height = int(fg_height * max_avatar_size / fg_width)
        else:
            new_height = max_avatar_size
            new_width = int(fg_width * max_avatar_size / fg_height)

        return foreground.resize((new_width, new_height), Image.LANCZOS)

    def _composite_images(self, background: "Any", foreground: "Any",
                         config: BackgroundConfig) -> "Any":
        """画像を合成"""
        # 新しい画像作成
        result = background.copy()

        # 前景の位置設定
        bg_width, bg_height = background.size
        fg_width, fg_height = foreground.size

        # オーバーレイ設定に基づく位置調整
        overlay_settings = config.overlay_settings
        position_x = overlay_settings.get('position_x', 'center')
        position_y = overlay_settings.get('position_y', 'bottom')

        if position_x == 'left':
            x = 50
        elif position_x == 'right':
            x = bg_width - fg_width - 50
        else:  # center
            x = (bg_width - fg_width) // 2

        if position_y == 'top':
            y = 50
        elif position_y == 'center':
            y = (bg_height - fg_height) // 2
        else:  # bottom
            y = bg_height - fg_height - 50

        # 合成
        if foreground.mode == 'RGBA':
            # アルファチャンネル対応
            result.paste(foreground, (x, y), foreground)
        else:
            result.paste(foreground, (x, y))

        return result

    async def _apply_effects(self, image: "Any", effects: List[Dict[str, Any]]) -> "Any":
        """エフェクトを適用"""
        result = image.copy()

        for effect in effects:
            effect_type = effect.get('type')

            if effect_type == 'blur':
                radius = effect.get('radius', 2)
                result = result.filter(ImageFilter.GaussianBlur(radius))

            elif effect_type == 'brightness':
                factor = effect.get('factor', 1.0)
                enhancer = ImageEnhance.Brightness(result)
                result = enhancer.enhance(factor)

            elif effect_type == 'contrast':
                factor = effect.get('factor', 1.0)
                enhancer = ImageEnhance.Contrast(result)
                result = enhancer.enhance(factor)

            elif effect_type == 'saturation':
                factor = effect.get('factor', 1.0)
                enhancer = ImageEnhance.Color(result)
                result = enhancer.enhance(factor)

            elif effect_type == 'sharpness':
                factor = effect.get('factor', 1.0)
                enhancer = ImageEnhance.Sharpness(result)
                result = enhancer.enhance(factor)

        return result

    async def _apply_branding(self, image: "Any", branding: Dict[str, Any]) -> "Any":
        """ブランディングを適用"""
        result = image.copy()

        # ロゴ追加
        logo_path = branding.get('logo_path')
        if logo_path and Path(logo_path).exists():
            logo = Image.open(logo_path).convert('RGBA')

            # ロゴサイズ調整
            logo_width = branding.get('logo_width', 200)
            logo.thumbnail((logo_width, logo_width), Image.LANCZOS)

            # ロゴ位置
            position = branding.get('logo_position', 'top_right')
            bg_width, bg_height = result.size
            logo_w, logo_h = logo.size

            if position == 'top_left':
                x, y = 20, 20
            elif position == 'top_right':
                x, y = bg_width - logo_w - 20, 20
            elif position == 'bottom_left':
                x, y = 20, bg_height - logo_h - 20
            elif position == 'bottom_right':
                x, y = bg_width - logo_w - 20, bg_height - logo_h - 20
            else:
                x, y = bg_width - logo_w - 20, 20

            # ロゴ合成
            if result.mode != 'RGBA':
                result = result.convert('RGBA')
            result.paste(logo, (x, y), logo)

        # テキスト追加
        text_overlay = branding.get('text_overlay')
        if text_overlay:
            from PIL import ImageDraw, ImageFont

            draw = ImageDraw.Draw(result)

            # フォント設定
            try:
                font_path = branding.get('font_path', "arial.ttf")
                font_size = branding.get('font_size', 48)
                font = ImageFont.truetype(font_path, font_size)
            except (OSError, IOError) as e:
                logger.debug(f"Failed to load font {branding.get('font_path')}: {e}")
                font = ImageFont.load_default()

            # テキスト設定
            text = text_overlay.get('text', '')
            text_color = text_overlay.get('color', '#FFFFFF')
            text_position = text_overlay.get('position', 'bottom_center')

            # テキストサイズ取得
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # 位置設定
            bg_width, bg_height = result.size

            if text_position == 'top_center':
                x, y = (bg_width - text_width) // 2, 20
            elif text_position == 'bottom_center':
                x, y = (bg_width - text_width) // 2, bg_height - text_height - 20
            elif text_position == 'center':
                x, y = (bg_width - text_width) // 2, (bg_height - text_height) // 2
            else:
                x, y = 20, bg_height - text_height - 20

            # テキスト描画（影付き）
            shadow_offset = text_overlay.get('shadow_offset', 2)
            if shadow_offset > 0:
                draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill='#000000')

            draw.text((x, y), text, font=font, fill=text_color)

        return result

class VirtualBackgroundsService:
    """
    仮想背景サービス
    背景テンプレートの管理と適用
    """

    def __init__(self):
        self.security_manager = get_security_manager()
        self.processor = BackgroundProcessor()

        # ディレクトリ設定
        self.templates_dir = Path("data/backgrounds/templates")
        self.thumbnails_dir = Path("data/backgrounds/thumbnails")
        self.custom_dir = Path("data/backgrounds/custom")

        # テンプレートストレージ
        self.templates: Dict[str, BackgroundTemplate] = {}

        logger.info("Virtual Backgrounds Service initialized")

    async def initialize(self):
        """初期化"""
        # ディレクトリ作成
        for dir_path in [self.templates_dir, self.thumbnails_dir, self.custom_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # デフォルトテンプレート読み込み
        await self.load_templates()

        # デフォルトテンプレートが存在しない場合は作成
        if not self.templates:
            await self.create_default_templates()

    async def load_templates(self):
        """テンプレートを読み込み"""
        metadata_file = Path("data/backgrounds/templates_metadata.json")

        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    templates_data = json.load(f)

                for template_data in templates_data:
                    template = BackgroundTemplate(**template_data)
                    self.templates[template.template_id] = template

                logger.info(f"Loaded {len(self.templates)} background templates")

            except Exception as e:
                logger.error(f"Failed to load background templates: {e}")

    async def create_default_templates(self):
        """デフォルトテンプレートを作成"""
        default_templates = [
            # オフィスカテゴリ
            BackgroundTemplate(
                template_id="office_modern",
                name="モダンオフィス",
                description="クリーンでモダンなオフィス環境",
                category="office",
                image_path="",
                tags=["office", "modern", "clean", "professional"],
                settings={"lighting": "bright", "style": "minimalist"}
            ),
            BackgroundTemplate(
                template_id="office_conference",
                name="会議室",
                description="プロフェッショナルな会議室環境",
                category="office",
                image_path="",
                tags=["office", "conference", "meeting", "professional"],
                settings={"lighting": "neutral", "style": "corporate"}
            ),

            # スタジオカテゴリ
            BackgroundTemplate(
                template_id="studio_green",
                name="グリーンスクリーン",
                description="クロマキー対応グリーンスクリーン",
                category="studio",
                image_path="",
                tags=["studio", "green_screen", "chroma_key", "professional"],
                settings={"color": "#00FF00", "lighting": "uniform"}
            ),
            BackgroundTemplate(
                template_id="studio_gradient",
                name="グラデーション",
                description="シンプルなグラデーション背景",
                category="studio",
                image_path="",
                tags=["studio", "gradient", "simple", "modern"],
                settings={"gradient": "blue_to_white", "lighting": "soft"}
            ),

            # 屋外カテゴリ
            BackgroundTemplate(
                template_id="outdoor_park",
                name="公園",
                description="自然な屋外環境",
                category="outdoor",
                image_path="",
                tags=["outdoor", "park", "nature", "casual"],
                settings={"weather": "sunny", "time": "day"}
            ),
            BackgroundTemplate(
                template_id="outdoor_city",
                name="都市景観",
                description="モダンな都市の風景",
                category="outdoor",
                image_path="",
                tags=["outdoor", "city", "urban", "modern"],
                settings={"time": "day", "style": "metropolitan"}
            ),

            # 抽象カテゴリ
            BackgroundTemplate(
                template_id="abstract_geometric",
                name="幾何学模様",
                description="モダンな幾何学デザイン",
                category="abstract",
                image_path="",
                tags=["abstract", "geometric", "modern", "artistic"],
                settings={"pattern": "hexagonal", "colors": ["blue", "white"]}
            ),
            BackgroundTemplate(
                template_id="abstract_blur",
                name="ぼかし背景",
                description="プロフェッショナルなぼかし効果",
                category="abstract",
                image_path="",
                tags=["abstract", "blur", "bokeh", "professional"],
                settings={"blur_radius": 5, "colors": ["gray", "blue"]}
            ),

            # ブランドカテゴリ
            BackgroundTemplate(
                template_id="brand_minimal",
                name="ミニマルブランド",
                description="ブランドロゴが際立つミニマルデザイン",
                category="brand",
                image_path="",
                tags=["brand", "minimal", "logo", "corporate"],
                settings={"logo_space": "center", "colors": "brand_colors"},
                is_premium=True
            ),
            BackgroundTemplate(
                template_id="brand_luxury",
                name="ラグジュアリーブランド",
                description="高級感のあるブランド背景",
                category="brand",
                image_path="",
                tags=["brand", "luxury", "premium", "elegant"],
                settings={"texture": "velvet", "colors": "gold_silver"},
                is_premium=True
            )
        ]

        # テンプレート画像生成
        for template in default_templates:
            try:
                # テンプレート画像を生成
                image = await self._generate_template_image(template)
                if image:
                    # 画像保存
                    image_path = self.templates_dir / f"{template.template_id}.png"
                    image.save(image_path, 'PNG')
                    template.image_path = str(image_path)

                    # サムネイル生成
                    thumbnail = image.copy()
                    thumbnail.thumbnail(self.processor.thumbnail_size)
                    thumbnail_path = self.thumbnails_dir / f"{template.template_id}_thumb.png"
                    thumbnail.save(thumbnail_path, 'PNG')
                    template.thumbnail_path = str(thumbnail_path)

                self.templates[template.template_id] = template
                await self._save_template_metadata(template)

            except Exception as e:
                logger.error(f"Failed to create template {template.template_id}: {e}")

        # メタデータを保存
        await self._save_all_templates_metadata()

    async def _generate_template_image(self, template: BackgroundTemplate) -> "Optional[Any]":
        """テンプレート画像を生成"""
        try:
            width, height = 1920, 1080

            if template.category == "office":
                if "modern" in template.template_id:
                    return self._create_modern_office_bg(width, height)
                elif "conference" in template.template_id:
                    return self._create_conference_room_bg(width, height)

            elif template.category == "studio":
                if "green" in template.template_id:
                    return self._create_green_screen_bg(width, height)
                elif "gradient" in template.template_id:
                    return self._create_gradient_bg(width, height)

            elif template.category == "outdoor":
                if "park" in template.template_id:
                    return self._create_park_bg(width, height)
                elif "city" in template.template_id:
                    return self._create_city_bg(width, height)

            elif template.category == "abstract":
                if "geometric" in template.template_id:
                    return self._create_geometric_bg(width, height)
                elif "blur" in template.template_id:
                    return self._create_blur_bg(width, height)

            elif template.category == "brand":
                if "minimal" in template.template_id:
                    return self._create_minimal_brand_bg(width, height)
                elif "luxury" in template.template_id:
                    return self._create_luxury_brand_bg(width, height)

            # デフォルト背景
            return self.processor._create_default_background()

        except Exception as e:
            logger.error(f"Template image generation failed for {template.template_id}: {e}")
            return None

    def _create_modern_office_bg(self, width: int, height: int) -> "Any":
        """モダンオフィス背景を作成"""
        image = Image.new('RGB', (width, height), '#F8F9FA')

        # シンプルなデスクとモニターのシルエットを描画
        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)

        # デスク
        desk_color = '#E9ECEF'
        draw.rectangle([width//4, height*3//4, width*3//4, height], fill=desk_color)

        # モニター
        monitor_color = '#ADB5BD'
        draw.rectangle([width//3, height//2, width*2//3, height*3//4], fill=monitor_color)

        return image

    def _create_conference_room_bg(self, width: int, height: int) -> "Any":
        """会議室背景を作成"""
        image = Image.new('RGB', (width, height), '#FFFFFF')

        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)

        # 会議テーブル
        table_color = '#6C757D'
        draw.rectangle([width//6, height*2//3, width*5//6, height*5//6], fill=table_color)

        # 椅子
        chair_color = '#495057'
        chair_positions = [
            (width//4, height*3//4),
            (width//2, height*3//4),
            (width*3//4, height*3//4)
        ]

        for x, y in chair_positions:
            draw.rectangle([x-30, y-20, x+30, y+20], fill=chair_color)

        return image

    def _create_green_screen_bg(self, width: int, height: int) -> "Any":
        """グリーンスクリーン背景を作成"""
        return Image.new('RGB', (width, height), '#00FF00')

    def _create_gradient_bg(self, width: int, height: int) -> "Any":
        """グラデーション背景を作成"""
        image = Image.new('RGB', (width, height))

        for y in range(height):
            # 青から白へのグラデーション
            r = int(135 + (255 - 135) * (y / height))
            g = int(206 + (255 - 206) * (y / height))
            b = int(235 + (255 - 235) * (y / height))

            for x in range(width):
                image.putpixel((x, y), (r, g, b))

        return image

    def _create_park_bg(self, width: int, height: int) -> "Any":
        """公園背景を作成"""
        image = Image.new('RGB', (width, height), '#90EE90')

        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)

        # 木
        tree_color = '#228B22'
        draw.rectangle([width//4, height//3, width//3, height*2//3], fill=tree_color)
        draw.rectangle([width*2//3, height//4, width*3//4, height//2], fill=tree_color)

        # 地面
        ground_color = '#8B4513'
        draw.rectangle([0, height*4//5, width, height], fill=ground_color)

        return image

    def _create_city_bg(self, width: int, height: int) -> "Any":
        """都市背景を作成"""
        image = Image.new('RGB', (width, height), '#87CEEB')

        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)

        # 建物
        building_color = '#696969'
        buildings = [
            (width//6, height//2, width//4, height),
            (width//3, height//3, width//2, height),
            (width*2//3, height//4, width*5//6, height)
        ]

        for x1, y1, x2, y2 in buildings:
            draw.rectangle([x1, y1, x2, y2], fill=building_color)

        return image

    def _create_geometric_bg(self, width: int, height: int) -> "Any":
        """幾何学背景を作成"""
        image = Image.new('RGB', (width, height), '#FFFFFF')

        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)

        # 六角形パターン
        hex_color = '#007BFF'
        hex_size = 50

        for x in range(0, width, hex_size * 3):
            for y in range(0, height, hex_size * 2):
                # 六角形を描画
                points = []
                for i in range(6):
                    px = x + hex_size * (1 + (i % 2) * 0.5)
                    py = y + hex_size * (1 + (i // 2) * 0.5)
                    points.extend([px, py])

                if len(points) >= 12:
                    draw.polygon(points[:12], fill=hex_color)

        return image

    def _create_blur_bg(self, width: int, height: int) -> "Any":
        """ぼかし背景を作成"""
        # カラフルなベース画像を作成
        base_image = Image.new('RGB', (width, height))

        # ランダムな色のパッチ
        from PIL import ImageDraw
        draw = ImageDraw.Draw(base_image)

        import random
        for _ in range(20):
            x1 = random.randint(0, width//2)
            y1 = random.randint(0, height//2)
            x2 = random.randint(x1, width)
            y2 = random.randint(y1, height)

            color = (random.randint(100, 200), random.randint(100, 200), random.randint(100, 200))
            draw.rectangle([x1, y1, x2, y2], fill=color)

        # ぼかし適用
        return base_image.filter(ImageFilter.GaussianBlur(10))

    def _create_minimal_brand_bg(self, width: int, height: int) -> "Any":
        """ミニマルブランド背景を作成"""
        return Image.new('RGB', (width, height), '#F8F9FA')

    def _create_luxury_brand_bg(self, width: int, height: int) -> "Any":
        """ラグジュアリーブランド背景を作成"""
        image = Image.new('RGB', (width, height), '#1A1A1A')

        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)

        # 金色のアクセント
        gold_color = '#FFD700'
        draw.rectangle([width//4, height//4, width*3//4, height*3//4],
                      outline=gold_color, width=5)

        return image

    async def _save_template_metadata(self, template: BackgroundTemplate):
        """テンプレートメタデータを保存"""
        metadata = {
            "template_id": template.template_id,
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "image_path": template.image_path,
            "thumbnail_path": template.thumbnail_path,
            "tags": template.tags,
            "is_premium": template.is_premium,
            "settings": template.settings,
            "created_at": template.created_at.isoformat(),
            "usage_count": template.usage_count
        }

        metadata_file = self.templates_dir / f"{template.template_id}_metadata.json"
        async with aiofiles.open(metadata_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(metadata, ensure_ascii=False, indent=2))

    async def _save_all_templates_metadata(self):
        """全テンプレートメタデータを保存"""
        templates_data = []
        for template in self.templates.values():
            templates_data.append({
                "template_id": template.template_id,
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "image_path": template.image_path,
                "thumbnail_path": template.thumbnail_path,
                "tags": template.tags,
                "is_premium": template.is_premium,
                "settings": template.settings,
                "created_at": template.created_at.isoformat(),
                "usage_count": template.usage_count
            })

        metadata_file = Path("data/backgrounds/templates_metadata.json")
        async with aiofiles.open(metadata_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(templates_data, ensure_ascii=False, indent=2))

    def get_templates(self, category: Optional[str] = None,
                     tags: Optional[List[str]] = None,
                     premium_only: bool = False) -> List[BackgroundTemplate]:
        """背景テンプレートを取得"""
        templates = list(self.templates.values())

        if category:
            templates = [t for t in templates if t.category == category]

        if tags:
            templates = [t for t in templates if any(tag in t.tags for tag in tags)]

        if premium_only:
            templates = [t for t in templates if t.is_premium]

        return sorted(templates, key=lambda x: x.usage_count, reverse=True)

    def get_categories(self) -> Dict[str, str]:
        """カテゴリを取得"""
        return {
            "office": "オフィス",
            "studio": "スタジオ",
            "outdoor": "屋外",
            "abstract": "抽象",
            "brand": "ブランド"
        }

    async def apply_background_config(self, foreground_path: str,
                                    background_config: BackgroundConfig,
                                    output_path: Optional[str] = None) -> str:
        """
        背景設定を適用

        Args:
            foreground_path: 前景画像パス
            background_config: 背景設定
            output_path: 出力パス（指定なしの場合は自動生成）

        Returns:
            出力画像パス
        """
        try:
            # 前景画像読み込み
            foreground = Image.open(foreground_path).convert('RGBA')

            # 背景適用
            result_image = await self.processor.apply_background(foreground, background_config)

            # 出力パス設定
            if not output_path:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                output_path = f"data/backgrounds/output/background_applied_{timestamp}.png"

            # ディレクトリ作成
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # 保存
            result_image.save(output_path, 'PNG')

            # テンプレート使用カウント更新
            if background_config.template_id and background_config.template_id in self.templates:
                self.templates[background_config.template_id].usage_count += 1
                await self._save_template_metadata(self.templates[background_config.template_id])

            return output_path

        except Exception as e:
            logger.error(f"Background application failed: {e}")
            raise

    async def create_custom_background(self, image_path: str, name: str,
                                     category: str = "custom") -> BackgroundTemplate:
        """
        カスタム背景を作成

        Args:
            image_path: 背景画像パス
            name: 背景名
            category: カテゴリ

        Returns:
            作成されたテンプレート
        """
        try:
            # 画像検証
            if not Path(image_path).exists():
                raise FileNotFoundError(f"Background image not found: {image_path}")

            # テンプレートID生成
            template_id = f"custom_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

            # 画像をコピー
            template_image_path = self.custom_dir / f"{template_id}.png"
            shutil.copy2(image_path, template_image_path)

            # サムネイル作成
            image = Image.open(image_path)
            image.thumbnail(self.processor.thumbnail_size)
            thumbnail_path = self.custom_dir / f"{template_id}_thumb.png"
            image.save(thumbnail_path, 'PNG')

            # テンプレート作成
            template = BackgroundTemplate(
                template_id=template_id,
                name=name,
                description=f"カスタム背景: {name}",
                category=category,
                image_path=str(template_image_path),
                thumbnail_path=str(thumbnail_path),
                tags=["custom", category]
            )

            self.templates[template_id] = template
            await self._save_template_metadata(template)

            return template

        except Exception as e:
            logger.error(f"Custom background creation failed: {e}")
            raise

    async def delete_template(self, template_id: str) -> bool:
        """テンプレートを削除"""
        if template_id not in self.templates:
            return False

        template = self.templates[template_id]

        # ファイル削除
        try:
            if template.image_path and Path(template.image_path).exists():
                Path(template.image_path).unlink()

            if template.thumbnail_path and Path(template.thumbnail_path).exists():
                Path(template.thumbnail_path).unlink()

            # メタデータファイル削除
            metadata_file = self.templates_dir / f"{template_id}_metadata.json"
            if metadata_file.exists():
                metadata_file.unlink()

            del self.templates[template_id]

            # 全メタデータ更新
            await self._save_all_templates_metadata()

            return True

        except Exception as e:
            logger.error(f"Template deletion failed: {e}")
            return False

# グローバルインスタンス管理
_virtual_backgrounds_service = None

async def get_virtual_backgrounds_service() -> VirtualBackgroundsService:
    """仮想背景サービスのインスタンスを取得"""
    global _virtual_backgrounds_service

    if _virtual_backgrounds_service is None:
        _virtual_backgrounds_service = VirtualBackgroundsService()
        await _virtual_backgrounds_service.initialize()

    return _virtual_backgrounds_service
