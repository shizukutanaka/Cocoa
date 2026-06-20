# main/ar_cloud_manager.py
"""
AR Cloud Manager for Cocoa
現実世界との完全統合を実現するARクラウドシステム
"""

import asyncio
import json
import logging
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import open3d as o3d
    OPEN3D_AVAILABLE = True
except ImportError:
    OPEN3D_AVAILABLE = False
    logging.warning("Open3D not available. 3D reconstruction features will be limited.")

try:
    import pyproj  # noqa: F401
    PYPROJ_AVAILABLE = True
except ImportError:
    PYPROJ_AVAILABLE = False
    logging.warning("PyProj not available. Geospatial features will be limited.")

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class SpatialAnchor:
    """空間アンカー"""
    anchor_id: str
    position: Tuple[float, float, float]  # x, y, z
    rotation: Tuple[float, float, float, float]  # quaternion x, y, z, w
    scale: Tuple[float, float, float]  # x, y, z
    coordinate_system: str  # "local", "global", "gps"
    confidence: float  # 0.0-1.0
    created_by: str  # device_id or user_id
    created_at: datetime
    expires_at: Optional[datetime] = None

@dataclass
class ARContent:
    """ARコンテンツ"""
    content_id: str
    content_type: str  # "3d_model", "text", "image", "video", "audio", "avatar"
    position: Tuple[float, float, float]
    rotation: Tuple[float, float, float, float]
    scale: Tuple[float, float, float]
    data: Dict[str, Any]  # コンテンツ固有データ
    visibility_rules: Dict[str, Any]  # 表示条件
    interaction_enabled: bool
    persistent: bool  # 永続性
    created_by: str
    created_at: datetime
    last_accessed: datetime
    access_count: int

@dataclass
class PointCloudData:
    """ポイントクラウドデータ"""
    points: "Any"  # N x 3 ndarray
    colors: "Any"  # N x 3 ndarray
    normals: "Optional[Any]" = None
    timestamp: datetime = None
    device_id: str = ""
    location: Tuple[float, float, float] = None

@dataclass
class ARCloudMap:
    """ARクラウドマップ"""
    map_id: str
    name: str
    bounds: Tuple[Tuple[float, float, float], Tuple[float, float, float]]  # min, max
    coordinate_system: str
    point_cloud: Optional[PointCloudData]
    anchors: List[SpatialAnchor]
    content: List[ARContent]
    mesh_data: Optional[Dict[str, Any]]  # 3Dメッシュ
    created_at: datetime
    last_updated: datetime
    version: str

