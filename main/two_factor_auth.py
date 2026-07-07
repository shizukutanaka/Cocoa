"""
2要素認証 (2FA) システム - Production-Grade Two-Factor Authentication

国家レベルの運用に耐えうる2要素認証機能:
- TOTP (Time-based One-Time Password) アルゴリズム
- QRコードによる簡単セットアップ
- 複数のバックアップコード
- デバイス紛失時の回復機能
- 監査証跡付きの完全なログ記録
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import struct
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    qrcode = None
import io

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except (KeyboardInterrupt, SystemExit):
    raise
except BaseException:
    # BaseException (not just Exception) because a broken native crypto
    # binding can raise pyo3 PanicException, which is not an Exception.
    # KeyboardInterrupt / SystemExit are re-raised above so import-time
    # Ctrl+C / sys.exit() still work.
    CRYPTO_AVAILABLE = False
    Fernet = None
    hashes = None
    PBKDF2HMAC = None

logger = logging.getLogger(__name__)

class TOTPGenerator:
    """TOTP (Time-based One-Time Password) ジェネレーター"""

    def __init__(self, secret: str, digits: int = 6, interval: int = 30):
        """TOTPジェネレーターを初期化"""
        self.secret = secret
        self.digits = digits
        self.interval = interval

    def _hmac_sha1(self, key: bytes, message: bytes) -> bytes:
        """HMAC-SHA1計算"""
        return hmac.new(key, message, hashlib.sha1).digest()

    def _truncate(self, digest: bytes) -> int:
        """ダイナミック・トランケーション"""
        offset = digest[-1] & 0x0F
        binary = ((digest[offset] & 0x7F) << 24) | \
                ((digest[offset + 1] & 0xFF) << 16) | \
                ((digest[offset + 2] & 0xFF) << 8) | \
                (digest[offset + 3] & 0xFF)
        return binary % (10 ** self.digits)

    def generate_token(self, timestamp: Optional[int] = None) -> str:
        """TOTPトークンを生成"""
        if timestamp is None:
            timestamp = int(time.time())

        # タイムステップを計算
        time_step = timestamp // self.interval

        # 秘密鍵をデコード
        key = base64.b32decode(self.secret)

        # タイムステップをバイト列に変換（ビッグエンディアン）
        time_bytes = struct.pack('>Q', time_step)

        # HMAC計算
        digest = self._hmac_sha1(key, time_bytes)

        # トランケーションとフォーマット
        token = self._truncate(digest)
        return str(token).zfill(self.digits)

    def verify_token(self, token: str, window: int = 1) -> bool:
        """TOTPトークンを検証"""
        current_time = int(time.time())

        for offset in range(-window, window + 1):
            timestamp = current_time + (offset * self.interval)
            if hmac.compare_digest(self.generate_token(timestamp), token):
                return True

        return False

    def get_remaining_time(self) -> int:
        """次のトークン生成までの残り時間を取得（秒）"""
        current_time = int(time.time())
        return self.interval - (current_time % self.interval)


class TwoFactorStore:
    """Thread-safe in-memory persistence for 2FA secrets and backup codes.

    Matches this codebase's established in-memory-singleton pattern (cart,
    wishlist, gift_card, membership, license, etc. stores all work this way).

    Before this class existed, TwoFactorAuthService always constructed
    TwoFactorAuthManager with db_manager=None, so every method that depends on
    persistence (_get_user_secret, _get_user_backup_codes) fell into its
    documented fail-closed path unconditionally: setup_2fa generated and
    returned real secrets/codes to the caller, but nothing was ever stored, so
    enable_2fa / verify_2fa_token / verify_backup_code always failed, and
    get_2fa_status always reported hardcoded False/None regardless of what
    setup_2fa had returned. 2FA was fully non-functional end-to-end.

    Implements the exact duck-typed interface TwoFactorAuthManager already
    expects (get_two_factor_secret, get_two_factor_backup_codes, save), plus
    the additional methods it opportunistically uses when present:
    consume_two_factor_backup_code (atomic single-use check-and-remove --
    without this, a leaked backup code could be replayed forever), set_enabled,
    is_enabled, is_setup_completed, remaining_backup_codes_count, and delete.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._secrets: Dict[int, str] = {}
        self._backup_codes: Dict[int, List[str]] = {}
        self._enabled: Dict[int, bool] = {}
        self._setup_completed: Dict[int, bool] = {}

    def save(self, collection: str, data: Dict[str, Any]) -> None:
        """Generic save() matching the call TwoFactorAuthManager.setup_2fa()
        already makes: self.db_manager.save('two_factor_setup', setup_data)."""
        if collection != "two_factor_setup":
            return
        user_id = data["user_id"]
        with self._lock:
            self._secrets[user_id] = data["secret"]
            self._backup_codes[user_id] = list(data["backup_codes"])
            self._enabled[user_id] = bool(data.get("is_enabled", False))
            self._setup_completed[user_id] = bool(data.get("setup_completed", False))

    def get_two_factor_secret(self, user_id: int) -> Optional[str]:
        with self._lock:
            return self._secrets.get(user_id)

    def get_two_factor_backup_codes(self, user_id: int) -> List[str]:
        with self._lock:
            return list(self._backup_codes.get(user_id, []))

    def consume_two_factor_backup_code(self, user_id: int, code: str) -> bool:
        """Atomically verify-and-remove a backup code so it can never be
        replayed. Timing-safe comparison against every stored code (no early
        return on the comparison itself, so failure doesn't leak which
        position -- if any -- was closest to matching)."""
        with self._lock:
            codes = self._backup_codes.get(user_id, [])
            match_index = -1
            for i, vc in enumerate(codes):
                if hmac.compare_digest(code, vc):
                    match_index = i
            if match_index < 0:
                return False
            del codes[match_index]
            return True

    def set_enabled(self, user_id: int, enabled: bool) -> None:
        with self._lock:
            self._enabled[user_id] = enabled
            if enabled:
                self._setup_completed[user_id] = True

    def is_enabled(self, user_id: int) -> bool:
        with self._lock:
            return self._enabled.get(user_id, False)

    def is_setup_completed(self, user_id: int) -> bool:
        with self._lock:
            return self._setup_completed.get(user_id, False)

    def remaining_backup_codes_count(self, user_id: int) -> int:
        with self._lock:
            return len(self._backup_codes.get(user_id, []))

    def delete(self, user_id: int) -> None:
        """Remove all 2FA state for a user (called on disable_2fa)."""
        with self._lock:
            self._secrets.pop(user_id, None)
            self._backup_codes.pop(user_id, None)
            self._enabled.pop(user_id, None)
            self._setup_completed.pop(user_id, None)


