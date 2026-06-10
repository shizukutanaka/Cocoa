"""
集中管理ロギング基盤
Python logging の統一的な設定と使用

設計原則:
- 単一の設定ファイル
- JSON形式のログ（ログ集約ツール対応）
- 相関ID追跡
- 環境ごとの自動切り替え
- 非本番環境での詳細ログ
"""

import json
import logging
import logging.config
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _validate_level(level: str) -> int:
    """Return the numeric logging level for *level*, raising ValueError if unknown."""
    upper = level.upper()
    if upper not in _VALID_LEVELS:
        raise ValueError(
            f"Invalid log level: {level!r}. Must be one of {sorted(_VALID_LEVELS)}"
        )
    return getattr(logging, upper)

# グローバルロガーレジストリ
_loggers: Dict[str, logging.Logger] = {}
_correlation_id: Optional[str] = None


def get_correlation_id() -> Optional[str]:
    """現在の相関IDを取得"""
    return _correlation_id


def set_correlation_id(correlation_id: str) -> None:
    """相関IDを設定（リクエストごとに呼び出し）"""
    global _correlation_id
    _correlation_id = correlation_id


class CorrelationIdFilter(logging.Filter):
    """相関IDをログレコードに追加するフィルター"""

    def filter(self, record):
        record.correlation_id = get_correlation_id() or "N/A"
        return True


class JSONFormatter(logging.Formatter):
    """JSON形式でログを出力（ログ集約ツール対応）"""

    def format(self, record):
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", "N/A"),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 例外情報を含む
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def configure_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = True,
    environment: str = "development"
) -> None:
    """
    ロギングを設定

    Args:
        level: ログレベル (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: ログファイルのパス（Noneの場合は stdout のみ）
        json_format: JSON形式でログを出力するか
        environment: 環境 (development/production)
    """

    # ログレベルの決定（無効な値は ValueError）
    numeric_level = _validate_level(level)

    # ルートロガーの設定
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # 既存のハンドラーをクリア
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # フォーマッターを設定
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    # コンソール出力（stdout）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(CorrelationIdFilter())
    root_logger.addHandler(console_handler)

    # ファイル出力（オプション）
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(CorrelationIdFilter())
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    ロガーを取得

    使用例:
        logger = get_logger(__name__)
        logger.info("Operation started")
        logger.error("Operation failed", exc_info=True)
    """
    if name not in _loggers:
        logger = logging.getLogger(name)
        logger.addFilter(CorrelationIdFilter())
        _loggers[name] = logger

    return _loggers[name]


# ロギングのベストプラクティス

class LogContext:
    """ロギングコンテキスト管理"""

    def __init__(self, logger: logging.Logger, operation: str):
        self.logger = logger
        self.operation = operation

    def __enter__(self):
        self.logger.info(f"Starting: {self.operation}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.logger.info(f"Completed: {self.operation}")
        else:
            # logger.exception() は自動的にスタックトレースを含める
            self.logger.exception(f"Failed: {self.operation}")
        return False


def setup_production_logging() -> None:
    """本番環境用のロギング設定"""
    environment = os.environ.get("ENVIRONMENT", "development")
    log_level = os.environ.get("LOG_LEVEL", "WARNING")
    log_file = os.environ.get("LOG_FILE", "logs/cocoa.log")

    configure_logging(
        level=log_level,
        log_file=log_file,
        json_format=True,
        environment=environment
    )


def setup_development_logging() -> None:
    """開発環境用のロギング設定"""
    configure_logging(
        level="DEBUG",
        log_file=None,  # 開発時はファイル不要
        json_format=False,  # 見やすくするため
        environment="development"
    )


# 使用例
if __name__ == "__main__":
    # 本番環境
    setup_production_logging()

    # 開発環境
    # setup_development_logging()

    logger = get_logger(__name__)

    # 相関IDを設定（リクエストハンドラーで実行）
    set_correlation_id("req-12345-abcde")

    # 通常のログ
    logger.info("Application started")
    logger.warning("Configuration warning")

    # コンテキストマネージャーでの使用
    with LogContext(logger, "database_connection"):
        # 処理を実行
        logger.debug("Connecting to database...")

    # 例外ログ（スタックトレース自動追加）
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("Math error occurred")  # この行でスタックトレース自動追加
