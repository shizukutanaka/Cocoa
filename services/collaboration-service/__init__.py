"""
Collaboration Service
リアルタイムコラボレーション機能を提供（WebSocket + WebRTCベース）
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
import uvicorn
from contextlib import asynccontextmanager

# WebRTC関連インポート
try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel, RTCConfiguration, RTCIceServer
    from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False

from services.shared.config import get_config, ConfigManager
from services.shared.models import CollaborationSession, CollaborationParticipant, CollaborationMessage, User
from services.shared.database import DatabaseManager, get_db

logger = logging.getLogger(__name__)
from services.shared.logger import setup_logging


# グローバル変数
app: Optional[FastAPI] = None
active_connections: Dict[str, List[WebSocket]] = {}  # session_id -> connections
active_webrtc_connections: Dict[str, Dict[str, RTCPeerConnection]] = {}  # session_id -> user_id -> peer_connection
webrtc_data_channels: Dict[str, Dict[str, RTCDataChannel]] = {}  # session_id -> user_id -> data_channel


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションライフサイクル管理"""
    # スタートアップ
    setup_logging()
    logger = logging.getLogger(__name__)

    # データベース初期化
    db_manager = DatabaseManager()
    await db_manager.initialize()

    logger.info("Collaboration Service started")

    yield

    # シャットダウン
    await db_manager.close()

    # WebSocket接続を閉じる
    for connections in active_connections.values():
        for connection in connections:
            try:
                await connection.close()
            except Exception:
                pass

    # WebRTC接続を閉じる
    if WEBRTC_AVAILABLE:
        for session_connections in active_webrtc_connections.values():
            for peer_connection in session_connections.values():
                try:
                    await peer_connection.close()
                except Exception:
                    pass

    logger.info("Collaboration Service stopped")


def create_app() -> FastAPI:
    """FastAPIアプリケーション作成"""
    global app

    config = get_config()

    app_settings = {
        "title": "Cocoa Collaboration Service",
        "description": "リアルタイムコラボレーションサービス",
        "version": "2.1.0",
        "debug": config.services["collaboration-service"].debug
    }

    app = FastAPI(**app_settings, lifespan=lifespan)
    return app


def get_app() -> FastAPI:
    """アプリケーション取得"""
    global app
    if app is None:
        app = create_app()
    return app


# データベース依存関係
async def get_database():
    """データベースセッション取得"""
    db_manager = DatabaseManager()
    session = await db_manager.get_session()
    try:
        yield session
    finally:
        await session.close()