class ARCloudManager:
    """
    ARクラウドマネージャー
    現実世界との完全統合を実現するARクラウドシステム
    """

    def __init__(self, cloud_dir: str = "data/ar_cloud"):
        self.cloud_dir = Path(cloud_dir)
        self.cloud_dir.mkdir(parents=True, exist_ok=True)

        # 空間マッピング
        self.spatial_maps: Dict[str, ARCloudMap] = {}
        self.spatial_anchors: Dict[str, SpatialAnchor] = {}
        self.ar_content: Dict[str, ARContent] = {}

        # ポイントクラウド
        self.point_clouds: Dict[str, PointCloudData] = {}
        self.global_point_cloud: Optional[PointCloudData] = None

        # デバイス追跡
        self.connected_devices: Dict[str, Dict[str, Any]] = {}
        self.device_poses: Dict[str, Dict[str, Any]] = {}

        # 設定
        self.max_map_size = 1000  # 最大マップサイズ（MB）
        self.anchor_expiry_hours = 24  # アンカー有効期限
        self.content_retention_days = 30  # コンテンツ保持期間

        # 統計
        self.total_maps = 0
        self.total_anchors = 0
        self.total_content = 0
        self.data_processed_mb = 0

        # バックグラウンドタスク参照（GC防止）
        self._background_tasks: list = []

        logger.info("AR Cloud Manager initialized")

    async def initialize(self):
        """ARクラウドマネージャーの初期化"""
        await self._load_existing_maps()
        await self._initialize_spatial_system()
        self._background_tasks.append(asyncio.create_task(self._start_maintenance_tasks()))

    async def _load_existing_maps(self):
        """既存のARマップを読み込み"""
        maps_dir = self.cloud_dir / "maps"
        if maps_dir.exists():
            for map_file in maps_dir.glob("*.json"):
                try:
                    with open(map_file, encoding='utf-8') as f:  # noqa: ASYNC230
                        data = json.load(f)

                        # ポイントクラウドを読み込み
                        point_cloud = None
                        if data.get("point_cloud"):
                            points = np.array(data["point_cloud"]["points"])
                            colors = np.array(data["point_cloud"]["colors"])
                            point_cloud = PointCloudData(
                                points=points,
                                colors=colors,
                                timestamp=datetime.fromisoformat(data["point_cloud"]["timestamp"]),
                                device_id=data["point_cloud"]["device_id"],
                                location=tuple(data["point_cloud"]["location"]) if data["point_cloud"]["location"] else None
                            )

                        # アンカーを読み込み
                        anchors = [
                            SpatialAnchor(
                                anchor_id=anchor["anchor_id"],
                                position=tuple(anchor["position"]),
                                rotation=tuple(anchor["rotation"]),
                                scale=tuple(anchor["scale"]),
                                coordinate_system=anchor["coordinate_system"],
                                confidence=anchor["confidence"],
                                created_by=anchor["created_by"],
                                created_at=datetime.fromisoformat(anchor["created_at"]),
                                expires_at=datetime.fromisoformat(anchor["expires_at"]) if anchor.get("expires_at") else None
                            )
                            for anchor in data["anchors"]
                        ]

                        # コンテンツを読み込み
                        content = [
                            ARContent(
                                content_id=content_item["content_id"],
                                content_type=content_item["content_type"],
                                position=tuple(content_item["position"]),
                                rotation=tuple(content_item["rotation"]),
                                scale=tuple(content_item["scale"]),
                                data=content_item["data"],
                                visibility_rules=content_item["visibility_rules"],
                                interaction_enabled=content_item["interaction_enabled"],
                                persistent=content_item["persistent"],
                                created_by=content_item["created_by"],
                                created_at=datetime.fromisoformat(content_item["created_at"]),
                                last_accessed=datetime.fromisoformat(content_item["last_accessed"]),
                                access_count=content_item["access_count"]
                            )
                            for content_item in data["content"]
                        ]

                        # マップを作成
                        ar_map = ARCloudMap(
                            map_id=data["map_id"],
                            name=data["name"],
                            bounds=tuple(data["bounds"]),
                            coordinate_system=data["coordinate_system"],
                            point_cloud=point_cloud,
                            anchors=anchors,
                            content=content,
                            mesh_data=data.get("mesh_data"),
                            created_at=datetime.fromisoformat(data["created_at"]),
                            last_updated=datetime.fromisoformat(data["last_updated"]),
                            version=data["version"]
                        )

                        self.spatial_maps[ar_map.map_id] = ar_map
                        self.total_maps += 1

                except Exception as e:
                    logger.error(f"Failed to load AR map {map_file}: {e}")

    async def _initialize_spatial_system(self):
        """空間システムの初期化"""
        if OPEN3D_AVAILABLE:
            logger.info("Open3D initialized for 3D spatial processing")
        if PYPROJ_AVAILABLE:
            logger.info("PyProj initialized for geospatial coordinate systems")

    async def _start_maintenance_tasks(self):
        """メンテナンスタスクを開始"""
        # バックグラウンドで定期メンテナンス
        while True:
            try:
                await self._cleanup_expired_anchors()
                await self._cleanup_old_content()
                await self._optimize_maps()
                await asyncio.sleep(3600)  # 1時間間隔

            except Exception as e:
                logger.error(f"Maintenance task failed: {e}")
                await asyncio.sleep(1800)  # 30分待機

    async def create_spatial_map(self, name: str, coordinate_system: str = "local",
                               bounds: Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = None) -> str:
        """
        空間マップを作成

        Args:
            name: マップ名
            coordinate_system: 座標系
            bounds: 境界ボックス

        Returns:
            マップID
        """
        map_id = f"map_{uuid.uuid4().hex[:16]}"

        if bounds is None:
            # デフォルト境界
            bounds = ((-100, -100, -100), (100, 100, 100))

        ar_map = ARCloudMap(
            map_id=map_id,
            name=name,
            bounds=bounds,
            coordinate_system=coordinate_system,
            point_cloud=None,
            anchors=[],
            content=[],
            mesh_data=None,
            created_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
            version="1.0.0"
        )

        self.spatial_maps[map_id] = ar_map
        self.total_maps += 1

        await self._save_spatial_map(ar_map)

        logger.info(f"Created spatial map: {map_id} ({name})")
        return map_id

    async def _save_spatial_map(self, ar_map: ARCloudMap):
        """空間マップを保存"""
        maps_dir = self.cloud_dir / "maps"
        maps_dir.mkdir(parents=True, exist_ok=True)

        map_data = {
            "map_id": ar_map.map_id,
            "name": ar_map.name,
            "bounds": list(ar_map.bounds),
            "coordinate_system": ar_map.coordinate_system,
            "point_cloud": {
                "points": ar_map.point_cloud.points.tolist() if ar_map.point_cloud else [],
                "colors": ar_map.point_cloud.colors.tolist() if ar_map.point_cloud else [],
                "timestamp": ar_map.point_cloud.timestamp.isoformat() if ar_map.point_cloud else None,
                "device_id": ar_map.point_cloud.device_id if ar_map.point_cloud else "",
                "location": list(ar_map.point_cloud.location) if ar_map.point_cloud and ar_map.point_cloud.location else None
            } if ar_map.point_cloud else None,
            "anchors": [
                {
                    "anchor_id": anchor.anchor_id,
                    "position": list(anchor.position),
                    "rotation": list(anchor.rotation),
                    "scale": list(anchor.scale),
                    "coordinate_system": anchor.coordinate_system,
                    "confidence": anchor.confidence,
                    "created_by": anchor.created_by,
                    "created_at": anchor.created_at.isoformat(),
                    "expires_at": anchor.expires_at.isoformat() if anchor.expires_at else None
                }
                for anchor in ar_map.anchors
            ],
            "content": [
                {
                    "content_id": content.content_id,
                    "content_type": content.content_type,
                    "position": list(content.position),
                    "rotation": list(content.rotation),
                    "scale": list(content.scale),
                    "data": content.data,
                    "visibility_rules": content.visibility_rules,
                    "interaction_enabled": content.interaction_enabled,
                    "persistent": content.persistent,
                    "created_by": content.created_by,
                    "created_at": content.created_at.isoformat(),
                    "last_accessed": content.last_accessed.isoformat(),
                    "access_count": content.access_count
                }
                for content in ar_map.content
            ],
            "mesh_data": ar_map.mesh_data,
            "created_at": ar_map.created_at.isoformat(),
            "last_updated": ar_map.last_updated.isoformat(),
            "version": ar_map.version
        }

        map_file = maps_dir / f"{ar_map.map_id}.json"
        with open(map_file, 'w', encoding='utf-8') as f:  # noqa: ASYNC230
            json.dump(map_data, f, indent=2, ensure_ascii=False)

    async def add_spatial_anchor(self, map_id: str, position: Tuple[float, float, float],
                               rotation: Tuple[float, float, float, float],
                               coordinate_system: str = "local", created_by: str = "system") -> str:
        """
        空間アンカーを追加

        Args:
            map_id: マップID
            position: 位置
            rotation: 回転
            coordinate_system: 座標系
            created_by: 作成者

        Returns:
            アンカーID
        """
        if map_id not in self.spatial_maps:
            raise ValueError(f"Map not found: {map_id}")

        anchor_id = f"anchor_{uuid.uuid4().hex[:16]}"
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(hours=self.anchor_expiry_hours)

        anchor = SpatialAnchor(
            anchor_id=anchor_id,
            position=position,
            rotation=rotation,
            scale=(1.0, 1.0, 1.0),  # デフォルトスケール
            coordinate_system=coordinate_system,
            confidence=0.95,  # デフォルト信頼度
            created_by=created_by,
            created_at=created_at,
            expires_at=expires_at
        )

        self.spatial_anchors[anchor_id] = anchor
        self.spatial_maps[map_id].anchors.append(anchor)
        self.total_anchors += 1

        # マップを更新
        await self._update_spatial_map(map_id)

        logger.info(f"Added spatial anchor: {anchor_id} to map {map_id}")
        return anchor_id

    async def _update_spatial_map(self, map_id: str):
        """空間マップを更新"""
        if map_id in self.spatial_maps:
            self.spatial_maps[map_id].last_updated = datetime.now(timezone.utc)
            await self._save_spatial_map(self.spatial_maps[map_id])

    async def add_ar_content(self, map_id: str, content_type: str, position: Tuple[float, float, float],
                           content_data: Dict[str, Any], created_by: str = "system",
                           persistent: bool = True) -> str:
        """
        ARコンテンツを追加

        Args:
            map_id: マップID
            content_type: コンテンツタイプ
            position: 位置
            content_data: コンテンツデータ
            created_by: 作成者
            persistent: 永続性

        Returns:
            コンテンツID
        """
        if map_id not in self.spatial_maps:
            raise ValueError(f"Map not found: {map_id}")

        content_id = f"content_{uuid.uuid4().hex[:16]}"
        created_at = datetime.now(timezone.utc)

        content = ARContent(
            content_id=content_id,
            content_type=content_type,
            position=position,
            rotation=(0.0, 0.0, 0.0, 1.0),  # デフォルト回転
            scale=(1.0, 1.0, 1.0),  # デフォルトスケール
            data=content_data,
            visibility_rules={"public": True, "authenticated": False},  # デフォルト表示ルール
            interaction_enabled=True,
            persistent=persistent,
            created_by=created_by,
            created_at=created_at,
            last_accessed=created_at,
            access_count=0
        )

        self.ar_content[content_id] = content
        self.spatial_maps[map_id].content.append(content)
        self.total_content += 1

        # マップを更新
        await self._update_spatial_map(map_id)

        logger.info(f"Added AR content: {content_id} ({content_type}) to map {map_id}")
        return content_id

    async def process_point_cloud(self, device_id: str, point_cloud_data: PointCloudData,
                                map_id: Optional[str] = None) -> str:
        """
        ポイントクラウドを処理

        Args:
            device_id: デバイスID
            point_cloud_data: ポイントクラウドデータ
            map_id: マップID（指定しない場合は自動作成）

        Returns:
            処理されたマップID
        """
        try:
            # マップIDが指定されていない場合は作成
            if map_id is None or map_id not in self.spatial_maps:
                map_name = f"auto_map_{device_id}_{int(datetime.now(timezone.utc).timestamp())}"
                map_id = await self.create_spatial_map(map_name, "local")

            # 既存のポイントクラウドと統合
            if self.spatial_maps[map_id].point_cloud is None:
                self.spatial_maps[map_id].point_cloud = point_cloud_data
            else:
                # ICP（Iterative Closest Point）アルゴリズムで統合
                integrated_cloud = await self._integrate_point_clouds(
                    self.spatial_maps[map_id].point_cloud,
                    point_cloud_data
                )
                self.spatial_maps[map_id].point_cloud = integrated_cloud

            # 3Dメッシュ生成（可能な場合）
            if OPEN3D_AVAILABLE:
                mesh_data = await self._generate_mesh_from_point_cloud(
                    self.spatial_maps[map_id].point_cloud
                )
                self.spatial_maps[map_id].mesh_data = mesh_data

            # マップを更新
            await self._update_spatial_map(map_id)

            logger.info(f"Processed point cloud for device {device_id}, map {map_id}")
            return map_id

        except Exception as e:
            logger.error(f"Point cloud processing failed: {e}")
            raise

    async def _integrate_point_clouds(self, cloud1: PointCloudData, cloud2: PointCloudData) -> PointCloudData:
        """ポイントクラウドを統合"""
        if not OPEN3D_AVAILABLE:
            # 簡易的な統合
            combined_points = np.vstack([cloud1.points, cloud2.points])
            combined_colors = np.vstack([cloud1.colors, cloud2.colors])
        else:
            # Open3Dを使用した高精度統合
            pcd1 = o3d.geometry.PointCloud()
            pcd1.points = o3d.utility.Vector3dVector(cloud1.points)
            pcd1.colors = o3d.utility.Vector3dVector(cloud1.colors)

            pcd2 = o3d.geometry.PointCloud()
            pcd2.points = o3d.utility.Vector3dVector(cloud2.points)
            pcd2.colors = o3d.utility.Vector3dVector(cloud2.colors)

            # ICPによる位置合わせ
            reg_p2p = o3d.pipelines.registration.registration_icp(
                pcd2, pcd1, 0.1, np.eye(4),
                o3d.pipelines.registration.TransformationEstimationPointToPoint()
            )

            pcd2.transform(reg_p2p.transformation)

            # 統合
            combined_pcd = pcd1 + pcd2
            combined_points = np.asarray(combined_pcd.points)
            combined_colors = np.asarray(combined_pcd.colors)

        return PointCloudData(
            points=combined_points,
            colors=combined_colors,
            timestamp=datetime.now(timezone.utc),
            device_id=f"combined_{cloud1.device_id}_{cloud2.device_id}",
            location=cloud1.location  # 最初のクラウドの位置を使用
        )

    async def _generate_mesh_from_point_cloud(self, point_cloud: PointCloudData) -> Dict[str, Any]:
        """ポイントクラウドからメッシュを生成"""
        if not OPEN3D_AVAILABLE:
            return {"error": "Open3D not available"}

        try:
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(point_cloud.points)
            pcd.colors = o3d.utility.Vector3dVector(point_cloud.colors)

            # 法線を推定
            pcd.estimate_normals()

            # Poisson reconstructionでメッシュ生成
            mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=8)

            # メッシュをクリーンアップ
            mesh.remove_degenerate_triangles()
            mesh.remove_duplicated_triangles()
            mesh.remove_duplicated_vertices()
            mesh.remove_non_manifold_edges()

            # メッシュデータを保存可能な形式に変換
            vertices = np.asarray(mesh.vertices)
            triangles = np.asarray(mesh.triangles)
            vertex_colors = np.asarray(mesh.vertex_colors) if mesh.has_vertex_colors() else None

            return {
                "vertices": vertices.tolist(),
                "triangles": triangles.tolist(),
                "vertex_colors": vertex_colors.tolist() if vertex_colors is not None else None,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Mesh generation failed: {e}")
            return {"error": str(e)}

    async def localize_device(self, device_id: str, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        デバイスをローカライズ

        Args:
            device_id: デバイスID
            sensor_data: センサーデータ（カメラ画像、IMU、GPS等）

        Returns:
            ローカライズ結果
        """
        try:
            # 既存のマップから位置を推定
            best_map_id = None
            best_confidence = 0.0
            best_pose = None

            for map_id, ar_map in self.spatial_maps.items():
                if ar_map.point_cloud is None:
                    continue

                # 簡易的な特徴マッチング
                confidence, pose = await self._match_features(device_id, sensor_data, ar_map)

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_map_id = map_id
                    best_pose = pose

            if best_map_id and best_confidence > 0.7:  # 70%以上の信頼度
                # デバイス位置を更新
                self.device_poses[device_id] = {
                    "map_id": best_map_id,
                    "pose": best_pose,
                    "confidence": best_confidence,
                    "timestamp": datetime.now(timezone.utc)
                }

                result = {
                    "localized": True,
                    "map_id": best_map_id,
                    "pose": best_pose,
                    "confidence": best_confidence,
                    "available_content": len(self.spatial_maps[best_map_id].content),
                    "available_anchors": len(self.spatial_maps[best_map_id].anchors)
                }

                logger.info(f"Device localized: {device_id} in map {best_map_id} (confidence: {best_confidence:.2f})")
            else:
                result = {
                    "localized": False,
                    "reason": "insufficient_confidence",
                    "best_confidence": best_confidence,
                    "available_maps": len(self.spatial_maps)
                }

            return result

        except Exception as e:
            logger.error(f"Device localization failed: {e}")
            return {"localized": False, "error": str(e)}

    async def _match_features(self, device_id: str, sensor_data: Dict[str, Any], ar_map: ARCloudMap) -> Tuple[float, Dict[str, Any]]:
        """特徴マッチング"""
        # 簡易的な特徴マッチング実装
        # 実際にはSIFT, ORB, またはニューラルネットワークによる特徴抽出を使用

        # センサーデータから特徴を抽出
        if "camera_image" in sensor_data:
            # カメラ画像からの特徴抽出
            confidence = 0.8 + (0.2 * (len(ar_map.anchors) / 100))  # アンカー数に応じて信頼度調整
        elif "imu_data" in sensor_data:
            # IMUデータからの推定
            confidence = 0.6
        else:
            confidence = 0.3

        # 位置推定（簡易的）
        pose = {
            "position": (0.0, 0.0, 0.0),
            "rotation": (0.0, 0.0, 0.0, 1.0),
            "scale": (1.0, 1.0, 1.0)
        }

        return confidence, pose

    async def get_nearby_content(self, device_id: str, radius: float = 10.0) -> List[Dict[str, Any]]:
        """
        近くのARコンテンツを取得

        Args:
            device_id: デバイスID
            radius: 検索半径（メートル）

        Returns:
            近くのコンテンツリスト
        """
        if device_id not in self.device_poses:
            return []

        device_pose = self.device_poses[device_id]
        map_id = device_pose["map_id"]
        device_position = device_pose["pose"]["position"]

        if map_id not in self.spatial_maps:
            return []

        nearby_content = []
        ar_map = self.spatial_maps[map_id]

        for content in ar_map.content:
            # 距離を計算
            distance = math.sqrt(
                sum((a - b) ** 2 for a, b in zip(content.position, device_position))
            )

            if distance <= radius:
                # コンテンツを更新
                content.last_accessed = datetime.now(timezone.utc)
                content.access_count += 1

                nearby_content.append({
                    "content_id": content.content_id,
                    "content_type": content.content_type,
                    "position": content.position,
                    "rotation": content.rotation,
                    "scale": content.scale,
                    "data": content.data,
                    "distance": distance,
                    "interaction_enabled": content.interaction_enabled,
                    "visibility_rules": content.visibility_rules
                })

        # アクセス順でソート
        nearby_content.sort(key=lambda x: x["distance"])

        # マップを更新
        await self._update_spatial_map(map_id)

        logger.info(f"Found {len(nearby_content)} nearby AR content for device {device_id}")
        return nearby_content

    async def _cleanup_expired_anchors(self):
        """期限切れアンカーをクリーンアップ"""
        current_time = datetime.now(timezone.utc)
        expired_anchors = []

        for anchor_id, anchor in list(self.spatial_anchors.items()):
            if anchor.expires_at and current_time > anchor.expires_at:
                expired_anchors.append(anchor_id)

        for anchor_id in expired_anchors:
            del self.spatial_anchors[anchor_id]

            # 各マップから削除
            for map_id, ar_map in self.spatial_maps.items():
                ar_map.anchors = [a for a in ar_map.anchors if a.anchor_id != anchor_id]
                await self._update_spatial_map(map_id)

        if expired_anchors:
            logger.info(f"Cleaned up {len(expired_anchors)} expired anchors")

    async def _cleanup_old_content(self):
        """古いコンテンツをクリーンアップ"""
        current_time = datetime.now(timezone.utc)
        retention_period = timedelta(days=self.content_retention_days)

        old_content = []

        for content_id, content in list(self.ar_content.items()):
            if not content.persistent and (current_time - content.last_accessed) > retention_period:
                old_content.append(content_id)

        for content_id in old_content:
            del self.ar_content[content_id]

            # 各マップから削除
            for map_id, ar_map in self.spatial_maps.items():
                ar_map.content = [c for c in ar_map.content if c.content_id != content_id]
                await self._update_spatial_map(map_id)

        if old_content:
            logger.info(f"Cleaned up {len(old_content)} old content items")

    async def _optimize_maps(self):
        """マップを最適化"""
        for map_id, ar_map in self.spatial_maps.items():
            # ポイントクラウドのダウンサンプリング
            if ar_map.point_cloud and len(ar_map.point_cloud.points) > 1000000:
                # 1Mポイントを超える場合はダウンサンプリング
                ar_map.point_cloud.points = ar_map.point_cloud.points[::10]  # 10分の1に
                ar_map.point_cloud.colors = ar_map.point_cloud.colors[::10]
                await self._update_spatial_map(map_id)

    def get_ar_cloud_status(self) -> Dict[str, Any]:
        """ARクラウドステータスを取得"""
        return {
            "total_maps": self.total_maps,
            "total_anchors": self.total_anchors,
            "total_content": self.total_content,
            "connected_devices": len(self.connected_devices),
            "localized_devices": len(self.device_poses),
            "open3d_available": OPEN3D_AVAILABLE,
            "pyproj_available": PYPROJ_AVAILABLE,
            "data_processed_mb": self.data_processed_mb,
            "maps": {
                map_id: {
                    "name": ar_map.name,
                    "anchors": len(ar_map.anchors),
                    "content": len(ar_map.content),
                    "has_point_cloud": ar_map.point_cloud is not None,
                    "last_updated": ar_map.last_updated.isoformat()
                }
                for map_id, ar_map in self.spatial_maps.items()
            }
        }

# グローバルインスタンス
_ar_cloud_manager = None

async def get_ar_cloud_manager() -> ARCloudManager:
    """ARクラウドマネージャーのインスタンスを取得"""
    global _ar_cloud_manager

    if _ar_cloud_manager is None:
        _ar_cloud_manager = ARCloudManager()
        await _ar_cloud_manager.initialize()

    return _ar_cloud_manager
