# main/interactive_avatar.py
"""
Interactive Avatar Module for Cocoa
リアルタイムアバター交信システム
"""

import asyncio
import logging
import json
import websockets
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
import queue

from ai_avatar_generator import get_ai_avatar_generator, AvatarGenerationRequest
from integrated_security import get_security_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class InteractionMessage:
    """交信メッセージ"""
    message_id: str
    user_id: str
    message_type: str  # 'text', 'command', 'emotion'
    content: str
    timestamp: datetime
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class AvatarResponse:
    """アバター応答"""
    response_id: str
    avatar_id: str
    response_type: str  # 'text', 'animation', 'emotion'
    content: str
    emotion: str = "neutral"
    animation_data: Dict = None
    audio_data: Optional[bytes] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.animation_data is None:
            self.animation_data = {}
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

class InteractiveAvatar:
    """
    インタラクティブアバター
    リアルタイムでのアバター交信を実現
    """

    def __init__(self, avatar_id: str, style: str = "professional"):
        self.avatar_id = avatar_id
        self.style = style
        self.security_manager = get_security_manager()
        self.avatar_generator = None

        # 接続管理
        self.connected_clients: Dict[str, Dict] = {}
        self.message_queue = queue.Queue()
        self.response_queue = queue.Queue()

        # アバターステータス
        self.is_active = False
        self.current_emotion = "neutral"
        self.conversation_history: List[Dict] = []

        # WebSocketサーバー
        self.websocket_server = None
        self.server_thread = None

        logger.info(f"Interactive Avatar {avatar_id} initialized")

    async def initialize(self):
        """初期化"""
        if not self.avatar_generator:
            self.avatar_generator = await get_ai_avatar_generator()

        # アバター画像の準備
        await self._prepare_avatar_image()

    async def _prepare_avatar_image(self):
        """アバター画像を準備"""
        try:
            # デフォルトのアバター画像を生成または取得
            request = AvatarGenerationRequest(
                user_id="system",
                prompt=f"default interactive avatar in {self.style} style",
                style=self.style,
                quality="high"
            )

            result = await self.avatar_generator.generate_avatar(request)
            if result.success:
                self.avatar_image_path = result.avatar_path
            else:
                logger.warning("Failed to generate avatar image, using default")
                self.avatar_image_path = None

        except Exception as e:
            logger.error(f"Avatar image preparation failed: {e}")
            self.avatar_image_path = None

    async def start_server(self, host: str = "localhost", port: int = 8765):
        """WebSocketサーバーを開始"""
        try:
            self.websocket_server = await websockets.serve(
                self._handle_connection,
                host,
                port
            )

            self.is_active = True
            logger.info(f"Interactive Avatar server started on {host}:{port}")

            # メッセージ処理ループを開始
            asyncio.create_task(self._process_messages())

            return True

        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False

    async def stop_server(self):
        """サーバーを停止"""
        self.is_active = False

        if self.websocket_server:
            self.websocket_server.close()
            await self.websocket_server.wait_closed()

        logger.info("Interactive Avatar server stopped")

    async def _handle_connection(self, websocket, path):
        """WebSocket接続を処理"""
        client_id = f"client_{len(self.connected_clients)}"

        try:
            # クライアント登録
            self.connected_clients[client_id] = {
                "websocket": websocket,
                "connected_at": datetime.now(timezone.utc),
                "last_activity": datetime.now(timezone.utc)
            }

            logger.info(f"Client {client_id} connected")

            # ウェルカムメッセージ送信
            welcome_msg = {
                "type": "welcome",
                "avatar_id": self.avatar_id,
                "style": self.style,
                "emotion": self.current_emotion,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await websocket.send(json.dumps(welcome_msg))

            # メッセージ受信ループ
            async for message in websocket:
                try:
                    data = json.loads(message)
                    interaction = InteractionMessage(
                        message_id=f"msg_{datetime.now(timezone.utc).timestamp()}",
                        user_id=client_id,
                        message_type=data.get("type", "text"),
                        content=data.get("content", ""),
                        timestamp=datetime.now(timezone.utc),
                        metadata=data.get("metadata", {})
                    )

                    # メッセージをキューに追加
                    self.message_queue.put(interaction)

                    # 最終アクティビティ更新
                    self.connected_clients[client_id]["last_activity"] = datetime.now(timezone.utc)

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received from {client_id}")
                except Exception as e:
                    logger.error(f"Error processing message from {client_id}: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {client_id} disconnected")
        finally:
            # クライアント削除
            if client_id in self.connected_clients:
                del self.connected_clients[client_id]

    async def _process_messages(self):
        """メッセージを処理"""
        while self.is_active:
            try:
                # メッセージを取得（タイムアウト付き）
                if not self.message_queue.empty():
                    message = self.message_queue.get_nowait()

                    # 応答生成
                    response = await self._generate_response(message)

                    # 会話履歴に追加
                    self._add_to_history(message, response)

                    # 応答を送信
                    await self._send_response(message.user_id, response)

                # 定期的なクリーンアップ
                await self._cleanup_inactive_clients()

                # 少し待機
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error processing messages: {e}")
                await asyncio.sleep(1)

    async def _generate_response(self, message: InteractionMessage) -> AvatarResponse:
        """メッセージに対する応答を生成"""
        try:
            response_id = f"resp_{datetime.now(timezone.utc).timestamp()}"

            if message.message_type == "text":
                # テキストメッセージの処理
                response_text = await self._generate_text_response(message.content)

                # 感情分析
                emotion = self._analyze_emotion(message.content)

                return AvatarResponse(
                    response_id=response_id,
                    avatar_id=self.avatar_id,
                    response_type="text",
                    content=response_text,
                    emotion=emotion
                )

            elif message.message_type == "command":
                # コマンドの処理
                return await self._handle_command(message)

            elif message.message_type == "emotion":
                # 感情表現の処理
                self.current_emotion = message.content
                return AvatarResponse(
                    response_id=response_id,
                    avatar_id=self.avatar_id,
                    response_type="emotion",
                    content=f"感情を {message.content} に変更しました",
                    emotion=message.content
                )

            else:
                return AvatarResponse(
                    response_id=response_id,
                    avatar_id=self.avatar_id,
                    response_type="text",
                    content="申し訳ありませんが、そのタイプのメッセージは理解できません。",
                    emotion="confused"
                )

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return AvatarResponse(
                response_id=f"error_{datetime.now(timezone.utc).timestamp()}",
                avatar_id=self.avatar_id,
                response_type="text",
                content="申し訳ありません、エラーが発生しました。",
                emotion="sad"
            )

    async def _generate_text_response(self, user_message: str) -> str:
        """テキスト応答を生成"""
        # シンプルな応答ロジック（実際にはNLPモデルを使用）
        responses = {
            "こんにちは": "こんにちは！お会いできて嬉しいです。",
            "ありがとう": "どういたしまして！",
            "元気": "はい、元気です！あなたはどうですか？",
            "default": "それは興味深いですね。もっと詳しく教えてください。"
        }

        # キーワードマッチング
        for keyword, response in responses.items():
            if keyword in user_message and keyword != "default":
                return response

        return responses["default"]

    def _analyze_emotion(self, text: str) -> str:
        """テキストから感情を分析"""
        # シンプルな感情分析（実際には感情分析モデルを使用）
        positive_words = ["嬉しい", "楽しい", "好き", "良い", "素晴らしい", "ありがとう"]
        negative_words = ["悲しい", "辛い", "嫌い", "悪い", "大変", "ごめん"]

        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)

        if positive_count > negative_count:
            return "happy"
        elif negative_count > positive_count:
            return "sad"
        else:
            return "neutral"

    async def _handle_command(self, message: InteractionMessage) -> AvatarResponse:
        """コマンドを処理"""
        command = message.content.lower()

        if command == "status":
            return AvatarResponse(
                response_id=f"cmd_{datetime.now(timezone.utc).timestamp()}",
                avatar_id=self.avatar_id,
                response_type="text",
                content=f"現在のステータス: アクティブ, 感情: {self.current_emotion}, 接続クライアント数: {len(self.connected_clients)}",
                emotion="neutral"
            )

        elif command == "emotion":
            available_emotions = ["happy", "sad", "angry", "surprised", "neutral"]
            return AvatarResponse(
                response_id=f"cmd_{datetime.now(timezone.utc).timestamp()}",
                avatar_id=self.avatar_id,
                response_type="text",
                content=f"利用可能な感情: {', '.join(available_emotions)}",
                emotion="neutral"
            )

        elif command.startswith("set_emotion "):
            new_emotion = command.split(" ", 1)[1]
            if new_emotion in ["happy", "sad", "angry", "surprised", "neutral"]:
                self.current_emotion = new_emotion
                return AvatarResponse(
                    response_id=f"cmd_{datetime.now(timezone.utc).timestamp()}",
                    avatar_id=self.avatar_id,
                    response_type="text",
                    content=f"感情を {new_emotion} に変更しました",
                    emotion=new_emotion
                )
            else:
                return AvatarResponse(
                    response_id=f"cmd_{datetime.now(timezone.utc).timestamp()}",
                    avatar_id=self.avatar_id,
                    response_type="text",
                    content="無効な感情です",
                    emotion="confused"
                )

        else:
            return AvatarResponse(
                response_id=f"cmd_{datetime.now(timezone.utc).timestamp()}",
                avatar_id=self.avatar_id,
                response_type="text",
                content="不明なコマンドです。'status', 'emotion', 'set_emotion [感情]' が利用可能です。",
                emotion="confused"
            )

    def _add_to_history(self, message: InteractionMessage, response: AvatarResponse):
        """会話履歴に追加"""
        history_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_message": {
                "type": message.message_type,
                "content": message.content,
                "user_id": message.user_id
            },
            "avatar_response": {
                "type": response.response_type,
                "content": response.content,
                "emotion": response.emotion
            }
        }

        self.conversation_history.append(history_entry)

        # 履歴を制限（最新100件）
        if len(self.conversation_history) > 100:
            self.conversation_history = self.conversation_history[-100:]

    async def _send_response(self, client_id: str, response: AvatarResponse):
        """クライアントに応答を送信"""
        if client_id not in self.connected_clients:
            return

        try:
            websocket = self.connected_clients[client_id]["websocket"]

            response_data = {
                "type": "response",
                "response_id": response.response_id,
                "avatar_id": response.avatar_id,
                "response_type": response.response_type,
                "content": response.content,
                "emotion": response.emotion,
                "timestamp": response.timestamp.isoformat()
            }

            # アニメーションデータがある場合
            if response.animation_data:
                response_data["animation"] = response.animation_data

            await websocket.send(json.dumps(response_data, ensure_ascii=False))

        except Exception as e:
            logger.error(f"Failed to send response to {client_id}: {e}")

    async def _cleanup_inactive_clients(self):
        """非アクティブなクライアントをクリーンアップ"""
        current_time = datetime.now(timezone.utc)
        inactive_clients = []

        for client_id, client_info in self.connected_clients.items():
            last_activity = client_info["last_activity"]
            if (current_time - last_activity).seconds > 300:  # 5分以上非アクティブ
                inactive_clients.append(client_id)

        for client_id in inactive_clients:
            logger.info(f"Removing inactive client: {client_id}")
            del self.connected_clients[client_id]

    def get_status(self) -> Dict:
        """アバターのステータスを取得"""
        return {
            "avatar_id": self.avatar_id,
            "style": self.style,
            "is_active": self.is_active,
            "current_emotion": self.current_emotion,
            "connected_clients": len(self.connected_clients),
            "conversation_count": len(self.conversation_history),
            "avatar_image_path": self.avatar_image_path
        }

    def get_conversation_history(self, limit: int = 50) -> List[Dict]:
        """会話履歴を取得"""
        return self.conversation_history[-limit:]

# グローバルインスタンス管理
_interactive_avatars: Dict[str, InteractiveAvatar] = {}

async def create_interactive_avatar(avatar_id: str, style: str = "professional") -> InteractiveAvatar:
    """インタラクティブアバターを作成"""
    if avatar_id in _interactive_avatars:
        return _interactive_avatars[avatar_id]

    avatar = InteractiveAvatar(avatar_id, style)
    await avatar.initialize()
    _interactive_avatars[avatar_id] = avatar

    return avatar

async def get_interactive_avatar(avatar_id: str) -> Optional[InteractiveAvatar]:
    """インタラクティブアバターを取得"""
    return _interactive_avatars.get(avatar_id)

def list_interactive_avatars() -> List[str]:
    """利用可能なインタラクティブアバター一覧を取得"""
    return list(_interactive_avatars.keys())
