import psutil
import time
from typing import Dict, Any
from datetime import datetime
from .error_handling import PerformanceError
from .logging_manager import Logger

class PerformanceAnalyzer:
    """Analyze system and application performance"""
    
    def __init__(self, logger: Logger):
        """Initialize performance analyzer"""
        self.logger = logger
        self.metrics = {
            'cpu': [],
            'memory': [],
            'disk': [],
            'network': []
        }
        self.running = False
    
    def start_monitoring(self, interval: int = 5) -> None:
        """Start performance monitoring"""
        if self.running:
            raise PerformanceError("Performance monitoring is already running")
            
        self.running = True
        print("Starting performance monitoring...")
        
        try:
            while self.running:
                self._collect_metrics()
                time.sleep(interval)
        except Exception as e:
            self.logger.error(f"Error in performance monitoring: {str(e)}")
            raise PerformanceError(f"Failed to monitor performance: {str(e)}")
    
    def stop_monitoring(self) -> None:
        """Stop performance monitoring"""
        self.running = False
        print("Performance monitoring stopped")
    
    def _collect_metrics(self) -> None:
        """Collect system metrics"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            self.metrics['cpu'].append({
                'timestamp': timestamp,
                'percent': cpu_percent,
                'count': cpu_count
            })
            
            # Memory metrics
            memory = psutil.virtual_memory()
            self.metrics['memory'].append({
                'timestamp': timestamp,
                'total': memory.total,
                'used': memory.used,
                'percent': memory.percent
            })
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            self.metrics['disk'].append({
                'timestamp': timestamp,
                'total': disk.total,
                'used': disk.used,
                'percent': disk.percent
            })
            
            # Network metrics
            net_io = psutil.net_io_counters()
            self.metrics['network'].append({
                'timestamp': timestamp,
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv
            })
            
            # Log metrics
            self.logger.info(f"Performance metrics collected at {timestamp}")
            
        except Exception as e:
            self.logger.error(f"Error collecting metrics: {str(e)}")
            raise PerformanceError(f"Failed to collect metrics: {str(e)}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics"""
        return self.metrics.copy()
    
    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze collected metrics"""
        try:
            analysis = {
                'cpu': self._analyze_cpu(),
                'memory': self._analyze_memory(),
                'disk': self._analyze_disk(),
                'network': self._analyze_network()
            }
            return analysis
        except Exception as e:
            raise PerformanceError(f"Failed to analyze performance: {str(e)}")
    
    def _analyze_cpu(self) -> Dict[str, Any]:
        """Analyze CPU metrics"""
        cpu_data = self.metrics['cpu']
        if not cpu_data:
            return {'error': 'No CPU data available'}
            
        avg_percent = sum(item['percent'] for item in cpu_data) / len(cpu_data)
        max_percent = max(item['percent'] for item in cpu_data)
        
        return {
            'average_usage': avg_percent,
            'max_usage': max_percent,
            'core_count': cpu_data[0]['count']
        }
    
    def _analyze_memory(self) -> Dict[str, Any]:
        """Analyze memory metrics"""
        memory_data = self.metrics['memory']
        if not memory_data:
            return {'error': 'No memory data available'}
            
        avg_percent = sum(item['percent'] for item in memory_data) / len(memory_data)
        max_percent = max(item['percent'] for item in memory_data)
        
        return {
            'average_usage': avg_percent,
            'max_usage': max_percent,
            'total_memory': memory_data[0]['total']
        }
    
    def _analyze_disk(self) -> Dict[str, Any]:
        """Analyze disk metrics"""
        disk_data = self.metrics['disk']
        if not disk_data:
            return {'error': 'No disk data available'}
            
        avg_percent = sum(item['percent'] for item in disk_data) / len(disk_data)
        max_percent = max(item['percent'] for item in disk_data)
        
        return {
            'average_usage': avg_percent,
            'max_usage': max_percent,
            'total_space': disk_data[0]['total']
        }
    
    def _analyze_network(self) -> Dict[str, Any]:
        """Analyze network metrics"""
        network_data = self.metrics['network']
        if not network_data:
            return {'error': 'No network data available'}
            
        # Calculate average transfer rates
        avg_sent = (network_data[-1]['bytes_sent'] - network_data[0]['bytes_sent']) / len(network_data)
        avg_recv = (network_data[-1]['bytes_recv'] - network_data[0]['bytes_recv']) / len(network_data)
        
        return {
            'average_upload': avg_sent,
            'average_download': avg_recv
        }