class TwoFactorAuthManager:
    """2要素認証マネージャー"""

    def __init__(self, secret_key: str, db_manager=None):
        """2FAマネージャーを初期化"""
        self.secret_key = secret_key
        self.db_manager = db_manager
        self.fernet = Fernet(self._derive_key()) if CRYPTO_AVAILABLE else None

        # 設定
        self.issuer_name = "Cocoa Avatar System"
        self.account_name_template = "{username}"
        self.qr_code_size = 256

        # バックアップコード設定
        self.backup_code_count = 10
        self.backup_code_length = 8

        # リプレイ攻撃対策: 使用済み TOTP トークンを記録
        # {user_id: [(time_step, token), ...]}
        self._used_totp_tokens: Dict[int, List] = {}

        logger.info("TwoFactorAuthManager initialized")

    def _derive_key(self) -> bytes:
        """暗号化キーを導出"""
        if not CRYPTO_AVAILABLE:
            import hashlib
            return base64.urlsafe_b64encode(hashlib.sha256(self.secret_key.encode()).digest())
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"cocoa_2fa_salt_2025",
            iterations=100000
        )
        return base64.urlsafe_b64encode(kdf.derive(self.secret_key.encode()))

    def _generate_secret(self) -> str:
        """新しい秘密鍵を生成"""
        return base64.b32encode(secrets.token_bytes(32)).decode('utf-8')

    def _generate_backup_codes(self) -> List[str]:
        """バックアップコードを生成"""
        codes = []
        for _ in range(self.backup_code_count):
            code = ''.join(secrets.choice('0123456789') for _ in range(self.backup_code_length))
            codes.append(code)
        return codes

    def _encrypt_data(self, data: Dict) -> str:
        """データを暗号化"""
        json_data = json.dumps(data).encode()
        return self.fernet.encrypt(json_data).decode()

    def _decrypt_data(self, encrypted_data: str) -> Dict:
        """データを復号化"""
        decrypted_data = self.fernet.decrypt(encrypted_data.encode())
        return json.loads(decrypted_data.decode())

    def generate_qr_code_uri(self, username: str, secret: str) -> str:
        """QRコード用のURIを生成"""
        account_name = self.account_name_template.format(username=username)
        return (
            f"otpauth://totp/{self.issuer_name}:{account_name}"
            f"?secret={secret}&issuer={self.issuer_name}&algorithm=SHA1&digits=6&period=30"
        )

    def create_qr_code(self, username: str, secret: str) -> bytes:
        """QRコード画像を生成"""
        if not QRCODE_AVAILABLE:
            raise RuntimeError("qrcode library not installed")
        uri = self.generate_qr_code_uri(username, secret)

        # QRコード生成
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)

        # 画像をバイト列に変換。qrcode の既定イメージファクトリは Pillow が
        # インストールされていれば PilImage（.save() に format= が必須。
        # BytesIO にはファイル名が無く拡張子から推測できないため）、
        # 無ければピュア Python の PyPNGImage（.save() は format= 引数を
        # 受け付けず TypeError になる）に変わる。どちらでも動くように、
        # まず format='PNG' を試し、非対応なら引数無しで再試行する。
        img = qr.make_image(fill_color="black", back_color="white")
        img_buffer = io.BytesIO()
        try:
            img.save(img_buffer, format='PNG')
        except TypeError:
            img_buffer = io.BytesIO()
            img.save(img_buffer)
        return img_buffer.getvalue()

    def setup_2fa(self, user_id: int, username: str) -> Dict[str, Any]:
        """2FAをセットアップ"""
        try:
            # 新しい秘密鍵を生成
            secret = self._generate_secret()

            # バックアップコードを生成
            backup_codes = self._generate_backup_codes()

            # データベース保存処理（実際の実装では適切なデータベース操作）
            if self.db_manager:
                from datetime import timezone
                setup_data = {
                    'user_id': user_id,
                    'username': username,
                    'secret': secret,
                    'backup_codes': backup_codes,
                    'is_enabled': False,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'setup_completed': False,
                }
                self.db_manager.save('two_factor_setup', setup_data)

            # The QR image is a convenience; the URI alone is sufficient for
            # manual entry in any authenticator app. Degrade gracefully rather
            # than failing the whole setup (and losing the just-generated
            # secret/backup codes from the response) when the qrcode package
            # isn't installed.
            qr_code_image = self.create_qr_code(username, secret) if QRCODE_AVAILABLE else None

            return {
                'secret': secret,
                'backup_codes': backup_codes,
                'qr_code_uri': self.generate_qr_code_uri(username, secret),
                'qr_code_image': qr_code_image,
                'status': 'setup_required'
            }

        except Exception as e:
            logger.error(f"2FAセットアップエラー: {e}")
            raise

    def _get_user_secret(self, user_id: int) -> Optional[str]:
        """Return the user's enrolled TOTP secret, or None if it can't be
        retrieved securely.

        SECURITY: verification must use the per-user secret created at setup.
        Until a persistence layer exposing ``get_two_factor_secret`` is wired in,
        this returns None so every verifier FAILS CLOSED — never falling back to
        a hardcoded, source-visible secret that anyone reading this file could
        use to mint valid tokens for any account.
        """
        db = self.db_manager
        getter = getattr(db, "get_two_factor_secret", None) if db is not None else None
        if callable(getter):
            try:
                return getter(user_id)
            except Exception as e:  # pragma: no cover - defensive
                logger.error(f"2FA secret retrieval failed: {e}")
                return None
        return None

    def _get_user_backup_codes(self, user_id: int) -> List[str]:
        """Return the user's remaining backup codes, or [] if unavailable
        (→ fail closed, same rationale as _get_user_secret)."""
        db = self.db_manager
        getter = getattr(db, "get_two_factor_backup_codes", None) if db is not None else None
        if callable(getter):
            try:
                return list(getter(user_id) or [])
            except Exception as e:  # pragma: no cover - defensive
                logger.error(f"2FA backup-code retrieval failed: {e}")
                return []
        return []

    def enable_2fa(self, user_id: int, username: str, token: str) -> Dict[str, Any]:
        """2FAを有効化（セットアップ完了）"""
        try:
            # Verify with the user's OWN enrolled secret — never a hardcoded one.
            secret = self._get_user_secret(user_id)
            if not secret:
                logger.warning("2FA enable denied: no per-user secret for user %s", user_id)
                return {
                    'success': False,
                    'error': '2要素認証が構成されていません'
                }

            totp = TOTPGenerator(secret)
            if not totp.verify_token(token):
                return {
                    'success': False,
                    'error': '無効なトークンです'
                }

            # 2FAを有効化
            db = self.db_manager
            setter = getattr(db, "set_enabled", None) if db is not None else None
            if callable(setter):
                setter(user_id, True)

            # 監査ログを記録
            logger.info(f"2FA enabled for user: {username}")

            return {
                'success': True,
                'message': '2要素認証が有効になりました'
            }

        except Exception as e:
            logger.error(f"2FA有効化エラー: {e}")
            return {
                'success': False,
                'error': '2要素認証の有効化に失敗しました'
            }

    def verify_2fa_token(self, user_id: int, token: str) -> Dict[str, Any]:
        """2FAトークンを検証"""
        try:
            # Validate against the user's OWN enrolled secret. If it cannot be
            # retrieved, fail closed rather than accept a hardcoded global secret.
            secret = self._get_user_secret(user_id)
            if not secret:
                logger.warning("2FA verify denied: no per-user secret for user %s", user_id)
                return {
                    'valid': False,
                    'error': '2要素認証が構成されていません'
                }

            totp = TOTPGenerator(secret)
            # リプレイ攻撃対策: 同一ウィンドウ内で同じトークンを再使用させない
            window = 1
            current_step = int(time.time()) // totp.interval
            valid_steps = {current_step + o for o in range(-window, window + 1)}
            used = self._used_totp_tokens.get(user_id, [])
            if any(step in valid_steps and tok == token for step, tok in used):
                return {
                    'valid': False,
                    'error': 'このトークンは既に使用されています'
                }
            if totp.verify_token(token):
                # 使用済みトークンを記録し、古いエントリを削除
                used.append((current_step, token))
                cutoff = current_step - (window + 1)
                self._used_totp_tokens[user_id] = [(s, t) for s, t in used if s >= cutoff]
                return {
                    'valid': True,
                    'remaining_time': totp.get_remaining_time()
                }
            return {
                'valid': False,
                'error': '無効なトークンです'
            }

        except Exception as e:
            logger.error(f"2FAトークン検証エラー: {e}")
            return {
                'valid': False,
                'error': 'トークン検証に失敗しました'
            }

    def verify_backup_code(self, user_id: int, backup_code: str) -> Dict[str, Any]:
        """バックアップコードを検証（利用可能なら単回使用として消費する）"""
        try:
            db = self.db_manager
            consumer = getattr(db, "consume_two_factor_backup_code", None) if db is not None else None
            if callable(consumer):
                # Preferred path: atomic check-and-remove so a leaked backup
                # code can never be replayed after its first successful use.
                try:
                    consumed = consumer(user_id, backup_code)
                except Exception as e:  # pragma: no cover - defensive
                    logger.error(f"バックアップコード消費エラー: {e}")
                    consumed = False
                if consumed:
                    return {
                        'valid': True,
                        'message': 'バックアップコードが認証されました'
                    }
                if not self._get_user_backup_codes(user_id):
                    return {
                        'valid': False,
                        'error': '2要素認証が構成されていません'
                    }
                return {
                    'valid': False,
                    'error': '無効なバックアップコードです'
                }

            # Fallback for db_managers that only implement the read-only
            # get_two_factor_backup_codes() (external callers pre-dating
            # single-use support). Matches the historical behavior: a valid
            # code passes but is not consumed.
            valid_codes = self._get_user_backup_codes(user_id)
            if not valid_codes:
                return {
                    'valid': False,
                    'error': '2要素認証が構成されていません'
                }
            if any(hmac.compare_digest(backup_code, vc) for vc in valid_codes):
                return {
                    'valid': True,
                    'message': 'バックアップコードが認証されました'
                }
            return {
                'valid': False,
                'error': '無効なバックアップコードです'
            }

        except Exception as e:
            logger.error(f"バックアップコード検証エラー: {e}")
            return {
                'valid': False,
                'error': 'バックアップコード検証に失敗しました'
            }

    def disable_2fa(self, user_id: int, password: str) -> Dict[str, Any]:
        """2FAを無効化（パスワード確認が必要）"""
        try:
            # Verify the password against the real account credential.
            # Fail closed if no verifier is available — a hardcoded fallback
            # would let anyone who reads the source code disable 2FA for any user.
            db = self.db_manager
            verifier = getattr(db, "verify_password", None) if db is not None else None
            if not callable(verifier):
                logger.warning("disable_2fa: no verify_password callable — fail closed for user %s", user_id)
                return {
                    'success': False,
                    'error': 'パスワード検証機能が設定されていません'
                }
            if not verifier(user_id, password):
                return {
                    'success': False,
                    'error': 'パスワードが正しくありません'
                }

            deleter = getattr(db, "delete", None) if db is not None else None
            if callable(deleter):
                deleter(user_id)

            logger.info(f"2FA disabled for user: {user_id}")
            return {
                'success': True,
                'message': '2要素認証が無効になりました'
            }

        except Exception as e:
            logger.error(f"2FA無効化エラー: {e}")
            return {
                'success': False,
                'error': '2要素認証の無効化に失敗しました'
            }

    def get_2fa_status(self, user_id: int) -> Dict[str, Any]:
        """2FAステータスを取得"""
        try:
            db = self.db_manager
            is_enabled_fn = getattr(db, "is_enabled", None) if db is not None else None
            if callable(is_enabled_fn):
                # Real persistence is wired in: report the user's actual state
                # instead of the hardcoded stub this always returned before.
                setup_fn = getattr(db, "is_setup_completed", None)
                remaining_fn = getattr(db, "remaining_backup_codes_count", None)
                return {
                    'is_enabled': bool(is_enabled_fn(user_id)),
                    'setup_completed': bool(setup_fn(user_id)) if callable(setup_fn) else False,
                    'backup_codes_remaining': remaining_fn(user_id) if callable(remaining_fn) else 0,
                    'last_used': None
                }

            # No persistence layer wired in: nothing has ever been enabled.
            return {
                'is_enabled': False,
                'setup_completed': False,
                'backup_codes_remaining': 0,
                'last_used': None
            }

        except Exception as e:
            logger.error(f"2FAステータス取得エラー: {e}")
            return {
                'error': 'ステータス取得に失敗しました'
            }


