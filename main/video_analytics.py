# main/video_analytics.py
"""
Video Analytics Module for Cocoa
アバター動画のエンゲージメント・パフォーマンス計測
"""

import asyncio
import json
import logging
import queue
import sqlite3
import statistics
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from integrated_security import get_security_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class VideoEvent:
    """動画イベント"""
    event_id: str
    video_id: str
    user_id: str
    event_type: str  # 'play', 'pause', 'complete', 'seek', 'interaction'
    timestamp: datetime
    position: float = 0.0  # 動画内の位置（秒）
    metadata: Dict[str, Any] = None
    session_id: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class VideoMetrics:
    """動画メトリクス"""
    video_id: str
    total_views: int = 0
    unique_viewers: int = 0
    completion_rate: float = 0.0
    average_watch_time: float = 0.0
    drop_off_points: List[Tuple[float, int]] = None  # (position, drop_off_count)
    engagement_score: float = 0.0
    last_updated: datetime = None

    def __post_init__(self):
        if self.drop_off_points is None:
            self.drop_off_points = []
        if self.last_updated is None:
            self.last_updated = datetime.now(timezone.utc)

@dataclass
class AnalyticsReport:
    """アナリティクスレポート"""
    report_id: str
    video_id: str
    report_type: str  # 'daily', 'weekly', 'monthly', 'custom'
    start_date: datetime
    end_date: datetime
    metrics: Dict[str, Any]
    insights: List[str]
    generated_at: datetime = None

    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.now(timezone.utc)

