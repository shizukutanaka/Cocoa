#!/usr/bin/env python3
"""
Enhanced Prometheus Monitoring Integration
Prometheus/Grafana 2025ベストプラクティス統合

参考:
- Better Stack: "Python Monitoring with Prometheus"
- Medium: "Observability Practices with Python, Prometheus, and Grafana"
- TechCloudUp: "7 Essential Prometheus Monitoring Best Practices"
"""

try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary,
        CollectorRegistry, push_to_gateway, generate_latest,
        CONTENT_TYPE_LATEST,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = Gauge = Histogram = Summary = None
    CollectorRegistry = push_to_gateway = generate_latest = None
    CONTENT_TYPE_LATEST = None

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

from typing import Optional
from dataclasses import dataclass
from enum import Enum
import time
import logging

logger = logging.getLogger(__name__)


class Environment(Enum):
    """環境種別"""
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


@dataclass
class MetricConfig:
    """メトリクス設定"""
    scrape_interval: int = 15  # seconds
    push_gateway_url: Optional[str] = None
    job_name: str = "cocoa"
    enable_process_metrics: bool = True
    enable_system_metrics: bool = True


class EnhancedPrometheusMonitor:
    """
    強化されたPrometheusメトリクス収集システム

    ベストプラクティス:
    - 効率的なラベリング戦略 (env="prod" not environment_production="true")
    - 4つのコアメトリクスタイプ全対応
    - 適切なスクレイプ間隔設定
    - ヒストグラムバケット最適化
    """

    def __init__(
        self,
        config: Optional[MetricConfig] = None,
        environment: Environment = Environment.PROD
    ):
        """
        初期化

        Args:
            config: メトリクス設定
            environment: 実行環境
        """
        self.config = config or MetricConfig()
        self.environment = environment
        self.registry = CollectorRegistry() if CollectorRegistry is not None else None

        # メトリクス初期化
        self._init_counters()
        self._init_gauges()
        self._init_histograms()
        self._init_summaries()

        logger.info(
            f"Initialized Prometheus monitor for {environment.value} environment"
        )

    def _init_counters(self):
        """カウンターメトリクス初期化"""

        # 操作カウンター
        self.operations_total = Counter(
            'cocoa_operations_total',
            'Total number of operations',
            ['operation_type', 'status', 'env'],
            registry=self.registry
        )

        # エラーカウンター
        self.errors_total = Counter(
            'cocoa_errors_total',
            'Total number of errors',
            ['error_type', 'severity', 'env'],
            registry=self.registry
        )

        # リクエストカウンター
        self.requests_total = Counter(
            'cocoa_requests_total',
            'Total number of requests',
            ['method', 'endpoint', 'status_code', 'env'],
            registry=self.registry
        )

        # セキュリティイベントカウンター
        self.security_events_total = Counter(
            'cocoa_security_events_total',
            'Total number of security events',
            ['event_type', 'severity', 'env'],
            registry=self.registry
        )

    def _init_gauges(self):
        """ゲージメトリクス初期化"""

        # アクティブユーザー数
        self.active_users = Gauge(
            'cocoa_active_users',
            'Number of active users',
            ['env'],
            registry=self.registry
        )

        # CPU使用率
        self.cpu_usage_percent = Gauge(
            'cocoa_cpu_usage_percent',
            'CPU usage percentage',
            ['env'],
            registry=self.registry
        )

        # メモリ使用量
        self.memory_usage_bytes = Gauge(
            'cocoa_memory_usage_bytes',
            'Memory usage in bytes',
            ['env'],
            registry=self.registry
        )

        # メモリ使用率
        self.memory_usage_percent = Gauge(
            'cocoa_memory_usage_percent',
            'Memory usage percentage',
            ['env'],
            registry=self.registry
        )

        # ディスク使用量
        self.disk_usage_bytes = Gauge(
            'cocoa_disk_usage_bytes',
            'Disk usage in bytes',
            ['mount_point', 'env'],
            registry=self.registry
        )

        # ディスク使用率
        self.disk_usage_percent = Gauge(
            'cocoa_disk_usage_percent',
            'Disk usage percentage',
            ['mount_point', 'env'],
            registry=self.registry
        )

        # キャッシュヒット率
        self.cache_hit_rate = Gauge(
            'cocoa_cache_hit_rate',
            'Cache hit rate (0-1)',
            ['cache_name', 'env'],
            registry=self.registry
        )

        # データベース接続プール
        self.db_connections_active = Gauge(
            'cocoa_db_connections_active',
            'Active database connections',
            ['db_name', 'env'],
            registry=self.registry
        )

    def _init_histograms(self):
        """ヒストグラムメトリクス初期化"""

        # リクエスト処理時間（ベストプラクティス: 適切なバケット設定）
        self.request_duration_seconds = Histogram(
            'cocoa_request_duration_seconds',
            'Request duration in seconds',
            ['operation_type', 'env'],
            buckets=[
                .001, .0025, .005, .0075,  # 1-7.5ms
                .01, .025, .05, .075,       # 10-75ms
                .1, .25, .5, .75,           # 100-750ms
                1.0, 2.5, 5.0, 7.5,         # 1-7.5s
                10.0, 30.0, 60.0            # 10-60s
            ],
            registry=self.registry
        )

        # データベースクエリ時間
        self.db_query_duration_seconds = Histogram(
            'cocoa_db_query_duration_seconds',
            'Database query duration in seconds',
            ['query_type', 'env'],
            buckets=[.001, .005, .01, .025, .05, .1, .25, .5, 1.0, 2.5, 5.0],
            registry=self.registry
        )

        # ファイルサイズ
        self.file_size_bytes = Histogram(
            'cocoa_file_size_bytes',
            'File size in bytes',
            ['file_type', 'env'],
            buckets=[
                1024, 10240, 102400,        # 1KB, 10KB, 100KB
                1048576, 10485760,          # 1MB, 10MB
                104857600, 1073741824       # 100MB, 1GB
            ],
            registry=self.registry
        )

    def _init_summaries(self):
        """サマリーメトリクス初期化"""

        # 暗号化処理時間
        self.encryption_duration_seconds = Summary(
            'cocoa_encryption_duration_seconds',
            'Encryption operation duration',
            ['env'],
            registry=self.registry
        )

        # バックアップサイズ
        self.backup_size_bytes = Summary(
            'cocoa_backup_size_bytes',
            'Backup size in bytes',
            ['env'],
            registry=self.registry
        )

    # === メトリクス記録メソッド ===

    def record_operation(
        self,
        operation_type: str,
        status: str = "success"
    ):
        """操作を記録"""
        self.operations_total.labels(
            operation_type=operation_type,
            status=status,
            env=self.environment.value
        ).inc()

    def record_error(
        self,
        error_type: str,
        severity: str = "error"
    ):
        """エラーを記録"""
        self.errors_total.labels(
            error_type=error_type,
            severity=severity,
            env=self.environment.value
        ).inc()

    def record_request(
        self,
        method: str,
        endpoint: str,
        status_code: int
    ):
        """HTTPリクエストを記録"""
        self.requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code),
            env=self.environment.value
        ).inc()

    def record_security_event(
        self,
        event_type: str,
        severity: str = "warning"
    ):
        """セキュリティイベントを記録"""
        self.security_events_total.labels(
            event_type=event_type,
            severity=severity,
            env=self.environment.value
        ).inc()

    def update_active_users(self, count: int):
        """アクティブユーザー数を更新"""
        self.active_users.labels(env=self.environment.value).set(count)

    def update_system_metrics(self):
        """システムメトリクスを更新"""
        env = self.environment.value

        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        self.cpu_usage_percent.labels(env=env).set(cpu_percent)

        # メモリ
        mem = psutil.virtual_memory()
        self.memory_usage_bytes.labels(env=env).set(mem.used)
        self.memory_usage_percent.labels(env=env).set(mem.percent)

        # ディスク
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                self.disk_usage_bytes.labels(
                    mount_point=partition.mountpoint,
                    env=env
                ).set(usage.used)
                self.disk_usage_percent.labels(
                    mount_point=partition.mountpoint,
                    env=env
                ).set(usage.percent)
            except (PermissionError, FileNotFoundError):
                continue

    def observe_request_duration(
        self,
        operation_type: str,
        duration_seconds: float
    ):
        """リクエスト処理時間を記録"""
        self.request_duration_seconds.labels(
            operation_type=operation_type,
            env=self.environment.value
        ).observe(duration_seconds)

    def observe_db_query_duration(
        self,
        query_type: str,
        duration_seconds: float
    ):
        """データベースクエリ時間を記録"""
        self.db_query_duration_seconds.labels(
            query_type=query_type,
            env=self.environment.value
        ).observe(duration_seconds)

    # === デコレーター ===

    def measure_duration(self, operation_type: str):
        """処理時間測定デコレーター"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    self.record_operation(operation_type, 'success')
                    return result
                except Exception as e:
                    self.record_operation(operation_type, 'failure')
                    self.record_error(type(e).__name__, 'error')
                    raise
                finally:
                    duration = time.time() - start
                    self.observe_request_duration(operation_type, duration)
            return wrapper
        return decorator

    def measure_encryption(self):
        """暗号化処理時間測定デコレーター"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start = time.time()
                try:
                    return func(*args, **kwargs)
                finally:
                    duration = time.time() - start
                    self.encryption_duration_seconds.labels(
                        env=self.environment.value
                    ).observe(duration)
            return wrapper
        return decorator

    # === エクスポート ===

    def push_metrics(self, gateway_url: Optional[str] = None):
        """メトリクスをPushgatewayへ送信"""
        url = gateway_url or self.config.push_gateway_url

        if not url:
            logger.warning("Push gateway URL not configured")
            return

        try:
            push_to_gateway(
                url,
                job=self.config.job_name,
                registry=self.registry
            )
            logger.debug(f"Pushed metrics to {url}")
        except Exception as e:
            logger.error(f"Failed to push metrics: {e}")

    def expose_metrics(self) -> bytes:
        """メトリクスをテキスト形式でエクスポート"""
        return generate_latest(self.registry)

    def get_content_type(self) -> str:
        """Content-Typeヘッダーを取得"""
        return CONTENT_TYPE_LATEST


