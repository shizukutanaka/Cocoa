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
| 9 | ログイン時の 2FA 強制 | `auth_manager.login()` が 2FA 有効状態を一切参照せず、有効化してもパスワードのみでフルトークンが発行され続けていた。`PendingTwoFactor` 型 + `POST /api/auth/login/verify-2fa` を新設し、2FA 未設定ユーザーへの影響ゼロを維持したまま強制 | `0b7c24a` |
| 10 | Prometheus の実スクレイプ対象 | `/metrics` は JSON+認証必須で収集不能、本物のエクスポーターは独立プロセス設計で未統合だった。`get_prometheus_monitor()` シングルトンと `GET /metrics/prometheus`（未認証・Prometheusテキスト形式）を新設し `docker/prometheus.yml` から実際にスクレイプ可能に。`psutil.cpu_percent(interval=1)` の1秒ブロッキングは `run_in_threadpool` で回避 | `a6aa3f1` |
| 12 | Prometheus リクエスト計装（#10 のフォローアップ） | `#10` 時点では http request カウンタ・レイテンシヒストグラムがゼロのままだった。`security_middleware` に `_record_request_metrics()` を配線し全リクエストで `record_request` + `observe_request_duration` を記録。ラベルは生パスではなくルートテンプレート（`request.scope["route"].path`）に限定して高カーディナリティを回避、ルート未マッチ（404・レート制限拒否）は `unmatched` に集約。計装は best-effort（例外はレスポンスに影響させず握りつぶす） | `41d3301` |
| 11 | 非金銭データのアカウント削除カスケード（3-3 の一部） | 実装中に判明: `DELETE /api/auth/me` は**既に存在**していたが、パスワード確認なし（トークンのみでアカウント無効化可能というセキュリティ上の欠落）・ソフト削除のみ（`is_active=False`、ユーザー名/メール解放されず）・カスケードはリスティングのみという不完全な実装だった（当初の監査記述「セルフ削除APIが存在しない」は誤りだったため訂正）。パスワード確認必須の新実装に置き換え、`AuthManager.delete_own_account()` でハード削除（管理者削除と同じ`store.delete_user()`を使用しユーザー名/メールを解放）。カート・ウィッシュリスト・コレクション・保存検索・通知・2FA秘密鍵を横断削除する `_cascade_delete_user_data()` を新設し、管理者削除エンドポイントとも共有。クレジット残高・台帳・コミッション・紹介コード・会員ティア・ライセンスキーは会計/法務判断が必要なため意図的に対象外（3-3後半として下記に残す） | `37d7287` |
| 13 | 決済系2エンドポイントの冪等性欠如 | gift/tip/gift-card購入/gift-card交換の4エンドポイントは`Idempotency-Key`ヘッダに対応済みだったが、最も金額の大きい`POST /api/cart/checkout`と`POST /api/bundles/{id}/purchase`だけ未対応。リトライで注文レコード重複・副作用（ティア加算等）の二重発火が起きる状態だった。既存4エンドポイントと同一パターンで統一 | `0ff3cc5` |
| 14 | `/api/2fa/enable`が実際には有効化しない | `setup_2fa()`を再度呼び秘密鍵を上書きした上、検証成功時も有効化状態を永続化する処理が皆無で、レスポンスは常に`{"status":"enabled"}`という嘘を返していた。`TwoFactorAuthService.enable_user_2fa()`を呼ぶよう修正 | `47e4137` |
| 15 | `/api/2fa/verify-backup`が常に例外 | エンドポイント関数名が`main/two_factor_auth.py`からインポートした同名の便利関数`verify_backup_code`と衝突（シャドーイング）。実行時に自分自身を誤って呼び出しシグネチャ不一致で必ず例外になっていた。関数名変更で解消 | `47e4137` |
| 16 | `POST /api/2fa/setup`がqrcodeインストール環境で常に500 | `qr_code_image`が生PNGバイト列のままFastAPIのJSONレスポンスに直接返され、`jsonable_encoder`のUTF-8デコードでクラッシュしていた。base64の`data:image/png;base64,...`形式に変更 | `252bd22` |
| 17 | Web フロントエンドが未接続・未ビルド | `frontend/`にVite+React+TSのSPAが存在したが、依存2つ欠落・lockfileなし・`tsconfig.node.json`不在で`tsc`が即失敗という**ビルド不能**な状態だった。さらに呼び出すAPI契約（`/api/v1/ai/generate-avatar`等）が実バックエンドに一切存在せず、ダッシュボードの統計は全てハードコードのダミー値。実際の221エンドポイント（認証+2FA・マーケットプレイス・カート決済・コレクション等）に対応する画面が皆無だった。依存を37→12パッケージに削減し、実APIに接続する7ページ（ログイン+2FA・登録・マーケットプレイス閲覧・詳細・カート決済・コレクション・マイページ5タブ）に全面再構築。`main/api_server.py`に`frontend/dist`を配信するStaticFilesマウント + SPAフォールバックルートを追加（`dist`未ビルド時は従来のJSON応答を維持し後方互換）。`npm run build`/`tsc --noEmit`/`eslint`が通ることを確認の上、実際に`uvicorn`を起動しPlaywrightで実ブラウザ検証（登録→ログイン→2FA設定でQRコード実際に表示→出品→カート追加→チェックアウト→注文履歴、コンソールエラー0件） | `dfff4e3` |
| 18 | Docker イメージがフロントエンドを含まず、デフォルト CMD が矛盾 | `docker/Dockerfile`は単一ステージで `python main/main.py`（tkinter GUI）をデフォルト起動していた（`docker-compose.yml`側の`command:`上書きで実害は無かったが、`docker run`単体では起動しない）。かつ`frontend/`を一切ビルド・同梱しておらず、#17のStaticFiles配信は空振りする状態だった。node:22-slimでフロントエンドをビルドしpython:3.11-slimにコピーする2段階構成に変更、CMDもuvicorn起動に修正。`docker-compose.yml`の環境変数も実際にコードが読まない変数（`COCOA_SECRET_KEY`/`DATABASE_URL`等、到達不能な`config.py`専用）から実変数（`COCOA_JWT_SECRET`/`DB_HOST`等）に修正し、Postgres/Grafanaのハードコードパスワードも変数化（Grafanaは未設定時に明示的に失敗するよう`:?`必須指定）。存在しない`docker/frontend.Dockerfile`を参照していた別サービスも削除（フロントエンドはapiサービスの単一イメージに統合済みのため）。**検証の限界**: サンドボックスのegressポリシーがDocker Hub（`registry-1.docker.io`）を403で拒否するため、実際の`docker build`は実行できず未検証（`docker compose config`によるYAML/変数解決の検証のみ実施）。パス整合性（`WORKDIR /app` + `COPY main/`/`COPY frontend/dist` が `_FRONTEND_DIST_DIR` の実際の解決先と一致するか）は手動でトレース確認済み | `640fbb3` |
| 19 | 架空ドメイン `cocoa-avatar.com` のハードコード | 到達不能な2モジュールが、このプロジェクトが所有していないドメインをあたかも実在するインフラのように直書きしていた: `nft_avatar_manager.py`のNFTメタデータ`external_url`が常に`https://cocoa-avatar.com/avatar/{hash}`を返し、`global_edge_manager.py`の`cdn_domains`が`cdn.cocoa-avatar.com`等3つを既定値としていた。前者は`COCOA_NFT_EXTERNAL_URL_BASE`未設定時はフィールド自体を省略（NFTメタデータ仕様上オプショナル）、後者は`COCOA_CDN_DOMAINS`（カンマ区切り）読み込み・未設定時は空リストに変更。「CDN未設定」を正直な既定値とした | `0b9299d` |
| 20 | フロントエンドのAPIカバレッジが低い（221エンドポイント中25呼び出しのみ） | レビュー投稿/閲覧・注文詳細・ギフトカード購入/交換の3画面が未実装だった。`ListingDetail.tsx`にレビュー一覧+投稿フォーム（`StarRating`コンポーネント）、`me/OrderDetail.tsx`、`me/GiftCards.tsx`（購入/コード交換/自分のカード一覧）を追加。実uvicorn+Playwrightで検証: 未購入リスティングへのレビュー投稿が正しく400（「購入済みのリスティングのみレビューできます」）、購入後は成功（5つ星+テキスト+役に立った投票ボタンが表示、平均評価が更新）、残高超過のギフトカード購入が正しく400（「残高不足」）、許容範囲内では201+一覧に反映、を確認。25→28エンドポイント呼び出しに増加（依然として大部分は未カバー、優先度に応じて継続） | `ca50e0f` |
| 23 | 紹介プログラムが実質機能不全（登録経路が未配線）＋レビュー返信UI皆無 | バックエンド突合調査で発見: `ReferralManager.apply_referral_code()` は完成・単体テスト済みで、成立側（`on_first_purchase` → 紹介元へ50cr）も3つの購入経路すべてに配線済みだったが、**呼び出す側が存在しなかった**。`POST /api/auth/register` に `referral_code` フィールドが無く、実際のサインアップから紹介レコードが作られる経路がゼロ＝ボーナスは永久に発火しない（`is_active`未シリアライズ・2FA有効化と同種の「配線漏れ」実バグ）。`RegisterRequest` に `referral_code: Optional[str]` を追加し、登録成功後に best-effort で適用（無効コード・自己紹介・マネージャ不在でも登録は失敗しない、signup bonus と同一パターン）。回帰テスト4件追加。UI: `Register.tsx` に招待コード欄（`/register?ref=CODE` から自動入力・編集可）、新規 `me/Referrals.tsx`（自分のコード＋招待リンクのコピー、統計タイル、招待履歴と成立バッジ）、「友達を招待」タブ。レビュー返信: バックエンド完備（`/api/marketplace/reviews/{id}/replies` POST/GET/DELETE）だがUI皆無だった。`ReviewReplies` コンポーネントをレビュー欄に追加（スレッド表示・インライン返信フォーム・自分の返信の削除、GET が要認証のため未ログイン時はクエリ自体を発行しない）。実uvicorn+Playwrightで検証: `?ref=` 付き登録（欄に自動入力）→紹介pending→有料リスティング購入→紹介元statsがconverted/+50crに変化→Referralsページに「購入済み」バッジと+50cr表示、返信の投稿→スレッド表示→削除。全フロー4xx/5xxゼロ。バックエンド1215/1215 | `662545c` |
| 22 | 発見性UI・AI生成開示・パラメータプレビュー・アクセシビリティ/性能（最新論文・業界情報リサーチに基づく） | 競合ベンチ（VRChat「試着」・手数料透明性）、EC検索ベストプラクティス（検索利用者はCVR2.5倍・オートコンプリートで摩擦30-50%減）、WCAG 2.2新設SC、EU AI Act第50条（2026-08-02施行）を調査。バックエンドに**完成済みだがフロント未使用**のAPIが複数存在していた。①検索オートコンプリート（`GET /api/search/suggest`、250msデバウンス）②カテゴリ/タグフィルタ（`/api/marketplace/categories`＋既存browse）③保存検索UI（`/api/search/saved` CRUD＋通知トグル、新規`me/SavedSearches.tsx`）④関連アバター（`GET /api/marketplace/{id}/related`）を配線。加えて実在しなかった2機能を新設: ⑤`is_ai_generated`フラグ（default False・後方互換、publish/update/to_dict＋リクエストモデルに配線、出品フォームのチェックボックス＋カード/詳細の「AI生成」バッジ）⑥パラメータプレビュー（`to_dict()`に`parameter_count`＋`parameter_keys_preview`＝キー名先頭10件を追加、**値は購入まで秘匿**のまま形状のみ開示＝パラメータ版「試着」）。さらにa11y/性能: skip-link・アイコンボタンのaria-label・`aria-pressed`・最小ターゲットサイズ、ルート分割（React.lazy+Suspense、メインバンドル298KB→254KB）、サムネ`loading="lazy"`、`usePageTitle`。実uvicorn+Playwrightで検証: オートコンプリート「fo」→「fox」候補表示・選択で検索遷移、カテゴリフィルタ、保存→保存検索ページに表示・通知トグル、詳細ページのAIバッジ/14件パラメータプレビュー（10チップ+「+4」）/関連2件、全フローでAPI 4xx/5xxゼロ。バックエンド1211/1211。**未実装/保留は据え置き**（Stripe決済・出金・永続化＝監査3節、C2PA署名＝アップロード基盤不在、MLレコメンド＝規模的に過剰） | `7aaa0e5` |
| 21 | 「買えるが売れない」フロントエンドの欠落、ウィッシュリストUI皆無、`is_active`のシリアライズ漏れ | バックエンドは`POST /api/marketplace/publish`・`PATCH/DELETE /api/marketplace/{id}`・`GET /api/marketplace/mine`・ウィッシュリスト一式（`GET/PUT/DELETE /api/wishlist/*`、価格下落/在庫切れ状態付き）を完備していたが、対応する画面が一切無かった。`me/CreateListing.tsx`（`MarketplaceStore.publish()`の制約に合わせたバリデーション付き出品フォーム）、`me/MyListings.tsx`（`include_inactive=true`で公開中/取り下げ済みを併せて表示、取り下げ操作）、`me/Wishlist.tsx`（`with_status=true`で値下がり/在庫切れ/削除済みバッジ、カートへの直接追加）、`ListingDetail.tsx`にウィッシュリスト追加/削除トグルを追加。実装中に発見: `MarketplaceListing.to_dict()`が`is_active`を返しておらず、`get_user_listings_page(include_inactive=True)`が公開中/取り下げ済みを一覧で返す設計であるにもかかわらず呼び出し元がどちらか判別不能だった（`main/avatar_marketplace.py`で修正、回帰テスト追加）。実uvicorn+Playwrightで検証: 出品→一覧表示→取り下げ（ラベルが「非公開」に変化しボタンが消える）、ウィッシュリスト追加→専用ページに反映（値下がり/在庫切れバッジ表示）→カートへ直接追加、を確認。全フローでAPI 4xx/5xxゼロ | `14f54bf` |

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

