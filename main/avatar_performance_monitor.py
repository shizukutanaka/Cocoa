# main/avatar_performance_monitor.py
"""
Avatar Performance Monitor Module for Cocoa
アバター生成・動画作成パフォーマンスのリアルタイム監視
"""

import asyncio
import logging
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque
import statistics

from .integrated_security import get_security_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class AvatarPerformanceMetrics:
    """アバターパフォーマンスメトリクス"""
    operation_type: str  # 'avatar_generation', 'video_creation', 'voice_cloning', etc.
    user_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    success: bool = False
    error_message: Optional[str] = None
    resource_usage: Dict[str, Any] = None
    quality_metrics: Dict[str, Any] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.resource_usage is None:
            self.resource_usage = {}
        if self.quality_metrics is None:
            self.quality_metrics = {}
        if self.metadata is None:
            self.metadata = {}

@dataclass
class PerformanceStats:
    """パフォーマンス統計"""
    operation_type: str
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    average_duration: float = 0.0
    min_duration: float = 0.0
    max_duration: float = 0.0
    success_rate: float = 0.0
    last_updated: datetime = None

    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()

@dataclass
class PerformanceAlert:
    """パフォーマンスアラート"""
    alert_id: str
    alert_type: str  # 'slow_operation', 'high_failure_rate', 'resource_overuse'
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    operation_type: str
    threshold_value: Union[int, float]
    current_value: Union[int, float]
    timestamp: datetime
    resolved: bool = False

