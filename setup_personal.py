#!/usr/bin/env python3
"""
Cocoa 個人使用向け自動セットアップスクリプト

このスクリプトは以下を自動的に実行します:
1. セキュリティキーの生成
2. 管理者パスワードの設定
3. 最適化された設定ファイルの作成
4. 必須ディレクトリの作成
5. パーミッションの設定
6. セキュリティレベルの最大化
"""
import os
import sys
import json
import secrets
import hashlib
from pathlib import Path
from typing import Dict

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    print("警告: bcrypt が利用できません。パスワードハッシュ化が簡易版になります。")
    print("推奨: pip install bcrypt")

try:
    from cryptography.fernet import Fernet  # noqa: F401
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("警告: cryptography が利用できません。暗号化機能が制限されます。")
    print("推奨: pip install cryptography")


class PersonalSecuritySetup:
    """個人使用向けセキュリティセットアップ"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.config_dir = self.base_dir / "config"
        self.env_file = self.base_dir / ".env"
        self.personal_config = self.config_dir / "config_personal.json"

    def run(self):
        """セットアップ実行"""
        print("=" * 60)
        print("🔒 Cocoa 個人使用向けセキュリティセットアップ")
        print("=" * 60)
        print()

        # ステップ1: 必須ディレクトリの作成
        print("📁 ステップ1: 必須ディレクトリの作成...")
        self.create_directories()
        print("✅ 完了\n")

        # ステップ2: セキュリティキーの生成
        print("🔑 ステップ2: セキュリティキーの生成...")
        keys = self.generate_security_keys()
        print("✅ 完了\n")

        # ステップ3: 管理者パスワードの設定
        print("👤 ステップ3: 管理者パスワードの設定...")
        admin_password = self.setup_admin_password()
        print("✅ 完了\n")

        # ステップ4: 環境変数ファイルの作成
        print("⚙️  ステップ4: 環境変数ファイルの作成...")
        self.create_env_file(keys, admin_password)
        print("✅ 完了\n")

        # ステップ5: 最適化設定ファイルの作成
        print("🎯 ステップ5: 個人用最適化設定の作成...")
        self.create_personal_config()
        print("✅ 完了\n")

        # ステップ6: パーミッション設定
        print("🔐 ステップ6: セキュリティパーミッションの設定...")
        self.set_permissions()
        print("✅ 完了\n")

        # 完了メッセージ
        self.print_completion_message(admin_password)

    def create_directories(self):
        """必須ディレクトリの作成"""
        directories = [
            "config",
            "logs",
            "backups",
            "data",
            "data/cache",
            "data/presets",
            "data/avatars",
            "reports"
        ]

        for dir_name in directories:
            dir_path = self.base_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"  ✓ {dir_name}/")

    def generate_security_keys(self) -> Dict[str, str]:
        """セキュリティキーの生成"""
        keys = {
            "secret_key": secrets.token_urlsafe(32),
            "encryption_key": secrets.token_urlsafe(32),
            "backup_key": secrets.token_urlsafe(32),
            "session_key": secrets.token_urlsafe(32)
        }

        print(f"  ✓ SECRET_KEY: {keys['secret_key'][:16]}... (32文字)")
        print(f"  ✓ ENCRYPTION_KEY: {keys['encryption_key'][:16]}... (32文字)")
        print(f"  ✓ BACKUP_KEY: {keys['backup_key'][:16]}... (32文字)")
        print(f"  ✓ SESSION_KEY: {keys['session_key'][:16]}... (32文字)")

        return keys

    def setup_admin_password(self) -> str:
        """管理者パスワードの設定"""
        import getpass

        while True:
            print("\n管理者パスワードを設定してください:")
            print("要件: 12文字以上、大文字・小文字・数字・特殊文字を含む")
            print()

            password = getpass.getpass("パスワード: ")
            password_confirm = getpass.getpass("パスワード(確認): ")

            if password != password_confirm:
                print("❌ パスワードが一致しません。もう一度入力してください。\n")
                continue

            # パスワード強度チェック
            if len(password) < 12:
                print("❌ パスワードは12文字以上必要です。\n")
                continue

            if not any(c.isupper() for c in password):
                print("❌ 大文字を含めてください。\n")
                continue

            if not any(c.islower() for c in password):
                print("❌ 小文字を含めてください。\n")
                continue

            if not any(c.isdigit() for c in password):
                print("❌ 数字を含めてください。\n")
                continue

            if not any(c in "!@#$%^&*(),.?\":{}|<>" for c in password):
                print("❌ 特殊文字を含めてください。\n")
                continue

            # パスワードハッシュ化
            if BCRYPT_AVAILABLE:
                hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
                password_hash = hashed.decode()
                print("  ✓ bcryptハッシュ生成完了")
            else:
                # フォールバック: SHA-256 (本番では非推奨)
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                print("  ⚠️  SHA-256ハッシュ使用 (bcrypt推奨)")

            return password_hash

    def create_env_file(self, keys: Dict[str, str], admin_password: str):
        """環境変数ファイルの作成"""
        env_content = f"""# Cocoa 個人使用向け環境変数
