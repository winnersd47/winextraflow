"""Production readiness check — full user journey + all button endpoints (in-process ASGI).

Tests the CURRENT code (not the stale :8000). Registration, login, and every
endpoint the UI buttons call.
"""
import asyncio, os, sys, random
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import httpx
from app.main import app

R = {"pass": 0, "fail": 0, "fails": []}
def ck(name, ok, detail=""):
    if ok: R["pass"] += 1; print(f"  [PASS] {name}")
    else: R["fail"] += 1; R["fails"].append(f"{name}: {detail}"); print(f"  [FAIL] {name} — {detail}")

async def main():
    tr = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=tr, base_url="http://t") as c:
        # ── ADMIN LOGIN (for referral code) ──
        print("\n=== AUTH / REGISTRATION ===")
        r = await c.post("/api/v1/auth/login", json={"email": "winnersd47@gmail.com", "password": "Yjhnljcn/95"})
        ck("admin login", r.status_code == 200, f"{r.status_code}")
        ah = {"Authorization": f"Bearer {r.json().get('access_token','')}"}
        ref = (await c.get("/api/v1/referrals/my-code", headers=ah)).json().get("referral_code", "")

        # register WITHOUT referral -> must 400 (invite-only)
        s = random.randint(100000, 999999)
        r = await c.post("/api/v1/auth/register", json={"email": f"u{s}@t.com", "username": f"u{s}", "password": "TestPass123!", "referral_code": ""})
        ck("register without referral -> rejected", r.status_code == 400, f"{r.status_code}")

        # register WITH valid referral -> success
        r = await c.post("/api/v1/auth/register", json={"email": f"u{s}@t.com", "username": f"u{s}", "password": "TestPass123!", "referral_code": ref})
        ck("register with valid referral", r.status_code in (200, 201), f"{r.status_code} {r.text[:120]}")

        # login as new user
        r = await c.post("/api/v1/auth/login", json={"email": f"u{s}@t.com", "password": "TestPass123!"})
        ck("new user login (email unverified)", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        uh = {"Authorization": f"Bearer {r.json().get('access_token','')}"} if r.status_code == 200 else ah

        r = await c.get("/api/v1/auth/me", headers=uh)
        ck("GET /auth/me", r.status_code == 200, f"{r.status_code}")

        # ── USER-FACING ENDPOINTS (buttons) ──
        print("\n=== DASHBOARD PAGES / BUTTONS ===")
        checks = [
            ("GET", "/api/v1/signals", uh, None),
            ("GET", "/api/v1/providers", uh, None),
            ("GET", "/api/v1/providers/leaderboard", uh, None),
            ("GET", "/api/v1/quant/regime", uh, None),
            ("GET", "/api/v1/quant/evolution", uh, None),
            ("GET", "/api/v1/moex/overview", uh, None),
            ("GET", "/api/v1/moex/heatmap", uh, None),
            ("GET", "/api/v1/portfolio/summary", uh, None),
            ("GET", "/api/v1/journal", uh, None),
            ("GET", "/api/v1/alerts", uh, None),
            ("GET", "/api/v1/screener/scan?market=moex", uh, None),
            ("GET", "/api/v1/feedback", uh, None),
            ("GET", "/api/v1/payments/plans", uh, None),
            ("GET", "/api/v1/premium/status", uh, None),
            ("GET", "/api/v1/referrals/my-code", uh, None),
            ("GET", "/api/v1/referrals/stats", uh, None),
            ("GET", "/api/v1/achievements", uh, None),
            ("GET", "/api/v1/notifications", uh, None),
            ("GET", "/api/v1/products/telegram-premium", uh, None),
            ("GET", "/api/v1/channels/markets", uh, None),
            ("GET", "/api/v1/channels/monitored", uh, None),
            ("GET", "/api/v1/compliance/level", uh, None),
            ("POST", "/api/v1/ai-chat/ask", uh, {"message": "SBER"}),
            ("POST", "/api/v1/payments/checkout", uh, {"plan": "monthly", "return_url": "http://t"}),
            ("POST", "/api/v1/calculator/expert-plan", uh, {"ticker": "SBER", "action": "buy", "entry_price": 300, "take_profit": 330, "stop_loss": 285}),
        ]
        for method, path, hdr, body in checks:
            if method == "GET":
                r = await c.get(path, headers=hdr)
            else:
                r = await c.post(path, headers=hdr, json=body)
            ck(f"{method} {path}", r.status_code == 200, f"{r.status_code} {r.text[:80]}")

        # signal detail chain (if any signal exists)
        sigs = (await c.get("/api/v1/signals", headers=uh)).json().get("items", [])
        if sigs:
            sid = sigs[0]["id"]
            for p in [f"/api/v1/signals/{sid}", f"/api/v1/signals/{sid}/rating", f"/api/v1/signals/{sid}/quality", f"/api/v1/quant/recommend/{sid}"]:
                r = await c.get(p, headers=uh)
                ck(f"GET {p.split(sid)[0]}{{id}}{p.split(sid)[1]}", r.status_code == 200, f"{r.status_code}")

        # public (no auth)
        print("\n=== PUBLIC ===")
        r = await c.get("/api/v1/public/stats")
        ck("GET /public/stats (no auth)", r.status_code == 200, f"{r.status_code}")

    print(f"\n{'='*54}\nPROD CHECK: {R['pass']} passed, {R['fail']} failed")
    for f in R["fails"]: print(f"  - {f}")
    print("="*54)

asyncio.run(main())
