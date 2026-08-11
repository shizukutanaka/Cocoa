"""Regression tests: unauthenticated access must return 401, never 500.

``security = HTTPBearer(auto_error=False)`` makes FastAPI pass ``None`` when the
Authorization header is missing or not a Bearer header. Endpoints that reached
into ``credentials.credentials`` directly raised AttributeError -> HTTP 500 for
an anonymous caller. ``_bearer_token()`` now normalises that to 401.
"""

import pytest
from fastapi.testclient import TestClient

from main.api_server import app, _bearer_token

client = TestClient(app)

# Endpoints that previously raised AttributeError -> 500 when unauthenticated.
PREVIOUSLY_500 = [
    "/api/membership",
    "/api/admin/membership",
    "/api/admin/membership/distribution",
    "/api/refunds/mine",
    "/api/admin/refunds",
    "/api/gift-cards/mine",
]


@pytest.mark.parametrize("path", PREVIOUSLY_500)
def test_unauthenticated_returns_401_not_500(path):
    resp = client.get(path)
    assert resp.status_code == 401, f"{path} -> {resp.status_code}: {resp.text[:200]}"


@pytest.mark.parametrize("header", [
    {},                                    # no Authorization header at all
    {"Authorization": "Bearer "},          # Bearer with empty token
    {"Authorization": "Basic abc"},        # wrong scheme -> HTTPBearer yields None
])
def test_malformed_auth_header_is_401(header):
    resp = client.get("/api/membership", headers=header)
    assert resp.status_code == 401


def test_no_get_route_returns_5xx_when_unauthenticated():
    """Whole-surface sweep: no parameterless GET may 5xx for an anonymous caller."""
    failures = []
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        if "GET" not in methods or "{" in route.path:
            continue
        try:
            resp = client.get(route.path)
        except Exception as exc:  # unhandled -> would be a 500 in production
            failures.append((route.path, repr(exc)[:120]))
            continue
        if resp.status_code >= 500:
            failures.append((route.path, resp.status_code))
    assert not failures, f"routes 5xx-ing while unauthenticated: {failures}"


def test_bearer_token_helper_rejects_none():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        _bearer_token(None)
    assert ei.value.status_code == 401


def test_bearer_token_helper_returns_token():
    class Creds:
        credentials = "tok123"

    assert _bearer_token(Creds()) == "tok123"
