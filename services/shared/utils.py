"""
共通ユーティリティ関数
全サービスで共有される汎用関数
"""

import re
import uuid


def generate_id() -> str:
    """一意のIDを生成"""
    return str(uuid.uuid4())


def validate_uuid(value: str) -> bool:
    """UUID形式を検証"""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError):
        return False


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """入力文字列をサニタイズ"""
    if not isinstance(text, str):
        return ""
    # 制御文字を除去
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # 長さ制限
    return text[:max_length]
