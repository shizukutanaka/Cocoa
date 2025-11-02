"""
ログ管理システム
軽量で実用的なログ管理機能を提供
"""
import logging
import logging.handlers
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 暗号化機能の追加
try:
    from cryptography.fernet import Fernet
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

logger = logging.getLogger(__name__)


class EncryptedFileHandler(logging.handlers.RotatingFileHandler):
    """暗号化されたログファイルハンドラー"""

    def __init__(self, filename, encryption_key=None, maxBytes=0, backupCount=0, encoding=None, delay=False):
        self.encryption_key = encryption_key or os.environ.get('COCOA_LOG_ENCRYPTION_KEY')
        if not self.encryption_key and CRYPTOGRAPHY_AVAILABLE:
            logger.warning("ログ暗号化キーが設定されていません")
            self.fernet = None
        elif CRYPTOGRAPHY_AVAILABLE:
            self.fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        else:
            logger.warning("cryptographyライブラリが利用できないため、暗号化を無効化します")
            self.fernet = None

        super().__init__(filename, maxBytes, backupCount, encoding, delay)

    def emit(self, record):
        if self.fernet:
            try:
                # ログメッセージを暗号化
                message = self.format(record)
                encrypted_message = self.fernet.encrypt(message.encode('utf-8'))
                # 暗号化されたメッセージをファイルに書き込み
                self.stream.write(encrypted_message.decode('latin1') + '\n')
                self.stream.write('---ENCRYPTED---\n')  # マーカー
            except Exception:
                # 暗号化失敗時は通常のログを記録
                super().emit(record)
        else:
            super().emit(record)

    def read_encrypted_logs(self, limit=100):
        """暗号化されたログを復号して読み込み"""
        if not self.fernet:
            return []

        logs = []
        try:
            with open(self.baseFilename, 'r', encoding='latin1') as f:
                encrypted_lines = []
                for line in f:
                    if line.strip() == '---ENCRYPTED---':
                        if encrypted_lines:
                            try:
                                encrypted_data = ''.join(encrypted_lines)
                                decrypted_data = self.fernet.decrypt(encrypted_data.encode('latin1'))
                                logs.append(json.loads(decrypted_data.decode('utf-8')))
                            except Exception as e:
                                logger.error(f"ログ復号エラー: {e}")
                            encrypted_lines = []
                    else:
                        encrypted_lines.append(line)

                    if len(logs) >= limit:
                        break

            return logs
        except Exception as e:
            logger.error(f"暗号化ログ読み込みエラー: {e}")
            return []


