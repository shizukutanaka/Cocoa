"""
パフォーマンス監視システム
バージョン: 1.0.0
特徴:
- リアルタイムパフォーマンスモニタリング
- アバター処理パフォーマンス監視
- プレセット処理パフォーマンス監視
- メモリ使用量監視
- CPU使用率監視
- アラート通知機能
"""
import os
import psutil
import logging
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional
from config_manager import get_config_manager

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """パフォーマンス監視クラス"""
    def __init__(self):
        """初期化"""
        self.config = get_config_manager()
        self.settings = self.config.get_plugin_config("performance_monitor")
        
        if self.settings:
            self.interval = self.settings.get("interval", 5)  # 監視間隔（秒）
            self.thresholds = {
                "memory": self.settings.get("memory_threshold", 80),  # メモリ使用率閾値（%）
                "cpu": self.settings.get("cpu_threshold", 90),  # CPU使用率閾値（%）
                "avatar_processing": self.settings.get("avatar_processing_threshold", 100),  # アバター処理時間閾値（ms）
                "preset_processing": self.settings.get("preset_processing_threshold", 50)  # プレセット処理時間閾値（ms）
            }
            
            self.alert_enabled = self.settings.get("alert_enabled", True)
            self.alert_threshold = self.settings.get("alert_threshold", 3)  # 連続アラート閾値
            
            self.alert_count = 0
            self.last_alert = None
            
            # モニタリングスレッドの初期化
            self.monitor_thread = None
            self.running = False
            
            # アバター処理時間計測器
            self.avatar_timer = PerformanceTimer()
            self.preset_timer = PerformanceTimer()
            
    def start_monitoring(self) -> None:
        """モニタリングを開始"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            logger.info("パフォーマンス監視を開始しました")
    
    def stop_monitoring(self) -> None:
        """モニタリングを停止"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
            logger.info("パフォーマンス監視を停止しました")
    
    def _monitor(self) -> None:
        """モニタリングループ"""
        while self.running:
            try:
                # パフォーマンスデータの収集
                stats = self._collect_stats()
                
                # アラートチェック
                if self._check_alerts(stats):
                    self._send_alert(stats)
                
                # ログ記録
                self._log_stats(stats)
                
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"パフォーマンス監視中にエラーが発生しました: {e}")
                time.sleep(self.interval)
    
    def _collect_stats(self) -> Dict[str, Any]:
        """パフォーマンス統計を収集"""
        return {
            "timestamp": datetime.now().isoformat(),
            "memory": {
                "total": psutil.virtual_memory().total,
                "used": psutil.virtual_memory().used,
                "percent": psutil.virtual_memory().percent
            },
            "cpu": {
                "usage": psutil.cpu_percent(interval=1),
                "count": psutil.cpu_count()
            },
            "avatar_processing": {
                "time_ms": self.avatar_timer.get_average_time(),
                "count": self.avatar_timer.get_count()
            },
            "preset_processing": {
                "time_ms": self.preset_timer.get_average_time(),
                "count": self.preset_timer.get_count()
            }
        }
    
    def _check_alerts(self, stats: Dict[str, Any]) -> bool:
        """アラート条件をチェック"""
        alerts = []
        
        # メモリチェック
        if stats["memory"]["percent"] > self.thresholds["memory"]:
            alerts.append(f"メモリ使用率が{self.thresholds['memory']}%を超過")
        
        # CPUチェック
        if stats["cpu"]["usage"] > self.thresholds["cpu"]:
            alerts.append(f"CPU使用率が{self.thresholds['cpu']}%を超過")
        
        # アバター処理チェック
        if stats["avatar_processing"]["time_ms"] > self.thresholds["avatar_processing"]:
            alerts.append(f"アバター処理時間が{self.thresholds['avatar_processing']}msを超過")
        
        # プレセット処理チェック
        if stats["preset_processing"]["time_ms"] > self.thresholds["preset_processing"]:
            alerts.append(f"プレセット処理時間が{self.thresholds['preset_processing']}msを超過")
        
        # アラート発生時
        if alerts:
            self.alert_count += 1
            if self.alert_count >= self.alert_threshold:
                return True
        else:
            self.alert_count = 0
        
        return False
    
    def _send_alert(self, stats: Dict[str, Any]) -> None:
        """アラートを送信"""
        if self.alert_enabled:
            message = f"パフォーマンス警告: {datetime.now().isoformat()}\n"
            message += f"メモリ: {stats['memory']['percent']}%\n"
            message += f"CPU: {stats['cpu']['usage']}%\n"
            message += f"アバター処理: {stats['avatar_processing']['time_ms']}ms\n"
            message += f"プレセット処理: {stats['preset_processing']['time_ms']}ms\n"
            
            # アラート通知（プラットフォームに応じて）
            if os.name == 'nt':
                import win10toast
                toaster = win10toast.ToastNotifier()
                toaster.show_toast(
                    "Cocoa Performance Alert",
                    message,
                    duration=10
                )
            else:
                print(f"\n警告: {message}")
            
            self.last_alert = datetime.now()
            self.alert_count = 0
    
    def _log_stats(self, stats: Dict[str, Any]) -> None:
        """パフォーマンス統計をログに記録"""
        log_msg = f"パフォーマンス統計 - {stats['timestamp']}\n"
        log_msg += f"メモリ: {stats['memory']['percent']}%\n"
        log_msg += f"CPU: {stats['cpu']['usage']}%\n"
        log_msg += f"アバター処理: {stats['avatar_processing']['time_ms']}ms\n"
        log_msg += f"プレセット処理: {stats['preset_processing']['time_ms']}ms\n"
        
        logger.info(log_msg)

class PerformanceTimer:
    """パフォーマンス計測クラス"""
    def __init__(self):
        self.total_time = 0
        self.count = 0
        self.start_time = None
        
    def start(self) -> None:
        """計測開始"""
        self.start_time = time.perf_counter()
        
    def stop(self) -> float:
        """計測終了"""
        if self.start_time is None:
            return 0
            
        elapsed = (time.perf_counter() - self.start_time) * 1000  # msに変換
        self.total_time += elapsed
        self.count += 1
        self.start_time = None
        return elapsed
        
    def get_average_time(self) -> float:
        """平均処理時間の取得"""
        return self.total_time / self.count if self.count > 0 else 0
        
    def get_count(self) -> int:
        """計測回数の取得"""
        return self.count
