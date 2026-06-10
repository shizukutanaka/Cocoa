"""
データベースマネージャー
全サービスで共有されるデータベース接続を管理
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_config
from .models import Base


class DatabaseManager:
    """非同期データベースマネージャー"""

    def __init__(self):
        self._engine: Optional[create_async_engine] = None
        self._sessionmaker: Optional[async_sessionmaker] = None
        self._logger = logging.getLogger(__name__)

    async def initialize(self):
        """データベース初期化"""
        try:
            config = get_config()

            # データベースURL取得（各サービス用に設定）
            # ここではメインのデータベースURLを使用
            database_url = config.database.get("main_database_url", "sqlite+aiosqlite:///data/cocoa.db")

            # エンジン作成
            self._engine = create_async_engine(
                database_url,
                echo=config.services[list(config.services.keys())[0]].debug,  # 最初のサービスのデバッグ設定を使用
                pool_size=config.database.get("pool_size", 10),
                max_overflow=config.database.get("max_overflow", 20),
                pool_pre_ping=True,  # 接続の健全性チェック
            )

            # セッションメーカー作成
            self._sessionmaker = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            # テーブル作成（開発環境のみ）
            if config.environment == "development":
                async with self._engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)

            self._logger.info("データベースが初期化されました")

        except Exception as e:
            self._logger.error(f"データベース初期化エラー: {e}")
            raise

    async def close(self):
        """データベース接続を閉じる"""
        if self._engine:
            await self._engine.dispose()
            self._logger.info("データベース接続が閉じられました")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """データベースセッションを取得"""
        if not self._sessionmaker:
            await self.initialize()

        async with self._sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


# グローバルインスタンス
_db_manager: Optional[DatabaseManager] = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """グローバルデータベースセッション取得"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()

    async with _db_manager.get_session() as session:
        yield session


def reset_db():
    """データベースをリセット（テスト用）"""
    global _db_manager
    _db_manager = None
