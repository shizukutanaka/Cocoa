# 仕様書: redis_cache_manager

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/redis_cache_manager.py`
**目的**: `FallbackCacheManager` の存在しないメソッド参照と no-op set/delete バグの修正。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-RCM-01 | `FallbackCacheManager.cached_async()` が `MemoryCache.cached_async()` を呼ぶが未定義 | AttributeError で即クラッシュ |
| GAP-RCM-02 | `FallbackCacheManager.cached_sync()` が `MemoryCache.cached_sync()` を呼ぶが未定義 | AttributeError で即クラッシュ |
| GAP-RCM-03 | `FallbackCacheManager.set()` は実際に値を保存しない（常に `True` を返す） | フォールバック時にキャッシュが機能しない |
| GAP-RCM-04 | `FallbackCacheManager.delete()` は `memory_cache.delete()` を呼ばない | 削除操作が無視される |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-RCM-01 | `FallbackCacheManager.cached_async()` は functools.wraps を使った正しい async デコレーターを返す | 内部で `self.get/set` を呼ぶ |
| REQ-RCM-02 | `FallbackCacheManager.cached_sync()` は functools.wraps を使った正しい sync デコレーターを返す | 内部で `self.memory_cache.get/set` を呼ぶ |
| REQ-RCM-03 | `FallbackCacheManager.set()` は `self.memory_cache.set(key, value)` を呼ぶ | TTL は MemoryCache の init 時設定で代用 |
| REQ-RCM-04 | `FallbackCacheManager.delete()` は `self.memory_cache.delete(key)` を呼ぶ | |

## 3. 受け入れ基準（テスト）

`tests/test_redis_cache_manager.py`（stdlib unittest, redis なしで動作）:
- `FallbackCacheManager` の作成が成功する
- `get()` は存在しないキーで `None` を返す
- `set()` 後に `get()` が値を返す
- `delete()` 後に `exists()` が `False` を返す
- `cached_async()` / `cached_sync()` がデコレーターを返す（呼び出し可能）
- `get_cache_manager()` が Redis 未インストール環境で `FallbackCacheManager` を返す
