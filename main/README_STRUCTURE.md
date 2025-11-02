# Cocoa プロジェクト構造

## プロジェクト概要

Cocoaは、VRChatなどのプラットフォームで使用するアバターやプリセットを管理するシステムです。セキュリティ、性能、安定性を重視した設計で、国家機関や大企業での利用も可能です。

## フォルダ構成

```
Cocoa/
├── .claude/                    # AIアシスタント設定
├── .git/                      # Gitリポジトリ
├── .gitignore                 # Git除外設定
├── .gitkeep                   # 空ディレクトリ保持
├── DEPLOYMENT.md              # デプロイメントガイド
├── README.md                  # プロジェクト概要
├── README_old.md              # 旧README
├── config/                    # 設定ファイル
│   ├── security.json          # セキュリティ設定
│   ├── error_recovery.json    # エラー復旧設定
│   └── cache_manager.json     # キャッシュ設定
├── docs/                      # ドキュメント
│   ├── API_REFERENCE.md       # APIリファレンス
│   ├── CODE_FULL_CHECK_GUIDE.md # コードチェックガイド
│   ├── CONFIGURATION.md       # 設定ガイド
│   ├── DEVELOPER_GUIDE.md     # 開発者ガイド
│   ├── README.md              # ドキュメント概要
│   ├── TROUBLESHOOTING.md     # トラブルシューティング
│   └── improvement_backlog.md # 改善バックログ
├── launch/                    # 起動スクリプト
│   ├── run_cocoa.bat          # Windows起動スクリプト
│   └── run_cocoa.sh           # macOS起動スクリプト
├── locales/                   # 多言語対応
│   ├── en.json                # 英語
│   ├── ja.json                # 日本語
│   ├── zh.json                # 中国語
│   └── ...                    # その他言語
├── mac/                       # macOS固有ファイル
├── main/                      # メインソースコード
│   ├── security_manager.py    # セキュリティ管理
│   ├── performance_manager.py # パフォーマンス管理
│   ├── cache_manager.py       # キャッシュ管理
│   ├── error_recovery_system.py # エラー復旧システム
│   ├── logging_manager.py     # ログ管理
│   ├── input_validator.py     # 入力検証
│   ├── database_manager.py    # データベース管理
│   ├── backup_recovery_system.py # バックアップシステム
│   ├── web_admin_improved.py  # Web管理コンソール
│   ├── main.py                # メインモジュール
│   ├── i18n_manager.py        # 多言語管理
│   ├── notification_system.py # 通知システム
│   ├── preset_manager.py      # プリセット管理
│   ├── avatar_loader.py       # アバターローダー
│   └── ...                    # その他モジュール
├── requirements.txt           # Python依存関係
├── run_tests.py              # テストランナー
├── run_tests_new.py          # 新テストランナー
├── scripts/                  # ユーティリティスクリプト
├── setup/                    # セットアップファイル
│   ├── setup.bat              # Windowsセットアップ
│   ├── setup.sh               # macOSセットアップ
│   └── requirements.txt       # 追加依存関係
├── tests/                    # テストファイル
└── win/                      # Windows固有ファイル
```

## モジュール分類

### コア機能
- **main/main.py**: アプリケーションのエントリーポイント
- **main/security_manager.py**: セキュリティ管理（ゼロトラスト、暗号化）
- **main/performance_manager.py**: パフォーマンス監視と最適化
- **main/cache_manager.py**: キャッシュ管理（非同期、リソースプーリング）
- **main/error_recovery_system.py**: エラー処理と自動復旧

### 管理機能
- **main/web_admin_improved.py**: Web管理コンソール
- **main/database_manager.py**: データベース操作
- **main/backup_recovery_system.py**: バックアップと復旧
- **main/logging_manager.py**: ログ管理
- **main/notification_system.py**: 通知システム

### ユーティリティ
- **main/i18n_manager.py**: 多言語対応
- **main/input_validator.py**: 入力検証
- **main/preset_manager.py**: プリセット管理
- **main/avatar_loader.py**: アバターローディング

### 設定と構成
- **config/**: 各種設定ファイル
- **locales/**: 多言語リソース
- **setup/**: インストールスクリプト

## 開発ガイドライン

### コーディング標準
- PEP 8準拠
- 型ヒントの使用
- ドキュメンテーション（docstring）
- ユニットテスト必須

### テスト
- 単体テスト: 各モジュール
- 統合テスト: モジュール間連携
- パフォーマンステスト: 負荷テスト
- セキュリティテスト: 脆弱性チェック

### デプロイメント
- Docker対応
- CI/CDパイプライン
- 環境別設定（dev/staging/production）

## インストール手順

1. リポジトリをクローン
```bash
git clone <repository-url>
cd Cocoa
```

2. 仮想環境を作成
```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate     # Windows
```

3. 依存関係をインストール
```bash
pip install -r requirements.txt
```

4. セットアップスクリプトを実行
```bash
# Windows
setup\setup.bat

# macOS/Linux
./setup/setup.sh
```

## 起動手順

1. 仮想環境を有効化
2. メインアプリケーション起動
```bash
python main/main.py
```

3. Webコンソール起動（オプション）
```bash
python main/web_admin_improved.py
```

## バックアップ手順

自動バックアップが有効化されている場合、定期的に実行されます。手動で実行する場合は：

```bash
python -c "from main.backup_recovery_system import BackupRecoverySystem; BackupRecoverySystem().perform_backup()"
```

## トラブルシューティング

詳細は `docs/TROUBLESHOOTING.md` を参照してください。

## 貢献

プルリクエストやIssueの作成を歓迎します。詳細は `docs/CONTRIBUTING.md` を参照してください。
