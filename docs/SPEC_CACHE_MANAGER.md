# 仕様書: CacheManager

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/cache_manager.py`
**目的**: スレッド安全性、カプセル化、デコレーター正確性の改善。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-CM-01 | `CacheManager.invalidate()` が `memory_cache.cache` と `memory_cache.access_order` に lock なしで直接アクセス | スレッド競合状態 |
| GAP-CM-02 | `MemoryCache` に `delete(key)` メソッドがない | 外部からの安全な削除 API がない |
| GAP-CM-03 | `cached()` デコレーターに `@wraps` がない | `__name__`, `__doc__` が失われる |
| GAP-CM-04 | `async_cached()` が `async def` で定義されている | デコレーターとして `@async_cached()` で使えない（`await` 必須になる） |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-CM-01 | `MemoryCache.delete(key)` — ロック保護付き削除 | `with self.lock: del self.cache[key]; remove from access_order` |
| REQ-CM-02 | `CacheManager.invalidate()` は `memory_cache.delete(key)` を呼ぶ | 直接内部構造へのアクセスを排除 |
| REQ-CM-03 | `cached()` は `@wraps(func)` を適用 | `functools.wraps` 使用 |
| REQ-CM-04 | `async_cached()` を `async def` から `def` に変更 | デコレーターとして正しく機能させる |

## 3. 仕様詳細

### `MemoryCache.delete(key)` (REQ-CM-01)
```python
def delete(self, key: str) -> None:
    with self.lock:
        self.cache.pop(key, None)
        try:
            self.access_order.remove(key)
        except ValueError:
            pass
```

### `CacheManager.invalidate()` リファクタリング (REQ-CM-02)
```python
def invalidate(self, key: str) -> None:
    self.memory_cache.delete(key)
    cache_path = self.file_cache._get_cache_path(key)
    if cache_path.exists():
        try:
            cache_path.unlink()
        except (OSError, PermissionError) as e:
            logger.warning(...)
```

### `cached()` デコレーター (REQ-CM-03)
```python
from functools import wraps
def cached(ttl_seconds=300, use_file_cache=False):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ...
        return wrapper
    return decorator
```

### `async_cached()` 修正 (REQ-CM-04)
```python
def async_cached(ttl_seconds=300, use_file_cache=False):  # def, not async def
    def decorator(func):
        ...
    return decorator
```

## 4. 受け入れ基準（テスト）

`tests/test_cache_manager.py`（stdlib unittest, ファイル不要):
- `MemoryCache`: set/get, TTL失効, LRU eviction, delete, clear
- `CacheManager`: invalidate via delete (not direct access)
- `cached()`: `__name__` 保持確認
- `async_cached()`: 同期的に呼べる（`await` 不要）確認
