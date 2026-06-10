"""
Cocoa Shared Libraries
共通で使用されるユーティリティ、設定、データモデル
"""

from .config import ConfigManager, get_config
from .database import DatabaseManager, get_db
from .exceptions import CocoaError, SecurityError, ValidationError
from .logger import get_logger, setup_logging
from .models import Avatar, BaseModel, Preset, User
from .utils import generate_id, sanitize_input, validate_uuid

"""
Shared Services for Microservices Architecture

共通機能を提供：
- サービスレジストリとディスカバリ
- サービス間通信
- 共通モデルと設定
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """サービスレジストリとディスカバリ"""

    def __init__(self):
        self.services: Dict[str, Dict[str, Any]] = {}
        self.heartbeats: Dict[str, datetime] = {}
        self.service_timeout = 30  # 秒

    def register_service(self, service_name: str, service_info: Dict[str, Any]) -> bool:
        """サービスを登録"""
        try:
            service_info['registered_at'] = datetime.now(timezone.utc).isoformat()
            service_info['last_heartbeat'] = datetime.now(timezone.utc).isoformat()

            self.services[service_name] = service_info
            self.heartbeats[service_name] = datetime.now(timezone.utc)

            logger.info(f"サービス登録: {service_name}")
            return True

        except Exception as e:
            logger.error(f"サービス登録エラー: {e}")
            return False

    def unregister_service(self, service_name: str) -> bool:
        """サービスを登録解除"""
        if service_name in self.services:
            del self.services[service_name]
            del self.heartbeats[service_name]
            logger.info(f"サービス登録解除: {service_name}")
            return True
        return False

    def heartbeat(self, service_name: str) -> bool:
        """サービスからのハートビートを記録"""
        if service_name in self.services:
            self.heartbeats[service_name] = datetime.now(timezone.utc)
            self.services[service_name]['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def discover_service(self, service_name: str) -> Optional[Dict[str, Any]]:
        """サービス情報を取得"""
        if service_name not in self.services:
            return None

        # タイムアウトチェック
        if datetime.now(timezone.utc) - self.heartbeats[service_name] > timedelta(seconds=self.service_timeout):
            logger.warning(f"サービスタイムアウト: {service_name}")
            self.unregister_service(service_name)
            return None

        return self.services[service_name]

    def get_all_services(self) -> Dict[str, Dict[str, Any]]:
        """全サービス情報を取得"""
        # タイムアウトチェック
        current_time = datetime.now(timezone.utc)
        timeout_services = [
            name for name, heartbeat in self.heartbeats.items()
            if current_time - heartbeat > timedelta(seconds=self.service_timeout)
        ]

        for service_name in timeout_services:
            self.unregister_service(service_name)

        return self.services.copy()

    def get_service_health(self) -> Dict[str, Any]:
        """サービスヘルス情報を取得"""
        total_services = len(self.services)
        healthy_services = len([
            name for name, heartbeat in self.heartbeats.items()
            if datetime.now(timezone.utc) - heartbeat <= timedelta(seconds=self.service_timeout)
        ])

        return {
            'total_services': total_services,
            'healthy_services': healthy_services,
            'unhealthy_services': total_services - healthy_services,
            'registry_size': len(self.services)
        }


class ServiceCommunicator:
    """サービス間通信クライアント"""

    def __init__(self, service_registry: ServiceRegistry):
        self.registry = service_registry
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def call_service(self, service_name: str, endpoint: str, method: str = 'GET', data: Dict[str, Any] = None) -> Dict[str, Any]:
        """サービスを呼び出し"""
        service_info = self.registry.discover_service(service_name)
        if not service_info:
            return {'error': f'サービスが見つかりません: {service_name}'}

        if not self.session:
            return {'error': 'セッションが初期化されていません'}

        try:
            url = f"{service_info['url']}{endpoint}"

            if method == 'GET':
                async with self.session.get(url) as response:
                    return await response.json()
            elif method == 'POST':
                async with self.session.post(url, json=data) as response:
                    return await response.json()
            elif method == 'PUT':
                async with self.session.put(url, json=data) as response:
                    return await response.json()
            elif method == 'DELETE':
                async with self.session.delete(url) as response:
                    return await response.json()
            else:
                return {'error': f'サポートされていないメソッド: {method}'}

        except Exception as e:
            logger.error(f"サービス呼び出しエラー ({service_name}): {e}")
            return {'error': str(e)}


# グローバルインスタンス
_service_registry: Optional[ServiceRegistry] = None


def get_service_registry() -> ServiceRegistry:
    """サービスレジストリを取得"""
    global _service_registry
    if _service_registry is None:
        _service_registry = ServiceRegistry()
    return _service_registry


def initialize_shared_services():
    """共有サービスを初期化"""
    global _service_registry
    _service_registry = ServiceRegistry()
    logger.info("共有サービスを初期化しました")


__version__ = "2.1.0"
__all__ = [
    "ConfigManager", "get_config",
    "get_logger", "setup_logging",
    "DatabaseManager", "get_db",
    "BaseModel", "Avatar", "User", "Preset",
    "CocoaError", "ValidationError", "SecurityError",
    "generate_id", "validate_uuid", "sanitize_input"
]
