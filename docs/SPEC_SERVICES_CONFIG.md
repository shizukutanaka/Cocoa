# 仕様書: ConfigManager (services/shared/config.py)

**版**: 1.0 / **作成日**: 2026-06-08 / **対象**: `services/shared/config.py`
**目的**: 環境変数オーバーライドのキー不整合バグと、ネスト config パスでの mkdir 失敗を修正。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-SC-01 | `_apply_env_overrides()` が env キーを `service_name.upper()` で生成 → ハイフン付きサービス名（`api-gateway`）で `"API-GATEWAY_PORT"` となる | 既定設定/ドキュメントは `"API_GATEWAY_PORT"`（アンダースコア）を使用。**ハイフンを含む全サービスで env オーバーライドが効かない** |
| GAP-SC-02 | `_create_default_config()` が `config_dir.mkdir(exist_ok=True)`（`parents` 無し） | ネストした config パス（例 `a/b/config.json` で `a` 不在）で `FileNotFoundError` |

`_create_default_config()` 内では env を `os.getenv("API_GATEWAY_PORT", ...)`（アンダースコア）で読むが、
`_apply_env_overrides()` は `f"{service_name.upper()}_{key.upper()}"` = `"API-GATEWAY_PORT"`（ハイフン）で読む不整合。

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-SC-01 | env オーバーライドキーはハイフンをアンダースコアに正規化する | `service_name.upper().replace("-", "_")` |
| REQ-SC-02 | デフォルト設定生成は親ディレクトリも作成する | `mkdir(parents=True, exist_ok=True)` |

## 3. 受け入れ基準（テスト）

`tests/test_services_config.py`（stdlib unittest, tempfile + 環境変数操作のみ）:
- `ServiceConfig` / `CocoaConfig` dataclass が構築できる
- `ConfigManager(config_path=...)` でカスタムパスを使える
- 設定ファイル不在時に既定設定が生成される
- ネストしたパス（`sub/dir/config.json`）でも既定設定が生成できる（REQ-SC-02）
- `API_GATEWAY_PORT` 環境変数が `api-gateway` の port をオーバーライドする（REQ-SC-01）
- `AVATAR_SERVICE_DEBUG=true` が debug を bool でオーバーライドする
- `get_service_config()` が正しい `ServiceConfig` を返す
- `reset_config()` がグローバルインスタンスをクリアする