class JsonLogFormatter(logging.Formatter):
    """1行1JSON形式でログを出力するフォーマッター。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info:
            payload["stack_info"] = record.stack_info

        extra = getattr(record, "extra_data", None)
        if extra:
            payload["extra"] = extra

        return json.dumps(payload, ensure_ascii=False)

class LoggingManager:
    """軽量で実用的なログ管理システム"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """ログ管理システムを初期化"""
        self.config = config or {}
        self.log_dir = Path(self.config.get("log_dir", "logs"))
        self.log_level = self.config.get("log_level", "INFO")
        self.max_bytes = self.config.get("max_bytes", 10 * 1024 * 1024)  # 10MB
        self.backup_count = self.config.get("backup_count", 5)
        self.enable_console = self.config.get("enable_console", True)
        self.enable_encryption = self.config.get("enable_encryption", False)
        self.encryption_key = self.config.get("encryption_key") or os.environ.get('COCOA_LOG_ENCRYPTION_KEY')

        # ログディレクトリの作成
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"ログディレクトリの作成に失敗しました: {e}")

        # ログレベルの設定
        self.log_levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }

        # ログ設定の初期化
        self._setup_logging()

    def _setup_logging(self) -> None:
        """ログ設定を初期化"""
        try:
            # フォーマッターの設定 (JSON形式)
            formatter = JsonLogFormatter()

            # 既存ハンドラーを除去し、重複設定を防止
            root_logger = logging.getLogger()
            for handler in list(root_logger.handlers):
                root_logger.removeHandler(handler)
                handler.close()

            # ローテーティングファイルハンドラーの設定
            log_file = self.log_dir / "otedama.log"
            if self.enable_encryption and self.encryption_key:
                file_handler = EncryptedFileHandler(
                    str(log_file),
                    encryption_key=self.encryption_key,
                    maxBytes=self.max_bytes,
                    backupCount=self.backup_count,
                    encoding='utf-8'
                )
            else:
                file_handler = logging.handlers.RotatingFileHandler(
                    str(log_file),
                    maxBytes=self.max_bytes,
                    backupCount=self.backup_count,
                    encoding='utf-8'
                )
            file_handler.setFormatter(formatter)

            # ルートロガーの設定
            root_logger.setLevel(self.log_levels.get(self.log_level, logging.INFO))
            root_logger.addHandler(file_handler)

            if self.enable_console:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                root_logger.addHandler(console_handler)

            logger.info("ログシステムを初期化しました")
        except Exception as e:
            logger.error(f"ログシステムの初期化に失敗しました: {e}")

    def set_log_level(self, level: str) -> bool:
        """ログレベルを設定"""
        try:
            if level not in self.log_levels:
                logger.warning(f"無効なログレベル: {level}")
                return False

            self.log_level = level
            root_logger = logging.getLogger()
            root_logger.setLevel(self.log_levels[level])
            logger.info(f"ログレベルを {level} に変更しました")
            return True
        except Exception as e:
            logger.error(f"ログレベルの変更に失敗しました: {e}")
            return False

    def log_message(self, level: str, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """ログメッセージを記録"""
        try:
            level_name = level.upper()
            if level_name not in self.log_levels:
                logger.warning(f"無効なログレベル: {level}")
                level_name = "INFO"

            log_level = self.log_levels[level_name]
            extra = {"extra_data": extra_data} if extra_data else None
            logger.log(log_level, message, extra=extra)
        except Exception as e:
            logger.error(f"ログメッセージの記録に失敗しました: {e}")

    def log_avatar_action(self, avatar_id: str, action: str, duration: float, success: bool = True) -> None:
        """アバター処理のログを記録"""
        try:
            status = "成功" if success else "失敗"
            message = f"アバター {avatar_id} - {action} ({status}) - 処理時間: {duration:.3f}秒"
            extra_data = {
                "avatar_id": avatar_id,
                "action": action,
                "duration": duration,
                "success": success
            }
            self.log_message("INFO", message, extra_data)
        except Exception as e:
            logger.error(f"アバターログの記録に失敗しました: {e}")

    def log_preset_action(self, preset_id: str, action: str, duration: float, success: bool = True) -> None:
        """プリセット処理のログを記録"""
        try:
            status = "成功" if success else "失敗"
            message = f"プリセット {preset_id} - {action} ({status}) - 処理時間: {duration:.3f}秒"
            extra_data = {
                "preset_id": preset_id,
                "action": action,
                "duration": duration,
                "success": success
            }
            self.log_message("INFO", message, extra_data)
        except Exception as e:
            logger.error(f"プリセットログの記録に失敗しました: {e}")

    def log_error(self, error: Exception, context: str = "") -> None:
        """エラーログを記録"""
        try:
            error_message = f"{context}: {str(error)}" if context else str(error)
            extra_data = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context
            }
            self.log_message("ERROR", error_message, extra_data)
        except Exception as e:
            logger.error(f"エラーログの記録に失敗しました: {e}")

    def search_logs(self, keyword: str, limit: int = 100) -> List[Dict[str, Any]]:
        """ログを検索"""
        results = []
        try:
            log_file = self.log_dir / "otedama.log"
            if not log_file.exists():
                logger.warning(f"ログファイルが存在しません: {log_file}")
                return results

            keyword_lower = keyword.lower()
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    parsed = self._parse_log_line(line)
                    haystack = json.dumps(parsed, ensure_ascii=False).lower()
                    if keyword_lower in haystack:
                        results.append(parsed)
                        if len(results) >= limit:
                            break

            return results
        except Exception as e:
            logger.error(f"ログ検索中にエラーが発生しました: {e}")
            return results

    def _parse_log_line(self, line: str) -> Dict[str, Any]:
        """ログ行を解析"""
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return {"raw": line.strip()}
        except Exception as e:
            return {"error": str(e), "raw": line.strip()}

    def get_log_stats(self) -> Dict[str, any]:
        """ログ統計を取得"""
        try:
            log_file = self.log_dir / "otedama.log"
            if not log_file.exists():
                return {"error": "ログファイルが存在しません"}

            file_size = log_file.stat().st_size
            line_count = sum(1 for _ in open(log_file, 'r', encoding='utf-8'))

            return {
                "file_size": file_size,
                "line_count": line_count,
                "log_level": self.log_level,
                "max_bytes": self.max_bytes,
                "backup_count": self.backup_count
            }
        except Exception as e:
            logger.error(f"ログ統計の取得に失敗しました: {e}")
            return {"error": str(e)}

    def clear_old_logs(self, days: int = 30) -> bool:
        """古いログファイルを削除"""
        try:
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)

            for log_file in self.log_dir.glob("*.log.*"):
                if log_file.stat().st_mtime < cutoff_date:
                    log_file.unlink()
                    logger.info(f"古いログファイルを削除しました: {log_file}")

            return True
        except Exception as e:
            logger.error(f"古いログファイルの削除に失敗しました: {e}")
            return False

    def export_logs(self, filename: str, format: str = "json") -> bool:
        """ログをエクスポート"""
        try:
            log_file = self.log_dir / "otedama.log"
            if not log_file.exists():
                logger.warning(f"ログファイルが存在しません: {log_file}")
                return False

            if format.lower() == "json":
                logs = [
                    self._parse_log_line(line)
                    for line in open(log_file, 'r', encoding='utf-8')
                    if line.strip()
                ]

                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(logs, f, indent=2, ensure_ascii=False)
            else:
                # テキスト形式でエクスポート
                import shutil
                shutil.copy2(str(log_file), filename)

            logger.info(f"ログをエクスポートしました: {filename}")
            return True
        except Exception as e:
            logger.error(f"ログエクスポートに失敗しました: {e}")
            return False
