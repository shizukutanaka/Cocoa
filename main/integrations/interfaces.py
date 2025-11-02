from __future__ import annotations

import abc
from typing import Iterable, Protocol

from .models import ConnectionParams, ControllerStatus, SceneInfo, SourceInfo


class StreamingController(abc.ABC):

    def __init__(self, params: ConnectionParams) -> None:
        self._params = params

    @property
    def params(self) -> ConnectionParams:
        return self._params

    @abc.abstractmethod
    async def connect(self) -> None:
        ...

    @abc.abstractmethod
    async def disconnect(self) -> None:
        ...

    @abc.abstractmethod
    async def status(self) -> ControllerStatus:
        ...

    @abc.abstractmethod
    async def list_scenes(self) -> Iterable[SceneInfo]:
        ...

    @abc.abstractmethod
    async def switch_scene(self, scene_name: str) -> None:
        ...

    @abc.abstractmethod
    async def list_sources(self, scene_name: str) -> Iterable[SourceInfo]:
        ...

    @abc.abstractmethod
    async def set_source_enabled(self, scene_name: str, source_name: str, enabled: bool) -> None:
        ...


class SupportsSyncController(Protocol):

    def connect(self) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def status(self) -> ControllerStatus:
        ...

    def list_scenes(self) -> Iterable[SceneInfo]:
        ...

    def switch_scene(self, scene_name: str) -> None:
        ...

    def list_sources(self, scene_name: str) -> Iterable[SourceInfo]:
        ...

    def set_source_enabled(self, scene_name: str, source_name: str, enabled: bool) -> None:
        ...
