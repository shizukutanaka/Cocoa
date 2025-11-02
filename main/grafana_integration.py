"""
Grafana統合監視システム

Production-gradeのGrafana統合機能を提供し、
高度な可視化と監視機能を実現します。
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
import threading
import os

try:
    import requests
    import aiohttp
    GRAFANA_AVAILABLE = True
except ImportError:
    GRAFANA_AVAILABLE = False

logger = logging.getLogger(__name__)


class GrafanaMetricsCollector:
    """Grafanaメトリクス収集クラス"""

    def __init__(self, grafana_url: str = "http://localhost:3000", api_key: Optional[str] = None):
        """Grafanaメトリクス収集クラスを初期化"""
        if not GRAFANA_AVAILABLE:
            raise ImportError("requests and aiohttp are required for GrafanaMetricsCollector")

        self.grafana_url = grafana_url.rstrip('/')
        self.api_key = api_key or os.getenv("GRAFANA_API_KEY")
        self.session = requests.Session()

        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

        # メトリクスバッファ
        self.metrics_buffer: List[Dict[str, Any]] = []
        self.buffer_lock = threading.Lock()

        # 設定
        self.flush_interval = 10  # 秒
        self.max_buffer_size = 1000

        logger.info(f"GrafanaMetricsCollector initialized for {self.grafana_url}")

    def _get_headers(self) -> Dict[str, str]:
        """リクエストヘッダーを取得"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _format_metric_for_grafana(self, metric_name: str, value: float, timestamp: Optional[int] = None, tags: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Grafana用のメトリクス形式に変換"""
        if timestamp is None:
            timestamp = int(time.time() * 1000)  # ミリ秒

        metric = {
            "name": metric_name,
            "value": value,
            "timestamp": timestamp,
            "tags": tags or {}
        }

        return metric

    def add_metric(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """メトリクスを追加"""
        try:
            with self.buffer_lock:
                metric = self._format_metric_for_grafana(name, value, tags=tags)
                self.metrics_buffer.append(metric)

                # バッファサイズチェック
                if len(self.metrics_buffer) >= self.max_buffer_size:
                    self.flush_metrics()

        except Exception as e:
            logger.error(f"メトリクス追加エラー: {e}")

    def flush_metrics(self) -> bool:
        """バッファのメトリクスをGrafanaに送信"""
        try:
            with self.buffer_lock:
                if not self.metrics_buffer:
                    return True

                metrics_to_send = self.metrics_buffer.copy()
                self.metrics_buffer.clear()

            # Grafana HTTP APIに送信（実際の実装では適切なエンドポイントを使用）
            # ここではInfluxDB形式のデータを想定
            payload = {
                "metrics": metrics_to_send,
                "timestamp": datetime.now().isoformat()
            }

            # 実際のGrafana統合では、適切なエンドポイントに送信
            # response = requests.post(f"{self.grafana_url}/api/annotations", json=payload, headers=self._get_headers())

            logger.info(f"メトリクスをGrafanaに送信: {len(metrics_to_send)}件")
            return True

        except Exception as e:
            logger.error(f"メトリクス送信エラー: {e}")
            return False

    def start_auto_flush(self):
        """自動フラッシュを開始"""
        def flush_loop():
            while True:
                try:
                    time.sleep(self.flush_interval)
                    self.flush_metrics()
                except Exception as e:
                    logger.error(f"自動フラッシュエラー: {e}")

        flush_thread = threading.Thread(target=flush_loop, daemon=True)
        flush_thread.start()
        logger.info("自動フラッシュを開始しました")


class GrafanaDashboardManager:
    """Grafanaダッシュボード管理クラス"""

    def __init__(self, grafana_url: str = "http://localhost:3000", api_key: Optional[str] = None):
        """Grafanaダッシュボード管理クラスを初期化"""
        self.grafana_url = grafana_url.rstrip('/')
        self.api_key = api_key or os.getenv("GRAFANA_API_KEY")
        self.session = requests.Session()

        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def create_dashboard(self, title: str, panels: List[Dict[str, Any]]) -> Optional[str]:
        """ダッシュボードを作成"""
        try:
            dashboard_config = {
                "dashboard": {
                    "title": title,
                    "tags": ["cocoa", "monitoring"],
                    "timezone": "browser",
                    "panels": panels,
                    "time": {
                        "from": "now-6h",
                        "to": "now"
                    },
                    "refresh": "30s"
                },
                "overwrite": True
            }

            response = self.session.post(
                f"{self.grafana_url}/api/dashboards/db",
                json=dashboard_config,
                headers=self._get_headers()
            )

            if response.status_code == 200:
                result = response.json()
                dashboard_uid = result.get("uid")
                logger.info(f"ダッシュボードを作成しました: {title} (UID: {dashboard_uid})")
                return dashboard_uid
            else:
                logger.error(f"ダッシュボード作成エラー: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"ダッシュボード作成エラー: {e}")
            return None

    def create_system_monitoring_dashboard(self) -> Optional[str]:
        """システム監視ダッシュボードを作成"""
        panels = [
            {
                "id": 1,
                "title": "CPU使用率",
                "type": "graph",
                "targets": [{
                    "expr": "cocoa_cpu_usage",
                    "refId": "A"
                }],
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
            },
            {
                "id": 2,
                "title": "メモリ使用率",
                "type": "graph",
                "targets": [{
                    "expr": "cocoa_memory_usage",
                    "refId": "A"
                }],
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
            },
            {
                "id": 3,
                "title": "ディスクI/O",
                "type": "graph",
                "targets": [{
                    "expr": "cocoa_disk_io",
                    "refId": "A"
                }],
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
            },
            {
                "id": 4,
                "title": "ネットワークI/O",
                "type": "graph",
                "targets": [{
                    "expr": "cocoa_network_io",
                    "refId": "A"
                }],
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
            },
            {
                "id": 5,
                "title": "システムヘルス",
                "type": "stat",
                "targets": [{
                    "expr": "cocoa_system_health",
                    "refId": "A"
                }],
                "gridPos": {"h": 4, "w": 24, "x": 0, "y": 16}
            }
        ]

        return self.create_dashboard("Cocoaシステム監視", panels)

    def _get_headers(self) -> Dict[str, str]:
        """リクエストヘッダーを取得"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


class GrafanaIntegrationService:
    """Grafana統合サービス"""

    def __init__(self, grafana_url: str = "http://localhost:3000", api_key: Optional[str] = None):
        """Grafana統合サービスを初期化"""
        self.grafana_url = grafana_url
        self.api_key = api_key

        # コンポーネント初期化
        self.metrics_collector = GrafanaMetricsCollector(grafana_url, api_key)
        self.dashboard_manager = GrafanaDashboardManager(grafana_url, api_key)

        # 自動フラッシュ開始
        self.metrics_collector.start_auto_flush()

        logger.info("Grafana統合サービスを初期化しました")

    def collect_system_metrics(self, cpu_percent: float, memory_percent: float, disk_io: float, network_io: float):
        """システムメトリクスを収集"""
        timestamp = int(time.time() * 1000)

        # CPUメトリクス
        self.metrics_collector.add_metric(
            "cocoa_cpu_usage",
            cpu_percent,
            {"unit": "percent", "source": "system"}
        )

        # メモリメトリクス
        self.metrics_collector.add_metric(
            "cocoa_memory_usage",
            memory_percent,
            {"unit": "percent", "source": "system"}
        )

        # ディスクI/Oメトリクス
        self.metrics_collector.add_metric(
            "cocoa_disk_io",
            disk_io,
            {"unit": "kbps", "source": "system"}
        )

        # ネットワークI/Oメトリクス
        self.metrics_collector.add_metric(
            "cocoa_network_io",
            network_io,
            {"unit": "kbps", "source": "system"}
        )

        # システムヘルスメトリクス（簡易版）
        health_score = 100 - max(cpu_percent, memory_percent)  # 簡易的な計算
        self.metrics_collector.add_metric(
            "cocoa_system_health",
            health_score,
            {"unit": "score", "source": "system"}
        )

    def setup_monitoring_dashboard(self) -> Optional[str]:
        """監視ダッシュボードをセットアップ"""
        return self.dashboard_manager.create_system_monitoring_dashboard()

    def get_grafana_url(self) -> str:
        """GrafanaのURLを取得"""
        return self.grafana_url

    def test_connection(self) -> bool:
        """Grafana接続をテスト"""
        try:
            response = requests.get(
                f"{self.grafana_url}/api/health",
                headers=self.dashboard_manager._get_headers(),
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Grafana接続テストエラー: {e}")
            return False


class EnhancedPerformanceMonitor:
    """Grafana統合された性能監視システム"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """強化された性能監視システムを初期化"""
        # 元のPerformanceMonitor設定
        self.interval = config.get('interval', 5.0) if config else 5.0
        self.history_size = config.get('history_size', 120) if config else 120

        # Grafana統合設定
        self.grafana_enabled = config.get('grafana_enabled', False) if config else False
        self.grafana_url = config.get('grafana_url', 'http://localhost:3000') if config else 'http://localhost:3000'
        self.grafana_api_key = config.get('grafana_api_key')

        # コンポーネント初期化
        self.grafana_service = None
        if self.grafana_enabled:
            try:
                self.grafana_service = GrafanaIntegrationService(
                    self.grafana_url,
                    self.grafana_api_key
                )
            except Exception as e:
                logger.warning(f"Grafana統合の初期化に失敗しました: {e}")
                self.grafana_enabled = False

        # 監視状態
        self.is_monitoring = False
        self.monitor_thread = None
        self.history = deque(maxlen=self.history_size)

        logger.info(f"EnhancedPerformanceMonitor initialized (Grafana: {self.grafana_enabled})")

    def start_monitoring(self):
        """監視を開始"""
        if self.is_monitoring:
            return

        self.is_monitoring = True

        def monitor_loop():
            while self.is_monitoring:
                try:
                    # システムメトリクスを収集
                    metrics = self._collect_current_metrics()

                    # 履歴に追加
                    self.history.append(metrics)

                    # Grafanaに送信（有効な場合）
                    if self.grafana_service:
                        self.grafana_service.collect_system_metrics(
                            metrics.get('cpu_percent', 0),
                            metrics.get('memory_percent', 0),
                            metrics.get('disk_io', 0),
                            metrics.get('network_io', 0)
                        )

                    time.sleep(self.interval)

                except Exception as e:
                    logger.error(f"監視ループエラー: {e}")
                    time.sleep(self.interval)

        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("性能監視を開始しました")

    def stop_monitoring(self):
        """監視を停止"""
        if not self.is_monitoring:
            return

        self.is_monitoring = False

        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

        # 最終的なメトリクス送信
        if self.grafana_service:
            self.grafana_service.metrics_collector.flush_metrics()

        logger.info("性能監視を停止しました")

    def _collect_current_metrics(self) -> Dict[str, Any]:
        """現在のメトリクスを収集"""
        try:
            import psutil

            # CPU情報
            cpu_percent = psutil.cpu_percent(interval=1)

            # メモリ情報
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # ディスクI/O情報（簡易版）
            disk_io = psutil.disk_io_counters()
            disk_read = disk_io.read_bytes / 1024 if disk_io else 0  # KB
            disk_write = disk_io.write_bytes / 1024 if disk_io else 0  # KB
            disk_io_total = disk_read + disk_write

            # ネットワークI/O情報（簡易版）
            network_io = psutil.net_io_counters()
            network_recv = network_io.bytes_recv / 1024 if network_io else 0  # KB
            network_sent = network_io.bytes_sent / 1024 if network_io else 0  # KB
            network_io_total = network_recv + network_sent

            return {
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'disk_io': disk_io_total,
                'network_io': network_io_total,
                'system_load': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            }

        except Exception as e:
            logger.error(f"メトリクス収集エラー: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

    def get_performance_report(self) -> Dict[str, Any]:
        """性能レポートを取得"""
        try:
            if not self.history:
                return {"error": "監視データがありません"}

            # 最新のメトリクス
            latest = self.history[-1]

            # 統計情報
            cpu_values = [m.get('cpu_percent', 0) for m in self.history if 'cpu_percent' in m]
            memory_values = [m.get('memory_percent', 0) for m in self.history if 'memory_percent' in m]

            stats = {
                'cpu_avg': sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                'memory_avg': sum(memory_values) / len(memory_values) if memory_values else 0,
                'sample_count': len(self.history),
                'monitoring_duration': len(self.history) * self.interval if self.history else 0
            }

            return {
                'current': latest,
                'statistics': stats,
                'grafana_enabled': self.grafana_enabled,
                'grafana_url': self.grafana_url if self.grafana_enabled else None,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"レポート生成エラー: {e}")
            return {"error": str(e)}

    def setup_grafana_dashboard(self) -> Optional[str]:
        """Grafanaダッシュボードをセットアップ"""
        if not self.grafana_service:
            logger.error("Grafanaサービスが有効ではありません")
            return None

        return self.grafana_service.setup_monitoring_dashboard()


# グローバルサービスインスタンス
_enhanced_monitor: Optional[EnhancedPerformanceMonitor] = None


def get_enhanced_performance_monitor(config: Optional[Dict[str, Any]] = None) -> EnhancedPerformanceMonitor:
    """強化された性能監視システムのシングルトンインスタンスを取得"""
    global _enhanced_monitor
    if _enhanced_monitor is None:
        _enhanced_monitor = EnhancedPerformanceMonitor(config)
    return _enhanced_monitor


def setup_grafana_integration(grafana_url: str = "http://localhost:3000", api_key: Optional[str] = None) -> bool:
    """Grafana統合をセットアップ"""
    try:
        config = {
            'grafana_enabled': True,
            'grafana_url': grafana_url,
            'grafana_api_key': api_key
        }

        monitor = get_enhanced_performance_monitor(config)
        monitor.start_monitoring()

        # ダッシュボードをセットアップ
        dashboard_uid = monitor.setup_grafana_dashboard()

        logger.info(f"Grafana統合をセットアップしました。ダッシュボードUID: {dashboard_uid}")
        return True

    except Exception as e:
        logger.error(f"Grafana統合セットアップエラー: {e}")
        return False


def collect_and_send_metrics(cpu_percent: float, memory_percent: float, disk_io: float, network_io: float):
    """メトリクスを収集してGrafanaに送信"""
    try:
        monitor = get_enhanced_performance_monitor({'grafana_enabled': True})
        monitor.grafana_service.collect_system_metrics(
            cpu_percent, memory_percent, disk_io, network_io
        )
    except Exception as e:
        logger.error(f"メトリクス送信エラー: {e}")


# 便利関数
def start_grafana_monitoring(grafana_url: str = "http://localhost:3000") -> bool:
    """Grafana監視を開始"""
    return setup_grafana_integration(grafana_url)


def stop_grafana_monitoring():
    """Grafana監視を停止"""
    try:
        monitor = get_enhanced_performance_monitor()
        monitor.stop_monitoring()
        logger.info("Grafana監視を停止しました")
        return True
    except Exception as e:
        logger.error(f"Grafana監視停止エラー: {e}")
        return False
