"""
Advanced Security System for Cocoa 2025
ゼロトラストセキュリティとポスト量子暗号を活用した高度なセキュリティシステム
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timezone
from dataclasses import dataclass
import hashlib
import secrets

logger = logging.getLogger(__name__)

# 古典暗号 (AEAD/KDF) — ハイブリッド方式の対称鍵部分に使用
try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _AEAD_AVAILABLE = True
except (ImportError, BaseException):
    _AEAD_AVAILABLE = False

# 耐量子暗号 (NIST PQC: ML-KEM/ML-DSA) — liboqs (oqs-python) を使用
try:
    import oqs  # https://github.com/open-quantum-safe/liboqs-python
    POST_QUANTUM_AVAILABLE = True
except (ImportError, BaseException):
    oqs = None
    POST_QUANTUM_AVAILABLE = False
    logger.info(
        "liboqs (oqs-python) 未インストールのため耐量子機能は無効です。"
        "NIST FIPS 203/204 準拠の ML-KEM/ML-DSA を使うには liboqs を導入してください。"
    )

# NIST 標準アルゴリズム (liboqs 名称)
PQ_SIGN_ALGORITHM = "ML-DSA-65"   # FIPS 204 (旧 Dilithium)
PQ_KEM_ALGORITHM = "ML-KEM-768"   # FIPS 203 (旧 Kyber)
# 旧称からの後方互換エイリアス
_PQ_ALIASES = {
    "dilithium": PQ_SIGN_ALGORITHM, "ml-dsa": PQ_SIGN_ALGORITHM,
    "falcon": PQ_SIGN_ALGORITHM,  # FN-DSA(FIPS 206)未確定のため ML-DSA にフォールバック
    "kyber": PQ_KEM_ALGORITHM, "ml-kem": PQ_KEM_ALGORITHM,
}


def _resolve_pq_alg(name: str) -> str:
    """旧称(dilithium/kyber 等)を NIST 標準名へ正規化する。"""
    return _PQ_ALIASES.get(name.lower(), name)


def _is_kem_alg(name: str) -> bool:
    return _resolve_pq_alg(name).upper().startswith("ML-KEM")


from integrated_security import get_security_manager

@dataclass
class ZeroTrustContext:
    """ゼロトラストコンテキスト情報"""
    user_id: str
    session_id: str
    device_fingerprint: str
    network_info: Dict[str, Any]
    behavioral_pattern: Dict[str, Any]
    risk_score: float
    access_level: str
    compliance_flags: List[str]

@dataclass
class PostQuantumKeyPair:
    """ポスト量子鍵ペア"""
    public_key: bytes
    private_key: bytes
    algorithm: str
    key_id: str
    created_at: str

class AdvancedSecurityManager:
    """
    2025年対応高度セキュリティマネージャー
    ゼロトラストとポスト量子暗号を統合
    """

    def __init__(self):
        self.security_manager = get_security_manager()

        # ゼロトラスト設定
        self.zero_trust_enabled = os.getenv("ZERO_TRUST_ENABLED", "true").lower() == "true"
        self.risk_threshold = float(os.getenv("RISK_THRESHOLD", "0.7"))
        self.session_timeout = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))

        # ポスト量子暗号設定
        self.post_quantum_enabled = POST_QUANTUM_AVAILABLE and os.getenv("POST_QUANTUM_ENABLED", "false").lower() == "true"
        self.key_rotation_interval = int(os.getenv("KEY_ROTATION_HOURS", "24"))

        # データディレクトリ
        self.security_data_dir = Path("data/advanced_security")
        self.security_data_dir.mkdir(parents=True, exist_ok=True)

        # 鍵管理
        self.post_quantum_keys: Dict[str, PostQuantumKeyPair] = {}
        self.active_key_rotation = {}

        # リスク評価モデル
        self.risk_factors = {
            "unusual_login_time": 0.3,
            "new_device": 0.4,
            "suspicious_behavior": 0.5,
            "geolocation_anomaly": 0.3,
            "multiple_failed_attempts": 0.6,
            "privileged_operation": 0.2
        }

        logger.info("Advanced Security Manager initialized")

    async def initialize_post_quantum_crypto(self):
        """ポスト量子暗号システムを初期化"""
        if not self.post_quantum_enabled:
            logger.info("Post-quantum cryptography disabled")
            return

        try:
            # 署名(ML-DSA)と鍵カプセル化(ML-KEM)の鍵ペアを生成
            key_algorithms = [PQ_SIGN_ALGORITHM, PQ_KEM_ALGORITHM] if POST_QUANTUM_AVAILABLE else []

            for algorithm in key_algorithms:
                key_pair = await self._generate_post_quantum_keypair(algorithm)
                self.post_quantum_keys[algorithm] = key_pair

            logger.info(f"Post-quantum cryptography initialized with algorithms: {key_algorithms}")

        except Exception as e:
            logger.error(f"Failed to initialize post-quantum cryptography: {e}")
            self.post_quantum_enabled = False

    async def _generate_post_quantum_keypair(self, algorithm: str) -> PostQuantumKeyPair:
        """ポスト量子鍵ペアを生成"""

        if not POST_QUANTUM_AVAILABLE:
            raise RuntimeError("Post-quantum cryptography not available (liboqs not installed)")

        alg = _resolve_pq_alg(algorithm)
        try:
            if _is_kem_alg(alg):
                with oqs.KeyEncapsulation(alg) as kem:
                    public_key = kem.generate_keypair()
                    private_key = kem.export_secret_key()
            else:
                with oqs.Signature(alg) as signer:
                    public_key = signer.generate_keypair()
                    private_key = signer.export_secret_key()

            return PostQuantumKeyPair(
                public_key=bytes(public_key),
                private_key=bytes(private_key),
                algorithm=alg,
                key_id=secrets.token_hex(16),
                created_at=datetime.now(timezone.utc).isoformat()
            )

        except Exception as e:
            logger.error(f"Failed to generate {alg} key pair: {e}")
            raise

    async def sign_with_post_quantum(self, data: bytes, algorithm: str = PQ_SIGN_ALGORITHM) -> bytes:
        """ML-DSA (FIPS 204) でデータに署名する。"""
        if not self.post_quantum_enabled:
            raise RuntimeError("Post-quantum cryptography not enabled")
        alg = _resolve_pq_alg(algorithm)
        key_pair = self.post_quantum_keys.get(alg)
        if not key_pair:
            raise ValueError(f"No post-quantum signing key for algorithm: {alg}")
        with oqs.Signature(alg, key_pair.private_key) as signer:
            return signer.sign(data)

    def verify_post_quantum_signature(
        self, data: bytes, signature: bytes, public_key: bytes,
        algorithm: str = PQ_SIGN_ALGORITHM
    ) -> bool:
        """ML-DSA (FIPS 204) 署名を検証する。"""
        if not POST_QUANTUM_AVAILABLE:
            raise RuntimeError("Post-quantum cryptography not available")
        alg = _resolve_pq_alg(algorithm)
        with oqs.Signature(alg) as verifier:
            return bool(verifier.verify(data, signature, public_key))

    async def evaluate_zero_trust_access(
        self,
        user_id: str,
        operation: str,
        context: Dict[str, Any]
    ) -> ZeroTrustContext:
        """
        ゼロトラストアクセス評価を実行

        Args:
            user_id: ユーザーID
            operation: 実行する操作
            context: アクセスコンテキスト

        Returns:
            ゼロトラストコンテキスト
        """
        try:
            # デバイス指紋の生成・検証
            device_fingerprint = self._generate_device_fingerprint(context)

            # ネットワーク情報の収集
            network_info = {
                "ip_address": context.get("ip_address", "unknown"),
                "user_agent": context.get("user_agent", ""),
                "geolocation": await self._get_geolocation(context.get("ip_address")),
                "vpn_detected": await self._detect_vpn(context.get("ip_address")),
                "proxy_detected": context.get("proxy_info", {}).get("detected", False)
            }

            # 行動パターンの分析
            behavioral_pattern = await self._analyze_behavioral_pattern(user_id, operation)

            # リスクスコアの計算
            risk_score = await self._calculate_risk_score(
                user_id, operation, context, network_info, behavioral_pattern
            )

            # アクセスレベルの決定
            access_level = self._determine_access_level(risk_score, operation)

            # コンプライアンスフラグの設定
            compliance_flags = await self._check_compliance_requirements(
                user_id, operation, risk_score
            )

            zero_trust_context = ZeroTrustContext(
                user_id=user_id,
                session_id=context.get("session_id", secrets.token_hex(16)),
                device_fingerprint=device_fingerprint,
                network_info=network_info,
                behavioral_pattern=behavioral_pattern,
                risk_score=risk_score,
                access_level=access_level,
                compliance_flags=compliance_flags
            )

            # 高リスクアクセスの場合、追加検証を要求
            if risk_score > self.risk_threshold:
                await self._require_additional_verification(zero_trust_context)

            return zero_trust_context

        except Exception as e:
            logger.error(f"Zero-trust access evaluation failed: {e}")
            raise

    def _generate_device_fingerprint(self, context: Dict[str, Any]) -> str:
        """デバイス指紋を生成"""

        fingerprint_data = [
            context.get("user_agent", ""),
            context.get("screen_resolution", ""),
            context.get("timezone", ""),
            context.get("language", ""),
            context.get("platform", "")
        ]

        fingerprint_string = "|".join(fingerprint_data)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()

    async def _get_geolocation(self, ip_address: str) -> Dict[str, Any]:
        """IPアドレスから地理位置情報を取得"""
        # 実際の実装ではジオロケーションAPIを使用
        return {
            "country": "unknown",
            "region": "unknown",
            "city": "unknown",
            "latitude": 0.0,
            "longitude": 0.0
        }

    async def _detect_vpn(self, ip_address: str) -> bool:
        """VPN検出"""
        # 実際の実装ではVPN検出サービスを使用
        return False

    async def _analyze_behavioral_pattern(
        self,
        user_id: str,
        operation: str
    ) -> Dict[str, Any]:
        """ユーザーの行動パターンを分析"""

        # 過去の行動データを取得（実際の実装ではデータベースから）
        pattern_data = {
            "usual_login_hours": [9, 10, 11, 14, 15, 16],
            "frequent_operations": ["avatar_view", "profile_update"],
            "avg_session_duration": 45,
            "device_consistency": 0.8,
            "location_consistency": 0.7
        }

        return pattern_data

    async def _calculate_risk_score(
        self,
        user_id: str,
        operation: str,
        context: Dict[str, Any],
        network_info: Dict[str, Any],
        behavioral_pattern: Dict[str, Any]
    ) -> float:
        """リスクスコアを計算"""

        risk_score = 0.0

        # 時間帯チェック
        current_hour = datetime.now(timezone.utc).hour
        if current_hour not in behavioral_pattern.get("usual_login_hours", []):
            risk_score += self.risk_factors["unusual_login_time"]

        # 新しいデバイスチェック
        if context.get("new_device", False):
            risk_score += self.risk_factors["new_device"]

        # ネットワーク異常チェック
        if network_info.get("vpn_detected", False):
            risk_score += 0.2  # VPNはリスク軽減要因として扱う場合もある

        # 特権操作チェック
        if operation in ["admin_access", "system_config", "user_delete"]:
            risk_score += self.risk_factors["privileged_operation"]

        # 地理的位置異常チェック
        if network_info.get("geolocation", {}).get("country") == "unknown":
            risk_score += self.risk_factors["geolocation_anomaly"]

        return min(risk_score, 1.0)

    def _determine_access_level(self, risk_score: float, operation: str) -> str:
        """リスクスコアに基づいてアクセスレベルを決定"""

        if risk_score > 0.8:
            return "denied"
        if risk_score > 0.6:
            return "restricted"
        if risk_score > 0.4:
            return "monitored"
        return "full"

    async def _check_compliance_requirements(
        self,
        user_id: str,
        operation: str,
        risk_score: float
    ) -> List[str]:
        """コンプライアンス要件をチェック"""

        compliance_flags = []

        # GDPR関連チェック
        if operation == "data_export" and risk_score > 0.3:
            compliance_flags.append("gdpr_verification_required")

        # SOX関連チェック（財務データ操作の場合）
        if operation in ["financial_report", "billing_data"] and risk_score > 0.5:
            compliance_flags.append("sox_audit_required")

        # HIPAA関連チェック（医療データの場合）
        if operation == "medical_data_access" and risk_score > 0.4:
            compliance_flags.append("hipaa_compliance_check")

        return compliance_flags

    async def _require_additional_verification(self, context: ZeroTrustContext):
        """追加検証を要求"""

        # 多要素認証の要求
        if context.access_level in ["restricted", "monitored"]:
            logger.info(f"Additional verification required for user {context.user_id}")

            # 実際の実装ではMFAサービスを呼び出し
            await self.security_manager.log_security_event(
                event_type="additional_verification_required",
                user_id=context.user_id,
                details={
                    "risk_score": context.risk_score,
                    "access_level": context.access_level,
                    "required_verification": "mfa"
                },
                ip_address=context.network_info.get("ip_address", "unknown")
            )

    async def encrypt_with_post_quantum(
        self,
        data: bytes,
        algorithm: str = PQ_KEM_ALGORITHM
    ) -> bytes:
        """ハイブリッド方式で暗号化する: ML-KEM(FIPS 203)で共有鍵をカプセル化し AES-256-GCM で本文を暗号化。

        フレーム: [2B kem_ct長][kem_ct][12B nonce][aes_gcm_ct]。
        注意: 署名アルゴリズム(ML-DSA)は暗号化には使用できない。
        """
        if not self.post_quantum_enabled:
            raise RuntimeError("Post-quantum cryptography not enabled")
        if not _AEAD_AVAILABLE:
            raise RuntimeError("AES-GCM (cryptography) unavailable for hybrid encryption")

        alg = _resolve_pq_alg(algorithm)
        if not _is_kem_alg(alg):
            raise ValueError(f"Encryption requires a KEM algorithm (e.g. {PQ_KEM_ALGORITHM}), got: {alg}")
        key_pair = self.post_quantum_keys.get(alg)
        if not key_pair:
            raise ValueError(f"No post-quantum KEM key pair for algorithm: {alg}")

        try:
            with oqs.KeyEncapsulation(alg) as kem:
                kem_ciphertext, shared_secret = kem.encap_secret(key_pair.public_key)

            aes_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                           info=b"cocoa-pq-hybrid").derive(shared_secret)
            nonce = secrets.token_bytes(12)
            aes_ct = AESGCM(aes_key).encrypt(nonce, data, None)
            return len(kem_ciphertext).to_bytes(2, "big") + kem_ciphertext + nonce + aes_ct

        except Exception as e:
            logger.error(f"Post-quantum encryption failed: {e}")
            raise

    async def decrypt_with_post_quantum(
        self,
        encrypted_data: bytes,
        algorithm: str = PQ_KEM_ALGORITHM
    ) -> bytes:
        """encrypt_with_post_quantum の逆: ML-KEM で共有鍵を復元し AES-256-GCM で復号する。"""

        if not self.post_quantum_enabled:
            raise RuntimeError("Post-quantum cryptography not enabled")
        if not _AEAD_AVAILABLE:
            raise RuntimeError("AES-GCM (cryptography) unavailable for hybrid decryption")

        alg = _resolve_pq_alg(algorithm)
        if not _is_kem_alg(alg):
            raise ValueError(f"Decryption requires a KEM algorithm (e.g. {PQ_KEM_ALGORITHM}), got: {alg}")
        key_pair = self.post_quantum_keys.get(alg)
        if not key_pair:
            raise ValueError(f"No post-quantum KEM key pair for algorithm: {alg}")

        try:
            ct_len = int.from_bytes(encrypted_data[:2], "big")
            offset = 2
            kem_ciphertext = encrypted_data[offset:offset + ct_len]
            offset += ct_len
            nonce = encrypted_data[offset:offset + 12]
            offset += 12
            aes_ct = encrypted_data[offset:]

            with oqs.KeyEncapsulation(alg, key_pair.private_key) as kem:
                shared_secret = kem.decap_secret(kem_ciphertext)

            aes_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                           info=b"cocoa-pq-hybrid").derive(shared_secret)
            return AESGCM(aes_key).decrypt(nonce, aes_ct, None)

        except Exception as e:
            logger.error(f"Post-quantum decryption failed: {e}")
            raise

    async def rotate_post_quantum_keys(self):
        """ポスト量子鍵をローテーション"""

        if not self.post_quantum_enabled:
            return

        try:
            for algorithm in list(self.post_quantum_keys.keys()):
                # 新しい鍵ペアを生成
                new_key_pair = await self._generate_post_quantum_keypair(algorithm)

                # 古い鍵をバックアップ
                old_key_backup = self.post_quantum_keys[algorithm]
                backup_file = self.security_data_dir / f"key_backup_{algorithm}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"

                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "algorithm": algorithm,
                        "public_key": old_key_backup.public_key.hex(),
                        "private_key": old_key_backup.private_key.hex(),
                        "key_id": old_key_backup.key_id,
                        "backed_up_at": datetime.now(timezone.utc).isoformat()
                    }, f)

                # 新しい鍵をアクティブに設定
                self.post_quantum_keys[algorithm] = new_key_pair

                logger.info(f"Post-quantum key rotated for algorithm: {algorithm}")

        except Exception as e:
            logger.error(f"Post-quantum key rotation failed: {e}")

    async def get_security_dashboard_data(self, time_range: str = "24h") -> Dict[str, Any]:
        """セキュリティダッシュボードデータを取得"""

        try:
            # 実際の実装ではデータベースから統計情報を収集
            dashboard_data = {
                "zero_trust_metrics": {
                    "total_access_requests": 1250,
                    "denied_requests": 15,
                    "high_risk_requests": 45,
                    "avg_risk_score": 0.23,
                    "mfa_challenges": 28
                },
                "post_quantum_crypto": {
                    "enabled": self.post_quantum_enabled,
                    "algorithms": list(self.post_quantum_keys.keys()),
                    "last_rotation": self.active_key_rotation.get("last_rotation"),
                    "keys_compromised": 0
                },
                "threat_intelligence": {
                    "active_threats": 3,
                    "blocked_ips": 12,
                    "suspicious_activities": 8,
                    "geographic_anomalies": 5
                },
                "compliance_status": {
                    "gdpr_compliant": True,
                    "sox_compliant": True,
                    "hipaa_compliant": True,
                    "last_audit": datetime.now(timezone.utc).isoformat()
                },
                "generated_at": datetime.now(timezone.utc).isoformat()
            }

            return dashboard_data

        except Exception as e:
            logger.error(f"Failed to get security dashboard data: {e}")
            return {}

# グローバルインスタンス
_advanced_security_manager = None

async def get_advanced_security_manager() -> AdvancedSecurityManager:
    """高度セキュリティマネージャーのインスタンスを取得"""

    global _advanced_security_manager

    if _advanced_security_manager is None:
        _advanced_security_manager = AdvancedSecurityManager()
        await _advanced_security_manager.initialize_post_quantum_crypto()

    return _advanced_security_manager
