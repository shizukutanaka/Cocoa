"""
設定ファイル暗号化システム
軽量で実用的な設定ファイルの暗号化・復号化機能を提供
"""

import json
import os
import time
import secrets
from pathlib import Path
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import logging

logger = logging.getLogger(__name__)


class ConfigEncryptor:
    """軽量で実用的な設定ファイル暗号化システム"""

    def __init__(self, encryption_key: Optional[str] = None):
        """暗号化システムを初期化"""
        self.key = encryption_key or os.getenv('COCOA_ENCRYPTION_KEY')
        if not self.key:
            # デフォルトキーを生成（本番環境では環境変数から取得）
            self.key = secrets.token_hex(32)
            logger.warning("暗号化キーが設定されていません。デフォルトキーを使用します。本番環境では環境変数から設定してください。")

        # キーをバイト列に変換
        self.key_bytes = self.key.encode('utf-8') if isinstance(self.key, str) else self.key

        # ソルトの生成
        self.salt = secrets.token_bytes(16)

    def _derive_key(self, salt: bytes) -> bytes:
        """パスワードから暗号化キーを派生"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(self.key_bytes)

    def encrypt_config_file(self, config_path: str, output_path: Optional[str] = None) -> bool:
        """設定ファイルを暗号化"""
        try:
            config_path_obj = Path(config_path)
            if not config_path_obj.exists():
                logger.error(f"設定ファイルが存在しません: {config_path}")
                return False

            # 設定ファイルの読み込み
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # 機密フィールドの抽出とマスク
            masked_config = self._mask_sensitive_data(config_data.copy())

            # 暗号化
            config_json = json.dumps(masked_config, ensure_ascii=False, indent=2)
            encrypted_data = self._encrypt_data(config_json.encode('utf-8'))

            # 出力パスの決定
            if output_path is None:
                output_path = str(config_path_obj.with_suffix('.encrypted'))

            # 暗号化ファイルの書き込み
            with open(output_path, 'wb') as f:
                f.write(encrypted_data)

            logger.info(f"設定ファイルを暗号化しました: {config_path} -> {output_path}")
            return True

        except Exception as e:
            logger.error(f"設定ファイル暗号化エラー: {e}")
            return False

    def decrypt_config_file(self, encrypted_path: str, output_path: Optional[str] = None) -> bool:
        """暗号化設定ファイルを復号化"""
        try:
            encrypted_path_obj = Path(encrypted_path)
            if not encrypted_path_obj.exists():
                logger.error(f"暗号化ファイルが存在しません: {encrypted_path}")
                return False

            # 暗号化ファイルの読み込み
            with open(encrypted_path, 'rb') as f:
                encrypted_data = f.read()

            # 復号化
            decrypted_json = self._decrypt_data(encrypted_data).decode('utf-8')
            config_data = json.loads(decrypted_json)

            # 元の機密データを復元
            restored_config = self._restore_sensitive_data(config_data)

            # 出力パスの決定
            if output_path is None:
                output_path = str(encrypted_path_obj.with_suffix('.json'))

            # 設定ファイルの書き込み
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(restored_config, f, ensure_ascii=False, indent=2)

            logger.info(f"設定ファイルを復号化しました: {encrypted_path} -> {output_path}")
            return True

        except Exception as e:
            logger.error(f"設定ファイル復号化エラー: {e}")
            return False

    def _encrypt_data(self, data: bytes) -> bytes:
        """データを暗号化"""
        # 初期化ベクターの生成
        iv = secrets.token_bytes(12)

        # キーの派生
        key = self._derive_key(self.salt)

        # AES-GCM暗号化の設定
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()

        # データの暗号化
        ciphertext = encryptor.update(data) + encryptor.finalize()

        # 暗号化データをエンコード（salt + iv + tag + ciphertext）
        encrypted_data = (
            self.salt +
            iv +
            encryptor.tag +
            ciphertext
        )

        return base64.b64encode(encrypted_data)

    def _decrypt_data(self, encrypted_data: bytes) -> bytes:
        """データを復号化"""
        try:
            # Base64デコード
            decoded_data = base64.b64decode(encrypted_data)

            # データの分割
            salt = decoded_data[:16]
            iv = decoded_data[16:28]
            tag = decoded_data[28:44]
            ciphertext = decoded_data[44:]

            # キーの派生
            key = self._derive_key(salt)

            # AES-GCM復号化の設定
            cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend())
            decryptor = cipher.decryptor()

            # データの復号化
            return decryptor.update(ciphertext) + decryptor.finalize()

        except Exception as e:
            logger.error(f"データ復号化エラー: {e}")
            raise

    def _mask_sensitive_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """機密データをマスク"""
        sensitive_keys = {
            'password', 'secret', 'key', 'token', 'credential',
            'smtp_password', 'api_key', 'webhook_secret', 'db_password'
        }

        def mask_dict(d: Dict[str, Any]) -> Dict[str, Any]:
            masked = {}
            for key, value in d.items():
                key_lower = key.lower()
                if any(sensitive in key_lower for sensitive in sensitive_keys):
                    if isinstance(value, str):
                        masked[key] = f"***{'*' * max(0, len(value) - 6)}***"
                    else:
                        masked[key] = "***MASKED***"
                elif isinstance(value, dict):
                    masked[key] = mask_dict(value)
                elif isinstance(value, list):
                    masked[key] = [mask_dict(item) if isinstance(item, dict) else item for item in value]
                else:
                    masked[key] = value
            return masked

        return mask_dict(config)

    def _restore_sensitive_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """マスクされた機密データを復元"""
        def restore_dict(d: Dict[str, Any]) -> Dict[str, Any]:
            restored = {}
            for key, value in d.items():
                if key.endswith('_env') and isinstance(value, str):
                    # 環境変数から取得を試みる
                    env_value = os.getenv(value)
                    if env_value:
                        restored[key.replace('_env', '')] = env_value
                elif isinstance(value, dict):
                    restored[key] = restore_dict(value)
                elif isinstance(value, list):
                    restored[key] = [restore_dict(item) if isinstance(item, dict) else item for item in value]
                else:
                    restored[key] = value
            return restored

        return restore_dict(config)

    def create_secure_backup(self, source_path: str, backup_path: str) -> bool:
        """セキュアなバックアップを作成"""
        try:
            source_obj = Path(source_path)
            backup_obj = Path(backup_path)

            if not source_obj.exists():
                logger.error(f"バックアップ元ファイルが存在しません: {source_path}")
                return False

            # バックアップディレクトリの作成
            backup_obj.parent.mkdir(parents=True, exist_ok=True)

            # ファイルのコピー
            import shutil
            shutil.copy2(source_path, backup_path)

            # バックアップファイルの暗号化
            encrypted_backup = backup_path + '.encrypted'
            if self.encrypt_config_file(backup_path, encrypted_backup):
                logger.info(f"セキュアバックアップを作成しました: {backup_path}")
                return True
            else:
                logger.error(f"バックアップの暗号化に失敗しました: {backup_path}")
                return False

        except Exception as e:
            logger.error(f"セキュアバックアップ作成エラー: {e}")
            return False


def encrypt_config_file(config_path: str, key: Optional[str] = None) -> bool:
    """設定ファイルを暗号化（便利関数）"""
    encryptor = ConfigEncryptor(key)
    return encryptor.encrypt_config_file(config_path)


def decrypt_config_file(encrypted_path: str, key: Optional[str] = None) -> bool:
    """設定ファイルを復号化（便利関数）"""
    encryptor = ConfigEncryptor(key)
    return encryptor.decrypt_config_file(encrypted_path)


def create_secure_config_backup(config_path: str, key: Optional[str] = None) -> bool:
    """セキュアな設定バックアップを作成"""
    encryptor = ConfigEncryptor(key)

    # バックアップパスの生成
    config_obj = Path(config_path)
    backup_path = f"{config_path}.backup.{int(time.time())}"

    return encryptor.create_secure_backup(config_path, backup_path)
