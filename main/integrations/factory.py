from __future__ import annotations

from typing import Any, Dict, Optional

from .interfaces import StreamingController
from .models import ConnectionParams
from .obs_controller import OBSController


def create_controller(target: str, params: ConnectionParams) -> StreamingController:
    lowered = (target or "").strip().lower()
    if lowered == "obs":
        return OBSController(params)
    if lowered == "obc":
        raise NotImplementedError("OBC controller is not yet implemented")
    raise ValueError(f"Unsupported streaming target: {target}")


def build_controller_from_config(config: Dict[str, Any]) -> Optional[StreamingController]:
    if not config or not config.get("enabled", False):
        return None
    connection = config.get("connection", {})
    options = config.get("options", {})
    params = ConnectionParams(
        host=str(connection.get("host", "127.0.0.1")),
        port=int(connection.get("port", 4455)),
        password=connection.get("password") or None,
        use_ssl=bool(connection.get("use_ssl", False)),
        reconnect_attempts=int(connection.get("reconnect_attempts", 3)),
        reconnect_interval=float(connection.get("reconnect_interval", 3)),
        auto_reconnect=bool(options.get("auto_reconnect", True)),
        heartbeat_interval=int(options.get("heartbeat_interval", 5)),
        request_timeout=float(options.get("request_timeout", 10.0)),
    )
    target = config.get("target", "obs")
    return create_controller(target, params)
