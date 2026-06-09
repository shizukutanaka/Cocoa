"""
ブロックチェーン統合サービス - NFTとデジタル通貨のサポート

メタバースアバター向けのブロックチェーン機能を提供：
- NFTアバターの作成・管理・取引
- デジタル通貨（仮想通貨）の管理
- ブロックチェーン上でのアセット所有権証明
- スマートコントラクト統合
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

try:
    from web3 import Web3
    import ipfshttpclient
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False

logger = logging.getLogger(__name__)


class BlockchainService:
    """ブロックチェーン統合サービス"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.web3 = None
        self.ipfs_client = None
        self.contracts = {}
        self.nft_metadata = {}

        if WEB3_AVAILABLE:
            self._initialize_blockchain()
        else:
            logger.warning("Web3ライブラリが利用できません。ブロックチェーン機能が制限されます。")

    def _initialize_blockchain(self):
        """ブロックチェーン接続を初期化"""
        try:
            # Ethereumネットワークに接続（実際の実装では環境変数から取得）
            rpc_url = self.config.get('rpc_url', 'https://mainnet.infura.io/v3/YOUR_INFURA_KEY')
            self.web3 = Web3(Web3.HTTPProvider(rpc_url))

            if not self.web3.is_connected():
                logger.error("ブロックチェーンに接続できません")
                return

            # IPFSクライアントを初期化
            self.ipfs_client = ipfshttpclient.connect('/ip4/127.0.0.1/tcp/5001')

            logger.info("ブロックチェーンサービスを初期化しました")

        except Exception as e:
            logger.error(f"ブロックチェーン初期化エラー: {e}")

    def create_nft_avatar(self, avatar_data: Dict[str, Any], owner_address: str) -> Dict[str, Any]:
        """NFTアバターを作成"""
        if not WEB3_AVAILABLE or not self.web3:
            return {'error': 'ブロックチェーン機能が利用できません'}

        try:
            # アバターデータをIPFSにアップロード
            metadata = {
                'name': avatar_data.get('name', 'Avatar'),
                'description': avatar_data.get('description', 'Metaverse Avatar'),
                'image': avatar_data.get('image_url', ''),
                'attributes': avatar_data.get('attributes', []),
                'created_at': datetime.now(timezone.utc).isoformat()
            }

            # IPFSにメタデータをアップロード
            ipfs_hash = self.ipfs_client.add_json(metadata)

            # NFTコントラクトをデプロイまたは呼び出し（簡易実装）
            # 実際の実装ではスマートコントラクトのアドレスとABIが必要

            nft_info = {
                'token_id': f"nft_{int(datetime.now(timezone.utc).timestamp())}",
                'metadata_ipfs': ipfs_hash,
                'owner': owner_address,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'blockchain': 'ethereum'
            }

            self.nft_metadata[nft_info['token_id']] = nft_info

            logger.info(f"NFTアバターを作成しました: {nft_info['token_id']}")
            return nft_info

        except Exception as e:
            logger.error(f"NFT作成エラー: {e}")
            return {'error': str(e)}

    def transfer_nft(self, token_id: str, from_address: str, to_address: str) -> Dict[str, Any]:
        """NFTを転送"""
        if not WEB3_AVAILABLE or not self.web3:
            return {'error': 'ブロックチェーン機能が利用できません'}

        if token_id not in self.nft_metadata:
            return {'error': 'NFTが見つかりません'}

        try:
            nft_info = self.nft_metadata[token_id]
            nft_info['owner'] = to_address
            nft_info['transferred_at'] = datetime.now(timezone.utc).isoformat()

            # 実際の実装ではブロックチェーン上で転送を実行

            logger.info(f"NFTを転送しました: {token_id} -> {to_address}")
            return {'success': True, 'token_id': token_id, 'new_owner': to_address}

        except Exception as e:
            logger.error(f"NFT転送エラー: {e}")
            return {'error': str(e)}

    def get_nft_info(self, token_id: str) -> Dict[str, Any]:
        """NFT情報を取得"""
        return self.nft_metadata.get(token_id, {'error': 'NFTが見つかりません'})

    def create_digital_currency_transaction(self, from_address: str, to_address: str, amount: float, currency: str = 'COCOA') -> Dict[str, Any]:
        """デジタル通貨の取引を作成"""
        if not WEB3_AVAILABLE or not self.web3:
            return {'error': 'ブロックチェーン機能が利用できません'}

        try:
            transaction = {
                'tx_id': f"tx_{int(datetime.now(timezone.utc).timestamp())}_{hash(f'{from_address}_{to_address}_{amount}') % 10000}",
                'from_address': from_address,
                'to_address': to_address,
                'amount': amount,
                'currency': currency,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'status': 'pending'
            }

            # 実際の実装ではブロックチェーン上で取引を実行

            logger.info(f"デジタル通貨取引を作成しました: {transaction['tx_id']}")
            return transaction

        except Exception as e:
            logger.error(f"取引作成エラー: {e}")
            return {'error': str(e)}

    def get_wallet_balance(self, address: str, currency: str = 'COCOA') -> Dict[str, Any]:
        """ウォレットの残高を取得"""
        if not WEB3_AVAILABLE or not self.web3:
            return {'error': 'ブロックチェーン機能が利用できません'}

        # 実際の実装ではブロックチェーンから残高を取得
        balance = 1000.0  # デフォルト値

        return {
            'address': address,
            'currency': currency,
            'balance': balance,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def verify_ownership(self, token_id: str, address: str) -> bool:
        """NFT所有権を検証"""
        nft_info = self.get_nft_info(token_id)
        if 'error' in nft_info:
            return False

        return nft_info.get('owner') == address

    def get_service_status(self) -> Dict[str, Any]:
        """サービスステータスを取得"""
        return {
            'blockchain_connected': self.web3.is_connected() if self.web3 else False,
            'ipfs_connected': self.ipfs_client is not None,
            'total_nfts': len(self.nft_metadata),
            'supported_currencies': ['COCOA', 'ETH', 'USDC']
        }


# グローバルインスタンス
_blockchain_service: Optional[BlockchainService] = None


def get_blockchain_service(config: Optional[Dict[str, Any]] = None) -> BlockchainService:
    """ブロックチェーンサービスを取得"""
    global _blockchain_service
    if _blockchain_service is None:
        _blockchain_service = BlockchainService(config)
    return _blockchain_service


def initialize_blockchain_service(config: Optional[Dict[str, Any]] = None) -> BlockchainService:
    """ブロックチェーンサービスを初期化"""
    global _blockchain_service
    _blockchain_service = BlockchainService(config)
    logger.info("ブロックチェーンサービスを初期化しました")
    return _blockchain_service
