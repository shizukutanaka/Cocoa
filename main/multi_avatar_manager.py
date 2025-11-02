# main/multi_avatar_manager.py
"""
Multi Avatar Manager Module for Cocoa
複数アバターの同時管理と複雑な交信シーン作成
"""

import os
import asyncio
import logging
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass
from datetime import datetime
import statistics
import numpy as np

from .integrated_security import get_security_manager
from .ai_avatar_generator import get_ai_avatar_generator
from .video_creator import get_video_creator

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class AvatarInstance:
    """アバターインスタンス"""
    instance_id: str
    avatar_id: str
    name: str
    position: Tuple[int, int]  # シーン内の位置 (x, y)
    size: Tuple[int, int]      # サイズ (width, height)
    z_index: int = 0           # 重ね順
    animation_state: Dict[str, Any] = None
    voice_settings: Dict[str, Any] = None
    dialogue_queue: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.animation_state is None:
            self.animation_state = {}
        if self.voice_settings is None:
            self.voice_settings = {}
        if self.dialogue_queue is None:
            self.dialogue_queue = []

@dataclass
class SceneElement:
    """シーン要素"""
    element_id: str
    element_type: str  # 'avatar', 'prop', 'text', 'background'
    position: Tuple[int, int]
    size: Tuple[int, int]
    z_index: int = 0
    properties: Dict[str, Any] = None
    animation_timeline: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.properties is None:
            self.properties = {}
        if self.animation_timeline is None:
            self.animation_timeline = []

@dataclass
class MultiAvatarScene:
    """複数アバターシーン"""
    scene_id: str
    name: str
    description: str
    duration: float  # 秒
    resolution: Tuple[int, int]
    background: Optional[str] = None
    avatars: List[AvatarInstance] = None
    elements: List[SceneElement] = None
    script: List[Dict[str, Any]] = None
    audio_tracks: List[Dict[str, Any]] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.avatars is None:
            self.avatars = []
        if self.elements is None:
            self.elements = []
        if self.script is None:
            self.script = []
        if self.audio_tracks is None:
            self.audio_tracks = []
        if self.created_at is None:
            self.created_at = datetime.now()

@dataclass
class SceneTimeline:
    """シーンタイムライン"""
    timeline_id: str
    scene_id: str
    total_duration: float
    events: List[Dict[str, Any]] = None
    keyframes: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.events is None:
            self.events = []
        if self.keyframes is None:
            self.keyframes = []

