"""Ticker Screener — scan tickers by conditions using platform signals and MOEX data.

Conditions: RSI zones, signal count, win rate, WEF score, regime, etc.
"""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.track_record import MIN_SAMPLE
from app.database import get_db
from app.models.signal import Signal, SignalAction, SignalStatus
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# All tracked tickers with categories
TICKERS = {
    "MOEX": [
        "SBER", "GAZP", "LKOH", "YNDX", "ROSN", "GMKN", "NVTK", "MGNT",
        "VTBR", "MTSS", "POLY", "FIVE", "OZON", "TCSG", "PHOR", "NLMK",
        "CHMF", "ALRS", "AFLT", "MOEX", "PLZL", "RUAL", "SNGS", "TATN",
    ],
    "Crypto": [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
        "ADAUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "AVAXUSDT",
        "LTCUSDT", "LINKUSDT", "UNIUSDT", "AAVEUSDT", "ATOMUSDT",
    ],
    "Forex": [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD",
        "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURAUD",
        "EURCHF", "GBPCHF", "CADJPY", "NZDJPY", "AUDCAD", "GBPAUD",
    ],
    "US Stocks": [
        # Mega-cap tech
        "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOG", "META", "NFLX", "AMD",
        # Semiconductors
        "INTC", "AVGO", "QCOM", "MU", "ARM", "SMCI",
        # Fintech
        "PYPL", "SQ", "COIN", "SOFI", "V", "MA",
        # Banks
        "GS", "JPM",
        # EV / Energy
        "RIVN", "NIO", "F", "XOM", "CVX",
        # Cloud / SaaS
        "CRM", "SNOW", "PLTR", "NET",
        # Social / Media
        "SNAP", "RBLX", "SPOT", "DIS",
        # Healthcare
        "JNJ", "PFE", "MRNA", "LLY",
        # Retail
        "WMT", "COST", "NKE", "SBUX",
        # Other
        "BA", "UBER", "ABNB",
    ],
    "EU/Asia": [
        "SAP", "ASML", "NVO", "SHEL", "AZN", "BP", "RIO",
        "TSM", "BABA", "JD", "PDD",
    ],
}


@router.get("/scan")
async def scan_tickers(
    market: str = Query("all", description="Market filter: all, MOEX, Crypto, Forex, US Stocks"),
    min_signals: int = Query(1, ge=0, description="Minimum signals in last 30 days"),
    min_wef_score: float = Query(0.0, ge=0, le=1, description="Minimum average WEF score"),
    action: str = Query("all", description="Filter: all, buy, sell"),
    sort_by: str = Query("wef_score", description="Sort: wef_score, signals, win_rate, profit"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Scan all tickers with filters and return ranked results."""
    # Determine which tickers to scan
    if market == "all":
        tickers = [t for group in TICKERS.values() for t in group]
    elif market in TICKERS:
        tickers = TICKERS[market]
    else:
        tickers = [t for group in TICKERS.values() for t in group]

    month_ago = datetime.now(timezone.utc) - timedelta(days=30)

    # Fetch all signals for these tickers in last 30 days.
    # Seed rows must be excluded: the TICKERS list above is the same set seed_data
    # generates from, so unfiltered the screener ranked demo data almost exclusively.
    from app.api.ai_insights import not_seed
    stmt = (
        select(Signal)
        .where(Signal.ticker.in_(tickers), Signal.created_at >= month_ago, not_seed())
    )
    all_signals = (await db.execute(stmt)).scalars().all()

    # Group by ticker
    by_ticker: dict[str, list] = {}
    for s in all_signals:
        by_ticker.setdefault(s.ticker, []).append(s)

    # Build results
    results = []
    for ticker in tickers:
        signals = by_ticker.get(ticker, [])
        if len(signals) < min_signals:
            continue

        total = len(signals)
        buys = sum(1 for s in signals if s.action == SignalAction.BUY)
        sells = total - buys
        avg_wef = sum(s.ai_confidence or 0 for s in signals) / total if total else 0
        active = sum(1 for s in signals if s.status == SignalStatus.ACTIVE)

        # Filter by WEF score
        if avg_wef < min_wef_score:
            continue

        # Filter by action
        if action == "buy" and buys == 0:
            continue
        if action == "sell" and sells == 0:
            continue

        # Closed signals stats. A per-ticker win rate over a handful of trades is
        # noise — one closed trade returned 1.0 and sorted that ticker to the top.
        # Reported only from MIN_SAMPLE closed trades, like everywhere else.
        closed = [s for s in signals if s.profit_pct is not None]
        enough = len(closed) >= MIN_SAMPLE
        wins = sum(1 for s in closed if s.profit_pct > 0)
        win_rate = wins / len(closed) if enough else None
        avg_profit = sum(s.profit_pct for s in closed) / len(closed) if enough else None

        # Latest signal
        latest = max(signals, key=lambda s: s.created_at)
        latest_action = latest.action.value if hasattr(latest.action, "value") else str(latest.action)

        # Determine market
        ticker_market = "Other"
        for m, ts in TICKERS.items():
            if ticker in ts:
                ticker_market = m
                break

        # Bias
        if total > 0:
            bias_pct = buys / total
        else:
            bias_pct = 0.5

        results.append({
            "ticker": ticker,
            "market": ticker_market,
            "total_signals": total,
            "active": active,
            "buys": buys,
            "sells": sells,
            "bias": "bullish" if bias_pct > 0.6 else "bearish" if bias_pct < 0.4 else "neutral",
            "bias_pct": round(bias_pct, 2),
            "avg_wef_score": round(avg_wef, 3),
            "win_rate": round(win_rate, 3) if win_rate is not None else None,
            "avg_profit": round(avg_profit, 2) if avg_profit is not None else None,
            "closed_trades": len(closed),
            "enough_data": enough,
            "latest_action": latest_action,
            "latest_price": latest.entry_price,
            "latest_tp": latest.take_profit,
            "latest_sl": latest.stop_loss,
            "latest_at": latest.created_at.isoformat() if latest.created_at else None,
        })

    # Sort
    def sort_key(r):
        if sort_by == "wef_score":
            return r["avg_wef_score"]
        elif sort_by == "signals":
            return r["total_signals"]
        elif sort_by == "win_rate":
            return r["win_rate"] or 0
        elif sort_by == "profit":
            return r["avg_profit"] or 0
        return r["avg_wef_score"]

    results.sort(key=sort_key, reverse=True)

    return {
        "total": len(results),
        "market": market,
        "filters": {
            "min_signals": min_signals,
            "min_wef_score": min_wef_score,
            "action": action,
            "sort_by": sort_by,
        },
        "items": results,
    }


@router.get("/markets")
async def get_markets(user: User = Depends(get_current_user)):
    """List available markets and their tickers."""
    return {
        market: {"tickers": tickers, "count": len(tickers)}
        for market, tickers in TICKERS.items()
    }
