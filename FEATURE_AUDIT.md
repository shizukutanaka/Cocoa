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
| 42 | パスワードリセット（パスワード忘れ）フローのUI皆無 | `POST /api/auth/password-reset`・`.../confirm` は完成・テスト済みだったがフロント未接続で、パスワードを忘れたユーザーがアカウントを回復する手段が皆無だった（本番マーケットプレイスとしての実質的欠落）。ログインページに「パスワードをお忘れですか？」リンク、新規 `/forgot-password`（メール入力→存在の有無を漏らさない一律応答＝バックエンドの列挙防止設計と一致。開発環境で `COCOA_EXPOSE_RESET_TOKEN=true` 時は dev_token とconfirmページへの直リンクを表示）、新規 `/reset-password`（メールリンクの `?token=` から自動入力・手動編集可＋新パスワード＋確認フィールドでクライアント側不一致チェック→成功時ログインへリダイレクト）。Playwright検証（`COCOA_EXPOSE_RESET_TOKEN=true` の実サーバー）: リンク→リセット申請で dev token 表示→トークン自動入力で進む→新パスワード設定→ログインへリダイレクト、その後**新パスワードは認証成功（200）・旧パスワードは拒否（401）**でパスワードが実際に変更されたことを確認。バックエンド変更なし（225/225）、build/lintクリーン | `0433420` |
| 41 | ギフトカードの事前確認（lookup）UI皆無 | `GET /api/gift-cards/lookup`（公開: 金額・有効性を購入者情報なしで返す）は完成・テスト済みだったがフロント未接続で、交換者はコードの金額や使用済みかどうかを実際に交換を試みるまで知る手段がなかった。ギフトカードページの交換フォームに「確認」ボタンを追加し、交換前に金額・有効期限を表示（使用済み/無効/期限切れの場合は明確なメッセージ）。lookup で無効が確定した場合は「使用する」ボタンを無効化し、既知の無効コードを送信できないようにした。コード編集時は古いプレビューをクリア。Playwright検証: 新規作成した10クレジットカードをlookupすると「10 クレジット」表示→交換で残高加算、存在しないコードのlookupはエラートースト（想定される404）でクラッシュせず処理。バックエンド変更なし（48/48）、build/lintクリーン | `a5f6f19` |
| 40 | VRChatパフォーマンス分析がUI未接続＋Quest指定で必ず400になるバグ | `POST /api/tools/vrchat/performance` は完成・テスト済みだったがフロント未接続。実装中に**バグを発見**: エンドポイントが `Platform.Quest if body.platform.lower() == "quest" else Platform.PC` としていたが、`Platform` enum は `PC`/`ANDROID`/`IOS` のみで `Quest` メンバーが存在せず、`Platform.Quest` が AttributeError を投げるため**Quest指定のリクエストが必ず400**になっていた（PCパスは動作）。QuestはVRChatではAndroidベースで分析器も非PCにANDROID_LIMITSを適用するため、quest/android→`Platform.ANDROID`にマップ。回帰テスト `test_performance_endpoint_accepts_quest_platform` をパッケージimport回帰クラス（サブプロセス）に追加。`VRChatTools.tsx` をタブ化（パラメータ予算/パフォーマンスランク）、新規 `PerformanceTool`（ポリゴン/マテリアル/ボーン/PhysBones/テクスチャメモリ/PC・Quest入力→ランク・スコア・検出された問題・カテゴリ別改善提案を表示）。E2E中に発見したフロントクラッシュも修正: レスポンスの `issues` は文字列でなくオブジェクト配列（`{severity, category, message, current, target}`）で、直接描画するとReact error #31でErrorBoundaryに落ちていた→型修正し`issue.message`を描画。Playwright検証: Questパス（旧400）が「Very Poor」＋ポリゴン数問題＋Polygon Reduction/Material Optimization提案を返す、PCパスも描画。4xx/5xxゼロ、バックエンド114/114（新規1件）、build/lintクリーン | `5000049` |
| 39 | VRChatパラメータ予算ツールがUI未接続＋本番で常に503になる import バグ | `POST /api/tools/vrchat/budget`（256ビット予算分析・最適化提案）と `/performance` は完成・テスト済みだったがフロント未接続。実装中に**本番バグを発見**: 両エンドポイントが `from vrchat_parameter_budget import ...` というフラット import を使用していたが、正規の起動方法 `uvicorn main.api_server:app`（Docker CMD・本番）ではこのファイルが `main` パッケージ配下にあるため bare import が ImportError となり、両ツールが**常に503を返す**状態だった。他のsibling importと同じ「相対import優先→フラットフォールバック」に修正。回帰テスト `TestVRChatToolsPackagedImport` はサブプロセスで `import main.api_server`（失敗していた正確な文脈）を実行して検証（他のテストは意図的に main/ を sys.path に載せるため bare import が解決してバグを隠す）。修正前のフラットimportに対してテストが FAIL することを確認済み。新規公開ページ `/tools/vrchat`（トップナビ「ツール」）: パラメータ表（名前/型/同期）の追加削除→予算エンドポイント呼び出し→使用ビット/256ビット・プログレスバー・型別内訳・予算超過警告・最適化提案を表示。Playwright検証: Bool+Intで9/256ビット予算内、同期Float34個追加で予算超過警告（281/256, +25）とOSCビットパッキング提案。修正後4xx/5xxゼロ（503は修正前のみ）。バックエンド593/593（新規2件）、build/lintクリーン | `fbd82eb` |
| 38 | リスティングのバージョン履歴UI・評価分布の可視化が皆無 | `GET /api/marketplace/{id}/versions`（全バージョン履歴）・`POST .../versions`（新バージョン公開）・`GET .../rating-distribution`（星別分布）は完成・テスト済みだったがフロント呼び出しゼロ。詳細ページに評価分布セクション（5→1星のバーチャート、平均・件数、公開可視の投票のみ集計しヘッドラインの平均と一致、評価ゼロ時は非表示）とバージョン履歴セクション（新しい順、changelog 表示、オーナーには changelog + 任意の更新パラメータ（submit 前に JSON 検証）を受け取る公開フォーム、非オーナーには自動生成の v1 のみの場合は非表示）を追加。Playwright検証: 5★+4★のレビューで平均4.5と正しい比率のバー表示、オーナーが v2 を changelog 付きで公開→履歴の v1 の上に表示、非オーナーは同じ履歴を見られるが公開ボタンは非表示。バックエンド変更なし（591/591）、build/lintクリーン | `6851a22` |
| 37 | CC BY/CC BY-SAリスティングのクローン（リミックス）UI皆無＋ダウンロード履歴ページなし | `clone_listing()`（メタデータ＋パラメータの完全値をコピー、CC BY/CC BY-SAのみ許可・事前購入不要）は完成・テスト済みだったが呼び出しゼロで、プラットフォーム自体がリミックス文化を前提にしたライセンス選択肢を用意しているのに実際にリミックスする手段が皆無だった。`ListingDetail.tsx`に「クローンして自分の作品として公開」ボタン（`listing.license_type`が`cc_by`/`cc_by_sa`の場合のみ表示、`CLONEABLE_LICENSES`をサービス層でエクスポートしゲート条件がバックエンドの許可値と乖離しないようにした。オーナー自身でもクローン可、バックエンド側にも所有者制限がないため一致）。新規`me/DownloadHistory.tsx`（`GET /api/marketplace/downloads/history`、削除済みリスティングは「削除されたリスティング」と表示）。Playwright検証: CC BYリスティングにのみボタン表示（personal ライセンスでは非表示）、クローン実行で「...(clone)」という名前の新規リスティングが自分の所有として作成されCC BYを継承（さらにリミックス可能）、ダウンロード履歴に元のダウンロードが表示。4xx/5xxゼロ、バックエンド変更なし（591/591）、build/lintクリーン | `ed8863a` |
| 36 | フォロー中クリエイターのフィード・公開コレクション閲覧が皆無 | `GET /api/auth/feed`と`GET /api/collections/public`は完成済みだったがフロント未接続。フォロー機能自体はラウンド3で配線済みだったが、フォローする実利（新着通知以外の可視的な効果）が皆無だった。新規`me/Feed.tsx`（トップナビ「フィード」、マーケットプレイス/バンドルの隣）でフォロー中クリエイターの新着を新しい順に表示。`Collections.tsx`に「自分のコレクション/公開コレクションを探す」タブを追加、公開タブはデバウンス検索＋`Collection.to_dict()`が`owner_id`のみで`owner_username`を持たないため`getPublicProfile()`によるオンデマンド解決（チップ送信履歴・ライセンス一覧で確立した同一パターンを再利用）。Playwright検証: フォロー中クリエイターが新規公開した直後にフィードへ即座に反映、公開コレクションがオーナー名・説明付きで表示、一致しない検索語で正しく空状態にフォールバック。4xx/5xxゼロ、バックエンド変更なし（390/390）、build/lintクリーン | `0320fd5` |
| 35 | リスティング譲渡・在庫上限設定のUI皆無（ユーザー名検索エンドポイントも未接続） | `transfer_listing()`・`set_stock_limit()`は完成・テスト済みだったがフロント呼び出しゼロで、クリエイターはリスティングを別アカウントに移す・販売数に上限を設ける手段がなかった。譲渡APIは`new_owner_id`（生のユーザーID）を要求するがそれを知る手段がなかったため、`GET /api/users/search`（これも完全に未接続だった）を使ったユーザー名検索オートコンプリートを新設。`MyListings.tsx`の各行に「詳細設定」トグル（デフォルト折りたたみ、ライセンス/取り下げボタンで既に混雑していたため）→在庫（現在の状態表示＋上限設定＋「無制限にする」）と譲渡（ユーザー名検索→選択→`window.confirm`で不可逆であることを明示した上で確定）。Playwright検証: 在庫上限5設定で「残り5/5」表示→無制限化で「無制限」に復帰、ユーザー名検索で候補表示→選択→譲渡確定→元のオーナーの一覧から消失・`GET /api/marketplace/mine`で新オーナーの所有をAPI側からも確認。4xx/5xxゼロ、バックエンド変更なし（816/816）、build/lintクリーン | `625b2ef` |
| 34 | リスティング/レビューの通報UIが皆無（信頼性・安全性の穴） | `POST /api/marketplace/{id}/report`と`reviews/{id}/report`は理由enum・自己通報/重複審査中の拒否・統合モデレーションキュー連携まで完成済みだったがフロント呼び出しがゼロで、買い手が不適切なコンテンツを報告する手段が一切なかった（既存の通報レコードがあったとしても生API呼び出し経由のみで作られたことになる）。`ListingDetail.tsx`に「このリスティングを通報する」リンク（自分のリスティングには非表示）＋理由選択＋任意詳細。各レビューの「役に立った」の隣に小さな「通報」リンク（`ReportReviewButton`コンポーネント）。実装中に判明: レビュー行の「通報」ボタンとリスティング側「...を通報する」リンクは両方とも部分文字列「通報」を含むため、Playwrightの`has-text`セレクタが曖昧に一致（UIバグではなくテストスクリプト側の問題、`.row-list`スコープで解消）。Playwright検証: リスティング通報→確認トースト、レビュー通報→確認トースト、同一リスティングへの2件目の審査中通報が正しく400（「すでに...審査中です」）でクラッシュせず処理される。4xx/5xx想定内（重複通報の400のみ）、バックエンド変更なし（591/591）、build/lintクリーン | `2dfe6a7` |
| 33 | クリエイター統計・収益ダッシュボード皆無＋クリエイター認定申請への導線なし | `GET /api/marketplace/analytics/me`（タグ/カテゴリ別DL内訳・人気リスティング・評価分布）と`earnings/me`（販売/チップ別収益）は完成済みだったがフロント呼び出しゼロで、クリエイターは公開ストアフロントの基本3統計以上の情報を見る手段がなかった。また`Creator.tsx`はラウンド3から`is_creator_verified`の「✓ 認証済み」バッジを表示していたが、実際に申請する導線（`POST /api/auth/creator-application`、完成・テスト済みだが未接続）が存在しなかった。新規`me/CreatorDashboard.tsx`（「ダッシュボード」タブ）に3セクション: 統計（公開数/総DL数/累計売上/レビュー数＋人気リスティング・タグ・カテゴリ別内訳、既存のスタットタイル/リストパターンを再利用しチャートライブラリ導入を回避）、収益（7/30/90日切替）、クリエイター認定申請（理由＋任意ポートフォリオURL、審査中/認定済み/却下のステータス表示、却下時のみ再申請可）。`getMyCreatorApplication()`は未申請時の期待される404を「申請なし」として扱う（他のオプショナルリソース取得と同じパターン）。Playwright検証: 1件販売済みのクリエイターで統計が正確に反映（DL数1・売上20cr・人気リスティング表示）、申請→審査中→リロード後も状態保持・フォーム非表示を確認。4xx/5xxゼロ（捕捉された唯一の404は申請前チェックの想定内応答）、バックエンド変更なし（816/816）、build/lintクリーン | `e34fe5b` |
| 32 | APIキー管理・会員ランク表示・価格変更履歴のUI未接続 | 発見性ワークフローの`deferred_no_action`（優先度は低いが「良いフィラー」と評価済み）から3件。`APIキー`（`/api/auth/api-keys` CRUD）: 生キーは作成時に一度だけ返る設計に合わせ、`Security.tsx`に2FAのバックアップコード表示と同じ「一度だけ表示」パターンで追加、以降は`key_prefix`のみ表示。`会員ランク`（`GET /api/membership`）: `Profile.tsx`に読み取り専用カード（ランク名・手数料割引率・次のランクまでの必要クレジット）。`価格変更履歴`（`GET /api/marketplace/{id}/price-history`）: `ListingDetail.tsx`に折りたたみセクション、価格が実際に変動した（履歴2件以上）リスティングのみ表示し初回公開のみのリスティングに冗長な1行を出さないようにした。Playwright検証: 価格を2回変更したリスティングで新しい順に3件表示、新規アカウントのプロフィールで「ブロンズ・次のランクまであと1,000cr」表示、APIキー作成で`cca_...`が一度だけバナー表示され以降はプレフィックスのみ、無効化で一覧が空に。4xx/5xxゼロ、バックエンド変更なし（336/336）、build/lintクリーン | `a94f722` |
| 31 | コミッション（受注制作）UI皆無 — 発見性ワークフロー最終項目 | 発見性ワークフロー総合ランキングの最終項目。自身のランキングで「本セッション最大の残存範囲（2つのダッシュボード・6段階以上の状態遷移）」と明示的にフラグされ、無理に早いラウンドに詰め込まず独立ラウンドとして先送りされていた。状態遷移（pending→accepted/declined→delivered→closed、＋モデレーションキュー連携の紛争提起）は`main/commissions.py`で完成・E2E相当のテストまで揃っていたがフロント呼び出しがゼロだった。`Creator.tsx`にチップ/フォローの隣に「コミッションを依頼する」ボタン（タイトル・依頼内容・参考予算＝実際の支払いはマーケットプレイス経由で別途、とバックエンドのdocstring通りに明記）。新規`me/Commissions.tsx`（受け取った依頼/自分の依頼タブ）は閲覧者の役割と現在のステータスに応じて有効なアクションのみ表示: クリエイターはpendingで承認/辞退・acceptedで納品、依頼者はpendingで取り消し・deliveredで受領クローズ、進行中/納品済みの双方で「問題を報告」（管理者モデレーションキューへ、`kind=\"commission_dispute\"`はサーバー側で宣言済みだったがこのUIが無ければ到達不能だった）。Playwright検証: 依頼→受け取った依頼タブで「承認待ち」→承認→「進行中」→納品→「納品済み」→自分の依頼タブに納品メッセージ表示→受領クローズ→双方で「完了」、全遷移で4xx/5xxゼロ。バックエンド回帰1327/1327（バックエンド変更なし）、build/lintクリーン。これでラウンド5〜9にわたる「バックエンド完成・フロント未接続」機能群（ライセンス・チップ・払い戻し・バンドル・コミッション）を完了 | `3489885` |
| 30 | バンドル（セット販売）UI皆無＋一時停止エンドポイント未配線 | 発見性ワークフロー総合ランキング4位、本セッション最大規模のラウンド。バンドル作成・購入APIは完成・テスト済みだったがフロントUIが皆無。実装中に発見: `BundleManager.deactivate_bundle()`/`activate_bundle()`はストア層で完成・単体テスト済みだったが、呼び出すHTTPエンドポイントが一つも存在せず、クリエイターが販売を止める唯一の手段が完全削除のみだった（`list_my_bundles`の`include_inactive`フラグも常に空振り）。`POST /api/bundles/{id}/activate`・`/deactivate`を新設（既存の作成/更新/削除エンドポイントと同じオーナー確認→403/404パターン）、テスト4件追加。公開ブラウズページ`Bundles.tsx`（トップナビ「バンドル」）: `Bundle.to_dict()`は`listing_ids`のみでリッチな商品情報や計算済み価格を持たないため、各カードが`ListingDetail.tsx`と同一の`["listing", id]`クエリキーで構成リスティングを解決しキャッシュ共有、サーバー側と同じ計算式（`unit_price * (100 - discount) // 100`）で割引後価格をクライアント側算出。クリエイター管理`me/Bundles.tsx`（「バンドル管理」タブ）: 自分の公開中リスティングからチェックボックスで2件以上選択→作成、一時停止/再開/削除。Playwright検証: 2点選択・25%引きでバンドル作成→公開中バッジ→購入者側で40cr→30cr表示を確認→購入で残高が正確に-30cr→クリエイターが一時停止→バッジが「一時停止中」に変化し公開一覧から即座に消失。4xx/5xxゼロ、バックエンド回帰1327/1327（新規4件含む）、build/lintクリーン | `a8cb891` |
| 29 | 払い戻し申請UI皆無（購入者の自己解決手段がなかった） | 発見性ワークフロー総合ランキング3位。`POST /api/refunds`（購入後72時間以内・1注文につき1件のpending/approvedリクエストのみをサーバー側で強制）と`GET /api/refunds/mine`は完成・テスト済みだったがフロント呼び出しがゼロで、購入者が問題のある注文に対して自己解決する手段がなく運営への手動対応に頼るしかなかった。`OrderDetail.tsx`の完了済み注文に「払い戻しを申請する」ボタン→理由入力フォーム、既存リクエストがあれば（`my-refunds`一覧を`order_id`で照合）フォームの代わりにステータス（審査中/承認済み/却下）と運営コメントを表示し、バックエンドが拒否するだけの重複申請導線を作らないようにした。新規`me/Refunds.tsx`（全申請履歴、ステータスバッジ、注文へのリンク）。Playwright検証: 購入→注文詳細→理由入力→申請→即座に「審査中」表示→`me/refunds`に同一リクエスト表示→再訪問時はフォームでなくステータスカード表示。4xx/5xxゼロ、バックエンド変更なし（160/160）、build/lintクリーン | `e59ba09` |
| 28 | チップ機能がUI未接続（送信・受信履歴とも皆無） | 発見性ワークフロー総合ランキング2位。`POST /api/tips`（冪等性キー対応・自己送金や1万クレジット超を拒否済み）と受信/送信履歴エンドポイントは完成・テスト済みだったがフロント呼び出しがゼロだった。`Creator.tsx`にチップ送信フォーム（フォローボタンの隣、金額+任意メッセージ、チェックアウトと同じ`newIdempotencyKey()`パターン）、新規`me/Tips.tsx`（受け取った/送った タブ）を追加。実装中に判明: `Tip.to_dict()`は`recipient_id`のみ保持し`recipient_username`を持たないため、「送った」タブでは初めて配線した`GET /api/users/{id}/profile`（`userService.getPublicProfile`）でオンデマンド解決。E2Eテスト作成中に「送る」ボタンのテキストセレクタが「チップを送る」トグルボタンにも部分一致し、フォームが送信されずに閉じるだけという事象が発生（UIバグではなくテストスクリプトの曖昧セレクタ問題と判明）→ 提出ボタンに`id="tip-submit"`を付与し解消。Playwright検証: チップ送信→トースト確認→送信者の「送った」タブにリンク付きで表示→受信者の「受け取った」タブに送信者名・メッセージ表示→残高が正確に+25。4xx/5xxゼロ、バックエンド変更なし（587/587）、build/lintクリーン | `4ab4da4` |
| 27 | ライセンスキー管理UI皆無（購入者は何を買ったか確認手段がなかった） | 発見性ワークフローの総合ランキングで最優先とされた項目: 有料・無料を問わず購入完了（直接ダウンロード・カートチェックアウト・バンドル購入の全経路）で`license_manager.issue_on_download()`がライセンスキーを自動発行済みだったが、購入者側に確認・アクティベートするUIが、クリエイター側に発行済みキーを確認・失効させるUIが、共に皆無だった。新規 `me/Licenses.tsx`（自分のキー一覧、リスティング名リンクは`ListingDetail.tsx`と同一クエリキーでキャッシュ共有、アクティベーション履歴、用途メモ付きアクティベートフォーム、上限到達時は無効化）。新規 `me/ListingLicenses.tsx`（`me/MyListings.tsx`の各行から遷移、オーナー専用、保有者ID・アクティベーション回数・失効操作）。実装中に判明: リスティング名自体に「ライセンス」という語を含めるとPlaywrightの`has-text`セレクタがリスティング名リンクと機能ボタンを曖昧に一致させることがあり、`aria-label`を追加して解消（副次的にアクセシビリティも向上）。Playwright検証: 購入→マイライセンスに表示（有効バッジ）→メモ付きアクティベート→履歴に記録、クリエイター側の同一キー確認→失効で「失効済み」に変化。4xx/5xxゼロ、バックエンド変更なし（631/631）、build/lintクリーン | `a2be559` |
| 26 | 保存済みXSS（プロフィールURL）＋プロモコードの譲渡未反映・クォータ誤集計（ワークフローによる敵対的検証済み監査で発見） | 並列調査ワークフロー（バックエンドギャップ探索・セキュリティレビュー・正しさレビュー・品質レビューの4系統＋各所見への敵対的検証）で発見・確認した3件。**保存型XSS（高深刻度）**: `auth_manager.update_profile()`が`website_url`/`avatar_url`のスキームを検証しておらず、ラウンド3で追加した`Creator.tsx`が両者を生の`&lt;a href&gt;`/`&lt;img src&gt;`として公開・未認証ページに描画していたため、`javascript:`URIを保存すればクリックした任意の訪問者（管理者含む、JWTはlocalStorageに常駐）のブラウザで実行される状態だった。`_sanitize_public_url()`（http(s)のみ許可、それ以外は例外を投げず黙って空文字列に）を新設し両フィールドに適用、`Creator.tsx`にもクライアント側の`isSafeHttpUrl()`を防御的に追加。**注意**: `social_links`の値は`@alice`等のハンドルでありURLではないため、同じサニタイザを適用したところ既存テストが失敗して発覚・除外した（過剰適用の自己訂正）。**プロモコードの譲渡未反映**: `transfer_listing()`がリスティングの`owner_id`のみ更新し`PromoCode.creator_id`を放置していたため、リスティング固有の有効なコードが譲渡直後に解決不能になり、旧オーナーは無効化可能・新オーナーは操作不能という状態だった。譲渡時に該当コードの`creator_id`も再割当（`listing_id=None`の汎用コードは意図通り元オーナーに残す）。**クォータの誤集計**: `create_promo_code()`の上限（50件）が無効化済みコードも含めた生涯合計を数えていたため、季節プロモ等で作成・無効化を繰り返すクリエイターが実質0件所有でも永久にロックされる状態だった。有効なコードのみでカウントするよう修正。回帰テスト10件追加。バックエンド699/699・225/225、build/lintクリーン | `0990d13` |
| 25 | プロモコードのパイプラインが両端未接続＋通知ミュート設定UI皆無 | カートは`promo_code`送信済み・チェックアウトは割引適用済みだったが、**作成側（クリエイター）も入力側（購入者）もUIが存在せず**パイプラインの両端が空だった。新規 `me/PromoCodes.tsx`（作成フォーム＋一覧＋ステータスバッジ「有効/期限切れ/使用上限到達/無効化済み」＋無効化）。`Cart.tsx` にコード入力＋`lookup_promo_code`での事前検証（無効コードをチェックアウト時の無言no-discountにしない）＋取り消し線付き割引表示、リロード後も`item.promo_code`から`useEffect`でプレビュー再構築。通知ミュート設定（`GET/PUT /api/notifications/preferences`）を通知ページに折りたたみセクションとして追加。Playwright検証: 作成→カートで適用（20cr→10cr表示）→チェックアウトで実際に10cr課金（残高50→40）を確認、別セッションでコード保存済みカートをリロードしても割引表示が復元、ミュートトグルが`muted_kinds`に反映。4xx/5xxゼロ、バックエンド変更なし（691/691）、build/lintクリーン | `f1e4cb4` |
| 24 | クリエイターページ・フォロー・トレンドがUI未接続（フォロー通知が発火不能） | フォロー系はサーバー側で完結済み（follow/unfollow・フォロワー数・`publish_avatar` のフォロワー通知配信）だったが、呼ぶUIが皆無のため実ユーザーには通知経路が永久に発火しない状態だった。ストアフロント（`GET /api/users/{id}/storefront`）・トレンド（`GET /api/marketplace/trending`）も同様に未接続。新規 `/users/:userId` ページ（プロフィールヘッダ＋認証済みバッジ＋フォロワー数＋フォロー/解除ボタン＋統計タイル＋リスティンググリッド）、詳細ページの「by クリエイター名」をリンク化（クリエイターが初めて回遊可能に）、`me/Following` タブ（一覧＋ワンクリック解除）、ランディングのトレンドストリップ（検索/フィルタ非適用時のみ表示＝検索結果を押し下げない）。Playwright検証: トレンド3件表示・詳細→ストアフロント遷移・フォローでボタンが「フォロー中」/フォロワー1人に変化・following一覧→解除で空に。4xx/5xxゼロ、バックエンド変更なし（801/801）、build/lintクリーン | `f1bd2e5` |
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
