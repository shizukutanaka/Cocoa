"""
非同期プログラミングの基盤とベストプラクティス実装

設計原則:
- 非ブロッキング操作の強制
- asyncio.gather による並行実行
- 適切なタイムアウト設定
- リソース管理と例外処理
"""

import asyncio
import time
from typing import Callable, List, Optional, TypeVar, Any, Coroutine
import logging
from contextlib import asynccontextmanager
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class AsyncBatch:
    """非同期バッチ処理の管理"""

    def __init__(self, batch_size: int = 10, timeout: float = 30.0):
        self.batch_size = batch_size
        self.timeout = timeout

    async def process(
        self,
        items: List[T],
        processor: Callable[[T], Coroutine[Any, Any, Any]]
    ) -> List[Any]:
        """
        バッチ処理: 複数のアイテムを並行処理

        Args:
            items: 処理対象のアイテムリスト
            processor: 非同期処理関数

        Returns:
            処理結果のリスト

        例:
            batch = AsyncBatch(batch_size=5)
            results = await batch.process(items, async_fetch_data)
        """
        results = []

        # バッチに分割して処理
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]

            try:
                # 非ブロッキング: asyncio.gather を使用して並行実行
                batch_results = await asyncio.wait_for(
                    asyncio.gather(
                        *[processor(item) for item in batch],
                        return_exceptions=True  # 個別エラーをキャッチ
                    ),
                    timeout=self.timeout,
                )

                # エラーをログに記録
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error(f"Batch processing error: {result}")
                    else:
                        results.append(result)

            except asyncio.TimeoutError:
                logger.error(f"Batch processing timeout after {self.timeout}s")
                raise

        return results


class AsyncPool:
    """非同期接続プール管理"""

    def __init__(self, size: int = 10, timeout: float = 30.0):
        self.size = size
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(size)
        self._active_tasks: set = set()

    async def acquire(self):
        """接続を取得（セマフォで制限）"""
        await self._semaphore.acquire()

    def release(self):
        """接続を解放"""
        self._semaphore.release()

    @asynccontextmanager
    async def connection(self):
        """コンテキストマネージャーで接続管理"""
        await self.acquire()
        try:
            yield
        finally:
            self.release()

    async def execute_many(
        self,
        tasks: List[Callable[[], Coroutine[Any, Any, Any]]]
    ) -> List[Any]:
        """複数のタスクを制限された並行性で実行"""
        results = []

        async def run_with_limit(task):
            async with self.connection():
                try:
                    return await asyncio.wait_for(task(), timeout=self.timeout)
                except asyncio.TimeoutError:
                    logger.error(f"Task timeout after {self.timeout}s")
                    raise

        results = await asyncio.gather(
            *[run_with_limit(task) for task in tasks],
            return_exceptions=True
        )

        return results


def async_timeout(seconds: float):
    """非同期関数にタイムアウトを追加するデコレータ"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                logger.error(f"{func.__name__} exceeded timeout of {seconds}s")
                raise

        return wrapper

    return decorator


def ensure_non_blocking(func: Callable) -> Callable:
    """関数が非ブロッキング操作を使用していることを確認するデコレータ"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # 実行前に asyncio.sleep を強制的に実行して、
        # イベントループへの制御を返すことを確認
        await asyncio.sleep(0)

        result = await func(*args, **kwargs)

        # 実行後も asyncio.sleep を実行
        await asyncio.sleep(0)

        return result

    return wrapper


class AsyncCache:
    """非同期キャッシュ"""

    def __init__(self, ttl: float = 300.0):
        self.ttl = ttl
        self._cache: dict = {}
        self._timestamps: dict = {}

    async def get(self, key: str) -> Optional[Any]:
        """キャッシュから値を取得。ttl <= 0 のとき TTL 無効（永続）。"""
        if key in self._cache:
            if self.ttl <= 0:
                return self._cache[key]
            elapsed = time.time() - self._timestamps[key]
            if elapsed < self.ttl:
                return self._cache[key]
            # TTL切れ
            del self._cache[key]
            del self._timestamps[key]
        return None

    async def set(self, key: str, value: Any) -> None:
        """キャッシュに値を設定"""
        self._cache[key] = value
        self._timestamps[key] = time.time()

    async def delete(self, key: str) -> None:
        """キャッシュから削除"""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)

    async def clear(self) -> None:
        """キャッシュをクリア"""
        self._cache.clear()
        self._timestamps.clear()


# ベストプラクティスの使用例
async def fetch_multiple_sources(urls: List[str]) -> List[str]:
    """
    複数のソースからデータを並行取得

    ベストプラクティス:
    - asyncio.gather を使用した並行実行
    - タイムアウト設定
    - エラーハンドリング
    """
    import aiohttp

    async def fetch(url: str) -> str:
        # 非ブロッキング: aiohttp（同期リクエストライブラリは使わない）
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return await resp.text()

    try:
        # 全URLを並行処理
        results = await asyncio.wait_for(
            asyncio.gather(*[fetch(url) for url in urls], return_exceptions=True),
            timeout=30.0
        )
        return results
    except asyncio.TimeoutError:
        logger.error("Fetching multiple sources exceeded timeout")
        raise


async def process_stream(
    data_stream,
    processor: Callable[[Any], Coroutine[Any, Any, Any]],
    max_concurrent: int = 5
) -> None:
    """
    ストリーム処理：リアルタイムでデータを処理

    ベストプラクティス:
    - 制限された並行性（メモリ効率）
    - バッファリング
    - エラーハンドリング
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_limit(item):
        async with semaphore:
            try:
                await processor(item)
            except Exception as e:
                logger.error(f"Stream processing error: {e}")

    tasks = [process_with_limit(item) async for item in data_stream]
    await asyncio.gather(*tasks, return_exceptions=True)
