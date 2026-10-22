"""One market classifier, and nothing that quietly keeps its own copy.

Five literals answered the same question and drifted apart:

    backtesting_real.detect_source   60 MOEX names, 25 currencies
    signal_chart._instrument         56 MOEX names,  8 currencies
    live_price.get_live_price        24 MOEX names, 14 currencies
    gen_chart (inside a function)    24 MOEX names,  8 currencies

Each gap was visible to a user. A FIXP signal was captioned "US/EU Stocks" with
prices in USD. POSI, ASTR, WUSH, SVCB and fifteen others were routed to a price
source that does not list them, so their entries fell back to a computed level
and the monitor could never resolve them. USDTRY and USDCNY were currency pairs
in one module and American stocks in another.

The duplication is the bug these tests guard, not any individual missing symbol.
"""

import ast
import re
from pathlib import Path

import pytest

from app.services import instruments
from app.services.instruments import (FOREX_CURRENCIES, MOEX_EQUITIES,
                                      asset_class, is_moex_equity)

SERVICES = Path(__file__).resolve().parents[1] / "app" / "services"
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _modules():
    for path in list(SERVICES.rglob("*.py")) + list(SCRIPTS.rglob("*.py")):
        if path.name == "instruments.py":
            continue
        yield path


# ═══════════════════════════════════════════════════════════════════════
# No second copy
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("literal", ["MOEX_TICKERS", "MOEX_EQUITIES",
                                     "FOREX_CURRENCIES", "SPOT_COMMODITIES"])
def test_no_module_redefines_the_classification_lists(literal):
    """Assignment from instruments is fine; a fresh set literal is not."""
    offenders = []
    for path in _modules():
        src = path.read_text(encoding="utf-8")
        # `X = {` or `X: ... = {` starting a literal, not `X = OTHER_NAME`.
        if re.search(rf"^\s*{literal}(?:\s*:[^=]+)?\s*=\s*(?:frozenset\()?\{{",
                     src, re.M):
            offenders.append(path.name)
    assert not offenders, (
        f"{literal} is defined again in {offenders} — it drifts from "
        f"instruments.py the moment a listing is added")


def test_classification_helpers_are_not_reimplemented():
    """`len(t) == 6 and t[:3] in FOREX_CURRENCIES` was written out by hand in
    four places; each copy then needed fixing separately."""
    pattern = re.compile(r"len\(\s*t\w*\s*\)\s*==\s*6\s*and.*FOREX_CURRENCIES")
    offenders = [p.name for p in _modules()
                 if pattern.search(p.read_text(encoding="utf-8"))]
    assert not offenders, f"inline forex test re-implemented in {offenders}"


# ═══════════════════════════════════════════════════════════════════════
# The classifier agrees with itself everywhere
# ═══════════════════════════════════════════════════════════════════════

# ticker -> (asset_class, what the card must call it, its currency)
EXPECTED = [
    ("SBER", "moex", "Акции РФ", "RUB"),
    ("FIXP", "moex", "Акции РФ", "RUB"),      # was "Акции"/USD
    ("GLTR", "moex", "Акции РФ", "RUB"),
    ("MDMG", "moex", "Акции РФ", "RUB"),
    ("SOFL", "moex", "Акции РФ", "RUB"),
    ("POSI", "moex", "Акции РФ", "RUB"),
    ("GAZR-12.26", "futures", "Фьючерс", "RUB"),
    ("BTCUSDT", "crypto", "Криптовалюта", "USDT"),
    ("EURUSD", "forex", "Валютная пара", "USD"),
    ("USDTRY", "forex", "Валютная пара", "TRY"),   # was "Акции"/USD
    ("USDCNY", "forex", "Валютная пара", "CNY"),
    ("AAPL", "stocks", "Акции", "USD"),
]


@pytest.mark.parametrize("ticker,cls,label,currency", EXPECTED)
def test_card_label_matches_the_classifier(ticker, cls, label, currency):
    from app.services.signal_chart import _instrument

    assert asset_class(ticker) == cls
    _exchange, _brokers, asset_type, cur = _instrument(ticker)
    assert asset_type == label, f"{ticker} captioned as {asset_type}"
    assert cur == currency, f"{ticker} priced in {cur}, should be {currency}"


@pytest.mark.parametrize("ticker,cls,_label,_cur", EXPECTED)
def test_data_source_matches_the_classifier(ticker, cls, _label, _cur):
    """detect_source and asset_class must not disagree about the same symbol."""
    from app.services.backtesting_real import detect_source

    equivalent = {
        "moex": {"moex", "moex_or_stocks"},
        "futures": {"moex_futures"},
        "crypto": {"binance"},
        "forex": {"forex"},
        "stocks": {"stocks", "moex_or_stocks"},
        "commodity": {"stocks"},      # no dedicated candle source yet
    }[cls]
    assert detect_source(ticker) in equivalent, (
        f"{ticker}: asset_class says {cls}, detect_source says "
        f"{detect_source(ticker)}")


def test_merged_lists_lost_nothing():
    """The union must cover every name any copy used to hold."""
    assert len(MOEX_EQUITIES) >= 60, f"only {len(MOEX_EQUITIES)} MOEX names"
    assert len(FOREX_CURRENCIES) >= 25, f"only {len(FOREX_CURRENCIES)} currencies"
    for t in ("SBER", "GAZP", "POSI", "FIXP", "GLTR", "MDMG", "SOFL", "VKCO"):
        assert is_moex_equity(t), f"{t} dropped during the merge"
    for c in ("EUR", "USD", "RUB", "TRY", "CNY", "PLN", "THB"):
        assert c in FOREX_CURRENCIES, f"{c} dropped during the merge"


def test_instruments_imports_nothing_from_services():
    """Everything imports this module, so a dependency of its own is a cycle."""
    tree = ast.parse((SERVICES / "instruments.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "app.services"):
            pytest.fail(f"instruments.py imports {node.module}")


def test_futures_are_classified_before_equities():
    """"VTBR-12.26" contains an equity symbol; order of checks decides."""
    assert asset_class("VTBR-12.26") == "futures"
    assert asset_class("VTBR") == "moex"
    assert instruments.is_moex_futures("GAZR-9.26")
    assert not instruments.is_moex_futures("GAZP")
