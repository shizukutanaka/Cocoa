"""
Avatar Service
アバターの管理、プリセット処理、AI生成などの機能を提供
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException

from services.shared.config import get_config
from services.shared.database import DatabaseManager
from services.shared.logger import setup_logging
from services.shared.models import Avatar, Preset, PresetHistory

# グローバル変数
app: Optional[FastAPI] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションライフサイクル管理"""
    # スタートアップ
    setup_logging()
    logger = logging.getLogger(__name__)

    # データベース初期化
    db_manager = DatabaseManager()
    await db_manager.initialize()

    logger.info("Avatar Service started")

    yield

    # シャットダウン
    await db_manager.close()
    logger.info("Avatar Service stopped")


def create_app() -> FastAPI:
    """FastAPIアプリケーション作成"""
    global app

    config = get_config()

    app_settings = {
        "title": "Cocoa Avatar Service",
        "description": "アバター管理サービス",
        "version": "2.1.0",
        "debug": config.services["avatar-service"].debug
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


# アバター関連エンドポイント
@app.post("/api/v1/avatars")
async def create_avatar(
    avatar_data: dict,
    current_user: Dict[str, Any] = Depends(lambda: {"id": "user_123"}),
    db = Depends(get_database)
):
    """新しいアバターを作成"""
    try:
        # アバターオブジェクト作成
        avatar = Avatar(
            name=avatar_data["name"],
            description=avatar_data.get("description"),
            parameters=avatar_data["parameters"],
            user_id=current_user["id"],
            is_public=avatar_data.get("is_public", False),
            category=avatar_data.get("category"),
            tags=avatar_data.get("tags", [])
        )

        # データベースに保存
        db.add(avatar)
        await db.commit()
        await db.refresh(avatar)

        return {
            "success": True,
            "avatar": avatar.to_dict(),
            "message": "アバターが正常に作成されました"
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"アバター作成エラー: {str(e)}") from e


@app.get("/api/v1/avatars")
async def list_avatars(
    user_id: Optional[str] = None,
    category: Optional[str] = None,
    is_public: Optional[bool] = None,
    page: int = 1,
    per_page: int = 20,
    current_user: Dict[str, Any] = Depends(lambda: {"id": "user_123"}),
    db = Depends(get_database)
):
    """アバター一覧を取得"""
    try:
        query = db.query(Avatar)

        # フィルター適用
        if user_id:
            query = query.filter(Avatar.user_id == user_id)
        elif not current_user.get("is_admin", False):
            # 管理者以外は自分のアバターか公開アバターのみ
            query = query.filter(
                (Avatar.user_id == current_user["id"]) |
                (Avatar.is_public.is_(True))
            )

        if category:
            query = query.filter(Avatar.category == category)

        if is_public is not None:
            query = query.filter(Avatar.is_public == is_public)

        # ページネーション
        offset = (page - 1) * per_page
        avatars = await query.offset(offset).limit(per_page).all()

        return {
            "avatars": [avatar.to_dict() for avatar in avatars],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": len(avatars)  # 本来はcountクエリが必要
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"アバター一覧取得エラー: {str(e)}") from e


@app.get("/api/v1/avatars/{avatar_id}")
async def get_avatar(
    avatar_id: str,
    current_user: Dict[str, Any] = Depends(lambda: {"id": "user_123"}),
    db = Depends(get_database)
):
    """特定のアバターを取得"""
    try:
        avatar = await db.query(Avatar).filter(Avatar.id == avatar_id).first()

        if not avatar:
            raise HTTPException(status_code=404, detail="アバターが見つかりません")

        # アクセス権限チェック
        if not avatar.is_public and avatar.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="アクセス権限がありません")

        return avatar.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"アバター取得エラー: {str(e)}") from e


@app.put("/api/v1/avatars/{avatar_id}")
async def update_avatar(
    avatar_id: str,
    avatar_data: dict,
    current_user: Dict[str, Any] = Depends(lambda: {"id": "user_123"}),
    db = Depends(get_database)
):
    """アバターを更新"""
    try:
        avatar = await db.query(Avatar).filter(Avatar.id == avatar_id).first()

        if not avatar:
            raise HTTPException(status_code=404, detail="アバターが見つかりません")

        # 所有権チェック
        if avatar.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="更新権限がありません")

        # 更新処理
        for key, value in avatar_data.items():
            if hasattr(avatar, key):
                setattr(avatar, key, value)

        avatar.updated_at = datetime.now(timezone.utc)
        await db.commit()

        return {
            "success": True,
            "avatar": avatar.to_dict(),
            "message": "アバターが正常に更新されました"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"アバター更新エラー: {str(e)}") from e


