#!/usr/bin/env python3
"""
Cocoa Security Setup Script
セキュアな本番環境セットアップ
"""
import os
import secrets
import hashlib
import getpass
import json
from pathlib import Path

def generate_secure_config():
    """セキュアな設定を生成"""

    print("=== Cocoa Security Setup ===")
    print("本番環境用のセキュア設定を生成します。")

    # セキュアなランダムキー生成
    secret_key = secrets.token_hex(32)

    # 管理者認証情報
    admin_user = input("管理者ユーザー名 (デフォルト: admin): ").strip() or "admin"

    while True:
        admin_pass = getpass.getpass("管理者パスワード (8文字以上): ")
        if len(admin_pass) >= 8:
            break
        print("パスワードは8文字以上である必要があります。")

    # パスワードハッシュ化
    admin_pass_hash = hashlib.sha256(admin_pass.encode()).hexdigest()

    # 環境変数ファイル生成
    env_content = f"""# Cocoa Security Configuration
# 本番環境では必ずこれらの環境変数を設定してください

export COCOA_SECRET_KEY="{secret_key}"
export COCOA_ADMIN_USER="{admin_user}"
export COCOA_ADMIN_PASS="{admin_pass_hash}"
export COCOA_SESSION_SECURE="true"
export COCOA_SESSION_SAMESITE="Strict"
export COCOA_SESSION_IDLE_TIMEOUT_SECONDS="900"
export COCOA_SESSION_DURATION_MINUTES="60"
export COCOA_MAX_CONTENT_LENGTH="1048576"

# 本番環境では以下も設定を推奨
# export COCOA_ALLOWED_HOSTS="your-domain.com"
# export COCOA_RATE_LIMIT="100/hour"
"""

    # セキュリティ設定保存
    env_file = Path("cocoa_security.env")
    env_file.write_text(env_content)

    print(f"\n✓ セキュリティ設定ファイルを生成しました: {env_file}")
    print("\n重要な注意事項:")
    print("1. このファイルを安全な場所に保管してください")
    print("2. 本番環境では環境変数として設定してください")
    print("3. デフォルトパスワードは絶対に使用しないでください")
    print("4. 定期的にパスワードを変更してください")

    # .env.example も生成
    example_content = """# Cocoa Environment Variables Example
# Copy this file to .env and fill in your values

COCOA_SECRET_KEY=your_secret_key_here
COCOA_ADMIN_USER=your_admin_username
COCOA_ADMIN_PASS=your_password_hash
COCOA_SESSION_SECURE=true
COCOA_SESSION_SAMESITE=Strict
"""
    Path(".env.example").write_text(example_content)

    return True

if __name__ == "__main__":
    generate_secure_config()