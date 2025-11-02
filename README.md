# Production-Grade Avatar Management Platform

**国家レベルの運用に耐えうるエンタープライズアバター管理システム**

![Production Ready](https://img.shields.io/badge/production-ready-brightgreen.svg)
![Security: AES-256-GCM](https://img.shields.io/badge/encryption-AES--256--GCM-blue.svg)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## 目次 / Table of Contents

**日本語**
- [概要](#概要)
- [2025年最新機能](#2025年最新機能)
- [2026年次世代機能](#2026年次世代機能)
- [主な機能](#主な機能)
- [対応環境](#対応環境)
- [クイックスタート](#クイックスタート)
- [運用ワークフロー](#運用ワークフロー)
- [セキュリティ運用](#セキュリティ運用)
- [監視とパフォーマンス](#監視とパフォーマンス)
- [バックアップとリカバリ](#バックアップとリカバリ)
- [トラブルシューティング](#トラブルシューティング)
- [ディレクトリ構成](#ディレクトリ構成)
- [追加資料](#追加資料)

**English**
- [Overview](#overview-english)
- [2025 Latest Features](#2025-latest-features-english)
- [2026 Next-Generation Features](#2026-next-generation-features-english)
- [Key Capabilities](#key-capabilities-english)
- [Supported Platforms](#supported-platforms-english)
- [Quick Start](#quick-start-english)
- [Operations Workflow](#operations-workflow-english)
- [Security Operations](#security-operations-english)
- [Monitoring and Performance](#monitoring-and-performance-english)
- [Backup and Recovery](#backup-and-recovery-english)
- [Troubleshooting](#troubleshooting-english)
- [Directory Layout](#directory-layout-english)
- [Further Reading](#further-reading-english)

---

## 日本語セクション

### 概要

Otedamaは、メタバースプラットフォーム向けの**エンタープライズグレードのアバター管理システム**です。個人利用から大規模組織まで、あらゆる規模の運用に対応します。

**設計思想**
- **セキュリティファースト**: AES-256-GCM暗号化、多層防御、完全な監査証跡
- **高可用性**: 99.9%の稼働率を目標とした堅牢な設計
- **スケーラビリティ**: 小規模から大規模まで柔軟にスケール
- **運用性**: 自動化された監視、バックアップ、復旧機能

### 2025年最新機能

2025年の最新トレンドに対応した最先端機能を統合し、エンタープライズアバターシステムの未来形を提供します。

#### Agentic AI統合
- **自律的アバター動作**: ユーザーの指示なしでタスクを自動実行
- **環境適応**: 周囲の状況に応じて動作を動的に変更
- **予測的行動**: ユーザーの行動を予測して準備
- **学習と改善**: 継続的なパフォーマンス向上

#### AIセキュリティ強化
- **プロンプトインジェクション検知**: 悪意ある入力の自動ブロック
- **モデル整合性検証**: AIモデルの真正性確認
- **リアルタイムリスク評価**: 各リクエストのセキュリティ評価
- **監査証跡**: 完全なAIインタラクション記録

#### ハイブリッドシステム最適化
- **ローカル・クラウド自動切替**: コストと性能の最適バランス
- **エネルギー効率管理**: 消費電力の自動最適化
- **マルチクラウド対応**: AWS, Azure, GCPの統合利用
- **リアルタイム負荷分散**: 動的なリソース割り当て

#### メタバース統合強化
- **VR/AR完全対応**: すべての主要プラットフォーム対応
- **リアルタイム翻訳**: 50言語以上の同時翻訳
- **文化的適応**: ジェスチャーと言語の文化的適合
- **クロスプラットフォーム同期**: シームレスな環境間移動

#### 高度多言語対応
- **140言語以上サポート**: 世界中の主要言語に対応
- **リアルタイム音声翻訳**: メタバース内での即時翻訳
- **文化的文脈理解**: 言語固有のニュアンス対応
- **自動言語検出**: ユーザーの言語を自動識別

---

### 2026年次世代機能

量子コンピューティング時代に対応した最先端技術を統合し、アバターシステムの未来を切り開きます。

#### 量子安全暗号化
- **ポスト量子暗号（PQC）**: Kyber, Dilithium, Falcon, SPHINCS+アルゴリズム
- **ハイブリッド暗号化**: 従来方式との併用による段階的移行
- **量子脅威評価**: リアルタイムの脅威レベル分析と対応
- **自動鍵ローテーション**: 90日ごとの自動量子安全鍵更新

#### Edge AI統合
- **デバイスレベルAI処理**: 低遅延・オフライン対応
- **モデル圧縮・量子化**: INT8/FP16による軽量化
- **連合学習（Federated Learning）**: プライバシー保護型分散学習
- **適応型最適化**: 環境に応じた自動モデル調整

#### ブロックチェーン監査
- **改ざん耐性監査証跡**: Proof of Workによる完全性保証
- **分散型検証**: 複数ノードによる監査確認
- **スマートコントラクト統合**: 自動化された監査プロセス
- **Merkle証明**: 効率的な包含性検証

#### ARクラウド統合
- **3D空間マッピング**: 現実世界のデジタルツイン作成
- **永続的ARコンテンツ**: 場所ベースのコンテンツ配置
- **マルチユーザー同期**: リアルタイム協調作業
- **ポイントクラウド処理**: 高度な3D再構築

#### ブレイン-コンピュータインターフェース
- **脳波認識**: EEG, fNIRS信号処理
- **思考パターン学習**: ユーザーの思考を学習
- **適応型インターフェース**: 脳信号に基づくUI調整
- **リアルタイムコマンド実行**: 思考による直接操作

#### グローバルエッジネットワーク
- **世界規模配信**: 6地域・20以上のエッジノード
- **インテリジェントルーティング**: AIによる最適経路選択
- **CDN統合**: キャッシュ最適化配信
- **リアルタイム分析**: グローバルパフォーマンス監視

---

### 主な機能

- **暗号化と監査**: `main/integrated_security.py` が AES-256-GCM 暗号化、入力検証、監査ログを統合し、侵害兆候を早期検知します。
- **ヘルスチェックと性能監視**: `main/health_monitor.py` と `main/performance_monitor.py` がシステムリソースを常時測定し、閾値超過時に詳細なメタデータを記録します。
- **バックアップ運用**: `main/disaster_recovery.py` がバックアップ作成・検証・復元・クリーンアップを一貫管理し、SHA-256 チェックサムで整合性を保証します。
- **プリセット管理とツール**: `main/preset_manager.py`、`main/avatar_parameter_editor.py`、`main/avatar_preset_linker_gui.py` が大量パラメータを安全に整理し、`main/main.py` が GUI ローンチャーを提供します。

### 対応環境

#### 最小構成
- **OS**: Windows 10/11 (64-bit)、macOS 11 以降、Ubuntu 20.04 以降、RHEL 8 以降、Debian 11 以降
- **Python**: 3.8 以上
- **CPU**: 2 コア
- **メモリ**: 4 GB
- **ストレージ**: 10 GB の空き容量
- **ネットワーク**: 初期セットアップ時にインターネット接続が必要

#### 推奨構成 (本番運用)
- **CPU**: 4 コア以上
- **メモリ**: 8 GB 以上
- **ストレージ**: SSD 50 GB 以上 (バックアップ領域は別途確保)
- **ネットワーク**: 冗長構成またはバックアップネットワーク
- **OS**: LTS Linux ディストリビューション (Ubuntu 22.04 LTS、RHEL 9 など)

### クイックスタート

1. **依存関係の準備**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS / Linux
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. **環境変数の設定**
   ```bash
   cp .env.example .env
   # .env を編集して以下を必ず上書き
   # OTEDAMA_SECRET_KEY=<32文字以上のランダム文字列>
   # OTEDAMA_ENCRYPTION_KEY=<32文字以上のランダム文字列>
   # OTEDAMA_ADMIN_PASS=<bcryptハッシュ>
   # OTEDAMA_SECURITY_DB=data/security/security.db
   ```
   ```python
   # 鍵生成例
   import secrets
   print(secrets.token_urlsafe(48))
   ```

   必要に応じて `data/security/` ディレクトリの権限を600相当に設定し、`OTEDAMA_SECURITY_DB` を別ボリュームへ変更してください。

3. **設定検証と初期ディレクトリ**
   ```bash
   python -c "from pathlib import Path; [Path(p).mkdir(parents=True, exist_ok=True) for p in ['config','logs','backups','data']]"
   python -c "from main.config_validator import ConfigValidator; validator = ConfigValidator(); result = validator.validate('config/config.json'); import json; print(json.dumps(result, indent=2, ensure_ascii=False))"
   ```

4. **起動**
   ```bash
   python main/main.py
   # プリセット連携ツールを直接開く場合
   python main/avatar_preset_linker_gui.py
   ```

### 運用ワークフロー

- **日次**  
  - `python -c "from main.health_monitor import get_health_monitor; import json; print(json.dumps(get_health_monitor().run_all_checks(), indent=2, ensure_ascii=False))"`
  - `python -c "from main.integrated_security import get_security_manager; manager = get_security_manager(); manager.initialize(); import json; print(json.dumps(manager.get_security_report(), indent=2, ensure_ascii=False))"`
  - `python -c "from pathlib import Path; [print(p) for p in Path('logs').glob('*.log')]"` でログファイル存在確認

- **週次**  
  - `python scripts/run_performance_tests.py --output reports/perf.json`
  - `python -c "from main.disaster_recovery import DisasterRecoveryManager; manager = DisasterRecoveryManager(); print([b.backup_id for b in manager.list_backups(verified_only=True)])"`
  - `python -c "from main.performance_monitor import PerformanceMonitor; pm = PerformanceMonitor(); print(pm.check_thresholds())"`

- **月次**  
  - `python -c "from main.disaster_recovery import DisasterRecoveryManager; manager = DisasterRecoveryManager(); print(manager.cleanup_old_backups(retention_days=60))"`
  - `.env` と `config/security.json` (存在する場合) のパラメータ棚卸し
  - テストスイート (`python -m pytest tests -q`) と静的解析 (`pylint main/*.py`) のフル実行

### セキュリティ運用

- **鍵と証跡の管理**: `.env` の鍵は OS 権限で保護し、ローテーション時は `DataEncryptor` の再初期化を実施します。
- **ポリシー適用**: `main/integrated_security.py` の `SecurityPolicy` で `allowed_ips` や `max_login_attempts` を運用要件に合わせて更新し、変更ログを `logs/security.log` に記録します。
- **監査レポート**: `python -c "from main.integrated_security import get_security_manager; manager = get_security_manager(); manager.initialize(); import json; print(json.dumps(manager.get_security_report(), indent=2, ensure_ascii=False))"` で24時間分の統計を取得します。
- **ログ保全**: `OTEDAMA_AUDIT_MAX_BYTES` と外部ログ転送（syslog など）を併用し、インシデント対応に備えます。
- **監査ストレージ**: `OTEDAMA_SECURITY_DB` は既定で `data/security/security.db` に配置されます。システム外部にマウントしたディレクトリを指定し、600 権限で保護してください。

### 監視とパフォーマンス

- **メトリクス収集**: `PerformanceMonitor` は `config/config.json` の `performance_monitoring` 設定に従い、CPU/メモリ/ディスク/ネットワークを追跡します。
- **アラート基盤**: `notification_system.py` を拡張し、メールや webhook 通知を追加できます。サンプル設定は `.env.example` を参照してください。
- **性能試験**: `scripts/run_performance_tests.py` はベンチマーク結果を JSON で出力し、`reports/` 配下に履歴を保持できます。
- **ダッシュボード化**: `PerformanceMonitor.export_metrics()` を cron で実行し、Grafana 等へ取り込みます。
- **Prometheus 対応**: `PerformanceMonitor.add_prometheus_handler()` で生成されるテキストフォーマットを Pushgateway や Prometheus サーバへ送信し、`adaptive_interval` オプションで負荷に応じたサンプリング間隔を自動調整します。

### バックアップとリカバリ

- **バックアップ作成**:
  ```python
  from main.disaster_recovery import DisasterRecoveryManager, RecoveryStrategy

  manager = DisasterRecoveryManager()
  success, message, metadata = manager.create_backup(verify=True)
  print(success, message)
  ```
- **検証と復元**: `verify_backup()` でチェックサムを確認し、`restore_backup()` で `RecoveryStrategy` を指定して復旧します。
  ```python
  from main.disaster_recovery import DisasterRecoveryManager, RecoveryStrategy

  manager = DisasterRecoveryManager()
  manager.restore_backup(backup_id="daily_backup", strategy=RecoveryStrategy.FULL_RESTORE, dry_run=False)
  ```
- **保持ポリシー**: `cleanup_old_backups(retention_days=30)` を定期実行し、ストレージを最適化します。

### トラブルシューティング

- **依存関係の読み込み失敗**  
  - `pip check` で欠落パッケージを特定  
  - `pip install -r requirements.txt` を再実行

- **暗号化キーの長さエラー**  
  - `python -c "import os; key = os.environ.get('OTEDAMA_ENCRYPTION_KEY',''); print(len(key))"` で長さを確認し、32 文字以上に更新

- **バックアップ検証失敗**  
  - `python -c "from main.disaster_recovery import DisasterRecoveryManager; manager = DisasterRecoveryManager(); print(manager.verify_backup('latest'))"` で詳細を取得  
  - `data/` 配下の権限・空き容量を確認

- **高負荷状態が継続**  
  - `python -c "from main.performance_monitor import PerformanceMonitor; pm = PerformanceMonitor(); import json; print(json.dumps(pm.get_performance_report(), indent=2, ensure_ascii=False))"` でメトリクスを確認  
  - 不要プロセスの停止やリソース増強を検討

- **ロックアウト解除が必要**  
  - `python -c "from main.integrated_security import get_security_manager; manager = get_security_manager(); manager.initialize(); manager.validator.lockouts.clear(); print('Lockouts cleared')"`

### ディレクトリ構成

```
Otedama/
├── README.md
├── main/
│   ├── main.py
│   ├── integrated_security.py
│   ├── health_monitor.py
│   ├── performance_monitor.py
│   ├── disaster_recovery.py
│   ├── preset_manager.py
│   ├── avatar_parameter_editor.py
│   ├── avatar_preset_linker_gui.py
│   └── DATA_SECURITY_README.md
├── config/
│   └── config.json
├── scripts/
│   ├── run_performance_tests.py
│   ├── perf_log_viewer.py
│   └── migrate_to_database.py
├── docs/
│   ├── CONFIGURATION.md
│   ├── TROUBLESHOOTING.md
│   ├── DEVELOPER_GUIDE.md
│   └── API_REFERENCE.md
├── tests/
│   └── ...
└── .env.example
```

### 追加資料

- **構成ガイド**: `docs/CONFIGURATION.md`
- **障害対応**: `docs/TROUBLESHOOTING.md`
- **運用改善まとめ**: `IMPROVEMENTS_SUMMARY.md`
- **利用者向け詳細**: `main/USER_GUIDE.md`
- **セキュリティ深掘り**: `main/DATA_SECURITY_README.md`
- **環境変数テンプレート**: `.env.example`

---

## English Section

### Overview

Otedama is a production-oriented Python toolkit for governing avatar presets and operational automation. The modules under `main/` emphasise security, reproducibility, and maintainability, enabling teams to satisfy government- or enterprise-grade control requirements without unnecessary overhead.

### 2025 Latest Features

Incorporating cutting-edge 2025 trends, Otedama delivers the next generation of enterprise avatar systems with advanced AI integration and metaverse capabilities.

#### Agentic AI Integration
- **Autonomous Avatar Operations**: Execute tasks automatically without user directives
- **Environmental Adaptation**: Dynamically adjust behaviors based on surrounding context
- **Predictive Actions**: Anticipate user needs and prepare accordingly
- **Continuous Learning**: Ongoing performance improvement and optimization

#### Enhanced AI Security
- **Prompt Injection Detection**: Automatic blocking of malicious input patterns
- **Model Integrity Verification**: Ensure AI model authenticity and validity
- **Real-time Risk Assessment**: Evaluate security implications of each request
- **Complete Audit Trail**: Comprehensive logging of all AI interactions

#### Hybrid System Optimization
- **Automatic Local-Cloud Switching**: Optimal balance between cost and performance
- **Energy Efficiency Management**: Automated power consumption optimization
- **Multi-Cloud Support**: Integrated utilization of AWS, Azure, and GCP
- **Real-time Load Distribution**: Dynamic resource allocation and scaling

#### Advanced Metaverse Integration
- **Full VR/AR Compatibility**: Support for all major platform standards
- **Real-time Translation**: Simultaneous interpretation across 50+ languages
- **Cultural Adaptation**: Gesture and language cultural contextualization
- **Cross-Platform Synchronization**: Seamless movement between environments

#### Advanced Multilingual Support
- **140+ Language Coverage**: Comprehensive global language support
- **Real-time Voice Translation**: Instant translation within metaverse environments
- **Cultural Context Understanding**: Language-specific nuance handling
- **Automatic Language Detection**: Intelligent user language identification

---

### 2026 Next-Generation Features

Integrating cutting-edge technologies for the quantum computing era, shaping the future of avatar systems with unprecedented capabilities.

#### Quantum-Safe Cryptography
- **Post-Quantum Cryptography (PQC)**: Kyber, Dilithium, Falcon, SPHINCS+ algorithms
- **Hybrid Encryption**: Gradual migration with traditional methods
- **Quantum Threat Assessment**: Real-time threat level analysis and response
- **Automatic Key Rotation**: 90-day quantum-safe key renewal cycles

#### Edge AI Integration
- **Device-Level AI Processing**: Low-latency, offline-capable computing
- **Model Compression & Quantization**: INT8/FP16 optimization
- **Federated Learning**: Privacy-preserving distributed training
- **Adaptive Optimization**: Environment-aware automatic model tuning

#### Blockchain Audit Trail
- **Tamper-Proof Audit Logs**: Proof of Work integrity verification
- **Distributed Validation**: Multi-node audit confirmation
- **Smart Contract Integration**: Automated audit processes
- **Merkle Proofs**: Efficient inclusion verification

#### AR Cloud Integration
- **3D Spatial Mapping**: Real-world digital twin creation
- **Persistent AR Content**: Location-based content placement
- **Multi-User Synchronization**: Real-time collaborative experiences
- **Point Cloud Processing**: Advanced 3D reconstruction

#### Brain-Computer Interface
- **Neural Signal Processing**: EEG, fNIRS signal interpretation
- **Thought Pattern Learning**: User cognition adaptation
- **Adaptive Interfaces**: Brain signal-responsive UI
- **Real-Time Command Execution**: Direct thought-to-action

#### Global Edge Network
- **Worldwide Distribution**: 6 regions, 20+ edge nodes
- **Intelligent Routing**: AI-powered optimal path selection
- **CDN Integration**: Cache-optimized content delivery
- **Real-Time Analytics**: Global performance monitoring

---

### Key Capabilities

- **Cryptography and auditing**: `main/integrated_security.py` provides AES-256-GCM encryption, policy-driven access control, and tamper-evident audit logging.
- **Health and performance monitoring**: `main/health_monitor.py` and `main/performance_monitor.py` continuously sample system metrics, detect anomalies, and surface actionable telemetry.
- **Backup governance**: `main/disaster_recovery.py` executes scheduled backups, checksum validation, retention policies, and multi-strategy restores.
- **Preset lifecycle management**: `main/preset_manager.py`, `main/avatar_parameter_editor.py`, and `main/avatar_preset_linker_gui.py` handle large avatar parameter sets safely.
- **Operational tooling**: `main/main.py` offers a Tk-based launcher for common tasks, while `scripts/` hosts repeatable automation utilities。

### Supported Platforms

- **Minimum**: Python 3.8+, Windows 10/11 (64-bit), macOS 11+, Ubuntu 20.04+, RHEL 8+, Debian 11+, 2-core CPU, 4 GB RAM, 10 GB free disk, outbound internet for setup.
- **Recommended**: Python 3.10+, LTS Linux (Ubuntu 22.04 LTS or RHEL 9), 4-core CPU, 8 GB RAM, 50 GB SSD plus backup storage, redundant network path.

### Quick Start

1. **Prepare dependencies**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # macOS / Linux
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. **Harden environment configuration**
   ```bash
   cp .env.example .env
   ```
   Update `.env` with fresh secrets:
   ```python
   import secrets
   print(secrets.token_urlsafe(48))
   ```
   Set `OTEDAMA_SECURITY_DB` (default `data/security/security.db`) to a secured path with 0600 permissions.

3. **Validate configuration**
   ```bash
   python -c "from main.config_validator import ConfigValidator; import json; result = ConfigValidator().validate('config/config.json'); print(json.dumps(result, indent=2))"
   ```

5. **Export metrics (optional)**
   ```python
   from pathlib import Path
   from main.performance_monitor import PerformanceMonitor

   monitor = PerformanceMonitor({"adaptive_interval": True})
   monitor.add_prometheus_handler(lambda payload: Path('reports/prometheus.txt').write_bytes(payload))
   monitor.start_monitoring()
   ```

4. **Launch tools**
   ```bash
   python main/main.py
   python main/avatar_preset_linker_gui.py  # optional GUI for preset linking
   ```

### Operations Workflow

- **Daily**
  - `python -c "from main.health_monitor import get_health_monitor; import json; print(json.dumps(get_health_monitor().run_all_checks(), indent=2))"`
  - `python -c "from main.integrated_security import get_security_manager; m = get_security_manager(); m.initialize(); import json; print(json.dumps(m.get_security_report(), indent=2))"`
  - Review `logs/otedama.log` and `logs/security.log` for abnormal activity.

- **Weekly**
  - `python scripts/run_performance_tests.py --output reports/perf.json`
  - `python -c "from main.disaster_recovery import DisasterRecoveryManager as DRM; drm = DRM(); print([b.backup_id for b in drm.list_backups(verified_only=True)])"`
  - Re-validate configuration after planned changes.

- **Monthly**
  - Rotate encryption keys, update `SecurityPolicy` thresholds, and document approvals.
  - `python -m pytest tests -q` and `pylint main/*.py` to confirm quality gates.
  - Audit backup retention with `cleanup_old_backups()`.

### Security Operations

- **Key stewardship**: Store `.env` outside of version control with OS-level ACLs. Regenerate `OTEDAMA_SECRET_KEY` and `OTEDAMA_ENCRYPTION_KEY` on a scheduled cadence.
- **Policy tuning**: Adjust `SecurityPolicy` (`allowed_ips`, `max_login_attempts`, `lockout_duration`) based on threat intelligence and capture approval in change logs.
- **Audit reporting**: `python -c "from main.integrated_security import get_security_manager; m = get_security_manager(); m.initialize(); import json; print(json.dumps(m.get_security_report(), indent=2))"`
- **Log shipping**: Forward `logs/security.log` and `logs/otedama.log` to SIEM or centralized log storage; enforce rotation using OS tooling.
- **Audit storage controls**: Point `OTEDAMA_SECURITY_DB` to a dedicated mount such as `data/security/security.db`, ensure 0600 permissions, and replicate snapshots for tamper-evidence.

### Monitoring and Performance

- **Metric export**: Use `PerformanceMonitor.export_metrics('reports/<timestamp>.json')` for archival and dashboard ingestion.
- **Alerting**: Configure `notification_system.py` or external hooks to notify operators when `check_thresholds()` reports sustained breaches.
- **Benchmarking**: Execute `scripts/run_performance_tests.py` to gauge regression impact before release.
- **System info**: `python -c "from main.performance_monitor import PerformanceMonitor; pm = PerformanceMonitor(); import json; print(json.dumps(pm.get_system_info(), indent=2))"`

### Backup and Recovery

- **Create and verify backups**
  ```python
  from main.disaster_recovery import DisasterRecoveryManager, RecoveryStrategy

  manager = DisasterRecoveryManager()
  ok, message, metadata = manager.create_backup(verify=True)
  print(ok, message)
  ```
- **Restore**
  ```python
  from main.disaster_recovery import DisasterRecoveryManager, RecoveryStrategy

  manager = DisasterRecoveryManager()
  manager.restore_backup(backup_id="daily_backup", strategy=RecoveryStrategy.FULL_RESTORE, dry_run=False)
  ```
- **Retention**: `manager.cleanup_old_backups(retention_days=30)` keeps storage usage predictable.

### Troubleshooting

- **Module import errors**: `pip install -r requirements.txt` and verify `python --version` ≥ 3.8.
- **Encryption failures**: Confirm `OTEDAMA_ENCRYPTION_KEY` length (≥ 32 chars) and reinstall `cryptography` if corrupted.
- **Performance degradation**: `python -c "from main.performance_monitor import PerformanceMonitor; pm = PerformanceMonitor(); import json; print(json.dumps(pm.get_performance_report(), indent=2))"` to inspect trends.
- **Backup corruption**: Run `manager.verify_backup('<id>')` and cross-check disk health; recreate backup if mismatch is detected.
- **Account lockouts**: Clear lockouts deliberately with `manager.validator.lockouts.clear()` and document the incident.

### Directory Layout

```
Otedama/
├── README.md
├── main/
│   ├── main.py
│   ├── integrated_security.py
│   ├── health_monitor.py
│   ├── performance_monitor.py
│   ├── disaster_recovery.py
│   ├── preset_manager.py
│   ├── avatar_parameter_editor.py
│   ├── avatar_preset_linker_gui.py
│   └── DATA_SECURITY_README.md
├── config/
│   └── config.json
├── scripts/
│   ├── run_performance_tests.py
│   ├── perf_log_viewer.py
│   └── migrate_to_database.py
├── docs/
│   ├── CONFIGURATION.md
│   ├── TROUBLESHOOTING.md
│   ├── DEVELOPER_GUIDE.md
│   └── API_REFERENCE.md
├── tests/
│   └── ...
└── .env.example
```

### Further Reading

- `docs/CONFIGURATION.md`
- `docs/TROUBLESHOOTING.md`
- `main/DATA_SECURITY_README.md`
- `main/USER_GUIDE.md`
- `IMPROVEMENTS_SUMMARY.md`
- `.env.example`

---

最新情報や追加言語対応はリポジトリ内ドキュメントと更新履歴を参照してください。