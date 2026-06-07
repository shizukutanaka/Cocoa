# 仕様書: 非同期プログラミング基盤

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/async_base.py`
**目的**: `AsyncBatch` のタイムアウト無効バグと `AsyncCache` のエッジケースを修正する。

## 1. 現状とギャップ

- **GAP-1**: **`AsyncBatch.timeout` が使われない**:
  コンストラクタで `self.timeout = timeout` と保存するが、
  `process()` メソッド内の `asyncio.gather()` にタイムアウトが渡されない。
  ハングするプロセッサー関数があると、バッチ全体が永遠に待ち続ける。
- **GAP-2**: **`AsyncCache` の `import time` がメソッド内にある**:
  `get()` と `set()` の内部で `import time` を呼んでいる。
  モジュールレベルで import すべき（パフォーマンスと可読性の問題）。
- **GAP-3**: **`AsyncCache` のゼロ TTL で即時期限切れにならない**:
  `ttl=0` のとき、`elapsed < self.ttl` は `0 < 0 = False` なので、
  セットした瞬間に取得しても `None` が返る。
  仕様として「`ttl <= 0` は TTL なし（永続）」と決めるか、
  「`ttl=0` は即時期限切れ」と明記する必要がある。
  → **仕様: `ttl=0` は TTL なし（永続キャッシュ）として扱う**。

## 2. 要件

| ID | 要件 | 状況 | 実装 |
|---|---|---|---|
| REQ-AB-01 | `AsyncBatch.process` がバッチ全体に `self.timeout` を適用 | ✅ 実装済 | `asyncio.wait_for(asyncio.gather(...), timeout)` |
| REQ-AB-02 | `import time` をモジュールレベルに移動 | ✅ 実装済 | モジュールヘッダー |
| REQ-AB-03 | `ttl <= 0` のとき TTL 無効（永続）として扱う | ✅ 実装済 | `AsyncCache.get` の条件分岐 |
| REQ-AB-04 | `AsyncBatch.process` がタイムアウトしたとき `asyncio.TimeoutError` を送出 | — | 既存ロガー行動は維持 |

## 3. 仕様詳細

### `AsyncBatch.process`（REQ-AB-01）
```python
batch_results = await asyncio.wait_for(
    asyncio.gather(*[processor(item) for item in batch], return_exceptions=True),
    timeout=self.timeout
)
```
`asyncio.TimeoutError` は呼び出し元に伝播させる（`return_exceptions` はバッチ内
個別タスクの例外のみキャッチ、バッチ全体のタイムアウトはキャッチしない）。

### `AsyncCache.get`（REQ-AB-03）
```python
if key in self._cache:
    if self.ttl <= 0:  # 永続
        return self._cache[key]
    elapsed = time.time() - self._timestamps[key]
    if elapsed < self.ttl:
        return self._cache[key]
    # TTL 期限切れ: 削除
    del self._cache[key]
    del self._timestamps[key]
return None
```

## 4. 受け入れ基準（テスト）
`tests/test_async_base.py`（stdlib unittest + asyncio.run, 本環境で実行可能）。