class ConnectionManager:
    """WebSocket接続マネージャー"""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        """接続を追加"""
        await websocket.accept()

        if session_id not in self.active_connections:
            self.active_connections[session_id] = []

        self.active_connections[session_id].append(websocket)

        # セッションデータを送信
        await self.send_session_data(websocket, session_id)

    def disconnect(self, session_id: str, websocket: WebSocket):
        """接続を削除"""
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)

            # セッションの全接続が切れたら削除
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """個人メッセージを送信"""
        try:
            await websocket.send_text(message)
        except Exception:
            pass

    async def broadcast_to_session(self, session_id: str, message: str, exclude: Optional[WebSocket] = None):
        """セッション内の全ユーザーにブロードキャスト"""
        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                if connection != exclude:
                    try:
                        await connection.send_text(message)
                    except Exception:
                        # 切断された接続は削除
                        self.disconnect(session_id, connection)

    async def send_session_data(self, websocket: WebSocket, session_id: str):
        """セッションデータを送信"""
        # 実際の実装ではデータベースからセッション情報を取得
        session_data = {
            "type": "session_info",
            "session_id": session_id,
            "participants": await self.get_session_participants(session_id),
            "messages": await self.get_recent_messages(session_id, limit=50)
        }

        await self.send_personal_message(json.dumps(session_data), websocket)

    async def get_session_participants(self, session_id: str) -> List[Dict[str, Any]]:
        """セッション参加者を取得"""
        # 実際の実装ではデータベースから取得
        return [
            {"id": "user_1", "username": "user1", "role": "owner"},
            {"id": "user_2", "username": "user2", "role": "participant"}
        ]

    async def get_recent_messages(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """最近のメッセージを取得"""
        # 実際の実装ではデータベースから取得
        return [
            {
                "id": "msg_1",
                "user_id": "user_1",
                "username": "user1",
                "content": "こんにちは！",
                "timestamp": datetime.utcnow().isoformat(),
                "type": "text"
            }
        ]


# グローバル接続マネージャー
manager = ConnectionManager()


# WebSocketエンドポイント
@app.websocket("/ws/collaboration/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = None,  # 認証トークン（クエリパラメータ）
    db = Depends(get_database)
):
    """コラボレーションWebSocketエンドポイント"""
    try:
        # 認証チェック（簡易的に）
        if token != "valid_token":  # 本来はJWT検証
            await websocket.close(code=4001, reason="認証エラー")
            return

        # セッション存在確認
        session = await db.query(CollaborationSession).filter(
            CollaborationSession.id == session_id,
            CollaborationSession.is_active.is_(True)
        ).first()

        if not session:
            await websocket.close(code=4002, reason="セッションが見つかりません")
            return

        # 接続を追加
        await manager.connect(session_id, websocket)

        try:
            while True:
                # メッセージ受信
                data = await websocket.receive_text()
                message_data = json.loads(data)

                # メッセージ処理
                await handle_collaboration_message(
                    session_id, message_data, websocket, db
                )

        except WebSocketDisconnect:
            manager.disconnect(session_id, websocket)
        except json.JSONDecodeError:
            await manager.send_personal_message(
                json.dumps({"error": "無効なJSON形式です"}),
                websocket
            )
        except Exception as e:
            logging.error(f"WebSocketエラー: {e}")
            await manager.send_personal_message(
                json.dumps({"error": "サーバーエラー"}),
                websocket
            )

    except Exception as e:
        logging.error(f"WebSocket接続エラー: {e}")
        try:
            await websocket.close(code=1011, reason="サーバーエラー")
        except Exception:
            pass


async def handle_collaboration_message(
    session_id: str,
    message_data: Dict[str, Any],
    websocket: WebSocket,
    db
):
    """コラボレーションメッセージを処理"""
    message_type = message_data.get("type")

    if message_type == "chat":
        # チャットメッセージ
        await handle_chat_message(session_id, message_data, websocket, db)

    elif message_type == "avatar_edit":
        # アバター編集メッセージ
        await handle_avatar_edit_message(session_id, message_data, websocket, db)

    elif message_type == "cursor_move":
        # カーソル移動メッセージ
        await handle_cursor_move_message(session_id, message_data, websocket)

    elif message_type == "ping":
        # ピンポン
        await manager.send_personal_message(json.dumps({"type": "pong"}), websocket)

    else:
        # 不明なメッセージタイプ
        await manager.send_personal_message(
            json.dumps({"error": "不明なメッセージタイプです"}),
            websocket
        )


async def handle_chat_message(session_id: str, message_data: Dict[str, Any], websocket: WebSocket, db):
    """チャットメッセージを処理"""
    # データベースにメッセージを保存
    message = CollaborationMessage(
        session_id=session_id,
        user_id=message_data.get("user_id", "anonymous"),
        message_type="text",
        content=message_data.get("content", ""),
        created_at=datetime.utcnow()
    )

    db.add(message)
    await db.commit()

    # セッション内の全ユーザーにブロードキャスト
    broadcast_data = {
        "type": "chat",
        "message": {
            "id": str(message.id),
            "user_id": message.user_id,
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
            "username": message_data.get("username", "匿名ユーザー")
        }
    }

    await manager.broadcast_to_session(
        session_id,
        json.dumps(broadcast_data),
        exclude=websocket
    )


async def handle_avatar_edit_message(session_id: str, message_data: Dict[str, Any], websocket: WebSocket, db):
    """アバター編集メッセージを処理"""
    # アバター変更をデータベースに記録
    edit_data = {
        "type": "avatar_edit",
        "edit": message_data,
        "timestamp": datetime.utcnow().isoformat()
    }

    # セッション内の全ユーザーにブロードキャスト（編集者以外）
    await manager.broadcast_to_session(
        session_id,
        json.dumps(edit_data),
        exclude=websocket
    )


async def handle_cursor_move_message(session_id: str, message_data: Dict[str, Any], websocket: WebSocket):
    """カーソル移動メッセージを処理"""
    # カーソル位置をセッション内の全ユーザーにブロードキャスト
    cursor_data = {
        "type": "cursor_move",
        "cursor": message_data,
        "timestamp": datetime.utcnow().isoformat()
    }

    await manager.broadcast_to_session(
        session_id,
        json.dumps(cursor_data),
        exclude=websocket
    )


# REST APIエンドポイント
@app.post("/api/v1/collaboration/sessions")
async def create_collaboration_session(
    session_data: dict,
    current_user: Dict[str, Any] = Depends(lambda: {"id": "user_123"}),
    db = Depends(get_database)
):
    """新しいコラボレーションセッションを作成"""
    try:
        session = CollaborationSession(
            name=session_data["name"],
            description=session_data.get("description"),
            avatar_id=session_data["avatar_id"],
            user_id=current_user["id"],
            session_type=session_data.get("session_type", "editing"),
            settings=session_data.get("settings", {}),
            max_participants=session_data.get("max_participants", 10)
        )

        db.add(session)
        await db.commit()
        await db.refresh(session)

        # オーナーとして参加者を追加
        participant = CollaborationParticipant(
            session_id=session.id,
            user_id=current_user["id"],
            role="owner"
        )

        db.add(participant)
        await db.commit()

        return {
            "success": True,
            "session": session.to_dict(),
            "message": "コラボレーションセッションが作成されました"
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"セッション作成エラー: {str(e)}")


@app.get("/api/v1/collaboration/sessions")
async def list_collaboration_sessions(
    avatar_id: Optional[str] = None,
    user_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: Dict[str, Any] = Depends(lambda: {"id": "user_123"}),
    db = Depends(get_database)
):
    """コラボレーションセッション一覧を取得"""
    try:
        query = db.query(CollaborationSession)

        if avatar_id:
            query = query.filter(CollaborationSession.avatar_id == avatar_id)

        if user_id:
            query = query.filter(CollaborationSession.user_id == user_id)

        if is_active is not None:
            query = query.filter(CollaborationSession.is_active == is_active)

        sessions = await query.all()

        return {
            "sessions": [session.to_dict() for session in sessions]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"セッション一覧取得エラー: {str(e)}")


@app.post("/api/v1/collaboration/sessions/{session_id}/join")
async def join_collaboration_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(lambda: {"id": "user_123"}),
    db = Depends(get_database)
):
    """コラボレーションセッションに参加"""
    try:
        # セッション存在確認
        session = await db.query(CollaborationSession).filter(
            CollaborationSession.id == session_id,
            CollaborationSession.is_active.is_(True)
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="セッションが見つかりません")

        # 既に参加していないか確認
        existing_participant = await db.query(CollaborationParticipant).filter(
            CollaborationParticipant.session_id == session_id,
            CollaborationParticipant.user_id == current_user["id"]
        ).first()

        if existing_participant:
            return {
                "success": True,
                "message": "既にセッションに参加しています",
                "role": existing_participant.role
            }

        # 参加者を追加
        participant = CollaborationParticipant(
            session_id=session_id,
            user_id=current_user["id"],
            role="participant"
        )

        db.add(participant)
        await db.commit()

        # 現在の参加者数を更新
        session.current_participants += 1
        await db.commit()

        return {
            "success": True,
            "message": "セッションに参加しました",
            "role": "participant"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"セッション参加エラー: {str(e)}")


