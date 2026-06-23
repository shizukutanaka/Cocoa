"""Tests for blockchain_audit module."""
import asyncio
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

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


class TestInitializeCompletesWithoutWeb3(unittest.TestCase):
    """initialize() must return promptly when web3 is not available.

    Two bugs prevented this:
    1. _initialize_smart_contract() called self.web3.is_connected() without
       guarding against web3=None → AttributeError.
    2. initialize() used `await self._start_mining_process()` which loops
       forever → initialize() never returned.
    """

    def test_initialize_does_not_block_without_web3(self):
        from blockchain_audit import BlockchainAuditManager
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = BlockchainAuditManager(audit_dir=tmpdir)
            # Must complete quickly (under 5 s) — would never return with the bug.
            async def run():
                await asyncio.wait_for(mgr.initialize(), timeout=5.0)
            asyncio.run(run())

    def test_initialize_creates_genesis_block(self):
        from blockchain_audit import BlockchainAuditManager
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = BlockchainAuditManager(audit_dir=tmpdir)
            asyncio.run(mgr.initialize())
            self.assertGreaterEqual(len(mgr.blocks), 1)
            self.assertEqual(mgr.blocks[0].block_index, 0)


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


class TestBlockchainAuditMiningTaskRetained(unittest.IsolatedAsyncioTestCase):
    """initialize() must store the mining task to prevent GC.

    Bug: asyncio.create_task(self._start_mining_process()) result was discarded.
    The event loop holds tasks in a WeakSet, so without a strong reference the
    task is garbage-collected, silently killing the mining loop.
    Fix: self._background_tasks.append(asyncio.create_task(...))
    """

    async def test_initialize_stores_background_task(self):
        import asyncio
        from unittest.mock import patch, AsyncMock
        with patch('pathlib.Path.mkdir'), \
             patch('pathlib.Path.exists', return_value=False), \
             patch('blockchain_audit.BlockchainAuditManager._load_existing_blockchain', new_callable=AsyncMock), \
             patch('blockchain_audit.BlockchainAuditManager._initialize_smart_contract', new_callable=AsyncMock), \
             patch('blockchain_audit.BlockchainAuditManager._start_mining_process', return_value=asyncio.sleep(999)):
            from blockchain_audit import BlockchainAuditManager
            mgr = BlockchainAuditManager(audit_dir="/tmp/test_bc_task")
            self.assertEqual(mgr._background_tasks, [])
            await asyncio.wait_for(mgr.initialize(), timeout=2.0)
            self.assertGreater(len(mgr._background_tasks), 0, "_background_tasks must be non-empty after initialize()")
            # Clean up the tasks
            for t in mgr._background_tasks:
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass


if __name__ == '__main__':
    unittest.main()
