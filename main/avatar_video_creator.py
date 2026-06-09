# main/avatar_video_creator.py
"""
Avatar Video Creator Module for Cocoa
アバターを使用した動画生成機能を提供
"""

import os
import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
try:
    import moviepy.editor as mp
    MOVIEPY_AVAILABLE = True
except ImportError:
    mp = None
    MOVIEPY_AVAILABLE = False

from integrated_security import get_security_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class VideoGenerationRequest:
    """動画生成リクエスト"""
    user_id: str
    avatar_id: str
    script_text: str
    voice_language: str = "ja"
    voice_gender: str = "neutral"
    background_music: Optional[str] = None
    video_style: str = "presentation"
    duration_limit: int = 300  # 5分制限
    resolution: Tuple[int, int] = (1920, 1080)
    fps: int = 30

@dataclass
class VideoGenerationResult:
    """動画生成結果"""
    success: bool
    video_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    metadata: Dict = None
    error_message: Optional[str] = None
    generation_time: float = 0.0

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class AvatarVideoCreator:
    """
    アバター動画作成システム
    アバターを使った動画を生成
    """

    def __init__(self, assets_dir: str = "data/video_assets"):
        """
        初期化

        Args:
            assets_dir: 動画アセットディレクトリ
        """
        self.security_manager = get_security_manager()
        self.assets_dir = Path(assets_dir)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

        # 動画生成設定
        self.supported_languages = ["ja", "en", "zh", "ko", "es", "fr", "de"]
        self.supported_styles = ["presentation", "tutorial", "storytelling", "interview"]
        self.max_duration = 600  # 10分制限

        # フォント設定
        self.fonts = self._load_fonts()

        logger.info(f"Avatar Video Creator initialized with assets dir: {assets_dir}")

    def _load_fonts(self) -> Dict[str, str]:
        """利用可能なフォントを読み込み"""
        fonts = {}

        # システムフォントの検索（簡易版）
        try:
            # Windows
            if os.name == 'nt':
                fonts_dir = "C:/Windows/Fonts"
                fonts["ja"] = f"{fonts_dir}/msgothic.ttc"
                fonts["en"] = f"{fonts_dir}/arial.ttf"
            # macOS
            elif os.name == 'posix' and 'darwin' in os.sys.platform:
                fonts["ja"] = "/System/Library/Fonts/Hiragino Sans GB.ttc"
                fonts["en"] = "/System/Library/Fonts/Arial.ttf"
            # Linux
            else:
                fonts["ja"] = "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"
                fonts["en"] = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        except (OSError, FileNotFoundError) as e:
            # デフォルトフォントとしてNoneを設定
            logger.info(f"Font paths not found, using defaults: {e}")
            fonts = {"ja": None, "en": None}

        return fonts

    async def generate_video(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        """
        アバター動画を生成

        Args:
            request: 動画生成リクエスト

        Returns:
            生成結果
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # セキュリティチェック
            await self._validate_request(request)

            # スクリプトを解析・分割
            script_segments = await self._parse_script(request.script_text, request.voice_language)

            # アバター画像を読み込み
            avatar_image = await self._load_avatar_image(request.avatar_id)

            # 動画フレームを生成
            frames = await self._generate_video_frames(
                avatar_image,
                script_segments,
                request.resolution,
                request.video_style
            )

            # 動画を合成
            video_path = await self._create_video_from_frames(
                frames,
                request.fps,
                request.voice_language
            )

            # サムネイルを生成
            thumbnail_path = await self._generate_thumbnail(frames[0] if frames else None)

            # メタデータを生成
            metadata = {
                "script_segments": len(script_segments),
                "total_frames": len(frames),
                "resolution": request.resolution,
                "fps": request.fps,
                "style": request.video_style,
                "language": request.voice_language,
                "duration": len(frames) / request.fps,
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            # 生成時間を計算
            generation_time = asyncio.get_event_loop().time() - start_time

            result = VideoGenerationResult(
                success=True,
                video_path=video_path,
                thumbnail_path=thumbnail_path,
                metadata=metadata,
                generation_time=generation_time
            )

            # セキュリティログ
            await self.security_manager.log_security_event(
                event_type="video_generated",
                user_id=request.user_id,
                details={
                    "avatar_id": request.avatar_id,
                    "duration": metadata["duration"],
                    "resolution": request.resolution,
                    "generation_time": generation_time
                }
            )

            return result

        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            generation_time = asyncio.get_event_loop().time() - start_time

            return VideoGenerationResult(
                success=False,
                error_message=str(e),
                generation_time=generation_time
            )

    async def _validate_request(self, request: VideoGenerationRequest):
        """リクエストの妥当性を検証"""
        # ユーザー認証チェック
        if not await self.security_manager.validate_user_access(request.user_id, "video_generation"):
            raise ValueError("Unauthorized video generation request")

        # スクリプトの検証
        if not request.script_text or len(request.script_text.strip()) < 10:
            raise ValueError("Script too short (minimum 10 characters)")

        if len(request.script_text) > 10000:  # 約1000文字制限
            raise ValueError("Script too long (maximum 10000 characters)")

        # 言語の検証
        if request.voice_language not in self.supported_languages:
            raise ValueError(f"Unsupported language: {request.voice_language}")

        # スタイルの検証
        if request.video_style not in self.supported_styles:
            raise ValueError(f"Unsupported video style: {request.video_style}")

        # 解像度の検証
        if request.resolution not in [(1920, 1080), (1280, 720), (854, 480)]:
            raise ValueError("Unsupported resolution")

        # 持続時間の検証
        estimated_duration = len(request.script_text) / 10  # 簡易計算
        if estimated_duration > request.duration_limit:
            raise ValueError(f"Estimated duration exceeds limit: {estimated_duration}s > {request.duration_limit}s")

    async def _load_avatar_image(self, avatar_id: str) -> Image.Image:
        """アバター画像を読み込み"""
        # アバター画像のパスを構築
        avatar_path = self.assets_dir / "avatars" / f"{avatar_id}.png"

        if not avatar_path.exists():
            # デフォルトアバターを使用
            avatar_path = self.assets_dir / "avatars" / "default_avatar.png"

        if not avatar_path.exists():
            # シンプルなデフォルトアバターを生成
            avatar_image = await self._create_default_avatar()
            return avatar_image

        return Image.open(avatar_path)

    async def _create_default_avatar(self) -> Image.Image:
        """デフォルトアバター画像を作成"""
        # シンプルな円形アバターを作成
        size = (256, 256)
        avatar = Image.new('RGB', size, color='#3B82F6')

        # 円を描画
        draw = ImageDraw.Draw(avatar)
        center = (size[0] // 2, size[1] // 2)
        radius = min(size) // 2 - 10
        draw.ellipse(
            [(center[0] - radius, center[1] - radius),
             (center[0] + radius, center[1] + radius)],
            fill='#FFFFFF'
        )

        # 目を追加
        eye_radius = 15
        eye_y = center[1] - 30
        draw.ellipse(
            [(center[0] - 50 - eye_radius, eye_y - eye_radius),
             (center[0] - 50 + eye_radius, eye_y + eye_radius)],
            fill='#000000'
        )
        draw.ellipse(
            [(center[0] + 50 - eye_radius, eye_y - eye_radius),
             (center[0] + 50 + eye_radius, eye_y + eye_radius)],
            fill='#000000'
        )

        # 口を追加
        mouth_y = center[1] + 30
        draw.ellipse(
            [(center[0] - 30, mouth_y - 10),
             (center[0] + 30, mouth_y + 10)],
            fill='#FF69B4'
        )

        return avatar

    async def _parse_script(self, script_text: str, language: str) -> List[Dict[str, Any]]:
        """スクリプトを解析してセグメントに分割"""
        # 簡易的なセグメント分割（文単位）
        import re

        # 文で分割
        sentences = re.split(r'[。．！？\n]+', script_text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]

        segments = []
        for i, sentence in enumerate(sentences):
            segments.append({
                "id": i,
                "text": sentence,
                "duration": min(5, max(2, len(sentence) / 20)),  # 文字数に基づく持続時間
                "position": "center"
            })

        return segments

    async def _generate_video_frames(self,
                                   avatar_image: Image.Image,
                                   script_segments: List[Dict[str, Any]],
                                   resolution: Tuple[int, int],
                                   style: str) -> List[np.ndarray]:
        """動画フレームを生成"""
        frames = []
        width, height = resolution

        # スタイルに応じた背景色
        background_colors = {
            "presentation": (240, 248, 255),  # Alice blue
            "tutorial": (245, 245, 220),     # Beige
            "storytelling": (255, 240, 245), # Lavender blush
            "interview": (255, 255, 255)     # White
        }

        bg_color = background_colors.get(style, (255, 255, 255))

        for segment in script_segments:
            # フレームを作成
            frame = np.full((height, width, 3), bg_color, dtype=np.uint8)

            # アバターをフレームに貼り付け
            avatar_resized = avatar_image.resize((256, 256))
            avatar_array = np.array(avatar_resized)

            # アバターの位置を計算
            avatar_x = (width - 256) // 2
            avatar_y = height - 300

            # アバターをフレームに合成
            frame[avatar_y:avatar_y+256, avatar_x:avatar_x+256] = avatar_array

            # テキストを追加
            await self._add_text_to_frame(frame, segment["text"], resolution)

            frames.append(frame)

        return frames

    async def _add_text_to_frame(self, frame: np.ndarray, text: str, resolution: Tuple[int, int]):
        """フレームにテキストを追加"""
        try:
            # PILでテキストを描画
            pil_frame = Image.fromarray(frame)
            draw = ImageDraw.Draw(pil_frame)

            # フォントサイズを計算
            width, height = resolution
            font_size = min(48, max(24, int(height / 20)))

            # フォントの取得（フォールバック対応）
            try:
                font = ImageFont.truetype(self.fonts.get("ja", None) or "", font_size)
            except (OSError, IOError) as e:
                logger.debug(f"Failed to load TrueType font, using default: {e}")
                font = ImageFont.load_default()

            # テキストの位置を計算
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            text_x = (width - text_width) // 2
            text_y = 50

            # テキストの背景
            draw.rectangle(
                [text_x - 10, text_y - 10, text_x + text_width + 10, text_y + text_height + 10],
                fill=(255, 255, 255, 180)
            )

            # テキストを描画
            draw.text(
                (text_x, text_y),
                text,
                fill=(0, 0, 0),
                font=font
            )

            # NumPy配列に戻す
            frame[:] = np.array(pil_frame)

        except Exception as e:
            logger.error(f"Failed to add text to frame: {e}")

    async def _create_video_from_frames(self,
                                      frames: List[np.ndarray],
                                      fps: int,
                                      language: str) -> str:
        """フレームから動画を作成"""
        if not frames:
            raise ValueError("No frames to create video")

        # 一時ディレクトリにフレームを保存
        temp_dir = self.assets_dir / "temp" / f"video_{uuid.uuid4()}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # フレームを画像として保存
            frame_paths = []
            for i, frame in enumerate(frames):
                frame_path = temp_dir / f"frame_{i:04d}.png"
                cv2.imwrite(str(frame_path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                frame_paths.append(str(frame_path))

            # 動画ファイル名を生成
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            video_filename = f"avatar_video_{timestamp}_{language}.mp4"
            video_path = self.assets_dir / "videos" / video_filename

            # 動画ディレクトリを作成
            video_path.parent.mkdir(parents=True, exist_ok=True)

            # MoviePyで動画を作成
            clip = mp.ImageSequenceClip(frame_paths, fps=fps)

            # 動画を保存
            clip.write_videofile(
                str(video_path),
                fps=fps,
                codec='libx264',
                audio=False,
                verbose=False,
                logger=None
            )

            return str(video_path)

        finally:
            # 一時ファイルをクリーンアップ
            import shutil
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    async def _generate_thumbnail(self, first_frame: Optional[np.ndarray]) -> str:
        """サムネイルを生成"""
        if first_frame is None:
            # デフォルトのサムネイルを作成
            thumbnail = np.full((270, 480, 3), (240, 240, 240), dtype=np.uint8)
        else:
            # 最初のフレームをリサイズ
            thumbnail = cv2.resize(first_frame, (480, 270))

        # サムネイルのパス
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        thumbnail_filename = f"thumbnail_{timestamp}.jpg"
        thumbnail_path = self.assets_dir / "thumbnails" / thumbnail_filename

        # サムネイルディレクトリを作成
        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

        # サムネイルを保存
        cv2.imwrite(str(thumbnail_path), cv2.cvtColor(thumbnail, cv2.COLOR_RGB2BGR))

        return str(thumbnail_path)

    async def get_video_templates(self) -> List[Dict[str, Any]]:
        """利用可能な動画テンプレートを取得"""
        return [
            {
                "id": "presentation",
                "name": "プレゼンテーション",
                "description": "ビジネスプレゼンテーション向けスタイル",
                "preview_image": "presentation_preview.jpg"
            },
            {
                "id": "tutorial",
                "name": "チュートリアル",
                "description": "教育・学習コンテンツ向けスタイル",
                "preview_image": "tutorial_preview.jpg"
            },
            {
                "id": "storytelling",
                "name": "ストーリーテリング",
                "description": "物語・ナラティブ向けスタイル",
                "preview_image": "storytelling_preview.jpg"
            },
            {
                "id": "interview",
                "name": "インタビュー",
                "description": "対談・インタビュー向けスタイル",
                "preview_image": "interview_preview.jpg"
            }
        ]

    async def get_user_videos(self, user_id: str) -> List[Dict[str, Any]]:
        """ユーザーの動画一覧を取得"""
        videos_dir = self.assets_dir / "videos"

        if not videos_dir.exists():
            return []

        videos = []
        for video_file in videos_dir.glob("*.mp4"):
            if user_id in video_file.name:
                # メタデータファイルもチェック
                metadata_file = video_file.with_suffix('.json')
                metadata = {}

                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                    except (IOError, json.JSONDecodeError) as e:
                        logger.warning(f"Failed to load video metadata from {metadata_file}: {e}")

                videos.append({
                    "id": video_file.stem,
                    "name": video_file.name,
                    "path": str(video_file),
                    "thumbnail": str(video_file.with_suffix('.jpg').replace('videos', 'thumbnails')),
                    "created_at": metadata.get("created_at", ""),
                    "duration": metadata.get("duration", 0),
                    "metadata": metadata
                })

        return sorted(videos, key=lambda x: x["created_at"], reverse=True)

# グローバルインスタンス管理
_video_creator_instance = None

async def get_avatar_video_creator() -> AvatarVideoCreator:
    """アバター動画作成者のインスタンスを取得"""
    global _video_creator_instance

    if _video_creator_instance is None:
        _video_creator_instance = AvatarVideoCreator()

    return _video_creator_instance
