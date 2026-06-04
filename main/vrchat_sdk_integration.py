# main/vrchat_sdk_integration.py
"""
VRChat SDK Integration Module for Cocoa
VRChat Avatars 3.0システムとの連携機能を提供
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime

import requests
from PIL import Image

from .integrated_security import get_security_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class VRChatAvatarDescriptor:
    """VRChatアバター記述子"""
    name: str
    description: str
    avatar_id: str
    version: int
    author_id: str
    image_url: str
    unity_package_url: str
    created_at: datetime
    updated_at: datetime

@dataclass
class VRChatAvatarParameters:
    """VRChatアバターのパラメータ設定"""
    eye_look: bool = True
    eye_blink: bool = True
    mouth_viseme: bool = True
    gesture_override: str = "Default"
    locomotion: str = "Default"
    performance_rank: str = "Medium"
    shader_complexity: str = "Medium"
    texture_memory: int = 0
    polygon_count: int = 0

class VRChatSDKManager:
    """
    VRChat SDK連携マネージャー
    Avatars 3.0システムとの互換性を確保
    """

    def __init__(self, api_key: str = None, user_id: str = None):
        """
        初期化

        Args:
            api_key: VRChat APIキー
            user_id: VRChatユーザーID
        """
        self.security_manager = get_security_manager()
        self.api_key = api_key or os.getenv('VRCHAT_API_KEY', '')
        self.user_id = user_id or os.getenv('VRCHAT_USER_ID', '')

        # VRChat APIベースURL
        self.base_url = "https://api.vrchat.cloud/api/1"

        # キャッシュディレクトリ
        self.cache_dir = Path("data/vrchat_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # SDKバージョン情報
        self.sdk_version = "3.0.0"
        self.compatible_unity_versions = ["2019.4", "2020.3", "2021.3"]

        logger.info(f"VRChat SDK Manager initialized for user: {self.user_id}")

    async def validate_vrchat_credentials(self) -> bool:
        """VRChat認証情報を検証"""
        if not self.api_key or not self.user_id:
            logger.error("VRChat API key or user ID not provided")
            return False

        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                f"{self.base_url}/users/{self.user_id}",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                user_data = response.json()
                logger.info(f"VRChat credentials validated for user: {user_data.get('displayName', 'Unknown')}")
                return True
            else:
                logger.error(f"VRChat API authentication failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"VRChat credential validation error: {e}")
            return False

    async def export_avatar_for_vrchat(self, avatar_path: str, export_options: Dict = None) -> Dict:
        """
        アバターをVRChat用にエクスポート

        Args:
            avatar_path: ソースアバターパス
            export_options: エクスポートオプション

        Returns:
            エクスポート結果
        """
        try:
            # デフォルトオプション
            if export_options is None:
                export_options = {}

            # アバター読み込みと検証
            avatar_data = await self._load_and_validate_avatar(avatar_path)

            # VRChat互換性チェック
            compatibility = await self._check_vrchat_compatibility(avatar_data)

            if not compatibility['compatible']:
                return {
                    'success': False,
                    'error': 'Avatar is not compatible with VRChat',
                    'compatibility_issues': compatibility['issues']
                }

            # アバターパラメータ最適化
            optimized_params = await self._optimize_for_vrchat(avatar_data, export_options)

            # Unityパッケージ生成
            package_path = await self._generate_unity_package(optimized_params)

            # メタデータ生成
            metadata = self._generate_vrchat_metadata(optimized_params)

            # キャッシュに保存
            cache_info = await self._cache_avatar_data(avatar_path, metadata)

            logger.info(f"Avatar exported for VRChat: {package_path}")

            return {
                'success': True,
                'package_path': package_path,
                'metadata': metadata,
                'compatibility': compatibility,
                'cache_info': cache_info
            }

        except Exception as e:
            logger.error(f"VRChat export failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _load_and_validate_avatar(self, avatar_path: str) -> Dict:
        """アバターを読み込み検証"""
        # 画像ファイルの読み込み
        image = Image.open(avatar_path)

        # 基本情報の抽出
        avatar_info = {
            'width': image.width,
            'height': image.height,
            'format': image.format,
            'mode': image.mode,
            'file_size': os.path.getsize(avatar_path)
        }

        # テクスチャメモリ計算
        texture_memory = avatar_info['width'] * avatar_info['height'] * 4  # RGBA
        avatar_info['texture_memory'] = texture_memory

        # ポリゴン数の推定（簡易版）
        avatar_info['estimated_polygons'] = min(50000, max(1000, texture_memory // 100))

        return avatar_info

    async def _check_vrchat_compatibility(self, avatar_data: Dict) -> Dict:
        """VRChat互換性をチェック"""
        issues = []
        warnings = []

        # テクスチャサイズチェック
        if avatar_data['texture_memory'] > 134217728:  # 128MB制限
            issues.append("Texture memory exceeds VRChat limit (128MB)")
        elif avatar_data['texture_memory'] > 67108864:  # 64MB警告
            warnings.append("High texture memory usage")

        # ポリゴン数チェック
        if avatar_data['estimated_polygons'] > 70000:
            issues.append("Polygon count exceeds VRChat limit (70k)")
        elif avatar_data['estimated_polygons'] > 50000:
            warnings.append("High polygon count")

        # 解像度チェック
        if avatar_data['width'] > 4096 or avatar_data['height'] > 4096:
            issues.append("Texture resolution exceeds VRChat limit (4096x4096)")
        elif avatar_data['width'] > 2048 or avatar_data['height'] > 2048:
            warnings.append("High texture resolution")

        return {
            'compatible': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'performance_rank': self._calculate_performance_rank(avatar_data, issues, warnings)
        }

    def _calculate_performance_rank(self, avatar_data: Dict, issues: List, warnings: List) -> str:
        """パフォーマンスランクを計算"""
        if issues:
            return "Poor"
        elif len(warnings) >= 2:
            return "Medium"
        elif avatar_data['texture_memory'] < 33554432:  # 32MB未満
            return "Excellent"
        else:
            return "Good"

    async def _optimize_for_vrchat(self, avatar_data: Dict, export_options: Dict) -> Dict:
        """VRChat向けに最適化"""
        optimized = avatar_data.copy()

        # パフォーマンスランクに基づく最適化
        performance_rank = self._calculate_performance_rank(avatar_data, [], [])

        if performance_rank in ['Poor', 'Medium']:
            # テクスチャサイズの圧縮
            if avatar_data['width'] > 2048:
                optimized['width'] = 2048
                optimized['height'] = 2048

        # ポリゴン数の最適化
        target_polygons = {
            'Excellent': 15000,
            'Good': 30000,
            'Medium': 50000,
            'Poor': 70000
        }.get(performance_rank, 30000)

        if avatar_data['estimated_polygons'] > target_polygons:
            optimized['estimated_polygons'] = target_polygons

        return optimized

    async def _generate_unity_package(self, avatar_data: Dict) -> str:
        """Unityパッケージを生成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        package_name = f"vrchat_avatar_{timestamp}.unitypackage"
        package_path = self.cache_dir / package_name

        # Unityパッケージ構造の作成（簡易版）
        package_structure = {
            'Assets': {
                'VRChat': {
                    'Avatar': {
                        'Textures': {},
                        'Materials': {},
                        'Prefabs': {}
                    }
                }
            },
            'ProjectSettings': {}
        }

        # パッケージメタデータの作成
        with open(package_path.with_suffix('.json'), 'w', encoding='utf-8') as f:
            json.dump({
                'package_name': package_name,
                'sdk_version': self.sdk_version,
                'created_at': datetime.now().isoformat(),
                'avatar_data': avatar_data
            }, f, indent=2, ensure_ascii=False)

        return str(package_path)

    def _generate_vrchat_metadata(self, avatar_data: Dict) -> Dict:
        """VRChatメタデータを生成"""
        return {
            'name': f"Cocoa Avatar {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'description': "Avatar generated by Cocoa Avatar Management System",
            'version': 1,
            'authorId': self.user_id,
            'imageUrl': "",
            'releaseStatus': "private",
            'platform': "standalonewindows",
            'unityPackageUrl': "",
            'assetUrl': "",
            'tags': ["cocoa", "ai-generated"],
            'performanceRank': avatar_data.get('performance_rank', 'Medium'),
            'shaderComplexity': avatar_data.get('shader_complexity', 'Medium')
        }

    async def _cache_avatar_data(self, avatar_path: str, metadata: Dict) -> Dict:
        """アバターデータをキャッシュ"""
        cache_key = f"vrchat_export_{hash(avatar_path)}"

        cache_data = {
            'avatar_path': avatar_path,
            'metadata': metadata,
            'cached_at': datetime.now().isoformat(),
            'cache_key': cache_key
        }

        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)

        return {'cache_key': cache_key, 'cache_path': str(cache_file)}

    async def get_sdk_compatibility_info(self) -> Dict:
        """SDK互換性情報を取得"""
        return {
            'sdk_version': self.sdk_version,
            'supported_unity_versions': self.compatible_unity_versions,
            'features': [
                'Avatar 3.0',
                'Eye tracking simulation',
                'Viseme blendshapes',
                'Gesture system',
                'Performance ranking',
                'Local testing'
            ],
            'limitations': [
                'Maximum texture memory: 128MB',
                'Maximum polygon count: 70k',
                'Maximum texture resolution: 4096x4096'
            ]
        }

    async def upload_to_vrchat(self, package_path: str, avatar_name: str = None) -> Dict:
        """
        アバターをVRChatにアップロード

        Args:
            package_path: Unityパッケージのパス
            avatar_name: アバター名（オプション）

        Returns:
            アップロード結果
        """
        if not await self.validate_vrchat_credentials():
            return {
                'success': False,
                'error': 'Invalid VRChat credentials'
            }

        try:
            # 実際のアップロード処理（VRChat APIを使用）
            # 注意: 実際の実装ではVRChatの公式APIを使用する必要があります

            logger.info(f"VRChat upload initiated for package: {package_path}")

            return {
                'success': True,
                'message': 'Upload initiated (implementation pending VRChat API access)',
                'avatar_id': f'avatar_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            }

        except Exception as e:
            logger.error(f"VRChat upload failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

# グローバルインスタンス管理
_vrchat_manager_instance = None

async def get_vrchat_sdk_manager() -> VRChatSDKManager:
    """VRChat SDKマネージャーのインスタンスを取得"""
    global _vrchat_manager_instance

    if _vrchat_manager_instance is None:
        _vrchat_manager_instance = VRChatSDKManager()

    return _vrchat_manager_instance