### 3-3. アカウント削除時の金銭・契約データの扱いが未決定【優先度: 高（法的リスク）】

セクション 2 の #11 で、非金銭データ（カート・ウィッシュリスト・コレクション・保存検索・
通知・2FA）のカスケード削除とパスワード確認必須のセルフ削除 API は実装済み。

- **残る事実**: `_cascade_delete_user_data()`（`main/api_server.py`）は
  マーケットプレイス残高・取引台帳・コミッション・紹介コード・会員ティア・ライセンスキーを
  意図的に削除対象外としている。理由はコメントに明記: 会計監査・契約記録としての
  保持義務があり得るため、削除するかハード削除するか匿名化するかは技術判断ではなく
  会計・法務判断を要する。
- **必要な実装**: 上記データを「削除」「匿名化（ユーザーIDのみ不可逆ハッシュに置換等）」
  「一定期間後に自動削除」のいずれで扱うかの方針決定後、`_cascade_delete_user_data()` に
  追加する。

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
2. **金銭・契約データの削除方針決定（3-3 残り）** — 会計/法務判断。非金銭データのカスケードは実装済み
3. **永続化（3-4）** — 1・2 の成果を再起動で失わないための土台（順序を上げる判断もあり）
4. **死コード削除** — 4-2 の 3 ファイルは即実行可能。残り 57 モジュールは個別精査後に一括判断

~~5. ログイン 2FA 強制~~ — `0b7c24a` で実装済み（セクション 2 参照）
~~6. Prometheus 実スクレイプ対象~~ — `a6aa3f1` で実装済み（セクション 2 参照）
~~7. 非金銭データのアカウント削除カスケード~~ — セクション 2 #11 で実装済み（金銭・契約データの扱いは 3-3 として残存）
~~8. 決済系エンドポイントの冪等性統一~~ — `0ff3cc5` で実装済み（セクション 2 #13）
~~9. legacy 2FA REST エンドポイントの実バグ3件~~ — `47e4137`/`252bd22` で実装済み（セクション 2 #14〜16）
~~10. Web フロントエンドの再構築・接続~~ — `dfff4e3` で実装済み（セクション 2 #17）
