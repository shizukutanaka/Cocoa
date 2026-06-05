# Cocoa カテゴリ別 改善リサーチ（arXiv / GitHub）

**作成日**: 2026-06-05 / **方式**: `/loop`（自己ペース）で 10 カテゴリ × 各10件を順次収集。
**関連**: [`IMPROVEMENT_BACKLOG.md`](IMPROVEMENT_BACKLOG.md)（競合+arXivの総括）, [`../FIX_REPORT.md`]。

## 進捗トラッカー
- [x] 1. AIアバター生成（2D/画像）
- [x] 2. 単一画像/テキスト→3D再構築・自動リグ
- [x] 3. VRChat最適化・パフォーマンス
- [x] 4. プリセット/パラメータ管理（差分・履歴・ロールバック）
- [x] 5. 音声: クローン/TTS/リップシンク(viseme)
- [x] 6. 会話AI・人格・自律エージェント
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

## カテゴリ 4: プリセット/パラメータ管理（差分・履歴・ロールバック）
**Cocoa 現状**: `preset_manager`, `preset_diff_core`, `preset_history_*`, `template_library`, `parameter_optimizer`。ローカル JSON のプリセットを差分/履歴/ロールバック。**VRChat の 256bit 同期予算やビットパッキングは未対応**。

**収集（GitHub/公式）**
1. VRLabs/Avatars-3.0-Manager — Playable Layer / Expression Parameters の統合管理。
2. OSC Parameter Sync (fuuujin) — 2int+2float で 255 float を同期（**ビットパッキング**で予算拡張）。
3. regzo2/OSCmooth — OSC パラメータの**ネットワーク平滑化/補間**。
4. I5UCC/VRCThumbParamsOSC — コントローラ/トラッカー入力→アバターパラメータ。
5. vrchat-community/osc #163 — **256bit 同期上限**の制約議論。
6. VRChat OSC Avatar Parameters（公式）— OSC パラメータ I/F。
7. Animator Parameters（公式）— Av3 パラメータモデル。
8. d4rkAvatarOptimizer — アニメータ/パラメータの統合・最適化も担う。
9. JSON Schema（一般）— プリセット構造の検証（`validate_and_repair_presets` と連携）。
10. CRDT / SemVer（一般）— 協調編集と履歴のマージ/競合解決。

**改善点**
- `parameter_optimizer` に **256bit 同期予算モデル + 自動ビットパッキング**を実装し、予算超過を警告。
- **OSC I/F**（live 制御 + OSCmooth 風平滑化）を追加し外部入力/トラッカー連携。
- `preset_manager` に **JSON Schema 検証**を導入（既存の修復ツールと統合）。
- 履歴に **CRDT/SemVer ベースのマージ**を加え、チーム協調編集と競合解決に対応。
- VRLabs Av3 Manager 互換の import/export でエコシステム接続。

## カテゴリ 5: 音声 クローン/TTS/リップシンク(viseme)
**Cocoa 現状**: `voice_cloning`（torch/torchaudio）, `video_creator`。**アバターのビセーム/ブレンドシェイプ駆動（口パク）は未実装**。

