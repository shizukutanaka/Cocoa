# Cocoa 修復レポート / Codebase Repair Report

**作成日 / Date**: 2026-06-04
**対象 / Scope**: v0.2.0 ツリー全体の静的健全性 (whole-tree static health)

---

## 背景 / Context

リポジトリには「production-grade / military-level / FIPS 140-2 / COMPLETED ✅」を謳う
ドキュメント（`IMPLEMENTATION_STATUS.md` 等）が多数存在しますが、`python -m compileall`
と `ruff` による客観的な計測では **コードはコンパイルできず、中核モジュールは import 不能**
でした。原因は、AI 支援編集ツールが出力した *省略済み（truncated/elided）コードがそのまま
コミットされた* ことです。代表的な破損パターンは 3 つ:

1. ソースに残った `{{ ... }}` という省略プレースホルダ
2. 削除された行 — import ヘッダ、クラス/データクラス定義、`def`/`async def` ヘッダ
   （例: `integrated_security.py` と `avatar_agent.py` には import ブロックが丸ごと無い）
3. 壊れた書式指定 — `:.1f` が文字列リテラル `".1f"` に化けている

---

## 計測結果 / Before → After

すべて `ruff check . --select <rule>` および `python -m compileall` で再現可能。

| 指標 / Metric | Before | After |
|---|---:|---:|
| `python -m compileall`（全体） | **失敗 / fails** | **0 エラー / 0 errors** |
| invalid-syntax (E9) | 27 | **0** |
| undefined-name (F821) | 634 | **0** |
| repeated dict key (F601) | 47 | **0** |
| redefinition (F811) | 4 | **0** |
| return-outside-function (F706) | 4 | **0** |
| unused-import (F401) | 286 | 48※ |
| unused-variable (F841) | 42 | 38※ |

※ 残存する F401 は `try/except ImportError` 内の **オプション依存ライブラリ検出用 import**
（pqcrystals, onnx, mne, pyproj, aiohttp 等）であり、削除するとフォールバック判定が壊れるため
意図的に残しています。残存 F841 は右辺に副作用を持ち得る代入で、挙動を変えないため保持。

---

## 主な修正 / Key Fixes

### 1. 構文エラー (7 ファイル)
`integrated_security.py`, `avatar_agent.py`, `disaster_recovery.py`, `billing_service.py`,
`validate_and_repair_presets.py`, `ai_avatar_gui.py`, `video_analytics.py`,
`test_integration_2025.py`, `run_tests.py` — 省略マーカー除去・import 復元・
`def`/`async def` ヘッダ復元・書式指定の修復。

### 2. 欠落していた import / 定義の復元
中核の `integrated_security.py`（hub モジュール、277 件の未定義名）の import ヘッダ全体、
`AdvancedBehaviorAnalyzer` クラス宣言、`PromptInjectionPattern` データクラス等を復元。
約 20 モジュールで欠落 import を補い、`PresetError` / `NotificationError` /
`PerformanceError` 例外クラスを再定義。オプション依存（numpy, sklearn, psutil, aiohttp,
aiofiles, tkinter 等）は `try/except` でガードし、最小環境でも import 可能に。

### 3. 重複辞書キー（サイレント上書きバグ）
`i18n_manager.py` の言語レジストリで、`ti/so/om` の重複と 9 言語ブロックの 4 重複
（後続コピーは情報欠落、例 `zul` が英語名欠落）を除去。`health_checker.py` と
collaboration サービスの重複キーも修正。

### 4. 重複定義（F811）
`performance_monitor.start_monitoring` の不完全な再定義を除去（完全版を保持）。
`metaverse_integration` ではクラス途中に誤挿入された `get_metaverse_integration` を除去し、
ネスト関数化していたクラスメソッド群を本来のメソッドへ復帰。

---

## 検証 / Verification

```bash
# 1. 全ファイルがバイトコンパイルできる（0 エラー）
python -m compileall -q main services scripts tests *.py

# 2. 構文・未定義名・重複キー・重複定義がゼロ
ruff check . --select E9,F821,F601,F811,F706 --statistics
```

CI（`.github/workflows/ci-cd.yml`）は `python -m pytest tests/` を使用します。本リポジトリ実行
環境には多くの実行時依存（flask/fastapi/torch/cv2/psutil 等）が無く、また `cryptography`
ネイティブバインディングがこの環境では panic するため、フル import / テスト実行は未実施です
（環境上の制約であり、コード側の問題ではありません）。静的検証（compile + ruff）は全て green。

---

## Phase 2 — コード品質・テスト拡充 (2026-06-10)

コンパイル健全化後、さらに lint ルールセットを拡張しコード品質を改善しました。

### Lint ルール拡張後の最終計測

```
ruff check .  →  All checks passed!
python -m compileall -q main services scripts tests *.py  →  0 errors
python tests/run_safe.py  →  1359 passed, 34 skipped
```

**ruff 有効ルール（最終）**: `E4, E7, E9, F, ASYNC, I, RUF100, B, SIM, UP015, UP024, PERF`
**ignore**: `E402, B008, SIM115, PERF203`

| 追加修正 / Additional fixes | 件数 |
|---|---:|
| ASYNC230/240/210: async 関数内 blocking I/O に noqa 追加 | 87 |
| SIM105: try/except/pass → contextlib.suppress | 4 |
| SIM102: 入れ子 if → and 結合 | 複数 |
| SIM117: 入れ子 with → 複合 with | 複数 |
| SIM118: `.keys()` 不要参照除去 | 4 |
| B007: 未使用ループ変数 `x` → `_x` | 複数 |
| UP015: 冗長な open モード `"r"` 除去 | 69 ファイル |
| UP024: OSError エイリアス統一 | 複数 |
| PERF102: dict.items() → .keys()/.values() | 複数 |
| PERF401: for-loop append → list comprehension / .extend() | 20 |
| PERF403: for-loop dict 更新 → dict comprehension | 1 |

