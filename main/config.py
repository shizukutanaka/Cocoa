"""
集中管理設定モジュール
環境変数と設定ファイルの一元管理

設計原則:
- Single Source of Truth: 設定値を一箇所で管理
- 環境による自動切り替え
- デフォルト値の提供
- 型安全性とバリデーション
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class APIConfig:
    """API設定"""
    host: str = os.environ.get("API_HOST", "0.0.0.0")
    port: int = int(os.environ.get("API_PORT", "8000"))
    debug: bool = os.environ.get("API_DEBUG", "false").lower() == "true"
    cors_origins: Optional[list] = None

    def __post_init__(self):
        if self.cors_origins is None:
            origins_env = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
            self.cors_origins = [o.strip() for o in origins_env.split(",")]


@dataclass
class DatabaseConfig:
    """データベース設定"""
    host: str = os.environ.get("DB_HOST", "localhost")
    port: int = int(os.environ.get("DB_PORT", "5432"))
    database: str = os.environ.get("DB_NAME", "cocoa")
    user: str = os.environ.get("DB_USER", "postgres")
    password: str = os.environ.get("DB_PASSWORD", "")
    pool_size: int = int(os.environ.get("DB_POOL_SIZE", "10"))


@dataclass
class SecurityConfig:
    """セキュリティ設定"""
    secret_key: str = os.environ.get("SECRET_KEY", "change-me-in-production")
    encryption_key: str = os.environ.get("ENCRYPTION_KEY", "change-me-in-production")
    admin_password: str = os.environ.get("ADMIN_PASSWORD", "")
    enable_2fa: bool = os.environ.get("ENABLE_2FA", "true").lower() == "true"
    session_timeout_minutes: int = int(os.environ.get("SESSION_TIMEOUT", "60"))

    def validate(self):
        """本番環境用の設定値検証（呼び元が適切なタイミングで呼ぶこと）"""
        if self.secret_key == "change-me-in-production":
            raise ValueError("SECRET_KEY must be set in production")
        if self.encryption_key == "change-me-in-production":
            raise ValueError("ENCRYPTION_KEY must be set in production")


@dataclass
class BackupConfig:
    """バックアップ設定"""
    enabled: bool = os.environ.get("BACKUP_ENABLED", "true").lower() == "true"
    retention_days: int = int(os.environ.get("BACKUP_RETENTION_DAYS", "30"))
    path: str = os.environ.get("BACKUP_PATH", "data/backups")
    verify: bool = os.environ.get("BACKUP_VERIFY", "true").lower() == "true"


@dataclass
class LoggingConfig:
    """ロギング設定"""
    level: str = os.environ.get("LOG_LEVEL", "INFO")
    file_path: str = os.environ.get("LOG_FILE", "logs/cocoa.log")
    max_bytes: int = int(os.environ.get("LOG_MAX_BYTES", "10485760"))  # 10MB
    backup_count: int = int(os.environ.get("LOG_BACKUP_COUNT", "10"))


class Config:
    """統合設定マネージャー"""

    def __init__(self, env: Optional[str] = None):
        self.environment = env or os.environ.get("ENVIRONMENT", "development")
        self.api = APIConfig()
        self.database = DatabaseConfig()
        self.security = SecurityConfig()
        self.backup = BackupConfig()
        self.logging = LoggingConfig()

        # 本番環境の検証
        if self.environment == "production":
            self.security.validate()

    @classmethod
    def from_file(cls, path: str) -> "Config":
        """設定ファイルから読み込み"""
        try:
            with open(path, encoding="utf-8") as f:
                config_dict = json.load(f)

            config = cls()

            # APIConfig
            if "api" in config_dict:
                api_conf = config_dict["api"]
                config.api = APIConfig(**api_conf)

            # DatabaseConfig
            if "database" in config_dict:
                db_conf = config_dict["database"]
                config.database = DatabaseConfig(**db_conf)

            # SecurityConfig
            if "security" in config_dict:
                sec_conf = config_dict["security"]
                config.security = SecurityConfig(**sec_conf)

            # BackupConfig
            if "backup" in config_dict:
                backup_conf = config_dict["backup"]
                config.backup = BackupConfig(**backup_conf)

            # LoggingConfig
            if "logging" in config_dict:
                log_conf = config_dict["logging"]
                config.logging = LoggingConfig(**log_conf)

            return config

        except Exception as e:
            logger.error(f"Failed to load config from {path}: {e}")
            raise

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式で取得"""
        return {
            "environment": self.environment,
            "api": {
                "host": self.api.host,
                "port": self.api.port,
                "debug": self.api.debug,
                "cors_origins": self.api.cors_origins,
            },
            "database": {
                "host": self.database.host,
                "port": self.database.port,
                "database": self.database.database,
                "user": self.database.user,
                "pool_size": self.database.pool_size,
            },
            "security": {
                "enable_2fa": self.security.enable_2fa,
                "session_timeout_minutes": self.security.session_timeout_minutes,
            },
            "backup": {
                "enabled": self.backup.enabled,
                "retention_days": self.backup.retention_days,
                "path": self.backup.path,
                "verify": self.backup.verify,
            },
            "logging": {
                "level": self.logging.level,
                "file_path": self.logging.file_path,
                "max_bytes": self.logging.max_bytes,
                "backup_count": self.logging.backup_count,
            }
        }


# グローバル設定インスタンス
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """グローバル設定インスタンスを取得"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def init_config(path: Optional[str] = None) -> Config:
    """設定を初期化"""
    global _config_instance

    if path and Path(path).exists():
        _config_instance = Config.from_file(path)
    else:
        _config_instance = Config()

    return _config_instance