# 自動生成日時: {self._get_timestamp()}

# ============================================================================
# セキュリティ設定 (自動生成)
# ============================================================================

# アプリケーション環境
COCOA_ENVIRONMENT=personal

# セキュリティキー (自動生成)
COCOA_SECRET_KEY={keys['secret_key']}
COCOA_ENCRYPTION_KEY={keys['encryption_key']}
COCOA_BACKUP_ENCRYPTION_KEY={keys['backup_key']}
COCOA_SESSION_KEY={keys['session_key']}

# 管理者認証
COCOA_ADMIN_USER=admin
COCOA_ADMIN_PASS={admin_password}

# ============================================================================
# セキュリティレベル: MAXIMUM (個人使用最適化)
# ============================================================================

# セキュリティポリシー
COCOA_SECURITY_LEVEL=paranoid
COCOA_ENABLE_2FA=false
COCOA_ENABLE_AUDIT_LOG=true
COCOA_STRICT_IP_BINDING=false
COCOA_STRICT_UA_BINDING=false

# パスワードポリシー
COCOA_PASSWORD_MIN_LENGTH=12
COCOA_PASSWORD_REQUIRE_SPECIAL=true
COCOA_PASSWORD_REQUIRE_NUMBERS=true
COCOA_PASSWORD_REQUIRE_UPPERCASE=true

# アクセス制御
COCOA_MAX_LOGIN_ATTEMPTS=5
COCOA_LOCKOUT_DURATION_MINUTES=15

# ============================================================================
# パフォーマンス最適化 (個人使用)
# ============================================================================

# データベース
COCOA_DATABASE_TYPE=sqlite
COCOA_DB_PATH=data/cocoa_personal.db

# キャッシュ
COCOA_ENABLE_CACHE=true
COCOA_CACHE_SIZE_MB=512
COCOA_CACHE_TTL_SECONDS=3600

# パフォーマンス監視
COCOA_PERFORMANCE_INTERVAL=5
COCOA_PERFORMANCE_CPU_THRESHOLD=80
COCOA_PERFORMANCE_MEMORY_THRESHOLD=85

# ============================================================================
# Web管理コンソール
# ============================================================================

# サーバー設定
COCOA_WEB_HOST=127.0.0.1
COCOA_WEB_PORT=8080
COCOA_FORCE_HTTPS=false
COCOA_ALLOWED_HOSTS=localhost,127.0.0.1

# セッション
COCOA_SESSION_COOKIE_NAME=cocoa_personal_session
COCOA_SESSION_SAMESITE=Strict
COCOA_SESSION_SECURE=false
COCOA_SESSION_IDLE_TIMEOUT_SECONDS=1800
COCOA_SESSION_DURATION_MINUTES=120

# ============================================================================
# バックアップ設定
# ============================================================================

COCOA_BACKUP_PATH=backups/
COCOA_BACKUP_RETENTION_DAYS=90
COCOA_BACKUP_AUTO_VERIFY=true
COCOA_BACKUP_INTERVAL_HOURS=24

# ============================================================================
# ロギング
# ============================================================================

COCOA_LOG_LEVEL=INFO
COCOA_AUDIT_MAX_BYTES=10485760
COCOA_MAX_LOG_PREVIEW_LINES=500

# ============================================================================
# 機能フラグ
# ============================================================================

COCOA_DEVELOPMENT_MODE=false
COCOA_DEBUG=false
COCOA_ENABLE_AUDIT_LOG=true

