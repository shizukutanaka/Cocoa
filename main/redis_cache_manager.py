"""
Redisベースの高度なキャッシュシステム

Production-gradeのRedisキャッシュ機能を提供し、
分散環境でのスケーラブルなキャッシュ機能を実現します。
"""

import asyncio
import functools
import hashlib
import json
import logging
import os
import pickle
import threading
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Union

from cache_manager import MemoryCache

try:
    import redis
    import redis.asyncio as redis_async
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class RedisCacheManager:
    """Redisベースの高度なキャッシュマネージャー"""

    def __init__(self,
                 host: str = 'localhost',
                 port: int = 6379,
                 db: int = 0,
                 password: Optional[str] = None,
                 max_connections: int = 20,
                 socket_timeout: int = 5,
                 socket_connect_timeout: int = 5,
                 retry_on_timeout: bool = True,
                 health_check_interval: int = 30):
        """Redisキャッシュマネージャーを初期化"""

        if not REDIS_AVAILABLE:
            raise ImportError("redis package is required for RedisCacheManager")

        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.max_connections = max_connections
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.retry_on_timeout = retry_on_timeout
        self.health_check_interval = health_check_interval

        # 接続プール設定
        self.connection_pool = redis.ConnectionPool(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            max_connections=self.max_connections,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_connect_timeout,
            retry_on_timeout=self.retry_on_timeout,
            decode_responses=True
        )

        # 同期・非同期クライアント
        self.redis_client = redis.Redis(connection_pool=self.connection_pool)
        self.redis_async_client = redis_async.Redis(connection_pool=self.connection_pool)

        # ヘルスチェック用の設定
        self.last_health_check = 0
        self.is_healthy = False

        # キャッシュ統計
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0
        }

        # ロック（スレッドセーフ用）
        self.lock = threading.RLock()

        # デフォルト設定
        self.default_ttl = 300  # 5分
        self.max_key_length = 250  # Redisのキー長制限
        self.compression_threshold = 1024  # 1KB以上で圧縮を検討

        logger.info(f"RedisCacheManager initialized for {self.host}:{self.port}")

    async def health_check(self) -> bool:
        """Redis接続のヘルスチェック"""
        try:
            await self.redis_async_client.ping()
            self.is_healthy = True
            self.last_health_check = time.time()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            self.is_healthy = False
            return False

    def _get_cache_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """キャッシュキーを生成"""
        key_data = f"{func.__name__}:{args}:{frozenset(kwargs.items())}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()

        # プレフィックスを追加して名前空間を確保
        return f"cocoa:cache:{key_hash}"

    def _serialize_value(self, value: Any) -> str:
        """値をシリアライズ"""
        try:
            # 大きな値は圧縮を検討
            if hasattr(value, '__sizeof__') and value.__sizeof__() > self.compression_threshold:
                # 実際の圧縮実装が必要な場合はここに追加
                pass

            return json.dumps(value, default=str)
        except (TypeError, ValueError):
            # JSONでシリアライズできない場合はpickleを使用
            return pickle.dumps(value).decode('latin1')

    def _deserialize_value(self, value: str) -> Any:
        """値をデシリアライズ"""
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            # JSONでデシリアライズできない場合はpickleを使用
            return pickle.loads(value.encode('latin1'))

    async def get(self, key: str) -> Optional[Any]:
        """キャッシュから値を取得（非同期）"""
        try:
            if not self.is_healthy:
                await self.health_check()

            value = await self.redis_async_client.get(key)
            if value is None:
                with self.lock:
                    self.stats['misses'] += 1
                return None

            # TTLチェック（-2: キーが存在しない、-1: キーは存在するが期限なし）
            ttl = await self.redis_async_client.ttl(key)
            if ttl == -2:  # キーが存在しない場合（GET後の競合で削除された）
                with self.lock:
                    self.stats['misses'] += 1
                return None

            deserialized_value = self._deserialize_value(value)

            with self.lock:
                self.stats['hits'] += 1

            logger.debug(f"Cache hit for key: {key}")
            return deserialized_value

        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            with self.lock:
                self.stats['errors'] += 1
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """キャッシュに値を設定（非同期）"""
        try:
            if not self.is_healthy:
                await self.health_check()

            if ttl is None:
                ttl = self.default_ttl

            serialized_value = self._serialize_value(value)

            # Redisに設定
            await self.redis_async_client.setex(key, ttl, serialized_value)

            with self.lock:
                self.stats['sets'] += 1

            logger.debug(f"Cache set for key: {key} (TTL: {ttl}s)")
            return True

        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            with self.lock:
                self.stats['errors'] += 1
            return False

    async def delete(self, key: str) -> bool:
        """キャッシュからキーを削除（非同期）"""
        try:
            if not self.is_healthy:
                await self.health_check()

            result = await self.redis_async_client.delete(key)

            with self.lock:
                self.stats['deletes'] += 1

            logger.debug(f"Cache delete for key: {key} (affected: {result})")
            return result > 0

        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            with self.lock:
                self.stats['errors'] += 1
            return False

    async def exists(self, key: str) -> bool:
        """キーの存在確認（非同期）"""
        try:
            return await self.redis_async_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """パターンにマッチするキーを削除（非同期）"""
        try:
            if not self.is_healthy:
                await self.health_check()

            keys = await self.redis_async_client.keys(pattern)
            if not keys:
                return 0

            deleted_count = await self.redis_async_client.delete(*keys)

            logger.info(f"Cleared {deleted_count} cache keys matching pattern: {pattern}")
            return deleted_count

        except Exception as e:
            logger.error(f"Cache clear pattern error for pattern {pattern}: {e}")
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        """キャッシュ統計情報を取得"""
        try:
            # Redisの情報も取得
            info = await self.redis_async_client.info()

            return {
                'cache_stats': self.stats.copy(),
                'redis_info': {
                    'connected_clients': info.get('connected_clients', 0),
                    'used_memory_human': info.get('used_memory_human', '0B'),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0),
                    'uptime_in_days': info.get('uptime_in_days', 0),
                },
                'health': {
                    'is_healthy': self.is_healthy,
                    'last_check': self.last_health_check,
                    'host': self.host,
                    'port': self.port
                }
            }
        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return {'error': str(e)}

    def cached_async(self, ttl: Optional[int] = None):
        """非同期関数をキャッシュするデコレーター"""
        def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            async def wrapper(*args, **kwargs) -> Any:
                cache_key = self._get_cache_key(func, args, kwargs)

                # キャッシュから取得を試行
                cached_result = await self.get(cache_key)
                if cached_result is not None:
                    return cached_result

                # 関数を実行して結果をキャッシュ
                result = await func(*args, **kwargs)
                await self.set(cache_key, result, ttl)

                return result

            return wrapper
        return decorator

    def cached_sync(self, ttl: Optional[int] = None):
        """同期関数をキャッシュするデコレーター"""
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            def wrapper(*args, **kwargs) -> Any:
                cache_key = self._get_cache_key(func, args, kwargs)

                # 非同期キャッシュから取得（同期関数でも非同期キャッシュを使用）
                # ループが実行中の場合は create_task を使わない（リークするため）
                cached_result = None
                try:
                    loop = asyncio.get_event_loop()
                    if not loop.is_running():
                        cached_result = loop.run_until_complete(self.get(cache_key))
                except RuntimeError:
                    pass

                if cached_result is not None:
                    return cached_result

                # 関数を実行して結果をキャッシュ
                result = func(*args, **kwargs)

                try:
                    loop = asyncio.get_event_loop()
                    if not loop.is_running():
                        loop.run_until_complete(self.set(cache_key, result, ttl))
                except RuntimeError:
                    pass

                return result

            return wrapper
        return decorator

    async def cleanup_expired(self) -> int:
        """期限切れのキーをクリーンアップ"""
        try:
            # Redisの自動クリーンアップ機能に任せるため、特別な処理は不要
            # ただし、特定のプレフィックスを持つ期限切れキーを削除する場合
            expired_keys = []

            # cocoa:cache:* パターンで期限切れのキーを探すロジックをここに実装可能
            # ただし、RedisのTTL機能に任せるのが最も効率的

            return len(expired_keys)
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
            return 0

    async def close(self):
        """接続を閉じる"""
        try:
            await self.redis_async_client.close()
            await self.redis_async_client.connection_pool.disconnect()
            logger.info("Redis cache manager connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")


