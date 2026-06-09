"""
API Gateway Service
全マイクロサービスへのリクエストをルーティングし、認証・認可を管理
"""

import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import uvicorn
from contextlib import asynccontextmanager

from services.shared.config import get_config
from services.shared.logger import setup_logging


# グローバル変数
app: Optional[FastAPI] = None
http_client: Optional[httpx.AsyncClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションライフサイクル管理"""
    global http_client

    # スタートアップ
    setup_logging()
    logger = logging.getLogger(__name__)

    # HTTPクライアント初期化
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
    )

    logger.info("API Gateway started")

    yield

    # シャットダウン
    if http_client:
        await http_client.aclose()
    logger.info("API Gateway stopped")


def create_app() -> FastAPI:
    """FastAPIアプリケーション作成"""
    global app

    config = get_config()

    # アプリケーション設定
    app_settings = {
        "title": "Cocoa API Gateway",
        "description": "エンタープライズグレードのアバター管理システム API Gateway",
        "version": "2.1.0",
        "debug": config.services["api-gateway"].debug
    }

    app = FastAPI(
        **app_settings,
        lifespan=lifespan
    )

    # CORS設定
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 本番環境では適切に制限する
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


def get_app() -> FastAPI:
    """アプリケーション取得"""
    global app
    if app is None:
        app = create_app()
    return app


# 依存関係関数
async def get_current_user(request: Request) -> Dict[str, Any]:
    """現在のユーザーを取得"""
    # JWTトークンからユーザー情報を取得するロジックを実装
    # ここでは簡易的に実装
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です"
        )

    token = auth_header.split(" ")[1]
    # JWT検証ロジックを実装（ここでは簡易的に）
    if token == "invalid":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効なトークンです"
        )

    return {"id": "user_123", "username": "test_user"}


# ヘルスチェックエンドポイント
@app.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {"status": "healthy", "service": "api-gateway"}


@app.get("/api/v1/health")
async def api_health_check():
    """APIヘルスチェック"""
    return {"status": "healthy", "version": "2.1.0"}


# サービスプロキシ
async def proxy_to_service(service_name: str, path: str, method: str = "GET", **kwargs) -> Dict[str, Any]:
    """サービスへのプロキシ"""
    global http_client

    if not http_client:
        raise HTTPException(status_code=500, detail="HTTPクライアントが初期化されていません")

    config = get_config()
    service_config = config.services[service_name]

    # サービスURL構築
    service_url = f"http://{service_config.host}:{service_config.port}{path}"

    try:
        # リクエスト実行
        response = await http_client.request(
            method=method,
            url=service_url,
            **kwargs
        )

        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
        }

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"{service_name}へのリクエストがタイムアウトしました")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"{service_name}に接続できません")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{service_name}へのリクエストでエラーが発生しました: {str(e)}")


# アバターサービスプロキシ
@app.api_route("/api/v1/avatars/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_avatar_service(path: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """アバターサービスへのプロキシ"""
    return await proxy_to_service(
        "avatar-service",
        f"/api/v1/avatars/{path}",
        method=request.method,
        headers=dict(request.headers),
        json=await request.json() if request.method in ["POST", "PUT"] else None
    )


# セキュリティサービスプロキシ
@app.api_route("/api/v1/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_security_service(path: str, request: Request):
    """セキュリティサービスへのプロキシ"""
    return await proxy_to_service(
        "security-service",
        f"/api/v1/auth/{path}",
        method=request.method,
        headers=dict(request.headers),
        json=await request.json() if request.method in ["POST", "PUT"] else None
    )


# コラボレーションサービスプロキシ
@app.api_route("/api/v1/collaboration/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_collaboration_service(path: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """コラボレーションサービスへのプロキシ"""
    return await proxy_to_service(
        "collaboration-service",
        f"/api/v1/collaboration/{path}",
        method=request.method,
        headers=dict(request.headers),
        json=await request.json() if request.method in ["POST", "PUT"] else None
    )


# AIサービスプロキシ
@app.api_route("/api/v1/ai/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_ai_service(path: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """AIサービスへのプロキシ"""
    return await proxy_to_service(
        "ai-service",
        f"/api/v1/ai/{path}",
        method=request.method,
        headers=dict(request.headers),
        json=await request.json() if request.method in ["POST", "PUT"] else None
    )


# ブロックチェーンサービスプロキシ
@app.api_route("/api/v1/blockchain/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_blockchain_service(path: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """ブロックチェーンサービスへのプロキシ"""
    return await proxy_to_service(
        "blockchain-service",
        f"/api/v1/blockchain/{path}",
        method=request.method,
        headers=dict(request.headers),
        json=await request.json() if request.method in ["POST", "PUT"] else None
    )


# エラーハンドラー
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP例外ハンドラー"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "type": "http_exception"}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """一般例外ハンドラー"""
    logger = logging.getLogger(__name__)
    logger.error(f"予期しないエラー: {str(exc)}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={"detail": "内部サーバーエラー", "type": "internal_error"}
    )


def main():
    """メイン関数"""
    config = get_config()
    service_config = config.services["api-gateway"]

    uvicorn.run(
        "services.api_gateway:app",
        host=service_config.host,
        port=service_config.port,
        reload=service_config.debug,
        log_level=config.security.get("log_level", "info").lower()
    )


if __name__ == "__main__":
    main()
