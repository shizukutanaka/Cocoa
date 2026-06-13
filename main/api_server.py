"""
REST API Server for Cocoa Avatar Management System

Production-grade APIサーバー実装
"""


from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import uvicorn
    from fastapi import (
        Depends,
        FastAPI,
        HTTPException,
        Query,
        Request,
        Response,
        WebSocket,
        WebSocketDisconnect,
        status,
    )
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, StreamingResponse
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # Minimal stubs so module-level code doesn't crash on import without FastAPI
    FastAPI = None
    HTTPException = None
    WebSocket = None
    WebSocketDisconnect = None
    status = None
    CORSMiddleware = None
    JSONResponse = None
    HTTPAuthorizationCredentials = None
    uvicorn = None
    Response = None
    Request = None
    def Query(default=None, **_kw):
        return default

    def Depends(x=None):
        return x

    def HTTPBearer(**_kwargs):
        return None

    class BaseModel:
        pass

    class _NullApp:
        """No-op stub for app when FastAPI is unavailable."""
        def get(self, *a, **kw): return lambda f: f
        def post(self, *a, **kw): return lambda f: f
        def put(self, *a, **kw): return lambda f: f
        def patch(self, *a, **kw): return lambda f: f
        def delete(self, *a, **kw): return lambda f: f
        def websocket(self, *a, **kw): return lambda f: f
        def middleware(self, *a, **kw): return lambda f: f
        def add_middleware(self, *a, **kw): pass
        def exception_handler(self, *a, **kw): return lambda f: f
        def on_event(self, *a, **kw): return lambda f: f

# カスタムモジュールインポート
try:
    from .database_manager import (
        create_avatar_preset,
        get_database_manager,
        get_database_service,
        get_user_avatars,
        log_audit_event,
    )
    from .disaster_recovery import get_recovery_manager
    from .health_monitor import get_health_monitor
    from .integrated_security import get_security_manager
    from .performance_monitor import PerformanceMonitor
    from .redis_cache_manager import cache_async, get_cache_manager
    from .two_factor_auth import (
        disable_2fa,
        get_2fa_status,
        get_two_factor_service,
        setup_2fa,
        verify_2fa_token,
        verify_backup_code,
    )
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

# New modules (always available — pure stdlib)
try:
    from .auth_manager import AuthError, get_auth_manager
    from .avatar_collections import get_collection_store
    from .avatar_marketplace import get_marketplace
    from .rate_limiter import get_client_ip, get_rate_limiter
    from .saved_searches import get_saved_search_store
    from .search_engine import get_search_index
    from .user_notifications import get_notification_queue
    _NEW_MODULES_AVAILABLE = True
except ImportError:
    _NEW_MODULES_AVAILABLE = False
    get_auth_manager = None
    get_marketplace = None
    get_rate_limiter = None
    get_search_index = None
    get_client_ip = None
    get_notification_queue = None
    get_collection_store = None
    get_saved_search_store = None
    AuthError = Exception

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPIアプリケーション作成
if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Cocoa Avatar Management API",
        description=(
            "Production-grade REST API for the Cocoa avatar management platform.\n\n"
            "## Authentication\n"
            "Most endpoints require a **Bearer JWT** token obtained from `POST /api/auth/login`.\n\n"
            "## Rate Limiting\n"
            "Rate limits are applied per authenticated user (or IP for anonymous requests). "
            "Limits are returned in `X-RateLimit-*` response headers.\n\n"
            "## Pagination\n"
            "All list endpoints return `total`, `offset`, `limit`, `has_more`, and "
            "`next_offset` (null when there are no more items)."
        ),
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {"name": "auth", "description": "Registration, login, token refresh, and profile management"},
            {"name": "marketplace", "description": "Avatar publishing, search, download, ratings, and reviews"},
            {"name": "search", "description": "Full-text search and autocomplete across the avatar catalog"},
            {"name": "collections", "description": "User-curated avatar collections (public or private)"},
            {"name": "notifications", "description": "In-app notification queue per user"},
            {"name": "admin", "description": "Administrative operations — requires admin role"},
            {"name": "system", "description": "Liveness, readiness, and monitoring probes"},
        ],
        contact={
            "name": "Cocoa Platform Team",
            "url": "https://github.com/shizukutanaka/Cocoa",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
    )

    # セキュリティ設定
    security = HTTPBearer(auto_error=False)

    # CORS設定
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
else:
    app = _NullApp()
    security = None

# セキュリティ・レート制限ミドルウェア
if FASTAPI_AVAILABLE:
    # Security response headers applied to every response
    _API_VERSION = "2.0.0"
    _SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-XSS-Protection": "1; mode=block",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "X-API-Version": _API_VERSION,
    }

    def _apply_security_headers(response):
        for k, v in _SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response

    def _rate_limit_key(request) -> str:
        """Prefer the authenticated user id as the rate-limit key, else fall back to IP.

        Decodes the Bearer token cheaply (signature-verified, no DB lookup) so users
        behind a shared NAT each get their own bucket. Falls back to ip:<addr>.
        """
        if get_auth_manager:
            auth_header = request.headers.get("authorization", "")
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:].strip()
                try:
                    payload = get_auth_manager().verify_access_token(token)
                    return f"user:{payload['sub']}"
                except Exception:
                    pass  # invalid/expired → fall through to IP
        return f"ip:{get_client_ip(request)}"

    @app.middleware("http")  # type: ignore[union-attr]
    async def security_middleware(request: Request, call_next):
        """Rate limiting + security headers middleware."""
        path = request.url.path
        logger.info(f"API Request: {request.method} {path}")

        if get_rate_limiter and get_client_ip:
            limiter = get_rate_limiter()
            client_key = _rate_limit_key(request)
            allowed, rl_headers = limiter.check(client_key, path)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "リクエスト制限を超えました。しばらく後に再試行してください。",
                        "error_code": 429,
                    },
                    headers={**rl_headers, **_SECURITY_HEADERS},
                )
            response = await call_next(request)
            for k, v in rl_headers.items():
                response.headers[k] = v
            return _apply_security_headers(response)

        response = await call_next(request)
        return _apply_security_headers(response)

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
async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """JWT or API key authentication."""
    # 1. Try X-API-Key header (programmatic access)
    if get_auth_manager and request is not None:
        api_key_header = request.headers.get("X-API-Key", "").strip()
        if api_key_header:
            auth = get_auth_manager()
            key_payload = auth.verify_api_key(api_key_header)
            if not key_payload:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="無効なAPIキーです")
            return {
                "user_id": key_payload["sub"],
                "username": key_payload.get("username", ""),
                "role": key_payload.get("role", "user"),
            }

    # 2. Bearer JWT
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="認証が必要です")

    token = credentials.credentials

    # Use real JWT auth when available
    if get_auth_manager:
        try:
            auth = get_auth_manager()
            payload = auth.verify_access_token(token)
            return {
                "user_id": payload["sub"],
                "username": payload.get("username", ""),
                "role": payload.get("role", "user"),
            }
        except AuthError as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.message) from e
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="無効なトークンです") from e

    # Fallback: legacy API secret
    if token != os.getenv("API_SECRET_TOKEN", "default-secret"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="無効なトークンです")
    return {"user_id": "system", "username": "system", "role": "admin"}


async def get_current_admin(current_user: dict = Depends(get_current_user)):
    """Admin-only dependency."""
    if current_user.get("role") not in ("admin", "moderator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="管理者権限が必要です")
    return current_user

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
            timestamp=datetime.now(timezone.utc).isoformat(),
            version="2.0.0",
            uptime=0.0  # 実際の起動時間を取得する場合は適切な実装が必要
        )
    except Exception as e:
        logger.error(f"ヘルスチェックエラー: {e}")
        raise HTTPException(status_code=500, detail="ヘルスチェックに失敗しました") from e


