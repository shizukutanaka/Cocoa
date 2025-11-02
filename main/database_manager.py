"""
PostgreSQLデータベース統合モジュール

Production-gradeのデータベース統合機能を提供し、
スケーラブルで信頼性の高いデータ永続化を実現します。
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, JSON, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError
import alembic
from alembic.config import Config
from alembic import command

logger = logging.getLogger(__name__)

# 型定義
T = TypeVar('T')
Base = declarative_base()

# データベース設定のデフォルト値
DEFAULT_DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'cocoa_db'),
    'username': os.getenv('DB_USER', 'cocoa_user'),
    'password': os.getenv('DB_PASSWORD', 'cocoa_password'),
    'pool_size': int(os.getenv('DB_POOL_SIZE', '10')),
    'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', '20')),
    'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', '30')),
    'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', '3600')),
    'echo': os.getenv('DB_ECHO', 'false').lower() == 'true'
}

class DatabaseManager:
    """PostgreSQLデータベースマネージャー"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """データベースマネージャーを初期化"""
        self.config = {**DEFAULT_DB_CONFIG, **(config or {})}
        self._engine = None
        self._session_factory = None
        self._is_initialized = False

    @property
    def engine(self):
        """SQLAlchemyエンジンを取得"""
        if self._engine is None:
            self._initialize_engine()
        return self._engine

    @property
    def session_factory(self):
        """セッションファクトリーを取得"""
        if self._session_factory is None:
            self._initialize_session_factory()
        return self._session_factory

    def _initialize_engine(self):
        """データベースエンジンを初期化"""
        try:
            # 接続文字列の構築
            connection_string = (
                f"postgresql://{self.config['username']}:{self.config['password']}"
                f"@{self.config['host']}:{self.config['port']}/{self.config['database']}"
            )

            # エンジンの作成
            self._engine = create_engine(
                connection_string,
                poolclass=QueuePool,
                pool_size=self.config['pool_size'],
                max_overflow=self.config['max_overflow'],
                pool_timeout=self.config['pool_timeout'],
                pool_recycle=self.config['pool_recycle'],
                echo=self.config['echo'],
                future=True
            )

            logger.info(f"Database engine initialized for {self.config['host']}:{self.config['port']}")

        except Exception as e:
            logger.error(f"Failed to initialize database engine: {e}")
            raise

    def _initialize_session_factory(self):
        """セッションファクトリーを初期化"""
        try:
            self._session_factory = sessionmaker(bind=self.engine)
            self._is_initialized = True
            logger.info("Database session factory initialized")
        except Exception as e:
            logger.error(f"Failed to initialize session factory: {e}")
            raise

    def create_tables(self):
        """データベーステーブルを作成"""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise

    def drop_tables(self):
        """データベーステーブルを削除（開発用）"""
        try:
            Base.metadata.drop_all(self.engine)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error(f"Failed to drop tables: {e}")
            raise

    def run_migrations(self, migration_path: str = "alembic"):
        """データベースマイグレーションを実行"""
        try:
            alembic_cfg = Config(f"{migration_path}/alembic.ini")
            command.upgrade(alembic_cfg, "head")
            logger.info("Database migrations completed")
        except Exception as e:
            logger.error(f"Failed to run migrations: {e}")
            raise

    @contextmanager
    def get_session(self):
        """データベースセッションを取得（コンテキストマネージャー）"""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def test_connection(self) -> bool:
        """データベース接続をテスト"""
        try:
            with self.get_session() as session:
                session.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False


# データベースモデル定義
class User(Base):
    """ユーザー情報テーブル"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # リレーションシップ
    avatars = relationship("Avatar", back_populates="owner")
    audit_logs = relationship("AuditLog", back_populates="user")


class Avatar(Base):
    """アバター情報テーブル"""
    __tablename__ = "avatars"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    avatar_id = Column(String(100), unique=True, index=True, nullable=False)
    parameters = Column(JSON, nullable=False)  # アバターパラメータのJSON
    preset_data = Column(JSON, nullable=True)  # プリセットデータ
    thumbnail_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 外部キー
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # リレーションシップ
    owner = relationship("User", back_populates="avatars")
    sessions = relationship("AvatarSession", back_populates="avatar")


class AvatarSession(Base):
    """アバターセッションテーブル"""
    __tablename__ = "avatar_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    avatar_id = Column(Integer, ForeignKey("avatars.id"), nullable=False)
    status = Column(String(20), default="active")  # active, inactive, error
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    metrics = Column(JSON, nullable=True)  # セッションメトリクス
    error_log = Column(Text, nullable=True)

    # リレーションシップ
    avatar = relationship("Avatar", back_populates="sessions")


