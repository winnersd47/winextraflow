"""Stress test — concurrent load against key endpoints.

Measures: latency (p50/p95/max), error rate, throughput.
Usage: python scripts/stress_test.py
"""

import asyncio
import statistics
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

import httpx

BASE = "http://localhost:8000/api/v1"
EMAIL = "winnersd47@gmail.com"
PASSWORD = "Yjhnljcn/95"


async def timed_request(client: httpx.AsyncClient, method: str, url: str, **kw) -> tuple[float, int]:
    start = time.perf_counter()
    try:
        r = await client.request(method, url, **kw)
        return (time.perf_counter() - start) * 1000, r.status_code
    except Exception:
        return (time.perf_counter() - start) * 1000, 0


async def run_wave(client: httpx.AsyncClient, name: str, method: str, url: str, n: int, **kw):
    """Fire n concurrent requests, report latency distribution."""
    results = await asyncio.gather(*[timed_request(client, method, url, **kw) for _ in range(n)])
    latencies = [r[0] for r in results]
    statuses = [r[1] for r in results]
    ok = sum(1 for s in statuses if 200 <= s < 300)
    errors = n - ok
    lat_sorted = sorted(latencies)
    p50 = lat_sorted[len(lat_sorted) // 2]
    p95 = lat_sorted[int(len(lat_sorted) * 0.95)]

    status = "OK " if errors == 0 else "ERR"
    print(f"  [{status}] {name:40s} n={n:3d}  ok={ok:3d}  err={errors:2d}  p50={p50:6.0f}ms  p95={p95:6.0f}ms  max={max(latencies):6.0f}ms")
    return errors


async def main():
    total_errors = 0

    async with httpx.AsyncClient(timeout=60) as c:
        # Login once
        r = await c.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        print("\n=== WAVE 1: Read endpoints (50 concurrent each) ===")
        total_errors += await run_wave(c, "GET /signals", "GET", f"{BASE}/signals", 50, headers=h)
        total_errors += await run_wave(c, "GET /providers", "GET", f"{BASE}/providers", 50, headers=h)
        total_errors += await run_wave(c, "GET /quant/regime", "GET", f"{BASE}/quant/regime", 50, headers=h)
        total_errors += await run_wave(c, "GET /payments/plans", "GET", f"{BASE}/payments/plans", 50, headers=h)
        total_errors += await run_wave(c, "GET /public/stats (no auth)", "GET", f"{BASE}/public/stats", 50)

        print("\n=== WAVE 2: Heavy compute (20 concurrent each) ===")
        total_errors += await run_wave(c, "POST /calculator/expert-plan", "POST", f"{BASE}/calculator/expert-plan", 20,
                                        headers=h, json={"ticker": "SBER", "action": "buy", "entry_price": 300, "take_profit": 330, "stop_loss": 285})
        total_errors += await run_wave(c, "GET /screener/scan", "GET", f"{BASE}/screener/scan?market=moex", 20, headers=h)
        total_errors += await run_wave(c, "POST /ai-chat/ask", "POST", f"{BASE}/ai-chat/ask", 20,
                                        headers=h, json={"message": "SBER"})

        print("\n=== WAVE 3: Auth storm (100 concurrent logins) ===")
        total_errors += await run_wave(c, "POST /auth/login x100", "POST", f"{BASE}/auth/login", 100,
                                        json={"email": EMAIL, "password": PASSWORD})

        print("\n=== WAVE 4: Webhook burst (30 signals at once) ===")
        total_errors += await run_wave(c, "POST /signals/webhook x30", "POST", f"{BASE}/signals/webhook/tradingview", 30,
                                        json={"ticker": "STRESST", "action": "buy", "price": 50.0, "take_profit": 55.0, "stop_loss": 47.0})

        print("\n=== WAVE 5: Mixed sustained (200 requests, mixed) ===")
        start = time.perf_counter()
        tasks = []
        for i in range(200):
            if i % 4 == 0:
                tasks.append(timed_request(c, "GET", f"{BASE}/signals", headers=h))
            elif i % 4 == 1:
                tasks.append(timed_request(c, "GET", f"{BASE}/quant/regime", headers=h))
            elif i % 4 == 2:
                tasks.append(timed_request(c, "GET", f"{BASE}/public/stats"))
            else:
                tasks.append(timed_request(c, "GET", f"{BASE}/providers", headers=h))
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start
        ok = sum(1 for _, s in results if 200 <= s < 300)
        rps = 200 / elapsed
        print(f"  200 mixed requests in {elapsed:.1f}s = {rps:.0f} req/s | ok={ok}/200")
        total_errors += 200 - ok

    print(f"\n{'='*50}")
    print(f"STRESS TEST: {'PASSED — 0 errors' if total_errors == 0 else f'{total_errors} ERRORS'}")
    print(f"{'='*50}")
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
