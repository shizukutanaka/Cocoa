# 🔧 Cocoaトラブルシューティングガイド

## 📋 目次

- [一般的な問題](#一般的な問題)
- [インストールと起動の問題](#インストールと起動の問題)
- [データベース関連の問題](#データベース関連の問題)
- [パフォーマンスの問題](#パフォーマンスの問題)
- [セキュリティ関連の問題](#セキュリティ関連の問題)
- [ネットワークとアクセスの問題](#ネットワークとアクセスの問題)
- [ファイルとデータの問題](#ファイルとデータの問題)
- [ログとデバッグ](#ログとデバッグ)
- [診断ツール](#診断ツール)
- [よくある質問 (FAQ)](#よくある質問-faq)

## 🚨 一般的な問題

### アプリケーションが起動しない

#### 症状
- `python main/main.py` を実行してもエラーが発生する
- 「モジュールが見つかりません」エラー

#### 原因と対策

1. **Python環境の問題**
```bash
# Python バージョン確認
python --version
# Python 3.9以上が必要

# 仮想環境の確認
which python
# venv内のPythonを使用しているか確認
```

2. **依存関係の問題**
```bash
# 依存関係の再インストール
pip install -r requirements.txt

# 特定のモジュールが見つからない場合
pip install [module_name]

# 依存関係の確認
pip list
```

3. **設定ファイルの問題**
```bash
# 設定ファイルの存在確認
ls config/
# config.json が存在するか確認

# 設定ファイルの構文チェック
python -c "import json; json.load(open('config/config.json'))"
```

#### 解決手順
```bash
# 1. 仮想環境アクティベート
source venv/bin/activate  # Linux/macOS
# または
venv\Scripts\activate     # Windows

# 2. 依存関係インストール
pip install -r requirements.txt

# 3. 設定ファイル作成
cp config/config.example.json config/config.json

# 4. セキュリティ設定
python setup_security.py

# 5. アプリケーション起動
python main/main.py
```

### Webインターフェースにアクセスできない

#### 症状
- ブラウザで `http://localhost:8080` にアクセスできない
- 「このサイトにアクセスできません」エラー

#### 診断コマンド
```bash
# プロセス確認
ps aux | grep python

# ポート使用状況確認
netstat -tlnp | grep 8080
lsof -i :8080

# ファイアウォール確認 (Linux)
sudo ufw status
iptables -L

# Windows ファイアウォール確認
netsh advfirewall show allprofiles
```

#### 解決策

1. **ポート競合の解決**
```json
// config/config.json
{
  "web_admin": {
    "port": 8081  // 異なるポート番号に変更
  }
}
```

2. **ホスト設定の変更**
```json
{
  "web_admin": {
    "host": "0.0.0.0",  // 外部からのアクセスを許可
    "port": 8080
  }
}
```

3. **ファイアウォール設定**
```bash
# Ubuntu/Debian
sudo ufw allow 8080

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload

# Windows
netsh advfirewall firewall add rule name="Cocoa" dir=in action=allow protocol=TCP localport=8080
```

## 💾 データベース関連の問題

### データベース接続エラー

#### 症状
- `Connection refused` エラー
- `Database file not found` エラー
- `Authentication failed` エラー

#### 診断と解決

1. **SQLite データベースの問題**
```bash
# データベースファイルの確認
ls -la data/
ls -la data/cocoa.db

# ディレクトリ権限の確認
ls -ld data/

# ディレクトリ作成
mkdir -p data

# データベース初期化
python scripts/migrate_to_database.py
```

2. **PostgreSQL接続問題**
```bash
# PostgreSQL サービス状態確認
sudo systemctl status postgresql

# 接続テスト
psql -h localhost -p 5432 -U cocoa_user -d cocoa

# 設定確認
cat config/database.json
```

3. **MySQL接続問題**
```bash
# MySQL サービス状態確認
sudo systemctl status mysql

# 接続テスト
mysql -h localhost -P 3306 -u cocoa_user -p cocoa

# 権限確認
mysql -u root -p -e "SHOW GRANTS FOR 'cocoa_user'@'localhost';"
```

#### データベース接続設定の修正

```json
// config/database.json
{
  "database": {
    "default": {
      "db_type": "sqlite",
      "database": "data/cocoa.db",
      "retry_attempts": 5,
      "retry_delay": 2.0,
      "pool_timeout": 60
    }
  }
}
```

### データ移行の問題

#### 症状
- 移行スクリプトが失敗する
- 「テーブルが存在しません」エラー

#### 解決手順

```bash
# 1. バックアップ作成
python scripts/migrate_to_database.py --backup

# 2. 強制移行実行
python scripts/migrate_to_database.py --force

# 3. ドライラン実行（問題確認）
python scripts/migrate_to_database.py --dry-run

# 4. 個別テーブル確認
sqlite3 data/cocoa.db ".tables"
sqlite3 data/cocoa.db ".schema presets"
```

## ⚡ パフォーマンスの問題

### アプリケーションが遅い

#### 症状
- レスポンス時間が長い（>5秒）
- CPU使用率が高い（>80%）
- メモリ使用量が多い（>2GB）

#### 診断ツール

```bash
# システムリソース確認
htop
top
free -h
df -h

# プロセス詳細確認
ps aux | grep python
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%mem

# パフォーマンステスト実行
python scripts/run_performance_tests.py

# 最適化実行
python main/performance_optimizer.py
```

#### 最適化設定

```json
// config/config.json - 低リソース環境用
{
  "performance": {
    "max_parallel_tasks": 2
  },
  "cache_manager": {
    "memory_cache_size": 256,
    "disk_cache_size": 512
  },
  "web_admin": {
    "max_workers": 2
  }
}
```

```json
// config/config.json - 高リソース環境用
{
  "performance": {
    "max_parallel_tasks": 8
  },
  "cache_manager": {
    "memory_cache_size": 2048,
    "disk_cache_size": 8192
  },
  "web_admin": {
    "max_workers": 8
  }
}
```

### メモリリーク

#### 症状
- メモリ使用量が継続的に増加
- アプリケーションが突然終了する

#### 診断と対策

```python
# メモリ使用量監視スクリプト
import psutil
import time

def monitor_memory():
    process = psutil.Process()

    for i in range(60):  # 60回監視
        memory_info = process.memory_info()
        print(f"Memory: {memory_info.rss / 1024 / 1024:.1f}MB")
        time.sleep(10)

# 実行
python -c "
import psutil, time
p = psutil.Process()
for i in range(10):
    print(f'Memory: {p.memory_info().rss/1024/1024:.1f}MB')
    time.sleep(5)
"
```

**対策:**

```json
{
  "performance": {
    "gc_threshold": [700, 10, 10]  // より頻繁なガベージコレクション
  },
  "cache_manager": {
    "cleanup_interval": 1800  // 30分間隔でクリーンアップ
  }
}
```

## 🔒 セキュリティ関連の問題

### ログインできない

#### 症状
- 正しいパスワードでログインできない
- 「認証に失敗しました」エラー

#### 診断と解決

```bash
# 1. 環境変数確認
echo $COCOA_ADMIN_USER
echo $COCOA_ADMIN_PASS

# 2. パスワードハッシュ確認
python -c "
from werkzeug.security import check_password_hash
import os
hash_value = os.environ.get('COCOA_ADMIN_PASS', '')
print('Hash exists:', bool(hash_value))
print('Hash valid:', check_password_hash(hash_value, 'your_password'))
"

# 3. 新しいパスワード設定
python setup_security.py
```

### セッションエラー

#### 症状
- ログイン後すぐにログアウトされる
- 「セッションが無効です」エラー

#### 解決策

```bash
# セッション設定確認
python -c "
import os
print('SECRET_KEY:', bool(os.environ.get('COCOA_SECRET_KEY')))
print('SESSION_SECURE:', os.environ.get('COCOA_SESSION_SECURE'))
"
```

```json
// セッション設定調整
{
  "web_admin": {
    "session_timeout": 7200,  // 2時間に延長
    "session_permanent": false
  }
}
```

### CSRF エラー

#### 症状
- フォーム送信時に「CSRF token missing」エラー

#### 解決策

```python
# CSRFトークン確認
# templates/base.html に以下を追加
<meta name="csrf-token" content="{{ csrf_token() }}">
```

## 🌐 ネットワークとアクセスの問題

### 外部からアクセスできない

#### 症状
- LAN内の他のコンピューターからアクセスできない

#### 解決手順

```bash
# 1. ホスト設定変更
{
  "web_admin": {
    "host": "0.0.0.0"  // 127.0.0.1 から変更
  }
}

# 2. ファイアウォール設定
sudo ufw allow 8080
sudo firewall-cmd --add-port=8080/tcp --permanent

# 3. 接続テスト
netstat -tlnp | grep 8080
telnet [server_ip] 8080
```

### プロキシ環境での問題

#### 症状
- リバースプロキシ経由でアクセスできない

#### Nginx設定例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 📁 ファイルとデータの問題

### ファイルアップロードエラー

#### 症状
- 「ファイルサイズが大きすぎます」エラー
- 「許可されていないファイル形式です」エラー

#### 解決策

```json
{
  "file_io": {
    "max_file_size_mb": 100,  // ファイルサイズ上限調整
    "allowed_extensions": [".json", ".vrm", ".png", ".jpg", ".jpeg", ".gif"]
  },
  "security": {
    "file_upload": {
      "max_file_size": 104857600,  // 100MB
      "scan_for_malware": false    // 一時的に無効化
    }
  }
}
```

### バックアップの問題

#### 症状
- バックアップが作成されない
- バックアップから復元できない

#### 診断と対策

```bash
# バックアップディレクトリ確認
ls -la backups/

# 権限確認
ls -ld backups/

# 手動バックアップ作成
python -c "
from main.backup_manager import BackupManager
backup_mgr = BackupManager()
backup_name = backup_mgr.create_backup()
print(f'Backup created: {backup_name}')
"

# バックアップ設定確認
python -c "
import json
with open('config/config.json') as f:
    config = json.load(f)
print('Backup config:', config.get('backup', {}))
"
```

## 📋 ログとデバッグ

### ログの確認方法

```bash
# アプリケーションログ
tail -f logs/cocoa.log
tail -n 100 logs/cocoa.log

# エラーログのみ表示
grep "ERROR" logs/cocoa.log
grep "CRITICAL" logs/cocoa.log

# 特定の時間範囲のログ
grep "2024-01-15 10:" logs/cocoa.log

# ログローテーション確認
ls -la logs/
```

### デバッグモードの有効化

```json
// config/config.json
{
  "debug": true,
  "log_level": "DEBUG",
  "web_admin": {
    "debug": true
  }
}
```

```bash
# 環境変数でデバッグ有効化
export FLASK_DEBUG=1
export COCOA_DEBUG=1
export COCOA_LOG_LEVEL=DEBUG

# デバッグ付きで起動
python main/web_admin_improved.py
```

### 詳細ログの有効化

```python
# デバッグログ設定
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
```

## 🔧 診断ツール

### 総合診断スクリプト

```bash
#!/bin/bash
# cocoa_diagnose.sh

echo "🔍 Cocoa システム診断"
echo "==================="

echo -e "\n📊 システム情報:"
echo "OS: $(uname -s)"
echo "Python: $(python --version)"
echo "メモリ: $(free -h | grep '^Mem:' | awk '{print $2}')"
echo "ディスク: $(df -h / | tail -1 | awk '{print $4}') 利用可能"

echo -e "\n🔧 プロセス状態:"
ps aux | grep -E "(python|cocoa)" | grep -v grep

echo -e "\n🌐 ネットワーク:"
netstat -tlnp | grep 8080

echo -e "\n📁 ファイル確認:"
echo "設定ファイル: $(ls config/*.json 2>/dev/null | wc -l) 個"
echo "ログファイル: $(ls logs/*.log 2>/dev/null | wc -l) 個"
echo "データファイル: $(ls data/* 2>/dev/null | wc -l) 個"

echo -e "\n🔒 セキュリティ:"
echo "SECRET_KEY: $([ -n "$COCOA_SECRET_KEY" ] && echo "設定済み" || echo "未設定")"
echo "ADMIN_USER: $([ -n "$COCOA_ADMIN_USER" ] && echo "設定済み" || echo "未設定")"

echo -e "\n✅ 診断完了"
```

### Python診断スクリプト

```python
#!/usr/bin/env python3
"""
Cocoa 診断スクリプト
"""

import sys
import os
import json
import psutil
from pathlib import Path

def check_python_environment():
    """Python環境チェック"""
    print("🐍 Python環境:")
    print(f"  バージョン: {sys.version}")
    print(f"  実行可能ファイル: {sys.executable}")

    # 必要なモジュールチェック
    required_modules = ['flask', 'psutil', 'werkzeug']
    for module in required_modules:
        try:
            __import__(module)
            print(f"  ✅ {module}: インストール済み")
        except ImportError:
            print(f"  ❌ {module}: 未インストール")

def check_config_files():
    """設定ファイルチェック"""
    print("\n⚙️ 設定ファイル:")

    config_files = [
        'config/config.json',
        'config/database.json'
    ]

    for config_file in config_files:
        path = Path(config_file)
        if path.exists():
            try:
                with open(path) as f:
                    json.load(f)
                print(f"  ✅ {config_file}: 正常")
            except json.JSONDecodeError as e:
                print(f"  ❌ {config_file}: JSON エラー - {e}")
        else:
            print(f"  ⚠️ {config_file}: ファイルが存在しません")

def check_system_resources():
    """システムリソースチェック"""
    print("\n💻 システムリソース:")

    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    print(f"  CPU使用率: {cpu_percent:.1f}%")

    # メモリ
    memory = psutil.virtual_memory()
    print(f"  メモリ使用率: {memory.percent:.1f}% ({memory.used // 1024 // 1024}MB / {memory.total // 1024 // 1024}MB)")

    # ディスク
    disk = psutil.disk_usage('/')
    print(f"  ディスク使用率: {disk.percent:.1f}% ({disk.free // 1024 // 1024 // 1024}GB 利用可能)")

def check_network():
    """ネットワーク状態チェック"""
    print("\n🌐 ネットワーク:")

    # ポート8080の確認
    connections = psutil.net_connections()
    port_8080_used = any(conn.laddr.port == 8080 for conn in connections if conn.laddr)

    if port_8080_used:
        print("  ✅ ポート8080: 使用中")
    else:
        print("  ⚠️ ポート8080: 未使用")

def main():
    """メイン診断実行"""
    print("🔍 Cocoa システム診断")
    print("=" * 40)

    check_python_environment()
    check_config_files()
    check_system_resources()
    check_network()

    print("\n✅ 診断完了")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ 診断が中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 診断エラー: {e}")
        sys.exit(1)
```

## ❓ よくある質問 (FAQ)

### Q1: Cocoaを初回起動時に何をすればよいですか？

**A:** 以下の手順で初期設定を行ってください：

```bash
# 1. 依存関係インストール
pip install -r requirements.txt

# 2. セキュリティ設定
python setup_security.py

# 3. 設定ファイル確認
cat config/config.json

# 4. データベース初期化（必要に応じて）
python scripts/migrate_to_database.py

# 5. アプリケーション起動
python main/web_admin_improved.py
```

### Q2: パスワードを忘れた場合はどうすればよいですか？

**A:** セキュリティ設定スクリプトで新しいパスワードを設定できます：

```bash
python setup_security.py
# 新しいパスワードを入力
# 環境変数が自動的に更新されます
```

### Q3: 別のポートで起動したい場合は？

**A:** 設定ファイルでポート番号を変更してください：

```json
{
  "web_admin": {
    "port": 8081
  }
}
```

### Q4: エラーログを詳細に見たい場合は？

**A:** ログレベルをDEBUGに変更してください：

```json
{
  "debug": true,
  "log_level": "DEBUG"
}
```

### Q5: バックアップからデータを復元するには？

**A:** バックアップマネージャーを使用してください：

```python
from main.backup_manager import BackupManager
backup_mgr = BackupManager()

# バックアップ一覧表示
backups = backup_mgr.list_backups()
for backup in backups:
    print(f"{backup['name']}: {backup['timestamp']}")

# 復元実行
backup_mgr.restore_backup("backup_20240115_120000")
```

### Q6: パフォーマンスを向上させるには？

**A:** パフォーマンス最適化スクリプトを実行してください：

```bash
python main/performance_optimizer.py
python scripts/run_performance_tests.py
```

### Q7: セキュリティ監査を実行するには？

**A:** セキュリティスキャナーを使用してください：

```python
from main.security_scanner import SecurityScanner
scanner = SecurityScanner()
results = scanner.comprehensive_scan()
print(f"セキュリティスコア: {results['security_score']}")
```

---

## 🆘 それでも解決しない場合

### サポートリソース

1. **社内サポート**: 運用担当者が案内するサポート窓口をご利用ください
2. **ドキュメント**: [開発者ガイド](DEVELOPER_GUIDE.md)
3. **チームチャット**: 導入環境で指定されたサポート掲示板やチャットツールを活用してください

### 問題報告時に必要な情報

```bash
# 以下の情報を収集してサポートに送信してください

echo "=== System Information ==="
uname -a
python --version
pip list

echo -e "\n=== Cocoa Configuration ==="
cat config/config.json

echo -e "\n=== Recent Logs ==="
tail -50 logs/cocoa.log

echo -e "\n=== Process Information ==="
ps aux | grep python

echo -e "\n=== Network Status ==="
netstat -tlnp | grep 8080

echo -e "\n=== Disk Space ==="
df -h

echo -e "\n=== Memory Usage ==="
free -h
```

### 緊急時の対応

**システムが完全に応答しない場合:**

```bash
# 1. プロセス強制終了
pkill -f "python.*cocoa"

# 2. 設定をデフォルトに戻す
cp config/config.example.json config/config.json

# 3. 最小構成で起動
python main/main.py --safe-mode

# 4. ログ確認
tail -100 logs/cocoa.log
```

このガイドで解決しない問題については、遠慮なくサポートにお問い合わせください。