"""Test all 5 top strategies on real historical data."""

import asyncio
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.quant.top_strategies import (
    pairs_trading_signal, mean_reversion_signal,
    dual_momentum_signal, multi_factor_score, select_strategy,
)
from app.services.backtesting_real import fetch_moex_candles, fetch_binance_candles, fetch_forex_candles


async def main():
    print("=" * 60)
    print("BACKTEST: Top 1% Strategies on Real Data")
    print("=" * 60)

    # 1. PAIRS TRADING: SBER vs GAZP
    print("\nFetching MOEX data...")
    sber = await fetch_moex_candles("SBER", "2025-12-01", "2026-06-15")
    gazp = await fetch_moex_candles("GAZP", "2025-12-01", "2026-06-15")

    if sber and gazp:
        sber_p = [c["close"] for c in sber if c.get("close")]
        gazp_p = [c["close"] for c in gazp if c.get("close")]
        n = min(len(sber_p), len(gazp_p))

        pair = pairs_trading_signal(sber_p[:n], gazp_p[:n], "SBER", "GAZP", lookback=60)
        print(f"\n{'='*50}")
        print(f"1. PAIRS TRADING: SBER/GAZP ({n} days)")
        print(f"{'='*50}")
        print(f"   Z-Score:    {pair.z_score}")
        print(f"   Action:     {pair.action}")
        print(f"   Confidence: {pair.confidence}")
        print(f"   {pair.entry_a} / {pair.entry_b}")
        print(f"   Stop Z:     {pair.stop_z}")

        # 2. MEAN REVERSION: SBER
        mr = mean_reversion_signal(sber_p, lookback=20)
        print(f"\n{'='*50}")
        print(f"2. MEAN REVERSION: SBER")
        print(f"{'='*50}")
        print(f"   Z-Score:    {mr['z_score']}")
        print(f"   Action:     {mr['action']}")
        print(f"   Deviation:  {mr['deviation_pct']}%")
        print(f"   Confidence: {mr['confidence']}")
        print(f"   Mean:       {mr['mean']}")
    else:
        print("MOEX unavailable (weekend)")

    # 3. DUAL MOMENTUM: BTC vs ETH
    print("\nFetching crypto data...")
    btc = await fetch_binance_candles("BTCUSDT", "2025-12-01", "2026-06-15")
    eth = await fetch_binance_candles("ETHUSDT", "2025-12-01", "2026-06-15")

    if btc and eth:
        btc_p = [c["close"] for c in btc]
        eth_p = [c["close"] for c in eth]

        dm = dual_momentum_signal(btc_p, eth_p, lookback=60)
        print(f"\n{'='*50}")
        print(f"3. DUAL MOMENTUM: BTC vs ETH ({len(btc_p)} days)")
        print(f"{'='*50}")
        print(f"   Action:     {dm['action']}")
        print(f"   BTC return: {dm['asset_return_pct']}%")
        print(f"   ETH return: {dm['benchmark_return_pct']}%")
        print(f"   Relative:   {dm['relative_momentum']}%")
        print(f"   Absolute:   {dm['absolute_momentum']}%")
        print(f"   Trend:      {dm['trend']}")
        print(f"   Confidence: {dm['confidence']}")
        print(f"   Reason:     {dm['reason']}")

        # 4. MULTI-FACTOR: BTC
        p = btc_p
        mom_1m = (p[-1] / p[-22] - 1) * 100 if len(p) > 22 else 0
        mom_3m = (p[-1] / p[-66] - 1) * 100 if len(p) > 66 else 0
        avg_vol = sum(abs(p[i] - p[i - 1]) / p[i - 1] * 100 for i in range(max(1, len(p) - 14), len(p))) / 14
        gains = [max(0, p[i] - p[i - 1]) for i in range(max(1, len(p) - 14), len(p))]
        losses = [max(0, p[i - 1] - p[i]) for i in range(max(1, len(p) - 14), len(p))]
        avg_g = sum(gains) / len(gains) if gains else 0
        avg_l = sum(losses) / len(losses) if losses else 1
        rsi = 100 - 100 / (1 + avg_g / avg_l) if avg_l > 0 else 50
        sma200 = sum(p[-min(200, len(p)):]) / min(200, len(p))
        dist_sma = (p[-1] - sma200) / sma200 * 100

        mf = multi_factor_score(mom_1m, mom_3m, avg_vol, 1.0, rsi, dist_sma)
        print(f"\n{'='*50}")
        print(f"4. MULTI-FACTOR: BTCUSDT")
        print(f"{'='*50}")
        print(f"   Composite:  {mf['composite_score']}")
        print(f"   Action:     {mf['action']}")
        print(f"   Confidence: {mf['confidence']}")
        for k, v in mf["factors"].items():
            print(f"   {k:15s} {v}")

    # 5. FOREX MEAN REVERSION: EURUSD
    print("\nFetching forex data...")
    eur = await fetch_forex_candles("EURUSD", "2025-12-01", "2026-06-15")

    if eur:
        eur_p = [c["close"] for c in eur if c.get("close")]
        mr_eur = mean_reversion_signal(eur_p, lookback=20)
        print(f"\n{'='*50}")
        print(f"5. MEAN REVERSION: EURUSD ({len(eur_p)} days)")
        print(f"{'='*50}")
        print(f"   Z-Score:    {mr_eur['z_score']}")
        print(f"   Action:     {mr_eur['action']}")
        print(f"   Deviation:  {mr_eur['deviation_pct']}%")
        print(f"   Mean:       {mr_eur['mean']}")
        print(f"   Current:    {mr_eur['current']}")

    # 6. REGIME STRATEGY SELECTOR
    print(f"\n{'='*50}")
    print(f"6. REGIME STRATEGY SELECTOR")
    print(f"{'='*50}")
    scenarios = [
        ("trending_up", "low"), ("trending_up", "high"),
        ("trending_down", "medium"), ("ranging", "low"),
        ("ranging", "high"), ("breakout", "medium"),
    ]
    for regime, vol in scenarios:
        sel = select_strategy(regime, vol, 0.7)
        print(f"   {regime:16s} + {vol:6s} -> {sel['recommended_strategy']:35s} size={sel['position_size_multiplier']}x  SL={sel['stop_loss_multiplier']}x")

    print(f"\n{'='*60}")
    print("DONE")


if __name__ == "__main__":
    asyncio.run(main())
