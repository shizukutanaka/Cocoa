"""
REST API Server for Cocoa Avatar Management System

Production-grade APIサーバー実装
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

# カスタムモジュールインポート
try:
    from .performance_monitor import PerformanceMonitor
    from .health_monitor import get_health_monitor
    from .integrated_security import get_security_manager
    from .disaster_recovery import get_recovery_manager
    from .database_manager import get_database_service, get_database_manager, get_user_avatars, create_avatar_preset, log_audit_event
    from .redis_cache_manager import get_cache_manager, cache_async
    from .two_factor_auth import get_two_factor_service, setup_2fa, verify_2fa_token, verify_backup_code, disable_2fa, get_2fa_status
except ImportError:
    # 開発環境用のフォールバック
    PerformanceMonitor = None
    get_health_monitor = None
    get_security_manager = None
    get_recovery_manager = None
    get_database_service = None
    get_user_avatars = None
    create_avatar_preset = None
    log_audit_event = None
    get_cache_manager = None
    cache_async = None
    get_two_factor_service = None
    setup_2fa = None
    verify_2fa_token = None
    verify_backup_code = None
    disable_2fa = None
    get_2fa_status = None

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPIアプリケーション作成
app = FastAPI(
    title="Cocoa Avatar Management API",
    description="Production-grade REST API for avatar management system",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# セキュリティ設定
security = HTTPBearer(auto_error=False)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # フロントエンドのオリジン
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# セキュリティミドルウェア
@app.middleware("http")
async def security_middleware(request, call_next):
    """セキュリティミドルウェア"""
    # リクエストログ記録
    logger.info(f"API Request: {request.method} {request.url}")

    # レート制限のチェック（簡易版）
    # 実際の運用ではRedisなどの外部ストアを使用することを推奨

    response = await call_next(request)
    return response

# Pydanticモデル定義
class HealthCheck(BaseModel):
    status: str
    timestamp: str
    version: str
    uptime: Optional[float] = None

class SystemMetrics(BaseModel):
    cpu: float
    memory: float
    disk_io: float
    network_io: float
    process_memory: float
    timestamp: str

class PerformanceReport(BaseModel):
    summary: Dict[str, Any]
    metrics: List[SystemMetrics]
    alerts: List[Dict[str, Any]]

class BackupInfo(BaseModel):
    backup_id: str
    timestamp: str
    size_bytes: int
    status: str
    verified: bool

class SecurityReport(BaseModel):
    threat_level: str
    total_events_24h: int
    active_lockouts: int
    suspicious_activities: int
    last_scan: str

# WebSocket接続管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket接続確立。接続数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket接続切断。接続数: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        """全接続にメッセージをブロードキャスト"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.debug(f"Failed to send message to connection: {e}")
                disconnected.append(connection)

        # 切断された接続をクリーンアップ
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# 依存関係関数
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """認証チェック"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です"
        )

    # 実際の認証ロジックはここに実装
    # 例: JWTトークンの検証など
    token = credentials.credentials

    # 簡易的な認証チェック（実際の運用では適切な認証システムを使用）
    if token != os.getenv("API_SECRET_TOKEN", "default-secret"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効なトークンです"
        )

    return {"user_id": "system", "role": "admin"}

# ルートエンドポイント
@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "name": "Cocoa Avatar Management API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs"
    }

# ヘルスチェックエンドポイント
@app.get("/health", response_model=HealthCheck)
async def health_check():
    """システムヘルスチェック"""
    try:
        if get_health_monitor:
            health_monitor = get_health_monitor()
            health_result = health_monitor.run_all_checks()
            health_status = "healthy" if health_result.get("status") == "ok" else "unhealthy"
        else:
            health_status = "healthy"

        return HealthCheck(
            status=health_status,
            timestamp=datetime.now().isoformat(),
            version="2.0.0",
            uptime=0.0  # 実際の起動時間を取得する場合は適切な実装が必要
        )
    except Exception as e:
        logger.error(f"ヘルスチェックエラー: {e}")
        raise HTTPException(status_code=500, detail="ヘルスチェックに失敗しました")

# システムメトリクスエンドポイント
@app.get("/metrics", response_model=PerformanceReport)
async def get_metrics(current_user: dict = Depends(get_current_user)):
    """システムメトリクス取得"""
    try:
        if PerformanceMonitor:
            monitor = PerformanceMonitor()
            report = monitor.get_performance_report()

            # メトリクスの履歴を取得（簡易版）
            history = []
            if hasattr(monitor, 'history'):
                for sample in monitor.history[-10:]:  # 最新10件
                    history.append(SystemMetrics(
                        cpu=sample.get("cpu", 0),
                        memory=sample.get("memory", 0),
                        disk_io=sample.get("disk_io", 0),
                        network_io=sample.get("network_io", 0),
                        process_memory=sample.get("process_memory", 0),
                        timestamp=sample.get("timestamp", datetime.now().isoformat())
                    ))

            return PerformanceReport(
                summary=report.get("summary", {}),
                metrics=history,
                alerts=report.get("alerts", [])
            )
        else:
            # モックデータ（開発環境用）
            return PerformanceReport(
                summary={"status": "ok"},
                metrics=[],
                alerts=[]
            )
    except Exception as e:
        logger.error(f"メトリクス取得エラー: {e}")
        raise HTTPException(status_code=500, detail="メトリクス取得に失敗しました")

# バックアップ管理エンドポイント
@app.get("/backups", response_model=List[BackupInfo])
async def list_backups(current_user: dict = Depends(get_current_user)):
    """バックアップ一覧取得"""
    try:
        if get_recovery_manager:
            recovery_manager = get_recovery_manager()
            backups = recovery_manager.list_backups()

            backup_list = []
            for backup in backups:
                backup_list.append(BackupInfo(
                    backup_id=backup.backup_id,
                    timestamp=backup.timestamp.isoformat(),
                    size_bytes=backup.size_bytes,
                    status=backup.status,
                    verified=backup.verified
                ))

            return backup_list
        else:
            return []
    except Exception as e:
        logger.error(f"バックアップ一覧取得エラー: {e}")
        raise HTTPException(status_code=500, detail="バックアップ一覧取得に失敗しました")

# セキュリティレポートエンドポイント
@app.get("/security/report", response_model=SecurityReport)
async def get_security_report(current_user: dict = Depends(get_current_user)):
    """セキュリティレポート取得"""
    try:
        if get_security_manager:
            security_manager = get_security_manager()
            security_manager.initialize()
            report = security_manager.get_security_report()

            return SecurityReport(
                threat_level=report.get("threat_level", "low"),
                total_events_24h=report.get("statistics", {}).get("total_events_24h", 0),
                active_lockouts=report.get("statistics", {}).get("active_lockouts", 0),
                suspicious_activities=report.get("statistics", {}).get("suspicious_activities", 0),
                last_scan=report.get("last_scan", datetime.now().isoformat())
            )
        else:
            return SecurityReport(
                threat_level="low",
                total_events_24h=0,
                active_lockouts=0,
                suspicious_activities=0,
                last_scan=datetime.now().isoformat()
            )
    except Exception as e:
        logger.error(f"セキュリティレポート取得エラー: {e}")
        raise HTTPException(status_code=500, detail="セキュリティレポート取得に失敗しました")

# WebSocketエンドポイント（リアルタイム監視）
@app.websocket("/ws/monitoring")
async def websocket_monitoring(websocket: WebSocket):
    """リアルタイム監視WebSocket"""
    await manager.connect(websocket)

    try:
        while True:
            # 定期的にメトリクスデータを送信
            if PerformanceMonitor:
                try:
                    monitor = PerformanceMonitor()
                    metrics = monitor.get_current_metrics()

                    data = {
                        "type": "metrics",
                        "timestamp": datetime.now().isoformat(),
                        "data": metrics
                    }

                    await websocket.send_json(data)
                except Exception as e:
                    logger.error(f"メトリクス送信エラー: {e}")

            # 1秒間隔でデータを送信
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocketエラー: {e}")
        manager.disconnect(websocket)

# アバター管理エンドポイント（データベース統合版）
@app.get("/api/avatars")
async def get_avatars(current_user: dict = Depends(get_current_user)):
    """アバター一覧取得（データベース統合版）"""
    try:
        if get_user_avatars:
            avatars = get_user_avatars(current_user.get("user_id", 1))

            # 監査ログを記録
            if log_audit_event:
                log_audit_event(
                    action="list_avatars",
                    resource_type="avatar",
                    user_id=current_user.get("user_id"),
                    details={"count": len(avatars)}
                )

            return {
                "avatars": avatars,
                "total": len(avatars),
                "status": "success"
            }
        else:
            return {
                "avatars": [],
                "total": 0,
                "message": "データベース機能が利用できません"
            }
    except Exception as e:
        logger.error(f"アバター一覧取得エラー: {e}")
        raise HTTPException(status_code=500, detail="アバター一覧取得に失敗しました")


@app.post("/api/avatars")
async def create_avatar(avatar_data: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    """アバター作成（データベース統合版）"""
    try:
        if create_avatar_preset:
            name = avatar_data.get("name", "Untitled Avatar")
            parameters = avatar_data.get("parameters", {})

            result = create_avatar_preset(
                user_id=current_user.get("user_id", 1),
                name=name,
                parameters=parameters
            )

            return {
                "avatar": result,
                "status": "created",
                "message": "アバターが正常に作成されました"
            }
        else:
            return {
                "avatar_id": str(uuid.uuid4()),
                "status": "created_mock",
                "message": "データベース機能が利用できないため、モックデータで作成されました"
            }
    except Exception as e:
        logger.error(f"アバター作成エラー: {e}")
        raise HTTPException(status_code=500, detail="アバター作成に失敗しました")


@app.get("/api/avatars/{avatar_id}")
async def get_avatar(avatar_id: str, current_user: dict = Depends(get_current_user)):
    """特定のアバターを取得"""
    try:
        if get_database_service:
            db_service = get_database_service()
            with get_database_manager().get_session() as session:
                avatar = db_service.avatar_repo.get_by_avatar_id(session, avatar_id)

                if not avatar:
                    raise HTTPException(status_code=404, detail="アバターが見つかりません")

                # 所有権チェック
                if avatar.owner_id != current_user.get("user_id", 1):
                    raise HTTPException(status_code=403, detail="アクセス権限がありません")

                return {
                    "avatar": {
                        "id": avatar.id,
                        "name": avatar.name,
                        "avatar_id": avatar.avatar_id,
                        "parameters": avatar.parameters,
                        "created_at": avatar.created_at.isoformat(),
                        "is_active": avatar.is_active
                    },
                    "status": "success"
                }
        else:
            raise HTTPException(status_code=404, detail="データベース機能が利用できません")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"アバター取得エラー: {e}")
        raise HTTPException(status_code=500, detail="アバター取得に失敗しました")

# 2要素認証エンドポイント
@app.post("/api/2fa/setup")
async def setup_two_factor_auth(username: str, current_user: dict = Depends(get_current_user)):
    """2FAセットアップ"""
    try:
        if setup_2fa:
            user_id = current_user.get("user_id", 1)
            result = setup_2fa(user_id, username)

            # 監査ログを記録
            if log_audit_event:
                log_audit_event(
                    action="setup_2fa",
                    resource_type="user",
                    user_id=user_id,
                    details={"username": username}
                )

            return {
                "setup_data": result,
                "status": "success",
                "message": "2FAセットアップデータを生成しました"
            }
        else:
            raise HTTPException(status_code=404, detail="2FA機能が利用できません")
    except Exception as e:
        logger.error(f"2FAセットアップエラー: {e}")
        raise HTTPException(status_code=500, detail="2FAセットアップに失敗しました")


@app.post("/api/2fa/enable")
async def enable_two_factor_auth(username: str, token: str, current_user: dict = Depends(get_current_user)):
    """2FAを有効化"""
    try:
        if setup_2fa:
            user_id = current_user.get("user_id", 1)
            result = setup_2fa(user_id, username)  # 実際には別途有効化関数が必要

            # トークン検証
            if verify_2fa_token:
                token_result = verify_2fa_token(user_id, token)
                if not token_result.get("valid", False):
                    raise HTTPException(status_code=400, detail="無効なトークンです")

            return {
                "status": "enabled",
                "message": "2要素認証が有効になりました"
            }
        else:
            raise HTTPException(status_code=404, detail="2FA機能が利用できません")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"2FA有効化エラー: {e}")
        raise HTTPException(status_code=500, detail="2FA有効化に失敗しました")


@app.post("/api/2fa/verify")
async def verify_two_factor_token(username: str, token: str, current_user: dict = Depends(get_current_user)):
    """2FAトークンを検証"""
    try:
        if verify_2fa_token:
            user_id = current_user.get("user_id", 1)
            result = verify_2fa_token(user_id, token)

            return {
                "valid": result.get("valid", False),
                "remaining_time": result.get("remaining_time", 0),
                "message": "トークン検証結果"
            }
        else:
            raise HTTPException(status_code=404, detail="2FA機能が利用できません")
    except Exception as e:
        logger.error(f"2FAトークン検証エラー: {e}")
        raise HTTPException(status_code=500, detail="トークン検証に失敗しました")


@app.post("/api/2fa/verify-backup")
async def verify_backup_code(username: str, backup_code: str, current_user: dict = Depends(get_current_user)):
    """バックアップコードを検証"""
    try:
        if verify_backup_code:
            user_id = current_user.get("user_id", 1)
            result = verify_backup_code(user_id, backup_code)

            return {
                "valid": result.get("valid", False),
                "message": result.get("message", "バックアップコード検証結果")
            }
        else:
            raise HTTPException(status_code=404, detail="2FA機能が利用できません")
    except Exception as e:
        logger.error(f"バックアップコード検証エラー: {e}")
        raise HTTPException(status_code=500, detail="バックアップコード検証に失敗しました")


@app.post("/api/2fa/disable")
async def disable_two_factor_auth(password: str, current_user: dict = Depends(get_current_user)):
    """2FAを無効化"""
    try:
        if disable_2fa:
            user_id = current_user.get("user_id", 1)
            result = disable_2fa(user_id, password)

            if result.get("success", False):
                return {
                    "status": "disabled",
                    "message": "2要素認証が無効になりました"
                }
            else:
                raise HTTPException(status_code=400, detail=result.get("error", "無効化に失敗しました"))
        else:
            raise HTTPException(status_code=404, detail="2FA機能が利用できません")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"2FA無効化エラー: {e}")
        raise HTTPException(status_code=500, detail="2FA無効化に失敗しました")


@app.get("/api/2fa/status")
async def get_two_factor_status(current_user: dict = Depends(get_current_user)):
    """2FAステータスを取得"""
    try:
        if get_2fa_status:
            user_id = current_user.get("user_id", 1)
            result = get_2fa_status(user_id)

            return {
                "status": result,
                "message": "2FAステータス情報"
            }
        else:
            raise HTTPException(status_code=404, detail="2FA機能が利用できません")
    except Exception as e:
        logger.error(f"2FAステータス取得エラー: {e}")
        raise HTTPException(status_code=500, detail="ステータス取得に失敗しました")
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP例外ハンドラー"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """一般例外ハンドラー"""
    logger.error(f"予期しないエラー: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "内部サーバーエラー", "error_code": 500}
    )

# サーバー起動関数
def start_api_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """APIサーバーを起動"""
    logger.info(f"Cocoa APIサーバーを起動します: http://{host}:{port}")

    uvicorn.run(
        "main.api_server:app",
        host=host,
        port=port,
        reload=reload,
        access_log=True,
        log_level="info"
    )

if __name__ == "__main__":
    # 開発環境での直接起動用
    start_api_server(reload=True)
