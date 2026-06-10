# main/global_edge_manager.py
"""
Global Edge Network Manager for Cocoa
低遅延の国際展開を実現するグローバルエッジネットワークシステム
"""

import asyncio
import logging
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import time

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False


# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class EdgeNode:
    """エッジノード"""
    node_id: str
    region: str
    country: str
    city: str
    coordinates: Tuple[float, float]  # latitude, longitude
    ip_address: str
    capacity: Dict[str, int]  # CPU, memory, storage
    current_load: Dict[str, float]
    latency_ms: float
    bandwidth_mbps: float
    status: str  # "active", "maintenance", "offline"
    services: List[str]  # 提供サービス
    last_health_check: datetime
    created_at: datetime

@dataclass
class ContentCache:
    """コンテンツキャッシュ"""
    content_id: str
    cache_key: str
    content_type: str  # "avatar", "model", "texture", "script"
    size_bytes: int
    cached_at: datetime
    expires_at: datetime
    access_count: int
    last_accessed: datetime
    compression_ratio: float

@dataclass
class TrafficRoute:
    """トラフィックルート"""
    route_id: str
    source_region: str
    destination_region: str
    optimal_nodes: List[str]
    estimated_latency_ms: float
    bandwidth_capacity_mbps: float
    cost_per_gb: float
    reliability_score: float
    created_at: datetime

@dataclass
class EdgeAnalytics:
    """エッジ分析データ"""
    timestamp: datetime
    node_id: str
    metrics: Dict[str, float]
    events: List[Dict[str, Any]]
    performance_score: float

