# Cocoa API リファレンス

## 概要

CocoaはVRoidアバター管理とプリセット操作のための包括的なAPIを提供します。このドキュメントでは、すべてのAPI エンドポイント、データ形式、認証方法について詳しく説明します。

## 目次

- [認証](#認証)
- [エラーハンドリング](#エラーハンドリング)
- [レート制限](#レート制限)
- [API エンドポイント](#api-エンドポイント)
  - [プリセット管理](#プリセット管理)
  - [アバター管理](#アバター管理)
  - [設定管理](#設定管理)
  - [システム情報](#システム情報)
  - [セキュリティ](#セキュリティ)
  - [パフォーマンス](#パフォーマンス)
- [WebSocket API](#websocket-api)
- [SDKと統合例](#sdkと統合例)

## 認証

### セッション認証

Cocoa APIはセッションベースの認証を使用します。

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "your_secure_password"
}
```

**レスポンス:**
```json
{
  "status": "success",
  "session_id": "abc123...",
  "expires_at": "2024-12-31T23:59:59Z",
  "user_info": {
    "username": "admin",
    "role": "administrator",
    "permissions": ["read", "write", "admin"]
  }
}
```

### API キー認証（オプション）

```http
GET /api/presets
Authorization: Bearer your_api_key_here
```

## エラーハンドリング

### エラーレスポンス形式

```json
{
  "status": "error",
  "error_code": "PRESET_NOT_FOUND",
  "message": "指定されたプリセットが見つかりません",
  "details": {
    "preset_id": "invalid_preset_123",
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "documentation_url": "/docs/errors/PRESET_NOT_FOUND"
}
```

### エラーコード一覧

| エラーコード | HTTPステータス | 説明 |
|-------------|----------------|------|
| `INVALID_REQUEST` | 400 | 不正なリクエスト形式 |
| `UNAUTHORIZED` | 401 | 認証が必要 |
| `FORBIDDEN` | 403 | アクセス権限なし |
| `PRESET_NOT_FOUND` | 404 | プリセットが見つからない |
| `VALIDATION_ERROR` | 422 | 入力値検証エラー |
| `RATE_LIMIT_EXCEEDED` | 429 | レート制限超過 |
| `INTERNAL_ERROR` | 500 | サーバー内部エラー |

## レート制限

### 制限値

- **一般ユーザー**: 100 リクエスト/分
- **認証済みユーザー**: 1000 リクエスト/分
- **管理者**: 5000 リクエスト/分

### レート制限ヘッダー

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642678800
```

## API エンドポイント

### プリセット管理

#### プリセット一覧取得

```http
GET /api/v1/presets
```

**クエリパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|-----------|---|------|------|
| `page` | integer | No | ページ番号（デフォルト: 1） |
| `limit` | integer | No | 1ページあたりの件数（デフォルト: 20） |
| `search` | string | No | 検索クエリ |
| `category` | string | No | カテゴリフィルター |
| `sort` | string | No | ソート方法（`name`, `created_at`, `updated_at`） |
| `order` | string | No | ソート順（`asc`, `desc`） |

**レスポンス:**
```json
{
  "status": "success",
  "data": {
    "presets": [
      {
        "id": "preset_123",
        "name": "カジュアルスタイル",
        "description": "日常的な服装プリセット",
        "category": "casual",
        "parameters": {
          "hair_color": "#8B4513",
          "outfit": "casual_shirt",
          "accessories": ["glasses"]
        },
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-15T11:45:00Z",
        "version": 1,
        "checksum": "abc123..."
      }
    ],
    "pagination": {
      "current_page": 1,
      "total_pages": 5,
      "total_items": 100,
      "items_per_page": 20
    }
  }
}
```

#### プリセット詳細取得

```http
GET /api/v1/presets/{preset_id}
```

**パスパラメータ:**
- `preset_id` (string): プリセットID

**レスポンス:**
```json
{
  "status": "success",
  "data": {
    "id": "preset_123",
    "name": "カジュアルスタイル",
    "description": "日常的な服装プリセット",
    "category": "casual",
    "parameters": {
      "hair_color": "#8B4513",
      "outfit": "casual_shirt",
      "accessories": ["glasses"],
      "facial_expression": "smile",
      "pose": "standing"
    },
    "metadata": {
      "author": "user_456",
      "tags": ["casual", "daily", "simple"],
      "download_count": 42,
      "rating": 4.8
    },
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T11:45:00Z",
    "version": 1
  }
}
```

#### プリセット作成

```http
POST /api/v1/presets
Content-Type: application/json
```

**リクエストボディ:**
```json
{
  "name": "新しいプリセット",
  "description": "プリセットの説明",
  "category": "formal",
  "parameters": {
    "hair_color": "#000000",
    "outfit": "business_suit",
    "accessories": ["watch", "tie"]
  },
  "tags": ["business", "formal", "professional"]
}
```

**レスポンス:**
```json
{
  "status": "success",
  "data": {
    "id": "preset_789",
    "name": "新しいプリセット",
    "created_at": "2024-01-15T12:00:00Z",
    "version": 1
  }
}
```

#### プリセット更新

```http
PUT /api/v1/presets/{preset_id}
Content-Type: application/json
```

**リクエストボディ:**
```json
{
  "name": "更新されたプリセット名",
  "description": "更新された説明",
  "parameters": {
    "hair_color": "#FF0000",
    "outfit": "updated_outfit"
  }
}
```

#### プリセット削除

```http
DELETE /api/v1/presets/{preset_id}
```

**レスポンス:**
```json
{
  "status": "success",
  "message": "プリセットが削除されました",
  "data": {
    "deleted_id": "preset_123",
    "deleted_at": "2024-01-15T12:30:00Z"
  }
}
```

#### プリセット複製

```http
POST /api/v1/presets/{preset_id}/duplicate
Content-Type: application/json
```

**リクエストボディ:**
```json
{
  "name": "複製されたプリセット",
  "modifications": {
    "hair_color": "#0000FF"
  }
}
```

#### プリセット比較

```http
GET /api/v1/presets/compare?preset1={id1}&preset2={id2}
```

**レスポンス:**
```json
{
  "status": "success",
  "data": {
    "preset1": {
      "id": "preset_123",
      "name": "プリセット1"
    },
    "preset2": {
      "id": "preset_456",
      "name": "プリセット2"
    },
    "differences": {
      "hair_color": {
        "preset1": "#8B4513",
        "preset2": "#FF0000"
      },
      "outfit": {
        "preset1": "casual_shirt",
        "preset2": "business_suit"
      }
    },
    "similarity_score": 0.75
  }
}
```

### アバター管理

#### アバター一覧取得

```http
GET /api/v1/avatars
```

**レスポンス:**
```json
{
  "status": "success",
  "data": {
    "avatars": [
      {
        "id": "avatar_123",
        "name": "マイアバター",
        "model_path": "/avatars/my_avatar.vrm",
        "thumbnail": "/thumbnails/avatar_123.png",
        "compatible_presets": ["preset_123", "preset_456"],
        "created_at": "2024-01-15T10:00:00Z",
        "file_size": 15728640,
        "version": "1.0"
      }
    ]
  }
}
```

#### アバターアップロード

```http
POST /api/v1/avatars/upload
Content-Type: multipart/form-data
```

**フォームデータ:**
- `file`: アバターファイル（.vrm）
- `name`: アバター名
- `description`: 説明（オプション）

#### アバターとプリセットの適用

```http
POST /api/v1/avatars/{avatar_id}/apply-preset
Content-Type: application/json
```

**リクエストボディ:**
```json
{
  "preset_id": "preset_123",
  "preview_only": false,
  "save_as_new_preset": true,
  "new_preset_name": "カスタムプリセット"
}
```

### 設定管理

#### 設定取得

```http
GET /api/v1/config
```

**レスポンス:**
```json
{
  "status": "success",
  "data": {
    "app_name": "Cocoa",
    "version": "2.0.0",
    "language": "ja",
    "performance": {
      "cache_enabled": true,
      "max_workers": 4
    },
    "ui": {
      "theme": "light",
      "auto_save": true
    }
  }
}
```

#### 設定更新

```http
PUT /api/v1/config
Content-Type: application/json
```

**リクエストボディ:**
```json
{
  "language": "en",
  "ui": {
    "theme": "dark",
    "auto_save": false
  }
}
```

### システム情報

#### システム状態取得

```http
GET /status
```

**レスポンス:**
```json
{
  "status": "success",
  "data": {
    "system_status": "healthy",
    "uptime": 86400,
    "version": "2.0.0",
    "environment": "production",
    "resources": {
      "cpu_usage": 15.2,
      "memory_usage": 45.8,
      "disk_usage": 62.1
    },
    "services": {
      "database": "healthy",
      "cache": "healthy",
      "web_server": "healthy"
    },
    "last_backup": "2024-01-15T06:00:00Z"
  }
}
```

#### システムメトリクス取得

```http
GET /api/v1/system/metrics
```

**クエリパラメータ:**
- `period`: 期間（`1h`, `24h`, `7d`, `30d`）
- `metric`: メトリクス種別（`cpu`, `memory`, `disk`, `network`）

**レスポンス:**
```json
{
  "status": "success",
  "data": {
    "period": "24h",
    "metrics": [
      {
        "timestamp": "2024-01-15T00:00:00Z",
        "cpu_usage": 12.5,
        "memory_usage": 42.3,
        "disk_io_read": 1024000,
        "disk_io_write": 512000
      }
    ],
    "summary": {
      "avg_cpu": 15.2,
      "max_memory": 58.9,
      "total_requests": 15240
    }
  }
}
```

### セキュリティ

#### セキュリティスキャン実行

```http
POST /api/v1/security/scan
Content-Type: application/json
```

**リクエストボディ:**
```json
{
  "scan_type": "comprehensive",
  "target_components": ["config", "presets", "uploads"],
  "include_performance": true
}
```

**レスポンス:**
```json
{
  "status": "success",
  "data": {
    "scan_id": "scan_789",
    "status": "completed",
    "security_score": 95,
    "vulnerabilities": [
      {
        "severity": "low",
        "category": "configuration",
        "description": "デバッグモードが有効になっています",
        "recommendation": "本番環境ではデバッグモードを無効にしてください"
      }
    ],
    "scan_duration": 12.5,
    "scanned_files": 156
  }
}
```

#### 監査ログ取得

```http
GET /api/v1/security/audit-log
```

**クエリパラメータ:**
- `start_date`: 開始日時
- `end_date`: 終了日時
- `user_id`: ユーザーID
- `action`: アクション種別
- `limit`: 取得件数

### パフォーマンス

#### パフォーマンステスト実行

```http
POST /api/v1/performance/test
Content-Type: application/json
```

**リクエストボディ:**
```json
{
  "test_suite": "comprehensive",
  "quick_mode": false,
  "include_optimization": true
}
```

**レスポンス:**
```json
{
  "status": "success",
  "data": {
    "test_id": "test_456",
    "status": "running",
    "estimated_duration": 120,
    "progress_url": "/api/v1/performance/test/test_456/progress"
  }
}
```

#### 最適化実行

```http
POST /api/v1/performance/optimize
Content-Type: application/json
```

**リクエストボディ:**
```json
{
  "optimization_level": "aggressive",
  "categories": ["memory", "cpu", "io", "database"],
  "dry_run": false
}
```

## WebSocket API

### 接続

```javascript
const ws = new WebSocket('wss://localhost:8080/api/ws');
```

### リアルタイム更新購読

```json
{
  "action": "subscribe",
  "channels": ["presets", "system_status", "performance"],
  "auth_token": "your_session_token"
}
```

### プリセット更新通知

```json
{
  "channel": "presets",
  "event": "preset_updated",
  "data": {
    "preset_id": "preset_123",
    "changes": ["parameters", "name"],
    "updated_by": "user_456",
    "timestamp": "2024-01-15T12:00:00Z"
  }
}
```

### システム状態通知

```json
{
  "channel": "system_status",
  "event": "resource_alert",
  "data": {
    "alert_type": "high_memory_usage",
    "current_value": 89.5,
    "threshold": 85.0,
    "severity": "warning"
  }
}
```

## SDKと統合例

### Python SDK

```python
from cocoa_sdk import CocoaClient

# クライアント初期化
client = CocoaClient(
    base_url="https://localhost:8080",
    api_key="your_api_key"
)

# プリセット取得
presets = client.presets.list(
    category="casual",
    limit=10
)

# プリセット作成
new_preset = client.presets.create(
    name="新しいプリセット",
    parameters={
        "hair_color": "#FF0000",
        "outfit": "casual_shirt"
    }
)

# アバターにプリセット適用
result = client.avatars.apply_preset(
    avatar_id="avatar_123",
    preset_id=new_preset.id
)
```

### JavaScript SDK

```javascript
import { CocoaAPI } from 'cocoa-js-sdk';

// クライアント初期化
const cocoa = new CocoaAPI({
  baseURL: 'https://localhost:8080',
  apiKey: 'your_api_key'
});

// プリセット取得
const presets = await cocoa.presets.list({
  category: 'casual',
  limit: 10
});

// プリセット作成
const newPreset = await cocoa.presets.create({
  name: '新しいプリセット',
  parameters: {
    hair_color: '#FF0000',
    outfit: 'casual_shirt'
  }
});

// リアルタイム更新購読
cocoa.subscribe('presets', (event) => {
  console.log('プリセット更新:', event.data);
});
```

### cURL例

```bash
# プリセット一覧取得
curl -X GET "https://localhost:8080/api/v1/presets" \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json"

# プリセット作成
curl -X POST "https://localhost:8080/api/v1/presets" \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "APIテストプリセット",
    "parameters": {
      "hair_color": "#0000FF"
    }
  }'

# システム状態確認
curl -X GET "https://localhost:8080/status" \
  -H "Authorization: Bearer your_api_key"
```

## データ形式

### プリセットパラメータ仕様

```json
{
  "parameters": {
    // 基本外見
    "hair_color": "#8B4513",
    "eye_color": "#0000FF",
    "skin_tone": "#FFDBAC",

    // 服装
    "outfit": "casual_shirt",
    "outfit_color": "#FF0000",
    "accessories": ["glasses", "watch"],

    // 表情・ポーズ
    "facial_expression": "smile",
    "pose": "standing",
    "gesture": "waving",

    // 詳細設定
    "hair_style": "short",
    "body_type": "average",
    "height": 165,

    // カスタムパラメータ
    "custom_params": {
      "special_effect": "glowing_eyes",
      "animation": "idle_casual"
    }
  }
}
```

### バリデーションルール

- `hair_color`, `eye_color`, `skin_tone`: 16進数カラーコード
- `height`: 100-200の数値
- `accessories`: 配列、最大10個
- 必須フィールド: `name`, `parameters`

## バージョニング

APIバージョンはURLパスで指定：
- 現在バージョン: `v1`
- ベータ機能: `v2-beta`
- 非推奨警告は6ヶ月前に通知

## レスポンス時間とパフォーマンス

### ターゲットレスポンス時間

| エンドポイント種別 | ターゲット時間 |
|-------------------|----------------|
| プリセット取得 | < 100ms |
| プリセット作成/更新 | < 500ms |
| アバター処理 | < 2s |
| システム情報 | < 50ms |
| セキュリティスキャン | < 30s |

### キャッシュ戦略

- プリセット一覧: 5分間キャッシュ
- システム設定: 1時間キャッシュ
- 静的アセット: 24時間キャッシュ

## 新機能拡張

### ログ暗号化機能

#### 概要
ログファイルの暗号化機能により、機密情報の漏洩を防ぎます。

#### 設定例
```json
{
  "logging": {
    "enable_encryption": true,
    "encryption_key": "your_32_byte_key_here"
  }
}
```

#### 使用例
```python
from main.logging_manager import LoggingManager

config = {
    "enable_encryption": True,
    "encryption_key": "your_32_byte_key_here",
    "log_dir": "logs"
}
logger = LoggingManager(config)
```

### 非同期キャッシュ機能

#### 概要
非同期処理に対応したキャッシュシステムで、パフォーマンスを向上させます。

#### 使用例
```python
from main.cache_manager import AsyncCacheManager

async def example():
    cache = AsyncCacheManager()
    await cache.set("key", "value")
    result = await cache.get("key")
```

### カスタムメトリクス機能

#### 概要
アプリケーション固有のメトリクスを収集・監視できます。

#### 使用例
```python
from main.performance_monitor import get_performance_monitor

monitor = get_performance_monitor()
monitor.add_custom_metric("active_users", 42, "count", "現在のアクティブユーザー数")
metrics = monitor.get_custom_metrics()
```

## 追加リソース

- [ログ暗号化ガイドライン](LOG_ENCRYPTION_GUIDE.md)
- [パフォーマンス最適化ベストプラクティス](PERFORMANCE_BEST_PRACTICES.md)
- [カスタムメトリクス実装例](CUSTOM_METRICS_EXAMPLES.md)

---