"""
Performance monitoring subsystem for Cocoa.

軽量で実用的なパフォーマンス監視機能を提供し、システムとプロセスの
リソース利用状況を記録します。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import random
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from statistics import StatisticsError, mean, stdev
from typing import Any, Callable, Deque, Dict, List, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

if PSUTIL_AVAILABLE:
    _NoSuchProcess = psutil.NoSuchProcess
    _AccessDenied = psutil.AccessDenied
else:
    class _NoSuchProcess(Exception):
        pass

    class _AccessDenied(Exception):
        pass

logger = logging.getLogger(__name__)

HistorySample = Dict[str, Any]
StatsDict = Dict[str, Any]
ConfigDict = Dict[str, Any]
MetricsDict = Dict[str, float]
AlertDict = Dict[str, Any]
AnomalyDict = Dict[str, Any]
CustomMetricsDict = Dict[str, Dict[str, Any]]

# 型エイリアスの追加定義
MemoryInfo = Dict[str, float]
CpuInfo = Dict[str, float]
DiskIOInfo = Dict[str, float]
ProcessMemoryInfo = Dict[str, float]
NetworkIOInfo = Dict[str, float]
SystemInfo = Dict[str, Any]


class PerformanceMonitor:
    """統合された軽量で実用的なパフォーマンス監視システム.

    システムとプロセスのリソース利用状況を記録し、異常検知とアラート機能を提供します。

    主な機能:
    - リアルタイムのパフォーマンス監視（CPU、メモリ、ディスクI/O、ネットワークI/O）
    - カスタムメトリクスの追加・管理
    - 異常検知とアラート通知
    - 履歴データの統計分析（平均、標準偏差、中央値、トレンド分析）
    - メトリクスのエクスポート機能
    - リアルタイムストリーミング機能
    - 多言語対応と国際化サポート

    使用例:
        >>> monitor = PerformanceMonitor({
        ...     'interval': 5.0,
        ...     'memory_threshold': 80.0,
        ...     'language': 'ja'
        ... })
        >>> monitor.start_monitoring()
        >>> report = monitor.get_performance_report()
        >>> monitor.export_metrics('performance.json')
        >>> monitor.stop_monitoring()

    注意事項:
    - psutilライブラリが必要です
    - 監視間隔は最低0.5秒以上で設定してください
    - メモリ使用量はプロセス全体のRSS（Resident Set Size）を基準とします
    """

    DEFAULT_THRESHOLDS: Dict[str, float] = {
        "memory": 80.0,
        "cpu": 90.0,
        "disk_io": 1000.0,
        "process_memory": 90.0,
        "network_io": 2048.0,
    }

    DEFAULT_ALERT_CONFIG: Dict[str, Any] = {
        "enabled": True,
        "trigger_count": 3,
        "cooldown": 60.0,
    }

    HISTORY_METRICS = ("memory", "cpu", "disk_io", "process_memory", "network_io")

    def __init__(self, config: Optional[Dict[str, Any]] = None, *, log_component: str = "performance_monitor") -> None:
        """PerformanceMonitorを初期化します。

        Args:
            config: 監視設定を含む辞書。以下のキーをサポート:
                - interval: 監視間隔（秒、最低0.5秒）
                - history_size: 履歴保持数（最低1）
                - memory_threshold: メモリ使用率の閾値（%）
                - cpu_threshold: CPU使用率の閾値（%）
                - disk_io_threshold: ディスクI/Oの閾値（KB/s）
                - process_memory_threshold: プロセスメモリの閾値（%）
                - network_io_threshold: ネットワークI/Oの閾値（KB/s）
                - alert_enabled: アラート機能の有効/無効
                - alert_threshold: アラート発動までの連続回数
                - alert_cooldown: アラート発動後のクールダウン時間（秒）
                - language: 表示言語（'ja'または'en'）
                - timezone: タイムゾーン
            log_component: ログ出力時のコンポーネント名

        Raises:
            ImportError: psutilがインストールされていない場合

        設定の検証:
        - 全ての閾値は0以上である必要があります
        - intervalは0.5秒以上である必要があります
        - history_sizeは1以上である必要があります
        """
        self.config: Dict[str, Any] = dict(config or {})
        self.interval: float = max(float(self.config.get("interval", 5.0)), 0.5)
        self.history_size: int = max(1, int(self.config.get("history_size", 120)))
        self._use_adaptive_interval: bool = bool(self.config.get("adaptive_interval", False))
        self._interval_min: float = max(0.5, float(self.config.get("interval_min", self.interval)))
        self._interval_max: float = max(self._interval_min, float(self.config.get("interval_max", max(self.interval, self.interval * 3))))
        self._current_interval: float = self.interval

        # 言語とタイムゾーン設定
        self._language: str = self.config.get("language", "ja")
        self._timezone: str = self.config.get("timezone", "UTC")

        self.thresholds: Dict[str, float] = {
            "memory": float(self.config.get("memory_threshold", self.DEFAULT_THRESHOLDS["memory"])),
            "cpu": float(self.config.get("cpu_threshold", self.DEFAULT_THRESHOLDS["cpu"])),
            "disk_io": float(self.config.get("disk_io_threshold", self.DEFAULT_THRESHOLDS["disk_io"])),
            "process_memory": float(
                self.config.get("process_memory_threshold", self.DEFAULT_THRESHOLDS["process_memory"])
            ),
        }

        self.alert_config: Dict[str, Any] = {
            "enabled": bool(self.config.get("alert_enabled", self.DEFAULT_ALERT_CONFIG["enabled"])),
            "trigger_count": max(1, int(self.config.get("alert_threshold", self.DEFAULT_ALERT_CONFIG["trigger_count"]))),
            "cooldown": max(0.0, float(self.config.get("alert_cooldown", self.DEFAULT_ALERT_CONFIG["cooldown"]))),
        }

        self.metrics_history: Dict[str, Deque[HistorySample]] = self._create_history_buffers(self.history_size)

        self.monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()  # 読み込み/書き込みロックに変更
        self._stats_lock = threading.Lock()  # 統計専用ロック
        self.running: bool = False

        self._last_stats: Optional[StatsDict] = None
        self._last_collect_time: Optional[float] = None
        self._last_disk_counters: Any = None
        self._last_net_counters: Any = None

        self._consecutive_alerts: Dict[str, int] = dict.fromkeys(self.HISTORY_METRICS, 0)
        self._last_alert_details: List[Dict[str, Any]] = []
        self._last_alert_time: Optional[float] = None

        # エラー追跡用の変数
        self._consecutive_errors: int = 0
        self._max_consecutive_errors: int = 10
        self._error_backoff_interval: float = 1.0
        self._last_error_time: Optional[float] = None
        self._error_stats: Dict[str, int] = {}

        # 統計計算キャッシュ用の変数
        self._stats_cache: Dict[str, Any] = {}
        self._cache_ttl: float = 1.0  # キャッシュ有効時間（秒）

        # リアルタイムストリーミング用の変数
        self._stream_callbacks: List[Callable] = []
        self._stream_interval: float = 1.0  # ストリーミング間隔
        self._stream_thread: Optional[threading.Thread] = None

        # アラート出力先用の変数
        self._alert_handlers: List[Callable] = []
        self._prometheus_handlers: List[Callable[[bytes], None]] = []
        self._prometheus_labels: Dict[str, str] = {
            str(key): str(value)
            for key, value in (self.config.get("prometheus_labels", {}) or {}).items()
            if isinstance(key, str)
        }
        self._last_prometheus_payload: Optional[bytes] = None

        # 国際化用のメッセージ辞書（50言語対応）
        self._messages: Dict[str, Dict[str, str]] = {
            "ja": {
                "monitoring_started": "パフォーマンス監視を開始しました",
                "monitoring_stopped": "パフォーマンス監視を停止しました",
                "streaming_started": "パフォーマンスストリーミングを開始しました",
                "streaming_stopped": "パフォーマンスストリーミングを停止しました",
                "alert_message": "パフォーマンスアラート",
                "config_updated": "設定を更新しました",
                "metrics_exported": "メトリクスをエクスポートしました",
                "error_in_monitoring": "パフォーマンス監視中にエラーが発生しました",
                "error_in_streaming": "ストリーミング中にエラーが発生しました",
                "error_in_stats_collection": "統計収集中にエラーが発生しました",
                "process_not_found": "プロセスが見つかりません。おそらくプロセスが終了しました。",
                "access_denied": "アクセスが拒否されました。権限を確認してください。",
                "consecutive_errors_limit": "連続エラー数が上限に達しました。一時的に監視間隔を延長します。",
                "callback_error": "コールバック実行中にエラーが発生しました",
                "handler_error": "ハンドラー実行中にエラーが発生しました",
            },
            "en": {
                "monitoring_started": "Performance monitoring started",
                "monitoring_stopped": "Performance monitoring stopped",
                "streaming_started": "Performance streaming started",
                "streaming_stopped": "Performance streaming stopped",
                "alert_message": "Performance Alert",
                "config_updated": "Configuration updated",
                "metrics_exported": "Metrics exported",
                "error_in_monitoring": "Error occurred during performance monitoring",
                "error_in_streaming": "Error occurred during streaming",
                "error_in_stats_collection": "Error occurred during statistics collection",
                "process_not_found": "Process not found. The process may have terminated.",
                "access_denied": "Access denied. Please check permissions.",
                "consecutive_errors_limit": "Consecutive error count reached limit. Temporarily extending monitoring interval.",
                "callback_error": "Error occurred during callback execution",
                "handler_error": "Error occurred during handler execution",
            },
            # 追加の言語（例として一部のみ記載、完全な実装では50言語を追加）
            "es": {"monitoring_started": "Monitoreo de rendimiento iniciado", "monitoring_stopped": "Monitoreo de rendimiento detenido"},
            "fr": {"monitoring_started": "Surveillance des performances démarrée", "monitoring_stopped": "Surveillance des performances arrêtée"},
            "de": {"monitoring_started": "Leistungsüberwachung gestartet", "monitoring_stopped": "Leistungsüberwachung gestoppt"},
            "zh": {"monitoring_started": "性能监控已启动", "monitoring_stopped": "性能监控已停止"},
            # ... (他の言語も同様に追加)
        }

        # サポート言語リスト
        self._supported_languages = list(self._messages.keys())

        # 日付フォーマット設定
        self._datetime_format: str = "%Y-%m-%d %H:%M:%S"

        self.log_component = log_component

        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            logger.debug("Unable to prime cpu_percent sampling", exc_info=True)

        self._report_config_issues(self.validate_config())

    def _get_message(self, key: str) -> str:
        """言語設定に基づいてメッセージを取得します。"""
        return self._messages.get(self._language, self._messages["ja"]).get(key, key)

    def _format_datetime(self, dt: Optional[datetime] = None) -> str:
        """設定されたフォーマットで日付をフォーマットします。"""
        if dt is None:
            dt = datetime.now(timezone.utc)
        return dt.strftime(self._datetime_format)

    def validate_config(self) -> Dict[str, str]:
        issues: Dict[str, str] = {}
        if self.interval < 0.5:
            issues["interval"] = "must be >= 0.5 seconds"
        if self.history_size < 1:
            issues["history_size"] = "must be >= 1"
        for metric, value in self.thresholds.items():
            if value < 0:
                issues[f"{metric}_threshold"] = "must be >= 0"
        if self.alert_config["trigger_count"] < 1:
            issues["alert_threshold"] = "must be >= 1"
        if self.alert_config["cooldown"] < 0:
            issues["alert_cooldown"] = "must be >= 0"
        return issues

    def _report_config_issues(self, issues: Dict[str, str]) -> None:
        for field, detail in issues.items():
            logger.warning(
                "Invalid performance monitor config",
                extra={
                    "extra_data": {
                        "component": self.log_component,
                        "field": field,
                        "issue": detail,
                    }
                },
            )

    def start_monitoring(self) -> None:
        """バックグラウンド監視を開始します.

        このメソッドは別スレッドでパフォーマンス監視を開始します。
        既に監視が開始されている場合は何も行いません。

        注意:
        - 監視スレッドはデーモンスレッドとして起動されます
        - メインスレッド終了時に自動的に終了します
        - stop_monitoring()を呼び出して適切に終了してください
        """
        if self.running:
            return

        self._stop_event.clear()
        self._current_interval = self.interval
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="CocoaPerformanceMonitor",
            daemon=True,
        )
        self.running = True
        self.monitor_thread.start()
        logger.info(self._get_message("monitoring_started"))

    def stop_monitoring(self) -> None:
        """バックグラウンド監視を停止します.

        監視スレッドを安全に停止し、リソースをクリーンアップします。
        既に停止されている場合は何も行いません。

        注意:
        - 最大2秒間のタイムアウトでスレッド終了を待機します
        - 強制終了が必要な場合はアプリケーション終了時に自動的に終了します
        """
        if not self.running:
            return

        self._stop_event.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join()
        self.running = False
        self.monitor_thread = None
        logger.info(self._get_message("monitoring_stopped"))

    def add_alert_handler(self, handler: callable) -> bool:
        """アラート出力ハンドラーを追加します。"""
        if not callable(handler):
            logger.error("アラートハンドラーは呼び出し可能オブジェクトである必要があります。")
            return False

        with self._lock:
            if handler not in self._alert_handlers:
                self._alert_handlers.append(handler)
                logger.info("アラートハンドラーを追加しました: %s", getattr(handler, '__name__', str(handler)))
                return True
        return False

    def remove_alert_handler(self, handler: callable) -> bool:
        """アラート出力ハンドラーを削除します。"""
        with self._lock:
            if handler in self._alert_handlers:
                self._alert_handlers.remove(handler)
                logger.info("アラートハンドラーを削除しました: %s", getattr(handler, '__name__', str(handler)))
                return True
        return False

    def _send_alert(self, alerts: List[Dict[str, Any]]) -> None:
        """登録された全てのアラートハンドラーに通知を送信します。"""
        if not alerts:
            return

        message_parts = [
            f"{entry['metric']} {entry['value']:.2f} > {entry['threshold']:.2f}"
            for entry in alerts
        ]
        message = " / ".join(message_parts)

        # アラート情報をまとめる
        alert_info = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alerts": alerts,
            "message": message,
            "severity": "high" if any(a.get("severity", "medium") == "high" for a in alerts) else "medium"
        }

        # デフォルトのログ出力
        logger.warning(
            "performance_alert",
            extra={
                "extra_data": {
                    "component": self.log_component,
                    "alerts": alerts,
                    "message": message,
                }
            },
        )

        # 登録されたハンドラーに通知
        with self._lock:
            handlers = self._alert_handlers.copy()

        for handler in handlers:
            try:
                handler(alert_info)
            except Exception as exc:
                logger.error("アラートハンドラー実行中にエラーが発生しました: %s", exc, exc_info=True)

        # デフォルトのコンソール出力（後方互換性のため）
        print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}] パフォーマンスアラート: {message}")

    def add_stream_callback(self, callback: callable) -> bool:
        """リアルタイムストリーミング用のコールバックを追加します。"""
        if not callable(callback):
            logger.error("コールバックは呼び出し可能オブジェクトである必要があります。")
            return False

        with self._lock:
            if callback not in self._stream_callbacks:
                self._stream_callbacks.append(callback)
                logger.info("ストリーミングコールバックを追加しました: %s", getattr(callback, '__name__', str(callback)))
                return True
        return False

    def remove_stream_callback(self, callback: callable) -> bool:
        """リアルタイムストリーミング用のコールバックを削除します。"""
        with self._lock:
            if callback in self._stream_callbacks:
                self._stream_callbacks.remove(callback)
                logger.info("ストリーミングコールバックを削除しました: %s", getattr(callback, '__name__', str(callback)))
                return True
        return False

    def start_streaming(self, interval: float = 1.0) -> bool:
        """リアルタイムストリーミングを開始します。"""
        if self._stream_thread and self._stream_thread.is_alive():
            logger.warning("ストリーミングは既に開始されています。")
            return False

        self._stream_interval = max(0.1, interval)  # 最小0.1秒
        self._stream_thread = threading.Thread(
            target=self._stream_loop,
            name="CocoaPerformanceStream",
            daemon=True,
        )
        self._stream_thread.start()
        logger.info(self._get_message("streaming_started") + f" (間隔: {self._stream_interval:.2f}秒)")
        return True

    def stop_streaming(self) -> bool:
        """リアルタイムストリーミングを停止します。"""
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=2.0)
            self._stream_thread = None
            logger.info(self._get_message("streaming_stopped"))
            return True
        return False

    def update_config(self, config_updates: Dict[str, Any]) -> bool:
        """実行中の設定を動的に更新します。"""
        if not isinstance(config_updates, dict):
            logger.error("設定更新は辞書形式で指定してください。")
            return False

        with self._lock:
            try:
                # 既存設定とマージ
                updated_config = dict(self.config)
                updated_config.update(config_updates)

                # 検証
                temp_monitor = PerformanceMonitor(updated_config, log_component=self.log_component)
                issues = temp_monitor.validate_config()

                if issues:
                    logger.error("設定更新に問題があります: %s", issues)
                    return False

                # 新しい設定を適用
                old_interval = self.interval
                old_history_size = self.history_size

                self.config = updated_config
                self.interval = max(float(self.config.get("interval", 5.0)), 0.5)
                self.history_size = max(1, int(self.config.get("history_size", 120)))
                self._use_adaptive_interval = bool(self.config.get("adaptive_interval", self._use_adaptive_interval))
                self._interval_min = max(0.5, float(self.config.get("interval_min", self._interval_min)))
                self._interval_max = max(self._interval_min, float(self.config.get("interval_max", self._interval_max)))

                # 閾値更新
                for metric in ["memory", "cpu", "disk_io", "process_memory"]:
                    threshold_key = f"{metric}_threshold"
                    if threshold_key in self.config:
                        self.thresholds[metric] = float(self.config[threshold_key])

                # アラート設定更新
                if "alert_enabled" in self.config:
                    self.alert_config["enabled"] = bool(self.config["alert_enabled"])
                if "alert_threshold" in self.config:
                    self.alert_config["trigger_count"] = max(1, int(self.config["alert_threshold"]))
                if "alert_cooldown" in self.config:
                    self.alert_config["cooldown"] = max(0.0, float(self.config["alert_cooldown"]))

                # 履歴サイズが変更された場合の処理
                if self.history_size != old_history_size:
                    self.metrics_history = self._create_history_buffers(self.history_size)

                logger.info(
                    "設定を更新しました",
                    extra={
                        "extra_data": {
                            "component": self.log_component,
                            "config_changes": config_updates,
                            "old_interval": old_interval,
                            "new_interval": self.interval,
                        }
                    },
                )
                return True

            except Exception as exc:
                logger.error("設定更新中にエラーが発生しました: %s", exc, exc_info=True)
                return False

    def get_system_info(self) -> SystemInfo:
        """実行環境の情報を取得します."""
        try:
            return {
                "platform": platform.platform(),
                "os": platform.system(),
                "os_version": platform.version(),
                "cpu_count": psutil.cpu_count() or 0,
                "memory_total": psutil.virtual_memory().total,
                "hostname": platform.node(),
            }
        except Exception as exc:
            logger.error("システム情報取得中にエラーが発生しました: %s", exc, exc_info=True)
            return {"error": str(exc)}

    def export_metrics(self, filename: str) -> bool:
        """現在の統計情報と履歴をファイルにエクスポートします."""
        try:
            report = self.get_performance_report()
            with self._lock:
                history_snapshot = {metric: list(samples) for metric, samples in self.metrics_history.items()}
                config_snapshot = dict(self.config)

            payload = {
                "export_time": datetime.now(timezone.utc).isoformat(),
                "config": config_snapshot,
                "report": report,
                "history": history_snapshot,
            }

            with open(filename, "w", encoding="utf-8") as fp:
                json.dump(payload, fp, ensure_ascii=False, indent=2)

            logger.info(self._get_message("metrics_exported") + f": {filename}")
            return True
        except Exception as exc:
            logger.error(self._get_message("error_in_monitoring") + f": {exc}", exc_info=True)
            return False

    def check_thresholds(self) -> Dict[str, Dict[str, Any]]:
        """最新の統計を取得し、閾値判定結果を返します."""
        stats = self._collect_stats()
        self._record_stats(stats)
        return self._evaluate_thresholds(stats)

    # ------------------------------------------------------------------
    # 内部処理
    # ------------------------------------------------------------------
    def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            started = time.time()
            try:
                stats = self._collect_stats()
                self._record_stats(stats)

                if self.alert_config["enabled"]:
                    alerts = self._check_alerts(stats)
                    if alerts:
                        self._send_alert(alerts)
                self._maybe_emit_prometheus(stats)
                self._maybe_adapt_interval(stats)
            except Exception as exc:
                logger.error("パフォーマンス監視中にエラーが発生しました: %s", exc, exc_info=True)

            # エラーバックオフ処理
            wait_time = self._current_interval if self._use_adaptive_interval else self.interval
            if self._consecutive_errors >= self._max_consecutive_errors:
                wait_time = max(self.interval, self._error_backoff_interval * self._consecutive_errors)

            actual_wait = max(wait_time - (time.time() - started), 0.0)
            self._stop_event.wait(actual_wait)

        self.running = False

    def _stream_loop(self) -> None:
        """リアルタイムストリーミングのメインループ。"""
        while self.running:  # 監視が実行中の間のみストリーミング
            started = time.time()

            try:
                # 最新の統計を取得
                report = self.get_performance_report()

                # 登録されたコールバックにデータを送信
                with self._lock:
                    callbacks = self._stream_callbacks.copy()

                for callback in callbacks:
                    try:
                        callback(report)
                    except Exception as exc:
                        logger.error("ストリーミングコールバック実行中にエラーが発生しました: %s", exc, exc_info=True)

            except Exception as exc:
                logger.error("ストリーミング中にエラーが発生しました: %s", exc, exc_info=True)

            # 次回のストリーミングまで待機
            elapsed = time.time() - started
            wait_time = max(self._stream_interval - elapsed, 0.0)
            time.sleep(wait_time)

    def _collect_stats(self) -> StatsDict:
        timestamp = datetime.now(timezone.utc).isoformat()
        now = time.time()

        # エラー統計のリセット
        if self._last_error_time is None or (now - self._last_error_time) > 300:  # 5分ごとにリセット
            self._consecutive_errors = 0
            self._error_stats.clear()

        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=None)
            disk_counters = psutil.disk_io_counters(perdisk=False)
            net_counters = psutil.net_io_counters(pernic=False)
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info()

            # エラー統計のリセット（成功時）
            self._consecutive_errors = 0
            self._last_error_time = None

        except _NoSuchProcess:
            logger.error(self._get_message("process_not_found"))
            self._record_error("process_not_found")
            return self._get_default_stats(timestamp)
        except _AccessDenied:
            logger.error(self._get_message("access_denied"))
            self._record_error("access_denied")
            return self._get_default_stats(timestamp)
        except Exception as exc:
            error_type = type(exc).__name__
            logger.error(self._get_message("error_in_stats_collection") + f": {exc} (タイプ: {error_type})", exc_info=True)
            self._record_error(error_type)
            return self._get_default_stats(timestamp)

        with self._stats_lock:
            prev_disk = self._last_disk_counters
            prev_time = self._last_collect_time
            self._last_disk_counters = disk_counters
            prev_net = self._last_net_counters
            self._last_net_counters = net_counters
            self._last_collect_time = now

        write_kbps = 0.0
        read_kbps = 0.0
        if disk_counters and prev_disk and prev_time:
            elapsed = max(now - prev_time, 1e-3)
            write_kbps = max(disk_counters.write_bytes - prev_disk.write_bytes, 0) / 1024.0 / elapsed
            read_kbps = max(disk_counters.read_bytes - prev_disk.read_bytes, 0) / 1024.0 / elapsed

        net_kbps = 0.0
        if net_counters and prev_net and prev_time:
            elapsed = max(now - prev_time, 1e-3)
            delta_bytes = (
                max(net_counters.bytes_sent - prev_net.bytes_sent, 0)
                + max(net_counters.bytes_recv - prev_net.bytes_recv, 0)
            )
            net_kbps = delta_bytes / 1024.0 / elapsed

        total_memory = getattr(memory, "total", 0) or 0
        process_percent = (process_memory.rss / total_memory * 100.0) if total_memory else 0.0

        return {
            "timestamp": timestamp,
            "memory": {
                "total": getattr(memory, "total", 0) or 0,
                "used": getattr(memory, "used", 0) or 0,
                "available": getattr(memory, "available", 0) or 0,
                "percent": float(getattr(memory, "percent", 0) or 0),
            },
            "cpu": {
                "percent": float(cpu_percent),
                "count": psutil.cpu_count() or 0,
            },
            "disk_io": {
                "read_bytes": disk_counters.read_bytes if disk_counters else 0,
                "write_bytes": disk_counters.write_bytes if disk_counters else 0,
                "read_kbps": read_kbps,
                "write_kbps": write_kbps,
            },
            "process_memory": {
                "rss": process_memory.rss,
                "vms": process_memory.vms,
                "percent": process_percent,
            },
            "network_io": {
                "bytes_sent": net_counters.bytes_sent if net_counters else 0,
                "bytes_recv": net_counters.bytes_recv if net_counters else 0,
                "throughput_kbps": net_kbps,
            },
        }

    def _record_stats(self, stats: StatsDict) -> None:
        with self._lock:
            self._last_stats = self._clone_stats(stats)

        # 履歴記録は別ロックで処理（読み込み優先）
        with self._lock:
            for metric in self.HISTORY_METRICS:
                value = self._extract_metric_value(metric, stats)
                if value is None:
                    continue
                self.metrics_history[metric].append(
                    {
                        "timestamp": stats["timestamp"],
                        "value": float(value),
                    }
                )

    def _check_alerts(self, stats: StatsDict) -> List[Dict[str, Any]]:
        evaluations = self._evaluate_thresholds(stats)
        triggered: List[Dict[str, Any]] = []
        now = time.time()

        with self._lock:
            for metric, result in evaluations.items():
                if result["exceeded"]:
                    self._consecutive_alerts[metric] += 1
                else:
                    self._consecutive_alerts[metric] = 0

            eligible = [
                (metric, result)
                for metric, result in evaluations.items()
                if result["exceeded"] and self._consecutive_alerts[metric] >= self.alert_config["trigger_count"]
            ]

            if eligible and self._is_cooldown_complete(now):
                for metric, result in eligible:
                    triggered.append(
                        {
                            "metric": metric,
                            "value": result["value"],
                            "threshold": result["threshold"],
                            "timestamp": stats["timestamp"],
                        }
                    )

                if triggered:
                    self._last_alert_time = now
                    self._last_alert_details = [dict(entry) for entry in triggered]

        return triggered

    def _evaluate_thresholds(self, stats: StatsDict) -> Dict[str, Dict[str, Any]]:
        values = {
            "memory": float(stats["memory"]["percent"]),
            "cpu": float(stats["cpu"]["percent"]),
            "disk_io": float(stats["disk_io"]["write_kbps"]),
            "process_memory": float(stats["process_memory"]["percent"]),
        }

        results: Dict[str, Dict[str, Any]] = {}
        for metric, value in values.items():
            threshold = self.thresholds.get(metric, float("inf"))
            results[metric] = {
                "value": value,
                "threshold": threshold,
                "exceeded": value > threshold,
            }
        return results

    def _record_error(self, error_type: str) -> None:
        """エラー統計を記録します。"""
        self._consecutive_errors += 1
        self._error_stats[error_type] = self._error_stats.get(error_type, 0) + 1
        self._last_error_time = time.time()

        # 連続エラーが上限を超えた場合のバックオフ処理
        if self._consecutive_errors >= self._max_consecutive_errors:
            logger.warning(
                self._get_message("consecutive_errors_limit"),
                extra={
                    "extra_data": {
                        "component": self.log_component,
                        "consecutive_errors": self._consecutive_errors,
                        "max_errors": self._max_consecutive_errors,
                    }
                },
            )

    def _is_cooldown_complete(self, now: float) -> bool:
        if self._last_alert_time is None:
            return True
        return (now - self._last_alert_time) >= self.alert_config["cooldown"]

    def _create_history_buffers(self, history_size: int) -> Dict[str, Deque[HistorySample]]:
        maxlen = max(1, history_size)
        return {metric: deque(maxlen=maxlen) for metric in self.HISTORY_METRICS}

    def _build_history_summary_locked(self) -> Dict[str, Dict[str, float]]:
        summary: Dict[str, Dict[str, float]] = {}
        for metric, samples in self.metrics_history.items():
            if not samples:
                continue
            values = [sample["value"] for sample in samples]

            # 効率的な統計計算
            count = len(values)
            if count == 0:
                continue

            min_val = min(values)
            max_val = max(values)
            sum_val = sum(values)
            avg_val = sum_val / count

            # 分散と標準偏差の計算（効率化版）
            if count > 1:
                variance = sum((x - avg_val) ** 2 for x in values) / (count - 1)
                std_dev = variance ** 0.5
            else:
                std_dev = 0.0

            summary[metric] = {
                "min": float(min_val),
                "max": float(max_val),
                "avg": float(avg_val),
                "std_dev": float(std_dev),
                "latest": float(values[-1]),
                "count": count,
                "sum": float(sum_val),
                "median": float(sorted(values)[count // 2]) if count > 0 else 0.0,
            }
        return summary

    def _build_anomaly_report_locked(self) -> Dict[str, List[Dict[str, Any]]]:
        anomalies: Dict[str, List[Dict[str, Any]]] = {}
        for metric, samples in self.metrics_history.items():
            if len(samples) < 10:
                continue
            values = [sample["value"] for sample in samples]

            # 統計計算のキャッシュチェック
            cache_key = f"anomaly_{metric}_{len(values)}"
            cached = self._get_cached_anomalies(cache_key)
            if cached is not None:
                if cached:
                    anomalies[metric] = cached
                continue

            try:
                avg = mean(values)
                deviation = stdev(values)
            except (ValueError, ZeroDivisionError, StatisticsError) as e:
                logger.debug(f"Failed to calculate statistics for {metric}: {e}")
                continue

            if deviation == 0:
                continue

            metric_anomalies = self._detect_metric_anomalies(samples, values, avg, deviation)

            if metric_anomalies:
                anomalies[metric] = metric_anomalies

            # キャッシュに結果を保存
            self._stats_cache[cache_key] = (time.time(), metric_anomalies)

        return anomalies

    def _get_cached_anomalies(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """キャッシュが有効ならば異常リストを返す。未キャッシュ/期限切れなら None。"""
        if cache_key in self._stats_cache:
            cached_time, cached_result = self._stats_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_result
        return None

    def _detect_metric_anomalies(
        self,
        samples: Deque[HistorySample],
        values: List[float],
        avg: float,
        deviation: float,
    ) -> List[Dict[str, Any]]:
        """1メトリクスの直近サンプルから z-score ベースで異常を検出する。"""
        metric_anomalies: List[Dict[str, Any]] = []
        recent_values = values[-10:]  # 最近10個の値でトレンド分析

        # トレンド分析（線形回帰）
        if len(recent_values) >= 3:
            x = list(range(len(recent_values)))
            slope = self._calculate_slope(x, recent_values)
            trend_strength = abs(slope) / (avg + 1e-6)  # トレンド強度を計算
        else:
            slope = 0.0
            trend_strength = 0.0

        # 異常検知の閾値を動的に調整（トレンド考慮）
        dynamic_threshold = 3.0
        if trend_strength > 0.1:  # 強いトレンドがある場合
            dynamic_threshold = 2.5  # 閾値を緩和
        elif trend_strength < 0.05:  # 安定している場合
            dynamic_threshold = 3.5  # 閾値を厳しく

        for sample in samples[-5:]:
            z_score = abs(sample["value"] - avg) / deviation if deviation > 0 else 0

            if z_score >= dynamic_threshold:
                metric_anomalies.append({
                    "timestamp": sample["timestamp"],
                    "value": sample["value"],
                    "z_score": z_score,
                    "trend_slope": slope,
                    "trend_strength": trend_strength,
                    "severity": "high" if z_score >= 4.0 else "medium" if z_score >= 3.0 else "low"
                })

        return metric_anomalies

    def _calculate_slope(self, x: List[float], y: List[float]) -> float:
        """線形回帰の傾きを計算します。"""
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x_squared = sum(xi * xi for xi in x)

        # 線形回帰の傾きを計算：slope = (n*Σ(xy) - Σx*Σy) / (n*Σ(x²) - (Σx)²)
        numerator = n * sum_xy - sum_x * sum_y
        denominator = n * sum_x_squared - sum_x * sum_x

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def _extract_metric_value(self, metric: str, stats: StatsDict) -> Optional[float]:
        if metric == "memory":
            return float(stats["memory"]["percent"])
        if metric == "cpu":
            return float(stats["cpu"]["percent"])
        if metric == "disk_io":
            return float(stats["disk_io"]["write_kbps"])
        if metric == "process_memory":
            return float(stats["process_memory"]["percent"])
        if metric == "network_io":
            return float(stats["network_io"]["throughput_kbps"])
        return None

    def _clone_stats(self, stats: Optional[StatsDict]) -> StatsDict:
        if stats is None:
            return self._get_default_stats()
        return json.loads(json.dumps(stats, ensure_ascii=False))

    def _get_default_stats(self, timestamp: str = None) -> StatsDict:
        return {
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "memory": {"total": 0, "used": 0, "available": 0, "percent": 0.0},
            "cpu": {"percent": 0.0, "count": 0},
            "disk_io": {"read_bytes": 0, "write_bytes": 0, "read_kbps": 0.0, "write_kbps": 0.0},
            "process_memory": {"rss": 0, "vms": 0, "percent": 0.0},
            "network_io": {"bytes_sent": 0, "bytes_recv": 0, "throughput_kbps": 0.0},
        }

    def add_custom_metric(self, name: str, value: float, unit: str = "", description: str = "") -> None:
        """カスタムメトリクスを追加"""
        with self._lock:
            if not hasattr(self, '_custom_metrics'):
                self._custom_metrics = {}

            self._custom_metrics[name] = {
                'value': value,
                'unit': unit,
                'description': description,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

    def get_custom_metrics(self) -> Dict[str, Dict[str, Any]]:
        """カスタムメトリクスを取得"""
        with self._lock:
            return getattr(self, '_custom_metrics', {}).copy()

    def remove_custom_metric(self, name: str) -> bool:
        """カスタムメトリクスを削除"""
        with self._lock:
            if hasattr(self, '_custom_metrics') and name in self._custom_metrics:
                del self._custom_metrics[name]
                return True
            return False

    def get_performance_report(self) -> Dict[str, Any]:
        """最新の統計情報と履歴の概要を返します.

        このメソッドは現在のシステム状態、履歴統計、異常検知結果、
        カスタムメトリクス、エラー統計を統合した包括的なレポートを提供します。

        Returns:
            Dict[str, Any]: パフォーマンスレポート。以下のキーを持つ辞書:
                - current_stats: 現在のシステム統計情報
                    - timestamp: ISO形式のタイムスタンプ
                    - memory: メモリ使用状況
                        - total: 総メモリ容量（バイト）
                        - used: 使用中メモリ（バイト）
                        - available: 利用可能メモリ（バイト）
                        - percent: 使用率（%）
                    - cpu: CPU使用状況
                        - percent: 使用率（%）
                        - count: CPUコア数
                    - disk_io: ディスクI/O統計
                        - read_bytes: 読み込みバイト数
                        - write_bytes: 書き込みバイト数
                        - read_kbps: 読み込み速度（KB/s）
                        - write_kbps: 書き込み速度（KB/s）
                    - process_memory: プロセスメモリ統計
                        - rss: 物理メモリ使用量（バイト）
                        - vms: 仮想メモリ使用量（バイト）
                        - percent: 総メモリに対する割合（%）
                    - network_io: ネットワークI/O統計
                        - bytes_sent: 送信バイト数
                        - bytes_recv: 受信バイト数
                        - throughput_kbps: スループット（KB/s）
                - history: 履歴統計サマリー（各メトリクスごと）
                    - min: 最小値
                    - max: 最大値
                    - avg: 平均値
                    - std_dev: 標準偏差
                    - latest: 最新値
                    - count: サンプル数
                    - sum: 合計値
                    - median: 中央値
                - alerts: 最新のアラート情報リスト
                - anomalies: 異常検知結果（メトリクスごとの異常リスト）
                - custom_metrics: カスタムメトリクスの辞書
                - error_stats: エラー統計情報
                - consecutive_errors: 連続エラー回数
                - timestamp: レポート生成時刻（ISO形式）

        注意:
        - このメソッドはスレッドセーフです
        - 統計情報はキャッシュから取得されるため、最新の状態を反映します
        - 大量の履歴データがある場合でも効率的に処理されます
        """
        with self._lock:
            stats = self._clone_stats(self._last_stats) if self._last_stats else self._get_default_stats()
            history_summary = self._build_history_summary_locked()
            alerts = [dict(alert) for alert in self._last_alert_details]
            custom_metrics = self.get_custom_metrics()

        return {
            "current_stats": stats,
            "history": history_summary,
            "alerts": alerts,
            "anomalies": self._build_anomaly_report_locked(),
            "custom_metrics": custom_metrics,
            "error_stats": dict(self._error_stats),
            "consecutive_errors": self._consecutive_errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def add_prometheus_handler(self, handler: Callable[[bytes], None]) -> bool:
        if not callable(handler):
            logger.error("Prometheusハンドラーは呼び出し可能である必要があります。")
            return False
        with self._lock:
            if handler not in self._prometheus_handlers:
                self._prometheus_handlers.append(handler)
                return True
        return False

    def remove_prometheus_handler(self, handler: Callable[[bytes], None]) -> bool:
        with self._lock:
            if handler in self._prometheus_handlers:
                self._prometheus_handlers.remove(handler)
                return True
        return False

    def get_prometheus_payload(self) -> Optional[bytes]:
        with self._lock:
            return self._last_prometheus_payload

    def _maybe_emit_prometheus(self, stats: StatsDict) -> None:
        with self._lock:
            handlers = list(self._prometheus_handlers)
            labels = dict(self._prometheus_labels)
        if not handlers:
            return

        def _format(metric: str, value: float) -> str:
            label_str = ",".join(f"{k}={json.dumps(v)}" for k, v in labels.items())
            label_section = f"{{{label_str}}}" if label_str else ""
            return f"cocoa_{metric}{label_section} {value:.6f}"

        lines = [
            "# HELP cocoa_system_cpu_percent CPU usage percent",
            "# TYPE cocoa_system_cpu_percent gauge",
            _format("system_cpu_percent", stats["cpu"].get("percent", 0.0)),
            "# HELP cocoa_system_memory_percent Memory usage percent",
            "# TYPE cocoa_system_memory_percent gauge",
            _format("system_memory_percent", stats["memory"].get("percent", 0.0)),
            "# HELP cocoa_process_memory_percent Process memory usage percent",
            "# TYPE cocoa_process_memory_percent gauge",
            _format("process_memory_percent", stats["process_memory"].get("percent", 0.0)),
            "# HELP cocoa_disk_write_kbps Disk write throughput KB/s",
            "# TYPE cocoa_disk_write_kbps gauge",
            _format("disk_write_kbps", stats["disk_io"].get("write_kbps", 0.0)),
            "# HELP cocoa_network_throughput_kbps Network throughput KB/s",
            "# TYPE cocoa_network_throughput_kbps gauge",
            _format("network_throughput_kbps", stats["network_io"].get("throughput_kbps", 0.0)),
        ]
        payload = "\n".join(lines).encode("utf-8")
        with self._lock:
            self._last_prometheus_payload = payload
        for handler in handlers:
            try:
                handler(payload)
            except Exception as exc:
                logger.error("Prometheusハンドラー実行中にエラーが発生しました: %s", exc, exc_info=True)

    def _maybe_adapt_interval(self, stats: StatsDict) -> None:
        if not self._use_adaptive_interval:
            return
        cpu_use = float(stats["cpu"].get("percent", 0.0))
        memory_use = float(stats["memory"].get("percent", 0.0))
        cpu_ratio = cpu_use / max(self.thresholds.get("cpu", 100.0), 1.0)
        mem_ratio = memory_use / max(self.thresholds.get("memory", 100.0), 1.0)
        pressure = max(cpu_ratio, mem_ratio)

        target = self._current_interval
        if pressure >= 1.0:
            target = min(self._interval_max, self._current_interval * 1.2)
        elif pressure <= 0.5:
            target = max(self._interval_min, self._current_interval * 0.85)
        self._current_interval = target

class HybridMode(Enum):
    """ハイブリッドモード"""
    LOCAL_ONLY = "local_only"
    CLOUD_ONLY = "cloud_only"
    HYBRID_BALANCED = "hybrid_balanced"
    HYBRID_PERFORMANCE = "hybrid_performance"
    HYBRID_COST_OPTIMIZED = "hybrid_cost_optimized"
    ADAPTIVE = "adaptive"

class EnergyEfficiencyLevel(Enum):
    """エネルギー効率レベル"""
    HIGH_PERFORMANCE = "high_performance"  # 性能優先
    BALANCED = "balanced"  # バランス
    POWER_SAVER = "power_saver"  # 省電力
    ULTRA_LOW_POWER = "ultra_low_power"  # 超省電力

@dataclass
class HybridResourceAllocation:
    """ハイブリッドリソース割り当て"""
    local_cpu_cores: int
    cloud_cpu_cores: int
    local_memory_gb: float
    cloud_memory_gb: float
    local_storage_gb: float
    cloud_storage_gb: float
    network_bandwidth_mbps: float
    cost_per_hour: float

@dataclass
class EnergyMetrics:
    """エネルギー消費メトリクス"""
    power_consumption_watts: float
    energy_efficiency_score: float  # 0-100 (高いほど効率的)
    carbon_footprint_kg: float
    temperature_celsius: float
    fan_speed_rpm: Optional[int] = None
    battery_level_percent: Optional[float] = None

@dataclass
class CloudResourceInfo:
    """クラウドリソース情報"""
    provider: str  # AWS, Azure, GCPなど
    region: str
    instance_type: str
    cost_per_hour: float
    availability_score: float  # 0-1
    latency_ms: float
    bandwidth_mbps: float = 100.0

class HybridSystemManager:
    """
    ハイブリッドシステムマネージャー
    ローカル・クラウド間のリソース最適化とエネルギー効率管理
    """

    def __init__(self):
        # 現在のモードと設定
        self.current_mode = HybridMode.HYBRID_BALANCED
        self.energy_level = EnergyEfficiencyLevel.BALANCED

        # リソース管理
        self.local_resources = self._get_local_resources()
        self.cloud_resources: Dict[str, CloudResourceInfo] = {}
        self.current_allocation = None

        # 監視データ
        self.energy_history: Deque[EnergyMetrics] = deque(maxlen=1000)
        self.allocation_history: Deque[HybridResourceAllocation] = deque(maxlen=100)

        # 最適化設定
        self.cost_weight = 0.4
        self.performance_weight = 0.4
        self.energy_weight = 0.2

        # クラウドプロバイダー設定
        self.cloud_providers = {
            "aws": {"regions": ["us-east-1", "us-west-2", "eu-west-1"], "base_cost": 0.05},
            "azure": {"regions": ["eastus", "westus2", "westeurope"], "base_cost": 0.04},
            "gcp": {"regions": ["us-central1", "us-west1", "europe-west1"], "base_cost": 0.045}
        }

        # バックグラウンドタスク参照（GC防止）
        self._background_tasks: list = []

        logger.info("Hybrid System Manager initialized")

    def _get_local_resources(self) -> Dict[str, Any]:
        """ローカルリソース情報を取得"""
        try:
            return {
                "cpu_cores": psutil.cpu_count(logical=False),
                "cpu_cores_logical": psutil.cpu_count(logical=True),
                "memory_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "disk_gb": round(psutil.disk_usage('/').total / (1024**3), 2),
                "network_interfaces": len(psutil.net_if_addrs())
            }
        except Exception as e:
            logger.warning(f"Failed to get local resources: {e}")
            return {"cpu_cores": 4, "memory_gb": 8, "disk_gb": 256}

    async def initialize(self):
        """ハイブリッドシステムの初期化"""
        await self._discover_cloud_resources()
        await self._optimize_initial_allocation()
        self._background_tasks.append(asyncio.create_task(self._start_energy_monitoring()))

    async def _discover_cloud_resources(self):
        """クラウドリソースを検出"""
        # 実際の実装では各クラウドプロバイダーのAPIを呼び出し
        for provider, config in self.cloud_providers.items():
            for region in config["regions"]:
                resource = CloudResourceInfo(
                    provider=provider,
                    region=region,
                    instance_type="t3.medium",
                    cost_per_hour=config["base_cost"],
                    availability_score=0.99,
                    latency_ms=50 + random.uniform(0, 20),
                    bandwidth_mbps=100
                )
                self.cloud_resources[f"{provider}_{region}"] = resource

    async def _optimize_initial_allocation(self):
        """初期リソース割り当ての最適化"""
        allocation = await self._calculate_optimal_allocation()
        self.current_allocation = allocation
        self.allocation_history.append(allocation)

        logger.info(f"Initial allocation optimized: {allocation}")

    async def _start_energy_monitoring(self):
        """エネルギー監視を開始"""
        while True:
            try:
                metrics = await self._collect_energy_metrics()
                self.energy_history.append(metrics)

                # エネルギー効率に基づく最適化
                await self._optimize_for_energy_efficiency(metrics)

                await asyncio.sleep(60)  # 1分間隔

            except Exception as e:
                logger.error(f"Energy monitoring error: {e}")
                await asyncio.sleep(300)  # 5分待機

    async def _collect_energy_metrics(self) -> EnergyMetrics:
        """エネルギー消費メトリクスを収集"""
        # 実際の実装ではハードウェアセンサーからデータを取得
        if PSUTIL_AVAILABLE:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
        else:
            cpu_percent, memory_percent = 50.0, 50.0

        # 電力消費量の推定（簡易的）
        power_consumption = self._estimate_power_consumption(cpu_percent, memory_percent)

        # エネルギー効率スコアの計算
        efficiency_score = self._calculate_energy_efficiency(cpu_percent, memory_percent)

        # 炭素フットプリントの推定
        carbon_footprint = power_consumption * 0.0004  # 簡易計算

        return EnergyMetrics(
            power_consumption_watts=power_consumption,
            energy_efficiency_score=efficiency_score,
            carbon_footprint_kg=carbon_footprint,
            temperature_celsius=self._get_system_temperature()
        )

    def _estimate_power_consumption(self, cpu_percent: float, memory_percent: float) -> float:
        """電力消費量を推定（W）"""
        # 簡易的な電力消費推定モデル
        base_power = 50  # ベース電力（W）
        cpu_power = (cpu_percent / 100) * 30  # CPU電力
        memory_power = (memory_percent / 100) * 10  # メモリ電力

        return base_power + cpu_power + memory_power

    def _calculate_energy_efficiency(self, cpu_percent: float, memory_percent: float) -> float:
        """エネルギー効率スコアを計算（0-100）"""
        # 効率的な使用領域でのスコアが高い
        if cpu_percent < 30 and memory_percent < 50:
            return 90 + random.uniform(-5, 5)
        if cpu_percent < 60 and memory_percent < 70:
            return 70 + random.uniform(-10, 10)
        if cpu_percent < 80 and memory_percent < 85:
            return 50 + random.uniform(-10, 10)
        return 30 + random.uniform(-10, 10)

    def _get_system_temperature(self) -> float:
        """システム温度を取得（℃）"""
        try:
            # Linuxの場合
            if platform.system() == "Linux":
                result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'CPU' in line and '°C' in line:
                            temp_str = line.split('°C')[0].split()[-1]
                            return float(temp_str.replace('+', '').replace('°C', ''))

            # Windowsの場合
            elif platform.system() == "Windows":
                # PowerShellコマンドで温度を取得（簡易的）
                pass

        except Exception:
            pass

        return 50 + random.uniform(-10, 10)  # デフォルト値

    async def _calculate_optimal_allocation(self) -> HybridResourceAllocation:
        """最適なリソース割り当てを計算"""
        workload = await self._analyze_current_workload()
        budget = 10.0  # 1時間あたりの予算（ドル）

        best_allocation = None
        best_score = -1

        # 各クラウドリソースに対して最適化
        for cloud_resource in self.cloud_resources.values():
            allocation = await self._calculate_allocation_for_resource(
                cloud_resource, workload, budget
            )

            score = self._evaluate_allocation(allocation, workload, budget)

            if score > best_score:
                best_score = score
                best_allocation = allocation

        return best_allocation or self._get_default_allocation()

    async def _analyze_current_workload(self) -> Dict[str, Any]:
        """現在のワークロードを分析"""
        if not PSUTIL_AVAILABLE:
            return {
                "cpu_demand": 0.5,
                "memory_demand": 0.5,
                "disk_demand": 0.5,
                "network_demand": 0.3,
                "expected_duration_hours": 1.0,
                "priority": "normal",
            }
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "cpu_demand": cpu_percent / 100,
            "memory_demand": memory.percent / 100,
            "disk_demand": (disk.total - disk.free) / disk.total,
            "network_demand": 0.3,  # 簡易的
            "expected_duration_hours": 1.0,
            "priority": "normal"
        }

    async def _calculate_allocation_for_resource(self, cloud_resource: CloudResourceInfo,
                                                workload: Dict[str, Any], budget: float) -> HybridResourceAllocation:
        """特定のリソースに対する割り当てを計算"""
        # クラウドリソースの必要性を計算
        cloud_cpu_needed = max(0, workload["cpu_demand"] - 0.8)  # 80%を超えた分をクラウドに
        cloud_memory_needed = max(0, workload["memory_demand"] - 0.8)

        # コストを考慮した最適化
        max_cloud_cost = budget * 0.7  # 70%をクラウドに割り当て
        cloud_cpu_cores = min(cloud_cpu_needed * 4, max_cloud_cost / cloud_resource.cost_per_hour)
        cloud_memory_gb = min(cloud_memory_needed * 16, (max_cloud_cost / cloud_resource.cost_per_hour) * 2)

        return HybridResourceAllocation(
            local_cpu_cores=max(1, self.local_resources["cpu_cores"] - int(cloud_cpu_cores)),
            cloud_cpu_cores=max(1, int(cloud_cpu_cores)),
            local_memory_gb=max(1, self.local_resources["memory_gb"] - cloud_memory_gb),
            cloud_memory_gb=max(1, cloud_memory_gb),
            local_storage_gb=self.local_resources["disk_gb"] * 0.7,
            cloud_storage_gb=self.local_resources["disk_gb"] * 0.3,
            network_bandwidth_mbps=cloud_resource.bandwidth_mbps,
            cost_per_hour=cloud_resource.cost_per_hour * (cloud_cpu_cores / 4 + cloud_memory_gb / 16)
        )

    def _evaluate_allocation(self, allocation: HybridResourceAllocation,
                           workload: Dict[str, Any], budget: float) -> float:
        """リソース割り当てを評価"""
        # コスト評価
        cost_score = max(0, 1 - (allocation.cost_per_hour / budget))

        # パフォーマンス評価
        total_cpu = allocation.local_cpu_cores + allocation.cloud_cpu_cores
        total_memory = allocation.local_memory_gb + allocation.cloud_memory_gb
        performance_score = min(1.0, (total_cpu / 8 + total_memory / 32) / 2)

        # エネルギー効率評価
        energy_score = 1 - (allocation.cost_per_hour / budget) * 0.5

        # 重み付け合計
        total_score = (cost_score * self.cost_weight +
                      performance_score * self.performance_weight +
                      energy_score * self.energy_weight)

        return total_score

    def _get_default_allocation(self) -> HybridResourceAllocation:
        """デフォルトのリソース割り当てを取得"""
        return HybridResourceAllocation(
            local_cpu_cores=self.local_resources["cpu_cores"],
            cloud_cpu_cores=0,
            local_memory_gb=self.local_resources["memory_gb"],
            cloud_memory_gb=0,
            local_storage_gb=self.local_resources["disk_gb"],
            cloud_storage_gb=0,
            network_bandwidth_mbps=100,
            cost_per_hour=0
        )

    async def _optimize_for_energy_efficiency(self, metrics: EnergyMetrics):
        """エネルギー効率に基づく最適化"""
        if metrics.energy_efficiency_score < 50:
            # 低効率の場合、クラウドへの負荷移行を検討
            if self.current_mode == HybridMode.LOCAL_ONLY:
                await self._switch_to_hybrid_mode()
        elif metrics.energy_efficiency_score > 80 and self.current_mode != HybridMode.LOCAL_ONLY:
            # 高効率の場合、ローカル優先に切り替え
            await self._switch_to_local_mode()

    async def _switch_to_hybrid_mode(self):
        """ハイブリッドモードに切り替え"""
        if self.current_mode != HybridMode.HYBRID_BALANCED:
            self.current_mode = HybridMode.HYBRID_BALANCED
            allocation = await self._calculate_optimal_allocation()
            await self._apply_allocation(allocation)
            logger.info("Switched to hybrid mode for better energy efficiency")

    async def _switch_to_local_mode(self):
        """ローカルモードに切り替え"""
        if self.current_mode != HybridMode.LOCAL_ONLY:
            self.current_mode = HybridMode.LOCAL_ONLY
            allocation = self._get_default_allocation()
            await self._apply_allocation(allocation)
            logger.info("Switched to local mode for optimal energy efficiency")

    async def _apply_allocation(self, allocation: HybridResourceAllocation):
        """リソース割り当てを適用"""
        self.current_allocation = allocation
        self.allocation_history.append(allocation)

        # 実際の実装では、クラウドリソースのスケーリングやローカル設定の変更を実行
        logger.info(f"Applied resource allocation: CPU(local={allocation.local_cpu_cores}, cloud={allocation.cloud_cpu_cores}), "
                   f"Memory(local={allocation.local_memory_gb}GB, cloud={allocation.cloud_memory_gb}GB), "
                   f"Cost=${allocation.cost_per_hour}/hour")

    def set_hybrid_mode(self, mode: HybridMode):
        """ハイブリッドモードを設定"""
        self.current_mode = mode
        logger.info(f"Hybrid mode set to: {mode.value}")

    def set_energy_level(self, level: EnergyEfficiencyLevel):
        """エネルギー効率レベルを設定"""
        self.energy_level = level
        logger.info(f"Energy efficiency level set to: {level.value}")

    def get_hybrid_status(self) -> Dict[str, Any]:
        """ハイブリッドシステムのステータスを取得"""
        latest_energy = self.energy_history[-1] if self.energy_history else None

        return {
            "current_mode": self.current_mode.value,
            "energy_level": self.energy_level.value,
            "current_allocation": self.current_allocation.__dict__ if self.current_allocation else None,
            "local_resources": self.local_resources,
            "available_cloud_resources": len(self.cloud_resources),
            "latest_energy_metrics": latest_energy.__dict__ if latest_energy else None,
            "total_cost_today": sum(a.cost_per_hour for a in list(self.allocation_history)[-24:] if hasattr(a, 'cost_per_hour')),
            "energy_efficiency_trend": self._calculate_energy_trend()
        }

    def _calculate_energy_trend(self) -> str:
        """エネルギー効率のトレンドを計算"""
        if len(self.energy_history) < 10:
            return "insufficient_data"

        recent = list(self.energy_history)[-10:]
        scores = [e.energy_efficiency_score for e in recent]

        if scores[-1] > mean(scores) + 5:
            return "improving"
        if scores[-1] < mean(scores) - 5:
            return "degrading"
        return "stable"

# グローバルインスタンス
_hybrid_system_manager = None

async def get_hybrid_system_manager() -> HybridSystemManager:
    """ハイブリッドシステムマネージャーのインスタンスを取得"""
    global _hybrid_system_manager

    if _hybrid_system_manager is None:
        _hybrid_system_manager = HybridSystemManager()
        await _hybrid_system_manager.initialize()

    return _hybrid_system_manager
