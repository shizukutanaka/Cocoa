# Cocoa 引き継ぎ指示書 (Handoff Instructions for Opus / Sonnet)

このドキュメントは、**前提知識ゼロの新しい Claude セッション(Opus / Sonnet いずれも)が、この作業を安全に引き継ぐ**ために書かれている。
標準指示書ロジックのみで読めるよう、リポジトリ内の事実と実証済みコマンドだけを載せている。推測は書いていない。

まず `PRODUCT_ASSESSMENT.md`(長所・短所・改善案)と `FEATURE_AUDIT.md`(全 79 監査エントリ)を読むこと。この2つがプロダクトの現状の一次資料。

---

## 0. 30 秒サマリー

- **何を作っているか**: Cocoa = VRChat 等向けアバターのマーケットプレイス。FastAPI(Python)バックエンド + React(TypeScript)フロントエンド。UI は日本語。
- **ゴール**: 「フロントエンド〜バックエンドまで市販レベルの品質にする」。1 ラウンド = 1 つの完結した改善を、実装 → 検証 → PR → master マージ まで通す。
- **作業ブランチ**: `claude/deepresearch-ultrathink-improvement-MpLA3`(master から分岐。マージ済み PR は再利用せず、毎回 master から再スタートする)。
- **やってはいけないこと**: 金銭・法務・永続化の事業判断項目を勝手に実装しない(§6)。

---

## 1. アーキテクチャと正典 (Canonical facts)

