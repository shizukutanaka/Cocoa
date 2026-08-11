"""DataEncryptor の鍵選択・復号失敗伝播、および PBKDF2→Scrypt 移行の回帰テスト。

いずれも 2026-08-11 の監査で実際に再現した不具合に対応する:

1. `DataEncryptor(key)` に明示指定した鍵より環境変数
   `OTEDAMA_ENCRYPTION_KEY` が優先されていた（環境変数は fallback であるべき）。
   結果、env var のある環境と無い環境で導出鍵が変わり復号に失敗していた。
2. `decrypt_data()` が復号失敗時に `{}` を返していたため、AES-GCM の
   認証失敗（改竄・鍵違い）が「空データ」と区別できなかった。
3. `EncryptionMigrationHelper.migrate_from_pbkdf2()` が存在しない
   `DataEncryptor.decrypt()` を呼んでおり、必ず AttributeError で落ちていた。
"""

import base64
import json
import os
import unittest

from main.enhanced_encryption import (
    EncryptionMigrationHelper,
    EnhancedDataEncryptor,
    SecurityLevel,
)
from main.integrated_security import DataEncryptor

ENV_VAR = "OTEDAMA_ENCRYPTION_KEY"
SAMPLE = {"a": 1, "b": "テスト", "nested": {"x": [1, 2, 3]}}


class _EnvGuard:
    """テスト中だけ ENV_VAR を差し替え、終了時に元へ戻す。"""

    def __init__(self, value):
        self.value = value
        self._prev = None
        self._had = False

    def __enter__(self):
        self._had = ENV_VAR in os.environ
        self._prev = os.environ.get(ENV_VAR)
        if self.value is None:
            os.environ.pop(ENV_VAR, None)
        else:
            os.environ[ENV_VAR] = self.value
        return self

    def __exit__(self, *exc):
        if self._had:
            os.environ[ENV_VAR] = self._prev
        else:
            os.environ.pop(ENV_VAR, None)
        return False


class TestExplicitKeyBeatsEnvVar(unittest.TestCase):
    def test_explicit_key_survives_env_var_change(self):
        """明示鍵で暗号化したデータは env var の有無に関わらず復号できる。"""
        with _EnvGuard("env-key-must-be-fallback-only-000000"):
            blob = DataEncryptor("explicit-password").encrypt_data(SAMPLE)
        with _EnvGuard(None):
            self.assertEqual(
                DataEncryptor("explicit-password").decrypt_data(blob), SAMPLE
            )

    def test_env_var_used_only_when_no_explicit_key(self):
        """明示鍵が無い場合のみ env var が既定鍵として使われる。"""
        with _EnvGuard("shared-env-key-for-both-instances-01"):
            blob = DataEncryptor().encrypt_data(SAMPLE)
            self.assertEqual(DataEncryptor().decrypt_data(blob), SAMPLE)


class TestDecryptFailurePropagates(unittest.TestCase):
    def test_tampered_ciphertext_raises(self):
        """GCM 認証失敗は握り潰さず例外を送出する（空 dict を返さない）。"""
        enc = DataEncryptor("explicit-password")
        raw = bytearray(base64.b64decode(enc.encrypt_data(SAMPLE)))
        raw[-1] ^= 0x01
        with self.assertRaises(Exception):
            enc.decrypt_data(base64.b64encode(bytes(raw)).decode("ascii"))

    def test_wrong_key_raises(self):
        blob = DataEncryptor("password-one-abc").encrypt_data(SAMPLE)
        with self.assertRaises(Exception):
            DataEncryptor("password-two-xyz").decrypt_data(blob)

    def test_empty_payload_is_distinguishable_from_failure(self):
        """空 dict を暗号化したものは正常に空 dict として復号できる。"""
        enc = DataEncryptor("explicit-password")
        self.assertEqual(enc.decrypt_data(enc.encrypt_data({})), {})


class TestPbkdf2ToScryptMigration(unittest.TestCase):
    def test_migration_roundtrip(self):
        """移行後のデータが Scrypt 側で元の内容へ復号できる。"""
        pbkdf2_pw = "explicit-password"
        scrypt_pw = "NewStrongPw123!"
        blob = DataEncryptor(pbkdf2_pw).encrypt_data(SAMPLE)

        migrated = EncryptionMigrationHelper.migrate_from_pbkdf2(
            blob.encode("ascii"), pbkdf2_pw, scrypt_pw, SecurityLevel.BALANCED
        )
        out = EnhancedDataEncryptor(scrypt_pw, SecurityLevel.BALANCED).decrypt(migrated)
        self.assertEqual(json.loads(out.decode("utf-8")), SAMPLE)

    def test_migration_accepts_str_payload(self):
        """base64 文字列をそのまま渡しても移行できる。"""
        pbkdf2_pw = "explicit-password"
        scrypt_pw = "NewStrongPw123!"
        blob = DataEncryptor(pbkdf2_pw).encrypt_data(SAMPLE)

        migrated = EncryptionMigrationHelper.migrate_from_pbkdf2(
            blob, pbkdf2_pw, scrypt_pw, SecurityLevel.BALANCED
        )
        out = EnhancedDataEncryptor(scrypt_pw, SecurityLevel.BALANCED).decrypt(migrated)
        self.assertEqual(json.loads(out.decode("utf-8")), SAMPLE)

    def test_migration_with_wrong_pbkdf2_password_raises(self):
        blob = DataEncryptor("password-one-abc").encrypt_data(SAMPLE)
        with self.assertRaises(Exception):
            EncryptionMigrationHelper.migrate_from_pbkdf2(
                blob.encode("ascii"),
                "password-two-xyz",
                "NewStrongPw123!",
                SecurityLevel.BALANCED,
            )


if __name__ == "__main__":
    unittest.main()
