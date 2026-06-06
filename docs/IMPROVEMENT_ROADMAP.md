# Cocoa 改善ロードマップ（統合・優先順位付き）

**作成日**: 2026-06-05
**位置づけ**: [`IMPROVEMENT_BACKLOG.md`](IMPROVEMENT_BACKLOG.md)（競合+arXiv 総括, 13項目）と
[`CATEGORY_RESEARCH.md`](CATEGORY_RESEARCH.md)（10カテゴリ×各10件）で**洗い出した改善点を統合・重複排除し、
意思決定できる単一の優先順位リスト**にしたもの。スコアは Impact(製品価値/正しさ) × Effort × 依存。

## スコアリング指標
- **Impact**: 製品差別化・正しさ・ユーザ価値（H/M/L）
- **Effort**: 実装規模（S/M/L）
- **Conf**: 実現確度（既存OSS/論文の成熟度, H/M/L）
- **Dep**: 依存する先行項目

## 優先順位 Top 15（統合済み）

| 順 | 項目 | Impact | Effort | Conf | Dep | 主拠り所 |
|---|---|---|---|---|---|---|
| 1 | **アーキ健全化の完了**（hub依存分割・テスト整備） | H | M | H | — | FIX_REPORT |
| 2 ✅着手 | **PQC 是正**（dilithium/falcon は非実在→liboqs/oqs, ML-KEM/ML-DSA hybrid）＋誇大表記撤回。`advanced_security_2025.py` 実装済（非実在import除去・無害化された平文返却バグ修正・ML-DSA署名/ML-KEM+AES-GCMハイブリッド） | H | M | H | — | liboqs, NIST FIPS 203/204/205 |
| 3 | **基盤統一**（Flask/FastAPI混在→async FastAPI+Pydantic v2+SQLAlchemy2.0+Alembic、feature構成） | H | M | H | — | fastapi-best-practices |
| 4 | **実 VRM 1.0 / glTF 2.0 エクスポート**（名称のみ→UniVRM互換実体） | H | M | H | — | UniVRM, Khronos×VRM |
| 5 | **単一画像→駆動可能3Dヘッド**（FLAME+3DGS フィードフォワード） | H | L | M | 4 | GAGAvatar, FastAvatar, GaussianAvatars, AniGS |
| 6 | **生成品質 評価ハーネス**（FID/CLIP/CSIM/FVD）＋CI回帰ゲート | H | M | H | — | WB-DH, Awesome-Eval |
| 7 | **2D生成の同一性/制御強化**（IP-Adapter-FaceID/InstantID/ControlNet, SDXL/FLUX） | M | M | H | 6 | IP-Adapter, ControlNet |
| 8 | **リアルタイム リップシンク**（viseme/ARKit blendshape: uLipSync/Audio2Face） | H | M | M | 5 | uLipSync, Audio2Face |
| 9 | **音声クローン更新**（GPT-SoVITS/OpenVoice/XTTS, 感情, 多言語） | M | M | H | — | GPT-SoVITS, OpenVoice |
| 10 | **会話アバター**（LLM人格+長期記憶+RAG+反省）= character brain | H | L | M | 8,9 | Letta/MemGPT, SillyTavern, Generative Agents |
| 11 | **VRChat ワンクリック最適化**（非破壊 mesh/material/BlendTree/atlas） | H | M | H | — | d4rkAvatarOptimizer, VRCFury, NDMF |
| 12 🟡着手 | **パラメータ予算最適化**（256bit予算+ビットパッキング+OSC I/F）。コスト/予算/提案モデル実装済(`vrchat_parameter_budget.py`)。残: OSC I/F・自動パッキング | M | M | H | 3 | VRLabs Av3 Manager, OSCmooth |
| 13 | **可観測性の標準化**（独自→OpenTelemetry, Prometheus/Tempo/Loki/Grafana, SLO, Sentry） | M | M | H | 3 | fastapi-observability |
| 14 | **プライバシー/同意/来歴**（アップロード同意GDPR/APPI, C2PA透かし, 顔匿名化, 音声DF検出） | M | M | M | — | C2PA, 顔匿名化(arXiv:2510.01031) |
| 15 | **モバイル/Quest 3DGS 圧縮・配信**（Mobile-GS, HAC++ + edge/CDN） | M | L | M | 5 | Mobile-GS, CompMarkGS |

> 重複排除メモ: BACKLOG #1/#11=本表5、#2/#4=本表4、#3=本表10、#4=本表8、#6=本表11、#9=本表2、
> #10=本表6、#12=本表14。CATEGORY 各「改善点」も本表に集約済み。

## フェーズ別 実行順（依存解決済み）

- **Phase 0 — 健全化（前提, 小〜中）**: 項目1（アーキ/テスト）。[`../FIX_REPORT.md`] のフォローアップ。
- **Phase 1 — 整合性 & 基盤（小〜中, 速攻の信頼回復）**: 項目2(PQC是正), 3(基盤統一), 6(評価), 13(可観測性)。
  → 「主張と実装の乖離」を解消し、以降の機能開発の土台を作る。**クイックウィン**: 2, 6。
- **Phase 2 — 3D & 相互運用（核の差別化, 中〜大）**: 項目4(VRM出力), 5(画像→3D), 7(2D制御), 15(圧縮配信)。
- **Phase 3 — "動いて話す"（統合, 中〜大）**: 項目8(リップシンク), 9(声), 10(会話/記憶)。Phase2 と合流し全身トーキングアバター。
- **Phase 4 — VRChat 実戦 & ガバナンス（中）**: 項目11(自動最適化), 12(パラメータ予算), 14(同意/来歴)。

## 投資判断の要点
- **クイックウィン（高Impact×小Effort・高確度）**: #2 PQC是正, #6 評価ハーネス, #5 3Dヘッド(成熟OSS流用), #10 会話(既存OSS統合)。
- **ビッグベット（差別化の核）**: #4+#5+#8+#10 の統合 = 「写真1枚→VRMで動いて話すアバター」。
- **やめる/縮小（誇大表記の是正）**: 投機的 `bci_manager`、名称のみ機能、非機能PQC表記は experimental 化 or 撤回。

## 参照
- 競合+arXiv 総括: [`IMPROVEMENT_BACKLOG.md`](IMPROVEMENT_BACKLOG.md)
- カテゴリ別 10×10 詳細: [`CATEGORY_RESEARCH.md`](CATEGORY_RESEARCH.md)
- コンパイル健全化の実績: [`../FIX_REPORT.md`](../FIX_REPORT.md)
