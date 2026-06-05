# Cocoa カテゴリ別 改善リサーチ（arXiv / GitHub）

**作成日**: 2026-06-05 / **方式**: `/loop`（自己ペース）で 10 カテゴリ × 各10件を順次収集。
**関連**: [`IMPROVEMENT_BACKLOG.md`](IMPROVEMENT_BACKLOG.md)（競合+arXivの総括）, [`../FIX_REPORT.md`]。

## 進捗トラッカー
- [x] 1. AIアバター生成（2D/画像）
- [x] 2. 単一画像/テキスト→3D再構築・自動リグ
- [x] 3. VRChat最適化・パフォーマンス
- [ ] 4. プリセット/パラメータ管理（差分・履歴・ロールバック）
- [ ] 5. 音声: クローン/TTS/リップシンク(viseme)
- [ ] 6. 会話AI・人格・自律エージェント
- [ ] 7. メタバース/XR・相互運用（VRM/glTF/AR/edge）
- [ ] 8. セキュリティ・暗号・耐量子・監査
- [ ] 9. 監視・可観測性・信頼性（health/perf/DR/cache）
- [ ] 10. 基盤・運用（API/DB/課金/i18n/フロント/配信）

---

## カテゴリ 1: AIアバター生成（2D/画像生成）
**Cocoa 現状**: `ai_avatar_generator.py`（SD+CLIP）, `photo_to_avatar_generator.py`（SD img2img、一部プレースホルダ）。素の txt2img/img2img 中心で**同一性保存・ポーズ制御・評価が弱い**。

**収集（arXiv/GitHub）**
1. IP-Adapter (tencent-ailab/IP-Adapter) — 画像プロンプト注入の標準。
2. IP-Adapter-FaceID / -Portrait / -Plus (h94/IP-Adapter, HF) — 顔ID埋め込みで同一性保存。複数参照対応。
3. InstantID — 単一参照で高同一性・ゼロショット。
4. PhotoMaker — スタック型ID埋め込みで人物個別化。
5. ControlNet (lllyasviel/ControlNet) — ポーズ/深度/エッジ条件付け。
6. DreamBooth / LoRA (diffusers) — 軽量個別化学習。
7. StableAvatar (Francis-Rings/StableAvatar) — 参照画像+音声→無限長アバター動画(DiT)。
8. SDXL / FLUX — ベースモデル更新で品質/解像度向上。
9. ComfyUI — ノードベース生成パイプライン（再現性・拡張）。
10. Awesome-Evaluation-of-Visual-Generation (ziqihuangg) — 生成評価メトリクス集。

**改善点**
- 素の img2img を **IP-Adapter-FaceID / InstantID** に置換し**本人同一性**を担保。
- **ControlNet** でポーズ/構図制御、複数参照写真入力に対応。
- ベースを **SDXL/FLUX** に更新、パイプラインを **ComfyUI/diffusers** で再現可能化。
- 生成に **CLIP/FID/CSIM** 評価を付け、回帰検知（→ カテゴリ別バックログ #10 と連動）。

## カテゴリ 2: 単一画像/テキスト → 3D再構築・自動リギング
**Cocoa 現状**: **3D 再構築は未実装**（2Dのみ）。`metaverse_integration` の VRM/glTF は名称のみ。最大の製品ギャップ。

