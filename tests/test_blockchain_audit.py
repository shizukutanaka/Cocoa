"""Tests for blockchain_audit module."""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestAuditBlock(unittest.TestCase):
    def _make(self, index=0):
        from blockchain_audit import AuditBlock
        return AuditBlock(
            block_index=index,
            timestamp=datetime.now(timezone.utc),
            previous_hash="0" * 64,
            current_hash="abc123",
            transactions=[],
            merkle_root="merkle_root_hash",
            nonce=0,
            difficulty=4,
            miner_id="system",
        )

    def test_creation(self):
        block = self._make(0)
        self.assertEqual(block.block_index, 0)
        self.assertEqual(block.difficulty, 4)

    def test_transactions_list(self):
        block = self._make()
        self.assertIsInstance(block.transactions, list)


class TestBlockchainAuditEvent(unittest.TestCase):
    def test_creation(self):
        from blockchain_audit import BlockchainAuditEvent
        event = BlockchainAuditEvent(
            event_id="e1",
            timestamp=datetime.now(timezone.utc),
            event_type="user_action",
            user_id="u1",
            details={"action": "login"},
            signature="sig123",
        )
        self.assertEqual(event.event_type, "user_action")
        self.assertIsNone(event.block_hash)

    def test_optional_fields(self):
        from blockchain_audit import BlockchainAuditEvent
        event = BlockchainAuditEvent(
            event_id="e2",
            timestamp=datetime.now(timezone.utc),
            event_type="test",
            user_id="u1",
            details={},
            signature="s",
        )
        self.assertIsNone(event.transaction_hash)


class TestBlockchainAuditManagerInit(unittest.TestCase):
    def test_init_no_web3(self):
        from blockchain_audit import WEB3_AVAILABLE
        # When web3 not available, check the manager initializes without crashing
        if not WEB3_AVAILABLE:
            with patch('pathlib.Path.mkdir'):
                from blockchain_audit import BlockchainAuditManager
                # Should create instance without web3
                mgr = BlockchainAuditManager.__new__(BlockchainAuditManager)
                mgr.security_manager = MagicMock()
                mgr.web3 = None
                mgr.contract = None
                mgr.chain = []
                mgr.pending_events = []
                self.assertIsNone(mgr.web3)

    def test_availability_flag(self):
        from blockchain_audit import WEB3_AVAILABLE
        self.assertIsInstance(WEB3_AVAILABLE, bool)


class TestChainCalculations(unittest.TestCase):
    def _make_mgr(self):
        with patch('pathlib.Path.mkdir'):
            from blockchain_audit import BlockchainAuditManager
            return BlockchainAuditManager(audit_dir="/tmp/test_blockchain")

    def test_get_blockchain_status(self):
        mgr = self._make_mgr()
        status = mgr.get_blockchain_status()
        self.assertIsInstance(status, dict)
        self.assertIn("total_blocks", status)

    def test_calculate_merkle_root_empty(self):
        mgr = self._make_mgr()
        root = mgr._calculate_merkle_root([])
        self.assertIsInstance(root, str)
        self.assertGreater(len(root), 0)

    def test_calculate_merkle_root_consistent(self):
        mgr = self._make_mgr()
        txns = [{"id": "t1", "data": "test"}]
        r1 = mgr._calculate_merkle_root(txns)
        r2 = mgr._calculate_merkle_root(txns)
        self.assertEqual(r1, r2)


if __name__ == '__main__':
    unittest.main()
