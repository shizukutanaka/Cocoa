#!/usr/bin/env python3
"""
Enhanced Encryption System with Scrypt Key Derivation
Scryptベースの強化暗号化システム

参考: Stack Overflow - "Use scrypt instead of PBKDF2"
理由: 計算集約的かつメモリ集約的でASIC攻撃に強い
"""

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from dataclasses import dataclass
from enum import Enum
import secrets
import logging

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """セキュリティレベル"""
    BALANCED = "balanced"      # 一般用途: N=2^14
    HIGH = "high"              # 機密データ: N=2^16
    CRITICAL = "critical"      # 最重要データ: N=2^20


@dataclass
class ScryptParams:
    """Scryptパラメータ"""
    n: int  # CPU/メモリコスト (2の累乗)
    r: int  # ブロックサイズ
    p: int  # 並列化パラメータ

    @property
    def memory_cost_kb(self) -> int:
        """メモリコスト(KB)を計算"""
        return 128 * self.n * self.r // 1024


class ScryptConfig:
    """Scrypt設定データベース"""

    # セキュリティレベル別パラメータ
    PARAMS = {
        SecurityLevel.BALANCED: ScryptParams(
            n=2**14,  # 16,384 iterations
            r=8,
            p=1
        ),
        SecurityLevel.HIGH: ScryptParams(
            n=2**16,  # 65,536 iterations
            r=8,
            p=1
        ),
        SecurityLevel.CRITICAL: ScryptParams(
            n=2**20,  # 1,048,576 iterations (重要システム向け)
            r=8,
            p=1
        )
    }

    # 推奨最小値
    MIN_PASSWORD_LENGTH = 12
    SALT_LENGTH = 32  # 256 bits
    NONCE_LENGTH = 12  # 96 bits (GCM推奨)
    KEY_LENGTH = 32   # 256 bits

    @classmethod
    def get_params(cls, level: SecurityLevel) -> ScryptParams:
        """セキュリティレベルからパラメータ取得"""
        return cls.PARAMS[level]


class EnhancedDataEncryptor:
    """Scryptベースの強化暗号化システム"""

    def __init__(
        self,
        password: str,
        security_level: SecurityLevel = SecurityLevel.BALANCED
    ):
        """
        初期化

        Args:
            password: マスターパスワード
            security_level: セキュリティレベル
        """
        if len(password) < ScryptConfig.MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Password must be at least {ScryptConfig.MIN_PASSWORD_LENGTH} characters"
            )

        self.password = password.encode('utf-8')
        self.security_level = security_level
        self.params = ScryptConfig.get_params(security_level)

        logger.info(
            f"Initialized EnhancedDataEncryptor with {security_level.value} security "
            f"(N={self.params.n}, memory~{self.params.memory_cost_kb}KB)"
        )

    def derive_key(self, salt: bytes) -> bytes:
        """
        Scryptで鍵導出

        Args:
            salt: ソルト (32 bytes)

        Returns:
            導出された鍵 (32 bytes)
        """
        kdf = Scrypt(
            salt=salt,
            length=ScryptConfig.KEY_LENGTH,
            n=self.params.n,
            r=self.params.r,
            p=self.params.p,
            backend=default_backend()
        )

        try:
            return kdf.derive(self.password)
        except Exception as e:
            logger.error(f"Key derivation failed: {e}")
            raise

    def encrypt(self, plaintext: bytes) -> bytes:
        """
        データを暗号化

        データ構造: salt (32) + nonce (12) + ciphertext (variable) + tag (16)

        Args:
            plaintext: 平文データ

        Returns:
            暗号化データ
        """
        try:
            # ランダムsaltとnonce生成（暗号学的に安全）
            salt = secrets.token_bytes(ScryptConfig.SALT_LENGTH)
            nonce = secrets.token_bytes(ScryptConfig.NONCE_LENGTH)

            # Scryptで鍵導出
            key = self.derive_key(salt)

            # AES-256-GCMで暗号化
            aesgcm = AESGCM(key)
            ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)

            # 結合: salt + nonce + ciphertext + tag
            encrypted_data = salt + nonce + ciphertext_with_tag

            logger.debug(
                f"Encrypted {len(plaintext)} bytes to {len(encrypted_data)} bytes "
                f"(overhead: {len(encrypted_data) - len(plaintext)} bytes)"
            )

            return encrypted_data

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(self, encrypted_data: bytes) -> bytes:
        """
        データを復号化

        Args:
            encrypted_data: 暗号化データ

        Returns:
            復号化された平文
        """
        try:
            # データ構造の検証
            min_length = (
                ScryptConfig.SALT_LENGTH +
                ScryptConfig.NONCE_LENGTH +
                16  # 最小ciphertext + tag
            )

            if len(encrypted_data) < min_length:
                raise ValueError(
                    f"Encrypted data too short: {len(encrypted_data)} bytes "
                    f"(minimum: {min_length})"
                )

            # 分解: salt + nonce + ciphertext + tag
            salt = encrypted_data[:ScryptConfig.SALT_LENGTH]
            nonce = encrypted_data[
                ScryptConfig.SALT_LENGTH:
                ScryptConfig.SALT_LENGTH + ScryptConfig.NONCE_LENGTH
            ]
            ciphertext_with_tag = encrypted_data[
                ScryptConfig.SALT_LENGTH + ScryptConfig.NONCE_LENGTH:
            ]

            # Scryptで鍵導出
            key = self.derive_key(salt)

            # AES-256-GCMで復号化（認証タグ検証含む）
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext_with_tag, None)

            logger.debug(
                f"Decrypted {len(encrypted_data)} bytes to {len(plaintext)} bytes"
            )

            return plaintext

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise

    def encrypt_string(self, plaintext: str) -> bytes:
        """文字列を暗号化"""
        return self.encrypt(plaintext.encode('utf-8'))

    def decrypt_string(self, encrypted_data: bytes) -> str:
        """暗号化文字列を復号化"""
        return self.decrypt(encrypted_data).decode('utf-8')

    def change_security_level(self, new_level: SecurityLevel):
        """
        セキュリティレベルを変更

        注意: 既存の暗号化データは再暗号化が必要
        """
        old_level = self.security_level
        self.security_level = new_level
        self.params = ScryptConfig.get_params(new_level)

        logger.warning(
            f"Security level changed from {old_level.value} to {new_level.value}. "
            "Existing encrypted data must be re-encrypted."
        )