@app.post("/api/v1/collaboration/sessions/{session_id}/leave")
async def leave_collaboration_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(lambda: {"id": "user_123"}),
    db = Depends(get_database)
):
    """コラボレーションセッションから退出"""
    try:
        # 参加者情報を取得・削除
        participant = await db.query(CollaborationParticipant).filter(
            CollaborationParticipant.session_id == session_id,
            CollaborationParticipant.user_id == current_user["id"]
        ).first()

        if not participant:
            raise HTTPException(status_code=404, detail="セッションに参加していません")

        await db.delete(participant)

        # 現在の参加者数を更新
        session = await db.query(CollaborationSession).filter(
            CollaborationSession.id == session_id
        ).first()

        if session:
            session.current_participants = max(0, session.current_participants - 1)
            await db.commit()

        return {
            "success": True,
            "message": "セッションから退出しました"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"セッション退出エラー: {str(e)}")


# WebRTC関連関数
async def create_webrtc_connection(session_id: str, user_id: str) -> RTCPeerConnection:
    """WebRTCピア接続を作成"""
    if not WEBRTC_AVAILABLE:
        raise HTTPException(status_code=500, detail="WebRTC機能が利用できません")

    config = RTCConfiguration(
        iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")]
    )

    pc = RTCPeerConnection(configuration=config)

    # データチャネルの作成
    data_channel = pc.createDataChannel("collaboration")

    # データチャネルのイベントハンドラー
    @data_channel.on("open")
    def on_open():
        logger.info(f"データチャネルが開きました: {user_id}")

    @data_channel.on("message")
    def on_message(message):
        logger.info(f"データチャネルメッセージ受信: {user_id} - {message}")

    # ピア接続のイベントハンドラー
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info(f"接続状態変更: {user_id} - {pc.connectionState}")

        if pc.connectionState == "failed":
            await pc.close()

    # 接続を保存
    if session_id not in active_webrtc_connections:
        active_webrtc_connections[session_id] = {}

    active_webrtc_connections[session_id][user_id] = pc

    if session_id not in webrtc_data_channels:
        webrtc_data_channels[session_id] = {}

    webrtc_data_channels[session_id][user_id] = data_channel

    return pc


