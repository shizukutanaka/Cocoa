"""
ロギングマネージャー
全サービスで共有されるログ設定
"""

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import get_config


class JSONFormatter(logging.Formatter):
    """JSON形式のログフォーマッター"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 例外情報があれば追加
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # 追加のフィールドがあれば追加
        _exclude = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
            'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
            'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
            'thread', 'threadName', 'processName', 'process', 'getMessage',
            'format', 'formatMessage', 'formatException',
        }
        log_entry.update({k: v for k, v in record.__dict__.items() if k not in _exclude})

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = False
) -> None:
    """ログ設定をセットアップ"""

    # ルートロガーの設定
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 既存のハンドラーをクリア
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # フォーマッター設定
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    # コンソールハンドラー
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # ファイルハンドラー（設定されている場合）
    if log_file:
        # ログディレクトリ作成
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # ローテーティングファイルハンドラー
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # サードパーティライブラリのログレベル調整
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('fastapi').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)

    # 設定完了ログ
    logger = logging.getLogger(__name__)
    logger.info(f"ログ設定が完了しました (レベル: {log_level}, フォーマット: {'JSON' if json_format else 'テキスト'})")


def get_logger(name: str) -> logging.Logger:
    """名前付きロガーを取得"""
    return logging.getLogger(name)


# デフォルト設定でセットアップ
def initialize_logging():
    """デフォルト設定でログを初期化"""
    try:
        config = get_config()
        log_level = config.security.get("log_level", "INFO")

        # ログファイルパス設定（環境変数またはデフォルト）
        log_file = os.getenv("COCOA_LOG_FILE", "logs/cocoa.log")

        # JSON形式でログ出力（本番環境推奨）
        json_format = config.environment in ["production", "staging"]

        setup_logging(log_level, log_file, json_format)

    except Exception as e:
        # 設定読み込みエラー時はデフォルト設定を使用
        print(f"ログ設定エラー: {e}", file=sys.stderr)
        setup_logging("INFO", "logs/cocoa.log", False)
