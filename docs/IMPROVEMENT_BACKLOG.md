# Cocoa 改善バックログ — 同種ソフト & arXiv 調査ベース

**作成日 / Date**: 2026-06-05
**目的**: 同種ソフト（競合）と arXiv 最新研究を参照し、Cocoa の改善点を洗い出す。
**前提**: 本ドキュメントは「製品・技術の方向性」に関する改善提案であり、先行する
[`FIX_REPORT.md`](../FIX_REPORT.md)（コンパイル健全化）とは別レイヤ。各項目は Cocoa の
実モジュールに紐付けて記載する。

---

## 0. 調査方法

- **競合 (同種ソフト)**: Ready Player Me / Avaturn / VRoid Studio（アバター生成）、
  VRCFury・Modular Avatar・d4rkAvatarOptimizer（VRChat 制作/最適化）、
  Inworld・Convai（会話AI/NPC人格）。
- **学術 (arXiv 等)**: 単一画像→3Dアバター、テキスト→リグ済みアバター、音声駆動表情/
  リップシンク、リアルタイム会話アバター。
- **Cocoa 現状の実機能調査**（コード実査）:
  - `ai_avatar_generator.py` … Stable Diffusion (diffusers) + CLIP による **2D 画像生成**。
  - `photo_to_avatar_generator.py` … SD ベースの 2D スタイル変換。一部プレースホルダ
    （「実際の実装では Stable Diffusion などのモデルを使用」コメント残存）。
  - `metaverse_integration.py` … glTF/VRM「エクスポート」は**ファイル名生成のみで実メッシュ非出力**。
  - `vrchat_performance_analyzer.py` … 公式 Performance Rank 基準の**評価のみ**（最適化は行わない）。
  - `voice_cloning.py` … torch/torchaudio による音声クローン（実依存あり）。
  - `avatar_personality_tuner.py` / `rag_avatar_generator.py` … ヒューリスティック中心。

---

## 1. 最大のギャップ：「2D 画像生成」から「動かせる 3D アバター」へ

**現状**: Cocoa の生成系は実質 **2D 画像（Stable Diffusion）** であり、リグ済みで他プラット
フォームに持ち出せる **3D アバター**（glTF/VRM）を生成していない。一方、競合 (Avaturn,
Ready Player Me, VRoid) と arXiv SOTA は「**写真/テキスト 1 枚 → アニメーション可能な 3D アバター**」が
標準。これが製品価値上の最大の差。

**洗い出した改善 (P0)**: 単一画像/テキストからの **3D アバター再構築 + 自動リグ + VRM/glTF 出力**
パイプラインを新設し、既存の 2D 生成は「テクスチャ/スタイル指定」工程として下流に組み込む。

---

## 2. 競合比較（同種ソフト）

| 機能軸 | Cocoa 現状 | 競合の到達点 | 出典 |
|---|---|---|---|
| 写真→アバター | 2D 画像 (SD) | Avaturn=セルフィ→写実3Dヘッド, RPM=写真→クロスプラットフォーム3D | Avaturn / RPM |
| スタイル特化 | 汎用 SD | VRoid=アニメVRMに特化・全面手動調整 | VRoid |
| 相互運用 | glTF/VRM 名のみ | RPM=「1アバターを多数アプリで共用」, VRoid=VRM標準 | RPM / VRM |
| VRChat 最適化 | 解析のみ | d4rkAvatarOptimizer=アップロード時に非破壊でメッシュ/マテリアル/BlendTree 最適化 | d4rk |
| 非破壊合成 | なし | VRCFury / Modular Avatar=コンポーネントを非破壊で合成 | VRCFury |
| 会話/人格 | ヒューリスティック | Inworld=人格・感情・記憶の"character brain", Convai=低遅延音声+知覚+記憶 | Inworld / Convai |

---

## 3. arXiv 由来の技術改善（カテゴリ別）

### 3.1 単一画像 → アニメーション可能な 3D アバター（P0）
- **改善**: `photo_to_avatar_generator` を、単一画像から **animatable な 3D 表現
  (3D Gaussian Splatting / メッシュ)** を再構築する方式へ刷新。
- **参考**:
  - AniGS: Animatable Gaussian Avatar from a Single Image — arXiv:2412.02684
  - SVAD: Single Image → 3D Avatar via Synthetic Data (video diffusion) — arXiv:2505.05475
  - 3DGS-Avatar / Deformable 3DGS for Animatable Human Avatars — arXiv:2312.09228, 2312.15059
  - OMEGA-Avatar: One-shot 360° Gaussian Head — arXiv:2602.11693

### 3.2 テキスト/画像 → リグ済み 3D アバター（P1）
- **改善**: `rag_avatar_generator`（現状ヒューリスティック）を、**VLM エージェントで
  パラメータ決定 → パラメトリックモデル (SMPL-X/FLAME) に自動リグ**する設計へ。
  Cocoa の preset/parameter 体系（`preset_manager`, `avatar_parameter_editor`）と直結できる。
- **参考**:
  - SmartAvatar: Text-/Image-Guided, VLM AI Agents, fully rigged — arXiv:2506.04606
  - Text-based Animatable 3D Avatars w/ Morphable Model Alignment (SMPL-X) — arXiv:2504.15835
  - HeadEvolver: blendshape/rig を保存したまま変形 (FLAME/SMPL-X) — arXiv:2403.09326
  - AvatarStudio / DreamAvatar — arXiv:2311.17917, 2304.00916