**収集（arXiv/GitHub）**
1. GaussianAvatars (ShenhanQian, CVPR'24) — FLAME にリグした 3D ガウシアン頭部。
2. GAGAvatar — 汎化・単一フォワード・実時間リエンアクトの頭部アバター。
3. FastAvatar (hliang2/FastAvatar) — 単一非制約ポーズから即時 3DGS 顔。
4. SEGA — 単一画像から駆動可能 3DGS 頭部（FLAME 事前分布）— arXiv:2504.14373。
5. AniGS — 単一画像アニメ可能ガウシアン — arXiv:2412.02684。
6. SVAD — 単一画像→3DGS（動画拡散で合成データ）— arXiv:2505.05475。
7. OMEGA-Avatar — 単一画像→360°ガウシアン頭部 — arXiv:2602.11693。
8. Generalizable Animatable Full-Head Gaussian Avatar — arXiv:2601.12770。
9. FLAME-Universe (TimoBolkart) — FLAME 資源集（RingNet/DECA/EMOCA 等）。
10. RGBAvatar — 縮約ガウシアンブレンドシェイプによるオンライン頭部モデリング。

**改善点**
- **FLAME + 3DGS のフィードフォワード**（GAGAvatar/FastAvatar 系）を採用し、写真1枚→**駆動可能3D頭部**。
- FLAME ブレンドシェイプに**自動リグ**→ VRChat/VRM の表情・口パクと直結（カテゴリ5へ）。
- 全身は **SMPL-X**（SmartAvatar/Morphable Model Alignment, [`IMPROVEMENT_BACKLOG.md`] 3.2）。
- DECA/EMOCA で表情・形状の初期化を安定化。

## カテゴリ 3: VRChat アバター最適化・パフォーマンス
**Cocoa 現状**: `vrchat_performance_analyzer.py`（公式ランク基準の**評価のみ**）, `avatar_performance_monitor.py`。**最適化は未実施**。

**収集（GitHub/公式）**
1. d4rkAvatarOptimizer (d4rkc0d3r) — 非破壊でメッシュ/マテリアル/BlendTree 最適化。
2. VRCFury (vrcfury.com) — 非破壊コンポーネント（トグル/マージャ/最適化）。
3. Modular Avatar (bd_) — 非破壊アバター合成の基盤。
4. NDMF / awesome-ndmf — 非破壊ビルドのフレームワーク/フック集。
5. Thryrallo/VRC-Avatar-Performance-Tools — アップロード前 VRAM・統計チェック。
6. PoiyomiToonShader / lilToon — シェーダ（マテリアル数・実機性能に直結）。
7. VRChat Performance Ranking System（公式基準）。
8. Unity-Mesh-Transfer-Utility — Blender 不要のメッシュ結合。
9. creators.vrchat 最適化Tips / VRCLibrary 最適化ガイド。
10. PhysBones / Constraints のコスト指針（公式ドキュメント）。

**改善点**
- 解析専用 → **ワンクリック非破壊最適化**（メッシュ/マテリアル統合・BlendTree・テクスチャアトラス化）を追加し Rank を自動改善。
- **VRAM/実機統計**の事前見積（Thry 相当）と**シェーダ認識**の解析。
- NDMF/Modular Avatar 思想の**非破壊ビルドパイプライン**を Cocoa の preset 層に導入（→ カテゴリ4・7 と連動）。

---

## カテゴリ 4–10（次イテレーション以降で収集）
| # | カテゴリ | 対象モジュール |
|---|---|---|
| 4 | プリセット/パラメータ管理 | `preset_manager`, `preset_diff_core`, `preset_history_*`, `template_library`, `parameter_optimizer` |
| 5 | 音声 クローン/TTS/リップシンク | `voice_cloning`, `video_creator`, `avatar_video_creator` |
| 6 | 会話AI・人格・自律エージェント | `avatar_agent`, `avatar_personality_tuner`, `emotional_intelligence`, `interactive_avatar`, `rag_avatar_generator` |
| 7 | メタバース/XR・相互運用 | `metaverse_integration`, `ar_cloud_manager`, `edge_ai_manager`, `global_edge_manager`, `bci_manager` |
| 8 | セキュリティ・暗号・耐量子・監査 | `integrated_security`, `advanced_security_2025`, `config_encryptor`, `secret_manager`, `blockchain_audit` |
| 9 | 監視・可観測性・信頼性 | `health_monitor`, `performance_monitor`, `prometheus_monitor`, `grafana_integration`, `disaster_recovery`, `redis_cache_manager` |
| 10 | 基盤・運用 | `api_server`, `database_manager`, `billing_service`, `i18n_manager`, `frontend/`, `services/` |

---

## 主要ソース（カテゴリ1–3）
- IP-Adapter — https://github.com/tencent-ailab/IP-Adapter ・ IP-Adapter-FaceID — https://huggingface.co/h94/IP-Adapter-FaceID
- StableAvatar — https://github.com/Francis-Rings/StableAvatar ・ Awesome-Eval-of-Visual-Generation — https://github.com/ziqihuangg/Awesome-Evaluation-of-Visual-Generation
- GaussianAvatars — https://github.com/ShenhanQian/GaussianAvatars ・ FastAvatar — https://arxiv.org/pdf/2508.18389 ・ SEGA — https://arxiv.org/pdf/2504.14373
- Generalizable Full-Head Gaussian Avatar — https://arxiv.org/pdf/2601.12770 ・ FLAME-Universe — https://github.com/TimoBolkart/FLAME-Universe
- d4rkAvatarOptimizer — https://github.com/d4rkc0d3r/d4rkAvatarOptimizer ・ VRCFury — https://vrcfury.com/ ・ Thry Performance Tools — https://github.com/Thryrallo/VRC-Avatar-Performance-Tools