@app.get("/live", tags=["system"])
async def liveness_probe():
    """Liveness probe — プロセスが応答可能かのみを確認（依存チェックなし）"""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/ready", tags=["system"])
async def readiness_probe():
    """Readiness probe — 依存サブシステムが利用可能かを確認"""
    checks = {
        "auth": get_auth_manager is not None,
        "marketplace": get_marketplace is not None,
        "search": get_search_index is not None,
        "rate_limiter": get_rate_limiter is not None,
    }
    ready = all(checks.values())
    status_code = 200 if ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if ready else "not_ready",
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

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
                history.extend(
                    SystemMetrics(
                        cpu=sample.get("cpu", 0),
                        memory=sample.get("memory", 0),
                        disk_io=sample.get("disk_io", 0),
                        network_io=sample.get("network_io", 0),
                        process_memory=sample.get("process_memory", 0),
                        timestamp=sample.get("timestamp", datetime.now(timezone.utc).isoformat())
                    )
                    for sample in monitor.history[-10:]  # 最新10件
                )

            return PerformanceReport(
                summary=report.get("summary", {}),
                metrics=history,
                alerts=report.get("alerts", [])
            )
        # モックデータ（開発環境用）
        return PerformanceReport(
            summary={"status": "ok"},
            metrics=[],
            alerts=[]
        )
    except Exception as e:
        logger.error(f"メトリクス取得エラー: {e}")
        raise HTTPException(status_code=500, detail="メトリクス取得に失敗しました") from e

# バックアップ管理エンドポイント
@app.get("/backups", response_model=List[BackupInfo])
async def list_backups(current_user: dict = Depends(get_current_user)):
    """バックアップ一覧取得"""
    try:
        if get_recovery_manager:
            recovery_manager = get_recovery_manager()
            backups = recovery_manager.list_backups()

            return [
                BackupInfo(
                    backup_id=backup.backup_id,
                    timestamp=backup.timestamp.isoformat(),
                    size_bytes=backup.size_bytes,
                    status=backup.status,
                    verified=backup.verified
                )
                for backup in backups
            ]
        return []
    except Exception as e:
        logger.error(f"バックアップ一覧取得エラー: {e}")
        raise HTTPException(status_code=500, detail="バックアップ一覧取得に失敗しました") from e

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
                last_scan=report.get("last_scan", datetime.now(timezone.utc).isoformat())
            )
        return SecurityReport(
            threat_level="low",
            total_events_24h=0,
            active_lockouts=0,
            suspicious_activities=0,
            last_scan=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        logger.error(f"セキュリティレポート取得エラー: {e}")
        raise HTTPException(status_code=500, detail="セキュリティレポート取得に失敗しました") from e

# WebSocketエンドポイント（リアルタイム監視）
@app.websocket("/ws/monitoring")
async def websocket_monitoring(websocket: WebSocket, token: str = Query("")):
    """リアルタイム監視WebSocket — JWT 認証付き"""
    # Authenticate before accepting the connection
    if get_auth_manager and token:
        try:
            auth = get_auth_manager()
            auth.verify_access_token(token)
        except Exception:
            await websocket.close(code=4001, reason="Unauthorized")
            return
    elif get_auth_manager and not token:
        await websocket.close(code=4001, reason="Token required")
        return

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
                        "timestamp": datetime.now(timezone.utc).isoformat(),
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
        return {
            "avatars": [],
            "total": 0,
            "message": "データベース機能が利用できません"
        }
    except Exception as e:
        logger.error(f"アバター一覧取得エラー: {e}")
        raise HTTPException(status_code=500, detail="アバター一覧取得に失敗しました") from e


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
        return {
            "avatar_id": str(uuid.uuid4()),
            "status": "created_mock",
            "message": "データベース機能が利用できないため、モックデータで作成されました"
        }
    except Exception as e:
        logger.error(f"アバター作成エラー: {e}")
        raise HTTPException(status_code=500, detail="アバター作成に失敗しました") from e


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
        raise HTTPException(status_code=500, detail="アバター取得に失敗しました") from e

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
        raise HTTPException(status_code=404, detail="2FA機能が利用できません")
    except Exception as e:
        logger.error(f"2FAセットアップエラー: {e}")
        raise HTTPException(status_code=500, detail="2FAセットアップに失敗しました") from e


@app.post("/api/2fa/enable")
async def enable_two_factor_auth(username: str, token: str, current_user: dict = Depends(get_current_user)):
    """2FAを有効化"""
    try:
        if setup_2fa:
            user_id = current_user.get("user_id", 1)
            setup_2fa(user_id, username)  # 実際には別途有効化関数が必要

            # トークン検証
            if verify_2fa_token:
                token_result = verify_2fa_token(user_id, token)
                if not token_result.get("valid", False):
                    raise HTTPException(status_code=400, detail="無効なトークンです")

            return {
                "status": "enabled",
                "message": "2要素認証が有効になりました"
            }
        raise HTTPException(status_code=404, detail="2FA機能が利用できません")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"2FA有効化エラー: {e}")
        raise HTTPException(status_code=500, detail="2FA有効化に失敗しました") from e


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
        raise HTTPException(status_code=404, detail="2FA機能が利用できません")
    except Exception as e:
        logger.error(f"2FAトークン検証エラー: {e}")
        raise HTTPException(status_code=500, detail="トークン検証に失敗しました") from e


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
        raise HTTPException(status_code=404, detail="2FA機能が利用できません")
    except Exception as e:
        logger.error(f"バックアップコード検証エラー: {e}")
        raise HTTPException(status_code=500, detail="バックアップコード検証に失敗しました") from e


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
            raise HTTPException(status_code=400, detail=result.get("error", "無効化に失敗しました"))
        raise HTTPException(status_code=404, detail="2FA機能が利用できません")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"2FA無効化エラー: {e}")
        raise HTTPException(status_code=500, detail="2FA無効化に失敗しました") from e


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
        raise HTTPException(status_code=404, detail="2FA機能が利用できません")
    except Exception as e:
        logger.error(f"2FAステータス取得エラー: {e}")
        raise HTTPException(status_code=500, detail="ステータス取得に失敗しました") from e
# ===========================================================================
# AUTH ENDPOINTS
# ===========================================================================

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "user"


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class CreateApiKeyRequest(BaseModel):
    name: str


