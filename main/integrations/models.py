from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(slots=True)
class SourceInfo:
    name: str
    enabled: bool
    kind: Optional[str] = None
    group: Optional[str] = None


@dataclass(slots=True)
class SceneInfo:
    name: str
    is_active: bool
    sources: List[SourceInfo] = field(default_factory=list)


@dataclass(slots=True)
class ControllerStatus:
    connected: bool
    latency_ms: Optional[float] = None
    last_error: Optional[str] = None
    last_heartbeat: Optional[datetime] = None


@dataclass(slots=True)
class ConnectionParams:
    host: str = "127.0.0.1"
    port: int = 4455
    password: Optional[str] = None
    use_ssl: bool = False
    reconnect_attempts: int = 3
    reconnect_interval: float = 3.0
    auto_reconnect: bool = True
    heartbeat_interval: int = 5
    request_timeout: float = 10.0