class TwoFactorAuthService:
    """2要素認証サービス（簡易版）"""

    def __init__(self):
        """サービスを初期化"""
        # The 2FA master secret encrypts all stored TOTP seeds. A hardcoded
        # fallback would mean every deployment that forgot to set the env var
        # shares the same key — anyone with the source could decrypt their
        # users' TOTP seeds. Fail closed instead.
        secret = os.getenv("COCOA_2FA_SECRET")
        if not secret:
            raise RuntimeError(
                "COCOA_2FA_SECRET must be set to initialize 2FA. "
                "Generate one with `python -c 'import secrets; "
                "print(secrets.token_urlsafe(32))'` and store it in your "
                "environment / secret manager."
            )
        self.secret_key = secret
        # Wire in the in-memory persistence layer so setup/enable/verify/status
        # actually work end-to-end -- see TwoFactorStore's docstring for what
        # was broken before this existed. disable_2fa's password-verification
        # gate is intentionally untouched: it fails closed without a
        # verify_password callable, which TwoFactorStore does not provide
        # (password verification belongs to auth_manager, a separate concern).
        self.store = TwoFactorStore()
        self.tfa_manager = TwoFactorAuthManager(self.secret_key, db_manager=self.store)

    def setup_user_2fa(self, user_id: int, username: str) -> Dict[str, Any]:
        """ユーザーの2FAをセットアップ"""
        return self.tfa_manager.setup_2fa(user_id, username)

    def enable_user_2fa(self, user_id: int, username: str, token: str) -> Dict[str, Any]:
        """ユーザーの2FAを有効化"""
        return self.tfa_manager.enable_2fa(user_id, username, token)

    def verify_user_token(self, user_id: int, token: str) -> Dict[str, Any]:
        """ユーザーのトークンを検証"""
        return self.tfa_manager.verify_2fa_token(user_id, token)

    def verify_backup_code(self, user_id: int, backup_code: str) -> Dict[str, Any]:
        """バックアップコードを検証"""
        return self.tfa_manager.verify_backup_code(user_id, backup_code)

    def disable_user_2fa(self, user_id: int, password: str) -> Dict[str, Any]:
        """ユーザーの2FAを無効化"""
        return self.tfa_manager.disable_2fa(user_id, password)

    def get_user_2fa_status(self, user_id: int) -> Dict[str, Any]:
        """ユーザーの2FAステータスを取得"""
        return self.tfa_manager.get_2fa_status(user_id)