@app.post("/api/auth/register", tags=["auth"], status_code=201)
async def register(body: RegisterRequest):
    """新規ユーザー登録。email_verification_token を使って POST /api/auth/verify-email でメール確認を完了してください"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    try:
        auth = get_auth_manager()
        user = auth.register(body.username, body.email, body.password, body.role)
        verification_token = auth.create_email_verification_token(user.user_id)
        return {
            "user_id": user.user_id,
            "username": user.username,
            "role": user.role,
            "status": "created",
            "is_email_verified": user.is_email_verified,
            "email_verification_token": verification_token,
        }
    except (ValueError, AuthError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/auth/verify-email", tags=["auth"])
async def verify_email(body: dict):
    """メールアドレスを確認する。body: {\"token\": \"...\"}"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    token = body.get("token", "").strip() if isinstance(body, dict) else ""
    if not token:
        raise HTTPException(status_code=400, detail="token が必要です")
    ok = get_auth_manager().verify_email(token)
    if not ok:
        raise HTTPException(status_code=400, detail="トークンが無効または期限切れです")
    return {"status": "verified"}


@app.post("/api/auth/resend-verification", tags=["auth"])
async def resend_verification(current_user: dict = Depends(get_current_user)):
    """メール確認トークンを再送信（新しいトークンを発行）"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    auth = get_auth_manager()
    user = auth.store.get_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    if user.is_email_verified:
        raise HTTPException(status_code=400, detail="メールアドレスは既に確認済みです")
    token = auth.create_email_verification_token(user.user_id)
    return {"status": "sent", "email_verification_token": token}


@app.post("/api/auth/login", tags=["auth"])
async def login(body: LoginRequest):
    """ログイン（JWT トークンペアを返す）"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    try:
        auth = get_auth_manager()
        tokens = auth.login(body.username, body.password)
        return {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "token_type": tokens.token_type,
            "expires_in": tokens.expires_in,
        }
    except AuthError as e:
        code = 429 if e.code == "account_locked" else 401
        raise HTTPException(status_code=code, detail=e.message) from e


@app.post("/api/auth/refresh", tags=["auth"])
async def refresh_token(body: RefreshRequest):
    """アクセストークンをリフレッシュ"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    try:
        auth = get_auth_manager()
        tokens = auth.refresh(body.refresh_token)
        return {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "token_type": tokens.token_type,
            "expires_in": tokens.expires_in,
        }
    except AuthError as e:
        raise HTTPException(status_code=401, detail=e.message) from e


@app.post("/api/auth/logout", tags=["auth"])
async def logout(body: RefreshRequest, current_user: dict = Depends(get_current_user),
                 credentials: HTTPAuthorizationCredentials = Depends(security)):
    """ログアウト（トークンを無効化）"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    auth = get_auth_manager()
    auth.logout(credentials.credentials, body.refresh_token)
    return {"status": "logged_out"}


@app.get("/api/auth/me", tags=["auth"])
async def get_me(current_user: dict = Depends(get_current_user)):
    """現在のユーザー情報を取得"""
    return current_user


@app.put("/api/auth/me", tags=["auth"])
async def update_profile(body: UpdateProfileRequest, current_user: dict = Depends(get_current_user)):
    """プロフィール更新（表示名、自己紹介、アバター画像URL）"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    try:
        auth = get_auth_manager()
        user = auth.update_profile(
            current_user["user_id"],
            display_name=body.display_name,
            bio=body.bio,
            avatar_url=body.avatar_url,
        )
        return user.public_profile()
    except AuthError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@app.post("/api/auth/change-password", tags=["auth"])
async def change_password(body: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    """ログイン中のユーザーがパスワードを変更"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    try:
        get_auth_manager().change_password(current_user["user_id"], body.current_password, body.new_password)
        return {"status": "password_changed"}
    except AuthError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/notifications", tags=["notifications"])
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """通知一覧取得"""
    if not get_notification_queue:
        return {"total": 0, "unread_count": 0, "items": []}
    return get_notification_queue().get_notifications(
        current_user["user_id"], unread_only=unread_only, limit=limit, offset=offset
    )


@app.get("/api/notifications/unread-count", tags=["notifications"])
async def unread_notification_count(current_user: dict = Depends(get_current_user)):
    """未読通知数"""
    if not get_notification_queue:
        return {"unread_count": 0}
    return {"unread_count": get_notification_queue().unread_count(current_user["user_id"])}


@app.post("/api/notifications/{notification_id}/read", tags=["notifications"])
async def mark_notification_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    """通知を既読にする"""
    if not get_notification_queue:
        raise HTTPException(status_code=503, detail="通知システムが利用できません")
    ok = get_notification_queue().mark_read(current_user["user_id"], notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="通知が見つかりません")
    return {"status": "read", "notification_id": notification_id}


@app.post("/api/notifications/read-all", tags=["notifications"])
async def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    """全通知を既読にする"""
    if not get_notification_queue:
        raise HTTPException(status_code=503, detail="通知システムが利用できません")
    count = get_notification_queue().mark_all_read(current_user["user_id"])
    return {"status": "all_read", "marked_count": count}


@app.delete("/api/notifications/{notification_id}", tags=["notifications"])
async def delete_notification(notification_id: str, current_user: dict = Depends(get_current_user)):
    """通知を削除"""
    if not get_notification_queue:
        raise HTTPException(status_code=503, detail="通知システムが利用できません")
    ok = get_notification_queue().delete_notification(current_user["user_id"], notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="通知が見つかりません")
    return {"status": "deleted"}


@app.get("/api/notifications/preferences", tags=["notifications"])
async def get_notification_preferences(current_user: dict = Depends(get_current_user)):
    """ミュート中の通知種別を取得"""
    if not get_notification_queue:
        return {"muted_kinds": []}
    return {"muted_kinds": get_notification_queue().get_muted_kinds(current_user["user_id"])}


class NotificationPreferencesRequest(BaseModel):
    muted_kinds: List[str]


@app.put("/api/notifications/preferences", tags=["notifications"])
async def set_notification_preferences(
    body: NotificationPreferencesRequest,
    current_user: dict = Depends(get_current_user),
):
    """通知種別のミュート設定を更新。muted_kinds: [] でリセット"""
    if not get_notification_queue:
        raise HTTPException(status_code=503, detail="通知システムが利用できません")
    get_notification_queue().set_muted_kinds(current_user["user_id"], body.muted_kinds)
    return {"muted_kinds": get_notification_queue().get_muted_kinds(current_user["user_id"])}


@app.get("/api/auth/bookmarks", tags=["auth"])
async def list_bookmarks(current_user: dict = Depends(get_current_user)):
    """ブックマーク一覧取得"""
    if not get_auth_manager:
        return {"bookmarks": []}
    auth = get_auth_manager()
    try:
        return {"bookmarks": auth.get_bookmarks(current_user["user_id"])}
    except AuthError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@app.post("/api/auth/bookmarks/{item_id}", tags=["auth"])
async def add_bookmark(item_id: str, current_user: dict = Depends(get_current_user)):
    """ブックマーク追加"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    auth = get_auth_manager()
    try:
        bookmarks = auth.add_bookmark(current_user["user_id"], item_id)
        return {"bookmarks": bookmarks, "added": item_id}
    except AuthError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@app.delete("/api/auth/bookmarks/{item_id}", tags=["auth"])
async def remove_bookmark(item_id: str, current_user: dict = Depends(get_current_user)):
    """ブックマーク削除"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    auth = get_auth_manager()
    try:
        bookmarks = auth.remove_bookmark(current_user["user_id"], item_id)
        return {"bookmarks": bookmarks, "removed": item_id}
    except AuthError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@app.get("/api/auth/following", tags=["auth"])
async def list_following(current_user: dict = Depends(get_current_user)):
    """フォロー中クリエイター一覧"""
    if not get_auth_manager:
        return {"following": []}
    try:
        return {"following": get_auth_manager().get_following(current_user["user_id"])}
    except AuthError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@app.post("/api/auth/following/{creator_id}", tags=["auth"])
async def follow_creator(creator_id: str, current_user: dict = Depends(get_current_user)):
    """クリエイターをフォロー"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    try:
        following = get_auth_manager().follow(current_user["user_id"], creator_id)
        if get_notification_queue:
            get_notification_queue().push(
                creator_id, "new_follower",
                "新しいフォロワー",
                f"{current_user.get('username', 'Someone')} があなたをフォローしました",
                {"follower_id": current_user["user_id"], "follower_username": current_user.get("username")},
            )
        return {"following_count": len(following), "followed": creator_id}
    except (AuthError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.delete("/api/auth/following/{creator_id}", tags=["auth"])
async def unfollow_creator(creator_id: str, current_user: dict = Depends(get_current_user)):
    """クリエイターのフォローを解除"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    try:
        following = get_auth_manager().unfollow(current_user["user_id"], creator_id)
        return {"following_count": len(following), "unfollowed": creator_id}
    except AuthError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@app.get("/api/auth/feed", tags=["auth"])
async def creator_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """フォロー中クリエイターの最新公開アバター一覧"""
    if not get_auth_manager or not get_marketplace:
        return {"total": 0, "items": []}
    try:
        following_ids = {p["user_id"] for p in get_auth_manager().get_following(current_user["user_id"])}
    except AuthError:
        following_ids = set()
    if not following_ids:
        return {"total": 0, "items": []}
    mp = get_marketplace()
    all_listings = mp.search("", sort_by="newest", limit=1000)["items"]
    feed = [lst for lst in all_listings if lst["owner_id"] in following_ids]
    total = len(feed)
    page = feed[offset: offset + limit]
    has_more = offset + limit < total
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": has_more,
        "next_offset": offset + limit if has_more else None,
        "items": page,
    }


