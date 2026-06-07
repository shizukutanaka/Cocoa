# 仕様書: 依存性注入 (DI) コンテナ

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/dependency_injection.py`
**目的**: DI コンテナのランタイムクラッシュと `inject` デコレータの不備を修正する。

## 1. 現状とギャップ

- **GAP-1**: **`resolve_dependencies` が生の値に `.get_instance()` を呼ぶ**:
  `Container.register(MyService, host="localhost")` で `kwargs` から
  `{"host": "localhost"}` が `Dependency.dependencies` に格納される。
  しかし `resolve_dependencies` は全値に対して `dep.get_instance()` を呼ぶため、
  `"localhost".get_instance()` → `AttributeError` が発生する。
  **これはランタイムクラッシュを引き起こす実際のバグ。**

- **GAP-2**: **`inject` デコレータが `@wraps(func)` を使わない**:
  デコレートされた関数の `__name__`・`__doc__` が `async_wrapper`/`sync_wrapper`
  に置き換わる。スタックトレースとドキュメンテーションが壊れる。

- **GAP-3**: **`Scope.REQUEST` が `Scope.TRANSIENT` と同一動作**:
  コメントに "REQUEST / TRANSIENT" とあるが、コンテナは両者を区別しない。
  リクエストスコープとして `set_request_scoped` / `get_request_scoped` は
  別メカニズムであり、実態をドキュメントに合わせる必要がある。

## 2. 要件

| ID | 要件 | 状況 | 実装 |
|---|---|---|---|
| REQ-DI-01 | 生の値と `Dependency` オブジェクトの両方を `dependencies` に格納できる | ✅ 実装済 | `resolve_dependencies` 改修 |
| REQ-DI-02 | `inject` デコレータが `@wraps` を使う | ✅ 実装済 | `inject` 改修 |
| REQ-DI-03 | Singleton スコープは同一インスタンスを返す | — | 既存 (`_instances`) |
| REQ-DI-04 | `Transient` スコープは毎回新しいインスタンスを返す | — | 既存 |

## 3. 仕様詳細

### `resolve_dependencies`（REQ-DI-01）

```python
def resolve_dependencies(self) -> Dict[str, Any]:
    resolved = {}
    for name, dep in self.dependencies.items():
        if isinstance(dep, Dependency):
            resolved[name] = dep.get_instance()
        else:
            resolved[name] = dep  # raw value (str, int, etc.) — use as-is
    return resolved
```

### `inject` デコレータ（REQ-DI-02）

`async_wrapper` と `sync_wrapper` の両方に `@wraps(func)` を適用。

## 4. 受け入れ基準（テスト）

`tests/test_dependency_injection.py`（stdlib unittest, 本環境で実行可能）:
- Singleton で同一インスタンスが返ること
- Transient で毎回新しいインスタンスが返ること
- raw kwargs 値を持つ register でクラッシュしないこと（GAP-1 修正確認）
- `inject` デコレータが `__name__` を保持すること（GAP-2 修正確認）
