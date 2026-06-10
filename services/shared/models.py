"""
共通データモデル
全サービスで共有されるデータ構造
"""

import json
import uuid
from datetime import datetime

try:
    from sqlalchemy import (
        JSON,
        Boolean,
        Column,
        DateTime,
        Float,
        ForeignKey,
        Integer,
        String,
        Text,
    )
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import relationship
    SQLALCHEMY_AVAILABLE = True
    Base = declarative_base()
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    Base = object
    Column = String = Integer = Boolean = Float = Text = JSON = DateTime = ForeignKey = None
    relationship = lambda *a, **kw: None  # noqa: E731


class BaseModel:
    """ベースモデル"""

    def to_dict(self) -> dict:
        """辞書形式に変換"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result

    def to_json(self) -> str:
        """JSON文字列に変換"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class User(Base, BaseModel):
    """ユーザーモデル"""
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100))
    avatar_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)

    # リレーションシップ
    avatars = relationship("Avatar", back_populates="user")
    collaborations = relationship("CollaborationSession", back_populates="user")


class Avatar(Base, BaseModel):
    """アバターモデル"""
    __tablename__ = "avatars"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text)
    parameters = Column(JSON, nullable=False)  # アバターパラメータのJSON
    thumbnail_url = Column(String(500))
    model_url = Column(String(500))
    file_size = Column(Integer)  # ファイルサイズ（バイト）
    is_public = Column(Boolean, default=False)
    is_template = Column(Boolean, default=False)
    tags = Column(JSON)  # タグリスト
    category = Column(String(50))
    version = Column(String(20), default="1.0.0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # リレーションシップ
    user_id = Column(String, ForeignKey("users.id"))
    user = relationship("User", back_populates="avatars")
    presets = relationship("Preset", back_populates="avatar")
    collaborations = relationship("CollaborationSession", back_populates="avatar")


class Preset(Base, BaseModel):
    """プリセットモデル"""
    __tablename__ = "presets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text)
    parameters = Column(JSON, nullable=False)  # プリセットパラメータのJSON
    avatar_id = Column(String, ForeignKey("avatars.id"))
    avatar = relationship("Avatar", back_populates="presets")
    user_id = Column(String, ForeignKey("users.id"))
    user = relationship("User")
    is_public = Column(Boolean, default=False)
    is_system = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0)
    rating = Column(Float)  # 平均評価
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # リレーションシップ
    history = relationship("PresetHistory", back_populates="preset")


class PresetHistory(Base, BaseModel):
    """プリセット変更履歴"""
    __tablename__ = "preset_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    preset_id = Column(String, ForeignKey("presets.id"))
    preset = relationship("Preset", back_populates="history")
    action = Column(String(50), nullable=False)  # create, update, delete
    old_parameters = Column(JSON)  # 変更前のパラメータ
    new_parameters = Column(JSON)  # 変更後のパラメータ
    changed_by = Column(String, ForeignKey("users.id"))
    user = relationship("User")
    change_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class CollaborationSession(Base, BaseModel):
    """コラボレーションセッション"""
    __tablename__ = "collaboration_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text)
    avatar_id = Column(String, ForeignKey("avatars.id"))
    avatar = relationship("Avatar", back_populates="collaborations")
    user_id = Column(String, ForeignKey("users.id"))
    user = relationship("User", back_populates="collaborations")
    is_active = Column(Boolean, default=True)
    max_participants = Column(Integer, default=10)
    current_participants = Column(Integer, default=0)
    session_type = Column(String(50))  # editing, review, presentation
    settings = Column(JSON)  # セッション設定
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime)

    # リレーションシップ
    participants = relationship("CollaborationParticipant", back_populates="session")
    messages = relationship("CollaborationMessage", back_populates="session")


class CollaborationParticipant(Base, BaseModel):
    """コラボレーション参加者"""
    __tablename__ = "collaboration_participants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("collaboration_sessions.id"))
    session = relationship("CollaborationSession", back_populates="participants")
    user_id = Column(String, ForeignKey("users.id"))
    user = relationship("User")
    role = Column(String(50), default="participant")  # owner, moderator, participant
    permissions = Column(JSON)  # 権限設定
    joined_at = Column(DateTime, default=datetime.utcnow)
    left_at = Column(DateTime)


class CollaborationMessage(Base, BaseModel):
    """コラボレーションメッセージ"""
    __tablename__ = "collaboration_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("collaboration_sessions.id"))
    session = relationship("CollaborationSession", back_populates="messages")
    user_id = Column(String, ForeignKey("users.id"))
    user = relationship("User")
    message_type = Column(String(50))  # text, system, file, voice
    content = Column(Text)
    metadata = Column(JSON)  # メッセージメタデータ（ファイル情報など）
    created_at = Column(DateTime, default=datetime.utcnow)


class AIModel(Base, BaseModel):
    """AIモデル情報"""
    __tablename__ = "ai_models"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    model_type = Column(String(50), nullable=False)  # avatar_generation, parameter_optimization, etc.
    version = Column(String(20), nullable=False)
    model_path = Column(String(500), nullable=False)
    config = Column(JSON)  # モデル設定
    is_active = Column(Boolean, default=True)
    accuracy = Column(Float)  # 精度スコア
    training_data_size = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIGeneration(Base, BaseModel):
    """AI生成結果"""
    __tablename__ = "ai_generations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id = Column(String, ForeignKey("ai_models.id"))
    model = relationship("AIModel")
    user_id = Column(String, ForeignKey("users.id"))
    user = relationship("User")
    generation_type = Column(String(50), nullable=False)  # avatar, parameters, optimization
    input_data = Column(JSON, nullable=False)  # 入力データ
    output_data = Column(JSON, nullable=False)  # 生成結果
    parameters = Column(JSON)  # 生成パラメータ
    quality_score = Column(Float)  # 品質スコア
    processing_time_ms = Column(Integer)  # 処理時間（ミリ秒）
    created_at = Column(DateTime, default=datetime.utcnow)