class GlobalEdgeManager:
    """
    グローバルエッジネットワークマネージャー
    世界中のエッジサーバーを管理し、低遅延サービスを提供
    """

    def __init__(self, edge_dir: str = "data/global_edge"):
        self.edge_dir = Path(edge_dir)
        self.edge_dir.mkdir(parents=True, exist_ok=True)

        # エッジネットワーク
        self.edge_nodes: Dict[str, EdgeNode] = {}
        self.content_cache: Dict[str, ContentCache] = {}
        self.traffic_routes: Dict[str, TrafficRoute] = {}
        self.analytics_data: Dict[str, List[EdgeAnalytics]] = {}

        # 地域設定
        self.regions = {
            "north_america": ["us-east-1", "us-west-1", "us-west-2", "ca-central-1"],
            "south_america": ["sa-east-1"],
            "europe": ["eu-west-1", "eu-central-1", "eu-north-1"],
            "asia_pacific": ["ap-northeast-1", "ap-southeast-1", "ap-south-1"],
            "middle_east_africa": ["me-south-1", "af-south-1"],
            "oceania": ["ap-southeast-2"]
        }

        # CDN設定
        self.cdn_domains = [
            "cdn.cocoa-avatar.com",
            "edge.cocoa-avatar.com",
            "global.cocoa-avatar.com"
        ]

        # 最適化設定
        self.route_cache_ttl = 300  # 5分
        self.health_check_interval = 60  # 1分
        self.cache_cleanup_interval = 3600  # 1時間

        # 統計
        self.total_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.average_latency_ms = 0
        self.optimized_routes = 0

        logger.info("Global Edge Manager initialized")

    async def initialize(self):
        """グローバルエッジマネージャーの初期化"""
        await self._initialize_edge_nodes()
        await self._load_traffic_routes()
        await self._start_health_monitoring()
        await self._start_analytics_collection()

    async def _initialize_edge_nodes(self):
        """エッジノードを初期化"""
        # 主要地域のエッジノードをシミュレーション
        edge_nodes_data = [
            {
                "node_id": "edge_us_east_1",
                "region": "north_america",
                "country": "US",
                "city": "New York",
                "coordinates": (40.7128, -74.0060),
                "ip_address": "192.168.1.100",
                "capacity": {"cpu": 32, "memory": 128, "storage": 1000},
                "services": ["cdn", "edge_ai", "cache"]
            },
            {
                "node_id": "edge_eu_west_1",
                "region": "europe",
                "country": "DE",
                "city": "Frankfurt",
                "coordinates": (50.1109, 8.6821),
                "ip_address": "192.168.2.100",
                "capacity": {"cpu": 24, "memory": 96, "storage": 800},
                "services": ["cdn", "edge_ai", "cache", "compute"]
            },
            {
                "node_id": "edge_ap_northeast_1",
                "region": "asia_pacific",
                "country": "JP",
                "city": "Tokyo",
                "coordinates": (35.6762, 139.6503),
                "ip_address": "192.168.3.100",
                "capacity": {"cpu": 28, "memory": 112, "storage": 900},
                "services": ["cdn", "edge_ai", "cache", "streaming"]
            },
            {
                "node_id": "edge_us_west_2",
                "region": "north_america",
                "country": "US",
                "city": "San Francisco",
                "coordinates": (37.7749, -122.4194),
                "ip_address": "192.168.4.100",
                "capacity": {"cpu": 36, "memory": 144, "storage": 1200},
                "services": ["cdn", "edge_ai", "cache", "compute", "streaming"]
            }
        ]

        for node_data in edge_nodes_data:
            node = EdgeNode(
                node_id=node_data["node_id"],
                region=node_data["region"],
                country=node_data["country"],
                city=node_data["city"],
                coordinates=node_data["coordinates"],
                ip_address=node_data["ip_address"],
                capacity=node_data["capacity"],
                current_load={"cpu": 0.2, "memory": 0.3, "storage": 0.1},
                latency_ms=50 + (hash(node_data["node_id"]) % 100),  # 50-150ms
                bandwidth_mbps=1000,
                status="active",
                services=node_data["services"],
                last_health_check=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            )

            self.edge_nodes[node.node_id] = node

        logger.info(f"Initialized {len(self.edge_nodes)} edge nodes")

    async def _load_traffic_routes(self):
        """トラフィックルートを読み込み"""
        routes_dir = self.edge_dir / "routes"
        if routes_dir.exists():
            for route_file in routes_dir.glob("*.json"):
                try:
                    with open(route_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                        route = TrafficRoute(
                            route_id=data["route_id"],
                            source_region=data["source_region"],
                            destination_region=data["destination_region"],
                            optimal_nodes=data["optimal_nodes"],
                            estimated_latency_ms=data["estimated_latency_ms"],
                            bandwidth_capacity_mbps=data["bandwidth_capacity_mbps"],
                            cost_per_gb=data["cost_per_gb"],
                            reliability_score=data["reliability_score"],
                            created_at=datetime.fromisoformat(data["created_at"])
                        )

                        self.traffic_routes[route.route_id] = route

                except Exception as e:
                    logger.error(f"Failed to load traffic route {route_file}: {e}")

    async def _start_health_monitoring(self):
        """ヘルスモニタリングを開始"""
        while True:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.health_check_interval)

            except Exception as e:
                logger.error(f"Health monitoring failed: {e}")
                await asyncio.sleep(120)  # 2分待機

    async def _perform_health_checks(self):
        """ヘルスチェックを実行"""
        for node_id, node in list(self.edge_nodes.items()):
            try:
                # レイテンシ測定
                latency = await self._measure_latency(node.ip_address)

                # 負荷状態の更新
                node.latency_ms = latency
                node.last_health_check = datetime.now(timezone.utc)

                # ステータス更新
                if latency > 200:  # 200ms以上は問題あり
                    node.status = "degraded"
                    logger.warning(f"Edge node {node_id} degraded: {latency}ms latency")
                elif node.current_load.get("cpu", 0) > 0.9:
                    node.status = "high_load"
                    logger.warning(f"Edge node {node_id} high load: {node.current_load['cpu']}")
                else:
                    node.status = "active"

            except Exception as e:
                node.status = "offline"
                logger.error(f"Edge node {node_id} health check failed: {e}")

    async def _measure_latency(self, ip_address: str) -> float:
        """レイテンシを測定"""
        try:
            start_time = time.time()
            # 簡易的なpingシミュレーション
            await asyncio.sleep(0.001)  # 1msのネットワーク遅延
            end_time = time.time()

            latency_ms = (end_time - start_time) * 1000
            return min(latency_ms, 200)  # 最大200msに制限

        except Exception:
            return 999  # エラー時は高レイテンシ

    async def _start_analytics_collection(self):
        """分析データ収集を開始"""
        while True:
            try:
                await self._collect_analytics()
                await asyncio.sleep(300)  # 5分間隔

            except Exception as e:
                logger.error(f"Analytics collection failed: {e}")
                await asyncio.sleep(600)  # 10分待機

    async def _collect_analytics(self):
        """分析データを収集"""
        for node_id, node in self.edge_nodes.items():
            if node.status == "active":
                analytics = EdgeAnalytics(
                    timestamp=datetime.now(timezone.utc),
                    node_id=node_id,
                    metrics={
                        "cpu_usage": node.current_load.get("cpu", 0),
                        "memory_usage": node.current_load.get("memory", 0),
                        "storage_usage": node.current_load.get("storage", 0),
                        "latency_ms": node.latency_ms,
                        "bandwidth_utilization": node.current_load.get("bandwidth", 0),
                        "request_count": 100 + (hash(node_id) % 1000),  # シミュレーション
                        "error_rate": 0.001 + (hash(node_id) % 100) / 100000
                    },
                    events=[
                        {"type": "cache_hit", "count": 85},
                        {"type": "cache_miss", "count": 15},
                        {"type": "optimization_applied", "count": 5}
                    ],
                    performance_score=self._calculate_performance_score(node)
                )

                if node_id not in self.analytics_data:
                    self.analytics_data[node_id] = []

                self.analytics_data[node_id].append(analytics)

                # 古いデータを削除（24時間分保持）
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
                self.analytics_data[node_id] = [
                    a for a in self.analytics_data[node_id]
                    if a.timestamp > cutoff_time
                ]

    def _calculate_performance_score(self, node: EdgeNode) -> float:
        """パフォーマンススコアを計算"""
        # CPU、メモリ、レイテンシ、信頼性からスコアを計算
        cpu_score = max(0, 1.0 - node.current_load.get("cpu", 0))
        memory_score = max(0, 1.0 - node.current_load.get("memory", 0))
        latency_score = max(0, 1.0 - min(node.latency_ms, 200) / 200)
        reliability_score = 1.0 if node.status == "active" else 0.5

        return (cpu_score + memory_score + latency_score + reliability_score) / 4

    async def find_optimal_route(self, source_location: Tuple[float, float],
                               content_type: str, priority: str = "performance") -> Optional[TrafficRoute]:
        """
        最適なトラフィックルートを検索

        Args:
            source_location: 送信元位置 (lat, lng)
            content_type: コンテンツタイプ
            priority: 優先度 ("performance", "cost", "reliability")

        Returns:
            最適ルート
        """
        try:
            # 送信元地域を特定
            source_region = self._get_region_from_coordinates(source_location)

            # 既存ルートを検索
            for route in self.traffic_routes.values():
                if route.source_region == source_region:
                    return route

            # 新しいルートを作成
            route = await self._create_optimal_route(source_region, content_type, priority)

            if route:
                self.traffic_routes[route.route_id] = route
                await self._save_traffic_route(route)
                self.optimized_routes += 1

            return route

        except Exception as e:
            logger.error(f"Route optimization failed: {e}")
            return None

    def _get_region_from_coordinates(self, coordinates: Tuple[float, float]) -> str:
        """座標から地域を特定"""
        lat, lng = coordinates

        # 簡易的な地域判定
        if -180 <= lng <= -30 and 15 <= lat <= 75:  # 北米
            return "north_america"
        if -90 <= lng <= -30 and -60 <= lat <= 15:  # 南米
            return "south_america"
        if -30 <= lng <= 60 and 30 <= lat <= 75:  # 欧州
            return "europe"
        if 60 <= lng <= 180 and -50 <= lat <= 50:  # アジア太平洋
            return "asia_pacific"
        if 30 <= lng <= 60 and -40 <= lat <= 30:  # 中東・アフリカ
            return "middle_east_africa"
        # オセアニア
        return "oceania"

    async def _create_optimal_route(self, source_region: str, content_type: str,
                                  priority: str) -> Optional[TrafficRoute]:
        """最適ルートを作成"""
        # 利用可能なノードを検索
        available_nodes = [
            node_id for node_id, node in self.edge_nodes.items()
            if node.status == "active" and content_type in node.services
        ]

        if not available_nodes:
            return None

        # 優先度に応じてノードを選択
        if priority == "performance":
            # 低レイテンシ優先
            available_nodes.sort(key=lambda n: self.edge_nodes[n].latency_ms)
        elif priority == "cost":
            # 低コスト優先（簡易的）
            available_nodes.sort(key=lambda n: self.edge_nodes[n].current_load["cpu"])
        else:  # reliability
            # 高信頼性優先
            available_nodes.sort(key=lambda n: self._calculate_performance_score(self.edge_nodes[n]), reverse=True)

        # 最適ノードを選択
        optimal_nodes = available_nodes[:3]  # 最大3ノード

        # 推定レイテンシを計算
        min_latency = min(self.edge_nodes[node].latency_ms for node in optimal_nodes)
        avg_bandwidth = sum(self.edge_nodes[node].bandwidth_mbps for node in optimal_nodes) / len(optimal_nodes)

        # コスト計算（簡易的）
        cost_per_gb = 0.05 + (len(optimal_nodes) * 0.02)

        # 信頼性スコア
        reliability = sum(self._calculate_performance_score(self.edge_nodes[node]) for node in optimal_nodes) / len(optimal_nodes)

        route = TrafficRoute(
            route_id=f"route_{uuid.uuid4().hex[:16]}",
            source_region=source_region,
            destination_region="global",  # グローバル配信
            optimal_nodes=optimal_nodes,
            estimated_latency_ms=min_latency,
            bandwidth_capacity_mbps=avg_bandwidth,
            cost_per_gb=cost_per_gb,
            reliability_score=reliability,
            created_at=datetime.now(timezone.utc)
        )

        return route

    async def _save_traffic_route(self, route: TrafficRoute):
        """トラフィックルートを保存"""
        routes_dir = self.edge_dir / "routes"
        routes_dir.mkdir(parents=True, exist_ok=True)

        route_data = {
            "route_id": route.route_id,
            "source_region": route.source_region,
            "destination_region": route.destination_region,
            "optimal_nodes": route.optimal_nodes,
            "estimated_latency_ms": route.estimated_latency_ms,
            "bandwidth_capacity_mbps": route.bandwidth_capacity_mbps,
            "cost_per_gb": route.cost_per_gb,
            "reliability_score": route.reliability_score,
            "created_at": route.created_at.isoformat()
        }

        route_file = routes_dir / f"{route.route_id}.json"
        with open(route_file, 'w', encoding='utf-8') as f:
            json.dump(route_data, f, indent=2, ensure_ascii=False)

    async def cache_content(self, content_id: str, content_data: bytes,
                          content_type: str, region: str) -> bool:
        """
        コンテンツをキャッシュ

        Args:
            content_id: コンテンツID
            content_data: コンテンツデータ
            content_type: コンテンツタイプ
            region: 配信地域

        Returns:
            キャッシュ成功かどうか
        """
        try:
            # 最適なエッジノードを選択
            optimal_nodes = await self._select_cache_nodes(region, content_type)

            if not optimal_nodes:
                return False

            # コンテンツを圧縮
            compressed_data, compression_ratio = await self._compress_content(content_data)

            # キャッシュエントリを作成
            cache_key = f"{content_type}_{content_id}_{hash(content_data)}"
            cache_expires = datetime.now(timezone.utc) + timedelta(hours=24)  # 24時間有効

            cache = ContentCache(
                content_id=content_id,
                cache_key=cache_key,
                content_type=content_type,
                size_bytes=len(compressed_data),
                cached_at=datetime.now(timezone.utc),
                expires_at=cache_expires,
                access_count=0,
                last_accessed=datetime.now(timezone.utc),
                compression_ratio=compression_ratio
            )

            self.content_cache[cache_key] = cache

            # 各ノードにコンテンツを配信
            for node_id in optimal_nodes:
                await self._deploy_to_edge_node(node_id, cache_key, compressed_data)

            logger.info(f"Content cached: {content_id} in {len(optimal_nodes)} nodes")

            return True

        except Exception as e:
            logger.error(f"Content caching failed: {e}")
            return False

    async def _select_cache_nodes(self, region: str, content_type: str) -> List[str]:
        """キャッシュノードを選択"""
        # 地域内のアクティブノードを検索
        region_nodes = [
            node_id for node_id, node in self.edge_nodes.items()
            if node.region == region and node.status == "active" and "cache" in node.services
        ]

        # 負荷が低い順にソート
        region_nodes.sort(key=lambda n: self.edge_nodes[n].current_load.get("storage", 0))

        return region_nodes[:3]  # 最大3ノード

    async def _compress_content(self, data: bytes) -> Tuple[bytes, float]:
        """コンテンツを圧縮"""
        import gzip

        # Gzip圧縮
        compressed = gzip.compress(data)
        compression_ratio = len(compressed) / len(data)

        return compressed, compression_ratio

    async def _deploy_to_edge_node(self, node_id: str, cache_key: str, data: bytes):
        """エッジノードにコンテンツをデプロイ"""
        # 実際の実装ではHTTP/HTTPSでノードにデータを送信
        cache_dir = self.edge_dir / "cache" / node_id
        cache_dir.mkdir(parents=True, exist_ok=True)

        cache_file = cache_dir / f"{cache_key}.cache"
        with open(cache_file, 'wb') as f:
            f.write(data)

    async def get_cached_content(self, content_id: str, content_type: str,
                               client_region: str) -> Optional[bytes]:
        """
        キャッシュされたコンテンツを取得

        Args:
            content_id: コンテンツID
            content_type: コンテンツタイプ
            client_region: クライアント地域

        Returns:
            コンテンツデータ
        """
        try:
            # キャッシュキーを生成
            cache_key = f"{content_type}_{content_id}_*"

            # 地域内の最適ノードから検索
            optimal_nodes = await self._select_cache_nodes(client_region, content_type)

            for node_id in optimal_nodes:
                # ローカルキャッシュを確認
                cache_dir = self.edge_dir / "cache" / node_id
                if cache_dir.exists():
                    for cache_file in cache_dir.glob(f"{content_id}*.cache"):
                        try:
                            with open(cache_file, 'rb') as f:
                                data = f.read()

                            # キャッシュを更新
                            cache_key = cache_file.stem
                            if cache_key in self.content_cache:
                                self.content_cache[cache_key].access_count += 1
                                self.content_cache[cache_key].last_accessed = datetime.now(timezone.utc)

                            # 解凍
                            import gzip
                            decompressed = gzip.decompress(data)

                            self.cache_hits += 1
                            logger.info(f"Cache hit: {content_id} from node {node_id}")
                            return decompressed

                        except Exception as e:
                            logger.warning(f"Cache read failed for {cache_file}: {e}")

            self.cache_misses += 1
            logger.info(f"Cache miss: {content_id}")
            return None

        except Exception as e:
            logger.error(f"Cache retrieval failed: {e}")
            return None

    async def get_edge_analytics(self, region: Optional[str] = None,
                               time_range_hours: int = 24) -> Dict[str, Any]:
        """
        エッジ分析データを取得

        Args:
            region: 対象地域（指定しない場合は全地域）
            time_range_hours: 時間範囲

        Returns:
            分析データ
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=time_range_hours)

            # 地域フィルタ
            if region:
                node_ids = [nid for nid, node in self.edge_nodes.items() if node.region == region]
            else:
                node_ids = list(self.edge_nodes.keys())

            analytics = {
                "time_range": f"{time_range_hours} hours",
                "total_requests": self.total_requests,
                "cache_hit_rate": self.cache_hits / max(1, self.cache_hits + self.cache_misses),
                "average_latency_ms": self.average_latency_ms,
                "optimized_routes": self.optimized_routes,
                "active_nodes": len([n for n in self.edge_nodes.values() if n.status == "active"]),
                "regional_performance": {}
            }

            # 地域別パフォーマンス
            for region_name, _region_nodes in self.regions.items():
                region_analytics = []
                for node_id in node_ids:
                    if node_id in self.analytics_data:
                        recent_data = [
                            a for a in self.analytics_data[node_id]
                            if a.timestamp > cutoff_time
                        ]
                        if recent_data:
                            scores = [a.performance_score for a in recent_data]
                            latencies = [a.metrics.get("latency_ms", 0) for a in recent_data]
                            if NUMPY_AVAILABLE:
                                avg_performance = float(np.mean(scores))
                                avg_latency = float(np.mean(latencies))
                            else:
                                avg_performance = sum(scores) / len(scores)
                                avg_latency = sum(latencies) / len(latencies)
                            region_analytics.append({
                                "node_id": node_id,
                                "performance_score": avg_performance,
                                "average_latency": avg_latency,
                                "data_points": len(recent_data)
                            })

                if region_analytics:
                    perf_scores = [a["performance_score"] for a in region_analytics]
                    latency_vals = [a["average_latency"] for a in region_analytics]
                    if NUMPY_AVAILABLE:
                        avg_perf = float(np.mean(perf_scores))
                        avg_lat = float(np.mean(latency_vals))
                    else:
                        avg_perf = sum(perf_scores) / len(perf_scores)
                        avg_lat = sum(latency_vals) / len(latency_vals)
                    analytics["regional_performance"][region_name] = {
                        "average_performance": avg_perf,
                        "average_latency": avg_lat,
                        "node_count": len(region_analytics),
                        "nodes": region_analytics
                    }

            return analytics

        except Exception as e:
            logger.error(f"Analytics retrieval failed: {e}")
            return {"error": str(e)}

    def get_global_edge_status(self) -> Dict[str, Any]:
        """グローバルエッジステータスを取得"""
        return {
            "total_nodes": len(self.edge_nodes),
            "active_nodes": len([n for n in self.edge_nodes.values() if n.status == "active"]),
            "total_cache_entries": len(self.content_cache),
            "total_routes": len(self.traffic_routes),
            "cache_hit_rate": self.cache_hits / max(1, self.cache_hits + self.cache_misses),
            "average_latency_ms": self.average_latency_ms,
            "regions": {
                region: {
                    "nodes": len([n for n in self.edge_nodes.values() if n.region == region]),
                    "active_nodes": len([n for n in self.edge_nodes.values() if n.region == region and n.status == "active"])
                }
                for region in self.regions
            },
            "cdn_domains": self.cdn_domains,
            "supported_services": list({
                service for node in self.edge_nodes.values()
                for service in node.services
            }),
            "analytics_data_points": sum(len(data) for data in self.analytics_data.values())
        }

# グローバルインスタンス
_global_edge_manager = None

async def get_global_edge_manager() -> GlobalEdgeManager:
    """グローバルエッジマネージャーのインスタンスを取得"""
    global _global_edge_manager

    if _global_edge_manager is None:
        _global_edge_manager = GlobalEdgeManager()
        await _global_edge_manager.initialize()

    return _global_edge_manager