**収集（GitHub/arXiv）**
1. RVC-Boss/GPT-SoVITS — 1分音声で few-shot クローン TTS。
2. myshell-ai/OpenVoice — 即時クローン・多言語・トーン制御。
3. Coqui XTTS / IndexTTS(Bilibili) — zero-shot TTS。
4. F5-TTS / StyleTTS2 — 高品質・自然韻律 TTS。
5. Orpheus (Canopy AI) — Llama-3B、感情・0-shot クローン。
6. Qwen3-TTS (Alibaba, Apache-2.0) — 多言語 TTS（i18n と整合）。
7. hecomi/uLipSync — Unity の MFCC 音素→ブレンドシェイプ(A/I/U/E/O)。
8. NVIDIA Audio2Face — 実時間 音声→3D 表情（viseme/ARKit）。
9. Rudrabha/Wav2Lip — 音声→口元(2D, ACM MM'20)。
10. Rhubarb Lip Sync — 音声→2D viseme（ゲーム向け）。
11. wildminder/awesome-ai-voice — TTS/クローン横断リスト。

**改善点**
- **実時間 viseme/ARKit-blendshape リップシンク**（uLipSync/Audio2Face 系）を追加し、VRChat ビセーム・FLAME（カテゴリ2）と直結。
- クローンを **SOTA zero/few-shot**（GPT-SoVITS/OpenVoice/XTTS）へ更新、**感情**(Orpheus)・**多言語**(Qwen3-TTS) 対応。
- 会話用途のため**ストリーミング低遅延**化（カテゴリ6 と統合）。
- **同意確認・音声DF検出**（[`IMPROVEMENT_BACKLOG.md`] 7.4）を必須化。

## カテゴリ 6: 会話AI・人格・自律エージェント
**Cocoa 現状**: `avatar_agent`, `avatar_personality_tuner`（ヒューリスティック）, `emotional_intelligence`, `interactive_avatar`, `rag_avatar_generator`。**LLM・長期記憶・反省/計画が無い**。

**収集（GitHub/競合）**
1. Inworld / Convai — 人格・感情・記憶・低遅延音声の "character brain"。
2. SillyTavern — character cards / lorebook / group chat / メモリ。
3. Letta(ex-MemGPT) — ステートフル・階層型長期記憶エージェント。
4. MemGPT — LLM-as-OS のメモリ管理パラダイム。
5. Mem0 / Zep / Graphiti — エージェント記憶バックエンド。
6. choosewhatulike/trainable-agents (Character-LLM) — 役割演技の学習型エージェント。
7. NirDiamant/Agent_Memory_Techniques — 記憶30手法 + LoCoMo ベンチ。
8. Stanford Generative Agents (joonspk-research) — 記憶/反省/計画で信憑性ある行動。
9. nuochenpku/Awesome-Role-Play-Papers — ロールプレイ LLM 論文集。
10. LangChain / LlamaIndex — RAG フレームワーク（`rag_avatar_generator` 用）。

**改善点**
- ヒューリスティックを **LLM ペルソナ**へ：**character card + lorebook**（SillyTavern 形式）で人格定義。
- **長期記憶**(Letta/MemGPT/Mem0) を導入しユーザを跨セッションで記憶。
- `rag_avatar_generator` を **本物の RAG**（LlamaIndex + ベクタDB）に。
- `avatar_agent` に **反省/計画**(Generative Agents) を入れ自律行動。
- カテゴリ5(声)・2(顔) と統合し全身トーキングアバター化、**LoCoMo** で記憶評価。

---

## カテゴリ 7–10（次イテレーションで収集）
| # | カテゴリ | 対象モジュール |
|---|---|---|
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

## 主要ソース（カテゴリ4–6）
- VRLabs/Avatars-3.0-Manager — https://github.com/VRLabs/Avatars-3.0-Manager ・ OSCmooth — https://github.com/regzo2/OSCmooth ・ VRChat OSC #163 — https://github.com/vrchat-community/osc/issues/163
- GPT-SoVITS — https://github.com/RVC-Boss/GPT-SoVITS ・ OpenVoice — https://github.com/myshell-ai/OpenVoice ・ awesome-ai-voice — https://github.com/wildminder/awesome-ai-voice
- uLipSync — https://github.com/hecomi/uLipSync ・ Wav2Lip — https://github.com/Rudrabha/Wav2Lip ・ NVIDIA Audio2Face（Omniverse）
- SillyTavern（character cards/lorebook）・ Letta/MemGPT — https://github.com/jocelinho/MemGPT ・ Agent_Memory_Techniques — https://github.com/NirDiamant/Agent_Memory_Techniques
- trainable-agents (Character-LLM) — https://github.com/choosewhatulike/trainable-agents ・ Awesome-Role-Play-Papers — https://github.com/nuochenpku/Awesome-Role-Play-Papers