async def handle_webrtc_offer(session_id: str, user_id: str, offer: Dict[str, Any]) -> Dict[str, Any]:
    """WebRTCオファーを処理"""
    if not WEBRTC_AVAILABLE:
        return {"error": "WebRTC機能が利用できません"}

    try:
        pc = await create_webrtc_connection(session_id, user_id)

        # オファーを設定
        await pc.setRemoteDescription(RTCSessionDescription(**offer))

        # アンサーを生成
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return {
            "type": pc.localDescription.type,
            "sdp": pc.localDescription.sdp
        }

    except Exception as e:
        logger.error(f"WebRTCオファー処理エラー: {e}")
        return {"error": str(e)}


async def handle_webrtc_ice_candidate(session_id: str, user_id: str, candidate: Dict[str, Any]):
    """WebRTC ICE候補を処理"""
    if not WEBRTC_AVAILABLE:
        return

    try:
        if session_id in active_webrtc_connections and user_id in active_webrtc_connections[session_id]:
            pc = active_webrtc_connections[session_id][user_id]
            await pc.addIceCandidate(candidate)
    except Exception as e:
        logger.error(f"ICE候補処理エラー: {e}")


# WebRTCエンドポイント
@app.post("/api/v1/collaboration/webrtc/offer")
async def webrtc_offer(
    request: Request,
    current_user: Dict[str, Any] = Depends(lambda: {"id": "user_123"}),
    db = Depends(get_database)
):
    """WebRTCオファーを処理"""
    try:
        data = await request.json()
        session_id = data.get("session_id")
        offer = data.get("offer")

        if not session_id or not offer:
            raise HTTPException(status_code=400, detail="セッションIDとオファーが必要です")

        answer = await handle_webrtc_offer(session_id, current_user["id"], offer)

        return {
            "success": True,
            "answer": answer
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"WebRTCオファー処理エラー: {str(e)}")


@app.post("/api/v1/collaboration/webrtc/ice-candidate")
async def webrtc_ice_candidate(
    request: Request,
    current_user: Dict[str, Any] = Depends(lambda: {"id": "user_123"}),
    db = Depends(get_database)
):
    """WebRTC ICE候補を処理"""
    try:
        data = await request.json()
        session_id = data.get("session_id")
        candidate = data.get("candidate")

        if not session_id or not candidate:
            raise HTTPException(status_code=400, detail="セッションIDと候補が必要です")

        await handle_webrtc_ice_candidate(session_id, current_user["id"], candidate)

        return {"success": True}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ICE候補処理エラー: {str(e)}")


# ヘルスチェック
@app.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {
        "status": "healthy",
        "service": "collaboration-service",
        "webrtc_available": WEBRTC_AVAILABLE,
        "active_webrtc_connections": sum(len(conns) for conns in active_webrtc_connections.values())
    }


def main():
    """メイン関数"""
    config = get_config()
    service_config = config.services["collaboration-service"]

    uvicorn.run(
        "services.collaboration_service:app",
        host=service_config.host,
        port=service_config.port,
        reload=service_config.debug,
        log_level="info"
    )


if __name__ == "__main__":
    main()
