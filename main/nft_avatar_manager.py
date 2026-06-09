"""
NFT-Enhanced Avatar Management System for Cocoa
ブロックチェーンとNFTを活用したアバター真正性証明システム
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
import hashlib

try:
    from web3 import Web3
    from eth_account import Account
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    Web3 = None
    Account = None

try:
    import ipfshttpclient
    IPFS_AVAILABLE = True
except ImportError:
    IPFS_AVAILABLE = False
    ipfshttpclient = None

from integrated_security import get_security_manager

logger = logging.getLogger(__name__)

@dataclass
class AvatarNFTMetadata:
    """アバターNFTのメタデータ"""
    name: str
    description: str
    image_hash: str
    avatar_hash: str
    creator_id: str
    creation_date: str
    attributes: Dict[str, Any]
    ipfs_cid: str
    blockchain_tx_hash: Optional[str] = None
    token_id: Optional[str] = None
    contract_address: Optional[str] = None

    def to_ipfs_metadata(self) -> Dict:
        """IPFSメタデータフォーマットに変換"""
        return {
            "name": self.name,
            "description": self.description,
            "image": f"ipfs://{self.ipfs_cid}",
            "attributes": [
                {"trait_type": key, "value": value}
                for key, value in self.attributes.items()
            ],
            "external_url": f"https://cocoa-avatar.com/avatar/{self.avatar_hash}",
            "background_color": "000000"
        }

class NFTAvatarManager:
    """
    NFT統合アバター管理システム
    ブロックチェーンによる真正性証明とメタバース対応
    """

    def __init__(self):
        self.security_manager = get_security_manager()
        self.web3 = None
        self.account = None
        self.ipfs_client = None

        # 設定
        self.blockchain_network = os.getenv("BLOCKCHAIN_NETWORK", "polygon")
        self.contract_address = os.getenv("AVATAR_NFT_CONTRACT_ADDRESS")
        self.ipfs_gateway = os.getenv("IPFS_GATEWAY", "https://gateway.pinata.cloud/ipfs/")

        # データディレクトリ
        self.nft_data_dir = Path("data/nft_avatars")
        self.nft_data_dir.mkdir(parents=True, exist_ok=True)

        # ネットワーク設定
        self.network_configs = {
            "ethereum": {
                "rpc_url": "https://mainnet.infura.io/v3/YOUR_INFURA_KEY",
                "chain_id": 1,
                "currency": "ETH"
            },
            "polygon": {
                "rpc_url": "https://polygon-rpc.com",
                "chain_id": 137,
                "currency": "MATIC"
            },
            "bsc": {
                "rpc_url": "https://bsc-dataseed.binance.org",
                "chain_id": 56,
                "currency": "BNB"
            }
        }

        logger.info("NFT Avatar Manager initialized")

    async def initialize_blockchain(self):
        """ブロックチェーン接続を初期化"""
        try:
            network_config = self.network_configs.get(self.blockchain_network)
            if not network_config:
                raise ValueError(f"Unsupported blockchain network: {self.blockchain_network}")

            if not WEB3_AVAILABLE:
                raise RuntimeError("web3 not installed")
            # Web3インスタンス作成
            self.web3 = Web3(Web3.HTTPProvider(network_config["rpc_url"]))

            if not self.web3.is_connected():
                raise ConnectionError("Failed to connect to blockchain network")

            # アカウント初期化（環境変数から秘密鍵を読み込み）
            private_key = os.getenv("BLOCKCHAIN_PRIVATE_KEY")
            if private_key:
                self.account = Account.from_key(private_key)

            # IPFSクライアント初期化
            if IPFS_AVAILABLE:
                self.ipfs_client = ipfshttpclient.connect('/ip4/127.0.0.1/tcp/5001/http')

            logger.info(f"Blockchain initialized: {self.blockchain_network}")

        except Exception as e:
            logger.error(f"Failed to initialize blockchain: {e}")
            raise

    async def mint_avatar_nft(
        self,
        user_id: str,
        avatar_path: str,
        metadata: Dict,
        recipient_address: Optional[str] = None
    ) -> Optional[str]:
        """
        アバターをNFTとしてミント

        Args:
            user_id: ユーザーID
            avatar_path: アバター画像パス
            metadata: アバターのメタデータ
            recipient_address: 受信者アドレス（指定なしの場合ユーザーアドレス）

        Returns:
            トランザクションハッシュ
        """
        try:
            # セキュリティチェック
            if not await self.security_manager.validate_user_access(user_id, "nft_mint"):
                raise ValueError("Unauthorized NFT minting")

            # アバター画像のハッシュを計算
            avatar_hash = self._calculate_file_hash(avatar_path)

            # 画像をIPFSにアップロード
            ipfs_cid = await self._upload_to_ipfs(avatar_path)

            # NFTメタデータを作成
            nft_metadata = AvatarNFTMetadata(
                name=f"Cocoa Avatar #{avatar_hash[:8]}",
                description=f"AI-generated avatar created by Cocoa system for user {user_id}",
                image_hash=avatar_hash,
                avatar_hash=avatar_hash,
                creator_id=user_id,
                creation_date=datetime.now(timezone.utc).isoformat(),
                attributes=metadata,
                ipfs_cid=ipfs_cid,
                contract_address=self.contract_address
            )

            # IPFSメタデータをアップロード
            metadata_cid = await self._upload_metadata_to_ipfs(nft_metadata)

            # ブロックチェーンにミント（実際のコントラクト呼び出し）
            tx_hash = await self._mint_on_blockchain(
                nft_metadata, metadata_cid, recipient_address
            )

            if tx_hash:
                # データベースに記録
                await self._record_nft_mint(user_id, nft_metadata, tx_hash)

                logger.info(f"Avatar NFT minted successfully: {tx_hash}")

            return tx_hash

        except Exception as e:
            logger.error(f"Failed to mint avatar NFT: {e}")
            return None

    def _calculate_file_hash(self, file_path: str) -> str:
        """ファイルのSHA-256ハッシュを計算"""
        hash_sha256 = hashlib.sha256()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)

        return hash_sha256.hexdigest()

    async def _upload_to_ipfs(self, file_path: str) -> str:
        """ファイルをIPFSにアップロード"""
        try:
            if not self.ipfs_client:
                await self.initialize_blockchain()

            with open(file_path, 'rb') as f:
                # IPFSにファイルを追加
                result = self.ipfs_client.add(f.read())

                if isinstance(result, dict) and 'Hash' in result:
                    return result['Hash']
                elif isinstance(result, list) and len(result) > 0:
                    return result[0]['Hash']

                raise ValueError("Failed to get IPFS hash from upload result")

        except Exception as e:
            logger.error(f"IPFS upload failed: {e}")
            raise

    async def _upload_metadata_to_ipfs(self, nft_metadata: AvatarNFTMetadata) -> str:
        """NFTメタデータをIPFSにアップロード"""
        try:
            metadata_dict = nft_metadata.to_ipfs_metadata()

            if not self.ipfs_client:
                await self.initialize_blockchain()

            # JSONをバイトに変換してアップロード
            metadata_json = json.dumps(metadata_dict, ensure_ascii=False, indent=2)
            result = self.ipfs_client.add(metadata_json.encode('utf-8'))

            if isinstance(result, dict) and 'Hash' in result:
                return result['Hash']
            elif isinstance(result, list) and len(result) > 0:
                return result[0]['Hash']

            raise ValueError("Failed to get IPFS hash from metadata upload")

        except Exception as e:
            logger.error(f"IPFS metadata upload failed: {e}")
            raise

    async def _mint_on_blockchain(
        self,
        nft_metadata: AvatarNFTMetadata,
        metadata_cid: str,
        recipient_address: Optional[str]
    ) -> Optional[str]:
        """ブロックチェーン上でNFTをミント"""

        try:
            if not self.web3 or not self.account:
                await self.initialize_blockchain()

            # 実際のコントラクト呼び出し（コントラクトABIが必要）
            # ここではサンプル実装を示す

            # コントラクトABI（実際のコントラクトに合わせて変更）
            contract_abi = [
                {
                    "inputs": [
                        {"internalType": "address", "name": "to", "type": "address"},
                        {"internalType": "string", "name": "tokenURI", "type": "string"}
                    ],
                    "name": "mint",
                    "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                    "stateMutability": "nonpayable",
                    "type": "function"
                }
            ]

            if not self.contract_address:
                logger.warning("No contract address configured, skipping blockchain mint")
                return None

            # コントラクトインスタンス作成
            contract = self.web3.eth.contract(
                address=self.contract_address,
                abi=contract_abi
            )

            # トランザクションパラメータ
            recipient = recipient_address or self.account.address
            token_uri = f"{self.ipfs_gateway}{metadata_cid}"

            # トランザクション構築
            tx = contract.functions.mint(recipient, token_uri).build_transaction({
                'from': self.account.address,
                'gas': 200000,
                'gasPrice': self.web3.to_wei('20', 'gwei'),
                'nonce': self.web3.eth.get_transaction_count(self.account.address),
            })

            # 署名して送信
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)

            # トランザクションハッシュを返す（実際の確認はイベントリスナーで）
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Blockchain minting failed: {e}")
            return None

    async def _record_nft_mint(
        self,
        user_id: str,
        nft_metadata: AvatarNFTMetadata,
        tx_hash: str
    ):
        """NFTミント記録をデータベースに保存"""

        nft_record = {
            "user_id": user_id,
            "avatar_hash": nft_metadata.avatar_hash,
            "token_id": nft_metadata.token_id,
            "contract_address": nft_metadata.contract_address,
            "blockchain_network": self.blockchain_network,
            "tx_hash": tx_hash,
            "ipfs_cid": nft_metadata.ipfs_cid,
            "metadata": asdict(nft_metadata),
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        # JSONファイルとして保存
        record_file = self.nft_data_dir / f"nft_{nft_metadata.avatar_hash}.json"
        with open(record_file, 'w', encoding='utf-8') as f:
            json.dump(nft_record, f, ensure_ascii=False, indent=2)

        logger.info(f"NFT mint record saved: {record_file}")

    async def verify_avatar_ownership(
        self,
        avatar_hash: str,
        user_address: str
    ) -> bool:
        """
        アバターの所有権を検証

        Args:
            avatar_hash: アバターのハッシュ
            user_address: 検証するユーザーのブロックチェーンアドレス

        Returns:
            所有権が有効かどうか
        """
        try:
            # NFT記録を検索
            record_file = self.nft_data_dir / f"nft_{avatar_hash}.json"

            if not record_file.exists():
                return False

            with open(record_file, 'r', encoding='utf-8') as f:
                nft_record = json.load(f)

            # ブロックチェーンで所有権を確認（実際の実装では）
            # ここでは記録ファイルの情報で簡易検証
            recorded_address = nft_record.get("owner_address")
            return bool(recorded_address and recorded_address.lower() == user_address.lower())

        except Exception as e:
            logger.error(f"Avatar ownership verification failed: {e}")
            return False

    async def get_user_nfts(self, user_id: str) -> List[Dict]:
        """ユーザーのNFTアバター一覧を取得"""

        user_nfts = []

        try:
            # NFT記録ディレクトリからユーザーのNFTを検索
            for nft_file in self.nft_data_dir.glob("nft_*.json"):
                try:
                    with open(nft_file, 'r', encoding='utf-8') as f:
                        nft_record = json.load(f)

                    if nft_record.get("user_id") == user_id:
                        # メタデータを追加
                        nft_record["metadata"] = AvatarNFTMetadata(**nft_record["metadata"])
                        user_nfts.append(nft_record)

                except Exception as e:
                    logger.warning(f"Failed to load NFT record {nft_file}: {e}")

        except Exception as e:
            logger.error(f"Failed to get user NFTs: {e}")

        return sorted(user_nfts, key=lambda x: x["created_at"], reverse=True)

    async def transfer_avatar_nft(
        self,
        avatar_hash: str,
        from_user_id: str,
        to_address: str,
        transfer_metadata: Optional[Dict] = None
    ) -> Optional[str]:
        """
        アバターNFTを転送

        Args:
            avatar_hash: アバターのハッシュ
            from_user_id: 送信者ユーザーID
            to_address: 受信者アドレス
            transfer_metadata: 転送メタデータ

        Returns:
            転送トランザクションハッシュ
        """
        try:
            # セキュリティチェック
            if not await self.security_manager.validate_user_access(from_user_id, "nft_transfer"):
                raise ValueError("Unauthorized NFT transfer")

            # 所有権確認
            if not await self.verify_avatar_ownership(avatar_hash, from_user_id):
                raise ValueError("Avatar ownership verification failed")

            # ブロックチェーン上で転送（実際のコントラクト呼び出し）
            tx_hash = await self._transfer_on_blockchain(avatar_hash, to_address)

            if tx_hash:
                # 転送記録を更新
                await self._record_nft_transfer(avatar_hash, to_address, tx_hash)

            return tx_hash

        except Exception as e:
            logger.error(f"NFT transfer failed: {e}")
            return None

    async def _transfer_on_blockchain(self, avatar_hash: str, to_address: str) -> Optional[str]:
        """ブロックチェーン上でNFTを転送"""
        try:
            if not self.web3 or not self.account:
                await self.initialize_blockchain()

            # 実際の転送コントラクト呼び出し（実装例）
            # 実際には適切なコントラクトABIと関数名を使用

            logger.info(f"NFT transfer initiated: {avatar_hash} -> {to_address}")
            # 実際のトランザクションはここで実行

            return "0x" + "0" * 64  # ダミーのトランザクションハッシュ

        except Exception as e:
            logger.error(f"Blockchain transfer failed: {e}")
            return None

    async def _record_nft_transfer(
        self,
        avatar_hash: str,
        to_address: str,
        tx_hash: str
    ):
        """NFT転送記録を更新"""

        try:
            record_file = self.nft_data_dir / f"nft_{avatar_hash}.json"

            if record_file.exists():
                with open(record_file, 'r', encoding='utf-8') as f:
                    nft_record = json.load(f)

                # 転送情報を追加
                nft_record["transfer_history"] = nft_record.get("transfer_history", [])
                nft_record["transfer_history"].append({
                    "to_address": to_address,
                    "tx_hash": tx_hash,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                nft_record["owner_address"] = to_address

                with open(record_file, 'w', encoding='utf-8') as f:
                    json.dump(nft_record, f, ensure_ascii=False, indent=2)

                logger.info(f"NFT transfer record updated: {avatar_hash}")

        except Exception as e:
            logger.error(f"Failed to record NFT transfer: {e}")

# グローバルインスタンス
_nft_manager = None

async def get_nft_manager() -> NFTAvatarManager:
    """NFTマネージャーのインスタンスを取得"""

    global _nft_manager

    if _nft_manager is None:
        _nft_manager = NFTAvatarManager()
        await _nft_manager.initialize_blockchain()

    return _nft_manager
