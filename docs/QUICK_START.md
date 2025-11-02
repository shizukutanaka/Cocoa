# Cocoa クイックスタートガイド

## 概要

Cocoaは、VRChatなどのプラットフォームで使用するアバターやプリセットを管理するシステムです。本ガイドでは、インストールから基本的な使用方法までを迅速に説明します。

## 動作環境

- **OS**: Windows 10/11, macOS 10.15+, Linux
- **Python**: 3.8以上
- **メモリ**: 最小2GB、推奨4GB以上
- **ストレージ**: 最小1GBの空き容量

## インストール

### 1. リポジトリのクローン

```bash
git clone https://github.com/yourusername/cocoa.git
cd cocoa
```

### 2. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 3. 初期設定

初回起動時に必要な設定ファイルが自動的に作成されます：

```bash
python main.py --setup
```

または、手動で設定ファイルを作成：

```python
from main.config_validator import ConfigValidator

# 設定ファイルの検証と作成
validator = ConfigValidator()
result = validator.validate('config/config.json')

if result['valid']:
    print("設定ファイルが正常です")
else:
    print("設定エラー:", result['errors'])
```

## 基本的な使用方法

### アバター管理

```python
from main.avatar_parameters import AvatarParameters

# アバターの読み込み
avatar = AvatarParameters()
params = avatar.load_avatar('path/to/avatar.json')

# パラメータの取得・設定
shape_value = avatar.get_parameter('face_shape_0001')
avatar.set_parameter('face_shape_0001', 75)
```

### プリセット管理

```python
from main.preset_manager import PresetManager

# プリセットの読み込み
preset_manager = PresetManager()
presets = preset_manager.list_presets()

# プリセットの適用
preset_manager.apply_preset('preset_name')
```

### パフォーマンス監視

```python
from main.performance_monitor import PerformanceMonitor

# パフォーマンス監視の開始
monitor = PerformanceMonitor()
monitor.start_monitoring()

# メトリクスの取得
metrics = monitor.get_metrics()
print(f"CPU使用率: {metrics['cpu_percent']}%")
```

## 設定のカスタマイズ

### 基本設定 (`config/config.json`)

```json
{
  "app_name": "My Cocoa Setup",
  "language": "ja",
  "debug": false,
  "log_level": "INFO",
  "performance_monitoring": {
    "enabled": true,
    "interval_seconds": 5,
    "alert_thresholds": {
      "cpu_percent": 80,
      "memory_percent": 85
    }
  }
}
```

### セキュリティ設定

機密情報を含む設定は環境変数を使用することを推奨：

```bash
export COCOA_ENCRYPTION_KEY="your-32-character-key-here"
export DATABASE_PASSWORD="your-database-password"
```

設定ファイルの暗号化：

```python
from main.config_encryptor import encrypt_config_file

# 設定ファイルの暗号化
encrypt_config_file('config/config.json')
```

## トラブルシューティング

### よくある問題と解決方法

#### 設定ファイルのエラー

```bash
# 設定ファイルの検証
python -c "
from main.config_validator import ConfigValidator
validator = ConfigValidator()
result = validator.validate('config/config.json')
print('エラー:', result['errors'])
print('警告:', result['warnings'])
"
```

#### パフォーマンスの問題

```bash
# パフォーマンス統計の確認
python -c "
from main.performance_monitor import PerformanceMonitor
monitor = PerformanceMonitor()
stats = monitor.get_system_stats()
print('システム統計:', stats)
"
```

#### ログの確認

```bash
# ログファイルの場所
# Windows: %APPDATA%\Cocoa\logs\cocoa.log
# macOS/Linux: ~/.cocoa/logs/cocoa.log

# ログ検索
python -c "
from main.logging_manager import LoggingManager
lm = LoggingManager()
results = lm.search_logs('エラー', limit=10)
for result in results:
    print(result)
"
```

## 次のステップ

### 高度な機能

- **バックアップ機能**: `main/disaster_recovery.py`
- **通知システム**: `main/notification_system.py`
- **セキュリティ機能**: `main/integrated_security.py`

### カスタマイズ

システムをカスタマイズする場合は、以下のファイルを参照：

- `docs/CONFIGURATION.md` - 詳細な設定ガイド
- `docs/DEVELOPER_GUIDE.md` - 開発者向けガイド
- `docs/API_REFERENCE.md` - APIリファレンス

## サポート

問題が発生した場合は：

1. ログファイルを確認
2. 設定ファイルの検証を実行
3. トラブルシューティングガイドを参照
4. 必要に応じてGitHubのIssuesで報告

## バージョン情報

現在のバージョン: 1.0.0
リリース日: 2024年

更新情報は`CHANGELOG.md`またはリリースノートを参照してください。
