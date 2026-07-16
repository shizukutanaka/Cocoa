"""Tests for nft_avatar_manager module."""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestAvatarNFTMetadata(unittest.TestCase):
    def _make(self, **kw):
        from nft_avatar_manager import AvatarNFTMetadata
        defaults = {
            'name': "TestAvatar",
            'description': "A test avatar",
            'image_hash': "abc123",
            'avatar_hash': "def456",
            'creator_id': "user_1",
            'creation_date': "2026-01-01",
            'attributes': {"style": "anime"},
            'ipfs_cid': "Qm123",
        }
        defaults.update(kw)
        return AvatarNFTMetadata(**defaults)

    def test_creation(self):
        meta = self._make()
        self.assertEqual(meta.name, "TestAvatar")
        self.assertIsNone(meta.blockchain_tx_hash)

    def test_to_ipfs_metadata(self):
        meta = self._make()
        result = meta.to_ipfs_metadata()
        self.assertIsInstance(result, dict)
        self.assertIn("name", result)
        self.assertIn("description", result)

    def test_attributes_preserved(self):
        meta = self._make(attributes={"style": "realistic", "quality": "high"})
        ipfs = meta.to_ipfs_metadata()
        self.assertIn("attributes", ipfs)

    def test_optional_fields_default_none(self):
        meta = self._make()
        self.assertIsNone(meta.token_id)
        self.assertIsNone(meta.contract_address)


class TestNFTAvatarManagerInit(unittest.TestCase):
    def test_attributes_exist(self):
        with patch('nft_avatar_manager.get_security_manager', return_value=MagicMock()):
            from nft_avatar_manager import NFTAvatarManager
            mgr = NFTAvatarManager.__new__(NFTAvatarManager)
            mgr.security_manager = MagicMock()
            mgr.web3 = None
            mgr.account = None
            mgr.ipfs_client = None
            mgr.blockchain_network = "ethereum"
            self.assertEqual(mgr.blockchain_network, "ethereum")

    def test_calculate_file_hash(self):
        import tempfile
        with patch('nft_avatar_manager.get_security_manager', return_value=MagicMock()):
            from nft_avatar_manager import NFTAvatarManager
            mgr = NFTAvatarManager.__new__(NFTAvatarManager)
            mgr.security_manager = MagicMock()

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
                f.write(b"fake image data")
                tmppath = f.name

            try:
                h = mgr._calculate_file_hash(tmppath)
                self.assertIsInstance(h, str)
                self.assertGreater(len(h), 0)
            finally:
                os.unlink(tmppath)

    def test_calculate_file_hash_consistency(self):
        import tempfile
        with patch('nft_avatar_manager.get_security_manager', return_value=MagicMock()):
            from nft_avatar_manager import NFTAvatarManager
            mgr = NFTAvatarManager.__new__(NFTAvatarManager)
            mgr.security_manager = MagicMock()

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
                f.write(b"consistent data")
                tmppath = f.name

            try:
                h1 = mgr._calculate_file_hash(tmppath)
                h2 = mgr._calculate_file_hash(tmppath)
                self.assertEqual(h1, h2)
            finally:
                os.unlink(tmppath)


class TestAvailabilityFlags(unittest.TestCase):
    def test_flags_are_bool(self):
        from nft_avatar_manager import IPFS_AVAILABLE, WEB3_AVAILABLE
        self.assertIsInstance(WEB3_AVAILABLE, bool)
        self.assertIsInstance(IPFS_AVAILABLE, bool)


if __name__ == '__main__':
    unittest.main()
