"""Tests for enhanced_encryption module."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestSecurityLevel(unittest.TestCase):
    def test_values(self):
        from enhanced_encryption import SecurityLevel, CRYPTO_AVAILABLE
        if not CRYPTO_AVAILABLE:
            self.skipTest("cryptography not available")
        self.assertIsNotNone(SecurityLevel.STANDARD)
        self.assertIsNotNone(SecurityLevel.HIGH)


class TestScryptParams(unittest.TestCase):
    def test_defaults(self):
        from enhanced_encryption import ScryptParams, CRYPTO_AVAILABLE
        if not CRYPTO_AVAILABLE:
            self.skipTest("cryptography not available")
        params = ScryptParams()
        self.assertIsInstance(params.n, int)
        self.assertGreater(params.n, 0)

    def test_custom(self):
        from enhanced_encryption import ScryptParams, CRYPTO_AVAILABLE
        if not CRYPTO_AVAILABLE:
            self.skipTest("cryptography not available")
        params = ScryptParams(n=16384, r=8, p=1)
        self.assertEqual(params.n, 16384)


class TestEnhancedDataEncryptor(unittest.TestCase):
    def test_init(self):
        from enhanced_encryption import EnhancedDataEncryptor, CRYPTO_AVAILABLE
        if not CRYPTO_AVAILABLE:
            self.skipTest("cryptography not available")
        enc = EnhancedDataEncryptor()
        self.assertIsNotNone(enc)

    def test_encrypt_decrypt_roundtrip(self):
        from enhanced_encryption import EnhancedDataEncryptor, CRYPTO_AVAILABLE
        if not CRYPTO_AVAILABLE:
            self.skipTest("cryptography not available")
        enc = EnhancedDataEncryptor()
        data = b"test secret data"
        password = "strong_password"
        encrypted = enc.encrypt(data, password)
        self.assertIsInstance(encrypted, bytes)
        decrypted = enc.decrypt(encrypted, password)
        self.assertEqual(decrypted, data)

    def test_wrong_password_fails(self):
        from enhanced_encryption import EnhancedDataEncryptor, CRYPTO_AVAILABLE
        if not CRYPTO_AVAILABLE:
            self.skipTest("cryptography not available")
        enc = EnhancedDataEncryptor()
        data = b"secret"
        encrypted = enc.encrypt(data, "correct_password")
        with self.assertRaises(Exception):
            enc.decrypt(encrypted, "wrong_password")


if __name__ == '__main__':
    unittest.main()