# グローバルサービスインスタンス
_two_factor_service: Optional[TwoFactorAuthService] = None
_two_factor_service_lock = threading.Lock()


def get_two_factor_service() -> TwoFactorAuthService:
    """2要素認証サービスのシングルトンインスタンスを取得"""
    global _two_factor_service
    if _two_factor_service is None:
        with _two_factor_service_lock:
            if _two_factor_service is None:
                _two_factor_service = TwoFactorAuthService()
    return _two_factor_service


# 便利関数
def setup_2fa(user_id: int, username: str) -> Dict[str, Any]:
    """2FAセットアップの便利関数"""
    service = get_two_factor_service()
    return service.setup_user_2fa(user_id, username)


def verify_2fa_token(user_id: int, token: str) -> Dict[str, Any]:
    """2FAトークン検証の便利関数"""
    service = get_two_factor_service()
    return service.verify_user_token(user_id, token)


def verify_backup_code(user_id: int, backup_code: str) -> Dict[str, Any]:
    """バックアップコード検証の便利関数"""
    service = get_two_factor_service()
    return service.verify_backup_code(user_id, backup_code)


def disable_2fa(user_id: int, password: str) -> Dict[str, Any]:
    """2FA無効化の便利関数"""
    service = get_two_factor_service()
    return service.disable_user_2fa(user_id, password)


def get_2fa_status(user_id: int) -> Dict[str, Any]:
    """2FAステータス取得の便利関数"""
    service = get_two_factor_service()
    return service.get_user_2fa_status(user_id)