### 1.1 バックエンド
- 本体: `main/api_server.py`(FastAPI モノリス、233 ルート)。
- ストア: すべて **プロセス内メモリのシングルトン**(`main/*_manager.py`, `main/avatar_marketplace.py` 等)。
  既定では再起動でデータ消失だが、`COCOA_STATE_DIR` を設定すると **15ストア全部**が
  `state.json` に往復保存される(#74)。**単一プロセス限定**で、複数ワーカーは排他ロックにより
  起動を拒否する(#76 — 黙って壊れる代わりに)。
- **`main/` は 33 モジュールちょうど**で、全て `main.api_server` の import 閉包内(死コードは #59/#60 で削除完了)。新規モジュールを足すときは api_server から辿れるよう配線すること。
- **正典の起動形態は `main` パッケージ文脈**:
  ```
  cd /home/user/Cocoa && uvicorn main.api_server:app --port <PORT>
  ```
  この文脈では **フラットな sibling import(`from vrchat_parameter_budget import ...`)は失敗する**。必ず相対 import(`from .vrchat_parameter_budget import ...`)を先に試すこと。これを怠って本番 503 を 2 回出している(監査 #39)。旧世代のフラット版モジュールは #59/#60 で削除済み。

### 1.2 フロントエンド (`frontend/`)
- Vite + React 18 + TypeScript + react-router v6 + TanStack Query v5 + axios。
- ルート: `frontend/src/App.tsx`。マイページのタブ: `frontend/src/components/MyPageLayout.tsx`。共通レイアウト/ナビ: `frontend/src/components/Layout.tsx`。
- 型: `frontend/src/types/api.ts` にバックエンド `to_dict()` の出力をミラー。
- サービス層: `frontend/src/services/*.ts`(axios 呼び出しを関数化)。
- ページ: `frontend/src/pages/`(公開)と `frontend/src/pages/me/`(要認証)。

---

## 2. 確立済みラウンド手順 (The proven per-round workflow)

新機能・改善は毎回この順で進める。30 ラウンド超これで回してきた。

1. **契約読解**: 対象機能のバックエンド `to_dict()` とエンドポイント本体を読み、**正確なフィールド形状**を把握する(推測しない。例: performance の `issues` は文字列でなくオブジェクト配列)。
2. **型ミラー**: `frontend/src/types/api.ts` に型を追加/修正。
3. **サービス**: `frontend/src/services/<feature>Service.ts` に関数を追加。決済系は Idempotency-Key を付与(`newIdempotencyKey()`)。
4. **ページ**: `frontend/src/pages/` にページを追加/拡張。
5. **配線**: `App.tsx` にルート追加、`MyPageLayout.tsx` / `Layout.tsx` にタブ・リンク追加。
6. **ビルド/テスト**: `cd frontend && npm run build`(`tsc --noEmit` 含む)+ `npm run lint` + `npm test`(Vitest。テストは `src/` に `*.test.ts(x)` で同居)。
7. **E2E**: 実 uvicorn + Playwright(§3)。/api/ への 400 以上の応答を全捕捉し、スクリーンショットを撮る。
8. **回帰**: `python -m unittest`(§3)。バックエンドを変えたら必ず。
9. **コミット**: 機能コミット 1 件(詳細メッセージ)。
10. **監査追記**: `FEATURE_AUDIT.md` に次番号のエントリ(根本原因 → 修正 → 検証 → コミットハッシュ)を追記し、**別コミット**で。
11. **push → PR → マージ → 再スタート**(§5)。

---

## 3. 検証コマンド集 (実証済み — コピーして使う)

### 3.1 バックエンド回帰
```
cd /home/user/Cocoa && python -m unittest tests.test_api_server tests.test_avatar_marketplace
```
主要4モジュール(`tests.test_api_server tests.test_avatar_marketplace tests.test_auth_manager tests.test_email_sender`)で **950 件**。永続化を触ったら `tests.test_state_snapshot` も。
フル回帰は `python -m unittest discover tests`(約 2,100 件)。#59/#60 の死コード削除後、失敗集合は **0 失敗 / 3 エラーのみ**で、残る3件は `pytest`/`_cffi_backend` 未導入の**環境要因**(実コードのバグではない)。
変更前後で失敗集合が増えていないかを比較すること。

### 3.1b API スモークスイープ（全ルートに 500 が無いことの実測）

```
# 端末1
cd /home/user/Cocoa && COCOA_ADMIN_PASSWORD='AdminTest123!' uvicorn main.api_server:app --port 8250
# 端末2
cd /home/user/Cocoa && python3 scripts/smoke_api.py --base http://127.0.0.1:8250 --admin-password 'AdminTest123!'
```

宣言済み **227 ルート全部**に実リクエストを投げ、**予期しない 5xx があれば exit 1**。
`503`(サブシステム不在の正直な報告 = #47 の規約)は許容し、`500` は常に失敗として扱う。
実在オブジェクト(出品・ライセンス)を先に作ってからパスパラメータを埋めるので、not-found 分岐だけでなく**実処理の経路**に届く。

**このスイープが監査 #64・#65 の2件の実バグを発見した**(どちらもフロント・テストのどちらからも呼ばれていないエンドポイントで、単体テストはモックのため素通りしていた)。バックエンドを変更したら実行すること。

### 3.1c 未配線エンドポイントの棚卸し（「誰も開けないキュー」の検出）

```
cd /home/user/Cocoa && python3 scripts/unwired_endpoints.py
```

バックエンド218エンドポイントとフロントの実呼び出しを機械的に差分する(現在: 配線済み169 / 未配線49)。
**未配線＝バグではない**。判断は3択で、意識的に選んで `FEATURE_AUDIT.md` に理由を残すこと:
- **wire it** — ユーザーが既にデータを投入できるのに誰も取り出せない(#46・#68 の行き止まり)
- **delete it** — そもそも不要な部品(#57 のお気に入り: wishlist と重複)
- **leave it** — 意図的にサーバー専用(運用系・API クライアント向け)

### 3.2 フロントエンド
```
cd /home/user/Cocoa/frontend && npm run build && npm run lint && npm test
```

### 3.3 E2E 用 uvicorn 起動(バックグラウンド)
```
cd /home/user/Cocoa && COCOA_EXPOSE_RESET_TOKEN=true uvicorn main.api_server:app --port 8151
```
- `cd /home/user/Cocoa` を**必ず先に**。でないと `ModuleNotFoundError: No module named 'main'`。
- `COCOA_EXPOSE_RESET_TOKEN=true` / `COCOA_EXPOSE_VERIFY_TOKEN=true` はリセット/メール確認トークンを API 応答で返す**開発用**フラグ(既定 OFF。本番はメール配送のみ = 監査 #51)。
- `COCOA_2FA_SECRET` 未設定だと 2FA は「利用不可」として degrade する(500 にはならない = 監査 #53)。2FA を実際に試すなら設定する。
- メールは既定で `ConsoleEmailSender` がサーバーログに全文出力する。E2E はそのログで配送を検証できる。
- `COCOA_STATE_DIR=<dir>` を設定すると **15ストア全部**(アカウント・残高/台帳・出品・カート・注文ほか)が再起動を生き延びる(#71/#74。既定は未設定=完全インメモリ)。破損スナップショットや台帳不整合では起動を拒否する(fail-closed)ので、テストで壊れた状態ディレクトリを再利用しないこと。**同じディレクトリを2プロセスで使うと排他ロックで2つ目が起動しない**(#76)。
- フロントは `frontend` を build 済みなら uvicorn が配信する(SPA フォールバックあり)。

### 3.3b 重要ユーザー導線の E2E(コミット済み)

```
# terminal 1
RATE_LIMIT_AUTH_PER_MINUTE=100 \
  COCOA_ADMIN_PASSWORD='AdminTest123!' uvicorn main.api_server:app --port 8250

# terminal 2
python3 scripts/e2e_critical_flows.py --base http://127.0.0.1:8250 \
  --admin-password 'AdminTest123!'
```

実ブラウザで5つの導線を検証する(11チェック): 公開→公開検索に出る／UIログインがリロードを跨ぐ／
**カート購入で両者の残高が実際に動く**／払い戻し申請→管理者承認→買い手が全額回復／通報が
モデレーションコンソールに届く。**フロントを build 済みにしておくこと**。

3番目が最重要 — 監査 #44 は「有料出品が 0 クレジットで引き渡され売り手に入金されない」バグで、
当時の**全単体テストを通過**していた(レスポンス形状だけを見ていたため)。このスイートは
売り手への入金を潰すミューテーションで**実際に失敗する**ことを確認済み。

`RATE_LIMIT_AUTH_PER_MINUTE` を上げずに連続実行すると認証レート制限(既定10/分)に当たる。
その場合スクリプトは**「壊れた導線」ではなくスロットルだと明示して exit 3** で終わる。

### 3.4 Playwright(実ブラウザ・アドホック)
- Chromium 実体: `executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"`(`launch()` に渡す。`playwright install` はしない)。
- E2E スクリプトは scratchpad に置く。ひな型はこのセッションの `e2e_test*.py` を踏襲(response リスナーで `/api/` の `status >= 400` を全収集して最後に出力)。
- **毎回ユニークなユーザー名/メール**を使う(ストアはメモリなので前回の残骸と衝突する)。

---

## 4. 既知の落とし穴 (Pitfalls — 実際に踏んだもの)

- **Playwright セレクタの部分一致**: `has-text('送る')` は「チップを送る」等にも当たる。id(`#tip-submit`)、`aria-label`、スコープ(`.row-list` 内)で一意化する。
- **native dialog の自動 dismiss**: `confirm()`/`alert()` は放置すると Playwright が自動で閉じる。`page.on("dialog", lambda d: d.accept())` を先に登録。
- **バックグラウンドコマンドの cwd**: uvicorn/テストを background で回すと cwd がずれて import 失敗しやすい。必ず `cd /home/user/Cocoa &&` を前置。background の出力ファイルが空なら foreground で回し直す。
- **パッケージ import 事故**: §1.1 参照。回帰テスト `TestVRChatToolsPackagedImport`(サブプロセスでルートから `import main.api_server`)は、通常スイート(`main/` を sys.path に載せてしまう)では隠れる import バグを検出するためにある。消さない。
- **オブジェクト配列を描画してクラッシュ**: React error #31。`to_dict()` がオブジェクトを返すフィールドを文字列扱いすると落ちる。型を正しく引いてから描画する(監査 #41)。
- **分類器/ツールの一時エラー**: Bash の一時的な失敗は同一コマンドの再試行で通ることがある。

---

## 5. Git / GitHub 手順と制約

### 5.1 手順
```
# push(ネットワーク失敗のみ指数バックオフで最大4回)
git push -u origin claude/deepresearch-ultrathink-improvement-MpLA3

# PR は GitHub MCP ツールで作成(gh CLI は使えない)
#   mcp__github__create_pull_request
# マージも MCP:
#   mcp__github__merge_pull_request
# マージ後、master から再スタート:
git fetch origin master && git checkout -B claude/deepresearch-ultrathink-improvement-MpLA3 origin/master
```
- リポジトリスコープは `shizukutanaka/cocoa` のみ。
- **マージ済み PR は再利用しない。** フォローアップは master から再スタートした同名ブランチに載せ、新しい PR を切る。

### 5.2 トークン権限の制約(重要)
- **tag を push できない(403)。** リリースタグは**オーナーが手動で**作成する必要がある。GitHub MCP に create-release ツールはない。
- **`.github/workflows/*` を push できない。** 実際に試して GitHub が
  `refusing to allow a GitHub App to create or update workflow ... without \`workflows\` permission`
  で拒否することを確認済み。**動作するワークフローは `docs/ci/ci.yml` に用意済み**で、
  オーナーが `git mv docs/ci/ci.yml .github/workflows/` するだけで有効になる(#79 の前段)。
- リポジトリに CI チェックは未設定(status total_count 0)。緑を確認する CI はないので、ローカル検証(§3)が唯一の防御線。

---

## 6. 実装禁止の境界 (Do NOT implement without explicit instruction)

以下は事業・法務・金銭の判断を伴う。ユーザーの明示指示がない限り実装しない(`FEATURE_AUDIT.md` §3):
1. Stripe 等によるクレジット購入 — 実金銭の受領(§3-1)
2. クリエイター出金・換金(§3-2)
3. アカウント削除時の金銭・契約データの削除ポリシー(§3-3、法的リスク)
4. 永続化層への移行 — データモデル凍結を伴う(§3-4)

これらは「提案・設計」までは書いてよいが、コードとしての実装は保留。

---

## 7. バックログ(事業判断不要・すぐ着手できる順)

`PRODUCT_ASSESSMENT.md` §3〜§4 の詳細に対応する、次ラウンド候補:
~~1. メール送信抽象化~~ → **#51 で完了**(`main/email_sender.py`)
~~2. frontend テストのコミット~~ → **#52 で完了**(Vitest + Testing Library、50テスト)
~~3. メール認証の再送 UI~~ → **#51 で完了**(`me/Security.tsx` + `/verify-email`)
~~4. Creator ページのフォロワー/フォロー中一覧~~ → **#43 で完了**

残っている候補:
~~1. お気に入り機能の未露出~~ → **実装しない判断（#57 で確認）**: `favorite` エンドポイントは `auth_manager` の bookmark を読み書きしており（`/api/auth/bookmarks/*` と同一ストア）、既に UI 露出済みの wishlist と機能が重複する。露出すると「保存」概念が2つになりUXを損なうため露出しない。過剰（§4系）として扱う。
~~2. リーダーボード / トレンドタグ ウィジェット~~ → **#56 で完了**
3. **残りの admin エンドポイント(P3)**: ユーザー一覧・クレジット付与・モデレーションキュー・会員ティア調整・監査エクスポート。（BAN一覧/解除は #58 で配線済み）
4. **構成状態を500で報告している残り2件(P2)**: `GET /backups` と `GET /security/report`(`FEATURE_AUDIT.md` §3-6)。
5. **`useMutation` リファクタ / `api_server.py` の APIRouter 分割(P3)**: 動作は変えず整理。

各候補も §2 のラウンド手順に従って進めること。

---

## 8. モデル別の注意

- **Opus / Sonnet 共通**: この指示書と `PRODUCT_ASSESSMENT.md`・`FEATURE_AUDIT.md` を読めば前提は揃う。まず §3 のコマンドで現状が緑であることを確認してから着手する。
- **検証を省略しない**: このプロジェクトの価値は「動作を確認した」点にある。build/lint/E2E/unittest のいずれも飛ばさない。
- **1 ラウンド 1 PR**: スコープを広げすぎない。1 つの機能を完結させて master へ。