class Preset(Base):
    """プリセット情報テーブル"""
    __tablename__ = "presets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    preset_data = Column(JSON, nullable=False)
    category = Column(String(50), nullable=True)
    tags = Column(JSON, nullable=True)  # タグの配列
    version = Column(String(20), default="1.0.0")
    is_public = Column(Boolean, default=False)
    download_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 外部キー
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # リレーションシップ
    creator = relationship("User")


class AuditLog(Base):
    """監査ログテーブル"""
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # create, update, delete, login, etc.
    resource_type = Column(String(50), nullable=False)  # user, avatar, preset, system
    resource_id = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)

    # リレーションシップ
    user = relationship("User", back_populates="audit_logs")


class SystemMetrics(Base):
    """システムメトリクステーブル"""
    __tablename__ = "system_metrics"

    id = Column(BigInteger, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    metric_type = Column(String(50), nullable=False)  # cpu, memory, disk, network
    value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)  # %, bytes, count, etc.
    metadata = Column(JSON, nullable=True)


class SecurityAlert(Base):
    """セキュリティ警告テーブル"""
    __tablename__ = "security_alerts"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    alert_type = Column(String(50), nullable=False)  # intrusion, anomaly, policy_violation
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    source_ip = Column(String(45), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # リレーションシップ
    user = relationship("User", foreign_keys=[user_id])
    resolver = relationship("User", foreign_keys=[resolved_by])


# リポジトリパターン実装
class BaseRepository(Generic[T]):
    """ベースリポジトリクラス"""

    def __init__(self, model: Type[T], db_manager: DatabaseManager):
        self.model = model
        self.db_manager = db_manager

    def get_by_id(self, session: Session, id: int) -> Optional[T]:
        """IDでレコードを取得"""
        return session.query(self.model).filter(self.model.id == id).first()

    def get_all(self, session: Session, limit: Optional[int] = None, offset: Optional[int] = None) -> List[T]:
        """全レコードを取得"""
        query = session.query(self.model)
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        return query.all()

    def create(self, session: Session, **kwargs) -> T:
        """新しいレコードを作成"""
        instance = self.model(**kwargs)
        session.add(instance)
        session.flush()  # IDを取得するためにflush
        return instance

    def update(self, session: Session, instance: T, **kwargs) -> T:
        """レコードを更新"""
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        return instance

    def delete(self, session: Session, instance: T):
        """レコードを削除"""
        session.delete(instance)


# 具体的なリポジトリクラス
class UserRepository(BaseRepository[User]):
    """ユーザーリポジトリ"""

    def get_by_username(self, session: Session, username: str) -> Optional[User]:
        return session.query(User).filter(User.username == username).first()

    def get_by_email(self, session: Session, email: str) -> Optional[User]:
        return session.query(User).filter(User.email == email).first()


class AvatarRepository(BaseRepository[Avatar]):
    """アバターリポジトリ"""

    def get_by_avatar_id(self, session: Session, avatar_id: str) -> Optional[Avatar]:
        return session.query(Avatar).filter(Avatar.avatar_id == avatar_id).first()

    def get_by_owner(self, session: Session, owner_id: int) -> List[Avatar]:
        return session.query(Avatar).filter(Avatar.owner_id == owner_id).all()


class AuditLogRepository(BaseRepository[AuditLog]):
    """監査ログ"""

    def get_recent_logs(self, session: Session, hours: int = 24) -> List[AuditLog]:
        """最近のログを取得"""
        since = datetime.utcnow() - timedelta(hours=hours)
        return session.query(AuditLog).filter(AuditLog.timestamp >= since).all()

    def get_logs_by_user(self, session: Session, user_id: int, limit: int = 100) -> List[AuditLog]:
        """ユーザーのログを取得"""
        return session.query(AuditLog).filter(AuditLog.user_id == user_id).limit(limit).all()


# データベースサービスクラス
class DatabaseService:
    """データベースサービスクラス"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.user_repo = UserRepository(User, db_manager)
        self.avatar_repo = AvatarRepository(Avatar, db_manager)
        self.audit_repo = AuditLogRepository(AuditLog, db_manager)

    def create_user(self, username: str, email: str, password_hash: str) -> User:
        """新しいユーザーを作成"""
        with self.db_manager.get_session() as session:
            return self.user_repo.create(
                session,
                username=username,
                email=email,
                password_hash=password_hash
            )

    def get_user_by_username(self, username: str) -> Optional[User]:
        """ユーザー名でユーザーを取得"""
        with self.db_manager.get_session() as session:
            return self.user_repo.get_by_username(session, username)

    def create_avatar(self, name: str, avatar_id: str, owner_id: int, parameters: Dict) -> Avatar:
        """新しいアバターを作成"""
        with self.db_manager.get_session() as session:
            return self.avatar_repo.create(
                session,
                name=name,
                avatar_id=avatar_id,
                owner_id=owner_id,
                parameters=parameters
            )

    def log_audit_event(self, action: str, resource_type: str, user_id: Optional[int] = None,
                       resource_id: Optional[str] = None, details: Optional[Dict] = None,
                       ip_address: Optional[str] = None) -> AuditLog:
        """監査ログを記録"""
        with self.db_manager.get_session() as session:
            return self.audit_repo.create(
                session,
                action=action,
                resource_type=resource_type,
                user_id=user_id,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
                success=True
            )

    def get_system_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """システムメトリクスのサマリーを取得"""
        with self.db_manager.get_session() as session:
            since = datetime.utcnow() - timedelta(hours=hours)

            # 各メトリクスタイプの最新値を取得
            latest_metrics = {}
            for metric_type in ['cpu', 'memory', 'disk_io', 'network_io']:
                metric = session.query(SystemMetrics).filter(
                    SystemMetrics.metric_type == metric_type,
                    SystemMetrics.timestamp >= since
                ).order_by(SystemMetrics.timestamp.desc()).first()

                if metric:
                    latest_metrics[metric_type] = {
                        'value': metric.value,
                        'unit': metric.unit,
                        'timestamp': metric.timestamp.isoformat()
                    }

            return {
                'time_range_hours': hours,
                'metrics': latest_metrics,
                'generated_at': datetime.utcnow().isoformat()
            }


# グローバルデータベースマネージャー
_db_manager: Optional[DatabaseManager] = None
_db_service: Optional[DatabaseService] = None


def get_database_manager() -> DatabaseManager:
    """データベースマネージャーのシングルトンインスタンスを取得"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_database_service() -> DatabaseService:
    """データベースサービスのシングルトンインスタンスを取得"""
    global _db_service
    if _db_service is None:
        db_manager = get_database_manager()
        _db_service = DatabaseService(db_manager)
    return _db_service


def initialize_database():
    """データベースを初期化"""
    try:
        db_manager = get_database_manager()
        db_manager.create_tables()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


# データベースヘルパー関数
def log_audit_event(action: str, resource_type: str, user_id: Optional[int] = None,
                   resource_id: Optional[str] = None, details: Optional[Dict] = None,
                   ip_address: Optional[str] = None):
    """監査イベントを記録（便利関数）"""
    try:
        db_service = get_database_service()
        db_service.log_audit_event(
            action=action,
            resource_type=resource_type,
            user_id=user_id,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")


def get_user_avatars(user_id: int) -> List[Dict[str, Any]]:
    """ユーザーのアバター一覧を取得"""
    try:
        db_service = get_database_service()
        with get_database_manager().get_session() as session:
            avatars = db_service.avatar_repo.get_by_owner(session, user_id)
            return [
                {
                    'id': avatar.id,
                    'name': avatar.name,
                    'avatar_id': avatar.avatar_id,
                    'parameters': avatar.parameters,
                    'created_at': avatar.created_at.isoformat(),
                    'is_active': avatar.is_active
                }
                for avatar in avatars
            ]
    except Exception as e:
        logger.error(f"Failed to get user avatars: {e}")
        return []


def create_avatar_preset(user_id: int, name: str, parameters: Dict) -> Dict[str, Any]:
    """アバタープリセットを作成"""
    try:
        db_service = get_database_service()
        avatar = db_service.create_avatar(
            name=name,
            avatar_id=f"preset_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            owner_id=user_id,
            parameters=parameters
        )

        # 監査ログを記録
        log_audit_event(
            action="create_preset",
            resource_type="avatar",
            user_id=user_id,
            resource_id=avatar.avatar_id,
            details={"name": name}
        )

        return {
            'id': avatar.id,
            'name': avatar.name,
            'avatar_id': avatar.avatar_id,
            'created_at': avatar.created_at.isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to create avatar preset: {e}")
        raise
