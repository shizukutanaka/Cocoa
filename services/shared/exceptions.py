"""
共通例外クラス
全サービスで共有される例外定義
"""


class CocoaError(Exception):
    """Cocoa 基底例外"""

    def __init__(self, message: str, code: str = "COCOA_ERROR"):
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict:
        return {"error": self.code, "message": self.message}


class ValidationError(CocoaError):
    """バリデーションエラー"""

    def __init__(self, message: str, field: str = ""):
        super().__init__(message, "VALIDATION_ERROR")
        self.field = field

    def to_dict(self) -> dict:
        d = super().to_dict()
        if self.field:
            d["field"] = self.field
        return d


class SecurityError(CocoaError):
    """セキュリティエラー"""

    def __init__(self, message: str):
        super().__init__(message, "SECURITY_ERROR")


class NotFoundError(CocoaError):
    """リソース未発見エラー"""

    def __init__(self, resource: str, resource_id: str = ""):
        message = f"{resource} が見つかりません"
        if resource_id:
            message += f": {resource_id}"
        super().__init__(message, "NOT_FOUND")
        self.resource = resource
        self.resource_id = resource_id


class AuthenticationError(CocoaError):
    """認証エラー"""

    def __init__(self, message: str = "認証に失敗しました"):
        super().__init__(message, "AUTHENTICATION_ERROR")


class AuthorizationError(CocoaError):
    """認可エラー"""

    def __init__(self, message: str = "アクセス権限がありません"):
        super().__init__(message, "AUTHORIZATION_ERROR")