class FallbackCacheManager:
    """フォールバック用のメモリキャッシュマネージャー（Redisが利用できない場合）"""

    def __init__(self):
        self.memory_cache = MemoryCache(max_size=1000, ttl_seconds=300)
        logger.info("FallbackCacheManager initialized (Redis not available)")

    async def get(self, key: str) -> Optional[Any]:
        return self.memory_cache.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        self.memory_cache.set(key, value)
        return True

    async def delete(self, key: str) -> bool:
        self.memory_cache.delete(key)
        return True

    async def exists(self, key: str) -> bool:
        return self.memory_cache.get(key) is not None

    async def get_stats(self) -> Dict[str, Any]:
        return {'cache_type': 'memory', 'message': 'Redis not available'}

    def cached_async(self, ttl: Optional[int] = None):
        def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            @functools.wraps(func)
            async def wrapper(*args, **kwargs) -> Any:
                key = f"{func.__name__}:{args}:{frozenset(kwargs.items())}"
                cached = self.memory_cache.get(key)
                if cached is not None:
                    return cached
                result = await func(*args, **kwargs)
                self.memory_cache.set(key, result)
                return result
            return wrapper
        return decorator

    def cached_sync(self, ttl: Optional[int] = None):
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                key = f"{func.__name__}:{args}:{frozenset(kwargs.items())}"
                cached = self.memory_cache.get(key)
                if cached is not None:
                    return cached
                result = func(*args, **kwargs)
                self.memory_cache.set(key, result)
                return result
            return wrapper
        return decorator

    async def close(self):
        pass


# グローバルキャッシュマネージャーインスタンス
_cache_manager: Optional[Union[RedisCacheManager, FallbackCacheManager]] = None


def get_cache_manager() -> Union[RedisCacheManager, FallbackCacheManager]:
    """キャッシュマネージャーのシングルトンインスタンスを取得"""
    global _cache_manager

    if _cache_manager is None:
        try:
            # 環境変数からRedis設定を取得
            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port = int(os.getenv('REDIS_PORT', '6379'))
            redis_db = int(os.getenv('REDIS_DB', '0'))
            redis_password = os.getenv('REDIS_PASSWORD')

            _cache_manager = RedisCacheManager(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password
            )
        except Exception as e:
            logger.warning(f"Redis not available, falling back to memory cache: {e}")
            _cache_manager = FallbackCacheManager()

    return _cache_manager


# デコレーターの便利関数
def cache_async(ttl: Optional[int] = None):
    """非同期関数をキャッシュするデコレーター"""
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        cache_manager = get_cache_manager()
        return cache_manager.cached_async(ttl)(func)
    return decorator


def cache_sync(ttl: Optional[int] = None):
    """同期関数をキャッシュするデコレーター"""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        cache_manager = get_cache_manager()
        return cache_manager.cached_sync(ttl)(func)
    return decorator
