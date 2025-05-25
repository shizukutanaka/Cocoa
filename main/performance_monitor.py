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
    """Enhanced performance monitoring system with advanced features"""
    def __init__(self):
        """Initialize performance monitor"""
        self.config = get_config_manager()
        self.settings = self.config.get_plugin_config("performance_monitor")
        
        if self.settings:
            self.interval = self.settings.get("interval", 5)  # Monitoring interval (seconds)
            self.history_size = self.settings.get("history_size", 100)  # History size
            self.max_history = self.settings.get("max_history", 1000)  # Maximum history size
            self.cleanup_interval = self.settings.get("cleanup_interval", 3600)  # Cleanup interval (seconds)
            
            # Performance thresholds
            self.thresholds = {
                "memory": self.settings.get("memory_threshold", 80),  # Memory usage threshold (%)
                "cpu": self.settings.get("cpu_threshold", 90),  # CPU usage threshold (%)
                "avatar_processing": self.settings.get("avatar_processing_threshold", 100),  # Avatar processing threshold (ms)
                "preset_processing": self.settings.get("preset_processing_threshold", 50),  # Preset processing threshold (ms)
                "disk_io": self.settings.get("disk_io_threshold", 1000),  # Disk I/O threshold (KB/s)
                "network": self.settings.get("network_threshold", 1000),  # Network bandwidth threshold (KB/s)
                "gpu": self.settings.get("gpu_threshold", 90),  # GPU usage threshold (%)
                "process_memory": self.settings.get("process_memory_threshold", 90)  # Process memory threshold (%)
            }
            
            # Alert configuration
            self.alert_config = {
                "enabled": self.settings.get("alert_enabled", True),
                "threshold": self.settings.get("alert_threshold", 3),  # Consecutive alert threshold
                "cooldown": self.settings.get("alert_cooldown", 60),  # Alert cooldown period (seconds)
                "severity_levels": self.settings.get("severity_levels", {
                    "warning": 80,
                    "critical": 95
                })
            }
            
            # Optimization settings
            self.optimization_config = {
                "enabled": self.settings.get("optimization_enabled", True),
                "interval": self.settings.get("optimization_interval", 3600),  # Optimization check interval (seconds)
                "strategies": self.settings.get("optimization_strategies", {
                    "memory": ["compact", "clear_cache"],
                    "cpu": ["thread_pool", "priority"],
                    "disk": ["cache_clear", "file_optimize"],
                    "network": ["connection_pool", "compression"]
                })
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
            
    async def adaptive_optimize(self):
        """Adaptively optimize resources based on current conditions"""
        if not self.metrics:
            return
            
        current_time = time.time()
        if current_time - self._last_adaptive_optimization < self._adaptive_optimization_interval:
            return
            
        # Get current metrics
        metrics = self.metrics
        if not metrics:
            return
            
        # Forecast future usage
        predictions = await self.forecast_resource_usage()
        
        # Analyze patterns
        patterns = self._analyze_resource_patterns()
        
        # Determine optimization strategy
        strategy = self._adaptive_optimizer.determine_strategy(
            metrics,
            predictions,
            patterns
        )
        
        # Apply optimization
        await self._adaptive_optimizer.apply_strategy(strategy)
        
        self._last_adaptive_optimization = current_time
    
    def _analyze_resource_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Analyze resource usage patterns"""
        patterns = {}
        for resource, history in self.metrics.items():
            if history:
                values = [point['value'] for point in history]
                timestamps = [point['timestamp'] for point in history]
                patterns[resource] = {
                    'trend': self._calculate_trend(values),
                    'seasonality': self._calculate_seasonality(values, timestamps),
                    'variance': self._calculate_variance(values),
                    'peak': max(values),
                    'avg': sum(values) / len(values)
                }
        return patterns
    
    async def forecast_resource_usage(self) -> Dict[str, float]:
        """Forecast future resource usage"""
        predictions = {}
        for resource in self.metrics.keys():
            if self.metrics[resource]:
                prediction = await self._resource_forecaster.forecast(
                    resource,
                    self.metrics[resource],
                    time.time() + 3600
                )
                predictions[resource] = prediction
        return predictions
    
    class AdaptiveOptimizer:
        """Adaptive optimization engine"""
        
        def __init__(self):
            self._strategies = {
                'cpu': [
                    'load_balancing',
                    'priority_adjustment',
                    'process_scheduling'
                ],
                'memory': [
                    'compaction',
                    'cache_clearing',
                    'heap_optimization'
                ],
                'disk': [
                    'io_optimization',
                    'cache_clearing',
                    'data_compression'
                ],
                'network': [
                    'connection_optimization',
                    'traffic_compression',
                    'load_balancing'
                ],
                'gpu': [
                    'memory_optimization',
                    'process_scheduling',
                    'load_balancing'
                ]
            }
            self._last_strategies = {}
            self._strategy_effectiveness = {}
            
        def determine_strategy(self, 
                            metrics: Dict[str, List[Dict[str, Any]]],
                            predictions: Dict[str, float],
                            patterns: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
            """Determine optimal optimization strategy"""
            strategy = {}
            for resource in self._strategies.keys():
                if resource in metrics:
                    current = metrics[resource][-1]['value']
                    predicted = predictions[resource]
                    pattern = patterns[resource]
                    
                    # Determine strategy based on conditions
                    if predicted > 90:  # High usage predicted
                        strategy[resource] = self._strategies[resource][0]
                    elif predicted > 80:  # Moderate usage
                        strategy[resource] = self._strategies[resource][1]
                    else:  # Low usage
                        strategy[resource] = self._strategies[resource][2]
                        
                    # Consider previous strategy effectiveness
                    if resource in self._strategy_effectiveness:
                        if self._strategy_effectiveness[resource] < 0.5:
                            strategy[resource] = self._strategies[resource][0]
                            
            return strategy
            
        async def apply_strategy(self, strategy: Dict[str, str]):
            """Apply optimization strategy"""
            for resource, opt_strategy in strategy.items():
                if resource in self._strategies:
                    await getattr(self, f'_optimize_{opt_strategy}')(resource)
                    
        async def _optimize_compaction(self, resource: str):
            """Optimize memory compaction"""
            import gc
            gc.collect()
            
        async def _optimize_cache_clearing(self, resource: str):
            """Clear cache"""
            # Implementation depends on resource type
            pass
            
        async def _optimize_heap_optimization(self, resource: str):
            """Optimize heap memory"""
            # Implementation depends on resource type
            pass
            
        async def _optimize_load_balancing(self, resource: str):
            """Balance resource load"""
            # Implementation depends on resource type
            pass
            
        async def _optimize_priority_adjustment(self, resource: str):
            """Adjust process priority"""
            # Implementation depends on resource type
            pass
            
        async def _optimize_process_scheduling(self, resource: str):
            """Optimize process scheduling"""
            # Implementation depends on resource type
            pass
            
        async def _optimize_io_optimization(self, resource: str):
            """Optimize disk I/O"""
            # Implementation depends on resource type
            pass
            
        async def _optimize_data_compression(self, resource: str):
            """Compress data"""
            # Implementation depends on resource type
            pass
            
        async def _optimize_connection_optimization(self, resource: str):
            """Optimize network connections"""
            # Implementation depends on resource type
            pass
            
        async def _optimize_traffic_compression(self, resource: str):
            """Compress network traffic"""
            # Implementation depends on resource type
            pass
            
        async def _optimize_memory_optimization(self, resource: str):
            """Optimize GPU memory"""
            # Implementation depends on resource type
            pass
            
        async def evaluate_strategy(self, resource: str, strategy: str):
            """Evaluate strategy effectiveness"""
            if resource not in self._last_strategies:
                self._last_strategies[resource] = strategy
                return
                
            # Compare current metrics with previous
            current_metrics = await self._get_current_metrics(resource)
            previous_metrics = await self._get_previous_metrics(resource)
            
            # Calculate improvement
            improvement = self._calculate_improvement(
                current_metrics,
                previous_metrics
            )
            
            # Update strategy effectiveness
            self._strategy_effectiveness[resource] = improvement
            
        async def _get_current_metrics(self, resource: str) -> Dict[str, float]:
            """Get current resource metrics"""
            # Implementation depends on resource type
            pass
            
        async def _get_previous_metrics(self, resource: str) -> Dict[str, float]:
            """Get previous resource metrics"""
            # Implementation depends on resource type
            pass
            
        def _calculate_improvement(self, 
                                current: Dict[str, float],
                                previous: Dict[str, float]) -> float:
            """Calculate improvement percentage"""
            if not previous:
                return 1.0
                
            improvement = 0.0
            count = 0
            
            for metric, current_value in current.items():
                if metric in previous:
                    prev_value = previous[metric]
                    if prev_value > 0:
                        improvement += (current_value - prev_value) / prev_value
                        count += 1
                        
            return improvement / count if count > 0 else 1.0
    
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
        """Collect comprehensive performance statistics asynchronously"""
        try:
            # Collect statistics in parallel
            memory_stats = await self._collect_memory_stats()
            cpu_stats = await self._collect_cpu_stats()
            disk_stats = await self._collect_disk_stats()
            network_stats = await self._collect_network_stats()
            gpu_stats = await self._collect_gpu_stats()
            process_stats = await self._collect_process_stats()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "memory": memory_stats,
                "cpu": cpu_stats,
                "gpu": gpu_stats,
                "disk_io": disk_stats,
                "network": network_stats,
                "process": process_stats,
                "avatar_processing": self.avatar_timer.get_stats(),
                "preset_processing": self.preset_timer.get_stats(),
                "disk_processing": self.disk_timer.get_stats(),
                "network_processing": self.network_timer.get_stats()
            }
        except Exception as e:
            logger.error(f"Error collecting performance stats: {str(e)}")
            return self._get_default_stats()
            
        except Exception as e:
            logger.error(f"Error collecting performance stats: {str(e)}")
            return self._get_default_stats()
    
    async def _collect_memory_stats(self) -> Dict[str, Any]:
        """Collect comprehensive memory statistics"""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        process_mem = psutil.Process().memory_info()
        
        return {
            "system": {
                "total": mem.total,
                "used": mem.used,
                "percent": mem.percent,
                "available": mem.available,
                "swap": {
                    "total": swap.total,
                    "used": swap.used,
                    "percent": swap.percent
                }
            },
            "process": {
                "rss": process_mem.rss,
                "vms": process_mem.vms,
                "percent": process_mem.rss / mem.total * 100
            }
        }
    
    def _collect_cpu_stats(self) -> Dict[str, Any]:
        """Collect comprehensive CPU statistics"""
        cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
        cpu_times = psutil.cpu_times_percent(interval=0.1, percpu=True)
        cpu_freq = psutil.cpu_freq(percpu=True)
        
        return {
            "count": psutil.cpu_count(),
            "usage": {
                "total": sum(cpu_percent) / len(cpu_percent),
                "per_cpu": cpu_percent,
                "times": {
                    "user": [t.user for t in cpu_times],
                    "system": [t.system for t in cpu_times],
                    "idle": [t.idle for t in cpu_times]
                }
            },
            "frequency": {
                "current": [f.current for f in cpu_freq],
                "min": [f.min for f in cpu_freq],
                "max": [f.max for f in cpu_freq]
            }
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
        """Check for performance alerts with severity levels"""
        alerts = []
        
        # Memory usage check
        memory_usage = stats["memory"]["system"]["percent"]
        if memory_usage > self.thresholds["memory"]:
            severity = "warning" if memory_usage < self.alert_config["severity_levels"]["critical"] else "critical"
            alerts.append({
                "type": "memory",
                "value": memory_usage,
                "threshold": self.thresholds["memory"],
                "severity": severity
            })
        
        # CPU usage check
        cpu_usage = stats["cpu"]["usage"]["total"]
        if cpu_usage > self.thresholds["cpu"]:
            severity = "warning" if cpu_usage < self.alert_config["severity_levels"]["critical"] else "critical"
            alerts.append({
                "type": "cpu",
                "value": cpu_usage,
                "threshold": self.thresholds["cpu"],
                "severity": severity
            })
        
        # GPU usage check
        gpu_usage = stats.get("gpu", {}).get("stats", [])
        for gpu in gpu_usage:
            if gpu["load"] > self.thresholds["gpu"]:
                severity = "warning" if gpu["load"] < self.alert_config["severity_levels"]["critical"] else "critical"
                alerts.append({
                    "type": "gpu",
                    "value": gpu["load"],
                    "threshold": self.thresholds["gpu"],
                    "severity": severity,
                    "gpu_name": gpu["name"]
                })
        
        # Process memory check
        process_memory = stats["process"]["memory"]["percent"]
        if process_memory > self.thresholds["process_memory"]:
            severity = "warning" if process_memory < self.alert_config["severity_levels"]["critical"] else "critical"
            alerts.append({
                "type": "process_memory",
                "value": process_memory,
                "threshold": self.thresholds["process_memory"],
                "severity": severity
            })
        
        # Disk I/O check
        if stats["disk_io"]["write_bytes"] > self.thresholds["disk_io"]:
            severity = "warning" if stats["disk_io"]["write_bytes"] < self.alert_config["severity_levels"]["critical"] else "critical"
            alerts.append({
                "type": "disk_io",
                "value": stats["disk_io"]["write_bytes"],
                "threshold": self.thresholds["disk_io"],
                "severity": severity
            })
        
        # Network bandwidth check
        network_usage = stats["network"]["bytes_sent"] + stats["network"]["bytes_recv"]
        if network_usage > self.thresholds["network"]:
            severity = "warning" if network_usage < self.alert_config["severity_levels"]["critical"] else "critical"
            alerts.append({
                "type": "network",
                "value": network_usage,
                "threshold": self.thresholds["network"],
                "severity": severity
            })
        
        # Processing time checks
        if stats["avatar_processing"]["average_time"] > self.thresholds["avatar_processing"]:
            severity = "warning" if stats["avatar_processing"]["average_time"] < self.alert_config["severity_levels"]["critical"] else "critical"
            alerts.append({
                "type": "avatar_processing",
                "value": stats["avatar_processing"]["average_time"],
                "threshold": self.thresholds["avatar_processing"],
                "severity": severity
            })
        
        if stats["preset_processing"]["average_time"] > self.thresholds["preset_processing"]:
            severity = "warning" if stats["preset_processing"]["average_time"] < self.alert_config["severity_levels"]["critical"] else "critical"
            alerts.append({
                "type": "preset_processing",
                "value": stats["preset_processing"]["average_time"],
                "threshold": self.thresholds["preset_processing"],
                "severity": severity
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
    
    async def optimize_performance(self) -> None:
        """Optimize performance based on analysis"""
        if not self.optimization_config["enabled"]:
            return
            
        current_time = datetime.now()
        if self.last_optimization is None or \
           (current_time - self.last_optimization).total_seconds() > self.optimization_config["interval"]:
            
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
                    elif metric == 'disk':
                        await self._optimize_disk()
                    elif metric == 'network':
                        await self._optimize_network()
    
    async def _optimize_memory(self) -> None:
        """Optimize memory usage"""
        try:
            # Clear caches
            await self._clear_caches()
            
            # Compact memory
            await self._compact_memory()
            
            # Optimize data structures
            await self._optimize_data_structures()
            
        except Exception as e:
            logger.error(f"Memory optimization failed: {str(e)}")
    
    async def _optimize_cpu(self) -> None:
        """Optimize CPU usage"""
        try:
            # Adjust thread pool size
            await self._adjust_thread_pool()
            
            # Optimize process priority
            await self._optimize_process_priority()
            
            # Implement CPU scheduling optimizations
            await self._optimize_cpu_scheduling()
            
        except Exception as e:
            logger.error(f"CPU optimization failed: {str(e)}")
    
    async def _optimize_disk(self) -> None:
        """Optimize disk I/O"""
        try:
            # Clear disk cache
            await self._clear_disk_cache()
            
            # Optimize file operations
            await self._optimize_file_operations()
            
            # Implement disk I/O optimizations
            await self._optimize_disk_io()
            
        except Exception as e:
            logger.error(f"Disk optimization failed: {str(e)}")
    
    async def _optimize_network(self) -> None:
        """Optimize network usage"""
        try:
            # Optimize connection pool
            await self._optimize_connection_pool()
            
            # Implement network optimizations
            await self._optimize_network_usage()
            
            # Compress network traffic
            await self._compress_network_traffic()
            
        except Exception as e:
            logger.error(f"Network optimization failed: {str(e)}")
    
    async def _clear_caches(self) -> None:
        """Clear various caches"""
        import gc
        gc.collect()
        
    async def _compact_memory(self) -> None:
        """Compact memory usage"""
        import psutil
        process = psutil.Process()
        process.paged_memory_size()  # Force memory compaction
    
    async def _optimize_data_structures(self) -> None:
        """Optimize data structures"""
        # Implement data structure optimizations
        pass
    
    async def _adjust_thread_pool(self) -> None:
        """Adjust thread pool size based on system resources"""
        import psutil
        cpu_count = psutil.cpu_count()
        self._executor = ThreadPoolExecutor(max_workers=cpu_count * 2)
    
    async def _optimize_process_priority(self) -> None:
        """Optimize process priority"""
        import psutil
        process = psutil.Process()
        process.nice(psutil.HIGH_PRIORITY_CLASS)
    
    async def _optimize_cpu_scheduling(self) -> None:
        """Optimize CPU scheduling"""
        # Implement CPU scheduling optimizations
        pass
    
    async def _clear_disk_cache(self) -> None:
        """Clear disk cache"""
        import psutil
        process = psutil.Process()
        process.flush_io_counters()
    
    async def _optimize_file_operations(self) -> None:
        """Optimize file operations"""
        # Implement file operation optimizations
        pass
    
    async def _optimize_disk_io(self) -> None:
        """Optimize disk I/O"""
        # Implement disk I/O optimizations
        pass
    
    async def _optimize_connection_pool(self) -> None:
        """Optimize connection pool"""
        # Implement connection pool optimizations
        pass
    
    async def _optimize_network_usage(self) -> None:
        """Optimize network usage"""
        # Implement network usage optimizations
        pass
    
    async def _compress_network_traffic(self) -> None:
        """Compress network traffic"""
        # Implement network traffic compression
        pass
    
    def _analyze_performance(self) -> Dict[str, Any]:
        """Comprehensive performance analysis"""
        analysis = {}
        
        # Calculate detailed statistics
        for metric, history in self.metrics_history.items():
            if history:
                values = [item['value'] for item in history]
                analysis[metric] = {
                    'average': mean(values),
                    'std_dev': stdev(values) if len(values) > 1 else 0,
                    'current': values[-1],
                    'threshold': self.thresholds.get(metric, 0),
                    'min': min(values),
                    'max': max(values),
                    'p95': self._calculate_percentile(values, 95),
                    'p99': self._calculate_percentile(values, 99),
                    'trend': self._calculate_trend(values),
                    'anomalies': self._detect_anomalies(values)
                }
        
        # Detect performance issues
        issues = []
        for metric, data in analysis.items():
            if data['current'] > data['threshold']:
                issues.append({
                    'metric': metric,
                    'value': data['current'],
                    'threshold': data['threshold'],
                    'std_dev': data['std_dev'],
                    'severity': self._determine_severity(data['current'], data['threshold']),
                    'anomalies': data['anomalies']
                })
        
        return {
            'analysis': analysis,
            'issues': issues,
            'timestamp': datetime.now().isoformat(),
            'recommendations': self._generate_recommendations(issues)
        }
    
    def _calculate_percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile value"""
        if not values:
            return 0
            
        sorted_values = sorted(values)
        index = int(len(sorted_values) * (percentile / 100))
        return sorted_values[index]
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate performance trend"""
        if len(values) < 2:
            return "stable"
            
        avg_change = sum(values[i] - values[i-1] for i in range(1, len(values))) / (len(values) - 1)
        
        if avg_change > 0:
            return "increasing"
        elif avg_change < 0:
            return "decreasing"
        return "stable"
    
    def _detect_anomalies(self, values: List[float]) -> List[Dict[str, Any]]:
        """Detect performance anomalies"""
        if len(values) < 3:
            return []
            
        mean_val = mean(values)
        std_dev = stdev(values)
        
        anomalies = []
        for i, value in enumerate(values):
            if abs(value - mean_val) > 3 * std_dev:  # More than 3 standard deviations
                anomalies.append({
                    'timestamp': datetime.now() - timedelta(seconds=(len(values) - i) * self.interval),
                    'value': value,
                    'deviation': abs(value - mean_val) / std_dev
                })
        
        return anomalies
    
    def _determine_severity(self, value: float, threshold: float) -> str:
        """Determine severity level"""
        if value < threshold:
            return "normal"
        elif value < threshold * 1.5:
            return "warning"
        return "critical"
    
    def _generate_recommendations(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate optimization recommendations"""
        recommendations = []
        for issue in issues:
            metric = issue['metric']
            severity = issue['severity']
            
            if metric == 'memory':
                recommendations.append({
                    'type': 'memory',
                    'severity': severity,
                    'recommendation': self._get_memory_recommendations(issue)
                })
            elif metric == 'cpu':
                recommendations.append({
                    'type': 'cpu',
                    'severity': severity,
                    'recommendation': self._get_cpu_recommendations(issue)
                })
            elif metric == 'disk':
                recommendations.append({
                    'type': 'disk',
                    'severity': severity,
                    'recommendation': self._get_disk_recommendations(issue)
                })
            elif metric == 'network':
                recommendations.append({
                    'type': 'network',
                    'severity': severity,
                    'recommendation': self._get_network_recommendations(issue)
                })
        
        return recommendations
    
    def _get_memory_recommendations(self, issue: Dict[str, Any]) -> List[str]:
        """Get memory optimization recommendations"""
        recommendations = []
        if issue['severity'] == 'critical':
            recommendations.extend([
                "Clear memory caches",
                "Optimize data structures",
                "Implement memory compaction"
            ])
        else:
            recommendations.extend([
                "Monitor memory usage",
                "Optimize memory allocation",
                "Implement caching strategies"
            ])
        return recommendations
    
    def _get_cpu_recommendations(self, issue: Dict[str, Any]) -> List[str]:
        """Get CPU optimization recommendations"""
        recommendations = []
        if issue['severity'] == 'critical':
            recommendations.extend([
                "Adjust thread pool size",
                "Optimize process priority",
                "Implement CPU scheduling optimizations"
            ])
        else:
            recommendations.extend([
                "Monitor CPU usage",
                "Optimize algorithms",
                "Implement task prioritization"
            ])
        return recommendations
    
    def _get_disk_recommendations(self, issue: Dict[str, Any]) -> List[str]:
        """Get disk optimization recommendations"""
        recommendations = []
        if issue['severity'] == 'critical':
            recommendations.extend([
                "Clear disk cache",
                "Optimize file operations",
                "Implement disk I/O optimizations"
            ])
        else:
            recommendations.extend([
                "Monitor disk usage",
                "Optimize file access patterns",
                "Implement caching strategies"
            ])
        return recommendations
    
    def _get_network_recommendations(self, issue: Dict[str, Any]) -> List[str]:
        """Get network optimization recommendations"""
        recommendations = []
        if issue['severity'] == 'critical':
            recommendations.extend([
                "Optimize connection pool",
                "Implement network optimizations",
                "Compress network traffic"
            ])
        else:
            recommendations.extend([
                "Monitor network usage",
                "Optimize connection management",
                "Implement traffic optimization"
            ])
        return recommendations
    
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
