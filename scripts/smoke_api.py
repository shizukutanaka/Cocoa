#!/usr/bin/env python3
"""Probe every declared API route against a running server and fail on any 500.

Why this exists
---------------
Two real defects (FEATURE_AUDIT.md #64, #65) were found by mechanically calling
every route against a live server -- not by reading code, and not by the unit
suite, which mocks the very subsystems that broke. Both were in endpoints no
frontend page and no test exercised:

  * POST /api/admin/licenses/{key_id}/revoke -> 500 on every call (the handler
    read "sub" off the normalized auth payload, KeyError)
  * GET/POST /api/avatars* -> 500, or a fake empty 200, or a fake "created"
    response, when no database driver is installed

This script makes that sweep repeatable so the class cannot come back.

What counts as a failure
------------------------
Any 5xx that is NOT a deliberate, documented capability report. A 503 with an
explanatory detail is how this codebase reports "subsystem absent" (#47), so
503 is allowed; 500 never is. 4xx responses are expected and ignored -- probing
with a placeholder id or an empty body *should* yield 404/422/403.

Usage
-----
    # terminal 1
    cd /home/user/Cocoa
    COCOA_ADMIN_PASSWORD=AdminTest123! uvicorn main.api_server:app --port 8250

    # terminal 2
    python3 scripts/smoke_api.py --base http://127.0.0.1:8250 \
        --admin-password 'AdminTest123!'

Exits 0 when clean, 1 when any route answered 500 (and prints each one).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
API_SERVER = REPO_ROOT / "main" / "api_server.py"


def request(
    base: str, method: str, path: str, body: Optional[dict] = None, token: str = ""
) -> Tuple[int, str]:
    """Call the API. Returns (status, body-text); transport failures are -1."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()
    except Exception as exc:  # transport-level failure
        return -1, str(exc)


def declared_routes() -> List[Tuple[str, str]]:
    """Every (VERB, path) declared with an @app.<verb>("...") decorator."""
    source = API_SERVER.read_text(encoding="utf-8")
    routes: List[Tuple[str, str]] = []
    for verb in ("get", "post", "put", "delete", "patch"):
        for path in re.findall(rf'@app\.{verb}\("([^"]+)"', source):
            routes.append((verb.upper(), path))
    return sorted(set(routes))


def build_world(base: str, admin_password: str) -> Dict[str, Any]:
    """Create real objects so path parameters resolve to something that exists.

    Probing with a nonexistent id only ever exercises the not-found branch; a
    real listing/licence id reaches the code that actually does work, which is
    where #64 was hiding.
    """
    suffix = str(int(time.time()))
    seller, buyer = f"smoke_s_{suffix}", f"smoke_b_{suffix}"
    for name in (seller, buyer):
        request(base, "POST", "/api/auth/register",
                {"username": name, "email": f"{name}@example.com", "password": "OldPass123!"})

    def login(username: str, password: str) -> str:
        status, text = request(base, "POST", "/api/auth/login",
                               {"username": username, "password": password})
        if status != 200:
            raise SystemExit(f"login failed for {username}: {status} {text[:200]}")
        return json.loads(text)["access_token"]

    seller_token = login(seller, "OldPass123!")
    buyer_token = login(buyer, "OldPass123!")
    admin_token = login("admin", admin_password)

    seller_id = json.loads(request(base, "GET", "/api/auth/me", token=seller_token)[1])["user_id"]
    listing = json.loads(request(base, "POST", "/api/marketplace/publish", {
        "avatar_id": "smoke-avatar", "name": "Smoke Listing", "description": "smoke",
        "tags": ["smoke"], "category": "other", "parameters": {"p": 1},
    }, token=seller_token)[1])
    listing_id = listing.get("listing_id", "none")

    request(base, "POST", f"/api/marketplace/{listing_id}/download", {}, token=buyer_token)
    licences = json.loads(request(base, "GET", "/api/licenses/mine", token=buyer_token)[1])
    items = licences.get("items") or []
    key_id = items[0]["key_id"] if items else "none"

    return {
        "admin_token": admin_token,
        "substitutions": {
            "listing_id": listing_id,
            "user_id": seller_id,
            "key_id": key_id,
            "tag": "smoke",
            "category": "other",
            "username": "admin",
        },
    }


def fill(path: str, substitutions: Dict[str, str]) -> str:
    return re.sub(
        r"\{([^}:]+)(?::[^}]+)?\}",
        lambda m: str(substitutions.get(m.group(1), "none")),
        path,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="http://127.0.0.1:8250",
                        help="base URL of a running server")
    parser.add_argument("--admin-password", required=True,
                        help="value the server was started with as COCOA_ADMIN_PASSWORD")
    args = parser.parse_args()

    status, _ = request(args.base, "GET", "/health")
    if status != 200:
        print(f"server not reachable at {args.base} (/health returned {status})")
        return 1

    world = build_world(args.base, args.admin_password)
    token = world["admin_token"]
    substitutions = world["substitutions"]

    routes = declared_routes()
    failures: List[Tuple[int, str, str, str]] = []
    degraded: List[Tuple[str, str]] = []

    for verb, route in routes:
        path = fill(route, substitutions)
        # Empty object for writes: FastAPI answers 422 for a body that does not
        # validate, so anything that 500s here is a genuine defect.
        body = None if verb == "GET" else {}
        code, text = request(args.base, verb, path, body, token)
        if code == 503:
            degraded.append((f"{verb} {route}", text.strip()[:120]))
        elif code >= 500 or code == -1:
            failures.append((code, verb, route, text.strip()[:200]))

    print(f"probed {len(routes)} routes at {args.base}")
    if degraded:
        print(f"\n{len(degraded)} route(s) reported a capability as unavailable (503, allowed):")
        for name, detail in degraded:
            print(f"  {name}\n      {detail}")
    if failures:
        print(f"\nFAIL: {len(failures)} route(s) returned an unexpected 5xx:")
        for code, verb, route, text in failures:
            print(f"  {code} {verb} {route}\n      {text}")
        return 1

    print("\nOK: no unexpected 5xx")
    return 0


if __name__ == "__main__":
    sys.exit(main())
