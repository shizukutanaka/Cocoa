"""
共通設定マネージャー
全サービスで共有される設定を管理
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging


@dataclass
class ServiceConfig:
    """サービス設定"""
    name: str
    port: int
    host: str = "0.0.0.0"
    debug: bool = False
    database_url: Optional[str] = None
    redis_url: Optional[str] = None
    log_level: str = "INFO"


@dataclass
class CocoaConfig:
    """全体設定"""
    environment: str
    services: Dict[str, ServiceConfig]
    security: Dict[str, Any]
    database: Dict[str, Any]
    ai: Dict[str, Any]
    collaboration: Dict[str, Any]


class ConfigManager:
    """設定マネージャー"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/config.json"
        self._config: Optional[CocoaConfig] = None
        self._logger = logging.getLogger(__name__)

    def load_config(self) -> CocoaConfig:
        """設定ファイルから読み込み"""
        try:
            if not Path(self.config_path).exists():
                self._create_default_config()

            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 環境変数でオーバーライド
            self._apply_env_overrides(data)

            self._config = self._parse_config(data)
            return self._config

        except Exception as e:
            self._logger.error(f"設定読み込みエラー: {e}")
            raise

    def _create_default_config(self):
        """デフォルト設定ファイル作成"""
        config_dir = Path(self.config_path).parent
        config_dir.mkdir(exist_ok=True)

        default_config = {
            "environment": os.getenv("ENVIRONMENT", "development"),
            "services": {
                "api-gateway": {
                    "name": "api-gateway",
                    "port": int(os.getenv("API_GATEWAY_PORT", "8000")),
                    "host": os.getenv("API_GATEWAY_HOST", "0.0.0.0"),
                    "debug": os.getenv("DEBUG", "false").lower() == "true"
                },
                "avatar-service": {
                    "name": "avatar-service",
                    "port": int(os.getenv("AVATAR_SERVICE_PORT", "8001")),
                    "host": os.getenv("AVATAR_SERVICE_HOST", "0.0.0.0"),
                    "debug": os.getenv("DEBUG", "false").lower() == "true",
                    "database_url": os.getenv("AVATAR_DB_URL", "sqlite:///data/avatar.db")
                },
                "security-service": {
                    "name": "security-service",
                    "port": int(os.getenv("SECURITY_SERVICE_PORT", "8002")),
                    "host": os.getenv("SECURITY_SERVICE_HOST", "0.0.0.0"),
                    "debug": os.getenv("DEBUG", "false").lower() == "true",
                    "database_url": os.getenv("SECURITY_DB_URL", "sqlite:///data/security.db")
                },
                "collaboration-service": {
                    "name": "collaboration-service",
                    "port": int(os.getenv("COLLABORATION_SERVICE_PORT", "8003")),
                    "host": os.getenv("COLLABORATION_SERVICE_HOST", "0.0.0.0"),
                    "debug": os.getenv("DEBUG", "false").lower() == "true",
                    "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379")
                },
                "ai-service": {
                    "name": "ai-service",
                    "port": int(os.getenv("AI_SERVICE_PORT", "8004")),
                    "host": os.getenv("AI_SERVICE_HOST", "0.0.0.0"),
                    "debug": os.getenv("DEBUG", "false").lower() == "true"
                }
            },
            "security": {
                "secret_key": os.getenv("COCOA_SECRET_KEY", ""),
                "encryption_key": os.getenv("COCOA_ENCRYPTION_KEY", ""),
                "jwt_expiry_hours": int(os.getenv("JWT_EXPIRY_HOURS", "24")),
                "max_login_attempts": int(os.getenv("MAX_LOGIN_ATTEMPTS", "5")),
                "lockout_duration_minutes": int(os.getenv("LOCKOUT_DURATION_MINUTES", "15"))
            },
            "database": {
                "main_database_url": os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/cocoa"),
                "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
                "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20"))
            },
            "ai": {
                "model_path": os.getenv("AI_MODEL_PATH", "models/"),
                "enable_gpu": os.getenv("AI_ENABLE_GPU", "false").lower() == "true",
                "batch_size": int(os.getenv("AI_BATCH_SIZE", "32")),
                "max_tokens": int(os.getenv("AI_MAX_TOKENS", "512"))
            },
            "collaboration": {
                "max_users_per_room": int(os.getenv("MAX_USERS_PER_ROOM", "50")),
                "message_history_limit": int(os.getenv("MESSAGE_HISTORY_LIMIT", "1000")),
                "enable_voice_chat": os.getenv("ENABLE_VOICE_CHAT", "false").lower() == "true",
                "enable_screen_share": os.getenv("ENABLE_SCREEN_SHARE", "false").lower() == "true"
            }
        }

        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)

    def _apply_env_overrides(self, data: Dict[str, Any]):
        """環境変数で設定をオーバーライド"""
        # サービス設定のオーバーライド
        for service_name, service_config in data.get("services", {}).items():
            for key in ["port", "host", "debug"]:
                env_key = f"{service_name.upper()}_{key.upper()}"
                if env_key in os.environ:
                    if key == "port":
                        service_config[key] = int(os.environ[env_key])
                    elif key == "debug":
                        service_config[key] = os.environ[env_key].lower() == "true"
                    else:
                        service_config[key] = os.environ[env_key]

    def _parse_config(self, data: Dict[str, Any]) -> CocoaConfig:
        """設定データをパース"""
        services = {}
        for name, config in data.get("services", {}).items():
            services[name] = ServiceConfig(**config)

        return CocoaConfig(
            environment=data["environment"],
            services=services,
            security=data["security"],
            database=data["database"],
            ai=data["ai"],
            collaboration=data["collaboration"]
        )

    def get_service_config(self, service_name: str) -> ServiceConfig:
        """サービス設定取得"""
        if not self._config:
            self.load_config()
        return self._config.services[service_name]

    def get_config(self) -> CocoaConfig:
        """全体設定取得"""
        if not self._config:
            self.load_config()
        return self._config


# グローバルインスタンス
_config_manager: Optional[ConfigManager] = None


def get_config() -> CocoaConfig:
    """グローバル設定取得"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.get_config()


def reset_config():
    """設定をリセット（テスト用）"""
    global _config_manager
    _config_manager = None
