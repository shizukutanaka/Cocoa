"""Regression: unauthenticated requests must return 401, never 500.

``api_server.security`` is ``HTTPBearer(auto_error=False)``, so FastAPI passes
``None`` into the endpoint when the Authorization header is absent or
malformed. Endpoints that dereferenced ``credentials.credentials`` directly
raised ``AttributeError: 'NoneType' object has no attribute 'credentials'``,
which the global handler turned into a 500 for what is plainly a 401.

The ``_bearer_token()`` helper performs the None-check and raises 401. This
test pins that contract: reverting an endpoint to ``credentials.credentials``
makes it fail with 500.
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "main"))

fastapi_testclient = pytest.importorskip("fastapi.testclient")
api_server = pytest.importorskip("api_server")

TestClient = fastapi_testclient.TestClient

# Bearer-protected GET endpoints that take credentials via Depends(security).
PROTECTED_GET_PATHS = [
    "/api/membership",
]


@pytest.fixture(scope="module")
def client():
    return TestClient(api_server.app, raise_server_exceptions=False)


@pytest.mark.parametrize("path", PROTECTED_GET_PATHS)
def test_missing_auth_header_is_401_not_500(client, path):
    resp = client.get(path)
    assert resp.status_code != 500, (
        f"{path} returned 500 for a missing Authorization header; "
        "the endpoint likely dereferences credentials.credentials without "
        "going through _bearer_token()"
    )
    assert resp.status_code in (401, 503)


@pytest.mark.parametrize("path", PROTECTED_GET_PATHS)
def test_malformed_auth_header_is_401_not_500(client, path):
    # Not a Bearer scheme -> HTTPBearer(auto_error=False) yields None again.
    resp = client.get(path, headers={"Authorization": "Basic abc123"})
    assert resp.status_code != 500
    assert resp.status_code in (401, 503)


def test_bearer_token_helper_rejects_none():
    with pytest.raises(api_server.HTTPException) as exc:
        api_server._bearer_token(None)
    assert exc.value.status_code == 401


def test_bearer_token_helper_rejects_empty_credential():
    class _Empty:
        credentials = ""

    with pytest.raises(api_server.HTTPException) as exc:
        api_server._bearer_token(_Empty())
    assert exc.value.status_code == 401


def test_bearer_token_helper_returns_raw_token():
    class _Creds:
        credentials = "tok-123"

    assert api_server._bearer_token(_Creds()) == "tok-123"
