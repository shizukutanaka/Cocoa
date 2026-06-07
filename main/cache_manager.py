"""
軽量キャッシュシステム
パフォーマンス向上のための効率的なキャッシュ機能を提供
"""

import asyncio
import time
import json
import hashlib
from functools import wraps
from typing import Any, Dict, Optional, Callable
from pathlib import Path
import threading
import logging

logger = logging.getLogger(__name__)


class MemoryCache:
    """軽量なメモリキャッシュ"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        """キャッシュを初期化"""
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_order = []  # LRU実装のためのアクセス順序
        self.lock = threading.RLock()

    def _get_cache_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """キャッシュキーを生成"""
        # 関数名と引数を基にハッシュを生成
        key_data = f"{func.__name__}:{args}:{frozenset(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key: str) -> Any:
        """キャッシュから値を取得"""
        with self.lock:
            if key not in self.cache:
                return None

            entry = self.cache[key]

            # TTLチェック
            if time.time() - entry['timestamp'] > self.ttl_seconds:
                del self.cache[key]
                if key in self.access_order:
                    self.access_order.remove(key)
                return None

            # アクセス順序を更新
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)

            return entry['value']

    def set(self, key: str, value: Any) -> None:
        """キャッシュに値を設定"""
        with self.lock:
            now = time.time()

            # 最大サイズを超える場合は古いエントリを削除
            if len(self.cache) >= self.max_size and key not in self.cache:
                oldest_key = self.access_order.pop(0)
                del self.cache[oldest_key]

            # キャッシュに保存
            self.cache[key] = {
                'value': value,
                'timestamp': now
            }

            # アクセス順序を更新
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)

    def delete(self, key: str) -> None:
        """キャッシュからキーを削除"""
        with self.lock:
            self.cache.pop(key, None)
            try:
                self.access_order.remove(key)
            except ValueError:
                pass

    def clear(self) -> None:
        """キャッシュをクリア"""
        with self.lock:
            self.cache.clear()
            self.access_order.clear()

    def stats(self) -> Dict[str, Any]:
        """キャッシュ統計情報を取得"""
        with self.lock:
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'ttl_seconds': self.ttl_seconds,
                'hit_ratio': self._calculate_hit_ratio()
            }

    def _calculate_hit_ratio(self) -> float:
        """ヒット率を計算（簡易実装）"""
        # 実際の実装ではアクセスカウンターが必要
        return 0.0


class FileCache:
    """軽量なファイルベースキャッシュ"""

    def __init__(self, cache_dir: str = "cache", ttl_seconds: int = 3600):
        """ファイルキャッシュを初期化"""
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        """キャッシュファイルのパスを取得"""
        # キーのハッシュをファイル名に使用
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"

    def get(self, key: str) -> Any:
        """キャッシュから値を取得"""
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            # TTLチェック
            if time.time() - cache_path.stat().st_mtime > self.ttl_seconds:
                cache_path.unlink()
                return None

            # キャッシュファイルの読み込み
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            return cache_data['value']

        except Exception as e:
            logger.warning(f"キャッシュ読み込みエラー ({key}): {e}")
            # エラー時はファイルを削除
            try:
                cache_path.unlink()
            except (OSError, PermissionError) as cleanup_err:
                logger.warning(f"Failed to remove corrupted cache file: {cleanup_err}")
            return None

    def set(self, key: str, value: Any) -> None:
        """キャッシュに値を設定"""
        cache_path = self._get_cache_path(key)

        try:
            # キャッシュデータを保存
            cache_data = {
                'key': key,
                'value': value,
                'timestamp': time.time()
            }

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"キャッシュ書き込みエラー ({key}): {e}")

    def clear(self) -> None:
        """キャッシュをクリア"""
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
        except Exception as e:
            logger.error(f"キャッシュクリアエラー: {e}")

    def cleanup_expired(self) -> int:
        """期限切れキャッシュを削除"""
        cleaned_count = 0
        try:
            current_time = time.time()

            for cache_file in self.cache_dir.glob("*.cache"):
                if current_time - cache_file.stat().st_mtime > self.ttl_seconds:
                    cache_file.unlink()
                    cleaned_count += 1

        except Exception as e:
            logger.error(f"期限切れキャッシュ削除エラー: {e}")

        return cleaned_count


class CacheManager:
    """統合キャッシュマネージャー"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """キャッシュマネージャーを初期化"""
        config = config or {}

        self.memory_cache = MemoryCache(
            max_size=config.get('memory_cache_size', 1000),
            ttl_seconds=config.get('memory_cache_ttl', 300)
        )

        self.file_cache = FileCache(
            cache_dir=config.get('file_cache_dir', 'cache'),
            ttl_seconds=config.get('file_cache_ttl', 3600)
        )

        # キャッシュ戦略設定
        self.cache_strategy = config.get('cache_strategy', 'memory_first')  # memory_first, file_only, hybrid

    def get(self, key: str) -> Any:
        """キャッシュから値を取得"""
        # メモリキャッシュから優先的に取得
        value = self.memory_cache.get(key)
        if value is not None:
            return value

        # ファイルキャッシュから取得
        if self.cache_strategy in ['file_only', 'hybrid']:
            value = self.file_cache.get(key)
            if value is not None:
                # メモリキャッシュにも保存（次回アクセス高速化）
                self.memory_cache.set(key, value)
                return value

        return None

    def set(self, key: str, value: Any, use_file_cache: bool = False) -> None:
        """キャッシュに値を設定"""
        # 常にメモリキャッシュに保存
        self.memory_cache.set(key, value)

        # ファイルキャッシュにも保存する場合
        if use_file_cache or self.cache_strategy == 'file_only':
            self.file_cache.set(key, value)

    def invalidate(self, key: str) -> None:
        """キャッシュからキーを削除"""
        self.memory_cache.delete(key)

        cache_path = self.file_cache._get_cache_path(key)
        if cache_path.exists():
            try:
                cache_path.unlink()
            except (OSError, PermissionError) as e:
                logger.warning(f"Failed to remove cache key {key}: {e}")

    def clear_all(self) -> None:
        """全てのキャッシュをクリア"""
        self.memory_cache.clear()
        self.file_cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """キャッシュ統計情報を取得"""
        return {
            'memory_cache': self.memory_cache.stats(),
            'file_cache': {
                'cache_dir': str(self.file_cache.cache_dir),
                'ttl_seconds': self.file_cache.ttl_seconds,
                'file_count': len(list(self.file_cache.cache_dir.glob("*.cache")))
            },
            'strategy': self.cache_strategy
        }


# グローバルキャッシュインスタンス
_cache_manager: Optional[CacheManager] = None

def get_cache_manager() -> CacheManager:
    """キャッシュマネージャーを取得"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def cached(ttl_seconds: int = 300, use_file_cache: bool = False):
    """キャッシュデコレーター"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()
            cache_key = cache_manager.memory_cache._get_cache_key(func, args, kwargs)

            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result

            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, use_file_cache)
            return result

        return wrapper
    return decorator


def clear_cache():
    """キャッシュをクリア"""
    cache_manager = get_cache_manager()
    cache_manager.clear_all()


def cache_stats() -> Dict[str, Any]:
    """キャッシュ統計情報を取得"""
    cache_manager = get_cache_manager()
    return cache_manager.get_stats()


# 非同期キャッシュ機能の追加
class AsyncMemoryCache:
    """非同期対応のメモリキャッシュ"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        """キャッシュを初期化"""
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_order = []  # LRU実装のためのアクセス順序
        self.lock = asyncio.Lock()

    async def _get_cache_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """キャッシュキーを生成"""
        # 関数名と引数を基にハッシュを生成
        key_data = f"{func.__name__}:{args}:{frozenset(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def get(self, key: str) -> Any:
        """キャッシュから値を取得"""
        async with self.lock:
            if key not in self.cache:
                return None

            entry = self.cache[key]

            # TTLチェック
            if time.time() - entry['timestamp'] > self.ttl_seconds:
                del self.cache[key]
                if key in self.access_order:
                    self.access_order.remove(key)
                return None

            # アクセス順序を更新
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)

            return entry['value']

    async def set(self, key: str, value: Any) -> None:
        """キャッシュに値を設定"""
        async with self.lock:
            now = time.time()

            # 最大サイズを超える場合は古いエントリを削除
            if len(self.cache) >= self.max_size and key not in self.cache:
                oldest_key = self.access_order.pop(0)
                del self.cache[oldest_key]

            # キャッシュに保存
            self.cache[key] = {
                'value': value,
                'timestamp': now
            }

            # アクセス順序を更新
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)

    async def clear(self) -> None:
        """キャッシュをクリア"""
        async with self.lock:
            self.cache.clear()
            self.access_order.clear()


class AsyncCacheManager:
    """非同期対応のキャッシュマネージャー"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """キャッシュマネージャーを初期化"""
        config = config or {}

        self.memory_cache = AsyncMemoryCache(
            max_size=config.get('memory_cache_size', 1000),
            ttl_seconds=config.get('memory_cache_ttl', 300)
        )

        self.file_cache = FileCache(
            cache_dir=config.get('file_cache_dir', 'cache'),
            ttl_seconds=config.get('file_cache_ttl', 3600)
        )

        # キャッシュ戦略設定
        self.cache_strategy = config.get('cache_strategy', 'memory_first')

    async def get(self, key: str) -> Any:
        """キャッシュから値を取得"""
        # メモリキャッシュから優先的に取得
        value = await self.memory_cache.get(key)
        if value is not None:
            return value

        # ファイルキャッシュから取得
        if self.cache_strategy in ['file_only', 'hybrid']:
            value = self.file_cache.get(key)
            if value is not None:
                # メモリキャッシュにも保存（次回アクセス高速化）
                await self.memory_cache.set(key, value)
                return value

        return None

    async def set(self, key: str, value: Any, use_file_cache: bool = False) -> None:
        """キャッシュに値を設定"""
        # 常にメモリキャッシュに保存
        await self.memory_cache.set(key, value)

        # ファイルキャッシュにも保存する場合
        if use_file_cache or self.cache_strategy == 'file_only':
            self.file_cache.set(key, value)


def async_cached(ttl_seconds: int = 300, use_file_cache: bool = False):
    """非同期キャッシュデコレーター"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if asyncio.iscoroutinefunction(func):
                cache_manager = get_cache_manager()
                # _get_cache_key is sync on MemoryCache — no await
                cache_key = cache_manager.memory_cache._get_cache_key(func, args, kwargs)

                cached_result = cache_manager.get(cache_key)
                if cached_result is not None:
                    return cached_result

                result = await func(*args, **kwargs)
                cache_manager.set(cache_key, result, use_file_cache)
                return result
            else:
                return cached(ttl_seconds, use_file_cache)(func)(*args, **kwargs)

        return wrapper
    return decorator
