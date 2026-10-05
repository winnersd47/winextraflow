"""Position size and the deposit a signal actually needs.

A percentage result tells a reader nothing about their own money: -1.4% is a
rounding error on one deposit and a painful loss on another. What matters is the
risk per trade, and from it the position that keeps that risk fixed.

The chain is standard fixed-fractional sizing, run backwards from the stop:

    risk in money   = deposit x RISK_PER_TRADE
    position        = risk in money / stop distance in %
    result in money = position x result in %

The stop distance is what sets the size — that is why a 1% stop and a 10% stop on
the same deposit are completely different trades, and why the tight crypto stops
were so damaging: they invited a 10x larger position for the same nominal risk.

`optimal_deposit` answers the other direction: given the instrument's minimum
tradable amount, how much capital does a reader need for the position to be
possible at all without exceeding the risk budget. Below that number the trade
cannot be taken at correct size — it can only be taken oversized.
"""

REFERENCE_DEPOSIT_RUB = 100_000
REFERENCE_DEPOSIT_USD = 1_000
RISK_PER_TRADE = 0.01          # 1% of deposit at risk — half-Kelly territory for
                               # an unvalidated edge; see quant/expert_engine.py
MAX_POSITION_SHARE = 0.25      # never more than a quarter of the deposit in one name


def position_size(deposit: float, entry: float, stop: float,
                  risk_per_trade: float = RISK_PER_TRADE) -> dict:
    """Fixed-risk position size. Returns money at risk, position value, units."""
    if not entry or not stop or entry <= 0:
        return {}
    stop_pct = abs(entry - stop) / entry
    if stop_pct <= 0:
        return {}

    budget = deposit * risk_per_trade
    position = budget / stop_pct
    capped = min(position, deposit * MAX_POSITION_SHARE)

    # When the share cap bites, the position is smaller than the risk budget
    # would buy — so the stop costs LESS than the budget. Reporting the budget as
    # "money at risk" would overstate the loss by however much was cut off, and
    # the caller has no way to tell the two apart from a single field. So
    # `risk_money` is always what this position actually loses at its stop.
    risk_money = capped * stop_pct

    return {
        "stop_pct": stop_pct,
        "risk_money": risk_money,
        "risk_money_budget": budget,
        "position": capped,
        "position_capped": capped < position,
        "units": capped / entry,
        "share_of_deposit": capped / deposit if deposit else 0,
    }


def optimal_deposit(entry: float, stop: float, min_lot_units: float = 1.0,
                    risk_per_trade: float = RISK_PER_TRADE) -> float | None:
    """Smallest deposit on which one minimum lot still respects the risk budget."""
    if not entry or not stop or entry <= 0:
        return None
    stop_pct = abs(entry - stop) / entry
    if stop_pct <= 0:
        return None
    min_position = entry * min_lot_units
    # min_position must be <= deposit * risk / stop_pct
    return min_position * stop_pct / risk_per_trade


def sizing_block(ticker: str, entry: float, stop: float, result_pct: float | None = None,
                 currency: str = "RUB") -> str:
    """Human-readable sizing lines for a Telegram post.

    Kept to four short lines: what deposit is assumed, what is risked, what
    position that implies, and — when the trade is closed — what it came to in
    money. Without the deposit stated, the money figure would be meaningless.
    """
    deposit = REFERENCE_DEPOSIT_RUB if currency == "RUB" else REFERENCE_DEPOSIT_USD
    sym = "₽" if currency == "RUB" else "$"
    s = position_size(deposit, entry, stop)
    if not s:
        return ""

    def money(v: float, signed: bool = False) -> str:
        """Thin space as the thousands separator — applied to the number only, so
        it cannot eat the punctuation of the surrounding sentence."""
        return f"{v:+,.0f}".replace(",", " ") if signed else f"{v:,.0f}".replace(",", " ")

    lines = [
        f"💼 <b>Расчёт на депозит {money(deposit)} {sym}</b>",
        f"• Риск на сделку: {money(s['risk_money'])} {sym} "
        f"({s['risk_money'] / deposit:.2%} депозита)",
        f"• Позиция: {money(s['position'])} {sym} "
        f"({s['share_of_deposit']:.0%} депозита, стоп {s['stop_pct']:.1%})",
    ]
    if s["position_capped"]:
        # Say what the cap did to the risk, not just that it fired: a reader who
        # sees the budget figure elsewhere needs to know this trade risks less.
        lines.append(f"• Позиция урезана до {MAX_POSITION_SHARE:.0%} депозита "
                     f"(стоп узкий — полный размер вышел бы больше). "
                     f"Риск поэтому {money(s['risk_money'])} {sym}, "
                     f"а не {money(s['risk_money_budget'])} {sym}")
    if result_pct is not None:
        res = s["position"] * result_pct / 100
        lines.append(f"• <b>Результат: {money(res, signed=True)} {sym}</b> "
                     f"({res / deposit:+.2%} от депозита)")

    opt = optimal_deposit(entry, stop)
    if opt and opt > deposit * 0.5:
        lines.append(f"• Минимальный депозит для этой сделки: ~{money(opt)} {sym}")
    return "\n".join(lines)
