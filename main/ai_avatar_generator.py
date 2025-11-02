# main/ai_avatar_generator.py
"""
AI Avatar Generator Module for Cocoa
生産グレードのAIアバター生成システム
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime

import torch
from PIL import Image
import numpy as np
from diffusers import StableDiffusionPipeline, StableDiffusionImg2ImgPipeline
from transformers import CLIPProcessor, CLIPModel
import cv2

from .integrated_security import get_security_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class AvatarGenerationRequest:
    """アバター生成リクエスト"""
    user_id: str
    source_image_path: Optional[str] = None
    prompt: str = ""
    style: str = "realistic"
    quality: str = "high"
    customizations: Dict[str, Union[str, int, float]] = None

    def __post_init__(self):
        if self.customizations is None:
            self.customizations = {}

@dataclass
class AvatarGenerationResult:
    """アバター生成結果"""
    success: bool
    avatar_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    metadata: Dict = None
    error_message: Optional[str] = None
    generation_time: float = 0.0

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class AvatarStyle:
    """アバタースタイル定義"""
    REALISTIC = "realistic"
    CARTOON = "cartoon"
    ANIME = "anime"
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    FANTASY = "fantasy"

    @classmethod
    def get_available_styles(cls) -> List[str]:
        """利用可能なスタイルを取得"""
        return [
            cls.REALISTIC,
            cls.CARTOON,
            cls.ANIME,
            cls.PROFESSIONAL,
            cls.CASUAL,
            cls.FANTASY
        ]

class AIAvatarGenerator:
    """
    AIアバター生成器
    Stable Diffusionを使用した高品質アバター生成
    """

    def __init__(self, model_path: str = None, device: str = "auto"):
        """
        初期化

        Args:
            model_path: カスタムモデルパス（オプション）
            device: 計算デバイス ("auto", "cpu", "cuda")
        """
        self.security_manager = get_security_manager()
        self.model_path = model_path or "runwayml/stable-diffusion-v1-5"
        self.device = self._determine_device(device)

        # モデル初期化
        self.text2img_pipeline = None
        self.img2img_pipeline = None
        self.clip_model = None
        self.clip_processor = None

        # キャッシュディレクトリ
        self.cache_dir = Path("data/avatar_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # スタイルプロンプトテンプレート
        self.style_prompts = self._load_style_prompts()

        logger.info(f"AI Avatar Generator initialized with device: {self.device}")

    def _determine_device(self, device: str) -> str:
        """計算デバイスを決定"""
        if device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return device

    def _load_style_prompts(self) -> Dict[str, str]:
        """スタイル別のプロンプトテンプレートを読み込み"""
        return {
            AvatarStyle.REALISTIC: "photorealistic portrait, high quality, detailed face, professional lighting, 8k",
            AvatarStyle.CARTOON: "cartoon style portrait, colorful, animated, cel shading, vibrant colors",
            AvatarStyle.ANIME: "anime style portrait, manga, detailed eyes, vibrant colors, studio ghibli inspired",
            AvatarStyle.PROFESSIONAL: "professional headshot, business attire, clean background, corporate style",
            AvatarStyle.CASUAL: "casual portrait, friendly expression, natural lighting, everyday clothing",
            AvatarStyle.FANTASY: "fantasy character portrait, magical, mystical, detailed costume, ethereal lighting"
        }

    async def initialize_models(self):
        """AIモデルを初期化"""
        try:
            logger.info("Initializing AI models...")

            # Text-to-Imageパイプライン
            self.text2img_pipeline = StableDiffusionPipeline.from_pretrained(
                self.model_path,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                safety_checker=None  # 安全チェックを無効化（運用環境では適切に設定）
            )
            self.text2img_pipeline.to(self.device)

            # Image-to-Imageパイプライン
            self.img2img_pipeline = StableDiffusionImg2ImgPipeline.from_pretrained(
                self.model_path,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                safety_checker=None
            )
            self.img2img_pipeline.to(self.device)

            # CLIPモデル（類似度計算用）
            self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

            if self.device == "cuda":
                self.clip_model.to(self.device)

            logger.info("AI models initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize AI models: {e}")
            raise

    async def generate_avatar(self, request: AvatarGenerationRequest) -> AvatarGenerationResult:
        """
        アバターを生成

        Args:
            request: 生成リクエスト

        Returns:
            生成結果
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # セキュリティチェック
            await self._validate_request(request)

            # プロンプト構築
            final_prompt = self._build_prompt(request)

            # 生成実行
            if request.source_image_path:
                # Image-to-Image生成
                result = await self._generate_from_image(request, final_prompt)
            else:
                # Text-to-Image生成
                result = await self._generate_from_text(request, final_prompt)

            # 後処理
            processed_result = await self._post_process_result(result, request)

            # 生成時間を記録
            end_time = asyncio.get_event_loop().time()
            processed_result.generation_time = end_time - start_time

            # 監査ログ
            await self._log_generation(request, processed_result)

            return processed_result

        except Exception as e:
            logger.error(f"Avatar generation failed: {e}")
            end_time = asyncio.get_event_loop().time()

            return AvatarGenerationResult(
                success=False,
                error_message=str(e),
                generation_time=end_time - start_time
            )

    async def _validate_request(self, request: AvatarGenerationRequest):
        """リクエストの妥当性を検証"""
        # ユーザー認証チェック
        if not await self.security_manager.validate_user_access(request.user_id, "avatar_generation"):
            raise ValueError("Unauthorized avatar generation request")

        # 入力データチェック
        if request.source_image_path:
            if not Path(request.source_image_path).exists():
                raise FileNotFoundError(f"Source image not found: {request.source_image_path}")

            # 画像サイズ・形式チェック
            await self._validate_image_file(request.source_image_path)

        # スタイルチェック
        if request.style not in AvatarStyle.get_available_styles():
            raise ValueError(f"Unsupported style: {request.style}")

    async def _validate_image_file(self, image_path: str):
        """画像ファイルの妥当性を検証"""
        try:
            with Image.open(image_path) as img:
                # サイズチェック（最大10MB）
                if os.path.getsize(image_path) > 10 * 1024 * 1024:
                    raise ValueError("Image file too large (max 10MB)")

                # フォーマットチェック
                if img.format not in ['JPEG', 'PNG', 'BMP', 'TIFF']:
                    raise ValueError("Unsupported image format")

                # 最小サイズチェック
                if min(img.size) < 256:
                    raise ValueError("Image too small (minimum 256x256)")

        except Exception as e:
            raise ValueError(f"Invalid image file: {e}")

    def _build_prompt(self, request: AvatarGenerationRequest) -> str:
        """生成プロンプトを構築"""
        base_prompt = self.style_prompts.get(request.style, "")

        if request.prompt:
            prompt = f"{request.prompt}, {base_prompt}"
        else:
            prompt = f"portrait of a person, {base_prompt}"

        # カスタマイズ適用
        if request.customizations:
            for key, value in request.customizations.items():
                if key == "age":
                    prompt += f", {value} years old"
                elif key == "gender":
                    prompt += f", {value}"
                elif key == "hair_color":
                    prompt += f", {value} hair"
                elif key == "expression":
                    prompt += f", {value} expression"

        return prompt

    async def _generate_from_text(self, request: AvatarGenerationRequest, prompt: str) -> Dict:
        """テキストから画像を生成"""
        if not self.text2img_pipeline:
            raise RuntimeError("Text-to-image pipeline not initialized")

        # 生成パラメータ
        generator = torch.Generator(device=self.device).manual_seed(42)

        with torch.no_grad():
            result = self.text2img_pipeline(
                prompt=prompt,
                negative_prompt="blurry, low quality, deformed, ugly, disfigured",
                num_inference_steps=50 if request.quality == "high" else 30,
                guidance_scale=7.5,
                width=512,
                height=512,
                generator=generator
            )

        image = result.images[0]
        return {"image": image, "type": "text2img"}

    async def _generate_from_image(self, request: AvatarGenerationRequest, prompt: str) -> Dict:
        """画像から画像を生成"""
        if not self.img2img_pipeline:
            raise RuntimeError("Image-to-image pipeline not initialized")

        # ソース画像読み込み
        init_image = Image.open(request.source_image_path).convert("RGB")
        init_image = init_image.resize((512, 512))

        # 強度設定（カスタマイズ可能）
        strength = request.customizations.get("strength", 0.75)

        with torch.no_grad():
            result = self.img2img_pipeline(
                prompt=prompt,
                image=init_image,
                negative_prompt="blurry, low quality, deformed, ugly, disfigured",
                num_inference_steps=50 if request.quality == "high" else 30,
                guidance_scale=7.5,
                strength=strength,
                generator=torch.Generator(device=self.device).manual_seed(42)
            )

        image = result.images[0]
        return {"image": image, "type": "img2img"}

    async def _post_process_result(self, generation_result: Dict, request: AvatarGenerationRequest) -> AvatarGenerationResult:
        """生成結果を後処理"""
        image = generation_result["image"]

        # ファイルパス生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        user_dir = self.cache_dir / request.user_id
        user_dir.mkdir(exist_ok=True)

        avatar_filename = f"avatar_{timestamp}_{request.style}.png"
        thumbnail_filename = f"avatar_{timestamp}_{request.style}_thumb.jpg"

        avatar_path = user_dir / avatar_filename
        thumbnail_path = user_dir / thumbnail_filename

        # メイン画像保存
        image.save(avatar_path, "PNG", quality=95)

        # サムネイル生成
        thumbnail = image.copy()
        thumbnail.thumbnail((256, 256))
        thumbnail.save(thumbnail_path, "JPEG", quality=85)

        # メタデータ生成
        metadata = {
            "generation_type": generation_result["type"],
            "style": request.style,
            "quality": request.quality,
            "prompt": request.prompt,
            "customizations": request.customizations,
            "image_size": image.size,
            "file_size": os.path.getsize(avatar_path),
            "created_at": datetime.now().isoformat()
        }

        return AvatarGenerationResult(
            success=True,
            avatar_path=str(avatar_path),
            thumbnail_path=str(thumbnail_path),
            metadata=metadata
        )

    async def _log_generation(self, request: AvatarGenerationRequest, result: AvatarGenerationResult):
        """生成操作を監査ログに記録"""
        await self.security_manager.log_security_event(
            event_type="avatar_generation",
            user_id=request.user_id,
            details={
                "success": result.success,
                "style": request.style,
                "generation_time": result.generation_time,
                "error_message": result.error_message
            },
            ip_address="system"  # 内部生成のため
        )

    async def get_user_avatars(self, user_id: str) -> List[Dict]:
        """ユーザーのアバター一覧を取得"""
        user_dir = self.cache_dir / user_id
        if not user_dir.exists():
            return []

        avatars = []
        for avatar_file in user_dir.glob("avatar_*.png"):
            metadata_file = avatar_file.with_suffix('.json')
            metadata = {}

            if metadata_file.exists():
                try:
                    import json
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                except:
                    pass

            avatars.append({
                "path": str(avatar_file),
                "thumbnail": str(avatar_file.with_suffix('')) + '_thumb.jpg',
                "filename": avatar_file.name,
                "created_at": metadata.get("created_at", ""),
                "style": metadata.get("style", "unknown"),
                "metadata": metadata
            })

        return sorted(avatars, key=lambda x: x["created_at"], reverse=True)

    async def delete_avatar(self, user_id: str, avatar_filename: str) -> bool:
        """アバターを削除"""
        user_dir = self.cache_dir / user_id
        avatar_path = user_dir / avatar_filename

        if not avatar_path.exists():
            return False

        # セキュリティチェック
        if not await self.security_manager.validate_user_access(user_id, "avatar_delete"):
            raise ValueError("Unauthorized avatar deletion")

        # ファイル削除
        avatar_path.unlink()

        # サムネイルも削除
        thumbnail_path = avatar_path.with_suffix('').with_suffix('_thumb.jpg')
        if thumbnail_path.exists():
            thumbnail_path.unlink()

        # メタデータ削除
        metadata_path = avatar_path.with_suffix('.json')
        if metadata_path.exists():
            metadata_path.unlink()

        logger.info(f"Avatar deleted: {avatar_path}")
        return True

# グローバルインスタンス管理
_avatar_generator_instance = None

async def get_ai_avatar_generator() -> AIAvatarGenerator:
    """AIアバター生成器のインスタンスを取得"""
    global _avatar_generator_instance

    if _avatar_generator_instance is None:
        _avatar_generator_instance = AIAvatarGenerator()
        await _avatar_generator_instance.initialize_models()

    return _avatar_generator_instance