class AvatarPerformanceMonitor:
    """
    アバターパフォーマンス監視システム
    動画生成時間・成功率・リソース使用状況のリアルタイム追跡
    """

    def __init__(self):
        self.security_manager = get_security_manager()

        # データベース
        self.db_path = Path("data/avatar_performance.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # キャッシュ
        self.stats_cache: Dict[str, PerformanceStats] = {}
        self.active_operations: Dict[str, AvatarPerformanceMetrics] = {}

        # 監視設定
        self.alert_thresholds = {
            "max_duration": {
                "avatar_generation": 30.0,  # 30秒
                "video_creation": 300.0,    # 5分
                "voice_cloning": 60.0       # 1分
            },
            "min_success_rate": 0.8,  # 80%
            "max_failure_rate": 0.2   # 20%
        }

        # アラートキュー
        self.alert_queue: deque = deque(maxlen=100)

        # 監視スレッド
        self.monitoring_thread = None
        self.is_monitoring = False

        logger.info("Avatar Performance Monitor initialized")

    async def initialize(self):
        """初期化"""
        # データベース初期化
        await self._init_database()

        # 監視スレッド開始
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()

        logger.info("Avatar Performance Monitor initialized successfully")

    async def _init_database(self):
        """データベース初期化"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # パフォーマンスメトリクステーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS avatar_performance (
                    operation_id TEXT PRIMARY KEY,
                    operation_type TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration REAL,
                    success INTEGER DEFAULT 0,
                    error_message TEXT,
                    resource_usage TEXT,
                    quality_metrics TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # パフォーマンス統計テーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_stats (
                    operation_type TEXT PRIMARY KEY,
                    total_operations INTEGER DEFAULT 0,
                    successful_operations INTEGER DEFAULT 0,
                    failed_operations INTEGER DEFAULT 0,
                    average_duration REAL DEFAULT 0.0,
                    min_duration REAL DEFAULT 0.0,
                    max_duration REAL DEFAULT 0.0,
                    success_rate REAL DEFAULT 0.0,
                    last_updated TEXT
                )
            ''')

            # パフォーマンスアラートテーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_alerts (
                    alert_id TEXT PRIMARY KEY,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    threshold_value REAL NOT NULL,
                    current_value REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    resolved INTEGER DEFAULT 0
                )
            ''')

            # インデックス作成
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_performance_operation_type ON avatar_performance(operation_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_performance_user_id ON avatar_performance(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_performance_start_time ON avatar_performance(start_time)')

            conn.commit()

    def _monitoring_loop(self):
        """監視ループ"""
        self.is_monitoring = True

        while self.is_monitoring:
            try:
                # アクティブな操作のタイムアウトチェック
                self._check_operation_timeouts()

                # パフォーマンス統計更新
                asyncio.run(self._update_performance_stats())

                # アラートチェック
                asyncio.run(self._check_alert_conditions())

                # リソースクリーンアップ
                self._cleanup_old_data()

            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")

            time.sleep(10)  # 10秒間隔

    def _check_operation_timeouts(self):
        """アクティブな操作のタイムアウトをチェック"""
        current_time = datetime.now()
        timeout_operations = []

        for operation_id, metrics in self.active_operations.items():
            elapsed = (current_time - metrics.start_time).total_seconds()

            max_duration = self.alert_thresholds["max_duration"].get(metrics.operation_type, 300.0)

            if elapsed > max_duration * 2:  # 最大時間の2倍でタイムアウト
                metrics.success = False
                metrics.error_message = f"Operation timeout after {elapsed:.1f} seconds"
                metrics.end_time = current_time
                metrics.duration = elapsed

                timeout_operations.append(operation_id)

                # アラート生成
                alert = PerformanceAlert(
                    alert_id=f"alert_{operation_id}_{int(time.time())}",
                    alert_type="operation_timeout",
                    severity="high",
                    message=f"Operation {operation_id} timed out after {elapsed:.1f} seconds",
                    operation_type=metrics.operation_type,
                    threshold_value=max_duration * 2,
                    current_value=elapsed,
                    timestamp=current_time
                )
                self.alert_queue.append(alert)

        # タイムアウトした操作を完了としてマーク
        for operation_id in timeout_operations:
            completed_metrics = self.active_operations.pop(operation_id)
            asyncio.run(self._save_performance_metrics(completed_metrics))

    async def _update_performance_stats(self):
        """パフォーマンス統計を更新"""
        # 最近24時間のデータを集計
        cutoff_time = datetime.now() - timedelta(hours=24)

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # 操作タイプごとに統計を計算
            cursor.execute('''
                SELECT operation_type, COUNT(*), SUM(success), SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END),
                       AVG(duration), MIN(duration), MAX(duration)
                FROM avatar_performance
                WHERE start_time > ?
                GROUP BY operation_type
            ''', (cutoff_time.isoformat(),))

            rows = cursor.fetchall()

            for row in rows:
                operation_type, total, successful, failed, avg_duration, min_duration, max_duration = row

                success_rate = successful / total if total > 0 else 0.0

                stats = PerformanceStats(
                    operation_type=operation_type,
                    total_operations=total,
                    successful_operations=successful,
                    failed_operations=failed,
                    average_duration=avg_duration or 0.0,
                    min_duration=min_duration or 0.0,
                    max_duration=max_duration or 0.0,
                    success_rate=success_rate,
                    last_updated=datetime.now()
                )

                self.stats_cache[operation_type] = stats

                # データベース更新
                cursor.execute('''
                    INSERT OR REPLACE INTO performance_stats
                    (operation_type, total_operations, successful_operations, failed_operations,
                     average_duration, min_duration, max_duration, success_rate, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    operation_type, total, successful, failed,
                    avg_duration, min_duration, max_duration, success_rate,
                    datetime.now().isoformat()
                ))

            conn.commit()

    async def _check_alert_conditions(self):
        """アラート条件をチェック"""
        current_time = datetime.now()

        for operation_type, stats in self.stats_cache.items():
            # 成功率チェック
            if stats.success_rate < self.alert_thresholds["min_success_rate"]:
                alert = PerformanceAlert(
                    alert_id=f"alert_success_rate_{operation_type}_{int(time.time())}",
                    alert_type="low_success_rate",
                    severity="medium",
                    message=f"Low success rate for {operation_type}: {stats.success_rate:.2%}",
                    operation_type=operation_type,
                    threshold_value=self.alert_thresholds["min_success_rate"],
                    current_value=stats.success_rate,
                    timestamp=current_time
                )
                self.alert_queue.append(alert)

            # 平均時間チェック
            max_duration = self.alert_thresholds["max_duration"].get(operation_type, 300.0)
            if stats.average_duration > max_duration:
                alert = PerformanceAlert(
                    alert_id=f"alert_avg_duration_{operation_type}_{int(time.time())}",
                    alert_type="slow_operations",
                    severity="medium",
                    message=f"Slow average duration for {operation_type}: {stats.average_duration:.1f}s",
                    operation_type=operation_type,
                    threshold_value=max_duration,
                    current_value=stats.average_duration,
                    timestamp=current_time
                )
                self.alert_queue.append(alert)

        # アラートをデータベースに保存
        await self._save_alerts()

    async def _save_alerts(self):
        """アラートをデータベースに保存"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            while self.alert_queue:
                alert = self.alert_queue.popleft()

                cursor.execute('''
                    INSERT INTO performance_alerts
                    (alert_id, alert_type, severity, message, operation_type,
                     threshold_value, current_value, timestamp, resolved)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    alert.alert_id, alert.alert_type, alert.severity, alert.message,
                    alert.operation_type, alert.threshold_value, alert.current_value,
                    alert.timestamp.isoformat(), alert.resolved
                ))

            conn.commit()

    def _cleanup_old_data(self):
        """古いデータをクリーンアップ"""
        cutoff_time = datetime.now() - timedelta(days=30)  # 30日以上前のデータ

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # 古いパフォーマンスデータを削除
            cursor.execute('DELETE FROM avatar_performance WHERE start_time < ?',
                         (cutoff_time.isoformat(),))

            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old performance records")

            conn.commit()

    async def start_operation_tracking(self, operation_type: str, user_id: str,
                                     operation_id: Optional[str] = None,
                                     metadata: Optional[Dict] = None) -> str:
        """
        操作の追跡を開始

        Args:
            operation_type: 操作タイプ
            user_id: ユーザーID
            operation_id: 操作ID（指定なしの場合は自動生成）
            metadata: メタデータ

        Returns:
            操作ID
        """
        if not operation_id:
            operation_id = f"{operation_type}_{user_id}_{int(time.time() * 1000)}"

        metrics = AvatarPerformanceMetrics(
            operation_type=operation_type,
            user_id=user_id,
            start_time=datetime.now(),
            metadata=metadata or {}
        )

        self.active_operations[operation_id] = metrics

        # セキュリティログ
        await self.security_manager.log_security_event(
            event_type="avatar_performance_tracking_start",
            user_id=user_id,
            details={
                "operation_id": operation_id,
                "operation_type": operation_type
            },
            ip_address="system"
        )

        return operation_id

    async def end_operation_tracking(self, operation_id: str, success: bool = True,
                                   error_message: Optional[str] = None,
                                   resource_usage: Optional[Dict] = None,
                                   quality_metrics: Optional[Dict] = None) -> bool:
        """
        操作の追跡を終了

        Args:
            operation_id: 操作ID
            success: 成功かどうか
            error_message: エラーメッセージ
            resource_usage: リソース使用状況
            quality_metrics: 品質メトリクス

        Returns:
            保存成功かどうか
        """
        if operation_id not in self.active_operations:
            logger.warning(f"Operation {operation_id} not found in active operations")
            return False

        metrics = self.active_operations.pop(operation_id)
        metrics.end_time = datetime.now()
        metrics.duration = (metrics.end_time - metrics.start_time).total_seconds()
        metrics.success = success
        metrics.error_message = error_message

        if resource_usage:
            metrics.resource_usage.update(resource_usage)

        if quality_metrics:
            metrics.quality_metrics.update(quality_metrics)

        # 保存
        await self._save_performance_metrics(metrics)

        return True

    async def _save_performance_metrics(self, metrics: AvatarPerformanceMetrics):
        """パフォーマンスメトリクスを保存"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            operation_id = f"{metrics.operation_type}_{metrics.user_id}_{int(metrics.start_time.timestamp())}"

            cursor.execute('''
                INSERT INTO avatar_performance
                (operation_id, operation_type, user_id, start_time, end_time, duration,
                 success, error_message, resource_usage, quality_metrics, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                operation_id,
                metrics.operation_type,
                metrics.user_id,
                metrics.start_time.isoformat(),
                metrics.end_time.isoformat() if metrics.end_time else None,
                metrics.duration,
                metrics.success,
                metrics.error_message,
                json.dumps(metrics.resource_usage, ensure_ascii=False),
                json.dumps(metrics.quality_metrics, ensure_ascii=False),
                json.dumps(metrics.metadata, ensure_ascii=False)
            ))

            conn.commit()

    async def get_performance_stats(self, operation_type: Optional[str] = None,
                                  hours: int = 24) -> Dict[str, Any]:
        """
        パフォーマンス統計を取得

        Args:
            operation_type: 操作タイプ（指定なしの場合は全タイプ）
            hours: 集計期間（時間）

        Returns:
            パフォーマンス統計
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            if operation_type:
                # 特定の操作タイプ
                cursor.execute('''
                    SELECT operation_type, COUNT(*), SUM(success), SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END),
                           AVG(duration), MIN(duration), MAX(duration)
                    FROM avatar_performance
                    WHERE operation_type = ? AND start_time > ?
                ''', (operation_type, cutoff_time.isoformat()))

                row = cursor.fetchone()
                if row:
                    op_type, total, successful, failed, avg_duration, min_duration, max_duration = row
                    success_rate = successful / total if total > 0 else 0.0

                    return {
                        operation_type: {
                            "total_operations": total,
                            "successful_operations": successful,
                            "failed_operations": failed,
                            "average_duration": avg_duration or 0.0,
                            "min_duration": min_duration or 0.0,
                            "max_duration": max_duration or 0.0,
                            "success_rate": success_rate,
                            "period_hours": hours
                        }
                    }
                else:
                    return {}
            else:
                # 全操作タイプ
                cursor.execute('''
                    SELECT operation_type, COUNT(*), SUM(success), SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END),
                           AVG(duration), MIN(duration), MAX(duration)
                    FROM avatar_performance
                    WHERE start_time > ?
                    GROUP BY operation_type
                ''', (cutoff_time.isoformat(),))

                results = {}
                for row in cursor.fetchall():
                    op_type, total, successful, failed, avg_duration, min_duration, max_duration = row
                    success_rate = successful / total if total > 0 else 0.0

                    results[op_type] = {
                        "total_operations": total,
                        "successful_operations": successful,
                        "failed_operations": failed,
                        "average_duration": avg_duration or 0.0,
                        "min_duration": min_duration or 0.0,
                        "max_duration": max_duration or 0.0,
                        "success_rate": success_rate,
                        "period_hours": hours
                    }

                return results

    async def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """最近のアラートを取得"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT alert_id, alert_type, severity, message, operation_type,
                       threshold_value, current_value, timestamp, resolved
                FROM performance_alerts
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))

            alerts = []
            for row in cursor.fetchall():
                alerts.append({
                    "alert_id": row[0],
                    "alert_type": row[1],
                    "severity": row[2],
                    "message": row[3],
                    "operation_type": row[4],
                    "threshold_value": row[5],
                    "current_value": row[6],
                    "timestamp": row[7],
                    "resolved": bool(row[8])
                })

            return alerts

    async def get_operation_history(self, operation_type: Optional[str] = None,
                                  user_id: Optional[str] = None,
                                  limit: int = 100) -> List[Dict[str, Any]]:
        """操作履歴を取得"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            query = '''
                SELECT operation_id, operation_type, user_id, start_time, end_time,
                       duration, success, error_message
                FROM avatar_performance
                WHERE 1=1
            '''
            params = []

            if operation_type:
                query += ' AND operation_type = ?'
                params.append(operation_type)

            if user_id:
                query += ' AND user_id = ?'
                params.append(user_id)

            query += ' ORDER BY start_time DESC LIMIT ?'
            params.append(limit)

            cursor.execute(query, params)

            operations = []
            for row in cursor.fetchall():
                operations.append({
                    "operation_id": row[0],
                    "operation_type": row[1],
                    "user_id": row[2],
                    "start_time": row[3],
                    "end_time": row[4],
                    "duration": row[5],
                    "success": bool(row[6]),
                    "error_message": row[7]
                })

            return operations

    async def generate_performance_report(self, operation_type: Optional[str] = None,
                                        hours: int = 24) -> Dict[str, Any]:
        """
        パフォーマンスレポートを生成

        Args:
            operation_type: 操作タイプ
            hours: レポート期間（時間）

        Returns:
            パフォーマンスレポート
        """
        stats = await self.get_performance_stats(operation_type, hours)
        alerts = await self.get_recent_alerts(20)

        report = {
            "generated_at": datetime.now().isoformat(),
            "period_hours": hours,
            "operation_type": operation_type or "all",
            "statistics": stats,
            "recent_alerts": alerts,
            "summary": {}
        }

        # サマリー生成
        if stats:
            if operation_type:
                op_stats = stats.get(operation_type, {})
                report["summary"] = {
                    "total_operations": op_stats.get("total_operations", 0),
                    "success_rate": op_stats.get("success_rate", 0.0),
                    "average_duration": op_stats.get("average_duration", 0.0),
                    "performance_health": self._calculate_performance_health(op_stats)
                }
            else:
                # 全操作の集計
                total_ops = sum(s.get("total_operations", 0) for s in stats.values())
                avg_success_rate = statistics.mean([s.get("success_rate", 0.0) for s in stats.values()]) if stats else 0.0

                report["summary"] = {
                    "total_operations": total_ops,
                    "operation_types": len(stats),
                    "average_success_rate": avg_success_rate,
                    "performance_health": "good" if avg_success_rate > 0.8 else "needs_attention"
                }

        return report

    def _calculate_performance_health(self, stats: Dict[str, Any]) -> str:
        """パフォーマンス健全性を計算"""
        success_rate = stats.get("success_rate", 0.0)
        avg_duration = stats.get("average_duration", 0.0)
        operation_type = stats.get("operation_type", "")

        max_duration = self.alert_thresholds["max_duration"].get(operation_type, 300.0)

        if success_rate >= 0.95 and avg_duration <= max_duration * 0.5:
            return "excellent"
        elif success_rate >= 0.85 and avg_duration <= max_duration:
            return "good"
        elif success_rate >= 0.7:
            return "fair"
        else:
            return "needs_attention"

    async def export_performance_data(self, operation_type: Optional[str] = None,
                                    hours: int = 24, format: str = "json") -> Optional[str]:
        """
        パフォーマンスデータをエクスポート

        Args:
            operation_type: 操作タイプ
            hours: エクスポート期間（時間）
            format: エクスポート形式

        Returns:
            エクスポートファイルパス
        """
        # データ収集
        stats = await self.get_performance_stats(operation_type, hours)
        alerts = await self.get_recent_alerts(50)
        operations = await self.get_operation_history(operation_type, limit=1000)

        export_data = {
            "exported_at": datetime.now().isoformat(),
            "period_hours": hours,
            "operation_type": operation_type or "all",
            "statistics": stats,
            "alerts": alerts,
            "operations": operations
        }

        # エクスポートディレクトリ
        export_dir = Path("data/performance_exports")
        export_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"performance_export_{operation_type or 'all'}_{timestamp}.{format}"
        export_path = export_dir / filename

        if format == "json":
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
        elif format == "csv":
            await self._export_to_csv(export_data, export_path)

        return str(export_path)

    async def _export_to_csv(self, data: Dict, export_path: Path):
        """CSV形式でエクスポート"""
        import csv

        with open(export_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # 統計情報
            writer.writerow(['Section', 'Key', 'Value'])
            for section, stats in data.get('statistics', {}).items():
                for key, value in stats.items():
                    writer.writerow([section, key, value])

            writer.writerow([])
            writer.writerow(['Operations'])
            writer.writerow(['Operation ID', 'Type', 'User ID', 'Start Time', 'Duration', 'Success'])

            for op in data.get('operations', []):
                writer.writerow([
                    op['operation_id'],
                    op['operation_type'],
                    op['user_id'],
                    op['start_time'],
                    op['duration'],
                    op['success']
                ])

    async def close(self):
        """クリーンアップ"""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)

# グローバルインスタンス管理
_avatar_performance_monitor = None

async def get_avatar_performance_monitor() -> AvatarPerformanceMonitor:
    """アバターパフォーマンス監視システムのインスタンスを取得"""
    global _avatar_performance_monitor

    if _avatar_performance_monitor is None:
        _avatar_performance_monitor = AvatarPerformanceMonitor()
        await _avatar_performance_monitor.initialize()

    return _avatar_performance_monitor
