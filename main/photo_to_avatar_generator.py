# main/photo_to_avatar_generator.py
"""
Photo-to-Avatar AI Generator Module for Cocoa
写真から高品質なAIアバターを生成する機能を提供
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timezone

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    ImageDraw = None
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None

try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    face_recognition = None

from integrated_security import get_security_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class PhotoToAvatarRequest:
    """写真からアバター生成リクエスト"""
    user_id: str
    source_photo_path: str
    target_style: str = "realistic"
    enhance_features: bool = True
    preserve_identity: bool = True
    output_formats: List[str] = None
    quality_level: str = "high"
    include_animations: bool = False

    def __post_init__(self):
        if self.output_formats is None:
            self.output_formats = ["png", "jpg"]

@dataclass
class PhotoToAvatarResult:
    """写真からアバター生成結果"""
    success: bool
    avatar_paths: Dict[str, str] = None
    facial_features: Dict[str, Any] = None
    processing_metadata: Dict = None
    error_message: Optional[str] = None
    processing_time: float = 0.0

    def __post_init__(self):
        if self.avatar_paths is None:
            self.avatar_paths = {}
        if self.facial_features is None:
            self.facial_features = {}
        if self.processing_metadata is None:
            self.processing_metadata = {}

class FaceFeatureExtractor:
    """顔特徴抽出機能"""

    def __init__(self):
        self.face_detector = None
        self.landmark_predictor = None

    async def initialize(self):
        """顔認識モデルを初期化"""
        try:
            # face_recognitionライブラリを使用（dlibベース）
            logger.info("Face feature extractor initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize face detector: {e}")
            return False

    async def extract_features(self, image_path: str) -> Dict[str, Any]:
        """画像から顔の特徴を抽出"""
        try:
            # 画像を読み込み
            image = face_recognition.load_image_file(image_path)
            face_locations = face_recognition.face_locations(image)

            if not face_locations:
                raise ValueError("No faces detected in the image")

            # 最初の顔を使用（複数顔の場合は要検討）
            face_location = face_locations[0]

            # 顔のランドマークを検出
            face_landmarks = face_recognition.face_landmarks(image, [face_location])

            if not face_landmarks:
                raise ValueError("Failed to detect face landmarks")

            landmarks = face_landmarks[0]

            # 顔の特徴を分析
            features = {
                "face_location": face_location,
                "landmarks": landmarks,
                "face_shape": self._analyze_face_shape(landmarks),
                "eye_features": self._analyze_eye_features(landmarks),
                "nose_features": self._analyze_nose_features(landmarks),
                "mouth_features": self._analyze_mouth_features(landmarks),
                "overall_quality": self._assess_face_quality(image, face_location, landmarks)
            }

            return features

        except Exception as e:
            logger.error(f"Face feature extraction failed: {e}")
            return {}

    def _analyze_face_shape(self, landmarks: Dict[str, List]) -> str:
        """顔の形状を分析"""
        # 簡易的な顔形状分析
        chin_points = landmarks.get('chin', [])
        if not chin_points:
            return "unknown"

        # 顔の縦横比で形状を判定（簡易版）
        if len(chin_points) > 0:
            face_height = max(chin_points, key=lambda p: p[1])[1] - min(chin_points, key=lambda p: p[1])[1]
            face_width = max(chin_points, key=lambda p: p[0])[0] - min(chin_points, key=lambda p: p[0])[0]

            if face_height > face_width * 1.2:
                return "oval"
            if face_width > face_height * 1.1:
                return "round"
            return "heart"

        return "unknown"

    def _analyze_eye_features(self, landmarks: Dict[str, List]) -> Dict[str, Any]:
        """目の特徴を分析"""
        left_eye = landmarks.get('left_eye', [])
        right_eye = landmarks.get('right_eye', [])

        if not left_eye or not right_eye:
            return {}

        # 目のサイズと形状を分析（簡易版）
        left_eye_center = np.mean(left_eye, axis=0)
        right_eye_center = np.mean(right_eye, axis=0)
        eye_distance = np.linalg.norm(right_eye_center - left_eye_center)

        return {
            "eye_distance": float(eye_distance),
            "eye_symmetry": "symmetric" if abs(len(left_eye) - len(right_eye)) <= 2 else "asymmetric",
            "eye_size": "large" if eye_distance > 50 else "normal"
        }

    def _analyze_nose_features(self, landmarks: Dict[str, List]) -> Dict[str, Any]:
        """鼻の特徴を分析"""
        nose_bridge = landmarks.get('nose_bridge', [])
        nose_tip = landmarks.get('nose_tip', [])

        if not nose_bridge or not nose_tip:
            return {}

        bridge_length = len(nose_bridge)
        tip_width = max(nose_tip, key=lambda p: p[0])[0] - min(nose_tip, key=lambda p: p[0])[0]

        return {
            "nose_length": bridge_length,
            "nose_width": tip_width,
            "nose_shape": "straight" if bridge_length > tip_width else "wide"
        }

    def _analyze_mouth_features(self, landmarks: Dict[str, List]) -> Dict[str, Any]:
        """口の特徴を分析"""
        top_lip = landmarks.get('top_lip', [])
        bottom_lip = landmarks.get('bottom_lip', [])

        if not top_lip or not bottom_lip:
            return {}

        mouth_width = max(top_lip + bottom_lip, key=lambda p: p[0])[0] - min(top_lip + bottom_lip, key=lambda p: p[0])[0]
        mouth_height = max(top_lip + bottom_lip, key=lambda p: p[1])[1] - min(top_lip + bottom_lip, key=lambda p: p[1])[1]

        return {
            "mouth_width": mouth_width,
            "mouth_height": mouth_height,
            "mouth_shape": "full" if mouth_height > mouth_width * 0.3 else "thin"
        }

    def _assess_face_quality(self, image: "Any", face_location: Tuple, landmarks: Dict) -> str:
        """顔の品質を評価"""
        top, right, bottom, left = face_location
        face_roi = image[top:bottom, left:right]

        # 顔の明るさ、コントラスト、シャープネスを評価（簡易版）
        gray_face = cv2.cvtColor(face_roi, cv2.COLOR_RGB2GRAY)

        brightness = np.mean(gray_face)
        contrast = gray_face.std()

        # 品質スコアに基づいて評価
        if brightness > 100 and contrast > 30:
            return "excellent"
        if brightness > 60 and contrast > 20:
            return "good"
        return "fair"

class PhotoToAvatarGenerator:
    """
    写真からAIアバター生成システム
    高品質なアバターを1枚の写真から作成
    """

    def __init__(self, models_dir: str = "data/models/photo_to_avatar"):
        """
        初期化

        Args:
            models_dir: モデル保存ディレクトリ
        """
        self.security_manager = get_security_manager()
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # 顔特徴抽出器
        self.face_extractor = FaceFeatureExtractor()

        # AIモデル設定
        self.style_models = {
            "realistic": "stabilityai/stable-diffusion-2-1",
            "anime": "andite/anything-v4.0",
            "cartoon": "nitrosocke/mo-di-diffusion",
            "professional": "SG161222/RealVisXL_V2.0",
            "artistic": "runwayml/stable-diffusion-v1-5"
        }

        # 出力設定
        self.output_sizes = {
            "low": (512, 512),
            "medium": (1024, 1024),
            "high": (2048, 2048),
            "ultra": (4096, 4096)
        }

        logger.info(f"Photo-to-Avatar Generator initialized with models dir: {models_dir}")

    async def initialize_models(self):
        """AIモデルを初期化"""
        try:
            # 顔特徴抽出器を初期化
            await self.face_extractor.initialize()

            logger.info("Photo-to-Avatar models initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize models: {e}")
            return False

    async def generate_avatar_from_photo(self, request: PhotoToAvatarRequest) -> PhotoToAvatarResult:
        """
        写真からアバターを生成

        Args:
            request: 生成リクエスト

        Returns:
            生成結果
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # セキュリティチェック
            await self._validate_request(request)

            # 顔特徴を抽出
            facial_features = await self.face_extractor.extract_features(request.source_photo_path)

            if not facial_features:
                raise ValueError("Failed to extract facial features from the photo")

            # プロンプトを構築
            prompt = await self._build_generation_prompt(request, facial_features)

            # AIモデルでアバターを生成
            generated_images = await self._generate_with_ai(prompt, request)

            # 出力ファイルを保存
            avatar_paths = await self._save_generated_avatars(generated_images, request)

            # 処理時間を計算
            processing_time = asyncio.get_event_loop().time() - start_time

            result = PhotoToAvatarResult(
                success=True,
                avatar_paths=avatar_paths,
                facial_features=facial_features,
                processing_metadata={
                    "prompt": prompt,
                    "model_used": self.style_models.get(request.target_style, "unknown"),
                    "enhancement_applied": request.enhance_features,
                    "identity_preserved": request.preserve_identity,
                    "generation_timestamp": datetime.now(timezone.utc).isoformat()
                },
                processing_time=processing_time
            )

            # セキュリティログ
            await self.security_manager.log_security_event(
                event_type="photo_to_avatar_generated",
                user_id=request.user_id,
                details={
                    "target_style": request.target_style,
                    "facial_features_detected": len(facial_features),
                    "processing_time": processing_time,
                    "output_formats": request.output_formats
                }
            )

            return result

        except Exception as e:
            logger.error(f"Photo-to-avatar generation failed: {e}")
            processing_time = asyncio.get_event_loop().time() - start_time

            return PhotoToAvatarResult(
                success=False,
                error_message=str(e),
                processing_time=processing_time
            )

    async def _validate_request(self, request: PhotoToAvatarRequest):
        """リクエストの妥当性を検証"""
        # ユーザー認証チェック
        if not await self.security_manager.validate_user_access(request.user_id, "photo_to_avatar"):
            raise ValueError("Unauthorized photo-to-avatar generation request")

        # 写真ファイルの検証
        if not Path(request.source_photo_path).exists():
            raise FileNotFoundError(f"Source photo not found: {request.source_photo_path}")

        # 画像サイズと形式のチェック
        try:
            with Image.open(request.source_photo_path) as img:
                if img.size[0] < 256 or img.size[1] < 256:
                    raise ValueError("Photo too small (minimum 256x256)")

                if img.format not in ['JPEG', 'PNG', 'BMP', 'TIFF']:
                    raise ValueError("Unsupported image format")

        except Exception as e:
            raise ValueError(f"Invalid photo file: {e}") from e

        # スタイルの検証
        if request.target_style not in self.style_models:
            raise ValueError(f"Unsupported style: {request.target_style}")

    async def _build_generation_prompt(self, request: PhotoToAvatarRequest, facial_features: Dict) -> str:
        """AI生成用のプロンプトを構築"""
        # 基本スタイルのプロンプトを取得
        base_style_prompt = self._get_style_prompt(request.target_style)

        # 顔特徴に基づく詳細なプロンプトを構築
        feature_prompts = []

        # 顔形状
        face_shape = facial_features.get("face_shape", "unknown")
        if face_shape != "unknown":
            feature_prompts.append(f"{face_shape} face shape")

        # 目の特徴
        eye_features = facial_features.get("eye_features", {})
        if eye_features:
            eye_size = eye_features.get("eye_size", "normal")
            eye_symmetry = eye_features.get("eye_symmetry", "symmetric")
            feature_prompts.append(f"{eye_size} {eye_symmetry} eyes")

        # 鼻の特徴
        nose_features = facial_features.get("nose_features", {})
        if nose_features:
            nose_shape = nose_features.get("nose_shape", "straight")
            feature_prompts.append(f"{nose_shape} nose")

        # 口の特徴
        mouth_features = facial_features.get("mouth_features", {})
        if mouth_features:
            mouth_shape = mouth_features.get("mouth_shape", "normal")
            feature_prompts.append(f"{mouth_shape} lips")

        # 全体の品質
        quality = facial_features.get("overall_quality", "good")
        if quality == "excellent":
            feature_prompts.append("high quality facial features, detailed, photorealistic")
        elif quality == "good":
            feature_prompts.append("good quality facial features, clear, well-lit")
        else:
            feature_prompts.append("acceptable quality facial features")

        # 特徴強調オプション
        if request.enhance_features:
            feature_prompts.append("enhanced facial features, sharp details, professional lighting")

        # アイデンティティ保持オプション
        if request.preserve_identity:
            feature_prompts.append("preserve original identity, maintain facial characteristics")

        # 完全なプロンプトを構築
        full_prompt = f"{base_style_prompt}, {', '.join(feature_prompts)}"

        # ネガティブプロンプトを追加
        negative_prompt = "blurry, low quality, deformed, ugly, disfigured, extra limbs, mutated hands"

        return f"{full_prompt}, {negative_prompt}"

    def _get_style_prompt(self, style: str) -> str:
        """スタイルに応じたプロンプトを取得"""
        style_prompts = {
            "realistic": "photorealistic portrait, high quality, detailed face, professional lighting, sharp focus",
            "anime": "anime style portrait, manga, detailed eyes, vibrant colors, studio lighting",
            "cartoon": "cartoon style portrait, colorful, animated, cel shading, vibrant colors",
            "professional": "professional headshot, business attire, clean background, corporate style, high quality",
            "artistic": "artistic portrait, painterly style, detailed brushwork, artistic lighting, masterpiece"
        }

        return style_prompts.get(style, style_prompts["realistic"])

    async def _generate_with_ai(self, prompt: str, request: PhotoToAvatarRequest) -> "List[Any]":
        """AIモデルで画像を生成"""
        try:
            # 実際の実装ではStable Diffusionなどのモデルを使用
            # ここではシミュレーションとしてデフォルト画像を生成

            # 出力サイズを取得
            output_size = self.output_sizes.get(request.quality_level, self.output_sizes["high"])

            # スタイルに基づいてベース画像を作成（シミュレーション）
            generated_images = []

            for _i in range(len(request.output_formats)):
                # シミュレートされた画像生成
                base_color = {
                    "realistic": "#F5DEB3",
                    "anime": "#FFE4E1",
                    "cartoon": "#98FB98",
                    "professional": "#F0F8FF",
                    "artistic": "#FFF8DC"
                }.get(request.target_style, "#F5DEB3")

                # シンプルなアバター画像を生成（実際はAIモデルで生成）
                avatar_image = Image.new('RGB', output_size, base_color)

                # 顔の輪郭を追加（簡易版）
                draw = ImageDraw.Draw(avatar_image)
                center_x, center_y = output_size[0] // 2, output_size[1] // 2

                # 顔の円を描画
                face_radius = min(output_size) // 3
                draw.ellipse(
                    [(center_x - face_radius, center_y - face_radius),
                     (center_x + face_radius, center_y + face_radius)],
                    fill="#DEB887"
                )

                # 特徴を追加（簡易版）
                if request.enhance_features:
                    # 目を追加
                    eye_radius = 15
                    draw.ellipse(
                        [(center_x - 50 - eye_radius, center_y - 30 - eye_radius),
                         (center_x - 50 + eye_radius, center_y - 30 + eye_radius)],
                        fill="#000000"
                    )
                    draw.ellipse(
                        [(center_x + 50 - eye_radius, center_y - 30 - eye_radius),
                         (center_x + 50 + eye_radius, center_y - 30 + eye_radius)],
                        fill="#000000"
                    )

                    # 口を追加
                    draw.ellipse(
                        [(center_x - 25, center_y + 20),
                         (center_x + 25, center_y + 40)],
                        fill="#FF69B4"
                    )

                generated_images.append(avatar_image)

            return generated_images

        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            raise

    async def _save_generated_avatars(self, images: "List[Any]", request: PhotoToAvatarRequest) -> Dict[str, str]:
        """生成されたアバターを保存"""
        avatar_paths = {}
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        user_dir = self.models_dir / "output" / request.user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        for i, (image, format_type) in enumerate(zip(images, request.output_formats)):
            filename = f"avatar_{timestamp}_{request.target_style}_{i}.{format_type}"
            file_path = user_dir / filename

            # 画像を保存
            image.save(file_path, format_type.upper(), quality=95 if format_type == "jpg" else None)

            avatar_paths[format_type] = str(file_path)

        return avatar_paths

    async def get_supported_styles(self) -> List[Dict[str, str]]:
        """サポートされるスタイル一覧を取得"""
        return [
            {"id": "realistic", "name": "リアル", "description": "実在の人物のようなリアルな外見"},
            {"id": "anime", "name": "アニメ", "description": "日本のアニメスタイル"},
            {"id": "cartoon", "name": "カートゥーン", "description": "明るく楽しいカートゥーンスタイル"},
            {"id": "professional", "name": "プロフェッショナル", "description": "ビジネス向けのプロフェッショナルスタイル"},
            {"id": "artistic", "name": "アーティスティック", "description": "芸術的なスタイル"}
        ]

    async def analyze_photo_quality(self, photo_path: str) -> Dict[str, Any]:
        """写真の品質を分析"""
        try:
            features = await self.face_extractor.extract_features(photo_path)

            if not features:
                return {"quality": "poor", "reason": "No faces detected"}

            quality_score = features.get("overall_quality", "fair")

            return {
                "quality": quality_score,
                "face_shape": features.get("face_shape", "unknown"),
                "features_detected": len(features.get("facial_features", {})),
                "recommendations": self._get_quality_recommendations(quality_score)
            }

        except Exception as e:
            logger.error(f"Photo quality analysis failed: {e}")
            return {"quality": "error", "reason": str(e)}

    def _get_quality_recommendations(self, quality: str) -> List[str]:
        """品質に基づく推奨事項を取得"""
        recommendations = {
            "excellent": ["写真の品質が非常に良いです。このまま使用できます。"],
            "good": ["写真の品質が良好です。より良い結果のために照明を改善することを検討してください。"],
            "fair": ["写真の品質が普通です。より良い照明と正面からの撮影を推奨します。"],
            "poor": ["写真の品質が低いです。より良い照明と高解像度の写真を使用してください。"]
        }

        return recommendations.get(quality, ["品質を改善してください。"])

# グローバルインスタンス管理
_photo_generator_instance = None

async def get_photo_to_avatar_generator() -> PhotoToAvatarGenerator:
    """写真からアバター生成者のインスタンスを取得"""
    global _photo_generator_instance

    if _photo_generator_instance is None:
        _photo_generator_instance = PhotoToAvatarGenerator()
        await _photo_generator_instance.initialize_models()

    return _photo_generator_instance
