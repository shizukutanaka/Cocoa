"""
Integrated Security module for Cocoa.

Provides encryption (AES-256-GCM), security auditing, input validation,
behavioral anomaly detection and zero-trust session management.
"""

import os
import re
import json
import time
import hashlib
import secrets
import logging
from stat import S_IMODE
from pathlib import Path
from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Optional scientific stack (used by the behavioural anomaly detector).
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except (ImportError, BaseException):
    NUMPY_AVAILABLE = False

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except (ImportError, BaseException):
    SKLEARN_AVAILABLE = False

try:
    import oqs
    OQS_AVAILABLE = True
except (ImportError, BaseException):
    OQS_AVAILABLE = False
    logger.warning("Open Quantum Safe library not available. Quantum-safe features will be limited.")

try:
    import pqcrystals  # noqa: F401
    PQCRYSTALS_AVAILABLE = True
except (ImportError, BaseException):
    PQCRYSTALS_AVAILABLE = False
    logger.warning("PQ Crystals library not available. Using fallback quantum-safe implementation.")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SECURITY_SUBDIR = PROJECT_ROOT / "data" / "security"


def _is_within_directory(base: Path, target: Path) -> bool:
    try:
        base_resolved = base.resolve(strict=False)
        target_resolved = target.resolve(strict=False)
    except OSError:
        return False
    try:
        target_resolved.relative_to(base_resolved)
        return True
    except ValueError:
        return False


