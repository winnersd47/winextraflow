"""Security test — pre-deploy checks.

1. Protected endpoints require auth (401 without token)
2. Invalid/forged tokens rejected
3. SQL injection attempts return safe errors
4. XSS payloads not reflected
5. Rate limiting active on auth
6. Security headers present
7. Admin endpoints blocked for regular users

Usage: python scripts/security_test.py
"""

import asyncio
import sys

sys.stdout.reconfigure(encoding="utf-8")

import httpx

BASE = "http://localhost:8000/api/v1"
EMAIL = "winnersd47@gmail.com"
PASSWORD = "Yjhnljcn/95"

results = {"pass": 0, "fail": 0, "failures": []}


def check(name: str, ok: bool, detail: str = ""):
    if ok:
        results["pass"] += 1
        print(f"  [PASS] {name}")
    else:
        results["fail"] += 1
        results["failures"].append(f"{name}: {detail}")
        print(f"  [FAIL] {name} — {detail}")


async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        # ═══ 1. AUTH REQUIRED ═══
        print("\n=== 1. Protected endpoints require auth ===")
        protected = [
            ("GET", "/signals"), ("GET", "/auth/me"), ("GET", "/payments/history"),
            ("GET", "/portfolio/summary"), ("GET", "/journal"), ("GET", "/alerts"),
            ("POST", "/payments/checkout"), ("GET", "/premium/status"),
        ]
        for method, path in protected:
            r = await c.request(method, f"{BASE}{path}")
            check(f"{method} {path} without token -> 401/403/422", r.status_code in (401, 403, 422), f"got {r.status_code}")

        # ═══ 2. INVALID TOKENS ═══
        print("\n=== 2. Invalid tokens rejected ===")
        bad_tokens = [
            ("garbage", "Bearer garbage_token_12345"),
            ("empty bearer", "Bearer x"),
            ("forged JWT", "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJoYWNrZXIifQ.fake_signature_here"),
            ("none algorithm", "Bearer eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiJ9."),
        ]
        for name, token in bad_tokens:
            r = await c.get(f"{BASE}/auth/me", headers={"Authorization": token})
            check(f"Token '{name}' rejected", r.status_code in (401, 403, 422), f"got {r.status_code}")

        # ═══ 3. SQL INJECTION ═══
        print("\n=== 3. SQL injection attempts ===")
        r = await c.post(f"{BASE}/auth/login", json={"email": "' OR '1'='1' --", "password": "x"})
        check("SQLi in login email", r.status_code in (401, 422, 429), f"got {r.status_code}")

        # Get valid token for authenticated SQLi tests
        r = await c.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if r.status_code == 429:
            print("  (rate limited — waiting 60s for auth window)")
            await asyncio.sleep(61)
            r = await c.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
        token = r.json().get("access_token", "")
        h = {"Authorization": f"Bearer {token}"}

        injections = ["'; DROP TABLE signals; --", "1 UNION SELECT * FROM users", "1' OR '1'='1"]
        for inj in injections:
            r = await c.get(f"{BASE}/signals", params={"ticker": inj}, headers=h)
            check(f"SQLi in ticker param safe", r.status_code in (200, 422), f"got {r.status_code}")

        # ═══ 4. XSS ═══
        print("\n=== 4. XSS payload handling ===")
        xss = "<script>alert('xss')</script>"
        r = await c.post(f"{BASE}/signals/webhook/tradingview", json={"ticker": xss, "action": "buy", "price": 100})
        check("XSS ticker rejected by validation", r.status_code == 422, f"got {r.status_code}")

        # ═══ 5. RATE LIMITING ═══
        print("\n=== 5. Rate limiting ===")
        codes = []
        for _ in range(15):
            r = await c.post(f"{BASE}/auth/login", json={"email": "nobody@test.com", "password": "wrong"})
            codes.append(r.status_code)
        check("Login rate limit kicks in (429 seen)", 429 in codes, f"codes: {set(codes)}")

        # ═══ 6. SECURITY HEADERS ═══
        print("\n=== 6. Security headers ===")
        r = await c.get(f"{BASE}/public/stats")
        hdrs = r.headers
        check("X-Content-Type-Options: nosniff", hdrs.get("x-content-type-options") == "nosniff", str(hdrs.get("x-content-type-options")))
        check("X-Frame-Options present", "x-frame-options" in hdrs, "missing")
        check("Referrer-Policy present", "referrer-policy" in hdrs, "missing")

        # ═══ 7. ADMIN PROTECTION ═══
        print("\n=== 7. Admin endpoints ===")
        # Register a regular user
        import random
        suffix = random.randint(10000, 99999)
        r = await c.post(f"{BASE}/auth/register", json={
            "email": f"sectest{suffix}@test.com", "username": f"sectest{suffix}", "password": "TestPass123!", "referral_code": "",
        })
        if r.status_code in (200, 201):
            r2 = await c.post(f"{BASE}/auth/login", json={"email": f"sectest{suffix}@test.com", "password": "TestPass123!"})
            if r2.status_code == 200:
                user_h = {"Authorization": f"Bearer {r2.json()['access_token']}"}
                r3 = await c.get(f"{BASE}/admin/users", headers=user_h)
                check("GET /admin/users blocked for regular user", r3.status_code in (401, 403), f"got {r3.status_code}")
                r4 = await c.patch(f"{BASE}/compliance/business_registration/status?status=verified", headers=user_h)
                check("PATCH /compliance blocked for regular user", r4.status_code in (401, 403), f"got {r4.status_code}")
            else:
                print(f"  (skip admin tests — login rate limited: {r2.status_code})")
        else:
            print(f"  (skip admin tests — register returned {r.status_code})")

        # ═══ 8. WEBHOOK VALIDATION ═══
        print("\n=== 8. Webhook input validation ===")
        bad_payloads = [
            ({"ticker": "SBER", "action": "hack", "price": 100}, "invalid action"),
            ({"ticker": "SBER", "action": "buy", "price": -5}, "negative price"),
            ({"ticker": "", "action": "buy", "price": 100}, "empty ticker"),
            ({"action": "buy", "price": 100}, "missing ticker"),
        ]
        for payload, desc in bad_payloads:
            r = await c.post(f"{BASE}/signals/webhook/tradingview", json=payload)
            check(f"Webhook rejects {desc}", r.status_code == 422, f"got {r.status_code}")

    # ═══ SUMMARY ═══
    print(f"\n{'='*50}")
    print(f"SECURITY TEST: {results['pass']} passed, {results['fail']} failed")
    if results["failures"]:
        print("\nFailures:")
        for f in results["failures"]:
            print(f"  - {f}")
    print(f"{'='*50}")
    return 0 if results["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
