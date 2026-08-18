#!/usr/bin/env python3
"""List backend endpoints that no frontend source file ever calls.

Why this exists
---------------
This repository's recurring defect is not a crash but a dead end: a feature is
finished on the server, users can put data into it, and nothing in the product
can ever read that data back out.

  #46  listing reports piled up in a queue with no console to adjudicate them
  #49  creator applications did the same
  #68  a commission dispute -- over paid work -- sat in the moderation queue
       forever, because the frontend had zero references to
       /api/admin/moderation

Each was found by hand, late. This script surfaces the whole class in one run
so the next one is noticed immediately.

Reading the output
------------------
An unreferenced endpoint is NOT automatically a bug. Three outcomes are all
legitimate, and the point is to make the decision consciously:

  wire it    a user can already create the data (a report, a dispute) and
             nobody can act on it -- that is the #46 / #68 dead end
  delete it  the part should not exist (Musk step 2). #57 declined to expose
             the favourites endpoints because wishlist already covers them
  leave it   deliberately server-only: operational endpoints, or a capability
             kept for API clients. Record WHY in FEATURE_AUDIT.md

Usage
-----
    python3 scripts/unwired_endpoints.py            # grouped summary
    python3 scripts/unwired_endpoints.py --all      # include wired ones too
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
API_SERVER = REPO_ROOT / "main" / "api_server.py"
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

Endpoint = Tuple[str, str]  # (VERB, path)


def backend_endpoints() -> Set[Endpoint]:
    source = API_SERVER.read_text(encoding="utf-8")
    found: Set[Endpoint] = set()
    for verb in ("get", "post", "put", "delete", "patch"):
        for path in re.findall(rf'@app\.{verb}\("([^"]+)"', source):
            if path.startswith("/api/"):
                found.add((verb.upper(), path))
    return found


def frontend_paths() -> Set[str]:
    """Every /api/... string literal or template literal in shipped frontend code.

    Test files are excluded: a path that only appears in a test is not wired
    into the product.
    """
    paths: Set[str] = set()
    for file in FRONTEND_SRC.rglob("*.ts*"):
        if ".test." in file.name:
            continue
        text = file.read_text(encoding="utf-8")
        paths.update(re.findall(r'["\'`](/api/[^"\'`]*)["\'`]', text))
    return paths


def matcher(path: str) -> re.Pattern:
    """Match a declared path against the frontend's interpolated form.

    `/api/x/{id}/y` has to match `/api/x/${listingId}/y`, so each path
    parameter becomes a wildcard that cannot span a quote character.
    """
    literal_parts = re.sub(r"\{[^}]+\}", "\x00", path).split("\x00")
    pattern = r"[^\"'`]*?".join(re.escape(part) for part in literal_parts)
    return re.compile("^" + pattern + "$")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--all", action="store_true", help="also list wired endpoints")
    args = parser.parse_args()

    declared = backend_endpoints()
    called = frontend_paths()

    unwired: List[Endpoint] = []
    wired: List[Endpoint] = []
    for verb, path in sorted(declared):
        pattern = matcher(path)
        (wired if any(pattern.match(c) for c in called) else unwired).append((verb, path))

    print(f"backend /api/ endpoints : {len(declared)}")
    print(f"called from frontend    : {len(wired)}")
    print(f"never called            : {len(unwired)}")

    admin = [e for e in unwired if e[1].startswith("/api/admin")]
    rest = [e for e in unwired if not e[1].startswith("/api/admin")]

    print(f"\n--- unwired admin/operational ({len(admin)}) ---")
    for verb, path in admin:
        print(f"  {verb:6} {path}")
    print(f"\n--- unwired user-facing ({len(rest)}) ---")
    for verb, path in rest:
        print(f"  {verb:6} {path}")

    if args.all:
        print(f"\n--- wired ({len(wired)}) ---")
        for verb, path in wired:
            print(f"  {verb:6} {path}")

    print(
        "\nAn unwired endpoint is not automatically a bug -- see this file's "
        "docstring.\nThe one that matters is: can a user already put data in "
        "with no way to get it out?"
    )
    # Informational by design: the judgement is human, so never fail a build.
    return 0


if __name__ == "__main__":
    sys.exit(main())
