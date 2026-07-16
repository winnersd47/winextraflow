"""Pre-deploy smoke test — hit every critical endpoint against the running server.

Usage: python scripts/smoke_test.py
"""

import asyncio
import sys
import time

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
        # ═══ AUTH ═══
        print("\n=== AUTH ===")
        r = await c.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
        check("POST /auth/login", r.status_code == 200, f"status {r.status_code}")
        token = r.json().get("access_token", "")
        h = {"Authorization": f"Bearer {token}"}

        r = await c.get(f"{BASE}/auth/me", headers=h)
        check("GET /auth/me", r.status_code == 200 and r.json().get("email") == EMAIL, f"status {r.status_code}")

        # ═══ SIGNALS ═══
        print("\n=== SIGNALS ===")
        r = await c.get(f"{BASE}/signals", headers=h)
        check("GET /signals", r.status_code == 200 and "items" in r.json(), f"status {r.status_code}")
        signals = r.json().get("items", [])

        if signals:
            sid = signals[0]["id"]
            r = await c.get(f"{BASE}/signals/{sid}", headers=h)
            check("GET /signals/{id}", r.status_code == 200, f"status {r.status_code}")

            r = await c.get(f"{BASE}/signals/{sid}/rating", headers=h)
            check("GET /signals/{id}/rating", r.status_code == 200, f"status {r.status_code}")

            r = await c.get(f"{BASE}/signals/{sid}/quality", headers=h)
            check("GET /signals/{id}/quality", r.status_code == 200, f"status {r.status_code}")

            r = await c.get(f"{BASE}/quant/recommend/{sid}", headers=h)
            check("GET /quant/recommend/{id}", r.status_code == 200, f"status {r.status_code}")

        # Webhook (with TP/SL for quality gate)
        r = await c.post(f"{BASE}/signals/webhook/tradingview", json={
            "ticker": "TESTTICK", "action": "buy", "price": 100.0,
            "take_profit": 110.0, "stop_loss": 95.0,
        })
        check("POST /signals/webhook/tradingview", r.status_code == 201, f"status {r.status_code}")

        # ═══ PROVIDERS / LEADERBOARD ═══
        print("\n=== PROVIDERS ===")
        r = await c.get(f"{BASE}/providers", headers=h)
        check("GET /providers", r.status_code == 200, f"status {r.status_code}")

        r = await c.get(f"{BASE}/providers/leaderboard", headers=h)
        check("GET /providers/leaderboard", r.status_code == 200, f"status {r.status_code}")

        # ═══ PAYMENTS ═══
        print("\n=== PAYMENTS ===")
        r = await c.get(f"{BASE}/payments/plans", headers=h)
        check("GET /payments/plans", r.status_code == 200, f"status {r.status_code}")

        r = await c.post(f"{BASE}/payments/checkout", headers=h, json={"plan": "monthly", "return_url": "http://localhost:3000"})
        check("POST /payments/checkout (demo)", r.status_code == 200 and r.json().get("demo"), f"status {r.status_code}")

        r = await c.get(f"{BASE}/payments/history", headers=h)
        check("GET /payments/history", r.status_code == 200, f"status {r.status_code}")

        r = await c.get(f"{BASE}/premium/status", headers=h)
        check("GET /premium/status", r.status_code == 200, f"status {r.status_code}")

        # ═══ QUANT / INTELLIGENCE ═══
        print("\n=== QUANT ===")
        r = await c.get(f"{BASE}/quant/regime", headers=h)
        check("GET /quant/regime", r.status_code == 200, f"status {r.status_code}")

        r = await c.get(f"{BASE}/quant/evolution", headers=h)
        check("GET /quant/evolution", r.status_code == 200, f"status {r.status_code}")

        r = await c.get(f"{BASE}/quant/articles", headers=h)
        check("GET /quant/articles", r.status_code == 200, f"status {r.status_code}")

        # ═══ CALCULATOR ═══
        print("\n=== CALCULATOR ===")
        r = await c.post(f"{BASE}/calculator/expert-plan", headers=h, json={
            "ticker": "SBER", "action": "buy", "entry_price": 300, "take_profit": 330, "stop_loss": 285,
        })
        check("POST /calculator/expert-plan", r.status_code == 200 and "verdict" in r.json(), f"status {r.status_code}")

        # ═══ MOEX / MARKET DATA ═══
        print("\n=== MARKET DATA ===")
        r = await c.get(f"{BASE}/moex/overview", headers=h)
        check("GET /moex/overview", r.status_code == 200, f"status {r.status_code}")

        r = await c.get(f"{BASE}/moex/heatmap", headers=h)
        check("GET /moex/heatmap", r.status_code == 200, f"status {r.status_code}")

        # ═══ PORTFOLIO / JOURNAL / ALERTS ═══
        print("\n=== PORTFOLIO/JOURNAL/ALERTS ===")
        r = await c.get(f"{BASE}/portfolio/summary", headers=h)
        check("GET /portfolio/summary", r.status_code == 200, f"status {r.status_code}")

        r = await c.get(f"{BASE}/journal", headers=h)
        check("GET /journal", r.status_code == 200, f"status {r.status_code}")

        r = await c.get(f"{BASE}/alerts", headers=h)
        check("GET /alerts", r.status_code == 200, f"status {r.status_code}")

        # ═══ SOCIAL / FEEDBACK ═══
        print("\n=== SOCIAL ===")
        if signals:
            r = await c.get(f"{BASE}/social/signals/{signals[0]['id']}/comments", headers=h)
            check("GET /social/signals/{id}/comments", r.status_code == 200, f"status {r.status_code}")

        r = await c.get(f"{BASE}/feedback", headers=h)
        check("GET /feedback", r.status_code == 200, f"status {r.status_code}")

        # ═══ SCREENER / AI CHAT ═══
        print("\n=== SCREENER/AI ===")
        r = await c.get(f"{BASE}/screener/scan?market=moex", headers=h)
        check("GET /screener/scan", r.status_code == 200, f"status {r.status_code}")

        r = await c.post(f"{BASE}/ai-chat/ask", headers=h, json={"message": "Что такое WEF Score?"})
        check("POST /ai-chat/ask", r.status_code == 200, f"status {r.status_code}")

        # ═══ COMPLIANCE ═══
        print("\n=== COMPLIANCE ===")
        r = await c.get(f"{BASE}/compliance/level", headers=h)
        d = r.json() if r.status_code == 200 else {}
        check("GET /compliance/level = 100%", r.status_code == 200 and d.get("compliance_pct") == 100, f"status {r.status_code}, pct {d.get('compliance_pct')}")

        # ═══ PUBLIC (no auth) ═══
        print("\n=== PUBLIC ===")
        r = await c.get(f"{BASE}/public/stats")
        check("GET /public/stats (no auth)", r.status_code == 200, f"status {r.status_code}")

    # ═══ SUMMARY ═══
    print(f"\n{'='*50}")
    print(f"SMOKE TEST: {results['pass']} passed, {results['fail']} failed")
    if results["failures"]:
        print("\nFailures:")
        for f in results["failures"]:
            print(f"  - {f}")
    print(f"{'='*50}")
    return 0 if results["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