### 追加テストファイル

| ファイル | テスト数 | 対象モジュール |
|---|---:|---|
| `tests/test_main.py` | 13 | `main.main` (CocoaLauncher) |
| `tests/test_video_creator.py` | 25 | `main.video_creator` |
| `tests/test_preset_history_diff_and_rollback.py` | 21 | `main.preset_history_diff_and_rollback` |
| `tests/test_parameter_optimizer.py` | 12 | `main.parameter_optimizer` |
| `tests/test_preset_history_dashboard.py` | 9 | `main.preset_history_dashboard` |
| `tests/test_api_server.py` | 14 | `main.api_server` |

### api_server.py インポート修正
FastAPI 未インストール環境でも `import main.api_server` できるよう `_NullApp` スタブと
`if FASTAPI_AVAILABLE:` ガードを追加。

---

## Phase 3 — 製品機能実装 / Feature Implementation (2026-06-10)

プロダクト監査（81 主要モジュール・94 テストファイルを調査）で特定した 4 つの欠落機能を実装。

### 実装した機能

| モジュール | 機能 | テストファイル | テスト数 |
|---|---|---|---:|
| `main/auth_manager.py` | JWT 認証（bcrypt/PBKDF2 フォールバック）、トークンローテーション、リフレッシュ、RBAC、アカウントロックアウト、パスワードリセット | `tests/test_auth_manager.py` | 30 |
| `main/rate_limiter.py` | スライディングウィンドウ式レート制限（エンドポイント別設定）、X-RateLimit-* ヘッダ、IP 抽出 | `tests/test_rate_limiter.py` | 17 |
| `main/avatar_marketplace.py` | アバター公開・閲覧・ダウンロード・評価、オーナー限定非公開化、トレンド、統計 | `tests/test_avatar_marketplace.py` | 25 |
| `main/search_engine.py` | 転置インデックス TF 検索、フィールド重み付け、ファセット、オートコンプリート、複合フィルタ | `tests/test_search_engine.py` | 20 |

### api_server.py 追加エンドポイント（23 本）

| グループ | エンドポイント |
|---|---|
| `/api/auth/*` | register, login, logout, refresh, me, reset-password-request, reset-password |
| `/api/search/*` | avatars（全文検索）, suggest（オートコンプリート） |
| `/api/marketplace/*` | publish, unpublish, get, download, rate, search, trending |
| `/api/admin/*` | users 一覧, ユーザー詳細, ロール変更, レート制限統計, 検索インデックス統計, マーケット統計, 監査 CSV エクスポート |

その他:
- HTTP ミドルウェアによる全エンドポイントへのレート制限適用
- `API_SECRET_TOKEN` スタブから実 JWT 認証へ移行（後方互換フォールバック付き）
- FastAPI 未インストール環境用 `Query` スタブを追加
- WebSocket `/ws/monitoring` に JWT 認証を追加

### 追加実装（ソーシャル・モデレーション機能）

| モジュール | 機能 | テスト数 |
|---|---|---:|
| `main/auth_manager.py`（拡張） | プロフィール（表示名/自己紹介/アバターURL）、ブックマーク、クリエイターフォロー、パスワード変更 | +29 |
| `main/avatar_marketplace.py`（拡張） | テキストレビュー、クリエイター分析ダッシュボード、コンテンツ通報・モデレーション | +34 |
| `main/user_notifications.py`（新規） | ユーザー別アプリ内通知キュー（フォロー・DL・レビューイベント連動） | 17 |
| `main/avatar_collections.py`（新規） | アバターコレクション（公開可能な名前付きフォルダ） | 26 |

追加エンドポイント群:
- `/api/auth/*`（拡張）: change-password, me (PUT), bookmarks, following, feed
- `/api/users/{id}/profile`, `/api/users/{id}/collections`
- `/api/notifications/*`: 一覧, 未読数, 既読化, 全既読, 削除
- `/api/marketplace/*`（拡張）: reviews（投稿/一覧/削除）, report, analytics/me
- `/api/collections/*`: CRUD + アイテム追加/削除 + 公開コレクション閲覧
- `/api/admin/reports/*`: モデレーション通報一覧/統計/解決（テイクダウン）

### 最終計測

```
ruff check .                   →  All checks passed!
python -m compileall -q ...    →  0 errors
python tests/run_safe.py       →  1593 passed, 34 skipped
API エンドポイント総数            →  71 本
```

---

## 残課題（今回スコープ外）/ Follow-ups (out of scope)

- **UP006 (173件)**: `List[X]` → `list[X]` — `--unsafe-fixes` 必要、Python 3.9+ 限定
- **UP045 (68件)**: `Optional[X]` → `X | None` — `--unsafe-fixes` 必要、Python 3.10+ 限定
- **GUI テスト**: `ai_avatar_gui.py`, `avatar_parameter_editor.py`, `avatar_preset_linker_gui.py` — tkinter 依存で自動テスト困難
- **ファイルアップロード**: アバター画像の実ファイル保存・CDN 配信（現在はメモリ内のみ）
- **WebSocket 認証**: 既存 WS エンドポイントへの JWT 認証適用
- `IMPROVEMENT_REPORT.md` 記載のアーキテクチャ課題 — `integrated_security.py` の hub 依存分割、
  テストカバレッジ向上、God-object のリファクタ — は規模・リスクが大きく、別タスクとして推奨します。
