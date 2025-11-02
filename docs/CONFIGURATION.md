# Otedama設定リファレンス

## 目次

- [設定ファイル概要](#設定ファイル概要)
- [メイン設定 (config.json)](#メイン設定-configjson)
- [データベース設定 (database.json)](#データベース設定-databasejson)
- [セキュリティ設定](#セキュリティ設定)
- [パフォーマンス設定](#パフォーマンス設定)
- [国際化設定](#国際化設定)
- [環境変数](#環境変数)
- [設定の検証と最適化](#設定の検証と最適化)
- [トラブルシューティング](#トラブルシューティング)

## 設定ファイル概要

Otedamaは複数の設定ファイルを使用してシステムの動作を制御します。

```
config/
├── config.json              # メイン設定
├── database.json            # データベース設定
├── security.json            # セキュリティ設定
├── localization.json        # 国際化設定
└── performance.json         # パフォーマンス設定
```

### 設定読み込み優先順位

1. **環境変数** (最高優先度)
2. **コマンドライン引数**
3. **設定ファイル**
4. **デフォルト値** (最低優先度)

## メイン設定 (config.json)

### 基本構造

```json
{
  "app_name": "Otedama",
  "version": "2.0.0",
  "language": "ja",
  "debug": false,
  "log_level": "INFO",

  "web_admin": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 8080,
    "debug": false,
    "max_workers": 4,
    "session_timeout": 3600
  },

  "backup": {
    "enabled": true,
    "interval_minutes": 30,
    "max_backups": 48,
    "backup_path": "backups/",
    "compression": true
  },

  "performance_monitoring": {
    "enabled": true,
    "interval_seconds": 10,
    "alert_thresholds": {
      "cpu_percent": 70,
      "memory_percent": 80,
      "disk_usage_percent": 85,
      "response_time_ms": 1000
    }
  },

  "cache_manager": {
    "memory_cache_size": 1024,
    "disk_cache_size": 1024,
    "cache_ttl": 3600,
    "cleanup_interval": 3600
  },

  "file_io": {
    "buffer_size": 65536,
    "enable_async_io": true,
    "max_file_size_mb": 100,
  },

  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file_path": "logs/otedama.log",
    "max_file_size": "10MB",
    "backup_count": 5,
    "enable_rotation": true
  }
{{ ... }}
{{ ... }}

### 設定項目詳細

#### アプリケーション基本設定

| 項目 | 型 | デフォルト | 説明 |
|------|---|-----------|------|
| `app_name` | string | "Otedama" | アプリケーション名 |
| `version` | string | "2.0.0" | バージョン番号 |
| `language` | string | "ja" | デフォルト言語 |
| `debug` | boolean | false | デバッグモード有効/無効 |
| `log_level` | string | "INFO" | ログレベル |

#### Web管理インターフェース設定

| 項目 | 型 | デフォルト | 説明 |
|------|---|-----------|------|
| `web_admin.enabled` | boolean | true | Web管理画面の有効/無効 |
| `web_admin.host` | string | "127.0.0.1" | バインドホスト |
| `web_admin.port` | integer | 8080 | ポート番号 |
| `web_admin.debug` | boolean | false | フレームワークのデバッグモード |
| `web_admin.session.timeout_minutes` | integer | 30 | セッションタイムアウト（分） |
| `web_admin.session.max_sessions` | integer | 100 | 最大同時セッション数 |

#### バックアップ設定

| 項目 | 型 | デフォルト | 説明 |
|------|---|-----------|------|
| `backup.enabled` | boolean | true | 自動バックアップ有効/無効 |
| `backup.interval_minutes` | integer | 30 | バックアップ間隔（分） |
| `backup.max_backups` | integer | 48 | 保持するバックアップ数 |
| `backup.backup_path` | string | "backups/" | バックアップ保存パス |
| `backup.compression` | boolean | true | 圧縮有効/無効 |
| `security.password_min_length` | integer | 12 | 最小パスワード長 |
| `security.password_require_special` | boolean | true | 特殊文字を要求 |
| `security.password_require_numbers` | boolean | true | 数字を要求 |
| `security.password_require_lowercase` | boolean | true | 小文字を要求 |
| `security.password_require_uppercase` | boolean | true | 大文字を要求 |
| `security.max_login_attempts` | integer | 5 | 許容される最大ログイン試行回数 |
| `security.lockout_duration_minutes` | integer | 15 | ロックアウト継続時間（分） |
| `security.enable_2fa` | boolean | true | 二要素認証の有効/無効 |
| `security.enable_audit_log` | boolean | true | 監査ログ記録を有効化 |
| `security.allowed_ips` | array | [] | 許可するIP/CIDR一覧 |
| `security.blocked_ips` | array | [] | 拒否するIP/CIDR一覧 |

> `security.enable_audit_log` を false に設定すると検証時に警告が表示され、監査証跡が残りません。

#### 通知設定

| 項目 | 型 | デフォルト | 説明 |
|------|---|-----------|------|
| `notification.enabled` | boolean | false | 通知全体の有効/無効 |
| `notification.email.smtp_server` | string | null | SMTPサーバーアドレス（未設定可） |
| `notification.email.smtp_port` | integer | null | SMTPポート番号（指定時は1〜65535） |
| `notification.email.from_address` | string | null | 送信元メールアドレス（SMTP使用時に必須） |
| `notification.email.to_addresses` | array | [] | 送信先メールアドレス一覧（重複は警告） |
| `notification.webhook.url` | string | null | Webhook送信先URL |
| `notification.webhook.method` | string | null | 使用するHTTPメソッド（未指定時はPOST） |

> `notification.enabled` が true の場合は、メールまたはWebhookのいずれかで有効な送信先を構成する必要があります。
> `notification.email.to_addresses` に同一アドレスが含まれている場合は検証時に警告が表示されます。
> WebhookのURLのみが指定されメソッドが省略された場合、検証時に `POST` が設定されます。

#### 課金設定

| 項目 | 型 | デフォルト | 説明 |
|------|---|-----------|------|
| `billing.enabled` | boolean | false | Stripe連携を有効化するかを指定 |
| `billing.mode` | string | "subscription" | `buy_once`（買い切り）または `subscription` を選択 |
| `billing.currency` | string | "jpy" | ISO 4217通貨コード（例: `jpy`, `usd`） |
| `billing.default_price_tier` | string | "enterprise" | 標準プランに割り当てる `tiers` キー |
| `billing.trial_period_days` | integer | 14 | サブスクリプション試用期間（日数、0で無効） |
| `billing.tiers` | object | - | プラン名ごとの `price_id` と説明を定義 |
| `billing.webhook.enabled` | boolean | true | Webhook受信の有効/無効 |
| `billing.webhook.endpoint_secret_env` | string | `STRIPE_WEBHOOK_SECRET` | Webhook署名検証に使用する環境変数名 |
| `billing.checkout.success_url` | string | "https://localhost/billing/success" | Checkout完了後のリダイレクト先 |
| `billing.checkout.cancel_url` | string | "https://localhost/billing/cancel" | Checkoutキャンセル時のリダイレクト先 |

`billing.tiers` にはStripeダッシュボードで発行した `price_XXX` を設定します。プランを増減させる場合はキー名を追加し、`default_price_tier` を既存のプランのいずれかに合わせてください。

Webhookを利用する場合はStripe CLIまたはダッシュボードでエンドポイントを登録し、署名シークレットを `.env` の `STRIPE_WEBHOOK_SECRET` に設定します。

設定検証では以下を確認します。

- `billing.enabled` が true の場合に `tiers` が定義され、各ティアの `price_id` が `price_` で始まること。
- `default_price_tier` がティアに含まれるキーであること。
- `checkout.success_url` と `checkout.cancel_url` が http(s) URL であり、ホスト名を含むこと。
- Webhookが有効で `endpoint_secret_env` が未設定の場合に警告を出力すること。

#### 環境別設定例

##### 開発環境

```json
{
  "app_name": "Otedama Development",
  "debug": true,
  "log_level": "DEBUG",
  "web_admin": {
    "debug": true,
    "host": "0.0.0.0"
  },
  "backup": {
    "interval_minutes": 60
  },
  "performance_monitoring": {
    "interval_seconds": 30
  }
}
```

##### 本番環境

```json
{
  "app_name": "Otedama Production",
  "debug": false,
  "log_level": "WARNING",
  "web_admin": {
    "host": "127.0.0.1",
    "max_workers": 8
  },
  "backup": {
    "interval_minutes": 15,
    "max_backups": 96
  },
  "performance_monitoring": {
    "interval_seconds": 5,
    "alert_thresholds": {
      "cpu_percent": 60,
      "memory_percent": 70,
      "disk_usage_percent": 80
    }
  }
}
```

## データベース設定 (database.json)

### 基本構造

```json
{
  "database": {
    "default": {
      "db_type": "sqlite",
      "database": "data/cocoa.db",
      "pool_size": 10,
      "max_overflow": 20,
      "pool_timeout": 30,
      "retry_attempts": 3,
      "retry_delay": 1.0,
      "enable_encryption": true,
      "enable_compression": true,
      "backup_interval": 3600,
      "audit_enabled": true
    },
    "postgresql": {
      "db_type": "postgresql",
      "host": "localhost",
      "port": 5432,
      "database": "cocoa",
      "username": "",
      "password": "",
      "pool_size": 20,
      "max_overflow": 30
    },
    "mysql": {
      "db_type": "mysql",
      "host": "localhost",
      "port": 3306,
      "database": "cocoa",
      "username": "",
      "password": "",
      "pool_size": 15,
      "max_overflow": 25
    }
  },
  "migration": {
    "auto_migrate": true,
    "backup_before_migration": true,
    "migration_timeout": 300
  },
  "performance": {
    "query_timeout": 30,
    "slow_query_threshold": 1.0,
    "log_slow_queries": true,
    "enable_query_cache": true,
    "cache_size": 100
  },
  "security": {
    "encrypt_sensitive_data": true,
    "audit_all_operations": true,
    "log_failed_connections": true,
    "max_connection_attempts": 5,
    "connection_timeout": 30
  }
}
```

### データベース種別設定

#### SQLite設定

```json
{
  "db_type": "sqlite",
  "database": "data/cocoa.db",
  "pool_size": 10,
  "enable_wal_mode": true,
  "synchronous": "NORMAL",
  "journal_mode": "WAL",
  "foreign_keys": true
}
```

#### PostgreSQL設定

```json
{
  "db_type": "postgresql",
  "host": "localhost",
  "port": 5432,
  "database": "cocoa",
  "username": "cocoa_user",
  "password": "secure_password",
  "pool_size": 20,
  "max_overflow": 30,
  "pool_recycle": 3600,
  "ssl_mode": "require",
  "application_name": "Cocoa"
}
```

#### MySQL設定

```json
{
  "db_type": "mysql",
  "host": "localhost",
  "port": 3306,
  "database": "cocoa",
  "username": "cocoa_user",
  "password": "secure_password",
  "charset": "utf8mb4",
  "pool_size": 15,
  "autocommit": false,
  "sql_mode": "TRADITIONAL"
}
```

## セキュリティ設定

### セキュリティ設定ファイル

```json
{
  "authentication": {
    "session_timeout": 3600,
    "max_failed_attempts": 5,
    "lockout_duration": 300,
    "password_policy": {
      "min_length": 8,
      "require_uppercase": true,
      "require_lowercase": true,
      "require_numbers": true,
      "require_special_chars": true
    }
  },
  "encryption": {
    "algorithm": "AES-256-GCM",
    "key_rotation_interval": 86400,
    "encrypt_at_rest": true,
    "encrypt_in_transit": true
  },
  "rate_limiting": {
    "enabled": true,
    "requests_per_minute": 100,
    "burst_size": 200,
    "window_size": 60,
    "whitelist": ["127.0.0.1", "::1"]
  },
  "csrf_protection": {
    "enabled": true,
    "token_timeout": 3600,
    "secure_cookies": true,
    "same_site": "Strict"
  },
  "content_security": {
    "xss_protection": true,
    "content_type_options": "nosniff",
    "frame_options": "DENY",
    "hsts_max_age": 31536000
  },
  "file_upload": {
    "max_file_size": 104857600,
    "allowed_extensions": [".json", ".vrm", ".png", ".jpg", ".jpeg"],
    "scan_for_malware": true,
    "quarantine_suspicious": true
## 設定ファイル暗号化機能の追加設定項目

### 設定ファイル暗号化設定

新しい暗号化機能により、機密情報を含む設定ファイルの保護が可能になりました。

```json
{
  "config_encryption": {
    "enabled": true,
    "encryption_key_env": "COCOA_ENCRYPTION_KEY",
    "encrypted_files": [
      "config/database.json",
      "config/security.json"
    ],
    "auto_encrypt_on_save": true,
    "backup_original_files": true,
    "key_rotation_days": 90
  }
}
```

### 設定項目詳細

| 設定項目 | 型 | 説明 | デフォルト値 |
|----------|---|------|-------------|
| `enabled` | boolean | 暗号化機能の有効化 | `false` |
| `encryption_key_env` | string | 暗号化キーの環境変数名 | `"COCOA_ENCRYPTION_KEY"` |
| `encrypted_files` | array | 暗号化対象の設定ファイル一覧 | `[]` |
| `auto_encrypt_on_save` | boolean | 保存時に自動暗号化 | `true` |
| `backup_original_files` | boolean | 元ファイルをバックアップ | `true` |
| `key_rotation_days` | integer | キーローテーション間隔（日） | `90` |

### 環境変数による暗号化設定

```bash
# 暗号化キー設定（32文字以上を推奨）
export COCOA_ENCRYPTION_KEY="your-32-character-encryption-key-here"

# 暗号化対象ファイルの指定
export COCOA_ENCRYPTED_CONFIGS="database.json,security.json"

# キーローテーション設定
export COCOA_KEY_ROTATION_DAYS="90"
```

### 暗号化機能の使用例

#### Pythonコードでの使用

```python
from main.config_encryptor import ConfigEncryptor, encrypt_config_file, decrypt_config_file

# 暗号化キーの設定
encryptor = ConfigEncryptor("your-encryption-key")

# 設定ファイルの暗号化
success = encrypt_config_file('config/database.json')
print(f"暗号化成功: {success}")

# 設定ファイルの復号化
success = decrypt_config_file('config/database.json.encrypted')
print(f"復号化成功: {success}")
```

#### コマンドラインでの使用

```bash
# 設定ファイルの暗号化
python -c "from main.config_encryptor import encrypt_config_file; encrypt_config_file('config/database.json')"

# 設定ファイルの復号化
python -c "from main.config_encryptor import decrypt_config_file; decrypt_config_file('config/database.json.encrypted')"

# セキュアバックアップの作成
python -c "from main.config_encryptor import create_secure_config_backup; create_secure_config_backup('config/database.json')"
```

### 機密情報のマスク機能

暗号化された設定ファイルでは、機密情報が自動的にマスクされます：

**元の設定ファイル:**
```json
{
  "database": {
    "password": "secret_password_123",
    "api_key": "sk_live_1234567890abcdef"
  }
}
```

**暗号化後の設定ファイル:**
```json
{
  "database": {
    "password": "***MASKED***",
    "api_key": "***MASKED***"
  }
}
```

### セキュリティベストプラクティス

1. **キーの管理**: 暗号化キーは環境変数で管理し、バージョン管理システムに含めない
2. **定期的なローテーション**: 90日ごとに暗号化キーを変更することを推奨
3. **バックアップの保護**: 暗号化された設定ファイルのバックアップも暗号化する
4. **アクセス制御**: 暗号化キーのアクセス権を制限する
```

### 環境変数によるセキュリティ設定

本番環境では、機密情報は環境変数で設定することを強く推奨します。

```bash
# セキュリティ関連環境変数
export COCOA_SECRET_KEY="your_32_character_secret_key_here"
export COCOA_ADMIN_USER="admin"
export COCOA_ADMIN_PASS="$2b$12$hashed_password_here"
export COCOA_ENCRYPTION_KEY="your_encryption_key_here"
export COCOA_SESSION_SECURE="true"
export COCOA_SESSION_SAMESITE="Strict"

# データベース認証情報
export COCOA_DB_HOST="<データベースホスト名を指定>"
export COCOA_DB_USER="<データベースユーザー名を指定>"
export COCOA_DB_PASSWORD="<安全なパスワードを指定>"

# 外部サービス連携
export COCOA_SMTP_PASSWORD="<SMTPサービスのパスワードを指定>"
export COCOA_BACKUP_ENCRYPTION_KEY="<バックアップ暗号化キーを指定>"
```

## パフォーマンス設定

### パフォーマンス最適化設定

```json
{
  "performance": {
    "enable_parallel": true,
    "max_parallel_tasks": 4,
    "gc_threshold": [1000, 15, 15],
    "enable_profiling": false,
    "profile_requests": false
  },
  "caching": {
    "enable_memory_cache": true,
    "memory_cache_size_mb": 512,
    "enable_disk_cache": true,
    "disk_cache_size_mb": 2048,
    "cache_compression": true,
    "cache_encryption": false
  },
  "database_optimization": {
    "connection_pool_size": 20,
    "query_cache_size": 100,
    "enable_query_optimization": true,
    "batch_size": 1000,
    "index_maintenance": true
  },
  "file_io": {
    "buffer_size": 65536,
    "use_async_io": true,
    "enable_read_ahead": true,
    "compression_level": 6
  },
  "web_server": {
    "worker_processes": 4,
    "worker_connections": 1000,
    "keepalive_timeout": 65,
    "client_max_body_size": "10M",
    "gzip_compression": true
  }
}
```

### システムリソース別最適化

#### 低メモリ環境 (< 2GB)

```json
{
  "performance": {
    "max_parallel_tasks": 2
  },
  "caching": {
    "memory_cache_size_mb": 128,
    "disk_cache_size_mb": 512
  },
  "database_optimization": {
    "connection_pool_size": 5,
    "query_cache_size": 25
  },
  "web_server": {
    "worker_processes": 2,
    "worker_connections": 500
  }
}
```

#### 高メモリ環境 (>= 8GB)

```json
{
  "performance": {
    "max_parallel_tasks": 8
  },
  "caching": {
    "memory_cache_size_mb": 2048,
    "disk_cache_size_mb": 8192
  },
  "database_optimization": {
    "connection_pool_size": 50,
    "query_cache_size": 500
  },
  "web_server": {
    "worker_processes": 8,
    "worker_connections": 2000
  }
}
```

## 国際化設定

### 国際化設定ファイル

```json
{
  "localization": {
    "default_language": "ja",
    "fallback_language": "en",
    "supported_languages": [
      "ja", "en", "zh", "ko", "fr", "de", "es", "pt", "ru", "it", "nl"
    ],
    "auto_detect_language": true,
    "user_language_preference": true
  },
  "date_time": {
    "default_timezone": "Asia/Tokyo",
    "date_format": "YYYY-MM-DD",
    "time_format": "HH:mm:ss",
    "datetime_format": "YYYY-MM-DD HH:mm:ss"
  },
  "number_format": {
    "decimal_separator": ".",
    "thousands_separator": ",",
    "currency_symbol": "¥",
    "currency_position": "before"
  },
  "language_specific": {
    "ja": {
      "date_format": "YYYY年MM月DD日",
      "currency_symbol": "¥",
      "currency_position": "before"
    },
    "en": {
      "date_format": "MM/DD/YYYY",
      "currency_symbol": "$",
      "currency_position": "before"
    },
    "zh": {
      "date_format": "YYYY年MM月DD日",
      "currency_symbol": "¥",
      "currency_position": "before"
    }
  }
}
```

### 言語リソースファイル構造

各言語のリソースファイル (`locales/{language}.json`) の構造:

```json
{
  "common": {
    "save": "保存",
    "cancel": "キャンセル",
    "delete": "削除",
    "edit": "編集",
    "loading": "読み込み中...",
    "error": "エラー",
    "success": "成功"
  },
  "presets": {
    "title": "プリセット管理",
    "create_new": "新規プリセット作成",
    "edit_preset": "プリセット編集",
    "delete_confirm": "このプリセットを削除しますか？",
    "name_required": "プリセット名は必須です",
    "saved_successfully": "プリセットを保存しました"
  },
  "avatar": {
    "title": "アバター管理",
    "upload": "アバターアップロード",
    "apply_preset": "プリセット適用",
    "file_too_large": "ファイルサイズが大きすぎます"
  },
  "system": {
    "status": "システム状態",
    "performance": "パフォーマンス",
    "backup": "バックアップ",
    "settings": "設定"
  }
}
```

## 環境変数

### 重要な環境変数

| 変数名 | 型 | 説明 | 例 |
|--------|---|------|-----|
| `COCOA_ENVIRONMENT` | string | 実行環境 | `production`, `development`, `testing` |
| `COCOA_SECRET_KEY` | string | セッション暗号化キー | `your_32_character_secret_key` |
| `COCOA_ADMIN_USER` | string | 管理者ユーザー名 | `admin` |
| `COCOA_ADMIN_PASS` | string | 管理者パスワードハッシュ | `$2b$12$...` |
| `COCOA_DATABASE_TYPE` | string | データベース種別 | `sqlite`, `postgresql`, `mysql` |
| `COCOA_DB_HOST` | string | データベースホスト | `localhost` |
| `COCOA_DB_PORT` | integer | データベースポート | `5432` |
| `COCOA_DB_NAME` | string | データベース名 | `cocoa` |
| `COCOA_DB_USER` | string | データベースユーザー | `cocoa_user` |
| `COCOA_DB_PASSWORD` | string | データベースパスワード | `secure_password` |
| `COCOA_LOG_LEVEL` | string | ログレベル | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `COCOA_SESSION_SECURE` | boolean | セキュアセッション | `true`, `false` |
| `COCOA_SESSION_COOKIE_NAME` | string | FlaskセッションCookie名 | `cocoa_admin_session` |
| `COCOA_SESSION_SAMESITE` | string | セッションCookieのSameSite属性 | `Strict` |
| `COCOA_BACKUP_PATH` | string | バックアップパス | `/secure/backups/` |
| `COCOA_FORCE_HTTPS` | boolean | HTTPアクセスをHTTPSへリダイレクト | `true` |
| `COCOA_TRUST_PROXY_COUNT` | integer | 信頼するリバースプロキシ数 (ProxyFix) | `1` |
| `COCOA_STRICT_IP_BINDING` | boolean | セッションをクライアントIPに結び付ける | `true` |
| `COCOA_STRICT_UA_BINDING` | boolean | セッションをUser-Agentに結び付ける | `true` |
| `COCOA_NETWORK_POLICY_CACHE_SECONDS` | integer | 許可/拒否IPリストのキャッシュ秒数 | `60` |
| `COCOA_SESSION_IDLE_TIMEOUT_SECONDS` | integer | セッションアイドルタイムアウト (秒) | `900` |
| `COCOA_SESSION_DURATION_MINUTES` | integer | セッション絶対有効期限 (分) | `60` |
| `COCOA_SESSION_ROTATION_MINUTES` | integer | セッショントークンのローテーション間隔 (分) | `30` |
| `COCOA_MAX_CONFIG_PREVIEW_CHARS` | integer | 設定画面で表示する最大文字数 | `20000` |
| `COCOA_MAX_LOG_PREVIEW_LINES` | integer | ログプレビューの最大行数 | `200` |
| `COCOA_FALLBACK_RATE_LIMIT` | integer | セキュリティ拡張が無い場合のリクエスト上限 | `180` |
| `COCOA_FALLBACK_RATE_WINDOW` | integer | フォールバックレート制限の計測窓 (秒) | `60` |
| `COCOA_AUDIT_MAX_BYTES` | integer | 監査ログをローテーションするサイズしきい値 (バイト) | `5242880` |
| `COCOA_MAX_CONTENT_LENGTH` | integer | 受け付けるリクエストボディの最大サイズ (バイト) | `10485760` |
| `COCOA_ALLOWED_HOSTS` | string | 許可するHostヘッダーのカンマ区切り一覧 | `localhost,127.0.0.1` |
| `COCOA_DEVELOPMENT_MODE` | string | 開発モードの有効化 (`true`/`false`) | `true` |

### 環境変数の設定方法

#### Linux/macOS

```bash
# .env ファイル作成
cat > .env << EOF
COCOA_ENVIRONMENT=production
COCOA_SECRET_KEY=your_32_character_secret_key_here
COCOA_ADMIN_USER=admin
COCOA_ADMIN_PASS=hashed_password_here
EOF

# 環境変数読み込み
source .env

# または直接設定
export COCOA_ENVIRONMENT=production
export COCOA_SECRET_KEY="your_secret_key"
```

#### Windows

```cmd
# 環境変数設定
set COCOA_ENVIRONMENT=production
set COCOA_SECRET_KEY=your_secret_key

# または PowerShell
$env:COCOA_ENVIRONMENT="production"
$env:COCOA_SECRET_KEY="your_secret_key"
```

#### Docker

```yaml
# docker-compose.yml
services:
  cocoa:
    image: cocoa:latest
    environment:
      - COCOA_ENVIRONMENT=production
      - COCOA_SECRET_KEY=${SECRET_KEY}
      - COCOA_DB_HOST=database
    env_file:
      - .env
```

## 設定の検証と最適化

### 設定検証スクリプト

```python
#!/usr/bin/env python3
"""
設定ファイル検証スクリプト
"""

import json
import sys
from pathlib import Path

def validate_config():
    """設定ファイルの検証"""
    errors = []
    warnings = []

    # メイン設定検証
    config_path = Path("config/config.json")
    if not config_path.exists():
        errors.append("config.json が見つかりません")
        return errors, warnings

    with open(config_path) as f:
        config = json.load(f)

    # 必須項目チェック
    required_fields = ['app_name', 'version', 'web_admin']
    for field in required_fields:
        if field not in config:
            errors.append(f"必須項目が不足: {field}")

    # Web管理設定チェック
    if 'web_admin' in config:
        web_config = config['web_admin']

        if web_config.get('port', 0) < 1024:
            warnings.append("ポート番号が1024未満です（root権限が必要）")

        if web_config.get('debug', False) and config.get('debug', False):
            warnings.append("本番環境でデバッグモードが有効です")

    # パフォーマンス設定チェック
    if 'performance_monitoring' in config:
        thresholds = config['performance_monitoring'].get('alert_thresholds', {})

        if thresholds.get('cpu_percent', 0) > 90:
            warnings.append("CPU閾値が高すぎます（90%超）")

        if thresholds.get('memory_percent', 0) > 95:
            warnings.append("メモリ閾値が高すぎます（95%超）")

    return errors, warnings

def validate_database_config():
    """データベース設定検証"""
    errors = []
    warnings = []

    db_config_path = Path("config/database.json")
    if not db_config_path.exists():
        warnings.append("database.json が見つかりません（デフォルト設定を使用）")
        return errors, warnings

    with open(db_config_path) as f:
        db_config = json.load(f)

    # データベース設定チェック
    if 'database' in db_config:
        for db_name, config in db_config['database'].items():
            db_type = config.get('db_type')

            if db_type == 'postgresql':
                if not config.get('host'):
                    errors.append(f"PostgreSQL設定でホストが未設定: {db_name}")
                if not config.get('username'):
                    warnings.append(f"PostgreSQL設定でユーザー名が未設定: {db_name}")

            pool_size = config.get('pool_size', 0)
            if pool_size > 100:
                warnings.append(f"接続プールサイズが大きすぎます: {pool_size}")

    return errors, warnings

def main():
    """メイン関数"""
    print("Cocoa設定検証開始")
    print("=" * 50)

    all_errors = []
    all_warnings = []

    # メイン設定検証
    print("\nメイン設定検証")
    errors, warnings = validate_config()
    all_errors.extend(errors)
    all_warnings.extend(warnings)

    # データベース設定検証
    print("\nデータベース設定検証")
    errors, warnings = validate_database_config()
    all_errors.extend(errors)
    all_warnings.extend(warnings)

    # 結果表示
    print(f"\n検証結果")
    print(f"エラー: {len(all_errors)}件")
    print(f"警告: {len(all_warnings)}件")

    if all_errors:
        print(f"\nエラー:")
        for error in all_errors:
            print(f"  - {error}")

    if all_warnings:
        print(f"\n警告:")
        for warning in all_warnings:
            print(f"  - {warning}")

    if not all_errors and not all_warnings:
        print("\n設定に問題ありません")

    return len(all_errors)

if __name__ == "__main__":
    sys.exit(main())
```

### 設定最適化スクリプト

```python
def optimize_config_for_environment(environment: str):
    """環境別設定最適化"""

    if environment == "production":
        return {
            "debug": False,
            "log_level": "WARNING",
            "web_admin": {
                "debug": False,
                "max_workers": 8
            },
            "backup": {
                "interval_minutes": 15,
                "max_backups": 96
            },
            "performance_monitoring": {
                "interval_seconds": 5
            }
        }

    elif environment == "development":
        return {
            "debug": True,
            "log_level": "DEBUG",
            "web_admin": {
                "debug": True,
                "host": "0.0.0.0"
            },
            "backup": {
                "interval_minutes": 60
            }
        }

    elif environment == "testing":
        return {
            "debug": False,
            "log_level": "ERROR",
            "backup": {
                "enabled": False
            },
            "performance_monitoring": {
                "enabled": False
            }
        }
```

## トラブルシューティング

### よくある設定問題

#### 1. ポート番号衝突

**症状**: `Address already in use` エラー

**解決策**:
```bash
# ポート使用状況確認
lsof -i :8080
netstat -tlnp | grep 8080

# 設定変更
{
  "web_admin": {
    "port": 8081
  }
}
```

#### 2. データベース接続失敗

**症状**: `Connection refused` エラー

**解決策**:
```json
{
  "database": {
    "default": {
      "retry_attempts": 5,
      "retry_delay": 2.0,
      "pool_timeout": 60
    }
  }
}
```

#### 3. メモリ不足

**症状**: `MemoryError` または遅いレスポンス

**解決策**:
```json
{
  "cache_manager": {
    "memory_cache_size": 256,
    "disk_cache_size": 512
  },
  "performance": {
    "max_parallel_tasks": 2
  }
}
```

#### 4. ログファイルサイズ増大

**症状**: ディスク容量不足

**解決策**:
```json
{
  "logging": {
    "level": "WARNING",
    "max_file_size": "5MB",
    "backup_count": 3,
    "enable_rotation": true
  }
}
```

### 設定診断コマンド

```bash
# 設定検証
python scripts/validate_config.py

# 設定最適化
python scripts/optimize_config.py --environment production

# パフォーマンステスト
python scripts/run_performance_tests.py --quick

# 設定情報表示
python -c "
from main.config_validator import ConfigValidator
validator = ConfigValidator()
print(validator.get_config_summary())
"
```

### 設定バックアップと復元

```bash
# 設定バックアップ
mkdir -p config_backup
cp config/*.json config_backup/
echo "Configuration backed up to config_backup/"

# 設定復元
cp config_backup/*.json config/
echo "Configuration restored from backup"

# 設定のGit管理
git add config/
git commit -m "Update configuration"
```

---

## 参考資料

公式ドキュメント:
- [Flask Configuration](https://flask.palletsprojects.com/en/3.0.x/config/)
- [PostgreSQL Configuration](https://www.postgresql.org/docs/current/runtime-config.html)
- [MySQL Configuration](https://dev.mysql.com/doc/refman/8.0/en/server-configuration.html)
- [Python Logging Configuration](https://docs.python.org/3/library/logging.config.html)

Cocoa ドキュメント:
- `DEVELOPER_GUIDE.md`: 開発者向けガイド
- `TROUBLESHOOTING.md`: トラブルシューティング
- `API_REFERENCE.md`: API リファレンス

## サポート

設定に関するご質問やサポートが必要な場合:

- **ドキュメント**: `docs/` ディレクトリ内の各種ガイドを参照
- **ログ確認**: `logs/cocoa.log` で設定エラーを確認
- **設定検証**: `python -c "from main.config_validator import ConfigValidator; ConfigValidator().validate('config/config.json')"` で検証実行