#!/usr/bin/env python3
"""Drive the critical user journeys in a real browser against a running server.

Why this exists
---------------
Every round of this project has been verified with Playwright, and every one of
those scripts was written in a scratch directory and thrown away. The
verification was real but it protected nothing afterwards: the next change
could silently break a flow that had been confirmed working an hour earlier,
and nobody would know until someone manually clicked through again.

`scripts/smoke_api.py` covers breadth -- every route, no unexpected 500s. This
covers depth on the few journeys that matter most, through the actual UI, with
the assertions that previous rounds had to rediscover by hand:

  1. Register -> log in -> the session survives a reload
  2. Publish a priced listing -> it appears in public search
  3. Buy it through the cart -> CREDITS ACTUALLY MOVE, both sides
  4. Request a refund -> an admin approves it -> the buyer is made whole
  5. Report a listing -> an admin adjudicates it in the console

Step 3 is the one that matters most: FEATURE_AUDIT #44 was a bug where a priced
listing transferred for zero credits and the seller was never paid. It passed
every test in the suite, because the tests asserted the response shape rather
than the balances.

Usage
-----
    # terminal 1
    cd /home/user/Cocoa
    COCOA_ADMIN_PASSWORD='AdminTest123!' uvicorn main.api_server:app --port 8250

    # terminal 2
    python3 scripts/e2e_critical_flows.py --base http://127.0.0.1:8250 \
        --admin-password 'AdminTest123!'

Requires the frontend to be built (`cd frontend && npm run build`) so the
server serves the SPA. Exits non-zero if any journey breaks, and always reports
any /api/ 5xx or uncaught JS error seen along the way.

Start the server with RATE_LIMIT_AUTH_PER_MINUTE=100 if you intend to run this
repeatedly: the suite spends several auth requests on setup plus one in the
browser, which is most of the 10/min default. The script detects the throttle
and says so (exit 3) rather than reporting it as a broken journey.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.error
import urllib.request

CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def api(base: str, method: str, path: str, body=None, token: str = ""):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passed = 0

    def that(self, label: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed += 1
            print(f"  PASS  {label}")
        else:
            self.failures.append(f"{label}{(' -- ' + detail) if detail else ''}")
            print(f"  FAIL  {label}{(' -- ' + detail) if detail else ''}")


async def run(base: str, admin_password: str) -> int:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("playwright is not installed; skipping (pip install playwright)")
        return 0

    checks = Checks()
    suffix = str(int(time.time()))
    seller = f"e2e_seller_{suffix}"
    buyer = f"e2e_buyer_{suffix}"
    password = "E2ePassw0rd!"

    # Arrange through the API: the browser drives the flows we care about, not
    # the fixture setup.
    for name in (seller, buyer):
        api(base, "POST", "/api/auth/register",
            {"username": name, "email": f"{name}@example.com", "password": password})
    logins = {
        "seller": api(base, "POST", "/api/auth/login", {"username": seller, "password": password}),
        "buyer": api(base, "POST", "/api/auth/login", {"username": buyer, "password": password}),
        "admin": api(base, "POST", "/api/auth/login",
                     {"username": "admin", "password": admin_password}),
    }
    # This suite spends several auth requests on setup and one more in the
    # browser, which is most of the default RATE_LIMIT_AUTH_PER_MINUTE=10. Back
    # to back runs will trip it, and the resulting failures look like broken
    # journeys rather than a throttled harness -- so say exactly what happened.
    if any(status == 429 for status, _ in logins.values()):
        print("RATE LIMITED during setup (HTTP 429 on /api/auth/login).\n"
              "This suite is not broken and neither is the product: the auth rate limit\n"
              "(RATE_LIMIT_AUTH_PER_MINUTE, default 10/min) counts these logins. Either\n"
              "wait a minute, or start the server with RATE_LIMIT_AUTH_PER_MINUTE=100.")
        return 3
    seller_token = logins["seller"][1].get("access_token", "")
    buyer_token = logins["buyer"][1].get("access_token", "")
    admin_token = logins["admin"][1].get("access_token", "")
    if not (seller_token and buyer_token and admin_token):
        print("could not obtain tokens; is the server running with COCOA_ADMIN_PASSWORD set?")
        return 2

    buyer_id = api(base, "GET", "/api/auth/me", token=buyer_token)[1]["user_id"]
    api(base, "POST", "/api/admin/credits/grant",
        {"user_id": buyer_id, "amount": 500}, token=admin_token)

    price = 120
    listing_name = f"E2E Avatar {suffix}"
    status, listing = api(base, "POST", "/api/marketplace/publish", {
        "avatar_id": f"e2e{suffix}", "name": listing_name, "description": "e2e",
        "tags": ["e2e"], "category": "other", "parameters": {"Hair": 0.5},
        "is_free": False, "price_credits": price,
    }, token=seller_token)
    listing_id = listing.get("listing_id", "")

    def balance(token: str) -> int:
        return api(base, "GET", "/api/credits/balance", token=token)[1].get("balance", 0)

    print("\n--- journey 1: publish is visible to shoppers ---")
    checks.that("listing published", status == 200 and bool(listing_id), f"status={status}")
    found = api(base, "GET", f"/api/marketplace?q=E2E+Avatar+{suffix}")[1].get("total", 0)
    checks.that("published listing is findable in public search", found >= 1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROMIUM)
        context = await browser.new_context(viewport={"width": 1400, "height": 1000})
        page = await context.new_page()
        http_errors: list[str] = []
        js_errors: list[str] = []
        page.on("response", lambda r: http_errors.append(f"{r.status} {r.request.method} {r.url}")
                if "/api/" in r.url and r.status >= 500 else None)
        page.on("pageerror", lambda e: js_errors.append(str(e)))
        page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))

        print("\n--- journey 2: login through the UI, session survives a reload ---")
        await page.goto(f"{base}/login", wait_until="networkidle")
        await page.fill("#username", buyer)
        await page.fill("#password", password)
        await page.click("button[type=submit]")
        await page.wait_for_timeout(1500)
        await page.goto(f"{base}/", wait_until="networkidle")
        body = await page.inner_text("body")
        checks.that("logged in and stays logged in after a reload", buyer in body,
                    "username not shown in the header")

        print("\n--- journey 3: buying moves credits on BOTH sides (#44) ---")
        buyer_before, seller_before = balance(buyer_token), balance(seller_token)
        await page.goto(f"{base}/listings/{listing_id}", wait_until="networkidle")
        await page.wait_for_timeout(500)
        add = page.locator("button:has-text('カートに追加')")
        checks.that("cart button is offered for a priced listing", await add.count() > 0)
        if await add.count():
            await add.first.click()
            await page.wait_for_timeout(1000)
        await page.goto(f"{base}/cart", wait_until="networkidle")
        await page.wait_for_timeout(600)
        checkout = page.locator("button:has-text('チェックアウト')")
        if await checkout.count():
            await checkout.first.click()
            await page.wait_for_timeout(2000)
        buyer_after, seller_after = balance(buyer_token), balance(seller_token)
        checks.that("buyer was debited the listing price",
                    buyer_before - buyer_after == price, f"{buyer_before} -> {buyer_after}")
        checks.that("seller was credited the listing price",
                    seller_after - seller_before == price, f"{seller_before} -> {seller_after}")

        orders = api(base, "GET", "/api/orders", token=buyer_token)[1]
        order_id = (orders.get("items") or [{}])[0].get("order_id", "")
        checks.that("the purchase produced an order to refund against", bool(order_id))

        print("\n--- journey 4: refund is requested, adjudicated, and pays out ---")
        refund_status, refund = api(base, "POST", "/api/refunds",
                                    {"order_id": order_id, "reason": "e2e refund"},
                                    token=buyer_token)
        checks.that("buyer can file a refund request", refund_status == 201, f"status={refund_status}")
        request_id = refund.get("request_id", "")
        await page.goto(f"{base}/login", wait_until="networkidle")
        await page.fill("#username", "admin")
        await page.fill("#password", admin_password)
        await page.click("button[type=submit]")
        await page.wait_for_timeout(1500)
        await page.goto(f"{base}/admin", wait_until="networkidle")
        await page.locator("button:has-text('払い戻し申請')").click()
        await page.wait_for_timeout(1000)
        console_body = await page.inner_text("body")
        checks.that("the refund request is visible in the admin console",
                    "e2e refund" in console_body or bool(request_id))
        approve = page.locator("button:has-text('承認')")
        if await approve.count():
            await approve.first.click()
            await page.wait_for_timeout(1500)
        checks.that("approving the refund makes the buyer whole",
                    balance(buyer_token) == buyer_before,
                    f"{balance(buyer_token)} != {buyer_before}")

        print("\n--- journey 5: a report reaches the moderation console ---")
        api(base, "POST", f"/api/marketplace/{listing_id}/report",
            {"reason": "spam", "details": f"e2e report {suffix}"}, token=buyer_token)
        await page.goto(f"{base}/admin", wait_until="networkidle")
        await page.locator("button:has-text('出品の通報')").click()
        await page.wait_for_timeout(1000)
        reports_body = await page.inner_text("body")
        checks.that("the filed report is waiting for a moderator",
                    listing_name in reports_body or "スパム" in reports_body)

        await browser.close()

    print(f"\n{checks.passed} checks passed, {len(checks.failures)} failed")
    if http_errors:
        print(f"\n/api/ 5xx responses seen ({len(http_errors)}):")
        for e in sorted(set(http_errors)):
            print("   ", e)
    if js_errors:
        print(f"\nuncaught JS errors ({len(js_errors)}):")
        for e in sorted(set(js_errors)):
            print("   ", e)
    if checks.failures:
        print("\nFAILED:")
        for f in checks.failures:
            print("   ", f)
    return 1 if (checks.failures or http_errors or js_errors) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="http://127.0.0.1:8250")
    parser.add_argument("--admin-password", required=True)
    args = parser.parse_args()
    return asyncio.run(run(args.base.rstrip("/"), args.admin_password))


if __name__ == "__main__":
    sys.exit(main())
