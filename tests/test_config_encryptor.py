"""Tests for config_encryptor module."""
import sys
import os
import json
import unittest
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestConfigEncryptorInit(unittest.TestCase):
    def test_init_default(self):
        from config_encryptor import ConfigEncryptor, CRYPTO_AVAILABLE
        if not CRYPTO_AVAILABLE:
            self.skipTest("cryptography not available")
        enc = ConfigEncryptor()
        self.assertIsNotNone(enc)

    def test_mask_sensitive_data(self):
        from config_encryptor import ConfigEncryptor, CRYPTO_AVAILABLE
        if not CRYPTO_AVAILABLE:
            self.skipTest("cryptography not available")
        enc = ConfigEncryptor()
        config = {"password": "secret123", "username": "admin", "other": "value"}
        masked = enc._mask_sensitive_data(config)
        self.assertIsInstance(masked, dict)
        # Sensitive fields should be masked
        self.assertNotEqual(masked.get("password"), "secret123")

    def test_mask_nested(self):
        from config_encryptor import ConfigEncryptor, CRYPTO_AVAILABLE
        if not CRYPTO_AVAILABLE:
            self.skipTest("cryptography not available")
        enc = ConfigEncryptor()
        config = {"db": {"password": "dbpass", "host": "localhost"}}
        masked = enc._mask_sensitive_data(config)
        self.assertNotEqual(masked["db"]["password"], "dbpass")
        self.assertEqual(masked["db"]["host"], "localhost")

    def test_encrypt_decrypt_roundtrip(self):
        from config_encryptor import ConfigEncryptor, CRYPTO_AVAILABLE
        if not CRYPTO_AVAILABLE:
            self.skipTest("cryptography not available")
        enc = ConfigEncryptor()
        data = b"hello world config data"
        encrypted = enc._encrypt_data(data)
        decrypted = enc._decrypt_data(encrypted)
        self.assertEqual(decrypted, data)

    def test_encrypt_produces_different_output(self):
        from config_encryptor import ConfigEncryptor, CRYPTO_AVAILABLE
        if not CRYPTO_AVAILABLE:
            self.skipTest("cryptography not available")
        enc = ConfigEncryptor()
        data = b"test data"
        e1 = enc._encrypt_data(data)
        e2 = enc._encrypt_data(data)
        # AES-GCM uses random IV, so ciphertexts should differ
        self.assertNotEqual(e1, e2)


class TestEncryptDecryptFile(unittest.TestCase):
    def test_encrypt_decrypt_json_file(self):
        from config_encryptor import ConfigEncryptor, CRYPTO_AVAILABLE
        if not CRYPTO_AVAILABLE:
            self.skipTest("cryptography not available")
        with tempfile.TemporaryDirectory() as d:
            enc = ConfigEncryptor(encryption_key="test_key_12345")
            config = {"host": "localhost", "port": 5432, "password": "secret"}
            src = os.path.join(d, "config.json")
            with open(src, 'w') as f:
                json.dump(config, f)
            enc_path = os.path.join(d, "config.enc")
            result = enc.encrypt_config_file(src, enc_path)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(enc_path))

            dec_path = os.path.join(d, "config_dec.json")
            result2 = enc.decrypt_config_file(enc_path, dec_path)
            self.assertTrue(result2)

            with open(dec_path) as f:
                restored = json.load(f)
            self.assertEqual(restored["host"], "localhost")


if __name__ == '__main__':
    unittest.main()