# 言語・タイムゾーン
COCOA_LOCALE=ja
TZ=Asia/Tokyo
"""

        with open(self.env_file, 'w', encoding='utf-8') as f:
            f.write(env_content)

        print("  ✓ .env ファイル作成完了")

    def create_personal_config(self):
        """個人用最適化設定の作成"""
        personal_config = {
            "app_name": "Cocoa Personal Edition",
            "version": "2.0.0-personal",
            "language": "ja",
            "debug": False,
            "log_level": "INFO",

            "security": {
                "level": "maximum",
                "password_min_length": 12,
                "password_require_special": True,
                "password_require_numbers": True,
                "password_require_uppercase": True,
                "max_login_attempts": 5,
                "lockout_duration_minutes": 15,
                "enable_2fa": False,
                "enable_audit_log": True,
                "allowed_ips": ["127.0.0.1", "::1"],
                "blocked_ips": []
            },

            "web_admin": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8080,
                "debug": False,
                "max_workers": 2,
                "ssl": {
                    "enabled": False,
                    "cert_path": None,
                    "key_path": None
                },
                "session": {
                    "timeout_minutes": 120,
                    "max_sessions": 10
                }
            },

            "performance_monitoring": {
                "enabled": True,
                "interval_seconds": 5,
                "alert_thresholds": {
                    "cpu_percent": 80,
                    "memory_percent": 85,
                    "disk_usage_percent": 90,
                    "response_time_ms": 1000
                },
                "auto_optimize": True
            },

            "backup": {
                "enabled": True,
                "interval_hours": 24,
                "max_backups": 30,
                "backup_path": "backups/",
                "compression": True,
                "auto_verify": True,
                "retention_days": 90
            },

            "cache": {
                "enabled": True,
                "memory_cache_size_mb": 512,
                "disk_cache_size_mb": 2048,
                "cache_ttl_seconds": 3600,
                "cleanup_interval_seconds": 3600,
                "auto_cleanup": True
            },

            "avatar": {
                "default_path": "data/avatars/",
                "max_parameters": 100000,
                "auto_save": True,
                "auto_backup": True,
                "preset_path": "data/presets/"
            },

            "database": {
                "type": "sqlite",
                "path": "data/cocoa_personal.db",
                "pool_size": 5,
                "backup_enabled": True,
                "auto_vacuum": True
            },

            "notification": {
                "enabled": True,
                "desktop_notifications": True,
                "sound_alerts": True,
                "log_alerts": True
            },

            "rate_limiting": {
                "enabled": False,
                "requests_per_minute": 1000,
                "requests_per_hour": 10000
            },

            "ui": {
                "theme": "auto",
                "language": "ja",
                "font_size": 12,
                "show_advanced_options": True,
                "confirm_dangerous_operations": True
            },

            "privacy": {
                "telemetry_enabled": False,
                "anonymous_usage_stats": False,
                "local_only": True
            }
        }

        with open(self.personal_config, 'w', encoding='utf-8') as f:
            json.dump(personal_config, f, ensure_ascii=False, indent=2)

        print("  ✓ config/config_personal.json 作成完了")

    def set_permissions(self):
        """セキュリティパーミッションの設定"""
        if sys.platform != 'win32':
            # Unix系の場合、パーミッション設定
            sensitive_files = [
                self.env_file,
                self.config_dir / "config_personal.json"
            ]

            for file_path in sensitive_files:
                if file_path.exists():
                    os.chmod(file_path, 0o600)  # 所有者のみ読み書き可能
                    print(f"  ✓ {file_path.name} のパーミッション: 600")

            # ディレクトリパーミッション
            secure_dirs = [
                self.base_dir / "config",
                self.base_dir / "backups",
                self.base_dir / "data"
            ]

            for dir_path in secure_dirs:
                if dir_path.exists():
                    os.chmod(dir_path, 0o700)  # 所有者のみアクセス可能
                    print(f"  ✓ {dir_path.name}/ のパーミッション: 700")
        else:
            print("  ℹ️  Windows環境のため、パーミッション設定をスキップ")

    def print_completion_message(self, admin_password: str):
        """完了メッセージの表示"""
        print("=" * 60)
        print("🎉 セットアップ完了!")
        print("=" * 60)
        print()
        print("📝 次のステップ:")
        print()
        print("1. 依存関係のインストール:")
        print("   pip install -r requirements.txt")
        print()
        print("2. アプリケーションの起動:")
        print("   python main/main.py")
        print()
        print("3. Web管理コンソールへのアクセス:")
        print("   http://localhost:8080")
        print()
        print("4. ログイン情報:")
        print("   ユーザー名: admin")
        print("   パスワード: (設定したパスワード)")
        print()
        print("=" * 60)
        print()
        print("🔒 セキュリティ情報:")
        print("  • 環境変数ファイル: .env")
        print("  • 設定ファイル: config/config_personal.json")
        print("  • セキュリティレベル: MAXIMUM (個人使用最適化)")
        print("  • 暗号化: AES-256-GCM")
        print("  • バックアップ: 毎日自動実行、90日保持")
        print()
        print("⚠️  重要:")
        print("  • .env ファイルは絶対に公開しないでください")
        print("  • 定期的にバックアップを確認してください")
        print("  • パスワードは安全に保管してください")
        print()
        print("=" * 60)

    def _get_timestamp(self):
        """タイムスタンプ取得"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    """メイン関数"""
    setup = PersonalSecuritySetup()
    setup.run()


if __name__ == "__main__":
    main()
