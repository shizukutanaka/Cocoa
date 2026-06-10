"""
軽量な依存性注入（DI）フレームワーク
FastAPI との統合を想定した実装

設計原則:
- シンプルで Pythonic
- 型安全性
- リクエストスコープとシングルトン対応
- FastAPI の Depends() と互換性
"""

import inspect
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union
from enum import Enum
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class Scope(Enum):
    """依存性のスコープ定義"""
    SINGLETON = "singleton"  # アプリケーション全体で1インスタンス
    REQUEST = "request"      # リクエストごとに新しいインスタンス
    TRANSIENT = "transient"  # 毎回新しいインスタンス


class Dependency:
    """依存性定義"""

    def __init__(
        self,
        factory: Callable[..., Any],
        scope: Scope = Scope.TRANSIENT,
        dependencies: Optional[Dict[str, 'Dependency']] = None
    ):
        self.factory = factory
        self.scope = scope
        self.dependencies = dependencies or {}
        self._instances: Dict[str, Any] = {}  # シングルトンの保存

    def get_instance(self, **kwargs) -> Any:
        """依存性のインスタンスを取得"""
        if self.scope == Scope.SINGLETON:
            key = "_singleton"
            if key not in self._instances:
                self._instances[key] = self.factory(**kwargs)
            return self._instances[key]
        # REQUEST / TRANSIENT
        return self.factory(**kwargs)

    def resolve_dependencies(self) -> Dict[str, Any]:
        """依存性を解決。Dependency オブジェクトは get_instance()、生の値はそのまま使用。"""
        resolved = {}
        for name, dep in self.dependencies.items():
            if isinstance(dep, Dependency):
                resolved[name] = dep.get_instance()
            else:
                resolved[name] = dep
        return resolved


class Container:
    """依存性注入コンテナ"""

    def __init__(self):
        self._dependencies: Dict[str, Dependency] = {}
        self._request_scoped: Dict[str, Any] = {}

    def register(
        self,
        interface: Union[Type[T], str],
        factory: Optional[Callable[..., T]] = None,
        scope: Scope = Scope.TRANSIENT,
        **kwargs
    ) -> None:
        """依存性を登録"""
        key = interface if isinstance(interface, str) else interface.__name__

        # factory未指定の場合は interface をファクトリーとして使用
        if factory is None:
            if isinstance(interface, str):
                raise ValueError(f"factory must be provided for string key: {interface}")
            factory = interface

        # 依存性を解析
        sig = inspect.signature(factory)
        dependencies = {}
        for param_name, _param in sig.parameters.items():
            if param_name in kwargs:
                dependencies[param_name] = kwargs[param_name]

        self._dependencies[key] = Dependency(factory, scope, dependencies)
        logger.debug(f"Registered {key} with scope {scope.value}")

    def resolve(self, interface: Union[Type[T], str]) -> T:
        """依存性を解決してインスタンスを取得"""
        key = interface if isinstance(interface, str) else interface.__name__

        if key not in self._dependencies:
            raise ValueError(f"No dependency registered for {key}")

        dep = self._dependencies[key]
        resolved_deps = dep.resolve_dependencies()
        return dep.get_instance(**resolved_deps)

    def get_request_scoped(self, key: str) -> Optional[Any]:
        """リクエストスコープの値を取得"""
        return self._request_scoped.get(key)

    def set_request_scoped(self, key: str, value: Any) -> None:
        """リクエストスコープの値を設定"""
        self._request_scoped[key] = value

    def clear_request_scoped(self) -> None:
        """リクエストスコープをクリア"""
        self._request_scoped.clear()


# グローバルコンテナ
_global_container: Optional[Container] = None


def get_container() -> Container:
    """グローバルコンテナを取得"""
    global _global_container
    if _global_container is None:
        _global_container = Container()
    return _global_container


def init_container() -> Container:
    """コンテナを初期化"""
    global _global_container
    _global_container = Container()
    return _global_container


def inject(interface: Union[Type[T], str], scope: Scope = Scope.TRANSIENT):
    """依存性注入デコレータ（FastAPI Depends() 互換）"""
    from functools import wraps

    def wrapper(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            container = get_container()
            instance = container.resolve(interface)
            kwargs[interface.__name__ if not isinstance(interface, str) else interface] = instance
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            container = get_container()
            instance = container.resolve(interface)
            kwargs[interface.__name__ if not isinstance(interface, str) else interface] = instance
            return func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return wrapper


# 使用例を示すサンプルクラス
class ConfigService:
    """設定サービス（サンプル）"""

    def __init__(self):
        from config import get_config
        self.config = get_config()

    def get_api_config(self):
        return self.config.api


class LogService:
    """ログサービス（サンプル）"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def log(self, level: str, message: str):
        getattr(self.logger, level.lower())(message)