@app.delete("/api/v1/avatars/{avatar_id}")
async def delete_avatar(
    avatar_id: str,
    current_user: Dict[str, Any] = Depends(lambda: {"id": "user_123"}),
    db = Depends(get_database)
):
    """アバターを削除"""
    try:
        avatar = await db.query(Avatar).filter(Avatar.id == avatar_id).first()

        if not avatar:
            raise HTTPException(status_code=404, detail="アバターが見つかりません")

        # 所有権チェック
        if avatar.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="削除権限がありません")

        # 削除処理
        await db.delete(avatar)
        await db.commit()

        return {
            "success": True,
            "message": "アバターが正常に削除されました"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"アバター削除エラー: {str(e)}") from e


# プリセット関連エンドポイント
@app.post("/api/v1/presets")
async def create_preset(
    preset_data: dict,
    current_user: Dict[str, Any] = Depends(lambda: {"id": "user_123"}),
    db = Depends(get_database)
):
    """新しいプリセットを作成"""
    try:
        # アバター存在確認
        avatar = await db.query(Avatar).filter(Avatar.id == preset_data["avatar_id"]).first()
        if not avatar:
            raise HTTPException(status_code=404, detail="指定されたアバターが見つかりません")

        # プリセットオブジェクト作成
        preset = Preset(
            name=preset_data["name"],
            description=preset_data.get("description"),
            parameters=preset_data["parameters"],
            avatar_id=preset_data["avatar_id"],
            user_id=current_user["id"],
            is_public=preset_data.get("is_public", False)
        )

        # データベースに保存
        db.add(preset)
        await db.commit()
        await db.refresh(preset)

        # 履歴記録
        history = PresetHistory(
            preset_id=preset.id,
            action="create",
            new_parameters=preset.parameters,
            changed_by=current_user["id"]
        )
        db.add(history)
        await db.commit()

        return {
            "success": True,
            "preset": preset.to_dict(),
            "message": "プリセットが正常に作成されました"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"プリセット作成エラー: {str(e)}") from e


@app.get("/api/v1/presets/{preset_id}")
async def get_preset(
    preset_id: str,
    current_user: Dict[str, Any] = Depends(lambda: {"id": "user_123"}),
    db = Depends(get_database)
):
    """特定のプリセットを取得"""
    try:
        preset = await db.query(Preset).filter(Preset.id == preset_id).first()

        if not preset:
            raise HTTPException(status_code=404, detail="プリセットが見つかりません")

        # アクセス権限チェック
        if not preset.is_public and preset.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="アクセス権限がありません")

        return preset.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"プリセット取得エラー: {str(e)}") from e


# AI生成エンドポイント
@app.post("/api/v1/avatars/generate")
async def generate_avatar_with_ai(
    generation_data: dict,
    current_user: Dict[str, Any] = Depends(lambda: {"id": "user_123"}),
    db = Depends(get_database)
):
    """AIでアバターを生成"""
    try:
        # AIサービスを呼び出す（実際の実装では別サービスを呼び出す）
        # ここではモックとして実装

        generated_avatar = {
            "name": f"AI生成アバター_{current_user['id']}",
            "description": "AIによって自動生成されたアバター",
            "parameters": generation_data.get("parameters", {}),
            "user_id": current_user["id"],
            "is_public": False,
            "category": "ai_generated",
            "tags": ["ai", "generated"]
        }

        avatar = Avatar(**generated_avatar)
        db.add(avatar)
        await db.commit()
        await db.refresh(avatar)

        return {
            "success": True,
            "avatar": avatar.to_dict(),
            "message": "AIアバターが正常に生成されました"
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"AIアバター生成エラー: {str(e)}") from e


# ヘルスチェック
@app.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {"status": "healthy", "service": "avatar-service"}


def main():
    """メイン関数"""
    config = get_config()
    service_config = config.services["avatar-service"]

    uvicorn.run(
        "services.avatar_service:app",
        host=service_config.host,
        port=service_config.port,
        reload=service_config.debug,
        log_level="info"
    )


if __name__ == "__main__":
    main()
