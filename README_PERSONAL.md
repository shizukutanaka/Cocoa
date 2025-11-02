# Cocoa - 個人使用向けセットアップガイド

**最高レベルのセキュリティと機能を、簡単セットアップで**

## 🚀 クイックスタート (3ステップ)

### ステップ1: 自動セットアップの実行

```bash
# セットアップスクリプトを実行
python setup_personal.py
```

このスクリプトが自動的に以下を実行します:
- ✅ セキュリティキーの生成 (32文字の強力なキー)
- ✅ 管理者パスワードの設定
- ✅ 最適化された設定ファイルの作成
- ✅ 必須ディレクトリの作成
- ✅ パーミッションの設定

### ステップ2: 依存関係のインストール

```bash
pip install -r requirements.txt
```

### ステップ3: アプリケーションの起動

```bash
# メインアプリケーション
python main/main.py

# または Web管理コンソール
python main/avatar_preset_linker_gui.py
```

## 🔒 個人使用向け最適化セキュリティ

### セキュリティレベル: MAXIMUM

自動セットアップにより、以下の最高レベルセキュリティが設定されます:

#### 暗号化
- **AES-256-GCM**: 軍事レベルの暗号化
- **自動キー生成**: 32文字の強力なランダムキー
- **バックアップ暗号化**: 専用キーによる二重暗号化

#### アクセス制御
- **ローカルホストのみ**: 127.0.0.1からのアクセスのみ許可
- **強力なパスワード**: 12文字以上、大小英数字+特殊文字
- **bcryptハッシュ化**: 業界標準のパスワード保護

#### 監視とログ
- **完全な監査証跡**: すべての操作を記録
- **リアルタイム監視**: CPU、メモリ、ディスクの常時監視
- **自動アラート**: 異常検知時の即時通知

#### データ保護
- **毎日自動バックアップ**: 24時間ごとに自動実行
- **90日保持**: 3ヶ月分のバックアップを保持
- **整合性検証**: SHA-256チェックサムによる検証

## ⚙️ 個人使用向け最適化設定

### パフォーマンス最適化

```json
{
  "cache": {
    "memory_cache_size_mb": 512,
    "disk_cache_size_mb": 2048,
    "auto_cleanup": true
  },
  "performance_monitoring": {
    "interval_seconds": 5,
    "auto_optimize": true
  }
}
```

### UI/UX最適化

```json
{
  "ui": {
    "theme": "auto",
    "language": "ja",
    "show_advanced_options": true,
    "confirm_dangerous_operations": true
  }
}
```

### プライバシー優先

```json
{
  "privacy": {
    "telemetry_enabled": false,
    "anonymous_usage_stats": false,
    "local_only": true
  }
}
```

## 📁 ディレクトリ構造 (自動作成)

```
Cocoa/
├── .env                    # 環境変数 (自動生成、厳重に保護)
├── config/
│   └── config_personal.json # 個人用最適化設定
├── data/
│   ├── avatars/           # アバターデータ
│   ├── presets/           # プリセット
│   ├── cache/             # キャッシュ
│   └── cocoa_personal.db  # SQLiteデータベース
├── backups/               # 自動バックアップ (90日保持)
├── logs/                  # ログファイル
└── reports/               # レポート出力
```

## 🎯 主な機能 (個人使用最適化)

### 1. アバター管理
- 10万以上のパラメータに対応
- 自動保存とバックアップ
- 変更履歴の完全追跡
- ワンクリックで復元

### 2. プリセット管理
- 無制限のプリセット保存
- カテゴリ別整理
- 高速検索とフィルタリング
- エクスポート/インポート

### 3. セキュリティ
- すべてのデータを暗号化
- ローカル専用 (外部送信なし)
- 完全な監査ログ
- 自動脅威検知

### 4. バックアップ/復元
- 毎日自動バックアップ
- ワンクリック復元
- バージョン管理
- 整合性自動検証

### 5. パフォーマンス監視
- リアルタイムリソース監視
- 自動最適化
- パフォーマンスレポート
- アラートと通知

## 🔧 カスタマイズ

### 設定ファイルの編集

```bash
# 個人用設定ファイル
nano config/config_personal.json

# 環境変数
nano .env
```

### よく使う設定変更

#### バックアップ間隔の変更
```json
{
  "backup": {
    "interval_hours": 12  // 12時間ごと
  }
}
```

#### キャッシュサイズの変更
```json
{
  "cache": {
    "memory_cache_size_mb": 1024  // 1GB
  }
}
```

#### 言語の変更
```bash
# .env ファイル
COCOA_LOCALE=en  # 英語に変更
```