class VideoAnalyticsService:
    """
    動画アナリティクスサービス
    アバター動画のパフォーマンス計測とレポート生成
    """

    def __init__(self):
        self.security_manager = get_security_manager()

        # データベース
        self.db_path = Path("data/analytics.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # キャッシュ
        self.metrics_cache: Dict[str, VideoMetrics] = {}
        self.cache_lock = threading.Lock()

        # イベントキュー
        self.event_queue = queue.Queue()
        self.processing_thread = None
        self.is_processing = False

        # 設定
        self.cache_ttl = 300  # 5分
        self.batch_size = 100  # バッチ処理サイズ

        logger.info("Video Analytics Service initialized")

    async def initialize(self):
        """初期化"""
        # データベース初期化
        await self._init_database()

        # 処理スレッド開始
        self.processing_thread = threading.Thread(target=self._process_events_loop, daemon=True)
        self.processing_thread.start()

        logger.info("Video Analytics Service initialized successfully")

    async def _init_database(self):
        """データベース初期化"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # 動画イベントテーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_events (
                    event_id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    position REAL DEFAULT 0.0,
                    metadata TEXT,
                    session_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 動画メトリクステーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_metrics (
                    video_id TEXT PRIMARY KEY,
                    total_views INTEGER DEFAULT 0,
                    unique_viewers INTEGER DEFAULT 0,
                    completion_rate REAL DEFAULT 0.0,
                    average_watch_time REAL DEFAULT 0.0,
                    drop_off_points TEXT,
                    engagement_score REAL DEFAULT 0.0,
                    last_updated TEXT
                )
            ''')

            # アナリティクスレポートテーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analytics_reports (
                    report_id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL,
                    report_type TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    metrics TEXT NOT NULL,
                    insights TEXT NOT NULL,
                    generated_at TEXT
                )
            ''')

            # インデックス作成
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_events_video_id ON video_events(video_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_events_user_id ON video_events(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_events_timestamp ON video_events(timestamp)')

            conn.commit()

    def _process_events_loop(self):
        """イベント処理ループ"""
        self.is_processing = True

        while self.is_processing:
            try:
                # イベントをバッチ処理
                events = []
                try:
                    while len(events) < self.batch_size:
                        event = self.event_queue.get_nowait()
                        events.append(event)
                except queue.Empty:
                    pass

                if events:
                    asyncio.run(self._process_event_batch(events))

                # 定期的なメトリクス更新
                asyncio.run(self._update_metrics_cache())

            except Exception as e:
                logger.error(f"Event processing error: {e}")

            # 処理間隔
            import time
            time.sleep(1)

    async def _process_event_batch(self, events: List[VideoEvent]):
        """イベントバッチを処理"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            for event in events:
                try:
                    # イベント保存
                    cursor.execute('''
                        INSERT INTO video_events
                        (event_id, video_id, user_id, event_type, timestamp, position, metadata, session_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        event.event_id,
                        event.video_id,
                        event.user_id,
                        event.event_type,
                        event.timestamp.isoformat(),
                        event.position,
                        json.dumps(event.metadata, ensure_ascii=False),
                        event.session_id
                    ))

                    # リアルタイムメトリクス更新
                    await self._update_realtime_metrics(event)

                except Exception as e:
                    logger.error(f"Failed to process event {event.event_id}: {e}")

            conn.commit()

    async def _update_realtime_metrics(self, event: VideoEvent):
        """リアルタイムメトリクス更新"""
        with self.cache_lock:
            if event.video_id not in self.metrics_cache:
                self.metrics_cache[event.video_id] = await self._load_video_metrics(event.video_id)

            metrics = self.metrics_cache[event.video_id]

            # イベントタイプに応じたメトリクス更新
            if event.event_type == 'play':
                metrics.total_views += 1
            elif event.event_type == 'complete':
                # 完了率計算は後でバッチ処理
                pass
            elif event.event_type == 'pause' or event.event_type == 'seek':
                # ドロップオフポイント更新
                self._update_drop_off_points(metrics, event.position)

            metrics.last_updated = datetime.now(timezone.utc)

    def _update_drop_off_points(self, metrics: VideoMetrics, position: float):
        """ドロップオフポイントを更新"""
        # 位置を丸めてグループ化
        rounded_pos = round(position, 1)  # 0.1秒単位

        # 既存のポイントを探す
        found = False
        for i, (pos, count) in enumerate(metrics.drop_off_points):
            if abs(pos - rounded_pos) < 0.1:
                metrics.drop_off_points[i] = (pos, count + 1)
                found = True
                break

        if not found:
            metrics.drop_off_points.append((rounded_pos, 1))

        # 上位10件のみ保持
        metrics.drop_off_points.sort(key=lambda x: x[1], reverse=True)
        metrics.drop_off_points = metrics.drop_off_points[:10]

    async def track_event(self, event: VideoEvent):
        """
        動画イベントを追跡

        Args:
            event: 追跡するイベント
        """
        # イベントをキューに追加
        self.event_queue.put(event)

        # セキュリティログ
        await self.security_manager.log_security_event(
            event_type="video_analytics_event",
            user_id=event.user_id,
            details={
                "video_id": event.video_id,
                "event_type": event.event_type,
                "position": event.position
            },
            ip_address="system"
        )

    async def get_video_metrics(self, video_id: str, force_refresh: bool = False) -> VideoMetrics:
        """
        動画メトリクスを取得

        Args:
            video_id: 動画ID
            force_refresh: キャッシュを無視して強制更新

        Returns:
            動画メトリクス
        """
        # キャッシュチェック
        if not force_refresh:
            with self.cache_lock:
                cached = self.metrics_cache.get(video_id)
                if cached and (datetime.now(timezone.utc) - cached.last_updated).seconds < self.cache_ttl:
                    return cached

        # データベースから読み込み
        metrics = await self._load_video_metrics(video_id)

        # リアルタイム計算
        await self._calculate_realtime_metrics(metrics)

        # キャッシュ更新
        with self.cache_lock:
            self.metrics_cache[video_id] = metrics

        return metrics

    async def _load_video_metrics(self, video_id: str) -> VideoMetrics:
        """データベースから動画メトリクスを読み込み"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM video_metrics WHERE video_id = ?', (video_id,))
            row = cursor.fetchone()

            if row:
                # JSONデシリアライズ
                drop_off_points = json.loads(row[5]) if row[5] else []

                return VideoMetrics(
                    video_id=row[0],
                    total_views=row[1],
                    unique_viewers=row[2],
                    completion_rate=row[3],
                    average_watch_time=row[4],
                    drop_off_points=drop_off_points,
                    engagement_score=row[6],
                    last_updated=datetime.fromisoformat(row[7])
                )
            # 新規作成
            return VideoMetrics(video_id=video_id)

    async def _calculate_realtime_metrics(self, metrics: VideoMetrics):
        """リアルタイムメトリクスを計算"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # 総視聴数
            cursor.execute('''
                SELECT COUNT(*) FROM video_events
                WHERE video_id = ? AND event_type = 'play'
            ''', (metrics.video_id,))
            metrics.total_views = cursor.fetchone()[0]

            # ユニーク視聴者数
            cursor.execute('''
                SELECT COUNT(DISTINCT user_id) FROM video_events
                WHERE video_id = ? AND event_type = 'play'
            ''', (metrics.video_id,))
            metrics.unique_viewers = cursor.fetchone()[0]

            # 完了率と平均視聴時間
            cursor.execute('''
                SELECT event_type, position
                FROM video_events
                WHERE video_id = ?
                ORDER BY timestamp
            ''', (metrics.video_id,))

            play_events = []
            complete_events = []
            watch_times = []

            rows = cursor.fetchall()
            for row in rows:
                if row[0] == 'play':
                    play_events.append(row[1])
                elif row[0] == 'complete':
                    complete_events.append(row[1])
                elif row[0] == 'pause':
                    watch_times.append(row[1])

            if play_events:
                metrics.completion_rate = len(complete_events) / len(play_events)

            if watch_times:
                metrics.average_watch_time = statistics.mean(watch_times)

            # エンゲージメントスコア計算
            metrics.engagement_score = self._calculate_engagement_score(metrics)

            # データベース更新
            cursor.execute('''
                INSERT OR REPLACE INTO video_metrics
                (video_id, total_views, unique_viewers, completion_rate,
                 average_watch_time, drop_off_points, engagement_score, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                metrics.video_id,
                metrics.total_views,
                metrics.unique_viewers,
                metrics.completion_rate,
                metrics.average_watch_time,
                json.dumps(metrics.drop_off_points, ensure_ascii=False),
                metrics.engagement_score,
                metrics.last_updated.isoformat()
            ))

            conn.commit()

    def _calculate_engagement_score(self, metrics: VideoMetrics) -> float:
        """エンゲージメントスコアを計算"""
        score = 0.0

        # 完了率によるスコア（40%）
        score += metrics.completion_rate * 0.4

        # 平均視聴時間によるスコア（30%）
        # 仮定: 理想的な視聴時間は60秒
        if metrics.average_watch_time > 0:
            time_score = min(metrics.average_watch_time / 60.0, 1.0)
            score += time_score * 0.3

        # ユニーク視聴者率によるスコア（30%）
        if metrics.total_views > 0:
            unique_ratio = metrics.unique_viewers / metrics.total_views
            score += unique_ratio * 0.3

        return min(score, 1.0)  # 最大1.0

    async def generate_report(self, video_id: str, report_type: str = 'weekly',
                            start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None) -> AnalyticsReport:
        """
        アナリティクスレポートを生成

        Args:
            video_id: 動画ID
            report_type: レポートタイプ
            start_date: 開始日（指定なしの場合は自動設定）
            end_date: 終了日（指定なしの場合は自動設定）

        Returns:
            アナリティクスレポート
        """
        # 日付範囲設定
        if not start_date or not end_date:
            end_date = datetime.now(timezone.utc)
            if report_type == 'daily':
                start_date = end_date - timedelta(days=1)
            elif report_type == 'weekly':
                start_date = end_date - timedelta(weeks=1)
            elif report_type == 'monthly':
                start_date = end_date - timedelta(days=30)
            else:
                start_date = end_date - timedelta(days=7)

        # メトリクス取得
        metrics = await self.get_video_metrics(video_id, force_refresh=True)

        # 期間内のイベント分析
        period_metrics = await self._get_period_metrics(video_id, start_date, end_date)

        # インサイト生成
        insights = await self._generate_insights(metrics, period_metrics)

        # レポート作成
        report = AnalyticsReport(
            report_id=f"report_{video_id}_{report_type}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            video_id=video_id,
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            metrics={
                "current_metrics": {
                    "total_views": metrics.total_views,
                    "unique_viewers": metrics.unique_viewers,
                    "completion_rate": metrics.completion_rate,
                    "average_watch_time": metrics.average_watch_time,
                    "engagement_score": metrics.engagement_score
                },
                "period_metrics": period_metrics,
                "drop_off_analysis": self._analyze_drop_off_points(metrics.drop_off_points)
            },
            insights=insights
        )

        # データベース保存
        await self._save_report(report)

        return report

    async def _get_period_metrics(self, video_id: str, start_date: datetime,
                                end_date: datetime) -> Dict[str, Any]:
        """期間内のメトリクスを取得"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            start_str = start_date.isoformat()
            end_str = end_date.isoformat()

            # 期間内のイベント数
            cursor.execute('''
                SELECT event_type, COUNT(*) as count
                FROM video_events
                WHERE video_id = ? AND timestamp BETWEEN ? AND ?
                GROUP BY event_type
            ''', (video_id, start_str, end_str))

            event_counts = dict(cursor.fetchall())

            # 時間帯別視聴傾向
            cursor.execute('''
                SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
                FROM video_events
                WHERE video_id = ? AND event_type = 'play' AND timestamp BETWEEN ? AND ?
                GROUP BY hour
                ORDER BY hour
            ''', (video_id, start_str, end_str))

            hourly_views = dict(cursor.fetchall())

            return {
                "event_counts": event_counts,
                "hourly_views": hourly_views,
                "period_days": (end_date - start_date).days
            }

    def _analyze_drop_off_points(self, drop_off_points: List[Tuple[float, int]]) -> Dict[str, Any]:
        """ドロップオフポイントを分析"""
        if not drop_off_points:
            return {"critical_points": [], "recommendations": []}

        # 上位のドロップオフポイント
        sorted_points = sorted(drop_off_points, key=lambda x: x[1], reverse=True)
        critical_points = sorted_points[:3]

        # レコメンデーション生成
        recommendations = []
        for position, count in critical_points:
            if position < 10:
                recommendations.append(
                    f"開始直後（{position:.1f}秒地点）で離脱が集中しています（{count}件）。冒頭の導入を見直してください。"
                )
            elif position > 50:
                recommendations.append(
                    f"後半（{position:.1f}秒地点）で離脱が見られます（{count}件）。終盤の構成やテンポを見直してください。"
                )
            else:
                recommendations.append(
                    f"中盤（{position:.1f}秒地点）で離脱が見られます（{count}件）。展開のテンポを見直してください。"
                )
        return {
            "critical_points": [{"position": pos, "drop_offs": count} for pos, count in critical_points],
            "recommendations": recommendations[:3]  # 上位3件
        }

    async def _generate_insights(self, current_metrics: VideoMetrics,
                               period_metrics: Dict[str, Any]) -> List[str]:
        """インサイトを生成"""
        insights = []

        # 完了率の分析
        if current_metrics.completion_rate < 0.5:
            insights.append("完了率が50%未満です。動画の長さや内容を見直すことをおすすめします。")
        elif current_metrics.completion_rate > 0.8:
            insights.append("完了率が80%を超えています。優れたエンゲージメントです！")

        # 平均視聴時間の分析
        if current_metrics.average_watch_time < 30:
            insights.append("平均視聴時間が30秒未満です。冒頭部分の魅力を高めることを検討してください。")
        elif current_metrics.average_watch_time > 120:
            insights.append("平均視聴時間が2分を超えています。視聴者の興味を引きつけています。")

        # エンゲージメントスコアの分析
        if current_metrics.engagement_score > 0.7:
            insights.append("エンゲージメントスコアが優秀です。現在の戦略を継続してください。")
        elif current_metrics.engagement_score < 0.3:
            insights.append("エンゲージメントスコアが低いです。内容の改善やターゲティングの見直しを検討してください。")

        # 時間帯別分析
        hourly_views = period_metrics.get("hourly_views", {})
        if hourly_views:
            peak_hour = max(hourly_views.items(), key=lambda x: x[1])
            insights.append(f"最も視聴されている時間帯は{peak_hour[0]}時です。この時間帯に動画を公開することを検討してください。")

        return insights

    async def _save_report(self, report: AnalyticsReport):
        """レポートを保存"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO analytics_reports
                (report_id, video_id, report_type, start_date, end_date,
                 metrics, insights, generated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                report.report_id,
                report.video_id,
                report.report_type,
                report.start_date.isoformat(),
                report.end_date.isoformat(),
                json.dumps(report.metrics, ensure_ascii=False),
                json.dumps(report.insights, ensure_ascii=False),
                report.generated_at.isoformat()
            ))

            conn.commit()

    async def get_reports(self, video_id: Optional[str] = None,
                         report_type: Optional[str] = None) -> List[AnalyticsReport]:
        """レポートを取得"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM analytics_reports WHERE 1=1"
            params = []

            if video_id:
                query += " AND video_id = ?"
                params.append(video_id)

            if report_type:
                query += " AND report_type = ?"
                params.append(report_type)

            query += " ORDER BY generated_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [
                AnalyticsReport(
                    report_id=row[0],
                    video_id=row[1],
                    report_type=row[2],
                    start_date=datetime.fromisoformat(row[3]),
                    end_date=datetime.fromisoformat(row[4]),
                    metrics=json.loads(row[5]),
                    insights=json.loads(row[6]),
                    generated_at=datetime.fromisoformat(row[7])
                )
                for row in rows
            ]

    async def export_analytics(self, video_id: str, format: str = 'json') -> Optional[str]:
        """
        アナリティクスデータをエクスポート

        Args:
            video_id: 動画ID
            format: エクスポート形式 ('json', 'csv')

        Returns:
            エクスポートファイルのパス
        """
        # メトリクス取得
        metrics = await self.get_video_metrics(video_id)

        # レポート取得
        reports = await self.get_reports(video_id)

        # イベントデータ取得
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM video_events WHERE video_id = ? ORDER BY timestamp',
                         (video_id,))
            events = cursor.fetchall()

        export_data = {
            "video_id": video_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "current_metrics": {
                "total_views": metrics.total_views,
                "unique_viewers": metrics.unique_viewers,
                "completion_rate": metrics.completion_rate,
                "average_watch_time": metrics.average_watch_time,
                "engagement_score": metrics.engagement_score,
                "drop_off_points": metrics.drop_off_points
            },
            "reports": [
                {
                    "report_id": r.report_id,
                    "type": r.report_type,
                    "period": f"{r.start_date.date()} to {r.end_date.date()}",
                    "insights": r.insights
                }
                for r in reports
            ],
            "recent_events": [
                {
                    "event_type": event[3],
                    "timestamp": event[4],
                    "position": event[5],
                    "user_id": event[2][:8] + "..."  # プライバシー保護
                }
                for event in events[-100:]  # 最近100件
            ]
        }

        # エクスポートディレクトリ
        export_dir = Path("data/analytics_exports")
        export_dir.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"analytics_{video_id}_{timestamp}.{format}"
        export_path = export_dir / filename

        if format == 'json':
            with open(export_path, 'w', encoding='utf-8') as f:  # noqa: ASYNC230
                json.dump(export_data, f, ensure_ascii=False, indent=2)
        elif format == 'csv':
            # CSVエクスポートの実装
            await self._export_to_csv(export_data, export_path)

        return str(export_path)

    async def _export_to_csv(self, data: Dict, export_path: Path):
        """CSV形式でエクスポート"""
        import csv

        with open(export_path, 'w', newline='', encoding='utf-8') as f:  # noqa: ASYNC230
            writer = csv.writer(f)

            # ヘッダー
            writer.writerow(['Metric', 'Value'])

            # 現在のメトリクス
            current_metrics = data['current_metrics']
            for key, value in current_metrics.items():
                if isinstance(value, list):
                    value = str(value)
                writer.writerow([key, value])

            # レポート情報
            writer.writerow([])
            writer.writerow(['Reports'])
            for report in data['reports']:
                writer.writerow([f"Report {report['report_id']}", report['type']])

    async def _update_metrics_cache(self):
        """メトリクスキャッシュを定期的に更新"""
        # 古いキャッシュエントリをクリーンアップ
        current_time = datetime.now(timezone.utc)

        with self.cache_lock:
            to_remove = []
            for video_id, metrics in self.metrics_cache.items():
                if (current_time - metrics.last_updated).seconds > self.cache_ttl:
                    to_remove.append(video_id)

            for video_id in to_remove:
                del self.metrics_cache[video_id]

    async def cleanup_old_data(self, days_to_keep: int = 90):
        """古いデータをクリーンアップ"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # 古いイベント削除
            cursor.execute('DELETE FROM video_events WHERE timestamp < ?',
                         (cutoff_date.isoformat(),))

            # 古いレポート削除
            cursor.execute('DELETE FROM analytics_reports WHERE generated_at < ?',
                         (cutoff_date.isoformat(),))

            deleted_events = cursor.rowcount
            conn.commit()

        logger.info(f"Cleaned up {deleted_events} old analytics events")

    async def close(self):
        """クリーンアップ"""
        self.is_processing = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)

# グローバルインスタンス管理
_video_analytics_service = None

async def get_video_analytics_service() -> VideoAnalyticsService:
    """動画アナリティクスサービスのインスタンスを取得"""
    global _video_analytics_service

    if _video_analytics_service is None:
        _video_analytics_service = VideoAnalyticsService()
        await _video_analytics_service.initialize()

    return _video_analytics_service
