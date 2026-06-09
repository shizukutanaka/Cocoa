"""
VR/AR Enhanced Avatar System for Cocoa
WebXRとハプティック技術を活用した没入型アバター体験システム
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict

from integrated_security import get_security_manager

logger = logging.getLogger(__name__)

@dataclass
class VRAvatarConfig:
    """VRアバター設定"""
    avatar_id: str
    user_id: str
    vr_model: str
    animation_profile: str
    haptic_settings: Dict[str, Any]
    interaction_zones: List[Dict[str, Any]]
    metaverse_compatibility: List[str]
    performance_mode: str

@dataclass
class ARInteractionData:
    """ARインタラクションデータ"""
    gesture_type: str
    confidence_score: float
    hand_position: Dict[str, float]
    eye_tracking: Dict[str, float]
    voice_commands: List[str]
    environmental_context: Dict[str, Any]

class VRAvatarSystem:
    """
    VR/AR強化アバターシステム
    WebXR対応の没入型体験を提供
    """

    def __init__(self):
        self.security_manager = get_security_manager()

        # VR/AR設定
        self.supported_vr_platforms = [
            "oculus_quest", "htc_vive", "valve_index",
            "windows_mixed_reality", "playstation_vr"
        ]

        self.supported_ar_frameworks = [
            "webxr", "arkit", "arcore", "hololens"
        ]

        # アニメーションプロファイル
        self.animation_profiles = {
            "realistic": {
                "frame_rate": 90,
                "motion_smoothing": True,
                "physics_simulation": True,
                "facial_tracking": True
            },
            "performance": {
                "frame_rate": 60,
                "motion_smoothing": False,
                "physics_simulation": False,
                "facial_tracking": False
            },
            "casual": {
                "frame_rate": 30,
                "motion_smoothing": True,
                "physics_simulation": False,
                "facial_tracking": True
            }
        }

        # データディレクトリ
        self.vr_data_dir = Path("data/vr_avatars")
        self.vr_data_dir.mkdir(parents=True, exist_ok=True)

        logger.info("VR/AR Avatar System initialized")

    async def create_vr_avatar(
        self,
        user_id: str,
        avatar_id: str,
        vr_config: Dict
    ) -> Optional[VRAvatarConfig]:
        """
        VR対応アバターを作成

        Args:
            user_id: ユーザーID
            avatar_id: アバターID
            vr_config: VR設定

        Returns:
            VRアバター設定
        """
        try:
            # セキュリティチェック
            if not await self.security_manager.validate_user_access(user_id, "vr_avatar_create"):
                raise ValueError("Unauthorized VR avatar creation")

            # VR設定の検証
            validated_config = await self._validate_vr_config(vr_config)

            # アニメーションプロファイルの設定
            animation_profile = validated_config.get("animation_profile", "realistic")

            # ハプティック設定の初期化
            haptic_settings = {
                "vibration_intensity": validated_config.get("haptic_intensity", 0.7),
                "feedback_zones": validated_config.get("feedback_zones", ["hands", "head"]),
                "adaptive_feedback": True,
                "gesture_recognition": True
            }

            # インタラクションゾーンの設定
            interaction_zones = [
                {
                    "zone_id": "head",
                    "radius": 0.3,
                    "interaction_type": "gaze",
                    "sensitivity": 0.8
                },
                {
                    "zone_id": "hands",
                    "radius": 0.15,
                    "interaction_type": "gesture",
                    "sensitivity": 0.9
                }
            ]

            # メタバース互換性の設定
            metaverse_compatibility = [
                "decentraland", "sandbox", "somnium_space",
                "cryptovoxels", "horizon_worlds"
            ]

            # VRアバター設定の作成
            vr_avatar_config = VRAvatarConfig(
                avatar_id=avatar_id,
                user_id=user_id,
                vr_model=validated_config["vr_model"],
                animation_profile=animation_profile,
                haptic_settings=haptic_settings,
                interaction_zones=interaction_zones,
                metaverse_compatibility=metaverse_compatibility,
                performance_mode=validated_config.get("performance_mode", "balanced")
            )

            # 設定を保存
            await self._save_vr_avatar_config(vr_avatar_config)

            logger.info(f"VR avatar created successfully: {avatar_id}")
            return vr_avatar_config

        except Exception as e:
            logger.error(f"Failed to create VR avatar: {e}")
            return None

    async def _validate_vr_config(self, vr_config: Dict) -> Dict:
        """VR設定の検証"""

        # 必須フィールドのチェック
        required_fields = ["vr_model", "animation_profile"]
        for field in required_fields:
            if field not in vr_config:
                raise ValueError(f"Missing required VR config field: {field}")

        # VRモデルの検証
        if vr_config["vr_model"] not in self.supported_vr_platforms:
            logger.warning(f"Unsupported VR model: {vr_config['vr_model']}")

        # アニメーションプロファイルの検証
        if vr_config["animation_profile"] not in self.animation_profiles:
            logger.warning(f"Unknown animation profile: {vr_config['animation_profile']}")

        return vr_config

    async def _save_vr_avatar_config(self, vr_config: VRAvatarConfig):
        """VRアバター設定を保存"""

        config_dict = asdict(vr_config)
        config_dict["created_at"] = datetime.now().isoformat()

        config_file = self.vr_data_dir / f"vr_avatar_{vr_config.avatar_id}.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=2)

        logger.info(f"VR avatar config saved: {config_file}")

    async def process_ar_interaction(
        self,
        user_id: str,
        avatar_id: str,
        interaction_data: Dict
    ) -> Optional[ARInteractionData]:
        """
        ARインタラクションを処理

        Args:
            user_id: ユーザーID
            avatar_id: アバターID
            interaction_data: インタラクションデータ

        Returns:
            処理結果のインタラクションデータ
        """
        try:
            # セキュリティチェック
            if not await self.security_manager.validate_user_access(user_id, "ar_interaction"):
                raise ValueError("Unauthorized AR interaction")

            # インタラクションデータの解析
            ar_data = ARInteractionData(
                gesture_type=interaction_data.get("gesture_type", "unknown"),
                confidence_score=interaction_data.get("confidence", 0.0),
                hand_position=interaction_data.get("hand_position", {}),
                eye_tracking=interaction_data.get("eye_tracking", {}),
                voice_commands=interaction_data.get("voice_commands", []),
                environmental_context=interaction_data.get("environment", {})
            )

            # ジェスチャー認識処理
            await self._process_gesture_recognition(ar_data)

            # 視線追跡処理
            await self._process_eye_tracking(ar_data)

            # 音声コマンド処理
            await self._process_voice_commands(ar_data)

            # 環境適応処理
            await self._adapt_to_environment(ar_data)

            # インタラクション結果をログ記録
            await self._log_ar_interaction(user_id, avatar_id, ar_data)

            return ar_data

        except Exception as e:
            logger.error(f"AR interaction processing failed: {e}")
            return None

    async def _process_gesture_recognition(self, ar_data: ARInteractionData):
        """ジェスチャー認識処理"""

        gesture_type = ar_data.gesture_type
        confidence = ar_data.confidence_score

        # 高信頼度のジェスチャーを処理
        if confidence > 0.8:
            if gesture_type == "point":
                logger.info("Point gesture detected - triggering interaction")
            elif gesture_type == "grab":
                logger.info("Grab gesture detected - initiating object manipulation")
            elif gesture_type == "wave":
                logger.info("Wave gesture detected - social interaction")

    async def _process_eye_tracking(self, ar_data: ARInteractionData):
        """視線追跡処理"""

        eye_data = ar_data.eye_tracking

        if eye_data:
            gaze_direction = eye_data.get("gaze_direction", {})
            focus_point = eye_data.get("focus_point", {})

            # 視線ベースのインタラクション
            if gaze_direction and focus_point:
                logger.info(f"Eye tracking: gazing at {focus_point}")

    async def _process_voice_commands(self, ar_data: ARInteractionData):
        """音声コマンド処理"""

        voice_commands = ar_data.voice_commands

        for command in voice_commands:
            if "アバター" in command:
                logger.info(f"Avatar-related voice command: {command}")
            elif "移動" in command:
                logger.info(f"Movement voice command: {command}")

    async def _adapt_to_environment(self, ar_data: ARInteractionData):
        """環境適応処理"""

        environment = ar_data.environmental_context

        if environment:
            lighting = environment.get("lighting", "normal")
            noise_level = environment.get("noise_level", "low")

            # 環境に応じた調整
            if lighting == "dark":
                logger.info("Adapting avatar for dark environment")
            if noise_level == "high":
                logger.info("Adjusting audio sensitivity for noisy environment")

    async def _log_ar_interaction(
        self,
        user_id: str,
        avatar_id: str,
        ar_data: ARInteractionData
    ):
        """ARインタラクションをログ記録"""

        await self.security_manager.log_security_event(
            event_type="ar_interaction",
            user_id=user_id,
            details={
                "avatar_id": avatar_id,
                "gesture_type": ar_data.gesture_type,
                "confidence_score": ar_data.confidence_score,
                "voice_commands_count": len(ar_data.voice_commands),
                "environment_type": ar_data.environmental_context.get("type", "unknown")
            },
            ip_address="system"
        )

    async def get_vr_avatar_config(self, avatar_id: str) -> Optional[VRAvatarConfig]:
        """VRアバター設定を取得"""

        try:
            config_file = self.vr_data_dir / f"vr_avatar_{avatar_id}.json"

            if not config_file.exists():
                return None

            with open(config_file, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)

            # 作成日を除去してVRAvatarConfigを作成
            config_dict.pop("created_at", None)
            return VRAvatarConfig(**config_dict)

        except Exception as e:
            logger.error(f"Failed to load VR avatar config: {e}")
            return None

    async def update_vr_avatar_settings(
        self,
        avatar_id: str,
        user_id: str,
        updates: Dict
    ) -> bool:
        """
        VRアバター設定を更新

        Args:
            avatar_id: アバターID
            user_id: ユーザーID
            updates: 更新データ

        Returns:
            更新成功かどうか
        """
        try:
            # セキュリティチェック
            if not await self.security_manager.validate_user_access(user_id, "vr_avatar_update"):
                raise ValueError("Unauthorized VR avatar update")

            # 現在の設定を取得
            current_config = await self.get_vr_avatar_config(avatar_id)
            if not current_config:
                raise ValueError(f"VR avatar config not found: {avatar_id}")

            # 更新を適用
            for key, value in updates.items():
                if hasattr(current_config, key):
                    setattr(current_config, key, value)

            # 設定を保存
            await self._save_vr_avatar_config(current_config)

            logger.info(f"VR avatar settings updated: {avatar_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update VR avatar settings: {e}")
            return False

    async def generate_webxr_compatibility_report(
        self,
        avatar_id: str
    ) -> Dict[str, Any]:
        """
        WebXR互換性レポートを生成

        Args:
            avatar_id: アバターID

        Returns:
            互換性レポート
        """
        try:
            config = await self.get_vr_avatar_config(avatar_id)
            if not config:
                raise ValueError(f"VR avatar config not found: {avatar_id}")

            # WebXR機能のチェックリスト
            webxr_features = {
                "hand_tracking": True,
                "eye_tracking": config.animation_profile == "realistic",
                "voice_interaction": True,
                "haptic_feedback": bool(config.haptic_settings.get("vibration_intensity", 0)),
                "spatial_audio": True,
                "avatar_customization": True,
                "metaverse_integration": len(config.metaverse_compatibility) > 0
            }

            # サポートするフレームワーク
            supported_frameworks = [
                framework for framework in self.supported_ar_frameworks
                if framework in ["webxr", "arkit", "arcore"]  # WebXR関連のみ
            ]

            # パフォーマンススコア計算
            performance_score = self._calculate_performance_score(config)

            report = {
                "avatar_id": avatar_id,
                "webxr_compatibility_score": sum(webxr_features.values()) / len(webxr_features),
                "supported_frameworks": supported_frameworks,
                "webxr_features": webxr_features,
                "performance_score": performance_score,
                "metaverse_compatibility": config.metaverse_compatibility,
                "recommendations": await self._generate_webxr_recommendations(config),
                "generated_at": datetime.now().isoformat()
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate WebXR report: {e}")
            return {}

    def _calculate_performance_score(self, config: VRAvatarConfig) -> float:
        """パフォーマンススコアを計算"""

        base_score = 50.0

        # アニメーションプロファイルによる調整
        profile_scores = {
            "realistic": 20.0,
            "casual": 10.0,
            "performance": 0.0
        }

        base_score += profile_scores.get(config.animation_profile, 0)

        # ハプティック設定による調整
        if config.haptic_settings.get("adaptive_feedback", False):
            base_score += 10.0

        # メタバース互換性による調整
        base_score += min(len(config.metaverse_compatibility) * 2, 20.0)

        return min(base_score, 100.0)

    async def _generate_webxr_recommendations(self, config: VRAvatarConfig) -> List[str]:
        """WebXR改善の推奨事項を生成"""

        recommendations = []

        if config.animation_profile == "performance":
            recommendations.append("リアルなアニメーションのためにプロファイルを'casual'以上に変更することを検討してください")

        if not config.haptic_settings.get("gesture_recognition", False):
            recommendations.append("ジェスチャー認識を有効にして、より没入感のある体験を実現してください")

        if len(config.metaverse_compatibility) < 3:
            recommendations.append("追加のメタバースプラットフォームへの対応を検討してください")

        return recommendations

    async def get_vr_analytics(
        self,
        user_id: str,
        avatar_id: str,
        time_range: str = "24h"
    ) -> Dict[str, Any]:
        """
        VR使用分析データを取得

        Args:
            user_id: ユーザーID
            avatar_id: アバターID
            time_range: 時間範囲

        Returns:
            分析データ
        """
        try:
            # 実際の実装ではログファイルからデータを収集
            # ここではサンプルデータを返す

            analytics = {
                "user_id": user_id,
                "avatar_id": avatar_id,
                "time_range": time_range,
                "session_count": 15,
                "total_vr_time": "8h 32m",
                "most_used_gestures": ["point", "grab", "wave"],
                "metaverse_visits": ["decentraland", "sandbox"],
                "performance_issues": 2,
                "user_satisfaction_score": 4.2,
                "generated_at": datetime.now().isoformat()
            }

            return analytics

        except Exception as e:
            logger.error(f"Failed to get VR analytics: {e}")
            return {}

# グローバルインスタンス
_vr_system = None

async def get_vr_system() -> VRAvatarSystem:
    """VR/ARシステムのインスタンスを取得"""

    global _vr_system

    if _vr_system is None:
        _vr_system = VRAvatarSystem()

    return _vr_system