@app.get("/api/users/search", tags=["auth"])
async def search_users(
    q: str = Query("", min_length=1),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """ユーザー名・表示名でユーザーを検索（公開プロフィールのみ）"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    return get_auth_manager().search_users(q, limit=limit, offset=offset)


@app.get("/api/users/{user_id}/profile", tags=["auth"])
async def get_user_profile(user_id: str):
    """公開プロフィール取得"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    user = get_auth_manager().store.get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    profile = user.public_profile()
    profile["followers_count"] = get_auth_manager().get_followers_count(user_id)
    return profile


@app.post("/api/auth/password-reset", tags=["auth"])
async def request_password_reset(body: PasswordResetRequest):
    """パスワードリセットトークンを送信"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    auth = get_auth_manager()
    reset_token = auth.request_password_reset(body.email)
    # In production: send email with token. Here we return it for dev convenience.
    if reset_token:
        return {"status": "sent", "dev_token": reset_token}
    return {"status": "sent"}  # Don't leak whether email exists


@app.post("/api/auth/password-reset/confirm", tags=["auth"])
async def confirm_password_reset(body: PasswordResetConfirm):
    """パスワードをリセット"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    auth = get_auth_manager()
    ok = auth.reset_password(body.token, body.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail="無効または期限切れのトークンです")
    return {"status": "password_reset"}


@app.post("/api/auth/api-keys", tags=["auth"], status_code=201)
async def create_api_key(body: CreateApiKeyRequest, current_user: dict = Depends(get_current_user)):
    """APIキーを作成。raw_key は一度だけ返されます — 安全な場所に保管してください"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    try:
        result = get_auth_manager().create_api_key(current_user["user_id"], body.name)
        return result
    except (ValueError, AuthError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/auth/api-keys", tags=["auth"])
async def list_api_keys(current_user: dict = Depends(get_current_user)):
    """現在のユーザーのAPIキー一覧（raw_key は含まれません）"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    keys = get_auth_manager().list_api_keys(current_user["user_id"])
    return {"items": keys, "total": len(keys)}


@app.delete("/api/auth/api-keys/{key_id}", tags=["auth"])
async def revoke_api_key(key_id: str, current_user: dict = Depends(get_current_user)):
    """APIキーを無効化"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    ok = get_auth_manager().revoke_api_key(current_user["user_id"], key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="APIキーが見つかりません")
    return {"status": "revoked", "key_id": key_id}


# ===========================================================================
# AVATAR SEARCH ENDPOINTS
# ===========================================================================

@app.get("/api/search/avatars", tags=["search"])
async def search_avatars(
    q: str = Query("", description="検索クエリ"),
    tags: Optional[str] = Query(None, description="カンマ区切りのタグ"),
    category: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    sort_by: str = Query("relevance", description="relevance | name | newest | oldest"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """アバターの全文検索（フォロー中クリエーターのアバターを優先表示）"""
    if not get_search_index:
        return {"total": 0, "items": [], "facets": {}}
    idx = get_search_index()
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    # Personalization: boost results from creators the user follows
    boost_ids: Optional[List[str]] = None
    if get_auth_manager and sort_by == "relevance":
        try:
            user_rec = get_auth_manager().store.get_by_id(current_user["user_id"])
            if user_rec and user_rec.following:
                boost_ids = list(user_rec.following)
        except Exception:
            pass
    results = idx.search(
        query=q,
        owner_id=current_user["user_id"],
        public_only=False,
        tags=tag_list,
        category=category,
        platform=platform,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
        boost_owner_ids=boost_ids,
    )
    results["personalized"] = boost_ids is not None and len(boost_ids) > 0
    return results


@app.get("/api/search/suggest", tags=["search"])
async def search_suggest(
    prefix: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
):
    """オートコンプリート候補を取得"""
    if not get_search_index:
        return {"suggestions": []}
    idx = get_search_index()
    return {"suggestions": idx.suggest(prefix, limit)}


# ---------------------------------------------------------------------------
# Saved search presets
# ---------------------------------------------------------------------------

class SavedSearchCreateRequest(BaseModel):
    name: str
    query: str = ""
    filters: Dict[str, Any] = {}


class SavedSearchUpdateRequest(BaseModel):
    name: Optional[str] = None
    query: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


@app.post("/api/search/saved", tags=["search"], status_code=201)
async def create_saved_search(body: SavedSearchCreateRequest, current_user: dict = Depends(get_current_user)):
    """検索プリセットを保存"""
    if not get_saved_search_store:
        raise HTTPException(status_code=503, detail="保存検索モジュールが利用できません")
    try:
        ss = get_saved_search_store().create(
            current_user["user_id"], body.name, body.query, body.filters
        )
        return ss.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/search/saved", tags=["search"])
async def list_saved_searches(current_user: dict = Depends(get_current_user)):
    """保存済み検索プリセット一覧"""
    if not get_saved_search_store:
        return {"items": [], "total": 0}
    searches = get_saved_search_store().list(current_user["user_id"])
    return {"items": [s.to_dict() for s in searches], "total": len(searches)}


@app.patch("/api/search/saved/{search_id}", tags=["search"])
async def update_saved_search(
    search_id: str, body: SavedSearchUpdateRequest, current_user: dict = Depends(get_current_user)
):
    """保存済み検索プリセットを更新"""
    if not get_saved_search_store:
        raise HTTPException(status_code=503, detail="保存検索モジュールが利用できません")
    ss = get_saved_search_store().update(
        current_user["user_id"], search_id,
        name=body.name, query=body.query, filters=body.filters,
    )
    if ss is None:
        raise HTTPException(status_code=404, detail="保存検索が見つかりません")
    return ss.to_dict()


@app.delete("/api/search/saved/{search_id}", tags=["search"])
async def delete_saved_search(search_id: str, current_user: dict = Depends(get_current_user)):
    """保存済み検索プリセットを削除"""
    if not get_saved_search_store:
        raise HTTPException(status_code=503, detail="保存検索モジュールが利用できません")
    ok = get_saved_search_store().delete(current_user["user_id"], search_id)
    if not ok:
        raise HTTPException(status_code=404, detail="保存検索が見つかりません")
    return {"status": "deleted", "search_id": search_id}


@app.post("/api/search/saved/{search_id}/use", tags=["search"])
async def use_saved_search(search_id: str, current_user: dict = Depends(get_current_user)):
    """保存済み検索プリセットを適用（last_used / use_count を更新し検索パラメータを返す）"""
    if not get_saved_search_store:
        raise HTTPException(status_code=503, detail="保存検索モジュールが利用できません")
    store = get_saved_search_store()
    ss = store.get(current_user["user_id"], search_id)
    if ss is None:
        raise HTTPException(status_code=404, detail="保存検索が見つかりません")
    store.record_use(current_user["user_id"], search_id)
    return {
        "search_id": search_id,
        "query": ss.query,
        "filters": ss.filters,
    }


# ===========================================================================
# MARKETPLACE ENDPOINTS
# ===========================================================================

class PublishRequest(BaseModel):
    avatar_id: str
    name: str
    description: str = ""
    tags: List[str] = []
    category: str = ""
    platform: str = ""
    parameters: Dict[str, Any] = {}
    thumbnail_url: str = ""
    is_free: bool = True
    price_credits: int = 0
    license_type: str = "personal"
    license_details: str = ""


class RatingRequest(BaseModel):
    stars: int  # 1-5


class ReviewRequest(BaseModel):
    stars: int  # 1-5
    text: str = ""


class ReportRequest(BaseModel):
    reason: str  # inappropriate | spam | copyright | misleading | malware | other
    details: str = ""


class ResolveReportRequest(BaseModel):
    action: str  # resolved | dismissed
    note: str = ""
    takedown: bool = False


class BulkListingActionRequest(BaseModel):
    listing_ids: List[str]
    action: str  # unpublish | delete


class UpdateListingRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    parameters: Optional[Dict[str, Any]] = None
    thumbnail_url: Optional[str] = None
    is_free: Optional[bool] = None
    price_credits: Optional[int] = None
    license_type: Optional[str] = None
    license_details: Optional[str] = None


@app.post("/api/marketplace/publish", tags=["marketplace"])
async def publish_avatar(body: PublishRequest, current_user: dict = Depends(get_current_user)):
    """アバターをマーケットプレイスに公開"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    try:
        mp = get_marketplace()
        listing = mp.publish(
            avatar_id=body.avatar_id,
            owner_id=current_user["user_id"],
            owner_username=current_user.get("username", ""),
            name=body.name,
            description=body.description,
            tags=body.tags,
            category=body.category,
            parameters=body.parameters,
            thumbnail_url=body.thumbnail_url,
            is_free=body.is_free,
            price_credits=body.price_credits,
            license_type=body.license_type,
            license_details=body.license_details,
        )
        # Also index for search
        if get_search_index:
            idx = get_search_index()
            idx.index_from_dict({
                "doc_id": listing.listing_id,
                "owner_id": current_user["user_id"],
                "name": listing.name,
                "description": listing.description,
                "tags": listing.tags,
                "category": listing.category,
                "platform": body.platform,
                "parameters": listing.parameters,
                "is_public": True,
            })
        return listing.to_dict()
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/marketplace", tags=["marketplace"])
async def browse_marketplace(
    q: str = Query("", description="検索クエリ"),
    tags: Optional[str] = Query(None, description="カンマ区切りのタグ"),
    category: Optional[str] = Query(None),
    sort_by: str = Query("newest", description="newest | downloads | rating"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """マーケットプレイスを閲覧（認証不要）"""
    if not get_marketplace:
        return {"total": 0, "items": []}
    mp = get_marketplace()
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    return mp.search(query=q, tags=tag_list, category=category, sort_by=sort_by, limit=limit, offset=offset)


@app.get("/api/marketplace/trending", tags=["marketplace"])
async def trending_avatars(limit: int = Query(10, ge=1, le=50)):
    """トレンドアバターを取得"""
    if not get_marketplace:
        return {"items": []}
    return {"items": get_marketplace().get_trending(limit)}


@app.get("/api/marketplace/trending-tags", tags=["marketplace"])
async def trending_tags(limit: int = Query(20, ge=1, le=100)):
    """人気タグを集計して取得（ダウンロード数で重み付け）"""
    if not get_marketplace:
        return {"tags": []}
    return {"tags": get_marketplace().get_trending_tags(limit)}


@app.get("/api/marketplace/{listing_id}", tags=["marketplace"])
async def get_listing(listing_id: str):
    """マーケットプレイスのリスティング詳細を取得"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    listing = get_marketplace().get_listing(listing_id)
    if not listing or not listing.is_active:
        raise HTTPException(status_code=404, detail="リスティングが見つかりません")
    return listing.to_dict()


@app.get("/api/marketplace/{listing_id}/related", tags=["marketplace"])
async def related_listings(listing_id: str, limit: int = Query(6, ge=1, le=20)):
    """指定リスティングに類似したアバターを取得（タグ・カテゴリが近いもの）"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    items = get_marketplace().get_related(listing_id, limit=limit)
    return {"listing_id": listing_id, "items": items, "count": len(items)}


@app.post("/api/marketplace/{listing_id}/download", tags=["marketplace"])
async def download_avatar(listing_id: str, current_user: dict = Depends(get_current_user)):
    """マーケットプレイスからアバターをダウンロード（クローン）"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    mp = get_marketplace()
    try:
        data = mp.download(listing_id, current_user["user_id"])
    except ValueError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    if not data:
        raise HTTPException(status_code=404, detail="リスティングが見つかりません")
    listing = mp.get_listing(listing_id)
    if listing and get_notification_queue:
        get_notification_queue().push(
            listing.owner_id, "new_download",
            "アバターがダウンロードされました",
            f"「{listing.name}」が {current_user.get('username', '誰か')} にダウンロードされました",
            {"listing_id": listing_id, "downloader_id": current_user["user_id"], "total_downloads": listing.download_count},
        )
    return {"status": "downloaded", "avatar_data": data}


@app.post("/api/marketplace/{listing_id}/rate", tags=["marketplace"])
async def rate_avatar(listing_id: str, body: RatingRequest, current_user: dict = Depends(get_current_user)):
    """アバターを評価（1-5星）"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    try:
        avg = get_marketplace().rate(listing_id, current_user["user_id"], body.stars)
        return {"listing_id": listing_id, "average_rating": avg, "your_rating": body.stars}
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/marketplace/{listing_id}/reviews", tags=["marketplace"])
async def post_review(listing_id: str, body: ReviewRequest, current_user: dict = Depends(get_current_user)):
    """テキストレビューと星評価を投稿（既存レビューは更新）"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    try:
        mp = get_marketplace()
        avg, rv = mp.review(
            listing_id,
            current_user["user_id"],
            current_user.get("username", "unknown"),
            body.stars,
            body.text,
        )
        listing = mp.get_listing(listing_id)
        if listing and get_notification_queue:
            get_notification_queue().push(
                listing.owner_id, "new_review",
                "新しいレビュー",
                f"「{listing.name}」に {rv.stars}★ のレビューが届きました",
                {"listing_id": listing_id, "reviewer_id": current_user["user_id"], "stars": rv.stars},
            )
        return {"listing_id": listing_id, "average_rating": avg, "review": rv.to_dict()}
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/marketplace/{listing_id}/reviews", tags=["marketplace"])
async def list_reviews(
    listing_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """リスティングのレビュー一覧取得"""
    if not get_marketplace:
        return {"total": 0, "items": []}
    return get_marketplace().get_reviews(listing_id, limit=limit, offset=offset)


@app.delete("/api/marketplace/{listing_id}/reviews/mine", tags=["marketplace"])
async def delete_my_review(listing_id: str, current_user: dict = Depends(get_current_user)):
    """自分のレビューを削除"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    ok = get_marketplace().delete_review(listing_id, current_user["user_id"])
    if not ok:
        raise HTTPException(status_code=404, detail="レビューが見つかりません")
    return {"status": "deleted"}


class ReviewReplyRequest(BaseModel):
    text: str


@app.post("/api/marketplace/reviews/{review_id}/replies", tags=["marketplace"], status_code=201)
async def add_review_reply(
    review_id: str, body: ReviewReplyRequest, current_user: dict = Depends(get_current_user)
):
    """レビューへの返信を追加（クリエイターまたは他ユーザー）"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    try:
        reply = get_marketplace().add_review_reply(
            review_id, current_user["user_id"], current_user["username"], body.text
        )
        return reply.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/marketplace/reviews/{review_id}/replies", tags=["marketplace"])
async def get_review_replies(review_id: str, current_user: dict = Depends(get_current_user)):
    """レビューの返信一覧"""
    if not get_marketplace:
        return {"items": [], "total": 0}
    replies = get_marketplace().get_review_replies(review_id)
    return {"items": [r.to_dict() for r in replies], "total": len(replies)}


@app.delete("/api/marketplace/reviews/{review_id}/replies/{reply_id}", tags=["marketplace"])
async def delete_review_reply(
    review_id: str, reply_id: str, current_user: dict = Depends(get_current_user)
):
    """自分の返信を削除"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    ok = get_marketplace().delete_review_reply(review_id, reply_id, current_user["user_id"])
    if not ok:
        raise HTTPException(status_code=404, detail="返信が見つかりません")
    return {"status": "deleted", "reply_id": reply_id}


@app.post("/api/marketplace/{listing_id}/report", tags=["marketplace"])
async def report_listing(listing_id: str, body: ReportRequest, current_user: dict = Depends(get_current_user)):
    """リスティングを通報（モデレーション）"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    try:
        report = get_marketplace().report_listing(
            listing_id, current_user["user_id"], body.reason, body.details
        )
        return {"status": "reported", "report_id": report.report_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.delete("/api/marketplace/{listing_id}", tags=["marketplace"])
async def unpublish_avatar(listing_id: str, current_user: dict = Depends(get_current_user)):
    """マーケットプレイスからアバターを取り下げ"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    try:
        ok = get_marketplace().unpublish(listing_id, current_user["user_id"])
        if not ok:
            raise HTTPException(status_code=404, detail="リスティングが見つかりません")
        if get_search_index:
            get_search_index().remove(listing_id)
        return {"status": "unpublished"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@app.patch("/api/marketplace/{listing_id}", tags=["marketplace"])
async def update_listing(listing_id: str, body: UpdateListingRequest, current_user: dict = Depends(get_current_user)):
    """リスティングを更新（名前・説明・タグ・パラメータ・価格）。オーナーのみ可"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    try:
        listing = get_marketplace().update_listing(
            listing_id, current_user["user_id"],
            name=body.name,
            description=body.description,
            tags=body.tags,
            parameters=body.parameters,
            thumbnail_url=body.thumbnail_url,
            is_free=body.is_free,
            price_credits=body.price_credits,
            license_type=body.license_type,
            license_details=body.license_details,
        )
        # Re-index if name/description/tags changed
        if get_search_index and any(v is not None for v in [body.name, body.description, body.tags]):
            idx = get_search_index()
            idx.index_from_dict({
                "doc_id": listing.listing_id,
                "name": listing.name,
                "description": listing.description,
                "tags": listing.tags,
                "category": listing.category,
                "owner_id": listing.owner_id,
                "is_public": listing.is_active,
            })
        return {"status": "updated", "listing": listing.to_dict()}
    except (ValueError, PermissionError) as e:
        code = 403 if isinstance(e, PermissionError) else 400
        raise HTTPException(status_code=code, detail=str(e)) from e


@app.get("/api/marketplace/downloads/history", tags=["marketplace"])
async def my_download_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """自分のダウンロード履歴を取得（新しい順）"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    return get_marketplace().get_user_download_history(current_user["user_id"], limit=limit, offset=offset)


# ===========================================================================
# CREDITS ENDPOINTS
# ===========================================================================

@app.get("/api/credits/balance", tags=["marketplace"])
async def get_credits_balance(current_user: dict = Depends(get_current_user)):
    """自分のクレジット残高を取得"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    balance = get_marketplace().get_balance(current_user["user_id"])
    return {"user_id": current_user["user_id"], "balance": balance}


class GrantCreditsRequest(BaseModel):
    user_id: str
    amount: int


@app.post("/api/admin/credits/grant", tags=["admin"])
async def grant_credits(body: GrantCreditsRequest, admin: dict = Depends(get_current_admin)):
    """ユーザーにクレジットを付与（管理者専用）"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    try:
        new_balance = get_marketplace().add_credits(body.user_id, body.amount)
        return {"user_id": body.user_id, "granted": body.amount, "new_balance": new_balance}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class SetQuotaRequest(BaseModel):
    user_id: str
    max_listings: int


@app.post("/api/admin/quotas/set", tags=["admin"])
async def set_listing_quota(body: SetQuotaRequest, admin: dict = Depends(get_current_admin)):
    """ユーザーのリスティング公開上限を設定（管理者専用）。-1 で無制限に戻す"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    mp = get_marketplace()
    if body.max_listings < 0:
        mp._quotas.pop(body.user_id, None)  # Remove quota → unlimited
        return {"user_id": body.user_id, "max_listings": None, "status": "unlimited"}
    try:
        mp.set_quota(body.user_id, body.max_listings)
        active = mp.get_active_listing_count(body.user_id)
        return {
            "user_id": body.user_id,
            "max_listings": body.max_listings,
            "current_active": active,
            "status": "set",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/admin/quotas/{user_id}", tags=["admin"])
async def get_listing_quota(user_id: str, admin: dict = Depends(get_current_admin)):
    """ユーザーのリスティング公開状況を確認（管理者専用）"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    mp = get_marketplace()
    return {
        "user_id": user_id,
        "max_listings": mp.get_quota(user_id),
        "current_active": mp.get_active_listing_count(user_id),
    }


# ===========================================================================
# VRCHAT TOOLS ENDPOINTS
# ===========================================================================

class VRChatBudgetRequest(BaseModel):
    parameters: List[Dict[str, Any]]


@app.post("/api/tools/vrchat/budget", tags=["search"])
async def analyze_vrchat_budget(body: VRChatBudgetRequest):
    """VRChat 同期パラメータ予算の分析と最適化提案。認証不要"""
    try:
        from vrchat_parameter_budget import analyze_budget, suggest_optimizations
        analysis = analyze_budget(body.parameters)
        suggestions = suggest_optimizations(body.parameters)
        return {
            **analysis,
            "suggestions": suggestions,
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="VRChat ツールが利用できません")  # noqa: B904
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class VRChatStatsRequest(BaseModel):
    polygons: int = 0
    materials: int = 0
    bones: int = 0
    skinned_meshes: int = 0
    mesh_count: int = 0
    material_slots: int = 0
    physbones_components: int = 0
    physbones_transforms: int = 0
    physbones_colliders: int = 0
    animators: int = 0
    lights: int = 0
    particle_systems: int = 0
    particle_max_particles: int = 0
    audio_sources: int = 0
    texture_memory_mb: float = 0.0
    platform: str = "PC"  # PC | Quest


@app.post("/api/tools/vrchat/performance", tags=["search"])
async def analyze_vrchat_performance(body: VRChatStatsRequest):
    """VRChat アバター性能ランク分析（Excellent/Good/Medium/Poor/Very Poor）。認証不要"""
    try:
        from vrchat_performance_analyzer import (
            AvatarStats,
            Platform,
            VRChatPerformanceAnalyzer,
        )
        platform = Platform.Quest if body.platform.lower() == "quest" else Platform.PC
        stats = AvatarStats(
            polygons=body.polygons,
            materials=body.materials,
            bones=body.bones,
            skinned_meshes=body.skinned_meshes,
            mesh_count=body.mesh_count,
            material_slots=body.material_slots,
            physbones_components=body.physbones_components,
            physbones_transforms=body.physbones_transforms,
            physbones_colliders=body.physbones_colliders,
            animators=body.animators,
            lights=body.lights,
            particle_systems=body.particle_systems,
            particle_max_particles=body.particle_max_particles,
            audio_sources=body.audio_sources,
            texture_memory_mb=body.texture_memory_mb,
        )
        analyzer = VRChatPerformanceAnalyzer(platform=platform)
        result = analyzer.analyze_stats(stats)
        return {
            "rank": result.rank.value if hasattr(result.rank, "value") else str(result.rank),
            "score": result.score,
            "platform": body.platform,
            "issues": result.issues,
            "suggestions": [
                {
                    "category": s.category,
                    "severity": s.severity,
                    "current_value": s.current_value,
                    "target_value": s.target_value,
                    "suggestion": s.suggestion,
                }
                for s in result.suggestions
            ],
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="VRChat パフォーマンス分析ツールが利用できません")  # noqa: B904
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ===========================================================================
# COLLECTION ENDPOINTS
# ===========================================================================

class CollectionCreateRequest(BaseModel):
    name: str
    description: str = ""
    is_public: bool = False


class CollectionUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


@app.post("/api/collections", tags=["collections"])
async def create_collection(body: CollectionCreateRequest, current_user: dict = Depends(get_current_user)):
    """コレクションを作成"""
    if not get_collection_store:
        raise HTTPException(status_code=503, detail="コレクション機能が利用できません")
    try:
        col = get_collection_store().create(current_user["user_id"], body.name, body.description, body.is_public)
        return col.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/collections/mine", tags=["collections"])
async def my_collections(current_user: dict = Depends(get_current_user)):
    """自分のコレクション一覧"""
    if not get_collection_store:
        return {"collections": []}
    uid = current_user["user_id"]
    return {"collections": get_collection_store().list_user_collections(uid, requester_id=uid)}


@app.get("/api/collections/{collection_id}", tags=["collections"])
async def get_collection(collection_id: str, current_user: dict = Depends(get_current_user)):
    """コレクション詳細（公開または自分のもの）"""
    if not get_collection_store:
        raise HTTPException(status_code=503, detail="コレクション機能が利用できません")
    col = get_collection_store().get_public(collection_id, current_user["user_id"])
    if not col:
        raise HTTPException(status_code=404, detail="コレクションが見つかりません")
    return col.to_dict()


@app.put("/api/collections/{collection_id}", tags=["collections"])
async def update_collection(collection_id: str, body: CollectionUpdateRequest, current_user: dict = Depends(get_current_user)):
    """コレクションを更新"""
    if not get_collection_store:
        raise HTTPException(status_code=503, detail="コレクション機能が利用できません")
    try:
        col = get_collection_store().update(
            collection_id, current_user["user_id"],
            name=body.name, description=body.description, is_public=body.is_public,
        )
        return col.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@app.delete("/api/collections/{collection_id}", tags=["collections"])
async def delete_collection(collection_id: str, current_user: dict = Depends(get_current_user)):
    """コレクションを削除"""
    if not get_collection_store:
        raise HTTPException(status_code=503, detail="コレクション機能が利用できません")
    try:
        ok = get_collection_store().delete(collection_id, current_user["user_id"])
        if not ok:
            raise HTTPException(status_code=404, detail="コレクションが見つかりません")
        return {"status": "deleted"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@app.post("/api/collections/{collection_id}/items/{item_id}", tags=["collections"])
async def add_collection_item(collection_id: str, item_id: str, current_user: dict = Depends(get_current_user)):
    """コレクションにアイテムを追加"""
    if not get_collection_store:
        raise HTTPException(status_code=503, detail="コレクション機能が利用できません")
    try:
        col = get_collection_store().add_item(collection_id, current_user["user_id"], item_id)
        return col.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@app.delete("/api/collections/{collection_id}/items/{item_id}", tags=["collections"])
async def remove_collection_item(collection_id: str, item_id: str, current_user: dict = Depends(get_current_user)):
    """コレクションからアイテムを削除"""
    if not get_collection_store:
        raise HTTPException(status_code=503, detail="コレクション機能が利用できません")
    try:
        col = get_collection_store().remove_item(collection_id, current_user["user_id"], item_id)
        return col.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@app.get("/api/users/{user_id}/collections", tags=["collections"])
async def user_public_collections(user_id: str, current_user: dict = Depends(get_current_user)):
    """ユーザーの公開コレクション一覧"""
    if not get_collection_store:
        return {"collections": []}
    return {"collections": get_collection_store().list_user_collections(user_id, requester_id=current_user["user_id"])}


# ===========================================================================
# ADMIN ENDPOINTS
# ===========================================================================

@app.get("/api/admin/users", tags=["admin"])
async def list_users(admin: dict = Depends(get_current_admin)):
    """全ユーザー一覧（管理者専用）"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    auth = get_auth_manager()
    users = auth.store.list_users()
    return {
        "users": [
            {
                "user_id": u.user_id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat(),
                "last_login": u.last_login.isoformat() if u.last_login else None,
                "failed_attempts": u.failed_attempts,
                "locked": u.is_locked(),
            }
            for u in users
        ],
        "total": len(users),
    }


class RoleChangeRequest(BaseModel):
    new_role: str


@app.put("/api/admin/users/{user_id}/role", tags=["admin"])
async def change_user_role(user_id: str, body: RoleChangeRequest, admin: dict = Depends(get_current_admin)):
    """ユーザーロールを変更（管理者専用）"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    try:
        auth = get_auth_manager()
        auth.change_role(admin, user_id, body.new_role)
        return {"user_id": user_id, "new_role": body.new_role, "status": "updated"}
    except (AuthError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/admin/users/{user_id}/verify-creator", tags=["admin"])
async def verify_creator(user_id: str, admin: dict = Depends(get_current_admin)):
    """クリエイター認証バッジを付与（管理者専用）"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    try:
        user = get_auth_manager().verify_creator(admin, user_id)
        return {"user_id": user_id, "is_creator_verified": user.is_creator_verified, "status": "verified"}
    except AuthError as e:
        raise HTTPException(status_code=404 if e.code == "not_found" else 403, detail=e.message) from e


@app.delete("/api/admin/users/{user_id}/verify-creator", tags=["admin"])
async def revoke_creator_verification(user_id: str, admin: dict = Depends(get_current_admin)):
    """クリエイター認証バッジを取り消し（管理者専用）"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    try:
        user = get_auth_manager().revoke_creator_verification(admin, user_id)
        return {"user_id": user_id, "is_creator_verified": user.is_creator_verified, "status": "revoked"}
    except AuthError as e:
        raise HTTPException(status_code=404 if e.code == "not_found" else 403, detail=e.message) from e


@app.delete("/api/admin/users/{user_id}", tags=["admin"])
async def delete_user(user_id: str, admin: dict = Depends(get_current_admin)):
    """ユーザーを削除（管理者専用）"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    auth = get_auth_manager()
    ok = auth.store.delete_user(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    return {"user_id": user_id, "status": "deleted"}


@app.get("/api/marketplace/favorites", tags=["marketplace"])
async def list_favorites(current_user: dict = Depends(get_current_user)):
    """お気に入りリスト（ブックマーク済みのリスティング）"""
    if not get_auth_manager or not get_marketplace:
        return {"items": [], "total": 0}
    bookmarks = get_auth_manager().get_bookmarks(current_user["user_id"])
    mp = get_marketplace()
    items = []
    for item_id in bookmarks:
        listing = mp.get_listing(item_id)
        if listing and listing.is_active:
            items.append(listing.to_dict())
    return {"items": items, "total": len(items)}


@app.post("/api/marketplace/{listing_id}/favorite", tags=["marketplace"], status_code=201)
async def add_favorite(listing_id: str, current_user: dict = Depends(get_current_user)):
    """リスティングをお気に入りに追加"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    listing = get_marketplace().get_listing(listing_id)
    if not listing or not listing.is_active:
        raise HTTPException(status_code=404, detail="リスティングが見つかりません")
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    get_auth_manager().add_bookmark(current_user["user_id"], listing_id)
    return {"status": "added", "listing_id": listing_id}


@app.delete("/api/marketplace/{listing_id}/favorite", tags=["marketplace"])
async def remove_favorite(listing_id: str, current_user: dict = Depends(get_current_user)):
    """リスティングをお気に入りから削除"""
    if not get_auth_manager:
        raise HTTPException(status_code=503, detail="認証モジュールが利用できません")
    get_auth_manager().remove_bookmark(current_user["user_id"], listing_id)
    return {"status": "removed", "listing_id": listing_id}


@app.get("/api/marketplace/analytics/me", tags=["marketplace"])
async def my_creator_analytics(current_user: dict = Depends(get_current_user)):
    """自分のクリエイターダッシュボード統計（タグ・カテゴリー別ダウンロード内訳を含む）"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    return get_marketplace().get_creator_analytics(current_user["user_id"])


@app.get("/api/admin/stats", tags=["admin"])
async def admin_stats(admin: dict = Depends(get_current_admin)):
    """システム統計（管理者専用）"""
    stats: Dict[str, Any] = {}

    if get_auth_manager:
        auth = get_auth_manager()
        users = auth.store.list_users()
        stats["users"] = {
            "total": len(users),
            "by_role": {r: sum(1 for u in users if u.role == r) for r in ("user", "moderator", "admin")},
            "active": sum(1 for u in users if u.is_active),
            "locked": sum(1 for u in users if u.is_locked()),
        }

    if get_marketplace:
        stats["marketplace"] = get_marketplace().get_stats()

    if get_search_index:
        stats["search"] = get_search_index().stats()

    if get_rate_limiter:
        stats["rate_limiter"] = get_rate_limiter().get_stats()

    return stats


@app.get("/api/admin/search/analytics", tags=["admin"])
async def search_analytics(
    top_n: int = Query(20, ge=1, le=100),
    admin: dict = Depends(get_current_admin),
):
    """検索クエリの統計情報を取得（管理者専用）"""
    if not get_search_index:
        raise HTTPException(status_code=503, detail="検索インデックスが利用できません")
    return get_search_index().query_analytics(top_n=top_n)


# ===========================================================================
# AUDIT TRAIL EXPORT
# ===========================================================================

@app.get("/api/admin/audit/export", tags=["admin"])
async def export_audit_log(
    fmt: str = Query("json", description="json または csv"),
    limit: int = Query(1000, ge=1, le=10000),
    admin: dict = Depends(get_current_admin),
):
    """監査ログをエクスポート（JSON/CSV）"""
    # Gather available security events
    events: List[Dict[str, Any]] = []

    if get_security_manager:
        try:
            sm = get_security_manager()
            sm.initialize()
            report = sm.get_security_report()
            raw_events = report.get("recent_events", [])
            events = raw_events[:limit]
        except Exception as e:
            logger.warning("Security manager unavailable for audit export: %s", e)

    # Fallback: synthetic audit event list
    if not events:
        events = [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "audit_export",
                "actor": admin.get("username", "admin"),
                "details": "Audit log export requested (no events recorded yet)",
            }
        ]

    if fmt == "csv":
        fieldnames = list(events[0].keys()) if events else ["timestamp", "event_type", "actor", "details"]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(events)
        buf.seek(0)
        filename = f"audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "total": len(events),
        "events": events,
    }


# ===========================================================================
# RATE LIMITER ADMIN
# ===========================================================================

@app.get("/api/admin/rate-limiter/stats", tags=["admin"])
async def rate_limiter_stats(admin: dict = Depends(get_current_admin)):
    """レートリミッター統計"""
    if not get_rate_limiter:
        return {"available": False}
    return get_rate_limiter().get_stats()


@app.delete("/api/admin/rate-limiter/{client_key}", tags=["admin"])
async def reset_rate_limit(client_key: str, admin: dict = Depends(get_current_admin)):
    """特定クライアントのレート制限をリセット（管理者専用）"""
    if not get_rate_limiter:
        raise HTTPException(status_code=503, detail="レートリミッターが利用できません")
    get_rate_limiter().reset_client(client_key)
    return {"client_key": client_key, "status": "reset"}


@app.get("/api/admin/reports", tags=["admin"])
async def list_reports(
    status: Optional[str] = Query(None, description="pending | resolved | dismissed"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: dict = Depends(get_current_admin),
):
    """モデレーション通報一覧（管理者専用）"""
    if not get_marketplace:
        return {"total": 0, "items": []}
    return get_marketplace().get_reports(status=status, limit=limit, offset=offset)


@app.get("/api/admin/reports/stats", tags=["admin"])
async def report_stats(admin: dict = Depends(get_current_admin)):
    """通報統計（管理者専用）"""
    if not get_marketplace:
        return {"total": 0, "by_status": {}, "by_reason": {}}
    return get_marketplace().get_report_stats()


@app.post("/api/admin/reports/{report_id}/resolve", tags=["admin"])
async def resolve_report(report_id: str, body: ResolveReportRequest, admin: dict = Depends(get_current_admin)):
    """通報を解決（管理者専用）。takedown=True でリスティングを取り下げ"""
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")
    try:
        report = get_marketplace().resolve_report(
            report_id, admin["user_id"], body.action, body.note, takedown=body.takedown
        )
        # If the listing was taken down, remove from search index and notify owner
        if body.takedown:
            listing = get_marketplace().get_listing(report.listing_id)
            if get_search_index:
                get_search_index().remove(report.listing_id)
            if listing and get_notification_queue:
                get_notification_queue().push(
                    listing.owner_id, "system",
                    "リスティングが削除されました",
                    f"「{listing.name}」はモデレーションにより削除されました",
                    {"listing_id": report.listing_id, "reason": report.reason},
                )
        return {"status": "resolved", "report": report.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/admin/listings/bulk", tags=["admin"])
async def bulk_listing_action(body: BulkListingActionRequest, admin: dict = Depends(get_current_admin)):
    """複数リスティングへの一括操作（管理者専用）。action: unpublish | delete"""
    if body.action not in ("unpublish", "delete"):
        raise HTTPException(status_code=400, detail="action は 'unpublish' または 'delete' である必要があります")
    if not body.listing_ids:
        raise HTTPException(status_code=400, detail="listing_ids は1件以上必要です")
    if len(body.listing_ids) > 200:
        raise HTTPException(status_code=400, detail="一度に処理できるのは最大200件です")
    if not get_marketplace:
        raise HTTPException(status_code=503, detail="マーケットプレイスが利用できません")

    mp = get_marketplace()
    succeeded: List[str] = []
    failed: List[Dict[str, str]] = []

    for lid in body.listing_ids:
        try:
            listing = mp.get_listing(lid)
            if listing is None:
                failed.append({"listing_id": lid, "reason": "not_found"})
                continue
            if body.action == "unpublish":
                with mp._lock:
                    listing.is_active = False
            else:
                with mp._lock:
                    mp._listings.pop(lid, None)
                if get_search_index:
                    get_search_index().remove(lid)
            if get_notification_queue and listing:
                verb = "削除" if body.action == "delete" else "非公開化"
                get_notification_queue().push(
                    listing.owner_id, "system",
                    f"リスティングが管理者により{verb}されました",
                    f"「{listing.name}」が管理者操作により{verb}されました",
                    {"listing_id": lid, "action": body.action},
                )
            succeeded.append(lid)
        except Exception as exc:
            failed.append({"listing_id": lid, "reason": str(exc)})

    return {
        "action": body.action,
        "succeeded": succeeded,
        "failed": failed,
        "success_count": len(succeeded),
        "failure_count": len(failed),
    }


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
