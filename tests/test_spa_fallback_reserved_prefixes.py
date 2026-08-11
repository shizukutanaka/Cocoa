"""SPA catch-all が バックエンド所有プレフィックスを覆い隠さないことの回帰テスト。

バグ: _BACKEND_RESERVED_PREFIXES が手書きの静的リストだったため、後から追加された
/live・/ready (k8s プローブ) が漏れ、/ready/x や /readyz が 404 ではなく
index.html (200 text/html) を返していた。監視/LB のヘルスチェックが常に成功と
誤判定する。/health/x は 404 を返しており挙動が食い違っていた。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from main import api_server  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(api_server.app, raise_server_exceptions=False)


def test_reserved_prefixes_cover_every_registered_route():
    """登録済みルートの第一セグメントは全て予約プレフィックスに含まれること。"""
    registered = set()
    for route in api_server.app.routes:
        path = getattr(route, "path", "")
        if not isinstance(path, str) or not path.startswith("/"):
            continue
        segment = path.strip("/").split("/", 1)[0]
        if segment and not segment.startswith("{"):
            registered.add(segment)

    missing = sorted(registered - set(api_server._BACKEND_RESERVED_PREFIXES))
    assert not missing, f"SPA フォールバックが覆い隠すバックエンドプレフィックス: {missing}"


@pytest.mark.parametrize("path", ["/live", "/ready", "/health"])
def test_probe_endpoints_are_json_not_spa_html(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert "application/json" in resp.headers.get("content-type", "")


@pytest.mark.parametrize("path", ["/ready/x", "/live/x", "/health/x"])
def test_unknown_path_under_backend_prefix_is_404(client, path):
    resp = client.get(path)
    assert resp.status_code == 404, (
        f"{path} が {resp.status_code} を返した "
        f"(content-type={resp.headers.get('content-type')}) — SPA フォールバックが漏れている"
    )