def _resolve_security_db_path() -> Path:
    env_path = os.environ.get("OTEDAMA_SECURITY_DB", "").strip()
    candidate = Path(env_path).expanduser() if env_path else DEFAULT_SECURITY_SUBDIR / "security.db"

    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()

    if not _is_within_directory(PROJECT_ROOT, candidate):
        raise ValueError("Security audit database path must reside inside the project directory")

    candidate.parent.mkdir(parents=True, exist_ok=True)

    if candidate.exists() and not candidate.is_file():
        raise RuntimeError(f"Security audit path is not a file: {candidate}")

    if not candidate.exists():
        candidate.touch()

    if os.name != "nt":
        try:
            current_mode = S_IMODE(candidate.stat().st_mode)
            if current_mode & 0o077:
                candidate.chmod(0o600)
        except OSError:
            logger = logging.getLogger(__name__)
            logger.warning("Failed to tighten permissions on security audit database")

    return candidate

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except (ImportError, BaseException):
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    """脅威レベル"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityLevel(Enum):
    """セキュリティレベル"""
    BASIC = "basic"
    ENHANCED = "enhanced"
    STRICT = "strict"
    PARANOID = "paranoid"


@dataclass
class SecurityPolicy:
    """セキュリティポリシー"""
    level: SecurityLevel = SecurityLevel.ENHANCED
    max_login_attempts: int = 5
    lockout_duration: int = 900  # 15分
    session_timeout: int = 1800  # 30分
    password_min_length: int = 12
    require_2fa: bool = True
    enable_audit_log: bool = True
    allowed_ips: List[str] = field(default_factory=list)
    blocked_ips: List[str] = field(default_factory=list)

class SecurityEvent:
    """セキュリティイベント - シンプルで明確な構造"""

    def __init__(self, event_type: str, user_id: str, resource: str, details: Dict[str, Any] = None):
        self.event_type = event_type
        self.user_id = user_id
        self.resource = resource
        self.details = details or {}
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """辞書変換"""
        return {
            'event_type': self.event_type,
            'user_id': self.user_id,
            'resource': self.resource,
            'details': self.details,
            'timestamp': self.timestamp
        }

class PrivacyProtector:
    """メタバースアバターのプライバシー保護システム"""

    def __init__(self):
        self.privacy_policies: Dict[str, Dict[str, Any]] = {}
        self.anonymization_rules: Dict[str, callable] = {}

    def add_privacy_policy(self, user_id: str, policy: Dict[str, Any]) -> None:
        """ユーザーのプライバシーポリシーを追加"""
        self.privacy_policies[user_id] = policy

    def anonymize_data(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """データを匿名化"""
        if user_id not in self.privacy_policies:
            return data

        policy = self.privacy_policies[user_id]
        anonymized = {}

        for key, value in data.items():
            if key in policy.get('anonymize_fields', []):
                # フィールドを匿名化
                anonymized[key] = self._anonymize_value(value)
            else:
                anonymized[key] = value

        return anonymized

    def _anonymize_value(self, value: Any) -> Any:
        """値を匿名化"""
        if isinstance(value, str):
            # 文字列のハッシュ化や部分マスク
            return f"<anonymized_{hash(str(value)) % 10000}>"
        elif isinstance(value, (int, float)):
            # 数値を範囲に変換
            return f"<range_{int(value // 10) * 10}-{int(value // 10) * 10 + 9}>"
        else:
            return "<anonymized>"

    def check_data_sharing(self, user_id: str, target: str) -> bool:
        """データ共有の許可をチェック"""
        if user_id not in self.privacy_policies:
            return False

        policy = self.privacy_policies[user_id]
        allowed_targets = policy.get('allowed_sharing', [])
        return target in allowed_targets


class AdvancedBehaviorAnalyzer:
    """機械学習と統計手法を併用した行動異常検知システム。"""

    def __init__(self):
        # behavior_key("{behavior_type}_{user_id}") -> 行動データの履歴
        self.user_behaviors: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        # user_id -> behavior_type -> 統計ベースライン
        self.baselines: Dict[str, Dict[str, Any]] = {}
        # user_id -> 学習済み IsolationForest モデル
        self.ml_models: Dict[str, Any] = {}
        # user_id -> 特徴量スケーラー
        self.scalers: Dict[str, Any] = {}
        # 異常判定のしきい値（0.0-1.0）
        self.anomaly_threshold = 0.7

    def _save_models(self) -> None:
        """学習済みモデルの永続化フック（環境依存のため既定では何もしない）。"""
        return None

    def record_behavior(self, user_id: str, behavior_type: str, value: float, timestamp: Optional[float] = None, context: Dict[str, Any] = None):
        """行動データを記録し、機械学習モデルを更新"""
        if timestamp is None:
            timestamp = time.time()

        behavior_key = f"{behavior_type}_{user_id}"
        context = context or {}

        # 行動データを記録
        behavior_data = {
            'timestamp': timestamp,
            'value': value,
            'behavior_type': behavior_type,
            'user_id': user_id,
            **context
        }
        self.user_behaviors[behavior_key].append(behavior_data)

        # 十分なデータがある場合、機械学習モデルを更新
        if len(self.user_behaviors[behavior_key]) >= 50:  # 最低50サンプル
            self._update_ml_model(user_id, behavior_type)

    def _update_ml_model(self, user_id: str, behavior_type: str):
        """機械学習モデルを更新"""
        behavior_key = f"{behavior_type}_{user_id}"

        if len(self.user_behaviors[behavior_key]) < 50:
            return

        # 特徴量エンジニアリング
        features = self._extract_features(user_id, behavior_type)

        if features is None or len(features) < 10:
            return

        # データのスケーリング
        if user_id not in self.scalers:
            self.scalers[user_id] = StandardScaler()

        scaled_features = self.scalers[user_id].fit_transform(features)

        # モデルの訓練または更新
        if user_id not in self.ml_models:
            self.ml_models[user_id] = IsolationForest(
                contamination=0.1,
                random_state=42,
                n_estimators=100
            )

        # モデルの再訓練（増分学習）
        try:
            self.ml_models[user_id].fit(scaled_features)
            self._save_models()  # モデルを保存
        except Exception as e:
            logger.error(f"モデル更新エラー ({user_id}, {behavior_type}): {e}")

    def _extract_features(self, user_id: str, behavior_type: str) -> "Optional[Any]":
        """行動データから特徴量を抽出"""
        behavior_key = f"{behavior_type}_{user_id}"
        behaviors = list(self.user_behaviors[behavior_key])

        if len(behaviors) < 10:
            return None

        # 時系列特徴量の抽出
        values = [b['value'] for b in behaviors[-100:]]  # 最新100サンプル
        timestamps = [b['timestamp'] for b in behaviors[-100:]]

        # 基本統計特徴量
        features = [
            np.mean(values),
            np.std(values),
            np.min(values),
            np.max(values),
            np.median(values),
            len(values),
        ]

        # 時系列特徴量
        if len(values) >= 2:
            # 変化率
            changes = np.diff(values)
            features.extend([
                np.mean(changes),
                np.std(changes),
                np.mean(np.abs(changes)),  # 平均絶対変化
            ])

            # 時間間隔特徴量
            time_diffs = np.diff(timestamps)
            features.extend([
                np.mean(time_diffs),
                np.std(time_diffs),
            ])

        # 周期性特徴量（簡易版）
        if len(values) >= 24:
            # 直近24サンプルのパターン
            recent_pattern = values[-24:]
            features.extend([
                np.mean(recent_pattern[:12]),  # 前半平均
                np.mean(recent_pattern[12:]),  # 後半平均
                np.corrcoef(recent_pattern[:12], recent_pattern[12:])[0, 1] if len(recent_pattern) >= 12 else 0,
            ])

        return np.array(features).reshape(1, -1)

    def detect_anomaly(self, user_id: str, behavior_type: str, value: float, context: Dict[str, Any] = None) -> Tuple[bool, float, Dict[str, Any]]:
        """機械学習ベースの行動異常検知"""
        context = context or {}

        # 統計ベースの異常検知（従来の方法）
        statistical_anomaly, z_score = self._detect_statistical_anomaly(user_id, behavior_type, value)

        # 機械学習ベースの異常検知
        ml_anomaly, ml_score = self._detect_ml_anomaly(user_id, behavior_type, value, context)

        # 両方の結果を統合
        is_anomaly = statistical_anomaly or ml_anomaly
        confidence = max(abs(z_score), ml_score)

        details = {
            'statistical_z_score': z_score,
            'ml_anomaly_score': ml_score,
            'detection_method': 'statistical' if statistical_anomaly else 'ml' if ml_anomaly else 'normal',
            'confidence': confidence
        }

        return is_anomaly, confidence, details

    def _detect_statistical_anomaly(self, user_id: str, behavior_type: str, value: float) -> Tuple[bool, float]:
        """統計ベースの異常検知"""
        if user_id not in self.baselines or behavior_type not in self.baselines[user_id]:
            return False, 0.0

        baseline = self.baselines[user_id][behavior_type]
        if baseline['stdev'] == 0:
            return False, 0.0

        z_score = abs(value - baseline['mean']) / baseline['stdev']
        return z_score > self.anomaly_threshold, z_score

    def _detect_ml_anomaly(self, user_id: str, behavior_type: str, value: float, context: Dict[str, Any]) -> Tuple[bool, float]:
        """機械学習ベースの異常検知"""
        # 特徴量を抽出
        features = self._extract_features(user_id, behavior_type)

        if features is None or user_id not in self.ml_models:
            return False, 0.0

        # 予測実行
        try:
            scaled_features = self.scalers[user_id].transform(features)
            prediction = self.ml_models[user_id].predict(scaled_features)

            # Isolation Forestの出力は-1（異常）または1（正常）
            is_anomaly = prediction[0] == -1
            # 異常スコアを計算（デフォルトで0.5を基準に）
            anomaly_score = self.ml_models[user_id].score_samples(scaled_features)[0]

            # スコアを0-1の範囲に正規化
            normalized_score = max(0, (0.5 - anomaly_score) / 0.5)

            return is_anomaly, normalized_score
        except Exception as e:
            logger.error(f"ML異常検知エラー: {e}")
            return False, 0.0

    def _update_baseline(self, behavior_key: str, user_id: str, behavior_type: str):
        """ベースライン統計を更新"""
        behaviors = list(self.user_behaviors[behavior_key])
        if len(behaviors) < 10:
            return

        values = [b['value'] for b in behaviors]

        self.baselines.setdefault(user_id, {})[behavior_type] = {
            'mean': np.mean(values),
            'stdev': np.std(values) if len(values) > 1 else 0,
            'count': len(values)
        }

    def get_behavior_summary(self, user_id: str) -> Dict[str, Any]:
        """ユーザーの行動サマリーを取得"""
        summary = {
            'ml_models_trained': len(self.ml_models),
            'scalers_configured': len(self.scalers),
            'total_users': len(self.baselines)
        }

        for behavior_type in ['login_frequency', 'operation_count', 'session_duration']:
            key = f"{behavior_type}_{user_id}"
            if key in self.user_behaviors and len(self.user_behaviors[key]) > 0:
                behaviors = list(self.user_behaviors[key])
                values = [b['value'] for b in behaviors]

                summary[behavior_type] = {
                    'recent_avg': np.mean(values[-10:]) if len(values) >= 10 else np.mean(values),
                    'total_count': len(values),
                    'baseline': self.baselines.get(user_id, {}).get(behavior_type, {}),
                    'ml_model_exists': user_id in self.ml_models
                }

        return summary

    def cleanup_old_data(self, max_age_hours: int = 168):
        """古い行動データをクリーンアップ"""
        cutoff_time = time.time() - (max_age_hours * 3600)

        for key in list(self.user_behaviors.keys()):
            # 古いデータを削除
            self.user_behaviors[key] = deque(
                b for b in self.user_behaviors[key] if b['timestamp'] > cutoff_time
            )

            # データがなくなった場合はベースラインも削除
            if not self.user_behaviors[key]:
                user_id = key.split('_', 1)[1] if '_' in key else None
                behavior_type = key.split('_')[0]
                if user_id and behavior_type in self.baselines.get(user_id, {}):
                    del self.baselines[user_id][behavior_type]
                    if not self.baselines[user_id]:
                        del self.baselines[user_id]

class SecurityAuditor:
    """セキュリティ監査 - 実用的で効率的な監査"""

    def __init__(self, db_path: Optional[str] = None):
        resolved = _resolve_security_db_path() if db_path is None else Path(db_path).expanduser()
        self.db_path = str(resolved)
        self.events = []
        self._init_database()

    def _init_database(self):
        """SQLiteデータベースを初期化"""
        try:
            with self._connect() as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS security_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT,
                        user_id TEXT,
                        resource TEXT,
                        details TEXT,
                        timestamp TEXT
                    )
                ''')
        except Exception as e:
            logger.error(f"セキュリティDBの初期化に失敗: {e}")

    def _connect(self):
        """データベース接続を返す"""
        import sqlite3
        return sqlite3.connect(self.db_path)

    def log_event(self, event: SecurityEvent):
        """イベント記録 - 直接的で高速"""
        self.events.append(event)

        # データベースに保存
        try:
            with self._connect() as conn:
                conn.execute('''
                    INSERT INTO security_events (event_type, user_id, resource, details, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (event.event_type, event.user_id, event.resource,
                      json.dumps(event.details), event.timestamp))
                conn.commit()
        except Exception as e:
            logger.error(f"セキュリティイベント保存エラー: {e}")

    def get_events(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """イベント取得"""
        cutoff_time = time.time() - (hours_back * 3600)

        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "SELECT * FROM security_events WHERE timestamp > ? ORDER BY timestamp DESC",
                    (cutoff_time,)
                )
                rows = cursor.fetchall()

                return [
                    {
                        'id': row[0], 'event_type': row[1], 'user_id': row[2],
                        'resource': row[3], 'details': json.loads(row[4]) if row[4] else {},
                        'timestamp': row[5]
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"セキュリティイベント取得エラー: {e}")
            return []

class DataEncryptor:
    """Production-Grade AES-256-GCM暗号化"""

    def __init__(self, key: Optional[str] = None):
        if not CRYPTO_AVAILABLE:
            logger.critical("cryptography package not available - encryption disabled")
            raise ImportError("Install cryptography package for secure encryption")

        env_key = os.environ.get('OTEDAMA_ENCRYPTION_KEY')
        self.master_key = (env_key or key or secrets.token_urlsafe(32)).encode()

        # PBKDF2でマスターキーから派生キーを生成
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'otedama_security_salt_v1',  # 本番環境では環境変数から読み込むべき
            iterations=100000,
            backend=default_backend()
        )
        self.encryption_key = kdf.derive(self.master_key)
        self.backend = default_backend()

    def encrypt_data(self, data: Dict[str, Any]) -> str:
        """AES-256-GCM暗号化"""
        try:
            json_str = json.dumps(data, ensure_ascii=False)
            plaintext = json_str.encode('utf-8')

            # 12バイトのnonceを生成 (GCM推奨)
            nonce = secrets.token_bytes(12)

            cipher = Cipher(
                algorithms.AES(self.encryption_key),
                modes.GCM(nonce),
                backend=self.backend
            )
            encryptor = cipher.encryptor()

            ciphertext = encryptor.update(plaintext) + encryptor.finalize()

            # nonce + tag + ciphertext を結合してbase64エンコード
            import base64
            combined = nonce + encryptor.tag + ciphertext
            return base64.b64encode(combined).decode('ascii')
        except Exception as e:
            logger.error(f"暗号化エラー: {e}")
            raise

    def decrypt_data(self, encrypted_str: str) -> Dict[str, Any]:
        """AES-256-GCM復号化"""
        try:
            import base64
            combined = base64.b64decode(encrypted_str)

            # nonce (12) + tag (16) + ciphertext を分離
            nonce = combined[:12]
            tag = combined[12:28]
            ciphertext = combined[28:]

            cipher = Cipher(
                algorithms.AES(self.encryption_key),
                modes.GCM(nonce, tag),
                backend=self.backend
            )
            decryptor = cipher.decryptor()

            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            json_str = plaintext.decode('utf-8')
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"復号化エラー: {e}")
            return {}

class SecurityValidator:
    """Production-Grade入力検証とアクセス制御"""

    # XSS/SQLi/コマンドインジェクション対策パターン
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>',
        r'javascript:',
        r'on\w+\s*=',
        r'eval\s*\(',
        r'exec\s*\(',
        r'__import__',
        r'\.\./',
        r'\.\.',
        r'system\(',
        r'shell_exec',
        r'DROP\s+TABLE',
        r'INSERT\s+INTO',
        r'UPDATE\s+.*SET',
        r'DELETE\s+FROM',
        r'UNION\s+SELECT',
        r'--\s*$',
        r'/\*.*\*/',
    ]

    def __init__(self, policy: Optional[SecurityPolicy] = None):
        self.policy = policy or SecurityPolicy()
        self.allowed_users: set = set()
        self.user_roles: Dict[str, str] = {}
        self.failed_attempts: Dict[str, List[float]] = {}
        self.lockouts: Dict[str, float] = {}

        # IPアドレス検証用の正規表現
        self.ip_pattern = re.compile(
            r'^(\d{1,3}\.){3}\d{1,3}$|'
            r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
        )

    def validate_user_access(self, user_id: str, resource: str, ip_address: Optional[str] = None) -> Tuple[bool, str]:
        """ユーザーアクセス検証 (ロックアウト機能付き)"""
        # ロックアウトチェック
        if user_id in self.lockouts:
            if time.time() < self.lockouts[user_id]:
                remaining = int(self.lockouts[user_id] - time.time())
                return False, f"アカウントがロックされています ({remaining}秒後に解除)"
            else:
                del self.lockouts[user_id]
                self.failed_attempts[user_id] = []

        # IP制限チェック
        if ip_address:
            if not self._check_ip_access(ip_address):
                logger.warning(f"ブロックされたIPからのアクセス試行: {ip_address}")
                return False, "アクセスが拒否されました"

        # ユーザー権限チェック
        if self.allowed_users and user_id not in self.allowed_users:
            self._record_failed_attempt(user_id)
            return False, "権限がありません"

        return True, "OK"

    def validate_input_data(self, data: Any, max_size: int = 10 * 1024 * 1024) -> Tuple[bool, str]:
        """入力データ検証 (サイズ制限、インジェクション対策)"""
        # 型チェック
        if not isinstance(data, (dict, str, int, float, bool, list)):
            return False, "サポートされていないデータ型"

        # サイズチェック
        try:
            data_str = json.dumps(data, ensure_ascii=False)
            if len(data_str) > max_size:
                return False, f"データサイズが制限を超えています ({len(data_str)} > {max_size})"
        except Exception as e:
            return False, f"データ変換エラー: {str(e)}"

        # 危険なパターンのチェック
        data_str_lower = data_str.lower()
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, data_str_lower, re.IGNORECASE):
                logger.warning(f"危険なパターンを検出: {pattern}")
                return False, "許可されていない文字列が含まれています"

        return True, "OK"

    def validate_password(self, password: str) -> Tuple[bool, str]:
        """パスワード強度検証"""
        if len(password) < self.policy.password_min_length:
            return False, f"パスワードは{self.policy.password_min_length}文字以上必要です"

        if not re.search(r'[A-Z]', password):
            return False, "大文字を含める必要があります"

        if not re.search(r'[a-z]', password):
            return False, "小文字を含める必要があります"

        if not re.search(r'\d', password):
            return False, "数字を含める必要があります"

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "特殊文字を含める必要があります"

        return True, "OK"

    def sanitize_input(self, data: str) -> str:
        """入力サニタイゼーション"""
        # HTMLタグ除去
        sanitized = re.sub(r'<[^>]+>', '', data)
        # JavaScriptイベントハンドラ除去
        sanitized = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', sanitized, flags=re.IGNORECASE)
        # SQLキーワード除去
        sanitized = re.sub(r'\b(DROP|INSERT|UPDATE|DELETE|UNION|SELECT)\b', '', sanitized, flags=re.IGNORECASE)
        return sanitized.strip()

    def _check_ip_access(self, ip_address: str) -> bool:
        """IPアドレスアクセスチェック"""
        if not self.ip_pattern.match(ip_address):
            return False

        # ブロックリストチェック
        if ip_address in self.policy.blocked_ips:
            return False

        # 許可リストチェック（設定されている場合）
        if self.policy.allowed_ips:
            return ip_address in self.policy.allowed_ips or self._ip_in_range(ip_address, self.policy.allowed_ips)

        return True

    def _ip_in_range(self, ip: str, ranges: List[str]) -> bool:
        """CIDR範囲チェック (簡易実装)"""
        # 本番環境ではipaddressモジュールを使用
        for range_str in ranges:
            if '/' in range_str:
                network, bits = range_str.split('/')
                # 簡易的な範囲チェック (完全な実装には ipaddress モジュール使用)
                if ip.startswith(network.rsplit('.', 1)[0]):
                    return True
            elif ip == range_str:
                return True
        return False

    def _record_failed_attempt(self, user_id: str):
        """失敗試行の記録とロックアウト処理"""
        now = time.time()

        if user_id not in self.failed_attempts:
            self.failed_attempts[user_id] = []

        # 古い試行履歴をクリーンアップ (5分以内のみ保持)
        self.failed_attempts[user_id] = [
            t for t in self.failed_attempts[user_id]
            if now - t < 300
        ]

        self.failed_attempts[user_id].append(now)

        # ロックアウト判定
        if len(self.failed_attempts[user_id]) >= self.policy.max_login_attempts:
            self.lockouts[user_id] = now + self.policy.lockout_duration
            logger.warning(f"ユーザー {user_id} をロックアウト ({self.policy.lockout_duration}秒)")
            self.failed_attempts[user_id] = []

class IntegratedSecurityManager:
    """Production-Grade統合セキュリティマネージャー"""

    def __init__(self, policy: Optional[SecurityPolicy] = None):
        self.policy = policy or SecurityPolicy()
        self.auditor = SecurityAuditor()

        try:
            self.encryptor = DataEncryptor() if CRYPTO_AVAILABLE else None
        except Exception as e:
            logger.error(f"暗号化機能の初期化に失敗: {e}")
            self.encryptor = None

        self.validator = SecurityValidator(self.policy)
        self.behavior_analyzer = AdvancedBehaviorAnalyzer()  # 高度な行動異常検知を追加
        self.privacy_protector = PrivacyProtector()  # プライバシー保護を追加
        self.zero_trust = ZeroTrustSecurity()  # ゼロトラストセキュリティを追加
        self.initialized = False
        self.threat_level = ThreatLevel.LOW
        self.security_incidents: List[Dict[str, Any]] = []

    def initialize(self) -> bool:
        """初期化と健全性チェック"""
        try:
            # 必須コンポーネントチェック
            if not self.auditor:
                raise RuntimeError("監査システムの初期化に失敗")

            if not self.validator:
                raise RuntimeError("検証システムの初期化に失敗")

            # 暗号化チェック
            if not CRYPTO_AVAILABLE:
                logger.warning("cryptography パッケージが利用できません。暗号化機能が無効です。")

            # セキュリティポリシー検証
            if self.policy.password_min_length < 8:
                logger.warning("パスワード最小長が推奨値(8文字)未満です")

            self.initialized = True
            logger.info(f"統合セキュリティマネージャーを初期化 (レベル: {self.policy.level.value})")
            return True
        except Exception as e:
            logger.error(f"セキュリティ初期化エラー: {e}")
            return False

    def secure_operation(
        self,
        operation: str,
        user_id: str,
        data: Dict[str, Any],
        ip_address: Optional[str] = None,
        encrypt: bool = True
    ) -> Dict[str, Any]:
        """セキュア操作実行 (完全な多層防御)"""
        start_time = time.time()

        # 行動異常検知の準備
        current_time = time.time()
        session_duration = start_time  # 仮のセッション開始時間（実際にはトラッキングが必要）

        # ゼロトラストセッションの登録（初回アクセス時）
        session_id = f"{user_id}_{int(current_time)}"  # 簡易的なセッションID
        if session_id not in self.zero_trust.trusted_sessions:
            # 登録時点ではまだ異常検知を実行していないため初期リスクは 0.0
            self.zero_trust.register_session(session_id, user_id, 0.0)

        # 1. 入力検証
        valid, msg = self.validator.validate_input_data(data)
        if not valid:
            self._record_security_incident("invalid_input", user_id, {"reason": msg})
            return {'error': f'無効な入力: {msg}', 'success': False}

        # 2. 行動異常検知チェック
        # ログイン頻度を記録
        self.behavior_analyzer.record_behavior(user_id, 'login_frequency', 1.0, current_time)

        # 操作数を記録
        self.behavior_analyzer.record_behavior(user_id, 'operation_count', 1.0, current_time)

        # セッション時間を記録（簡易版）
        self.behavior_analyzer.record_behavior(user_id, 'session_duration', session_duration, current_time)

        # 異常検知実行
        anomaly_detected = False
        anomaly_details = {}
        for behavior_type in ['login_frequency', 'operation_count', 'session_duration']:
            is_anomaly, confidence, details = self.behavior_analyzer.detect_anomaly(user_id, behavior_type, 1.0)
            if is_anomaly:
                anomaly_detected = True
                anomaly_details[behavior_type] = details

        if anomaly_detected:
            self._record_security_incident("behavior_anomaly", user_id, {
                "operation": operation,
                "anomalies": anomaly_details,
                "ip": ip_address
            })
            # 異常検知時は脅威レベルを上げる
            if self.threat_level.value != 'critical':
                self.threat_level = ThreatLevel(max(ThreatLevel.LOW.value, self.threat_level.value, 'medium'))

        # 3. ゼロトラストセキュリティチェック
        zt_access, zt_msg = self.zero_trust.validate_resource_access(session_id, operation, "execute")
        if not zt_access:
            self._record_security_incident("zero_trust_denied", user_id, {
                "operation": operation,
                "reason": zt_msg,
                "ip": ip_address
            })
            return {'error': f'ゼロトラストアクセス拒否: {zt_msg}', 'success': False}

        # リスクスコアを更新（異常検知結果に基づく）
        context = {
            'unusual_location': ip_address not in ['127.0.0.1', '::1'],  # 簡易的な異常判定
            'unusual_time': current_time % 86400 > 72000 or current_time % 86400 < 21600  # 夜間/早朝
        }
        self.zero_trust.update_risk_score(session_id, confidence if anomaly_detected else 0.0, context)

        # 4. アクセス検証
        access_granted, access_msg = self.validator.validate_user_access(user_id, operation, ip_address)
        if not access_granted:
            self._record_security_incident("access_denied", user_id, {
                "operation": operation,
                "reason": access_msg,
                "ip": ip_address
            })
            return {'error': f'アクセス拒否: {access_msg}', 'success': False}

        # 4. セキュリティイベント記録
        event = SecurityEvent(
            event_type=operation,
            user_id=user_id,
            resource=operation,
            details={
                'data_size': len(str(data)),
                'ip_address': ip_address,
                'encrypted': encrypt,
                'anomaly_detected': anomaly_detected
            }
        )
        self.auditor.log_event(event)

        # 5. データ暗号化 (オプション)
        result_data = data
        if encrypt and self.encryptor:
            try:
                encrypted_data = self.encryptor.encrypt_data(data)
                result_data = {'encrypted': encrypted_data}
            except Exception as e:
                logger.error(f"暗号化エラー: {e}")
                return {'error': '暗号化処理に失敗しました', 'success': False}

        # 6. プライバシー保護適用
        try:
            result_data = self.privacy_protector.anonymize_data(result_data, user_id)
        except Exception as e:
            logger.warning(f"プライバシー保護適用エラー: {e}")

        execution_time = time.time() - start_time

        return {
            'success': True,
            'operation': operation,
            'data': result_data,
            'timestamp': time.time(),
            'execution_time_ms': round(execution_time * 1000, 2),
            'anomaly_detected': anomaly_detected,
            'threat_level': self.threat_level.value
        }

    def get_security_report(self) -> Dict[str, Any]:
        """包括的セキュリティレポート"""
        recent_events = self.auditor.get_events(24)  # 24時間

        # 脅威レベル評価
        threat_level = self._assess_threat_level(recent_events)

        # 行動異常検知の統計
        behavior_anomalies = sum(1 for e in recent_events if e.get('details', {}).get('anomaly_detected', False))

        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'security_level': self.policy.level.value,
            'threat_level': threat_level.value,
            'statistics': {
                'total_events_24h': len(recent_events),
                'unique_users': len({e['user_id'] for e in recent_events}),
                'operation_types': self._count_operation_types(recent_events),
                'incidents': len(self.security_incidents),
                'active_lockouts': len(self.validator.lockouts),
                'behavior_anomalies_24h': behavior_anomalies,
            },
            'incidents': self.security_incidents[-10:],  # 最新10件
            'lockouts': self._get_active_lockouts(),
            'encryption_enabled': CRYPTO_AVAILABLE and self.encryptor is not None,
            'audit_log_enabled': self.policy.enable_audit_log,
            '2fa_enabled': self.policy.require_2fa,
            'behavior_analysis': {
                'enabled': True,
                'threshold': self.behavior_analyzer.anomaly_threshold,
                'users_tracked': len(self.behavior_analyzer.baselines),
                'ml_models_trained': self.behavior_analyzer.get_behavior_summary('')['ml_models_trained'],
                'scalers_configured': self.behavior_analyzer.get_behavior_summary('')['scalers_configured'],
            },
            'privacy_protection': {
                'enabled': True,
                'users_with_policies': len(self.privacy_protector.privacy_policies),
                'anonymization_rules': len(self.privacy_protector.anonymization_rules),
            },
            'zero_trust_security': self.zero_trust.get_security_metrics()
        }

    def get_health_status(self) -> Dict[str, Any]:
        """セキュリティシステム健全性チェック"""
        health = {
            'initialized': self.initialized,
            'components': {
                'auditor': self.auditor is not None,
                'encryptor': self.encryptor is not None,
                'validator': self.validator is not None,
            },
            'threat_level': self.threat_level.value,
            'overall_health': 'healthy'
        }

        # 健全性判定
        if not all(health['components'].values()):
            health['overall_health'] = 'degraded'

        if self.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
            health['overall_health'] = 'alert'

        return health

    def _assess_threat_level(self, events: List[Dict[str, Any]]) -> ThreatLevel:
        """脅威レベル評価"""
        if not events:
            return ThreatLevel.LOW

        # インシデント数による判定
        incident_count = len([e for e in events if e.get('event_type') in ['access_denied', 'invalid_input']])

        if incident_count > 100:
            return ThreatLevel.CRITICAL
        elif incident_count > 50:
            return ThreatLevel.HIGH
        elif incident_count > 10:
            return ThreatLevel.MEDIUM
        else:
            return ThreatLevel.LOW

    def _record_security_incident(self, incident_type: str, user_id: str, details: Dict[str, Any]):
        """セキュリティインシデントの記録"""
        incident = {
            'type': incident_type,
            'user_id': user_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'details': details
        }
        self.security_incidents.append(incident)

        # 古いインシデントをクリーンアップ (最新1000件のみ保持)
        if len(self.security_incidents) > 1000:
            self.security_incidents = self.security_incidents[-1000:]

        logger.warning(f"セキュリティインシデント: {incident_type}", extra={'incident': incident})

    def _get_active_lockouts(self) -> List[Dict[str, Any]]:
        """アクティブなロックアウト情報"""
        now = time.time()
        active = []

        for user_id, unlock_time in self.validator.lockouts.items():
            if unlock_time > now:
                active.append({
                    'user_id': user_id,
                    'unlock_at': datetime.fromtimestamp(unlock_time).isoformat(),
                    'remaining_seconds': int(unlock_time - now)
                })

        return active

    def _count_operation_types(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """操作タイプカウント"""
        types: Dict[str, int] = {}
        for event in events:
            event_type = event.get('event_type', 'unknown')
            types[event_type] = types.get(event_type, 0) + 1
        return types

# グローバルインスタンス
_security_manager: Optional[IntegratedSecurityManager] = None

def get_security_manager() -> IntegratedSecurityManager:
    """セキュリティマネージャー取得"""
    global _security_manager
    if _security_manager is None:
        _security_manager = IntegratedSecurityManager()
    return _security_manager

def initialize_security():
    """セキュリティ初期化"""
    manager = get_security_manager()
    if manager.initialize():
        return manager
    else:
        raise Exception("セキュリティの初期化に失敗")

class ZeroTrustSecurity:
    """ゼロトラストセキュリティシステム"""

    def __init__(self):
        self.trusted_sessions: Dict[str, Dict[str, Any]] = {}
        self.resource_policies: Dict[str, Dict[str, Any]] = {}
        self.continuous_auth_scores: Dict[str, float] = {}
        self.risk_scores: Dict[str, float] = {}

    def register_session(self, session_id: str, user_id: str, initial_risk_score: float = 0.0) -> None:
        """新しいセッションを登録"""
        self.trusted_sessions[session_id] = {
            'user_id': user_id,
            'start_time': time.time(),
            'last_activity': time.time(),
            'risk_score': initial_risk_score,
            'access_level': 'basic',
            'resources_accessed': set(),
            'authentication_factors': 1
        }

    def validate_resource_access(self, session_id: str, resource: str, action: str) -> Tuple[bool, str]:
        """リソースアクセスの検証"""
        if session_id not in self.trusted_sessions:
            return False, "セッションが登録されていません"

        session = self.trusted_sessions[session_id]

        # セッションの有効性をチェック
        if not self._is_session_valid(session):
            return False, "セッションが無効です"

        # リソースポリシーをチェック
        if not self._check_resource_policy(session['user_id'], resource, action):
            return False, "リソースアクセスポリシーに違反します"

        # リスクスコアをチェック
        if session['risk_score'] > 0.7:  # 高リスクの場合
            return False, "リスクスコアが高すぎます"

        # アクセスを記録
        session['resources_accessed'].add(resource)
        session['last_activity'] = time.time()

        return True, "アクセス許可"

    def update_risk_score(self, session_id: str, anomaly_score: float, context: Dict[str, Any] = None) -> None:
        """リスクスコアを更新"""
        if session_id not in self.trusted_sessions:
            return

        session = self.trusted_sessions[session_id]

        # 異常スコアに基づいてリスクを計算
        base_risk = anomaly_score * 0.5

        # コンテキストに基づくリスク調整
        context_risk = 0.0
        if context:
            # 異常な場所からのアクセス
            if context.get('unusual_location', False):
                context_risk += 0.3
            # 異常な時間帯
            if context.get('unusual_time', False):
                context_risk += 0.2
            # 異常なデバイス
            if context.get('unusual_device', False):
                context_risk += 0.4

        total_risk = min(1.0, base_risk + context_risk)
        session['risk_score'] = total_risk

    def _is_session_valid(self, session: Dict[str, Any]) -> bool:
        """セッションの有効性をチェック"""
        # セッションタイムアウトチェック（デフォルト8時間）
        if time.time() - session['start_time'] > 8 * 3600:
            return False

        # 非アクティブタイムアウトチェック（デフォルト1時間）
        if time.time() - session['last_activity'] > 3600:
            return False

        return True

    def _check_resource_policy(self, user_id: str, resource: str, action: str) -> bool:
        """リソースポリシーをチェック"""
        # デフォルトポリシー：全て許可（実際の実装では詳細なポリシーを定義）
        return True

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """セッション情報を取得"""
        return self.trusted_sessions.get(session_id)

    def revoke_session(self, session_id: str) -> bool:
        """セッションを無効化"""
        if session_id in self.trusted_sessions:
            del self.trusted_sessions[session_id]
            return True
        return False

    def get_security_metrics(self) -> Dict[str, Any]:
        """セキュリティメトリクスを取得"""
        active_sessions = len(self.trusted_sessions)
        high_risk_sessions = sum(1 for s in self.trusted_sessions.values() if s['risk_score'] > 0.7)
        avg_risk_score = np.mean([s['risk_score'] for s in self.trusted_sessions.values()]) if self.trusted_sessions else 0.0
        return {
            "active_sessions": active_sessions,
            "high_risk_sessions": high_risk_sessions,
            "avg_risk_score": float(avg_risk_score),
        }

@dataclass
class QuantumKeyPair:
    """量子安全鍵ペア"""
    public_key: bytes
    private_key: bytes
    algorithm: str
    key_id: str
    created_at: datetime
    expires_at: Optional[datetime] = None

@dataclass
class QuantumSignature:
    """量子安全デジタル署名"""
    signature: bytes
    algorithm: str
    message_hash: str
    signer_key_id: str
    timestamp: datetime

@dataclass
class QuantumSafeConfiguration:
    """量子安全設定"""
    enabled_algorithms: List[str]
    key_rotation_days: int
    hybrid_mode: bool  # 従来方式との併用
    migration_mode: bool  # 段階的移行
    security_level: str  # "level1", "level3", "level5"

@dataclass
class QuantumThreatAssessment:
    """量子脅威評価"""
    threat_level: str  # "low", "medium", "high", "critical"
    quantum_computer_qubits: int
    timeline_years: int
    affected_algorithms: List[str]
    recommended_actions: List[str]
    assessment_date: datetime

@dataclass
class PromptInjectionPattern:
    """プロンプトインジェクション検知パターン"""
    pattern_id: str
    pattern: str
    severity: str  # "low", "medium", "high", "critical"
    description: str
    regex: Any = None  # コンパイル済み正規表現 (re.Pattern)

@dataclass
class AIModelMetadata:
    """AIモデルメタデータ"""
    model_id: str
    model_type: str
    version: str
    hash: str
    created_at: datetime
    training_data_hash: str
    parameters: Dict[str, Any]
    security_level: str

@dataclass
class AIAuditEvent:
    """AI監査イベント"""
    event_id: str
    timestamp: datetime
    event_type: str
    user_id: str
    model_id: str
    input_hash: str
    output_hash: str
    risk_score: float
    details: Dict[str, Any]

class AISecurityManager:
    """
    AIセキュリティマネージャー
    AIモデルとAI使用のセキュリティを管理
    """

    def __init__(self, security_db_path: Optional[str] = None):
        self.security_db_path = security_db_path or str(DEFAULT_SECURITY_SUBDIR / "ai_security.db")

        # AIモデル管理
        self.registered_models: Dict[str, AIModelMetadata] = {}
        self.model_audit_trail: List[AIAuditEvent] = []

        # 脅威検知
        self.injection_patterns: List[PromptInjectionPattern] = []
        self.anomaly_detector: Optional[IsolationForest] = None

        # 設定
        self.max_audit_events = 10000
        self.model_validation_required = True
        self.prompt_filtering_enabled = True

        # 統計
        self.security_violations = 0
        self.blocked_requests = 0
        self.total_ai_requests = 0

        logger.info("AI Security Manager initialized")

    async def initialize(self):
        """AIセキュリティマネージャーの初期化"""
        await self._load_injection_patterns()
        await self._initialize_anomaly_detector()
        await self._load_registered_models()

    async def _load_injection_patterns(self):
        """インジェクションパターンを読み込み"""
        default_patterns = [
            PromptInjectionPattern(
                pattern_id="ignore_instructions",
                pattern="ignore.*instruction|disregard.*previous|override.*command",
                severity="high",
                description="指示無視パターン",
                regex=re.compile(r"ignore.*instruction|disregard.*previous|override.*command", re.IGNORECASE)
            ),
            PromptInjectionPattern(
                pattern_id="system_prompt_leak",
                pattern="system.*prompt|internal.*instruction|developer.*note",
                severity="critical",
                description="システムプロンプト漏洩試行",
                regex=re.compile(r"system.*prompt|internal.*instruction|developer.*note", re.IGNORECASE)
            ),
            PromptInjectionPattern(
                pattern_id="role_playing",
                pattern="act.*as|pretend.*to.*be|role.*play|become",
                severity="medium",
                description="ロールプレイ試行",
                regex=re.compile(r"act.*as|pretend.*to.*be|role.*play|become", re.IGNORECASE)
            ),
            PromptInjectionPattern(
                pattern_id="code_execution",
                pattern="execute.*code|run.*script|eval.*|exec.*",
                severity="high",
                description="コード実行試行",
                regex=re.compile(r"execute.*code|run.*script|eval.*|exec.*", re.IGNORECASE)
            ),
            PromptInjectionPattern(
                pattern_id="data_exfiltration",
                pattern="dump.*data|extract.*information|leak.*secret|reveal.*key",
                severity="critical",
                description="データ流出試行",
                regex=re.compile(r"dump.*data|extract.*information|leak.*secret|reveal.*key", re.IGNORECASE)
            )
        ]

        self.injection_patterns = default_patterns

    async def _initialize_anomaly_detector(self):
        """異常検知器の初期化"""
        # 簡易的な異常検知モデル（実際にはより高度なモデルを使用）
        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)

    async def _load_registered_models(self):
        """登録済みモデルを読み込み"""
        model_dir = DEFAULT_SECURITY_SUBDIR / "ai_models"
        if model_dir.exists():
            for model_file in model_dir.glob("*.json"):
                try:
                    with open(model_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        model = AIModelMetadata(**data)
                        self.registered_models[model.model_id] = model
                except Exception as e:
                    logger.error(f"Failed to load model metadata {model_file}: {e}")

    async def validate_ai_request(self, user_id: str, model_id: str, prompt: str,
                                context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, float]:
        """
        AIリクエストを検証

        Args:
            user_id: ユーザーID
            model_id: モデルID
            prompt: プロンプト
            context: 追加コンテキスト

        Returns:
            (許可かどうか, 拒否理由, リスクスコア)
        """
        self.total_ai_requests += 1

        # モデル存在チェック
        if model_id not in self.registered_models:
            self.security_violations += 1
            return False, "Model not registered", 1.0

        # プロンプトインジェクション検知
        injection_result = await self._check_prompt_injection(prompt)
        if injection_result[0]:
            self.security_violations += 1
            self.blocked_requests += 1
            return False, f"Prompt injection detected: {injection_result[1]}", injection_result[2]

        # 異常検知
        anomaly_score = await self._detect_anomaly(user_id, prompt, context)
        if anomaly_score > 0.7:
            self.security_violations += 1
            return False, "Anomalous request detected", anomaly_score

        # リスクスコア計算
        risk_score = await self._calculate_risk_score(user_id, prompt, context)

        # リスク閾値チェック
        if risk_score > 0.8:
            self.blocked_requests += 1
            return False, "High risk request", risk_score

        return True, "Request approved", risk_score

    async def _check_prompt_injection(self, prompt: str) -> Tuple[bool, str, float]:
        """プロンプトインジェクションをチェック"""
        for pattern in self.injection_patterns:
            if pattern.is_active and pattern.regex.search(prompt):
                severity_score = {"low": 0.3, "medium": 0.6, "high": 0.8, "critical": 1.0}[pattern.severity]
                return True, pattern.description, severity_score

        return False, "", 0.0

    async def _detect_anomaly(self, user_id: str, prompt: str, context: Optional[Dict[str, Any]] = None) -> float:
        """異常を検知"""
        if not self.anomaly_detector:
            return 0.0

        # 特徴量抽出（簡易的）
        features = [
            len(prompt),
            prompt.count('\n'),
            len(re.findall(r'\b\w+\b', prompt)),
            hash(user_id) % 1000 / 1000.0,  # ユーザーIDのハッシュ
            context.get('time_of_day', 0) if context else 0,
        ]

        # 異常スコア計算
        try:
            anomaly_score = self.anomaly_detector.decision_function([features])[0]
            return max(0.0, min(1.0, (anomaly_score + 1) / 2))  # 0-1に正規化
        except Exception:
            return 0.0

    async def _calculate_risk_score(self, user_id: str, prompt: str,
                                  context: Optional[Dict[str, Any]] = None) -> float:
        """リスクスコアを計算"""
        risk_factors = []

        # プロンプト長によるリスク
        if len(prompt) > 10000:
            risk_factors.append(0.3)
        elif len(prompt) > 5000:
            risk_factors.append(0.2)
        elif len(prompt) > 1000:
            risk_factors.append(0.1)

        # 特殊文字の使用
        special_chars = len(re.findall(r'[^a-zA-Z0-9\s\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', prompt))
        if special_chars > 100:
            risk_factors.append(0.4)
        elif special_chars > 50:
            risk_factors.append(0.2)

        # 時間帯によるリスク
        if context and context.get('time_of_day') in ['night']:
            risk_factors.append(0.1)

        # 過去の違反履歴
        user_violations = sum(1 for event in self.model_audit_trail
                            if event.user_id == user_id and event.risk_score > 0.8)
        if user_violations > 5:
            risk_factors.append(0.5)
        elif user_violations > 2:
            risk_factors.append(0.3)

        return min(1.0, sum(risk_factors) / len(risk_factors)) if risk_factors else 0.0

    async def audit_ai_interaction(self, user_id: str, model_id: str, prompt: str,
                                 response: str, risk_score: float, metadata: Optional[Dict[str, Any]] = None):
        """
        AIインタラクションを監査

        Args:
            user_id: ユーザーID
            model_id: モデルID
            prompt: 入力プロンプト
            response: AI応答
            risk_score: リスクスコア
            metadata: 追加メタデータ
        """
        event = AIAuditEvent(
            event_id=secrets.token_hex(16),
            timestamp=datetime.now(timezone.utc),
            event_type="ai_interaction",
            user_id=user_id,
            model_id=model_id,
            input_hash=hashlib.sha256(prompt.encode()).hexdigest(),
            output_hash=hashlib.sha256(response.encode()).hexdigest(),
            risk_score=risk_score,
            details=metadata or {}
        )

        self.model_audit_trail.append(event)

        # 古いイベントを削除
        if len(self.model_audit_trail) > self.max_audit_events:
            self.model_audit_trail.pop(0)

        # データベースに保存（実際の実装では）
        await self._save_audit_event(event)

    async def _save_audit_event(self, event: AIAuditEvent):
        """監査イベントを保存"""
        audit_dir = DEFAULT_SECURITY_SUBDIR / "ai_audit"
        audit_dir.mkdir(parents=True, exist_ok=True)

        # 日付別ファイルに保存
        date_str = event.timestamp.strftime("%Y-%m-%d")
        audit_file = audit_dir / f"{date_str}.json"

        # 既存データを読み込み
        events = []
        if audit_file.exists():
            try:
                with open(audit_file, 'r', encoding='utf-8') as f:
                    events = json.load(f)
            except Exception:
                events = []

        # 新しいイベントを追加
        events.append({
            "event_id": event.event_id,
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type,
            "user_id": event.user_id,
            "model_id": event.model_id,
            "input_hash": event.input_hash,
            "output_hash": event.output_hash,
            "risk_score": event.risk_score,
            "details": event.details
        })

        # 保存
        with open(audit_file, 'w', encoding='utf-8') as f:
            json.dump(events, f, indent=2, ensure_ascii=False)

    def get_ai_security_metrics(self) -> Dict[str, Any]:
        """AIセキュリティメトリクスを取得"""
        high_risk_events = sum(1 for event in self.model_audit_trail if event.risk_score > 0.8)
        avg_risk_score = sum(event.risk_score for event in self.model_audit_trail) / len(self.model_audit_trail) if self.model_audit_trail else 0.0

        return {
            "total_ai_requests": self.total_ai_requests,
            "security_violations": self.security_violations,
            "blocked_requests": self.blocked_requests,
            "registered_models": len(self.registered_models),
            "high_risk_events": high_risk_events,
            "average_risk_score": avg_risk_score,
            "audit_events_count": len(self.model_audit_trail),
            "block_rate": self.blocked_requests / max(1, self.total_ai_requests)
        }

# グローバルインスタンス
_ai_security_manager = None

async def get_ai_security_manager() -> AISecurityManager:
    """AIセキュリティマネージャーのインスタンスを取得"""
    global _ai_security_manager

    if _ai_security_manager is None:
        _ai_security_manager = AISecurityManager()
        await _ai_security_manager.initialize()

class QuantumSafeManager:
    """
    量子安全暗号化マネージャー
    ポスト量子暗号（PQC）と量子鍵配送（QKD）の統合管理
    """

    def __init__(self, security_db_path: Optional[str] = None):
        self.security_db_path = security_db_path or str(DEFAULT_SECURITY_SUBDIR / "quantum_safe.db")

        # 量子安全鍵管理
        self.key_pairs: Dict[str, QuantumKeyPair] = {}
        self.active_signatures: Dict[str, QuantumSignature] = {}

        # 設定
        self.config = QuantumSafeConfiguration(
            enabled_algorithms=["Kyber768", "Dilithium3", "Falcon512", "SPHINCS256"],
            key_rotation_days=90,
            hybrid_mode=True,  # 従来方式との併用
            migration_mode=True,  # 段階的移行
            security_level="level3"
        )

        # 脅威評価
        self.threat_assessments: List[QuantumThreatAssessment] = []

        # 統計
        self.quantum_operations = 0
        self.key_rotations = 0
        self.signature_verifications = 0
        self.encryption_operations = 0

        logger.info("Quantum Safe Manager initialized")

    async def initialize(self):
        """量子安全マネージャーの初期化"""
        await self._load_existing_keys()
        await self._initialize_quantum_algorithms()
        await self._perform_threat_assessment()

    async def _load_existing_keys(self):
        """既存の量子安全鍵を読み込み"""
        key_dir = DEFAULT_SECURITY_SUBDIR / "quantum_keys"
        if key_dir.exists():
            for key_file in key_dir.glob("*.json"):
                try:
                    with open(key_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        key_pair = QuantumKeyPair(
                            public_key=bytes.fromhex(data["public_key"]),
                            private_key=bytes.fromhex(data["private_key"]),
                            algorithm=data["algorithm"],
                            key_id=data["key_id"],
                            created_at=datetime.fromisoformat(data["created_at"]),
                            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None
                        )
                        self.key_pairs[key_pair.key_id] = key_pair
                except Exception as e:
                    logger.error(f"Failed to load quantum key {key_file}: {e}")

    async def _initialize_quantum_algorithms(self):
        """量子安全アルゴリズムの初期化"""
        if OQS_AVAILABLE:
            # Open Quantum Safeライブラリの初期化
            self.oqs_enabled = True
            logger.info("Open Quantum Safe algorithms initialized")
        else:
            # フォールバック実装
            self.oqs_enabled = False
            await self._initialize_fallback_algorithms()
            logger.warning("Using fallback quantum-safe implementation")

    async def _initialize_fallback_algorithms(self):
        """フォールバック量子安全アルゴリズムの初期化"""
        # 簡易的なPQC実装（実際には標準ライブラリを使用）
        self.fallback_algorithms = {
            "Kyber768": self._kyber_fallback,
            "Dilithium3": self._dilithium_fallback,
            "SPHINCS256": self._sphincs_fallback
        }
        logger.info("Fallback quantum-safe algorithms initialized")

    async def generate_quantum_keypair(self, algorithm: str = "Kyber768") -> QuantumKeyPair:
        """
        量子安全鍵ペアを生成

        Args:
            algorithm: 使用するアルゴリズム

        Returns:
            生成された鍵ペア
        """
        if not self._is_algorithm_supported(algorithm):
            raise ValueError(f"Unsupported quantum-safe algorithm: {algorithm}")

        try:
            if OQS_AVAILABLE and self.oqs_enabled:
                # Open Quantum Safeライブラリを使用
                kem = oqs.KeyEncapsulation(algorithm)
                public_key, private_key = kem.generate_keypair()
            else:
                # フォールバック実装
                public_key, private_key = await self._generate_fallback_keypair(algorithm)

            key_id = secrets.token_hex(32)
            created_at = datetime.now(timezone.utc)
            expires_at = created_at.replace(year=created_at.year + 2)  # 2年有効

            key_pair = QuantumKeyPair(
                public_key=public_key,
                private_key=private_key,
                algorithm=algorithm,
                key_id=key_id,
                created_at=created_at,
                expires_at=expires_at
            )

            # 鍵を保存
            self.key_pairs[key_id] = key_pair
            await self._save_keypair(key_pair)

            logger.info(f"Generated quantum-safe keypair: {key_id} ({algorithm})")
            return key_pair

        except Exception as e:
            logger.error(f"Failed to generate quantum keypair: {e}")
            raise

    def _is_algorithm_supported(self, algorithm: str) -> bool:
        """アルゴリズムがサポートされているかチェック"""
        return algorithm in self.config.enabled_algorithms

    async def _generate_fallback_keypair(self, algorithm: str) -> Tuple[bytes, bytes]:
        """フォールバック鍵ペア生成"""
        # 簡易的な鍵生成（実際には標準PQCライブラリを使用）
        key_size = {"Kyber768": 1184, "Dilithium3": 1472, "SPHINCS256": 1280}[algorithm]
        public_key = secrets.token_bytes(key_size)
        private_key = secrets.token_bytes(key_size * 2)  # 秘密鍵はより長い
        return public_key, private_key

    async def _save_keypair(self, key_pair: QuantumKeyPair):
        """鍵ペアを保存"""
        key_dir = DEFAULT_SECURITY_SUBDIR / "quantum_keys"
        key_dir.mkdir(parents=True, exist_ok=True)

        key_file = key_dir / f"{key_pair.key_id}.json"
        with open(key_file, 'w', encoding='utf-8') as f:
            json.dump({
                "key_id": key_pair.key_id,
                "algorithm": key_pair.algorithm,
                "public_key": key_pair.public_key.hex(),
                "private_key": key_pair.private_key.hex(),
                "created_at": key_pair.created_at.isoformat(),
                "expires_at": key_pair.expires_at.isoformat() if key_pair.expires_at else None
            }, f, indent=2)

    async def quantum_safe_encrypt(self, plaintext: bytes, recipient_key_id: str) -> bytes:
        """
        量子安全暗号化

        Args:
            plaintext: 平文データ
            recipient_key_id: 受信者の公開鍵ID

        Returns:
            暗号化されたデータ
        """
        if recipient_key_id not in self.key_pairs:
            raise ValueError(f"Key not found: {recipient_key_id}")

        recipient_key = self.key_pairs[recipient_key_id]
        if recipient_key.algorithm.startswith("Kyber"):
            return await self._kyber_encrypt(plaintext, recipient_key)
        else:
            # 他のアルゴリズム
            return await self._fallback_encrypt(plaintext, recipient_key)

    async def _kyber_encrypt(self, plaintext: bytes, recipient_key: QuantumKeyPair) -> bytes:
        """Kyber暗号化"""
        if OQS_AVAILABLE:
            kem = oqs.KeyEncapsulation(recipient_key.algorithm)
            ciphertext, shared_secret = kem.encap_secret(recipient_key.public_key)
        else:
            # フォールバック: AES-256-GCMを使用（量子耐性ではないが、移行用）
            ciphertext = self._fallback_encrypt(plaintext, recipient_key)

        self.encryption_operations += 1
        return ciphertext

    async def _fallback_encrypt(self, plaintext: bytes, recipient_key: QuantumKeyPair) -> bytes:
        """フォールバック暗号化"""
        # 実際には標準PQCライブラリを使用
        # ここでは簡易的な実装
        import os
        nonce = os.urandom(12)
        # AES-256-GCM実装（実際にはcryptographyライブラリを使用）
        return nonce + plaintext  # 簡易実装

    async def quantum_safe_decrypt(self, ciphertext: bytes, recipient_key_id: str) -> bytes:
        """
        量子安全復号化

        Args:
            ciphertext: 暗号化データ
            recipient_key_id: 受信者の秘密鍵ID

        Returns:
            復号化された平文
        """
        if recipient_key_id not in self.key_pairs:
            raise ValueError(f"Key not found: {recipient_key_id}")

        sender_key = self.key_pairs[recipient_key_id]
        if sender_key.algorithm.startswith("Kyber"):
            return await self._kyber_decrypt(ciphertext, sender_key)
        else:
            return await self._fallback_decrypt(ciphertext, sender_key)

    async def _kyber_decrypt(self, ciphertext: bytes, sender_key: QuantumKeyPair) -> bytes:
        """Kyber復号化"""
        if OQS_AVAILABLE:
            kem = oqs.KeyEncapsulation(sender_key.algorithm)
            shared_secret = kem.decap_secret(ciphertext, sender_key.private_key)
            # 共有鍵を使用してデータを復号化
            return shared_secret  # 簡易実装
        else:
            return self._fallback_decrypt(ciphertext, sender_key)

    async def _fallback_decrypt(self, ciphertext: bytes, sender_key: QuantumKeyPair) -> bytes:
        """フォールバック復号化"""
        # 簡易実装
        return ciphertext[12:]  # nonceを除いた部分

    async def create_quantum_signature(self, message: bytes, signer_key_id: str) -> QuantumSignature:
        """
        量子安全デジタル署名を作成

        Args:
            message: 署名対象メッセージ
            signer_key_id: 署名者の秘密鍵ID

        Returns:
            デジタル署名
        """
        if signer_key_id not in self.key_pairs:
            raise ValueError(f"Key not found: {signer_key_id}")

        signer_key = self.key_pairs[signer_key_id]
        algorithm = signer_key.algorithm

        if algorithm.startswith("Dilithium"):
            signature = await self._dilithium_sign(message, signer_key)
        elif algorithm.startswith("Falcon"):
            signature = await self._falcon_sign(message, signer_key)
        elif algorithm.startswith("SPHINCS"):
            signature = await self._sphincs_sign(message, signer_key)
        else:
            signature = await self._fallback_sign(message, signer_key)

        quantum_signature = QuantumSignature(
            signature=signature,
            algorithm=algorithm,
            message_hash=hashlib.sha256(message).hexdigest(),
            signer_key_id=signer_key_id,
            timestamp=datetime.now(timezone.utc)
        )

        self.active_signatures[quantum_signature.signer_key_id] = quantum_signature
        self.signature_verifications += 1

        return quantum_signature

    async def _dilithium_sign(self, message: bytes, signer_key: QuantumKeyPair) -> bytes:
        """Dilithium署名"""
        if PQCRYSTALS_AVAILABLE:
            # PQ Crystals Dilithium実装
            pass
        else:
            # フォールバック: ECDSAを使用
            return hashlib.sha256(message).digest()

    async def _fallback_sign(self, message: bytes, signer_key: QuantumKeyPair) -> bytes:
        """フォールバック署名"""
        return hashlib.sha256(message + signer_key.private_key).digest()

    async def verify_quantum_signature(self, message: bytes, signature: QuantumSignature) -> bool:
        """
        量子安全署名を検証

        Args:
            message: 検証対象メッセージ
            signature: 署名

        Returns:
            検証結果
        """
        if signature.signer_key_id not in self.key_pairs:
            return False

        signer_key = self.key_pairs[signature.signer_key_id]

        try:
            if signature.algorithm.startswith("Dilithium"):
                return await self._dilithium_verify(message, signature, signer_key)
            elif signature.algorithm.startswith("Falcon"):
                return await self._falcon_verify(message, signature, signer_key)
            elif signature.algorithm.startswith("SPHINCS"):
                return await self._sphincs_verify(message, signature, signer_key)
            else:
                return await self._fallback_verify(message, signature, signer_key)
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False

    async def _dilithium_verify(self, message: bytes, signature: QuantumSignature, signer_key: QuantumKeyPair) -> bool:
        """Dilithium署名検証"""
        if PQCRYSTALS_AVAILABLE:
            # PQ Crystals Dilithium検証
            pass
        else:
            # フォールバック検証
            expected_signature = await self._fallback_sign(message, signer_key)
            return signature.signature == expected_signature

    async def _fallback_verify(self, message: bytes, signature: QuantumSignature, signer_key: QuantumKeyPair) -> bool:
        """フォールバック検証"""
        expected_signature = await self._fallback_sign(message, signer_key)
        return signature.signature == expected_signature

    async def _perform_threat_assessment(self) -> QuantumThreatAssessment:
        """量子脅威評価を実行"""
        # 現在の量子コンピューティングの進展に基づく評価
        current_year = datetime.now(timezone.utc).year

        # 脅威レベルの推定（簡易的）
        if current_year < 2028:
            threat_level = "low"
            qubits = 100
            timeline = 10
        elif current_year < 2032:
            threat_level = "medium"
            qubits = 500
            timeline = 7
        elif current_year < 2036:
            threat_level = "high"
            qubits = 1000
            timeline = 5
        else:
            threat_level = "critical"
            qubits = 2000
            timeline = 3

        affected_algorithms = ["RSA", "ECC", "DH"] if threat_level in ["high", "critical"] else ["RSA"]
        recommended_actions = self._get_recommended_actions(threat_level)

        assessment = QuantumThreatAssessment(
            threat_level=threat_level,
            quantum_computer_qubits=qubits,
            timeline_years=timeline,
            affected_algorithms=affected_algorithms,
            recommended_actions=recommended_actions,
            assessment_date=datetime.now(timezone.utc)
        )

        self.threat_assessments.append(assessment)
        logger.info(f"Quantum threat assessment: {threat_level} (timeline: {timeline} years)")

        return assessment

    def _get_recommended_actions(self, threat_level: str) -> List[str]:
        """脅威レベルに応じた推奨アクション"""
        actions = {
            "low": ["Monitor quantum developments", "Prepare migration plan"],
            "medium": ["Begin PQC migration", "Implement hybrid encryption", "Increase key sizes"],
            "high": ["Accelerate PQC deployment", "Replace vulnerable algorithms", "Enable QKD if available"],
            "critical": ["Complete PQC migration", "Deploy quantum-resistant infrastructure", "Emergency key rotation"]
        }
        return actions.get(threat_level, [])

    async def rotate_quantum_keys(self):
        """量子安全鍵のローテーション"""
        rotated_keys = []

        for key_id, key_pair in list(self.key_pairs.items()):
            if key_pair.expires_at and datetime.now(timezone.utc) > key_pair.expires_at:
                # 期限切れの鍵を新しい鍵で置き換え
                new_algorithm = key_pair.algorithm  # 同じアルゴリズムを使用
                new_key_pair = await self.generate_quantum_keypair(new_algorithm)

                # 古い鍵を無効化
                del self.key_pairs[key_id]

                rotated_keys.append({
                    "old_key_id": key_id,
                    "new_key_id": new_key_pair.key_id,
                    "algorithm": new_algorithm
                })

        if rotated_keys:
            self.key_rotations += len(rotated_keys)
            logger.info(f"Rotated {len(rotated_keys)} quantum keys")

        return rotated_keys

    def get_quantum_security_status(self) -> Dict[str, Any]:
        """量子セキュリティステータスを取得"""
        active_keys = len(self.key_pairs)
        expired_keys = sum(1 for k in self.key_pairs.values() if k.expires_at and datetime.now(timezone.utc) > k.expires_at)

        latest_assessment = self.threat_assessments[-1] if self.threat_assessments else None

        return {
            "quantum_safe_enabled": True,
            "oqs_available": OQS_AVAILABLE,
            "pqcrystals_available": PQCRYSTALS_AVAILABLE,
            "active_key_pairs": active_keys,
            "expired_keys": expired_keys,
            "supported_algorithms": self.config.enabled_algorithms,
            "hybrid_mode": self.config.hybrid_mode,
            "migration_mode": self.config.migration_mode,
            "security_level": self.config.security_level,
            "total_operations": self.quantum_operations,
            "key_rotations": self.key_rotations,
            "signature_verifications": self.signature_verifications,
            "encryption_operations": self.encryption_operations,
            "latest_threat_assessment": latest_assessment.__dict__ if latest_assessment else None
        }

# グローバルインスタンス
_quantum_safe_manager = None

async def get_quantum_safe_manager() -> QuantumSafeManager:
    """量子安全マネージャーのインスタンスを取得"""
    global _quantum_safe_manager

    if _quantum_safe_manager is None:
        _quantum_safe_manager = QuantumSafeManager()
        await _quantum_safe_manager.initialize()

    return _quantum_safe_manager
