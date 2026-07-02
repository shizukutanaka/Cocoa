# Cocoa 機能過不足監査レポート

対象ブランチ: `claude/deepresearch-ultrathink-improvement-MpLA3`（基点コミット `0f9a100` 時点）

この文書は、コードレベルの検証に基づく機能の「不足」と「過剰」の選別リストである。
読み手は本監査の経緯を知らない前提で書かれており、各主張には証拠（ファイルパス・シンボル名・
検証コマンド）を併記してあるため、この文書単体で再検証と着手が可能である。

---

## 1. 前提: 製品の実像

着手前に誤解しやすい 2 点を先に固定する。

1. **Cocoa の実体は「アバターパラメータ（JSON）の取引所」であり、3D モデルファイルの
   配布基盤ではない。** `main/avatar_marketplace.py` の `MarketplaceListing` dataclass に
   ファイル/モデル URL に相当するフィールドは存在せず（`thumbnail_url` のみ）、購入処理
   `download()` が買い手に返すのは `parameters`（dict）である。`README.md` 自身が
   "Preset Management: Large-scale parameter handling" と宣言しており、これは**欠陥ではなく
   意図されたスコープ**（アセット著作権の複雑さを回避する設計）と判断する。
2. **実行形態は単一 FastAPI モノリスである。** `main/api_server.py`（約 5,100 行、
   221 エンドポイント）が全 API を提供し、`main/main.py` は tkinter デスクトップ GUI
   ランチャー。マイクロサービス分割はコード上に存在しない。

---

## 2. 不足 — 対応済み（本ブランチのコミットで解消）

| # | 欠落していた機能 | 症状 | コミット |
|---|---|---|---|
| 1 | 2FA の永続化層 | `TwoFactorAuthService` が `db_manager=None` でマネージャを構築しており、setup が生成した秘密鍵・バックアップコードはどこにも保存されず、enable/verify/status が全て機能しない見せかけ実装だった | `2c6f0fd` |
| 2 | バックアップコードの使い捨て化 | 単回使用の消費機構がどの層にも無く、漏洩コードが無限に再利用可能な設計だった | `2c6f0fd` |
| 3 | 新規ユーザーのクレジット入手経路 | 初期残高 0 のまま入手手段が無く、有償リスティングを永久に購入不能だった。登録時に 50 クレジット付与で暫定対応 | `0f9a100` |
| 4 | コミッション紛争のエスカレーション | `moderation_queue.VALID_KINDS` に `commission_dispute` が宣言されていたが、それを生成する手段が存在しなかった。`POST /api/commissions/{id}/dispute` を新設 | `b86c334` |
| 5 | 通報→統合モデレーションキューの配線 | キュー自体は完成・テスト済みだったが、リスティング通報・レビュー通報・クリエイター申請のどれも `enqueue()` を呼んでいなかった。作成側・解決側の両方を配線 | `2a80aaf` |
| 6 | コレクションのライブ状態表示 | `item_ids` の生配列しか返さず、表示にアイテム数ぶんの API 呼び出しが必要だった。`get_items_with_status()` + `GET /api/collections/{id}/items` を新設 | `a4c5528` |
| 7 | ビルド可能なデプロイ構成 | `docker-compose.yml` が実在しない 5 つのサービス別 Dockerfile を参照しておりビルド不能だった。実在する構成（単一 api サービス + uvicorn 起動）に修正 | `0f9a100` |
| 8 | `qrcode` 依存の宣言と障害分離 | `requirements.txt` 未宣言のパッケージに `setup_2fa()` が無条件依存し、未インストール環境で 2FA の入口が全滅していた | `2c6f0fd` |

---

## 3. 不足 — 未対応（優先度順）

いずれも「一行修正」ではなく製品・法務レベルの判断を要するため、実装せず所見として残す。

### 3-1. クレジット購入フロー（実通貨 → クレジット）が存在しない【優先度: 最高】

- **事実**: `main/billing_service.py` の Stripe 連携はサブスクリプション課金専用
  （`mode == "subscription"`）。全 webhook ハンドラ（`_WEBHOOK_HANDLERS` に登録された
  `_handle_subscription_update` / `_handle_checkout_completed` / `_handle_invoice_payment` 等）を
  確認したが、どれも `marketplace_store.credit()` を呼ばない。
- **`credit()` の全呼び出し元**（検証: `grep -rn "\.credit(" main/ | grep -v "def credit"`）は
  ギフトカード還元・紹介ボーナス・返金・サインアップボーナスの 4 系統のみで、
  実通貨からの入金経路がゼロ。
- **帰結**: サインアップボーナス 50 クレジットを使い切ったユーザーに追加入手手段が無く、
  有償マーケットプレイスが商売として成立しない。