## 📊 日常の使い方

### 毎日のルーティン

1. **アプリケーション起動**
   ```bash
   python main/avatar_preset_linker_gui.py
   ```

2. **アバター編集**
   - GUIでパラメータを編集
   - 自動保存されます
   - プリセットとして保存可能

3. **定期確認** (週1回推奨)
   ```bash
   # ヘルスチェック
   python -c "from main.health_monitor import get_health_monitor; import json; print(json.dumps(get_health_monitor().run_all_checks(), indent=2))"

   # バックアップ確認
   ls -lh backups/
   ```

### バックアップの復元

```bash
# 利用可能なバックアップ一覧
python -c "from main.disaster_recovery import get_recovery_manager; manager = get_recovery_manager(); backups = manager.list_backups(); print('\n'.join([f'{b.backup_id}: {b.timestamp}' for b in backups]))"

# 復元実行
python -c "from main.disaster_recovery import get_recovery_manager, RecoveryStrategy; manager = get_recovery_manager(); success, msg = manager.restore_backup('backup_20250106_120000', RecoveryStrategy.FULL_RESTORE); print(msg)"
```

## 🆘 トラブルシューティング

### アプリケーションが起動しない

```bash
# ログ確認
tail -f logs/cocoa.log

# 依存関係確認
pip list | grep -E "(Flask|cryptography|psutil)"

# 設定検証
python -c "from main.config_validator import ConfigValidator; ConfigValidator().validate('config/config_personal.json')"
```

### パフォーマンスが遅い

```bash
# キャッシュクリア
rm -rf data/cache/*

# パフォーマンスレポート
python -c "from main.performance_monitor import PerformanceMonitor; pm = PerformanceMonitor(); pm.export_metrics('reports/perf.json')"
```

### データが消えた

```bash
# 最新バックアップから復元
python -c "from main.disaster_recovery import get_recovery_manager, RecoveryStrategy; manager = get_recovery_manager(); backups = manager.list_backups(verified_only=True); latest = backups[0]; success, msg = manager.restore_backup(latest.backup_id, RecoveryStrategy.FULL_RESTORE); print(msg)"
```

## 💡 ベストプラクティス

### セキュリティ

1. ✅ `.env` ファイルは絶対に共有しない
2. ✅ 定期的にパスワードを変更 (90日推奨)
3. ✅ バックアップは外部ストレージにもコピー
4. ✅ ログを定期的に確認

### パフォーマンス

1. ✅ 不要なキャッシュは定期的にクリア
2. ✅ ディスク容量を監視 (85%超えたらクリーンアップ)
3. ✅ 週1回はヘルスチェック実行
4. ✅ 古いバックアップは削除 (90日以上)

### データ管理

1. ✅ 重要なプリセットは複数バックアップ
2. ✅ 月1回は復元テストを実施
3. ✅ 変更履歴を定期的に確認
4. ✅ エクスポート機能で外部保存

## 🔄 アップデート

```bash
# 最新版の取得
git pull origin master

# 依存関係の更新
pip install --upgrade -r requirements.txt

# データベースマイグレーション (必要な場合)
python -c "from main.database_manager import upgrade_database; upgrade_database()"
```

## 📞 サポート

### ドキュメント
- `docs/TROUBLESHOOTING.md`: 詳細なトラブルシューティング
- `docs/CONFIGURATION.md`: 設定リファレンス
- `main/USER_GUIDE.md`: ユーザーガイド

### コマンド
```bash
# ヘルプ表示
python main/main.py --help

# バージョン確認
python -c "import json; print(json.load(open('config/config_personal.json'))['version'])"
```

## 🎁 おまけ機能

### デスクトップ通知
```json
{
  "notification": {
    "desktop_notifications": true,
    "sound_alerts": true
  }
}
```

### 自動最適化
```json
{
  "performance_monitoring": {
    "auto_optimize": true
  }
}
```

### テーマ設定
```json
{
  "ui": {
    "theme": "dark"  // "light", "dark", "auto"
  }
}
```

---

## ✨ まとめ

**Cocoa Personal Edition** は、個人使用に特化した最高レベルのセキュリティと機能を提供します:

- 🔒 軍事レベルの暗号化
- 🚀 最適化されたパフォーマンス
- 💾 自動バックアップと復元
- 📊 リアルタイム監視
- 🎯 使いやすいUI
- 🔐 完全なプライバシー保護

**3ステップで始められます:**

```bash
python setup_personal.py
pip install -r requirements.txt
python main/avatar_preset_linker_gui.py
```

**楽しいアバター管理を!** 🎉
