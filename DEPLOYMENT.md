# 🚀 Cocoa デプロイメントガイド

## 本番環境展開チェックリスト

### 1. セキュリティ設定（必須）

```bash
# 1. セキュアな管理者認証情報を設定
python setup_security.py

# 2. 環境変数設定
export COCOA_ENVIRONMENT="production"
export COCOA_SECRET_KEY="your_secure_random_key_32_chars_min"
export COCOA_ADMIN_USER="your_admin_username"
export COCOA_ADMIN_PASS="your_secure_password_hash"
export COCOA_SESSION_SECURE="true"
export COCOA_SESSION_SAMESITE="Strict"

# 3. ログレベル調整
export COCOA_LOG_LEVEL="WARNING"
```

### 2. 本番用設定ファイル

```json
{
  "app_name": "Cocoa Production",
  "version": "2.0.0",
  "language": "ja",
  "debug": false,
  "log_level": "WARNING",
  "backup": {
    "enabled": true,
    "interval_minutes": 30,
    "max_backups": 48,
    "backup_path": "/secure/backup/path/"
  },
  "performance_monitoring": {
    "enabled": true,
    "interval_seconds": 10,
    "alert_thresholds": {
      "cpu_percent": 70,
      "memory_percent": 80,
      "disk_usage_percent": 85
    }
  },
  "web_admin": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 8080,
    "debug": false
  }
}
```

### 3. ネットワークセキュリティ

```bash
# ファイアウォール設定（Ubuntu例）
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 443/tcp  # HTTPS only
sudo ufw deny 8080/tcp  # Direct access blocked

# リバースプロキシ設定（Nginx）
sudo apt install nginx
```

### 4. SSL/TLS設定

```nginx
# /etc/nginx/sites-available/cocoa
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/ssl/certificate.crt;
    ssl_certificate_key /path/to/ssl/private.key;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        # Update the port to match your web_admin configuration
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

### 5. サービス化（systemd）

```ini
# /etc/systemd/system/cocoa.service
[Unit]
Description=Cocoa Web Admin Service
After=network.target

[Service]
Type=simple
User=cocoa
Group=cocoa
WorkingDirectory=/opt/cocoa
Environment=COCOA_ENVIRONMENT=production
Environment=COCOA_SECRET_KEY=your_secret_key
Environment=COCOA_ADMIN_USER=your_admin
Environment=COCOA_ADMIN_PASS=your_password_hash
Environment=COCOA_SESSION_SECURE=true
ExecStart=/opt/cocoa/venv/bin/python main/web_admin_improved.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
# サービス有効化
sudo systemctl enable cocoa
sudo systemctl start cocoa
sudo systemctl status cocoa
```

### 6. 監視とログ

```bash
# ログローテーション設定
sudo nano /etc/logrotate.d/cocoa

/opt/cocoa/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 cocoa cocoa
    postrotate
        systemctl reload cocoa
    endscript
}
```

### 7. バックアップ自動化

```bash
#!/bin/bash
# backup_cocoa.sh

BACKUP_DIR="/secure/backups/cocoa"
DATE=$(date +%Y%m%d_%H%M%S)

# 設定バックアップ
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" /opt/cocoa/config/

# ログバックアップ
tar -czf "$BACKUP_DIR/logs_$DATE.tar.gz" /opt/cocoa/logs/

# 古いバックアップ削除（30日以上）
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete

# Crontab設定
# 0 2 * * * /opt/cocoa/scripts/backup_cocoa.sh
```

### 8. セキュリティ監査

```bash
# 1. ファイル権限確認
find /opt/cocoa -type f -name "*.py" -exec chmod 644 {} \;
find /opt/cocoa -type d -exec chmod 755 {} \;
chmod 600 /opt/cocoa/config/*.json

# 2. 所有者設定
chown -R cocoa:cocoa /opt/cocoa
chmod 750 /opt/cocoa

# 3. SELinux設定（RedHat系）
setsebool -P httpd_can_network_connect 1
```

## トラブルシューティング

### よくある問題

| 症状 | 原因 | 解決方法 |
|------|------|----------|
| 503 Service Unavailable | Cocoaサービス停止 | `systemctl start cocoa` |
| SSL証明書エラー | 証明書期限切れ | SSL証明書を更新 |
| ログイン失敗 | 環境変数未設定 | 認証情報を再設定 |
| メモリ不足 | リソース枯渇 | サーバーリソース確認 |

### ログ確認

```bash
# サービスログ
journalctl -u cocoa -f

# アプリケーションログ
tail -f /opt/cocoa/logs/cocoa.log

# Nginxログ
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### パフォーマンス監視

```bash
# システムリソース確認
htop
iotop
nethogs

# Cocoaメトリクス確認
curl -X GET https://your-domain.com/status
```

## セキュリティチェック

### 定期実行スクリプト

```bash
#!/bin/bash
# security_check.sh

echo "=== Cocoa Security Check ==="

# 1. プロセス確認
if ! pgrep -f "web_admin_improved.py" > /dev/null; then
    echo "⚠️  Cocoaプロセスが動作していません"
fi

# 2. ポート確認
if ! netstat -tln | grep ":8080" > /dev/null; then
    echo "⚠️  ポート8080がリッスンしていません"
fi

# 3. SSL証明書期限確認
DAYS_LEFT=$(openssl x509 -in /path/to/certificate.crt -checkend 604800 2>/dev/null)
if [ $? -ne 0 ]; then
    echo "⚠️  SSL証明書が7日以内に期限切れです"
fi

# 4. ログサイズ確認
LOG_SIZE=$(du -sm /opt/cocoa/logs/ | cut -f1)
if [ $LOG_SIZE -gt 1000 ]; then
    echo "⚠️  ログサイズが1GB を超えています: ${LOG_SIZE}MB"
fi

echo "セキュリティチェック完了"
```

## アップデート手順

```bash
# 1. バックアップ作成
./backup_cocoa.sh

# 2. サービス停止
sudo systemctl stop cocoa

# 3. コード更新
cd /opt/cocoa
git pull origin main

# 4. 依存関係更新
pip install -r requirements.txt

# 5. 設定検証
python -c "from main.config_validator import ConfigValidator; print(ConfigValidator().validate('config/config.json'))"

# 6. サービス再開
sudo systemctl start cocoa

# 7. 動作確認
curl -k https://localhost/status
```

---

**⚠️ 重要**: 本番環境では必ずHTTPSを使用し、デフォルトパスワードは絶対に使用しないでください。