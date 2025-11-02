# main/blockchain_audit.py
"""
Blockchain Audit System for Cocoa
改ざん耐性のある分散型監査証跡システム
"""

import os
import asyncio
import logging
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import threading
import queue

from web3 import Web3
from web3.eth import Eth
from web3.contract import Contract
import eth_account
from eth_account import Account

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class AuditBlock:
    """監査ブロック"""
    block_index: int
    timestamp: datetime
    previous_hash: str
    current_hash: str
    transactions: List[Dict[str, Any]]
    merkle_root: str
    nonce: int
    difficulty: int
    miner_id: str

@dataclass
class BlockchainAuditEvent:
    """ブロックチェーン監査イベント"""
    event_id: str
    timestamp: datetime
    event_type: str
    user_id: str
    details: Dict[str, Any]
    signature: str
    block_hash: Optional[str] = None
    transaction_hash: Optional[str] = None

@dataclass
class SmartContractConfig:
    """スマートコントラクト設定"""
    contract_address: str
    contract_abi: Dict[str, Any]
    chain_id: int
    gas_limit: int
    gas_price_gwei: int

class BlockchainAuditManager:
    """
    ブロックチェーン監査マネージャー
    改ざん耐性のある分散型監査証跡を提供
    """

    def __init__(self, audit_dir: str = "data/blockchain_audit"):
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        # ブロックチェーン設定
        self.web3_provider = os.getenv("WEB3_PROVIDER_URL", "http://localhost:8545")
        self.web3 = Web3(Web3.HTTPProvider(self.web3_provider))

        # スマートコントラクト
        self.contract_config = None
        self.contract: Optional[Contract] = None

        # ローカルブロックチェーン
        self.blocks: List[AuditBlock] = []
        self.pending_transactions: queue.Queue = queue.Queue()
        self.blockchain_file = self.audit_dir / "audit_blockchain.json"

        # マイニング設定
        self.difficulty = 4  # 簡易的な難易度
        self.block_time_target = 60  # 1分ごとのブロック生成

        # 統計
        self.total_events = 0
        self.total_blocks = 0
        self.verification_failures = 0

        logger.info("Blockchain Audit Manager initialized")

    async def initialize(self):
        """ブロックチェーン監査マネージャーの初期化"""
        await self._load_existing_blockchain()
        await self._initialize_smart_contract()
        await self._start_mining_process()

    async def _load_existing_blockchain(self):
        """既存のブロックチェーンを読み込み"""
        if self.blockchain_file.exists():
            try:
                with open(self.blockchain_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.blocks = [
                        AuditBlock(
                            block_index=block["block_index"],
                            timestamp=datetime.fromisoformat(block["timestamp"]),
                            previous_hash=block["previous_hash"],
                            current_hash=block["current_hash"],
                            transactions=block["transactions"],
                            merkle_root=block["merkle_root"],
                            nonce=block["nonce"],
                            difficulty=block["difficulty"],
                            miner_id=block["miner_id"]
                        )
                        for block in data["blocks"]
                    ]
                    self.total_blocks = len(self.blocks)
                logger.info(f"Loaded {self.total_blocks} audit blocks")
            except Exception as e:
                logger.error(f"Failed to load blockchain: {e}")
                self.blocks = []

        # ジェネシスブロックの作成（ブロックチェーンが空の場合）
        if not self.blocks:
            await self._create_genesis_block()

    async def _create_genesis_block(self):
        """ジェネシスブロックを作成"""
        genesis_block = AuditBlock(
            block_index=0,
            timestamp=datetime.now(),
            previous_hash="0000000000000000000000000000000000000000000000000000000000000000",
            current_hash="",
            transactions=[],
            merkle_root="0000000000000000000000000000000000000000000000000000000000000000",
            nonce=0,
            difficulty=self.difficulty,
            miner_id="system_genesis"
        )

        genesis_block.current_hash = self._calculate_block_hash(genesis_block)
        self.blocks.append(genesis_block)
        self.total_blocks = 1

        await self._save_blockchain()
        logger.info("Genesis block created")

    async def _initialize_smart_contract(self):
        """スマートコントラクトを初期化"""
        # 簡易的なコントラクト設定（実際にはデプロイ済みコントラクトを使用）
        self.contract_config = SmartContractConfig(
            contract_address="0x0000000000000000000000000000000000000000",  # デプロイ後に設定
            contract_abi={},  # 実際のABI
            chain_id=1,  # Ethereum Mainnet
            gas_limit=200000,
            gas_price_gwei=20
        )

        if self.web3.is_connected():
            logger.info(f"Connected to blockchain network: {self.web3_provider}")
        else:
            logger.warning("Blockchain network not available. Using local blockchain only.")

    async def _start_mining_process(self):
        """マイニングプロセスを開始"""
        # バックグラウンドでブロック生成
        while True:
            try:
                if not self.pending_transactions.empty():
                    await self._mine_new_block()

                await asyncio.sleep(30)  # 30秒間隔でチェック

            except Exception as e:
                logger.error(f"Mining process error: {e}")
                await asyncio.sleep(60)

    async def _mine_new_block(self):
        """新しいブロックをマイニング"""
        if self.pending_transactions.empty():
            return

        # 保留中のトランザクションを取得
        transactions = []
        while not self.pending_transactions.empty():
            try:
                transactions.append(self.pending_transactions.get_nowait())
            except queue.Empty:
                break

        if not transactions:
            return

        # 前のブロックを取得
        previous_block = self.blocks[-1] if self.blocks else None

        # Merkle rootを計算
        merkle_root = self._calculate_merkle_root(transactions)

        # ブロックを作成
        new_block = AuditBlock(
            block_index=self.total_blocks,
            timestamp=datetime.now(),
            previous_hash=previous_block.current_hash if previous_block else "",
            current_hash="",
            transactions=transactions,
            merkle_root=merkle_root,
            nonce=0,
            difficulty=self.difficulty,
            miner_id="audit_miner"
        )

        # マイニング（Proof of Work）
        new_block.current_hash, new_block.nonce = await self._mine_block(new_block)

        # ブロックを追加
        self.blocks.append(new_block)
        self.total_blocks += 1

        # ブロックチェーンを保存
        await self._save_blockchain()

        logger.info(f"Mined new audit block: {new_block.block_index} with {len(transactions)} transactions")

    def _calculate_merkle_root(self, transactions: List[Dict[str, Any]]) -> str:
        """Merkle rootを計算"""
        if not transactions:
            return "0000000000000000000000000000000000000000000000000000000000000000"

        # トランザクションをハッシュ化
        tx_hashes = []
        for tx in transactions:
            tx_data = json.dumps(tx, sort_keys=True).encode()
            tx_hash = hashlib.sha256(tx_data).hexdigest()
            tx_hashes.append(tx_hash)

        # Merkle treeを構築
        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 == 1:
                tx_hashes.append(tx_hashes[-1])  # 奇数の場合は最後のハッシュを複製

            new_hashes = []
            for i in range(0, len(tx_hashes), 2):
                combined = tx_hashes[i] + tx_hashes[i + 1]
                new_hash = hashlib.sha256(combined.encode()).hexdigest()
                new_hashes.append(new_hash)

            tx_hashes = new_hashes

        return tx_hashes[0] if tx_hashes else "0000000000000000000000000000000000000000000000000000000000000000"

    def _calculate_block_hash(self, block: AuditBlock) -> str:
        """ブロックハッシュを計算"""
        block_data = {
            "block_index": block.block_index,
            "timestamp": block.timestamp.isoformat(),
            "previous_hash": block.previous_hash,
            "merkle_root": block.merkle_root,
            "nonce": block.nonce,
            "difficulty": block.difficulty
        }

        block_json = json.dumps(block_data, sort_keys=True)
        return hashlib.sha256(block_json.encode()).hexdigest()

    async def _mine_block(self, block: AuditBlock) -> Tuple[str, int]:
        """ブロックをマイニング（Proof of Work）"""
        target = "0" * block.difficulty

        while True:
            block_hash = self._calculate_block_hash(block)
            if block_hash.startswith(target):
                return block_hash, block.nonce

            block.nonce += 1

            # 長時間かかる場合は中断
            if block.nonce > 1000000:
                logger.warning(f"Block mining timeout: {block.block_index}")
                return block_hash, block.nonce

    async def _save_blockchain(self):
        """ブロックチェーンを保存"""
        blockchain_data = {
            "total_blocks": self.total_blocks,
            "difficulty": self.difficulty,
            "block_time_target": self.block_time_target,
            "blocks": [
                {
                    "block_index": block.block_index,
                    "timestamp": block.timestamp.isoformat(),
                    "previous_hash": block.previous_hash,
                    "current_hash": block.current_hash,
                    "transactions": block.transactions,
                    "merkle_root": block.merkle_root,
                    "nonce": block.nonce,
                    "difficulty": block.difficulty,
                    "miner_id": block.miner_id
                }
                for block in self.blocks
            ]
        }

        with open(self.blockchain_file, 'w', encoding='utf-8') as f:
            json.dump(blockchain_data, f, indent=2, ensure_ascii=False)

    async def record_audit_event(self, event: BlockchainAuditEvent) -> bool:
        """
        監査イベントを記録

        Args:
            event: 監査イベント

        Returns:
            記録成功かどうか
        """
        try:
            # イベントをトランザクションとして追加
            transaction = {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "user_id": event.user_id,
                "details": event.details,
                "signature": event.signature,
                "block_hash": event.block_hash,
                "transaction_hash": event.transaction_hash
            }

            self.pending_transactions.put(transaction)
            self.total_events += 1

            # オンチェーン記録（可能な場合）
            if self.contract and self.web3.is_connected():
                await self._record_on_chain(transaction)

            logger.info(f"Audit event recorded: {event.event_id} ({event.event_type})")
            return True

        except Exception as e:
            logger.error(f"Failed to record audit event: {e}")
            return False

    async def _record_on_chain(self, transaction: Dict[str, Any]):
        """オンチェーンにトランザクションを記録"""
        try:
            # スマートコントラクトを呼び出し
            tx_hash = self.contract.functions.recordAuditEvent(
                transaction["event_id"],
                transaction["timestamp"],
                transaction["event_type"],
                transaction["user_id"],
                json.dumps(transaction["details"])
            ).transact({
                "from": self.web3.eth.default_account,
                "gas": self.contract_config.gas_limit,
                "gasPrice": self.web3.to_wei(self.contract_config.gas_price_gwei, 'gwei')
            })

            # トランザクション待機
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            logger.info(f"On-chain audit recorded: {transaction['event_id']}, tx: {tx_hash.hex()}")

        except Exception as e:
            logger.error(f"Failed to record on-chain: {e}")

    async def verify_audit_integrity(self, start_block: int = 0, end_block: Optional[int] = None) -> Dict[str, Any]:
        """
        監査の完全性を検証

        Args:
            start_block: 検証開始ブロック
            end_block: 検証終了ブロック

        Returns:
            検証結果
        """
        if end_block is None:
            end_block = len(self.blocks) - 1

        verification_result = {
            "verified": True,
            "total_blocks": end_block - start_block + 1,
            "invalid_blocks": [],
            "tampering_detected": False,
            "verification_time": datetime.now().isoformat()
        }

        try:
            for i in range(start_block, end_block + 1):
                block = self.blocks[i]

                # ブロックハッシュの検証
                calculated_hash = self._calculate_block_hash(block)
                if calculated_hash != block.current_hash:
                    verification_result["verified"] = False
                    verification_result["invalid_blocks"].append(i)
                    verification_result["tampering_detected"] = True
                    logger.warning(f"Block {i} hash mismatch: expected {block.current_hash}, got {calculated_hash}")

                # 前のブロックとの連鎖性検証
                if i > 0:
                    previous_block = self.blocks[i - 1]
                    if block.previous_hash != previous_block.current_hash:
                        verification_result["verified"] = False
                        verification_result["invalid_blocks"].append(i)
                        verification_result["tampering_detected"] = True
                        logger.warning(f"Block {i} chain broken: previous hash mismatch")

                # Merkle rootの検証
                calculated_merkle = self._calculate_merkle_root(block.transactions)
                if calculated_merkle != block.merkle_root:
                    verification_result["verified"] = False
                    verification_result["invalid_blocks"].append(i)
                    verification_result["tampering_detected"] = True
                    logger.warning(f"Block {i} merkle root mismatch")

            # Proof of Work検証
            if not await self._verify_proof_of_work(start_block, end_block):
                verification_result["verified"] = False
                verification_result["tampering_detected"] = True

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            verification_result["verified"] = False
            verification_result["error"] = str(e)

        verification_result["invalid_blocks_count"] = len(verification_result["invalid_blocks"])
        logger.info(f"Audit integrity verification completed: {verification_result['verified']}")

        return verification_result

    async def _verify_proof_of_work(self, start_block: int, end_block: int) -> bool:
        """Proof of Workを検証"""
        for i in range(start_block, end_block + 1):
            block = self.blocks[i]
            calculated_hash = self._calculate_block_hash(block)

            if not calculated_hash.startswith("0" * block.difficulty):
                logger.warning(f"Block {i} PoW verification failed")
                return False

        return True

    async def get_audit_proof(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        監査証明を取得

        Args:
            event_id: イベントID

        Returns:
            証明データ
        """
        # イベントを検索
        for block in self.blocks:
            for transaction in block.transactions:
                if transaction.get("event_id") == event_id:
                    # 証明を生成
                    proof = {
                        "event_id": event_id,
                        "block_index": block.block_index,
                        "block_hash": block.current_hash,
                        "merkle_proof": await self._generate_merkle_proof(block, transaction),
                        "timestamp": transaction["timestamp"],
                        "verification_status": "verified" if await self._verify_event_inclusion(event_id) else "invalid"
                    }

                    return proof

        return None

    async def _generate_merkle_proof(self, block: AuditBlock, target_transaction: Dict[str, Any]) -> List[str]:
        """Merkle証明を生成"""
        # 簡易的なMerkle証明生成
        proof = []
        tx_hashes = [hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest()
                    for tx in block.transactions]

        target_hash = hashlib.sha256(json.dumps(target_transaction, sort_keys=True).encode()).hexdigest()

        # 証明パスの生成（簡易実装）
        for tx_hash in tx_hashes:
            if tx_hash != target_hash:
                proof.append(tx_hash)

        return proof

    async def _verify_event_inclusion(self, event_id: str) -> bool:
        """イベントの包含性を検証"""
        # ブロックチェーン内のイベントを検証
        for block in self.blocks:
            for transaction in block.transactions:
                if transaction.get("event_id") == event_id:
                    # Merkle証明の検証
                    merkle_root = self._calculate_merkle_root(block.transactions)
                    return merkle_root == block.merkle_root

        return False

    async def create_audit_snapshot(self, description: str = "定期スナップショット") -> str:
        """
        監査スナップショットを作成

        Args:
            description: スナップショット説明

        Returns:
            スナップショットID
        """
        snapshot_id = f"snapshot_{int(datetime.now().timestamp())}"

        snapshot = {
            "snapshot_id": snapshot_id,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "block_count": len(self.blocks),
            "total_events": self.total_events,
            "blockchain_hash": self.blocks[-1].current_hash if self.blocks else "",
            "integrity_verified": (await self.verify_audit_integrity())["verified"]
        }

        # スナップショットを保存
        snapshot_file = self.audit_dir / "snapshots" / f"{snapshot_id}.json"
        snapshot_file.parent.mkdir(parents=True, exist_ok=True)

        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)

        logger.info(f"Audit snapshot created: {snapshot_id}")
        return snapshot_id

    def get_blockchain_status(self) -> Dict[str, Any]:
        """ブロックチェーンステータスを取得"""
        latest_block = self.blocks[-1] if self.blocks else None

        return {
            "total_blocks": self.total_blocks,
            "total_events": self.total_events,
            "pending_transactions": self.pending_transactions.qsize(),
            "web3_connected": self.web3.is_connected() if self.web3 else False,
            "smart_contract_deployed": self.contract is not None,
            "difficulty": self.difficulty,
            "block_time_target": self.block_time_target,
            "verification_failures": self.verification_failures,
            "latest_block": {
                "block_index": latest_block.block_index,
                "timestamp": latest_block.timestamp.isoformat(),
                "hash": latest_block.current_hash,
                "transactions": len(latest_block.transactions)
            } if latest_block else None,
            "chain_valid": (len(self.blocks) == 0 or all(
                self.blocks[i].current_hash == self._calculate_block_hash(self.blocks[i])
                for i in range(len(self.blocks))
            ))
        }

# グローバルインスタンス
_blockchain_audit_manager = None

async def get_blockchain_audit_manager() -> BlockchainAuditManager:
    """ブロックチェーン監査マネージャーのインスタンスを取得"""
    global _blockchain_audit_manager

    if _blockchain_audit_manager is None:
        _blockchain_audit_manager = BlockchainAuditManager()
        await _blockchain_audit_manager.initialize()

    return _blockchain_audit_manager
