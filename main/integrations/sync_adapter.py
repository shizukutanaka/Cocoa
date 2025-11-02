from __future__ import annotations

import asyncio
import threading
from typing import Any, Coroutine, Iterable, List

from .interfaces import StreamingController, SupportsSyncController
from .models import ControllerStatus, SceneInfo, SourceInfo


class _LoopWorker:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro: Coroutine[Any, Any, Any]) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def stop(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join()
        self._loop.close()


class SyncStreamingControllerAdapter(SupportsSyncController):
    def __init__(self, controller: StreamingController) -> None:
        self._controller = controller
        self._worker = _LoopWorker()

    def controller(self) -> StreamingController:
        return self._controller

    def connect(self) -> None:
        self._worker.run(self._controller.connect())

    def disconnect(self) -> None:
        self._worker.run(self._controller.disconnect())

    def status(self) -> ControllerStatus:
        return self._worker.run(self._controller.status())

    def list_scenes(self) -> Iterable[SceneInfo]:
        result: List[SceneInfo] = list(self._worker.run(self._controller.list_scenes()))
        return result

    def switch_scene(self, scene_name: str) -> None:
        self._worker.run(self._controller.switch_scene(scene_name))

    def list_sources(self, scene_name: str) -> Iterable[SourceInfo]:
        result: List[SourceInfo] = list(self._worker.run(self._controller.list_sources(scene_name)))
        return result

    def set_source_enabled(self, scene_name: str, source_name: str, enabled: bool) -> None:
        self._worker.run(self._controller.set_source_enabled(scene_name, source_name, enabled))

    def close(self) -> None:
        try:
            self.disconnect()
        finally:
            self._worker.stop()