class MultiAvatarManager:
    """
    複数アバター管理システム
    複雑な交信シーンの作成と管理
    """

    def __init__(self):
        self.security_manager = get_security_manager()
        self.avatar_generator = None
        self.video_creator = None

        # データベース
        self.db_path = Path("data/multi_avatar.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # シーンストレージ
        self.scenes: Dict[str, MultiAvatarScene] = {}
        self.active_scenes: Dict[str, SceneTimeline] = {}

        # 設定
        self.max_avatars_per_scene = 10
        self.max_scene_duration = 300  # 5分
        self.default_resolution = (1920, 1080)

        logger.info("Multi Avatar Manager initialized")

    async def initialize(self):
        """初期化"""
        # データベース初期化
        await self._init_database()

        # サービス取得
        if not self.avatar_generator:
            self.avatar_generator = await get_ai_avatar_generator()
        if not self.video_creator:
            self.video_creator = await get_video_creator()

        # 保存されたシーン読み込み
        await self._load_scenes()

        logger.info("Multi Avatar Manager initialized successfully")

    async def _init_database(self):
        """データベース初期化"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # シーン情報テーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scenes (
                    scene_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    duration REAL NOT NULL,
                    resolution TEXT NOT NULL,
                    background TEXT,
                    avatars TEXT NOT NULL,
                    elements TEXT NOT NULL,
                    script TEXT NOT NULL,
                    audio_tracks TEXT NOT NULL,
                    created_at TEXT
                )
            ''')

            # タイムラインテーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS timelines (
                    timeline_id TEXT PRIMARY KEY,
                    scene_id TEXT NOT NULL,
                    total_duration REAL NOT NULL,
                    events TEXT NOT NULL,
                    keyframes TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (scene_id) REFERENCES scenes(scene_id)
                )
            ''')

            # シーン実行履歴テーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scene_executions (
                    execution_id TEXT PRIMARY KEY,
                    scene_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output_path TEXT,
                    error_message TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    performance_metrics TEXT,
                    FOREIGN KEY (scene_id) REFERENCES scenes(scene_id)
                )
            ''')

            conn.commit()

    async def _load_scenes(self):
        """シーンを読み込み"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM scenes')
            rows = cursor.fetchall()

            for row in rows:
                scene = MultiAvatarScene(
                    scene_id=row[0],
                    name=row[1],
                    description=row[2],
                    duration=row[3],
                    resolution=tuple(map(int, row[4].strip('()').split(','))),
                    background=row[5],
                    avatars=[AvatarInstance(**a) for a in json.loads(row[6])],
                    elements=[SceneElement(**e) for e in json.loads(row[7])],
                    script=json.loads(row[8]),
                    audio_tracks=json.loads(row[9]),
                    created_at=datetime.fromisoformat(row[10])
                )
                self.scenes[scene.scene_id] = scene

    async def create_scene(self, scene_config: Dict[str, Any]) -> str:
        """
        複数アバターシーンを作成

        Args:
            scene_config: シーン設定

        Returns:
            シーンID
        """
        scene_id = f"scene_{int(datetime.now().timestamp() * 1000)}"

        # アバターインスタンス作成
        avatars = []
        for avatar_config in scene_config.get('avatars', []):
            avatar = AvatarInstance(
                instance_id=f"avatar_{len(avatars)}_{scene_id}",
                avatar_id=avatar_config['avatar_id'],
                name=avatar_config.get('name', f"Avatar {len(avatars) + 1}"),
                position=tuple(avatar_config.get('position', (100, 100))),
                size=tuple(avatar_config.get('size', (300, 400))),
                z_index=avatar_config.get('z_index', 0),
                voice_settings=avatar_config.get('voice_settings', {})
            )
            avatars.append(avatar)

        # シーン要素作成
        elements = []
        for element_config in scene_config.get('elements', []):
            element = SceneElement(
                element_id=f"element_{len(elements)}_{scene_id}",
                element_type=element_config['type'],
                position=tuple(element_config.get('position', (0, 0))),
                size=tuple(element_config.get('size', (100, 100))),
                z_index=element_config.get('z_index', 0),
                properties=element_config.get('properties', {})
            )
            elements.append(element)

        # シーン作成
        scene = MultiAvatarScene(
            scene_id=scene_id,
            name=scene_config.get('name', f"Multi Avatar Scene {scene_id}"),
            description=scene_config.get('description', ''),
            duration=scene_config.get('duration', 30.0),
            resolution=tuple(scene_config.get('resolution', self.default_resolution)),
            background=scene_config.get('background'),
            avatars=avatars,
            elements=elements,
            script=scene_config.get('script', []),
            audio_tracks=scene_config.get('audio_tracks', [])
        )

        # 保存
        self.scenes[scene_id] = scene
        await self._save_scene(scene)

        logger.info(f"Created multi avatar scene: {scene_id}")
        return scene_id

    async def _save_scene(self, scene: MultiAvatarScene):
        """シーンを保存"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO scenes
                (scene_id, name, description, duration, resolution, background,
                 avatars, elements, script, audio_tracks, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                scene.scene_id,
                scene.name,
                scene.description,
                scene.duration,
                str(scene.resolution),
                scene.background,
                json.dumps([{
                    'instance_id': a.instance_id,
                    'avatar_id': a.avatar_id,
                    'name': a.name,
                    'position': a.position,
                    'size': a.size,
                    'z_index': a.z_index,
                    'voice_settings': a.voice_settings
                } for a in scene.avatars], ensure_ascii=False),
                json.dumps([{
                    'element_id': e.element_id,
                    'element_type': e.element_type,
                    'position': e.position,
                    'size': e.size,
                    'z_index': e.z_index,
                    'properties': e.properties
                } for e in scene.elements], ensure_ascii=False),
                json.dumps(scene.script, ensure_ascii=False),
                json.dumps(scene.audio_tracks, ensure_ascii=False),
                scene.created_at.isoformat()
            ))

            conn.commit()

    async def add_avatar_to_scene(self, scene_id: str, avatar_config: Dict[str, Any]) -> bool:
        """
        シーンにアバターを追加

        Args:
            scene_id: シーンID
            avatar_config: アバター設定

        Returns:
            追加成功かどうか
        """
        if scene_id not in self.scenes:
            return False

        scene = self.scenes[scene_id]

        # アバター数制限チェック
        if len(scene.avatars) >= self.max_avatars_per_scene:
            return False

        # アバター作成
        avatar = AvatarInstance(
            instance_id=f"avatar_{len(scene.avatars)}_{scene_id}",
            avatar_id=avatar_config['avatar_id'],
            name=avatar_config.get('name', f"Avatar {len(scene.avatars) + 1}"),
            position=tuple(avatar_config.get('position', (100 + len(scene.avatars) * 150, 100))),
            size=tuple(avatar_config.get('size', (300, 400))),
            z_index=avatar_config.get('z_index', len(scene.avatars)),
            voice_settings=avatar_config.get('voice_settings', {})
        )

        scene.avatars.append(avatar)
        await self._save_scene(scene)

        return True

    async def update_avatar_position(self, scene_id: str, avatar_instance_id: str,
                                   new_position: Tuple[int, int]) -> bool:
        """
        アバターの位置を更新

        Args:
            scene_id: シーンID
            avatar_instance_id: アバターインスタンスID
            new_position: 新しい位置

        Returns:
            更新成功かどうか
        """
        if scene_id not in self.scenes:
            return False

        scene = self.scenes[scene_id]

        for avatar in scene.avatars:
            if avatar.instance_id == avatar_instance_id:
                avatar.position = new_position
                await self._save_scene(scene)
                return True

        return False

    async def create_scene_timeline(self, scene_id: str) -> Optional[str]:
        """
        シーンのタイムラインを作成

        Args:
            scene_id: シーンID

        Returns:
            タイムラインID
        """
        if scene_id not in self.scenes:
            return None

        scene = self.scenes[scene_id]
        timeline_id = f"timeline_{scene_id}_{int(datetime.now().timestamp())}"

        # スクリプトからイベント生成
        events = []
        keyframes = []

        current_time = 0.0
        for script_item in scene.script:
            duration = script_item.get('duration', 3.0)
            avatar_id = script_item.get('avatar_id')
            action = script_item.get('action', 'speak')
            content = script_item.get('content', '')

            # イベント作成
            event = {
                'event_id': f"event_{len(events)}_{timeline_id}",
                'time': current_time,
                'duration': duration,
                'avatar_id': avatar_id,
                'action': action,
                'content': content,
                'properties': script_item.get('properties', {})
            }
            events.append(event)

            # キーフレーム作成
            keyframe = {
                'time': current_time,
                'avatar_positions': {
                    a.instance_id: {'position': a.position, 'animation': a.animation_state}
                    for a in scene.avatars
                },
                'element_states': {
                    e.element_id: {'position': e.position, 'properties': e.properties}
                    for e in scene.elements
                }
            }
            keyframes.append(keyframe)

            current_time += duration

        # タイムライン作成
        timeline = SceneTimeline(
            timeline_id=timeline_id,
            scene_id=scene_id,
            total_duration=current_time,
            events=events,
            keyframes=keyframes
        )

        self.active_scenes[timeline_id] = timeline

        # データベース保存
        await self._save_timeline(timeline)

        return timeline_id

    async def _save_timeline(self, timeline: SceneTimeline):
        """タイムラインを保存"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO timelines
                (timeline_id, scene_id, total_duration, events, keyframes)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                timeline.timeline_id,
                timeline.scene_id,
                timeline.total_duration,
                json.dumps(timeline.events, ensure_ascii=False),
                json.dumps(timeline.keyframes, ensure_ascii=False)
            ))

            conn.commit()

    async def render_scene(self, scene_id: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        シーンをレンダリング

        Args:
            scene_id: シーンID
            output_path: 出力パス

        Returns:
            出力ファイルパス
        """
        if scene_id not in self.scenes:
            return None

        scene = self.scenes[scene_id]

        # 出力パス設定
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"data/multi_avatar_scenes/scene_{scene_id}_{timestamp}.mp4"

        # 実行ID生成
        execution_id = f"exec_{scene_id}_{int(datetime.now().timestamp())}"

        try:
            # 実行開始記録
            await self._start_scene_execution(execution_id, scene_id)

            # シーン合成
            result_path = await self._compose_multi_avatar_scene(scene, output_path)

            # 実行完了記録
            await self._complete_scene_execution(execution_id, result_path)

            return result_path

        except Exception as e:
            logger.error(f"Scene rendering failed: {e}")
            await self._fail_scene_execution(execution_id, str(e))
            return None

    async def _compose_multi_avatar_scene(self, scene: MultiAvatarScene, output_path: str) -> str:
        """
        複数アバターシーンを合成

        Args:
            scene: シーン情報
            output_path: 出力パス

        Returns:
            出力ファイルパス
        """
        try:
            # タイムライン取得または作成
            timeline_id = None
            for tid, timeline in self.active_scenes.items():
                if timeline.scene_id == scene.scene_id:
                    timeline_id = tid
                    break

            if not timeline_id:
                timeline_id = await self.create_scene_timeline(scene.scene_id)

            if not timeline_id or timeline_id not in self.active_scenes:
                raise ValueError("Failed to create scene timeline")

            timeline = self.active_scenes[timeline_id]

            # アバター動画生成
            avatar_videos = await self._generate_avatar_videos(scene, timeline)

            # シーン合成
            final_video = await self._composite_scene_elements(scene, avatar_videos, timeline, output_path)

            return final_video

        except Exception as e:
            logger.error(f"Scene composition failed: {e}")
            raise

    async def _generate_avatar_videos(self, scene: MultiAvatarScene,
                                    timeline: SceneTimeline) -> Dict[str, str]:
        """
        アバターごとの動画を生成

        Args:
            scene: シーン情報
            timeline: タイムライン

        Returns:
            アバターID -> 動画パスのマッピング
        """
        avatar_videos = {}

        for avatar in scene.avatars:
            # このアバターのイベントを取得
            avatar_events = [e for e in timeline.events if e.get('avatar_id') == avatar.instance_id]

            if not avatar_events:
                continue

            # スクリプト作成
            script_parts = []
            for event in avatar_events:
                if event['action'] == 'speak':
                    script_parts.append(event['content'])

            script = ' '.join(script_parts)

            if script.strip():
                # 動画作成リクエスト
                request = {
                    'user_id': 'multi_avatar_system',
                    'script': script,
                    'avatar_style': avatar.avatar_id.split('_')[0] if '_' in avatar.avatar_id else 'professional',
                    'voice_settings': avatar.voice_settings,
                    'video_settings': {
                        'resolution': '1080p',
                        'fps': 30,
                        'background': 'transparent'  # 透明背景
                    }
                }

                # 動画生成（簡易実装）
                # 実際にはvideo_creatorを使用
                video_path = f"data/temp/avatar_{avatar.instance_id}_video.mp4"
                avatar_videos[avatar.instance_id] = video_path

        return avatar_videos

    async def _composite_scene_elements(self, scene: MultiAvatarScene,
                                      avatar_videos: Dict[str, str],
                                      timeline: SceneTimeline,
                                      output_path: str) -> str:
        """
        シーン要素を合成

        Args:
            scene: シーン情報
            avatar_videos: アバター動画
            timeline: タイムライン
            output_path: 出力パス

        Returns:
            最終動画パス
        """
        # 簡易的な合成実装
        # 実際にはMoviePyなどのライブラリを使用
        try:
            # 背景作成
            background_path = await self._create_scene_background(scene)

            # アバター配置
            composite_path = await self._arrange_avatars_in_scene(
                scene, avatar_videos, background_path, timeline, output_path
            )

            return composite_path

        except Exception as e:
            logger.error(f"Scene element composition failed: {e}")
            raise

    async def _create_scene_background(self, scene: MultiAvatarScene) -> str:
        """シーン背景を作成"""
        background_path = f"data/temp/scene_{scene.scene_id}_background.png"

        try:
            from PIL import Image, ImageDraw

            # 背景画像作成
            image = Image.new('RGB', scene.resolution, (255, 255, 255))
            draw = ImageDraw.Draw(image)

            # 背景色または画像
            if scene.background:
                # 背景画像読み込み（簡易実装）
                pass
            else:
                # デフォルト背景
                draw.rectangle([0, 0, scene.resolution[0], scene.resolution[1]],
                             fill=(240, 240, 240))

            image.save(background_path)
            return background_path

        except Exception as e:
            logger.error(f"Background creation failed: {e}")
            # デフォルト背景を返す
            return ""

    async def _arrange_avatars_in_scene(self, scene: MultiAvatarScene,
                                      avatar_videos: Dict[str, str],
                                      background_path: str,
                                      timeline: SceneTimeline,
                                      output_path: str) -> str:
        """
        シーン内にアバターを配置

        Args:
            scene: シーン情報
            avatar_videos: アバター動画
            background_path: 背景パス
            timeline: タイムライン
            output_path: 出力パス

        Returns:
            合成動画パス
        """
        # 簡易実装：最初のフレームのみ合成
        try:
            from PIL import Image

            # 背景読み込み
            if background_path and Path(background_path).exists():
                background = Image.open(background_path)
            else:
                background = Image.new('RGB', scene.resolution, (240, 240, 240))

            # アバター配置（最初のフレームのみ）
            for avatar in scene.avatars:
                if avatar.instance_id in avatar_videos:
                    # アバター画像の配置（簡易実装）
                    # 実際には各タイムラインでの位置を考慮
                    x, y = avatar.position
                    # アバター画像を配置
                    pass

            # シーン要素配置
            for element in scene.elements:
                # 要素配置（テキスト、プロップなど）
                pass

            # 静止画像として保存（動画としては不完全）
            background.save(output_path.replace('.mp4', '_frame.png'))

            # ダミーの動画パスを返す
            return output_path

        except Exception as e:
            logger.error(f"Avatar arrangement failed: {e}")
            raise

    async def _start_scene_execution(self, execution_id: str, scene_id: str):
        """シーン実行を開始"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO scene_executions
                (execution_id, scene_id, status, started_at)
                VALUES (?, ?, ?, ?)
            ''', (
                execution_id,
                scene_id,
                'running',
                datetime.now().isoformat()
            ))

            conn.commit()

    async def _complete_scene_execution(self, execution_id: str, output_path: str):
        """シーン実行を完了"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE scene_executions
                SET status = ?, output_path = ?, completed_at = ?
                WHERE execution_id = ?
            ''', (
                'completed',
                output_path,
                datetime.now().isoformat(),
                execution_id
            ))

            conn.commit()

    async def _fail_scene_execution(self, execution_id: str, error_message: str):
        """シーン実行を失敗"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE scene_executions
                SET status = ?, error_message = ?, completed_at = ?
                WHERE execution_id = ?
            ''', (
                'failed',
                error_message,
                datetime.now().isoformat(),
                execution_id
            ))

            conn.commit()

    def get_scene(self, scene_id: str) -> Optional[MultiAvatarScene]:
        """シーンを取得"""
        return self.scenes.get(scene_id)

    def list_scenes(self) -> List[Dict[str, Any]]:
        """シーン一覧を取得"""
        return [{
            'scene_id': scene.scene_id,
            'name': scene.name,
            'description': scene.description,
            'duration': scene.duration,
            'avatar_count': len(scene.avatars),
            'created_at': scene.created_at.isoformat()
        } for scene in self.scenes.values()]

    async def delete_scene(self, scene_id: str) -> bool:
        """シーンを削除"""
        if scene_id not in self.scenes:
            return False

        # データベースから削除
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('DELETE FROM scenes WHERE scene_id = ?', (scene_id,))
            cursor.execute('DELETE FROM timelines WHERE scene_id = ?', (scene_id,))
            cursor.execute('DELETE FROM scene_executions WHERE scene_id = ?', (scene_id,))

            conn.commit()

        # メモリから削除
        del self.scenes[scene_id]

        # アクティブなタイムライン削除
        timelines_to_remove = [tid for tid, t in self.active_scenes.items() if t.scene_id == scene_id]
        for tid in timelines_to_remove:
            del self.active_scenes[tid]

        logger.info(f"Deleted scene: {scene_id}")
        return True

# グローバルインスタンス管理
_multi_avatar_manager = None

async def get_multi_avatar_manager() -> MultiAvatarManager:
    """複数アバター管理システムのインスタンスを取得"""
    global _multi_avatar_manager

    if _multi_avatar_manager is None:
        _multi_avatar_manager = MultiAvatarManager()
        await _multi_avatar_manager.initialize()

    return _multi_avatar_manager