- **必要な実装**: Stripe one-time payment のチェックアウト + webhook + 冪等性処理。
  `main/idempotency.py` が既存なので再利用できる。

### 3-2. クリエイター売上の現金化（クレジット → 実通貨）が存在しない【優先度: 高】

- **事実**: Stripe Connect・payout・transfer に類する機構が皆無
  （検証: `grep -rin "connect\|payout\|transfer\|cashout" main/billing_service.py` → 送金関連ヒットなし）。
- **帰結**: 3-1 と合わせ、クレジット経済は入口・出口とも実通貨と断絶した閉鎖系。
  クリエイターは売上をプラットフォーム内でしか使えない。
- **注意**: 資金移動業などの法規制判断を伴うため、技術実装より先にビジネス判断が必要。

### 3-3. アカウント削除のカスケードが存在しない【優先度: 高（法的リスク）】

- **事実**: `main/auth_manager.py` の `delete_user()`（407 行付近）は auth 内部の
  3 インデックス（`_by_id` / `_by_username` / `_by_email`）から pop するのみ。
  マーケットプレイス残高・取引台帳・公開リスティング・カート・ウィッシュリスト・
  コレクション・コミッション・紹介コード・会員ティア・ライセンスキー・
  **2FA 秘密鍵とバックアップコード**（`two_factor_auth.TwoFactorStore`）が全て残存する。
- **さらに**: この機能は管理者専用エンドポイント（`DELETE /api/admin/users/{user_id}`）のみで、
  ユーザー自身によるセルフ削除 API が存在しない。GDPR / CCPA の消去権に相当する機能の欠落。
- **必要な実装**: 10 以上のストアを横断する削除 or 匿名化。会計上の保持義務
  （台帳は消さず匿名化する等）の設計判断を伴う。

### 3-4. ビジネスデータの永続化が存在しない【優先度: 高】

- **事実**: マーケットプレイス・カート・ギフトカード・コミッション・モデレーション・
  会員ティア・ライセンス・紹介・2FA など、事実上すべてのビジネス状態がプロセス内
  Python dict（`threading.Lock` 保護のシングルトンストア）のみに存在する。
  PostgreSQL（`main/database_manager.py`）と Redis（`main/redis_cache_manager.py`）の
  基盤は存在するが、`main/api_server.py` からの実利用は各 2 箇所のみ
  （検証: `grep -c "get_database_service()\|get_cache_manager()" main/api_server.py`）。
- **帰結**: プロセス再起動（デプロイ・クラッシュ）で全データ消失。複数ワーカー・
  複数レプリカでは状態が分裂するため水平スケール不可。
- **注意**: 全ストアが同一のシングルトン + Lock パターンで書かれているため、
  ストアの下に永続化バックエンドを差す移行は機械的に進めやすい。

### 3-5. ログイン時に 2FA が強制されない【優先度: 中】

- **事実**: `auth_manager.login()` は 2FA の有効状態を一切参照しない
  （検証: `grep -in "2fa\|totp\|two_factor" main/auth_manager.py` → 0 件）。
  `2c6f0fd` で 2FA の永続化は機能するようになったが、有効化してもログインが
  2 要素にならない。`/api/2fa/*` は独立 API として動くだけ。
- **必要な実装**: login → 「2FA 有効なら一時トークンを返し、TOTP 検証後に本トークン発行」
  という 2 段階フロー。`auth_manager.py` は 193 テストを持つため慎重な変更が必要。

### 3-6. Prometheus の実スクレイプ対象が無い【優先度: 低】

- **事実**: `main/api_server.py` の `/metrics` は JSON レスポンス + 認証必須で、
  Prometheus のテキスト形式ではない。本物のエクスポーター（`main/prometheus_monitor.py`、
  `prometheus_client.generate_latest` 使用）は独立プロセス設計で API サーバーに未統合。
  詳細は `docker/prometheus.yml` 内のコメント参照。

---

## 4. 過剰 — 死んでいる / 余剰な機能

### 4-1. 到達不能モジュール 60/95（63%）

`main/` 配下 95 モジュールについて、2 つの実エントリポイント（`api_server.py` と
`main.py`）からの import 推移閉包を BFS で計算した結果、**60 モジュールがどちらからも
到達不能**。BCI（脳コンピュータ接続）・ブロックチェーン監査・NFT・メタバース統合・
エッジ AI・音声クローン・写真→アバター生成などの野心的 R&D 群がこれに含まれる。

再検証用スクリプト（リポジトリルートで実行）:

