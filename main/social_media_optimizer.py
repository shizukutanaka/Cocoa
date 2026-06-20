# main/social_media_optimizer.py
"""
Social Media Optimizer Module for Cocoa
各プラットフォームに最適化された動画フォーマット自動調整
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from video_encoding import EncodingPreset, get_video_encoder
    VIDEO_ENCODING_AVAILABLE = True
except ImportError:
    VIDEO_ENCODING_AVAILABLE = False
    get_video_encoder = None

    from dataclasses import dataclass as _dc
    from dataclasses import field as _field

    @_dc
    class EncodingPreset:
        preset_id: str = ""
        name: str = ""
        description: str = ""
        target_platform: str = ""
        video_codec: str = "libx264"
        audio_codec: str = "aac"
        bitrate_video: str = "2000k"
        bitrate_audio: str = "128k"
        resolution: tuple = (1920, 1080)
        fps: int = 30
        quality: str = "high"
        file_format: str = "mp4"
        estimated_file_size_mb: float = 50.0
        encoding_speed: str = "balanced"
        settings: dict = _field(default_factory=dict)

from integrated_security import get_security_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class PlatformSpec:
    """プラットフォーム仕様"""
    platform_id: str
    name: str
    max_duration: int  # 秒
    max_file_size: int  # MB
    resolutions: List[Tuple[int, int]]
    aspect_ratios: List[str]
    video_codecs: List[str]
    audio_codecs: List[str]
    frame_rates: List[int]
    bitrates: Dict[str, str]
    special_requirements: Dict[str, Any] = None

    def __post_init__(self):
        if self.special_requirements is None:
            self.special_requirements = {}

@dataclass
class OptimizationRequest:
    """最適化リクエスト"""
    video_path: str
    platforms: List[str]
    priority: str = "balanced"  # "quality", "size", "speed", "balanced"
    custom_settings: Dict[str, Any] = None

    def __post_init__(self):
        if self.custom_settings is None:
            self.custom_settings = {}

@dataclass
class OptimizationResult:
    """最適化結果"""
    success: bool
    optimized_videos: Dict[str, str] = None  # platform_id -> output_path
    thumbnails: Dict[str, str] = None
    metadata: Dict[str, Any] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.optimized_videos is None:
            self.optimized_videos = {}
        if self.thumbnails is None:
            self.thumbnails = {}
        if self.metadata is None:
            self.metadata = {}

class SocialMediaOptimizer:
    """
    ソーシャルメディア最適化ツール
    各プラットフォームに最適化された動画フォーマット調整
    """

    def __init__(self):
        self.security_manager = get_security_manager()
        self.video_encoder = None

        # プラットフォーム仕様定義
        self.platform_specs = self._create_platform_specs()

        # 出力ディレクトリ
        self.output_dir = Path("data/social_media_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Social Media Optimizer initialized")

    async def initialize(self):
        """初期化"""
        if not self.video_encoder and VIDEO_ENCODING_AVAILABLE and get_video_encoder:
            self.video_encoder = await get_video_encoder()

    def _create_platform_specs(self) -> Dict[str, PlatformSpec]:
        """プラットフォーム仕様を作成"""
        return {
            "youtube": PlatformSpec(
                platform_id="youtube",
                name="YouTube",
                max_duration=43200,  # 12時間
                max_file_size=256000,  # 256GB (事実上無制限)
                resolutions=[(3840, 2160), (1920, 1080), (1280, 720), (854, 480)],
                aspect_ratios=["16:9", "9:16", "1:1"],
                video_codecs=["avc1", "vp9"],
                audio_codecs=["mp4a"],
                frame_rates=[24, 25, 30, 48, 50, 60],
                bitrates={
                    "high": "8000k",
                    "medium": "5000k",
                    "low": "2500k"
                },
                special_requirements={
                    "squared_pixel": True,
                    "progressive_scan": True,
                    "color_space": "bt709",
                    "max_keyframe_interval": 250,
                    "recommended_bitrate": "8-12 Mbps for 1080p"
                }
            ),

            "instagram": PlatformSpec(
                platform_id="instagram",
                name="Instagram",
                max_duration=90,  # 90秒 (フィード), 60秒 (ストーリー)
                max_file_size=4000,  # 4GB
                resolutions=[(1080, 1920), (1080, 1350), (1080, 1080)],
                aspect_ratios=["9:16", "4:5", "1:1"],
                video_codecs=["h264"],
                audio_codecs=["aac"],
                frame_rates=[24, 25, 30],
                bitrates={
                    "high": "3500k",
                    "medium": "2500k",
                    "low": "1500k"
                },
                special_requirements={
                    "min_resolution": (600, 315),
                    "max_resolution": (1080, 1920),
                    "recommended_fps": 30,
                    "audio_channels": 2,
                    "sample_rate": 44100
                }
            ),

            "tiktok": PlatformSpec(
                platform_id="tiktok",
                name="TikTok",
                max_duration=600,  # 10分 (ただし推奨は15-60秒)
                max_file_size=4000,  # 4GB
                resolutions=[(1080, 1920), (720, 1280)],
                aspect_ratios=["9:16"],
                video_codecs=["h264"],
                audio_codecs=["aac", "mp3"],
                frame_rates=[24, 25, 30],
                bitrates={
                    "high": "2000k",
                    "medium": "1500k",
                    "low": "1000k"
                },
                special_requirements={
                    "aspect_ratio": "9:16",
                    "min_resolution": (540, 960),
                    "max_resolution": (1080, 1920),
                    "recommended_duration": "15-60秒",
                    "text_safe_zone": True
                }
            ),

            "facebook": PlatformSpec(
                platform_id="facebook",
                name="Facebook",
                max_duration=28800,  # 8時間
                max_file_size=4000,  # 4GB
                resolutions=[(1280, 720), (1920, 1080)],
                aspect_ratios=["16:9", "9:16", "1:1", "4:5"],
                video_codecs=["h264", "h265"],
                audio_codecs=["aac"],
                frame_rates=[24, 25, 30],
                bitrates={
                    "high": "4000k",
                    "medium": "2500k",
                    "low": "1500k"
                },
                special_requirements={
                    "min_resolution": (600, 315),
                    "recommended_fps": 30,
                    "square_pixel": True,
                    "color_space": "bt709"
                }
            ),

            "twitter": PlatformSpec(
                platform_id="twitter",
                name="Twitter/X",
                max_duration=140,  # 2分20秒
                max_file_size=512,  # 512MB
                resolutions=[(1280, 720), (1920, 1080), (720, 1280)],
                aspect_ratios=["16:9", "9:16", "1:1"],
                video_codecs=["h264"],
                audio_codecs=["aac"],
                frame_rates=[24, 25, 30, 60],
                bitrates={
                    "high": "5000k",
                    "medium": "2500k",
                    "low": "1500k"
                },
                special_requirements={
                    "aspect_ratio_recommended": "16:9 or 1:1",
                    "min_resolution": (32, 32),
                    "max_resolution": (1920, 1200),
                    "recommended_fps": 30
                }
            ),

            "linkedin": PlatformSpec(
                platform_id="linkedin",
                name="LinkedIn",
                max_duration=600,  # 10分
                max_file_size=5120,  # 5GB
                resolutions=[(1920, 1080), (1280, 720)],
                aspect_ratios=["16:9", "1:1", "9:16"],
                video_codecs=["h264"],
                audio_codecs=["aac"],
                frame_rates=[24, 25, 30],
                bitrates={
                    "high": "5000k",
                    "medium": "3000k",
                    "low": "1500k"
                },
                special_requirements={
                    "aspect_ratio_recommended": "16:9",
                    "min_resolution": (360, 640),
                    "recommended_fps": 30,
                    "text_overlay_safe": True
                }
            ),

            "snapchat": PlatformSpec(
                platform_id="snapchat",
                name="Snapchat",
                max_duration=60,  # 60秒
                max_file_size=2000,  # 2GB
                resolutions=[(1080, 1920), (720, 1280)],
                aspect_ratios=["9:16"],
                video_codecs=["h264"],
                audio_codecs=["aac"],
                frame_rates=[24, 25, 30],
                bitrates={
                    "high": "2000k",
                    "medium": "1500k",
                    "low": "1000k"
                },
                special_requirements={
                    "aspect_ratio": "9:16",
                    "min_resolution": (480, 854),
                    "max_resolution": (1080, 1920),
                    "recommended_fps": 25
                }
            ),

            "pinterest": PlatformSpec(
                platform_id="pinterest",
                name="Pinterest",
                max_duration=900,  # 15分
                max_file_size=2000,  # 2GB
                resolutions=[(1000, 1500), (1000, 1000), (1500, 1000)],
                aspect_ratios=["2:3", "1:1", "3:2"],
                video_codecs=["h264"],
                audio_codecs=["aac"],
                frame_rates=[24, 25, 30],
                bitrates={
                    "high": "3000k",
                    "medium": "2000k",
                    "low": "1000k"
                },
                special_requirements={
                    "aspect_ratio_recommended": "2:3 (vertical)",
                    "min_resolution": (600, 900),
                    "recommended_fps": 30,
                    "auto_loop": True
                }
            ),

            "reddit": PlatformSpec(
                platform_id="reddit",
                name="Reddit",
                max_duration=900,  # 15分
                max_file_size=1000,  # 1GB
                resolutions=[(1920, 1080), (1280, 720)],
                aspect_ratios=["16:9", "9:16", "1:1"],
                video_codecs=["h264", "vp9"],
                audio_codecs=["aac", "opus"],
                frame_rates=[24, 25, 30, 60],
                bitrates={
                    "high": "4000k",
                    "medium": "2500k",
                    "low": "1500k"
                },
                special_requirements={
                    "no_watermarks": True,
                    "min_resolution": (320, 240),
                    "recommended_fps": 30
                }
            ),

            "tumblr": PlatformSpec(
                platform_id="tumblr",
                name="Tumblr",
                max_duration=300,  # 5分
                max_file_size=500,  # 500MB
                resolutions=[(1280, 720), (854, 480)],
                aspect_ratios=["16:9", "1:1", "9:16"],
                video_codecs=["h264"],
                audio_codecs=["aac"],
                frame_rates=[24, 25, 30],
                bitrates={
                    "high": "2500k",
                    "medium": "1500k",
                    "low": "1000k"
                },
                special_requirements={
                    "min_resolution": (200, 200),
                    "max_resolution": (1920, 1080),
                    "recommended_fps": 30
                }
            )
        }

    def get_supported_platforms(self) -> List[str]:
        """サポートされているプラットフォームを取得"""
        return list(self.platform_specs.keys())

    def get_platform_spec(self, platform_id: str) -> Optional[PlatformSpec]:
        """プラットフォーム仕様を取得"""
        return self.platform_specs.get(platform_id)

    def validate_video_for_platform(self, video_path: str, platform_id: str) -> Dict[str, Any]:
        """
        動画がプラットフォームの要件を満たしているか検証

        Args:
            video_path: 動画ファイルパス
            platform_id: プラットフォームID

        Returns:
            検証結果
        """
        spec = self.get_platform_spec(platform_id)
        if not spec:
            return {"valid": False, "error": "Unsupported platform"}

        # ファイルサイズチェック
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        if file_size_mb > spec.max_file_size:
            return {
                "valid": False,
                "error": f"File size ({file_size_mb:.1f}MB) exceeds limit ({spec.max_file_size}MB)"
            }

        # ここでは基本的なチェックのみ
        # 実際にはFFprobeなどで詳細な検証を行う
        return {
            "valid": True,
            "warnings": [],
            "recommendations": []
        }

    async def optimize_for_platforms(self, request: OptimizationRequest) -> OptimizationResult:
        """
        複数プラットフォーム向けに動画を最適化

        Args:
            request: 最適化リクエスト

        Returns:
            最適化結果
        """
        await self.initialize()

        try:
            results = {}

            # 各プラットフォーム向けに並列処理
            supported_platforms = [pid for pid in request.platforms if pid in self.platform_specs]
            tasks = [
                self._optimize_single_platform(
                    request.video_path, pid, request.priority, request.custom_settings
                )
                for pid in supported_platforms
            ]

            # 並列実行
            platform_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 結果集約 — zip so indices always match (supported_platforms[i] == tasks[i])
            for platform_id, result in zip(supported_platforms, platform_results):
                if isinstance(result, Exception):
                    results[platform_id] = {"success": False, "error": str(result)}
                else:
                    results[platform_id] = result

            return OptimizationResult(
                success=True,
                optimized_videos={pid: data.get("output_path") for pid, data in results.items() if data.get("success")},
                metadata={
                    "total_platforms": len(request.platforms),
                    "successful_optimizations": len([r for r in results.values() if r.get("success")]),
                    "platform_results": results
                }
            )

        except Exception as e:
            logger.error(f"Platform optimization failed: {e}")
            return OptimizationResult(
                success=False,
                error_message=str(e)
            )

    async def _optimize_single_platform(self, video_path: str, platform_id: str,
                                       priority: str, custom_settings: Dict) -> Dict[str, Any]:
        """単一プラットフォーム向け最適化"""
        spec = self.platform_specs[platform_id]

        try:
            # プラットフォーム固有のプリセット作成
            preset = self._create_platform_preset(spec, priority, custom_settings)

            # 出力パス
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"optimized_{platform_id}_{timestamp}.mp4"
            output_path = self.output_dir / filename

            # エンコード実行
            result = await self.video_encoder.encode_video(video_path, preset, str(output_path))

            if result.success:
                # サムネイル生成
                thumbnail_path = await self._generate_platform_thumbnail(
                    result.output_path, platform_id
                )

                return {
                    "success": True,
                    "output_path": result.output_path,
                    "thumbnail_path": thumbnail_path,
                    "file_size": result.file_size,
                    "compression_ratio": result.compression_ratio,
                    "quality_score": result.quality_score,
                    "platform_spec": {
                        "resolution": f"{preset.resolution[0]}x{preset.resolution[1]}",
                        "bitrate": preset.bitrate_video,
                        "fps": preset.fps
                    }
                }
            return {
                "success": False,
                "error": result.error_message
            }

        except Exception as e:
            logger.error(f"Platform optimization failed for {platform_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _create_platform_preset(self, spec: PlatformSpec, priority: str,
                               custom_settings: Dict) -> EncodingPreset:
        """プラットフォーム固有のエンコードプリセットを作成"""
        # 優先度に応じた設定
        if priority == "quality":
            bitrate_key = "high"
            preset_name = "veryslow"
        elif priority == "size":
            bitrate_key = "low"
            preset_name = "fast"
        elif priority == "speed":
            bitrate_key = "medium"
            preset_name = "ultrafast"
        else:  # balanced
            bitrate_key = "medium"
            preset_name = "medium"

        # 解像度選択（プラットフォームで推奨される最大解像度）
        resolution = spec.resolutions[0] if spec.resolutions else (1920, 1080)

        # FPS選択
        fps = spec.frame_rates[0] if spec.frame_rates else 30

        # ビットレート
        bitrate_video = spec.bitrates.get(bitrate_key, "2500k")
        bitrate_audio = "128k"  # 標準

        # カスタム設定の上書き
        if "resolution" in custom_settings:
            resolution = custom_settings["resolution"]
        if "fps" in custom_settings:
            fps = custom_settings["fps"]
        if "bitrate" in custom_settings:
            bitrate_video = custom_settings["bitrate"]

        return EncodingPreset(
            preset_id=f"social_{spec.platform_id}",
            name=f"Social Media - {spec.name}",
            description=f"Optimized for {spec.name}",
            target_platform="social",
            video_codec="libx264",
            audio_codec="aac",
            bitrate_video=bitrate_video,
            bitrate_audio=bitrate_audio,
            resolution=resolution,
            fps=fps,
            quality="high",
            file_format="mp4",
            estimated_file_size_mb=50.0,
            encoding_speed="balanced",
            settings={
                "preset": preset_name,
                "profile": "high",
                "level": "4.0",
                "pix_fmt": "yuv420p",
                "keyint_min": 48,
                "sc_threshold": 0
            }
        )

    async def _generate_platform_thumbnail(self, video_path: str, platform_id: str) -> Optional[str]:
        """プラットフォーム固有のサムネイルを生成"""
        try:
            import cv2
            from PIL import Image

            # 動画からフレームを抽出
            cap = cv2.VideoCapture(video_path)
            cap.set(cv2.CAP_PROP_POS_FRAMES, 30)  # 1秒目のフレーム
            ret, frame = cap.read()
            cap.release()

            if ret:
                # OpenCV BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(frame_rgb)

                # プラットフォームに応じたサイズ調整
                if platform_id == "tiktok":
                    # TikTokは正方形サムネイル推奨
                    size = (500, 500)
                elif platform_id == "instagram":
                    # Instagramは縦長
                    size = (500, 889)
                else:
                    # デフォルト16:9
                    size = (640, 360)

                image.thumbnail(size, Image.LANCZOS)

                # 保存
                thumbnail_filename = f"{Path(video_path).stem}_thumb_{platform_id}.jpg"
                thumbnail_path = self.output_dir / thumbnail_filename
                image.save(thumbnail_path, 'JPEG', quality=85)

                return str(thumbnail_path)

        except Exception as e:
            logger.warning(f"Thumbnail generation failed for {platform_id}: {e}")

        return None

    def get_platform_recommendations(self, video_path: str) -> Dict[str, List[str]]:
        """
        動画に対して推奨されるプラットフォームを取得

        Args:
            video_path: 動画ファイルパス

        Returns:
            プラットフォーム別推奨理由
        """
        # 簡易的な推奨ロジック
        recommendations = {}

        # ファイルサイズ取得
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)

        for platform_id, spec in self.platform_specs.items():
            reasons = []

            if file_size_mb <= spec.max_file_size:
                reasons.append("ファイルサイズ適合")
            else:
                reasons.append(f"ファイルサイズ超過 ({file_size_mb:.1f}MB > {spec.max_file_size}MB)")
                continue

            # 他の推奨ロジックをここに追加可能
            # 例: アスペクト比、解像度など

            if reasons:
                recommendations[platform_id] = reasons

        return recommendations

    def generate_sharing_links(self, video_urls: Dict[str, str]) -> Dict[str, str]:
        """
        各プラットフォームの共有リンクを生成

        Args:
            video_urls: プラットフォーム別動画URL

        Returns:
            プラットフォーム別共有リンク
        """
        sharing_links = {}

        for platform_id, video_url in video_urls.items():
            if platform_id == "youtube":
                sharing_links[platform_id] = f"https://youtu.be/{self._extract_video_id(video_url)}"
            elif platform_id == "tiktok":
                sharing_links[platform_id] = f"https://tiktok.com/@user/video/{self._extract_video_id(video_url)}"
            elif platform_id == "instagram":
                sharing_links[platform_id] = f"https://instagram.com/p/{self._extract_video_id(video_url)}"
            # 他のプラットフォームも追加可能

        return sharing_links

    def _extract_video_id(self, url: str) -> str:
        """URLから動画IDを抽出（簡易実装）"""
        # 実際の実装では各プラットフォームのURLパターンを解析
        return "video_id_placeholder"

    async def batch_optimize(self, requests: List[OptimizationRequest],
                           max_concurrent: int = 3) -> List[OptimizationResult]:
        """
        バッチ最適化を実行

        Args:
            requests: 最適化リクエストのリスト
            max_concurrent: 最大同時実行数

        Returns:
            最適化結果のリスト
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []

        async def process_request(request):
            async with semaphore:
                result = await self.optimize_for_platforms(request)
                results.append(result)

        await asyncio.gather(*[process_request(req) for req in requests])

        return results

# グローバルインスタンス管理
_social_media_optimizer = None
_social_media_optimizer_lock = asyncio.Lock()

async def get_social_media_optimizer() -> SocialMediaOptimizer:
    """ソーシャルメディア最適化ツールのインスタンスを取得"""
    global _social_media_optimizer

    if _social_media_optimizer is None:
        async with _social_media_optimizer_lock:
            if _social_media_optimizer is None:
                _social_media_optimizer = SocialMediaOptimizer()
                await _social_media_optimizer.initialize()

    return _social_media_optimizer