### 3.3 音声駆動の表情・リップシンク（P1）
- **改善**: `voice_cloning` + `video_creator` を拡張し、**音声 → ビセーム/ARKit ブレンドシェイプ
  (VRChat の口パク・表情) を駆動**する talking-head を追加。リアルタイム会話アバターの基盤になる。
- **参考**:
  - ARTalk: Speech-Driven 3D Head Animation (Autoregressive, SIGGRAPH Asia 2025)
  - Livatar-1: Real-Time Talking Heads, Flow Matching — arXiv:2507.18649
  - SyncAnimation: Real-Time Audio-Driven Pose + Talking Head — arXiv:2501.14646
  - SayAnything: Audio Lip-Sync, Conditional Video Diffusion — arXiv:2502.11515

### 3.4 会話 AI・人格・記憶（P1）
- **改善**: `avatar_personality_tuner` / `avatar_agent` を、**LLM バックエンド + 長期記憶 +
  感情状態**の "character brain" へ昇格（Inworld/Convai 相当）。低遅延 TTS/STT を 3.3 と統合し、
  「話す・聞く・覚える」アバターを実現。
- **参考**: Inworld（人格・感情・記憶・LLM ルーティング）、Convai（低遅延音声・知覚・記憶）。
  - Beyond Monologue: Interactive Talking-Listening Avatar — arXiv:2604.10367

### 3.5 パフォーマンス「解析」→「自動最適化」（P1, VRChat 主戦場）
- **改善**: `vrchat_performance_analyzer`（評価のみ）に、d4rkAvatarOptimizer 相当の
  **非破壊メッシュ/マテリアル統合・BlendTree 最適化・テクスチャアトラス化**を追加し、
  Performance Rank を自動で 1 段以上引き上げる「ワンクリック最適化」を提供。
- **参考**: VRChat Performance Ranking System（公式）、d4rkAvatarOptimizer、VRCLibrary 最適化ガイド。

---

## 4. 相互運用・標準対応（P1）

- **改善**: `metaverse_integration` の glTF/VRM 出力を**実体のあるエクスポート**にし、
  **VRM 1.0 / glTF 2.0** に準拠。RPM の「1 アバターを多数アプリで共用」価値を Cocoa でも実現。
  併せて VRChat/Unity・VRM 対応アプリ・WebXR への明示的なエクスポートパスを用意。

---

## 5. 優先度付きバックログ

| # | 優先 | 項目 | 対象モジュール | 概算工数 |
|---|---|---|---|---|
| 1 | **P0** | 単一画像→animatable 3D (3DGS/メッシュ) パイプライン | `photo_to_avatar_generator` 新パイプライン | 大 |
| 2 | **P0** | VRM 1.0 / glTF 2.0 の実エクスポート | `metaverse_integration` | 中 |
| 3 | P1 | VLM/パラメトリック自動リグ (SMPL-X/FLAME) と preset 連携 | `rag_avatar_generator`, `preset_manager` | 大 |
| 4 | P1 | 音声駆動リップシンク/表情 (viseme/ARKit blendshape) | `voice_cloning`, `video_creator` | 中 |
| 5 | P1 | LLM+記憶+感情の会話アバター (Inworld/Convai 相当) | `avatar_agent`, `avatar_personality_tuner` | 大 |
| 6 | P1 | VRChat ワンクリック自動最適化 (メッシュ/マテリアル/BlendTree) | `vrchat_performance_analyzer` | 中 |
| 7 | P2 | 非破壊コンポーネント合成 (VRCFury/MA 互換の考え方) | preset/parameter 層 | 中 |
| 8 | P2 | 生成モデルの差し替え抽象化（torch 重依存の遅延/オプション化） | 生成系全般 | 小〜中 |

> 注: P0 は製品差別化の核（2D→3D）。先に [`FIX_REPORT.md`] のアーキ課題（hub 依存分割・テスト）を
> 解消してから着手すると安全。

---

## 6. 参考文献 (Sources)

**arXiv / 学術**
- AniGS — https://arxiv.org/abs/2412.02684
- SVAD — https://arxiv.org/html/2505.05475
- 3DGS-Avatar — https://arxiv.org/html/2312.09228 / Deformable 3DGS — https://arxiv.org/abs/2312.15059
- OMEGA-Avatar — https://arxiv.org/pdf/2602.11693
- SmartAvatar — https://arxiv.org/html/2506.04606v1
- Text-based Animatable 3D Avatars (Morphable Model Alignment) — https://arxiv.org/html/2504.15835
- HeadEvolver — https://arxiv.org/html/2403.09326v2
- AvatarStudio — https://arxiv.org/pdf/2311.17917 / DreamAvatar — https://arxiv.org/html/2304.00916
- Livatar-1 — https://arxiv.org/pdf/2507.18649
- SyncAnimation — https://arxiv.org/html/2501.14646v1
- SayAnything — https://arxiv.org/html/2502.11515v1
- Beyond Monologue (Talking-Listening Avatar) — https://arxiv.org/html/2604.10367

**競合 / 同種ソフト**
- d4rkAvatarOptimizer — https://github.com/d4rkc0d3r/d4rkAvatarOptimizer
- VRChat Performance Ranking System — https://creators.vrchat.com/avatars/avatar-performance-ranking-system/
- VRChat Avatar Optimization Tips — https://creators.vrchat.com/avatars/avatar-optimizing-tips/
- Inworld AI — https://inworld.ai/
- Convai — https://convai.com/
- Ready Player Me / VRoid 比較 — https://www.vr-wave.store/no/blogs/best-game-on-oculus-quest/ready-player-me-vs-vroid-studio-a-step-by-step-avatar-creation-tutorial