class MetricsServer:
    """HTTPメトリクスサーバー（Prometheus scrape用）"""

    def __init__(
        self,
        monitor: EnhancedPrometheusMonitor,
        port: int = 9090
    ):
        self.monitor = monitor
        self.port = port

    def start(self):
        """メトリクスサーバーを起動"""
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class MetricsHandler(BaseHTTPRequestHandler):
            def do_GET(self_handler):
                if self_handler.path == '/metrics':
                    # メトリクスを返す
                    metrics = self.monitor.expose_metrics()

                    self_handler.send_response(200)
                    self_handler.send_header(
                        'Content-Type',
                        self.monitor.get_content_type()
                    )
                    self_handler.end_headers()
                    self_handler.wfile.write(metrics)
                else:
                    self_handler.send_response(404)
                    self_handler.end_headers()

            def log_message(self_handler, format, *args):
                # ログを抑制
                pass

        server = HTTPServer(('0.0.0.0', self.port), MetricsHandler)
        logger.info(f"Metrics server started on http://0.0.0.0:{self.port}/metrics")

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Metrics server stopped")
            server.shutdown()


def example_usage():
    """使用例"""
    # モニター初期化
    monitor = EnhancedPrometheusMonitor(
        environment=Environment.PROD
    )

    # 操作記録
    monitor.record_operation('avatar_load', 'success')
    monitor.record_operation('preset_save', 'success')

    # エラー記録
    monitor.record_error('ValidationError', 'warning')

    # リクエスト記録
    monitor.record_request('POST', '/api/avatars', 201)

    # システムメトリクス更新
    monitor.update_system_metrics()

    # アクティブユーザー更新
    monitor.update_active_users(15)

    # デコレーター使用例
    @monitor.measure_duration('data_processing')
    def process_data():
        time.sleep(0.1)
        return "processed"

    process_data()

    # メトリクスをテキスト形式で出力
    metrics_text = monitor.expose_metrics().decode('utf-8')
    print(metrics_text[:500])  # 最初の500文字


def main():
    """テスト実行"""
    print("Enhanced Prometheus Monitoring System\n")
    print("=" * 70)

    # 使用例実行
    example_usage()

    print("\n" + "=" * 70)
    print("\nMetrics server can be started with:")
    print("  monitor = EnhancedPrometheusMonitor()")
    print("  server = MetricsServer(monitor, port=9090)")
    print("  server.start()")
    print("\nThen Prometheus can scrape from: http://localhost:9090/metrics")


if __name__ == "__main__":
    main()
