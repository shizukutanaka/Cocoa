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
from typing import Dict, Any, Optional, List, Tuple, Callable
from config_manager import get_config_manager
import asyncio
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from statistics import mean, stdev
import json

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Enhanced performance monitoring system"""
    def __init__(self):
        """Initialize performance monitor"""
        self.config = get_config_manager()
        self.settings = self.config.get_plugin_config("performance_monitor")
        
        if self.settings:
            self.interval = self.settings.get("interval", 5)  # Monitoring interval (seconds)
            self.history_size = self.settings.get("history_size", 100)  # History size
            
            self.thresholds = {
                "memory": self.settings.get("memory_threshold", 80),  # Memory usage threshold (%)
                "cpu": self.settings.get("cpu_threshold", 90),  # CPU usage threshold (%)
                "avatar_processing": self.settings.get("avatar_processing_threshold", 100),  # Avatar processing threshold (ms)
                "preset_processing": self.settings.get("preset_processing_threshold", 50),  # Preset processing threshold (ms)
                "disk_io": self.settings.get("disk_io_threshold", 1000),  # Disk I/O threshold (KB/s)
                "network": self.settings.get("network_threshold", 1000)  # Network bandwidth threshold (KB/s)
            }
            
            self.alert_config = {
                "enabled": self.settings.get("alert_enabled", True),
                "threshold": self.settings.get("alert_threshold", 3),  # Consecutive alert threshold
                "cooldown": self.settings.get("alert_cooldown", 60)  # Alert cooldown period (seconds)
            }
            
            self.alert_count = 0
            self.last_alert = None
            self.last_alert_time = None
            
            # Monitoring thread initialization
            self.monitor_thread = None
            self.running = False
            self.executor = ThreadPoolExecutor(max_workers=2)
            
            # Performance metrics history
            self.metrics_history = {
                'memory': deque(maxlen=self.history_size),
                'cpu': deque(maxlen=self.history_size),
                'disk_io': deque(maxlen=self.history_size),
                'network': deque(maxlen=self.history_size),
                'avatar_processing': deque(maxlen=self.history_size),
                'preset_processing': deque(maxlen=self.history_size)
            }
            
            # Performance timers
            self.avatar_timer = PerformanceTimer()
            self.preset_timer = PerformanceTimer()
            self.disk_timer = PerformanceTimer()
            self.network_timer = PerformanceTimer()
            
            # Optimization flags
            self.optimized_mode = False
            self.last_optimization = None
            self.optimization_interval = self.settings.get("optimization_interval", 3600)  # Optimization check interval (seconds)
            
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
    
    async def _collect_stats(self) -> Dict[str, Any]:
        """Collect performance statistics asynchronously"""
        try:
            # Collect statistics in parallel
            memory_stats = await self._collect_memory_stats()
            cpu_stats = await self._collect_cpu_stats()
            disk_stats = await self._collect_disk_stats()
            network_stats = await self._collect_network_stats()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "memory": memory_stats,
                "cpu": cpu_stats,
                "disk_io": disk_stats,
                "network": network_stats,
                "avatar_processing": self.avatar_timer.get_stats(),
                "preset_processing": self.preset_timer.get_stats(),
                "disk_processing": self.disk_timer.get_stats(),
                "network_processing": self.network_timer.get_stats()
            }
            
        except Exception as e:
            logger.error(f"Error collecting performance stats: {str(e)}")
            return self._get_default_stats()
    
    async def _collect_memory_stats(self) -> Dict[str, Any]:
        """Collect memory statistics"""
        mem = psutil.virtual_memory()
        return {
            "total": mem.total,
            "used": mem.used,
            "percent": mem.percent,
            "available": mem.available
        }
    
    async def _collect_cpu_stats(self) -> Dict[str, Any]:
        """Collect CPU statistics"""
        return {
            "usage": psutil.cpu_percent(interval=0.1),
            "count": psutil.cpu_count(),
            "per_cpu": psutil.cpu_percent(interval=0.1, percpu=True)
        }
    
    async def _collect_disk_stats(self) -> Dict[str, Any]:
        """Collect disk I/O statistics"""
        io_counters = psutil.disk_io_counters(perdisk=False)
        return {
            "read_bytes": io_counters.read_bytes,
            "write_bytes": io_counters.write_bytes,
            "read_time": io_counters.read_time,
            "write_time": io_counters.write_time
        }
    
    async def _collect_network_stats(self) -> Dict[str, Any]:
        """Collect network statistics"""
        net_io = psutil.net_io_counters(pernic=False)
        return {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv
        }
    
    def _get_default_stats(self) -> Dict[str, Any]:
        """Get default statistics"""
        return {
            "timestamp": datetime.now().isoformat(),
            "memory": {
                "total": 0,
                "used": 0,
                "percent": 0
            },
            "cpu": {
                "usage": 0,
                "count": 0
            },
            "disk_io": {
                "read_bytes": 0,
                "write_bytes": 0
            },
            "network": {
                "bytes_sent": 0,
                "bytes_recv": 0
            },
            "avatar_processing": self.avatar_timer.get_stats(),
            "preset_processing": self.preset_timer.get_stats(),
            "disk_processing": self.disk_timer.get_stats(),
            "network_processing": self.network_timer.get_stats()
        }
    
    async def _log_stats(self, stats: Dict[str, Any]) -> None:
        """Log performance statistics"""
        try:
            # Log to file
            log_file = self.config.config_path.parent / "performance.log"
            async with aiofiles.open(log_file, 'a', encoding='utf-8') as f:
                await f.write(json.dumps(stats) + "\n")
                
            # Update metrics history
            for metric in stats:
                if metric in self.metrics_history:
                    self.metrics_history[metric].append({
                        'timestamp': stats['timestamp'],
                        'value': stats[metric]['value'] if isinstance(stats[metric], dict) else stats[metric]
                    })
                    
        except Exception as e:
            logger.error(f"Error logging performance stats: {str(e)}")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get detailed performance report"""
        return {
            'current_stats': self._get_current_stats(),
            'history': self._get_history_report(),
            'analysis': self._analyze_performance(),
            'optimizations': self._get_optimization_status()
        }
    
    def _get_current_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        try:
            return asyncio.run(self._collect_stats())
        except Exception as e:
            logger.error(f"Error getting current stats: {str(e)}")
            return self._get_default_stats()
    
    def _get_history_report(self) -> Dict[str, Any]:
        """Get performance history report"""
        report = {}
        for metric, history in self.metrics_history.items():
            if history:
                report[metric] = {
                    'min': min(item['value'] for item in history),
                    'max': max(item['value'] for item in history),
                    'avg': mean(item['value'] for item in history),
                    'last': history[-1]['value'],
                    'trend': self._calculate_trend(history)
                }
        return report
    
    def _calculate_trend(self, history: List[Dict[str, Any]]) -> str:
        """Calculate performance trend"""
        if len(history) < 2:
            return "stable"
            
        values = [item['value'] for item in history]
        last_value = values[-1]
        avg = mean(values[:-1])
        
        if last_value > avg * 1.2:  # 20% above average
            return "increasing"
        elif last_value < avg * 0.8:  # 20% below average
            return "decreasing"
        return "stable"
    
    def _get_optimization_status(self) -> Dict[str, Any]:
        """Get optimization status"""
        return {
            'optimized_mode': self.optimized_mode,
            'last_optimization': self.last_optimization.isoformat() if self.last_optimization else None,
            'next_optimization': (self.last_optimization + 
                                timedelta(seconds=self.optimization_interval)).isoformat() 
                                if self.last_optimization else None
        }
    
    def _check_alerts(self, stats: Dict[str, Any]) -> bool:
        """Check for performance alerts"""
        alerts = []
        
        # Memory usage check
        if stats["memory"]["percent"] > self.thresholds["memory"]:
            alerts.append({
                "type": "memory",
                "value": stats["memory"]["percent"],
                "threshold": self.thresholds["memory"]
            })
        
        # CPU usage check
        if stats["cpu"]["usage"] > self.thresholds["cpu"]:
            alerts.append({
                "type": "cpu",
                "value": stats["cpu"]["usage"],
                "threshold": self.thresholds["cpu"]
            })
        
        # Disk I/O check
        if stats["disk_io"]["write_bytes"] > self.thresholds["disk_io"]:
            alerts.append({
                "type": "disk_io",
                "value": stats["disk_io"]["write_bytes"],
                "threshold": self.thresholds["disk_io"]
            })
        
        # Network bandwidth check
        if stats["network"]["bytes_sent"] + stats["network"]["bytes_recv"] > self.thresholds["network"]:
            alerts.append({
                "type": "network",
                "value": stats["network"]["bytes_sent"] + stats["network"]["bytes_recv"],
                "threshold": self.thresholds["network"]
            })
        
        # Processing time checks
        if stats["avatar_processing"]["average_time"] > self.thresholds["avatar_processing"]:
            alerts.append({
                "type": "avatar_processing",
                "value": stats["avatar_processing"]["average_time"],
                "threshold": self.thresholds["avatar_processing"]
            })
        
        if stats["preset_processing"]["average_time"] > self.thresholds["preset_processing"]:
            alerts.append({
                "type": "preset_processing",
                "value": stats["preset_processing"]["average_time"],
                "threshold": self.thresholds["preset_processing"]
            })
        
        # Check if we should send an alert
        if alerts:
            current_time = datetime.now()
            if self.last_alert_time is None or \
               (current_time - self.last_alert_time).total_seconds() > self.alert_config["cooldown"]:
                
                self.alert_count += 1
                if self.alert_count >= self.alert_config["threshold"]:
                    self.last_alert = alerts
                    self.last_alert_time = current_time
                    return True
        else:
            self.alert_count = 0
        
        return False
    
    def _analyze_performance(self) -> Dict[str, Any]:
        """Analyze performance metrics"""
        analysis = {}
        
        # Calculate averages and standard deviations
        for metric, history in self.metrics_history.items():
            if history:
                values = [item['value'] for item in history]
                analysis[metric] = {
                    'average': mean(values),
                    'std_dev': stdev(values) if len(values) > 1 else 0,
                    'current': values[-1],
                    'threshold': self.thresholds.get(metric, 0)
                }
        
        # Detect performance issues
        issues = []
        for metric, data in analysis.items():
            if data['current'] > data['threshold']:
                issues.append({
                    'metric': metric,
                    'value': data['current'],
                    'threshold': data['threshold'],
                    'std_dev': data['std_dev']
                })
        
        return {
            'analysis': analysis,
            'issues': issues,
            'timestamp': datetime.now().isoformat()
        }
    
    async def optimize_performance(self) -> None:
        """Optimize performance based on analysis"""
        if self.optimized_mode:
            return
            
        current_time = datetime.now()
        if self.last_optimization is None or \
           (current_time - self.last_optimization).total_seconds() > self.optimization_interval:
            
            analysis = self._analyze_performance()
            issues = analysis['issues']
            
            if issues:
                self.optimized_mode = True
                self.last_optimization = current_time
                
                # Implement optimization strategies
                for issue in issues:
                    metric = issue['metric']
                    if metric == 'memory':
                        await self._optimize_memory()
                    elif metric == 'cpu':
                        await self._optimize_cpu()
                    elif metric == 'disk_io':
                        await self._optimize_disk()
                    elif metric == 'network':
                        await self._optimize_network()
    
    async def _optimize_memory(self) -> None:
        """Optimize memory usage"""
        try:
            # Implement memory optimization strategies
            # Example: Clear caches, optimize data structures
            pass
        except Exception as e:
            logger.error(f"Memory optimization failed: {str(e)}")
    
    async def _optimize_cpu(self) -> None:
        """Optimize CPU usage"""
        try:
            # Implement CPU optimization strategies
            # Example: Adjust thread priorities, optimize algorithms
            pass
        except Exception as e:
            logger.error(f"CPU optimization failed: {str(e)}")
    
    async def _optimize_disk(self) -> None:
        """Optimize disk I/O"""
        try:
            # Implement disk optimization strategies
            # Example: Optimize file operations, cache frequently accessed files
            pass
        except Exception as e:
            logger.error(f"Disk optimization failed: {str(e)}")
    
    async def _optimize_network(self) -> None:
        """Optimize network usage"""
        try:
            # Implement network optimization strategies
            # Example: Optimize connection pooling, reduce bandwidth usage
            pass
        except Exception as e:
            logger.error(f"Network optimization failed: {str(e)}")
    
    def _send_alert(self, stats: Dict[str, Any]) -> None:
        """アラートを送信"""
        if self.alert_enabled:
            message = f"パフォーマンス警告: {datetime.now().isoformat()}\n"
            message += f"メモリ: {stats['memory']['percent']}%\n"
            message += f"CPU: {stats['cpu']['usage']}%\n"
            message += f"アバター処理: {stats['avatar_processing']['average_time']}ms\n"
            message += f"プレゼント処理: {stats['preset_processing']['average_time']}ms\n"
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