```python
import re, glob, os
def local_imports(path):
    src = open(path, encoding="utf-8", errors="ignore").read()
    mods = set()
    for m in re.finditer(r"from \.(\w+) import", src): mods.add(m.group(1))
    for m in re.finditer(r"^\s*import (\w+)$", src, re.MULTILINE): mods.add(m.group(1))
    for m in re.finditer(r"from (\w+) import", src): mods.add(m.group(1))
    return mods
files = {os.path.basename(p)[:-3]: p for p in glob.glob("main/*.py")}
graph = {n: local_imports(p) & set(files) for n, p in files.items()}
def reach(root):
    seen, stack = {root}, [root]
    while stack:
        for d in graph.get(stack.pop(), set()):
            if d not in seen: seen.add(d); stack.append(d)
    return seen
dead = sorted(set(files) - reach("api_server") - reach("main"))
print(len(dead), dead)
```

注意: この BFS は静的 import のみを見る。`main.py` が **subprocess 経由で**起動する
GUI ツール（`avatar_preset_linker_gui.py` 等）や、`__main__` を持つ独立 CLI は
「到達不能」と出ても実際には使われうる（後述 5 節）。60 件の一括削除は不可。個別精査が必要。

### 4-2. 置換済みの残骸 3 ファイル【削除推奨・未実行】

以下の 3 ファイルは最も厳格な基準で「死んでいる」ことを確認済み:

- `main/preset_manager.py`（+ `tests/test_preset_manager.py`）
- `main/preset_diff_core.py`（+ `tests/test_preset_diff_core.py`）
- `main/preset_schema.py`（+ `tests/test_preset_schema.py`）

根拠:
1. **importer ゼロ**: `grep -rln "preset_manager\|preset_diff_core\|preset_schema" main/ scripts/ setup_*.py`
   で自分自身とテスト以外のヒットなし（動的 import も `importlib\|__import__` で確認済み）。
2. **`__main__` エントリポイント無し** = 独立 CLI としての用途も無い。
3. **機能は置換済み**: `preset_manager` の役割（名前付きパラメータセットの保存）は
   `main/database_manager.py` の `create_avatar_preset(user_id, name, parameters)` が
   `/api/avatars`（api_server.py 内）で**実際に稼働中**。しかも旧実装には `user_id` の概念も
   `threading.Lock` も無く、仮に API に配線すればクロスユーザー脆弱性を生む代物。

削除はエージェント実行環境の権限制約でブロックされたため未実行。次の 1 コマンドで完了する:

```bash
git rm main/preset_manager.py main/preset_diff_core.py main/preset_schema.py \
       tests/test_preset_manager.py tests/test_preset_diff_core.py tests/test_preset_schema.py
# tests/run_safe.py から "tests.test_preset_manager" / "tests.test_preset_schema" /
# "tests.test_preset_diff_core" の 3 行も削除すること
```

### 4-3. 死コードに対するテスト投資 812 関数 / 8,333 行

到達不能な 60 モジュールのうち 58 個にテストファイルが存在し、その合計は
**812 テスト関数・8,333 行 = テストスイート全体の約 32%**。CI 実行のたびに、
本番でどのユーザーも通れない経路を検証し続けている。テスト自体は品質が高く
「将来配線されたときの保険」の価値はあるため、即削除ではなく 4-1 の個別精査と
セットで判断すべき。

### 4-4. ~~虚構の 5 マイクロサービス docker-compose~~（解消済み）

実在しない 5 つの Dockerfile を参照する構成だったが、`0f9a100` で実態
（単一 api サービス）に修正済み。

---

## 5. 過剰に見えて正当なもの（誤検出への注意書き）

将来の監査者が誤って「削除対象」と判定しないための注記:

| 対象 | 一見 | 実際 |
|---|---|---|
| 3D モデル配布機構の不在 | 重大な欠落 | 意図的スコープ（1 節参照）。README が宣言済み |
| `preset_history_*` 系 5 ファイル | preset 残骸の仲間 | `if __name__ == "__main__"` を持つ独立 CLI ツール。削除不可 |
| `billing_service` と `membership_manager` の二重「ティア」 | 概念の重複実装 | 別軸（サブスク課金プラン vs 生涯購入額ロイヤルティ）。統合不要 |
| クレジット台帳（`_credit_ledger`） | in-memory で脆弱 | append 専用 + `verify_ledger_integrity()` による自己整合性検証つき。アプリ層の設計としては健全（永続化の問題は 3-4 に帰着） |

---

## 6. 推奨着手順

1. **クレジット購入フロー（3-1）** — 有償マーケットプレイスが商売として成立する最低条件
2. **アカウント削除カスケード（3-3）** — 法的リスクの解消
3. **永続化（3-4）** — 1・2 の成果を再起動で失わないための土台（順序を上げる判断もあり）
4. **死コード削除** — 4-2 の 3 ファイルは即実行可能。残り 57 モジュールは個別精査後に一括判断
5. **ログイン 2FA 強制（3-5）** — セキュリティ完成度の引き上げ
