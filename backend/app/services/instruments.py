"""What market an instrument belongs to — one answer, one place.

The same question was answered by four separate copies of the same literal, each
drifting independently:

    backtesting_real.detect_source   60 tickers
    signal_chart._instrument         56   (missing FIXP, GLTR, MDMG, SOFL)
    live_price.get_live_price        24   (missing 36)
    gen_chart (local, in a function) 24   (missing 36)

None of this was theoretical. A FIXP signal was labelled "US/EU Stocks" with
prices in USD on the VIP card, because `signal_chart` had never heard of it.
`live_price` routed POSI, ASTR, WUSH, SVCB and fifteen others to Yahoo, which
does not list them — so their entries fell back to a computed level, the
staleness check had nothing to compare against, and the monitor could never
resolve them. And `FOREX_CURRENCIES` existed twice with 14 and 8 entries, so
USDTRY and USDCNY were "stocks" in one half of the codebase and currency pairs
in the other.

A list of Russian tickers is not a thing that should live in a module about
backtesting, or charts, or price fetching. It lives here, and those modules ask.

This module imports nothing from `app.services` on purpose: everything else
imports it, so any dependency of its own would be a cycle waiting to happen.
"""

import re

# ── MOEX equities ──────────────────────────────────────────────────────────
# The union of every copy that existed. Add new listings here and nowhere else.
MOEX_EQUITIES: frozenset[str] = frozenset({
    "SBER", "SBERP", "GAZP", "LKOH", "YNDX", "YDEX", "ROSN", "GMKN", "NVTK",
    "MGNT", "VTBR", "MTSS", "POLY", "FIVE", "OZON", "TCSG", "T", "PHOR",
    "NLMK", "MAGN", "CHMF", "ALRS", "AFLT", "MOEX", "PLZL", "RUAL", "SNGS",
    "SNGSP", "TATN", "TATNP", "SIBN", "PIKK", "AFKS", "RTKM", "HYDR", "IRAO",
    "FEES", "TRNFP", "BANE", "SELG", "UPRO", "MSNG", "FLOT", "SMLT", "SGZH",
    "POSI", "ASTR", "WUSH", "LEAS", "SVCB", "RENI", "BSPB", "CBOM", "ENPG",
    "FIXP", "GLTR", "MDMG", "SOFL", "UGLD", "VKCO",
})

# ── Currencies ─────────────────────────────────────────────────────────────
# Union of the three copies that existed. backtesting_real held 25 and the two
# others 14 and 8, so the same pair was forex in one module and a US stock in
# another — USDTRY and USDCNY were mislabelled on the card, USDRUB and USDPLN
# were not recognised as pairs at all.
FOREX_CURRENCIES: frozenset[str] = frozenset({
    "EUR", "USD", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF",
    "SEK", "NOK", "DKK", "SGD", "HKD", "TRY", "ZAR", "MXN",
    "PLN", "CZK", "HUF", "RUB", "CNY", "INR", "BRL", "KRW", "THB",
})

# ── Metals and energy quoted against a currency ────────────────────────────
# They read like FX pairs, but neither half is a currency, so a plain
# both-halves-are-currencies test drops them into "stocks" — and with it the 7%
# staleness tolerance, against gold's ~1% daily range.
SPOT_COMMODITIES: frozenset[str] = frozenset({
    "XAU", "XAG", "XPT", "XPD", "XBR", "WTI", "XTI", "XNG",
})

# Front-month future per commodity: no free spot feed exists for these.
COMMODITY_FUTURES: dict[str, str] = {
    "XAU": "GC=F",   # gold
    "XAG": "SI=F",   # silver
    "XPT": "PL=F",   # platinum
    "XPD": "PA=F",   # palladium
    "XBR": "BZ=F",   # Brent crude
    "WTI": "CL=F",   # WTI crude
    "XTI": "CL=F",
    "XNG": "NG=F",   # natural gas
}

# ── MOEX FORTS futures ─────────────────────────────────────────────────────
# Channels write "GAZR-9.26"; ISS wants the SECID "GZU6". Resolving one to the
# other needs a network call, so it stays in backtesting_real — this is only the
# shape test.
_FUTURES_RE = re.compile(r"^([A-Z]{2,4})-(\d{1,2})\.(\d{2})$")


def is_moex_futures(ticker: str) -> bool:
    return bool(_FUTURES_RE.match((ticker or "").upper()))


def is_moex_equity(ticker: str) -> bool:
    return (ticker or "").upper() in MOEX_EQUITIES


def is_forex_pair(ticker: str) -> bool:
    t = (ticker or "").upper()
    return len(t) == 6 and t[:3] in FOREX_CURRENCIES and t[3:] in FOREX_CURRENCIES


def is_spot_commodity(ticker: str) -> bool:
    t = (ticker or "").upper()
    return len(t) == 6 and t[:3] in SPOT_COMMODITIES and t[3:] in FOREX_CURRENCIES


def is_crypto(ticker: str) -> bool:
    t = (ticker or "").upper()
    return t.endswith("USDT") or t.endswith("BUSD") or t.endswith("BTC")


def asset_class(ticker: str) -> str:
    """forex | commodity | crypto | futures | moex | stocks.

    Order matters: crypto is checked before the MOEX list because a ticker can
    plausibly match both patterns, and futures before equities because
    "VTBR-12.26" contains an equity symbol.
    """
    t = (ticker or "").upper()
    if is_forex_pair(t):
        return "forex"
    if is_spot_commodity(t):
        return "commodity"
    if is_crypto(t):
        return "crypto"
    if is_moex_futures(t):
        return "futures"
    if is_moex_equity(t):
        return "moex"
    return "stocks"