class EncryptionMigrationHelper:
    """PBKDF2からScryptへの移行ヘルパー"""

    @staticmethod
    def detect_encryption_type(encrypted_data: bytes) -> str:
        """
        暗号化タイプを検出

        Returns:
            'scrypt' or 'pbkdf2' or 'unknown'
        """
        # データサイズでヒューリスティック判定
        # Scrypt: salt(32) + nonce(12) + ciphertext + tag(16) = 最小60バイト
        # PBKDF2: 異なる構造

        if len(encrypted_data) < 60:
            return 'unknown'

        # より正確には、バージョンヘッダーを追加すべき
        # 今回は簡易的にサイズで判定
        return 'scrypt'

    @staticmethod
    def migrate_from_pbkdf2(
        pbkdf2_encrypted_data: bytes,
        pbkdf2_password: str,
        scrypt_password: str,
        security_level: SecurityLevel = SecurityLevel.BALANCED
    ) -> bytes:
        """
        PBKDF2暗号化データをScrypt暗号化に移行

        Args:
            pbkdf2_encrypted_data: PBKDF2で暗号化されたデータ
            pbkdf2_password: PBKDF2のパスワード
            scrypt_password: Scryptの新パスワード
            security_level: 新しいセキュリティレベル

        Returns:
            Scryptで再暗号化されたデータ
        """
        try:
            # PBKDF2で復号化（既存のDataEncryptorを使用）
            from .integrated_security import DataEncryptor

            pbkdf2_encryptor = DataEncryptor(pbkdf2_password)
            plaintext = pbkdf2_encryptor.decrypt(pbkdf2_encrypted_data)

            # Scryptで再暗号化
            scrypt_encryptor = EnhancedDataEncryptor(
                scrypt_password,
                security_level
            )
            scrypt_encrypted_data = scrypt_encryptor.encrypt(plaintext)

            logger.info("Successfully migrated encryption from PBKDF2 to Scrypt")

            return scrypt_encrypted_data

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise


def benchmark_scrypt_params():
    """Scryptパラメータのベンチマーク"""
    import time

    password = "TestPassword123!@#"
    salt = secrets.token_bytes(32)

    print("Scrypt Parameter Benchmark")
    print("=" * 60)

    for level in SecurityLevel:
        params = ScryptConfig.get_params(level)

        start_time = time.time()

        kdf = Scrypt(
            salt=salt,
            length=32,
            n=params.n,
            r=params.r,
            p=params.p,
            backend=default_backend()
        )
        kdf.derive(password.encode())

        elapsed = time.time() - start_time

        print(f"\n{level.value.upper()}:")
        print(f"  N: {params.n:,}")
        print(f"  Memory: ~{params.memory_cost_kb:,} KB")
        print(f"  Time: {elapsed:.3f} seconds")


def main():
    """テスト実行"""
    print("Enhanced Encryption System - Scrypt Key Derivation\n")

    # ベンチマーク
    print("Running benchmark...\n")
    benchmark_scrypt_params()

    print("\n" + "=" * 60)
    print("Encryption Test\n")

    # 暗号化テスト
    password = "MySecurePassword123!@#"
    encryptor = EnhancedDataEncryptor(
        password,
        security_level=SecurityLevel.BALANCED
    )

    # テストデータ
    test_data = "This is highly sensitive data that needs strong encryption."
    print(f"Original: {test_data}")

    # 暗号化
    encrypted = encryptor.encrypt_string(test_data)
    print(f"Encrypted: {len(encrypted)} bytes")
    print(f"Hex preview: {encrypted[:40].hex()}...")

    # 復号化
    decrypted = encryptor.decrypt_string(encrypted)
    print(f"Decrypted: {decrypted}")

    # 検証
    assert test_data == decrypted, "Decryption verification failed!"
    print("\n✓ Encryption/Decryption test passed!")

    # セキュリティレベル比較
    print("\n" + "=" * 60)
    print("Security Level Comparison\n")

    for level in SecurityLevel:
        enc = EnhancedDataEncryptor("Password123!@#", level)
        params = enc.params
        print(f"{level.value.upper()}:")
        print(f"  Iterations: {params.n:,}")
        print(f"  Memory: ~{params.memory_cost_kb:,} KB")
        print("  Recommended for: ", end="")

        if level == SecurityLevel.BALANCED:
            print("General use, good balance of security and performance")
        elif level == SecurityLevel.HIGH:
            print("Sensitive data, higher security requirements")
        else:
            print("Critical systems, maximum security (slower)")
        print()


if __name__ == "__main__":
    main()
