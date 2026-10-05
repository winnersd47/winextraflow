"""Regression tests for the six integrity bugs that reached production.

Every case here corresponds to something that was actually published wrong to a
live channel, or that silently corrupted data. The existing 128 tests caught none
of them — they covered endpoints, not the signal pipeline.

  1. P&L reported from the current price instead of the closing level (+47.7%)
  2. Ancient channel history ingested as fresh signals (BTC entry 43650 from 2024)
  3. Analyst price targets published as trades (R:R 1:22.6, target +226%)
  4. Order-type / leverage words captured as tickers ("SELL LIMIT", "BUY 5-10X")
  5. Seed/demo rows counted in the public track record (717 fake closed trades)
  6. Free-channel teaser exposing the levels it claimed were VIP-only
"""

import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.track_record import _is_seed, _realized_pct
from app.models.signal import Signal, SignalAction, SignalStatus
from app.services.signal_quality import MAX_RR_RATIO, MAX_TP_PCT, check_signal_quality
from app.services.telegram import telegram_parser


def _sig(**kw) -> Signal:
    """Detached Signal for pure-function checks."""
    base = dict(id=uuid.uuid4(), ticker="SBER", action=SignalAction.BUY,
                entry_price=300.0, take_profit=330.0, stop_loss=285.0,
                status=SignalStatus.ACTIVE, ai_confidence=0.7, raw_message="")
    base.update(kw)
    return Signal(**base)


# ── 1. Realized P&L is measured at the closing level ────────────────────────

def test_realized_pnl_uses_closing_level_not_current_price():
    """BUG: BTC bought at 43650 with TP 44400 was reported as +47.7% because the
    monitor used the live price (64k). The realized result is the TP distance."""
    s = _sig(ticker="BTCUSDT", entry_price=43650.0, take_profit=44400.0,
             stop_loss=43300.0, status=SignalStatus.CLOSED_TP)
    pct = _realized_pct(s)
    assert pct == pytest.approx(1.72, abs=0.01)   # not 47.7
    assert pct < 5, "realized profit cannot exceed the TP distance"


def test_realized_pnl_sl_is_negative_and_bounded():
    """BUG: ALGO stop at -1.4% was reported as -94.4%."""
    s = _sig(ticker="ALGOUSDT", entry_price=1.41, take_profit=1.46,
             stop_loss=1.39, status=SignalStatus.CLOSED_SL)
    pct = _realized_pct(s)
    assert pct == pytest.approx(-1.42, abs=0.01)  # not -94.4
    assert pct > -5


def test_realized_pnl_sell_side_sign_is_flipped():
    """A short closing at a lower TP is a profit, not a loss."""
    s = _sig(action=SignalAction.SELL, entry_price=100.0, take_profit=90.0,
             stop_loss=105.0, status=SignalStatus.CLOSED_TP)
    assert _realized_pct(s) == pytest.approx(10.0)
    s.status = SignalStatus.CLOSED_SL
    assert _realized_pct(s) == pytest.approx(-5.0)


# ── 2. Stale channel history must not become a fresh signal ─────────────────

def test_backfill_declares_a_message_age_limit():
    """BUG: channels keep years of history; a 2024 post was ingested as new.
    The limit lives in the backfill script, so assert it exists and is sane."""
    src = (Path(__file__).resolve().parents[1] / "scripts" / "tg_backfill.py").read_text(encoding="utf-8")
    m = re.search(r"MAX_MESSAGE_AGE_HOURS\s*=\s*(\d+)", src)
    assert m, "backfill must define MAX_MESSAGE_AGE_HOURS"
    hours = int(m.group(1))
    assert 1 <= hours <= 168, f"age limit {hours}h is outside a sensible range"
    assert "m.date >= cutoff" in src, "backfill must filter messages by date"


def test_message_age_cutoff_logic():
    """A post from 400 days ago (the BTC-43650 case) falls outside the window."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=48)
    assert (now - timedelta(hours=1)) >= cutoff
    assert (now - timedelta(days=400)) < cutoff


# ── 3. Analyst price targets are not trade setups ──────────────────────────

@pytest.mark.asyncio
async def test_quality_gate_rejects_analyst_price_target(db: AsyncSession):
    """BUG: SNGS published with target +226% vs a -10% stop as 'R:R 1:22.6'."""
    s = _sig(ticker="SNGS", entry_price=15.10, take_profit=49.22, stop_loss=13.59)
    result = await check_signal_quality(db, s)
    assert not result.passed
    assert any("unrealistic" in i.lower() for i in result.issues), result.issues


@pytest.mark.asyncio
async def test_quality_gate_accepts_normal_setup(db: AsyncSession):
    """A sane 2:1 setup must still pass — the guard must not over-reject."""
    s = _sig(entry_price=300.0, take_profit=330.0, stop_loss=285.0, ai_confidence=0.7)
    result = await check_signal_quality(db, s)
    assert result.passed, result.issues


@pytest.mark.asyncio
async def test_quality_gate_rejects_inverted_risk_reward(db: AsyncSession):
    """Reward smaller than risk is a losing setup by construction."""
    s = _sig(entry_price=300.0, take_profit=302.0, stop_loss=280.0)
    result = await check_signal_quality(db, s)
    assert not result.passed


def test_quality_bounds_are_sane():
    assert 1.5 < MAX_RR_RATIO <= 20
    assert 20 <= MAX_TP_PCT <= 100


# ── 4. Ticker validation ───────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "SELL LIMIT @ 4074 TP 4050 SL 4100",     # order type
    "BUY 5-10X @ 1.135",                     # leverage
    "BUY BELOW @ 0.00137",                   # direction word
    "LONG 10X entry 500 TP 550 SL 480",      # leverage
])
def test_parser_rejects_non_ticker_tokens(text):
    """BUG: these produced 'signals' for tickers named LIMIT / 5-10X / BELOW."""
    assert telegram_parser.parse_message(text) is None, text


@pytest.mark.parametrize("text,ticker", [
    ("BUY SBER @ 300 TP: 330 SL: 285", "SBER"),
    ("LONG BTCUSDT entry 65000 TP 68000 SL 62000", "BTCUSDT"),
])
def test_parser_still_accepts_real_tickers(text, ticker):
    parsed = telegram_parser.parse_message(text)
    assert parsed is not None and parsed.ticker == ticker


def test_crypto_range_format_yields_complete_signal():
    """Range format must produce entry+TP+SL, not entry alone."""
    parsed = telegram_parser.parse_message(
        "Long enjusdt 2.47-2.50\nTarget 2.54-2.61-2.74+\nStop loss- 2.4499\nLev- 5x"
    )
    assert parsed is not None
    assert parsed.ticker == "ENJUSDT" and parsed.action == "buy"
    assert parsed.entry_price == pytest.approx(2.47)
    assert parsed.take_profit == pytest.approx(2.54)
    assert parsed.stop_loss == pytest.approx(2.4499)


@pytest.mark.parametrize("promo", [
    "From 1 BTC to 6 BTC Easily! Join our accurate signals here",
    "#Today premium group profit\nLong kavausdt reached 5.59\nProfit 69.15%",
])
def test_parser_ignores_promo_and_results(promo):
    assert telegram_parser.parse_message(promo) is None


# ── 5. Seed/demo rows must never enter the track record ────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("Auto-generated signal #754", True),
    ("auto-generated signal #1", True),
    ("**🇷🇺 Инвест-идеи по русским акциям** Прогноз по акции Газпром", False),
    ('{"ticker":"SBER","action":"buy","price":321.5}', False),
    ("", False),
])
def test_seed_detection(raw, expected):
    """BUG: 772 of 790 closed signals were seed rows, inflating the public
    track record to 717 trades / 64.9% win rate / PF 3.58."""
    assert _is_seed(_sig(raw_message=raw)) is expected


# ── 6. Free-channel teaser must not disclose the levels ───────────────────

def test_teaser_caption_hides_levels():
    """BUG: the teaser promised levels were 'в VIP' while the video showed them."""
    from app.services.signal_clip import build_clip_caption
    entry, tp, sl = 15.10, 49.22, 13.59
    teaser = build_clip_caption("SNGS", "buy", entry, tp, sl, 69, teaser=True)
    for value in (f"{entry}", f"{tp}", f"{sl}", "15.10", "49.22", "13.59"):
        assert value not in teaser, f"teaser leaks {value}"
    assert "VIP" in teaser


def test_vip_caption_does_include_levels():
    """The paid card must still carry the actual numbers."""
    from app.services.signal_clip import build_clip_caption
    full = build_clip_caption("SBER", "buy", 300.0, 330.0, 285.0, 71, teaser=False)
    assert "300" in full and "330" in full and "285" in full


# ── Stale-entry tolerance must follow the market, not a single constant ────

@pytest.mark.parametrize("ticker,klass", [
    ("EURUSD", "forex"), ("GBPJPY", "forex"),
    ("BTCUSDT", "crypto"), ("ENJUSDT", "crypto"),
    ("SBER", "moex"), ("YDEX", "moex"),
    ("BR-8.26", "futures"),
    ("AAPL", "stocks"), ("LSTR", "stocks"),
])
def test_asset_class_detection(ticker, klass):
    from app.services.live_price import asset_class
    assert asset_class(ticker) == klass


def test_stale_tolerance_is_ordered_by_volatility():
    """A single 10% threshold treated EURUSD and an altcoin the same."""
    from app.services.live_price import stale_tolerance
    assert stale_tolerance("EURUSD") < stale_tolerance("SBER") < stale_tolerance("BTCUSDT")
    assert stale_tolerance("EURUSD") <= 0.03
    assert stale_tolerance("BTCUSDT") >= 0.10


# ── Clip renders must not collide ──────────────────────────────────────────

def test_clip_paths_are_unique_per_render():
    """BUG: VIP and teaser clips shared a filename, so one overwrote the other
    and both channels received whichever finished last."""
    from app.services.signal_clip import _clip_path
    paths = [_clip_path("SBER", ""), _clip_path("SBER", "_teaser"), _clip_path("SBER", "")]
    assert len(set(paths)) == 3
    assert str(os.getpid()) in paths[0], "path must be process-scoped"


def test_broadcast_clip_renders_teaser_without_levels():
    """broadcast_clip(teaser=True) must pass hide_levels through, or the free
    channel gets a clip showing the levels its caption calls VIP-only."""
    src = (Path(__file__).resolve().parents[1] / "app" / "services" / "signal_clip.py").read_text(encoding="utf-8")
    body = src.split("async def broadcast_clip", 1)[1]
    assert "hide_levels=teaser" in body


# ── Analyst recommendations must not ship fabricated levels ───────────────

def test_analyst_format_is_flagged_as_derived():
    """The beststocks parser back-calculates the entry and invents a -10% stop.
    Downstream has to know those two numbers are ours, not the source's."""
    msg = ("Тикер: SBER\nРекомендация: Покупать\n"
           "Прогнозная цена: 345 ₽ (+7%)\nhttps://beststocks.ru/rustock/sber")
    parsed = telegram_parser.parse_message(msg)
    assert parsed is not None and parsed.derived_levels is True


def test_explicit_signal_is_not_flagged_as_derived():
    """A channel that publishes its own entry/TP/SL must be taken at its word."""
    parsed = telegram_parser.parse_message("BUY SBER @ 300 TP: 330 SL: 285")
    assert parsed is not None and parsed.derived_levels is False


@pytest.mark.asyncio
async def test_stop_inside_noise_is_widened(monkeypatch):
    """BUG: ENJUSDT/MATIC/CRV/ALGO carried 0.8-1.4% stops against ~4.8% ATR and
    every one closed at a loss. A stop tighter than 1 ATR is noise-bait."""
    from app.services import signal_levels
    monkeypatch.setattr(signal_levels, "atr_pct", lambda *a, **k: _async(0.048))
    lv = await signal_levels.resolve_levels("ENJUSDT", "buy", 2.47, 2.54, 2.4499)
    dist = abs(lv["entry"] - lv["stop_loss"]) / lv["entry"]
    assert dist >= 0.048, f"stop still inside one ATR: {dist:.2%}"
    assert any("шум" in n for n in lv["notes"]), lv["notes"]


@pytest.mark.asyncio
async def test_source_stop_outside_noise_is_kept(monkeypatch):
    """The widening must not touch a stop the source set sensibly."""
    from app.services import signal_levels
    monkeypatch.setattr(signal_levels, "atr_pct", lambda *a, **k: _async(0.02))
    lv = await signal_levels.resolve_levels("SBER", "buy", 300.0, 330.0, 285.0)
    assert lv["stop_loss"] == 285.0
    assert not any("стоп" in n for n in lv["notes"]), lv["notes"]


@pytest.mark.asyncio
async def test_derived_levels_use_live_entry_and_volatility_stop(monkeypatch):
    """BUG: the parser's entry for SBER was 322.43 while the market was 283.98 —
    subscribers were given a price 13.5% away from anything tradable."""
    from app.services import live_price, signal_levels
    monkeypatch.setattr(signal_levels, "atr_pct", lambda *a, **k: _async(0.02))
    monkeypatch.setattr(live_price, "get_live_price", lambda *a, **k: _async({"price": 283.98}))

    lv = await signal_levels.resolve_levels("SBER", "buy", 322.43, 345.0, 290.19,
                                            derived=True)
    assert lv["entry"] == 283.98, "entry must come from the market, not arithmetic"
    dist = abs(lv["entry"] - lv["stop_loss"]) / lv["entry"]
    assert abs(dist - 0.10) > 0.01, "stop is still the fabricated flat 10%"
    assert 0.01 <= dist <= 0.12
    # 345 is a year out from a 284 entry, so it becomes the long-horizon reference
    # and the tradable target sits at 4xATR. The analyst number must not be lost.
    assert lv["long_target"] == 345.0
    assert lv["entry"] < lv["take_profit"] < 345.0


def _async(value):
    """Wrap a value in an awaitable, for monkeypatching async helpers."""
    async def _inner(*a, **k):
        return value
    return _inner()


# ── Free-channel exclusivity must reflect the real score distribution ─────

@pytest.mark.asyncio
async def test_recent_wef_percentile_needs_a_real_sample(db: AsyncSession):
    """With no history the percentile must return None, not a made-up threshold."""
    from app.services.signal_quality import recent_wef_percentile
    assert await recent_wef_percentile(db) is None


def test_teaser_gate_has_both_absolute_and_percentile_rules():
    src = (Path(__file__).resolve().parents[1] / "app" / "services" / "signal_pipeline.py").read_text(encoding="utf-8")
    assert "free_teaser_max_wef" in src
    assert "recent_wef_percentile" in src, "absolute 70 alone made only ~6% VIP-exclusive"


# ── Analyst targets must be converted to a tradable horizon ───────────────

@pytest.mark.asyncio
async def test_far_analyst_target_moves_to_near_target(monkeypatch):
    """An annual +49% forecast against a ~5% stop can only ever resolve at the
    stop, and resolves at nothing for months — which is why no results appeared."""
    from app.services import signal_levels
    monkeypatch.setattr(signal_levels, "atr_pct", lambda *a, **k: _async(0.048))
    lv = await signal_levels.resolve_levels("ONTO", "buy", 268.7, 400.0, 236.5)
    assert lv["long_target"] == 400.0, "the analyst number must be kept, not dropped"
    assert lv["take_profit"] < 400.0
    near_pct = (lv["take_profit"] - 268.7) / 268.7
    assert 0.05 < near_pct < 0.30, f"near target {near_pct:.1%} is not a tradable horizon"


@pytest.mark.asyncio
async def test_close_target_is_left_alone(monkeypatch):
    """We never invent a target more ambitious than the source published."""
    from app.services import signal_levels
    monkeypatch.setattr(signal_levels, "atr_pct", lambda *a, **k: _async(0.048))
    lv = await signal_levels.resolve_levels("SBER", "buy", 300.0, 310.0, 285.0)
    assert lv["take_profit"] == 310.0
    assert lv["long_target"] is None


@pytest.mark.asyncio
async def test_sell_side_near_target_is_below_entry(monkeypatch):
    from app.services import signal_levels
    monkeypatch.setattr(signal_levels, "atr_pct", lambda *a, **k: _async(0.03))
    lv = await signal_levels.resolve_levels("BR-9.26", "sell", 100.0, 60.0, 105.0)
    assert lv["long_target"] == 60.0
    assert 100.0 > lv["take_profit"] > 60.0


# ── Market data routing: silent no-data meant no chart, no ATR, no monitor ──

@pytest.mark.parametrize("ticker,expected", [
    ("BR-9.26", "moex_futures"),
    ("GAZR-12.26", "moex_futures"),
    ("RTS-9.26", "moex_futures"),
    ("SBER", "moex"),
    ("BTCUSDT", "binance"),
    ("AAPL", "stocks"),
])
def test_data_source_routing(ticker, expected):
    from app.services.backtesting_real import detect_source
    assert detect_source(ticker) == expected


def test_binance_symbol_is_normalised():
    """BUG: "ZIL/BTC" was sent verbatim; Binance replied with an error dict which
    was then parsed as candle rows ("could not convert string to float: 'o'")."""
    import inspect
    from app.services import backtesting_real
    src = inspect.getsource(backtesting_real.fetch_binance_candles)
    assert 'replace("/", "")' in src
    assert "isinstance(raw, list)" in src, "error dict must not be parsed as klines"


# ── Money that isn't real must never be countable as a result ─────────────

def test_stress_test_tickers_are_treated_as_seed():
    """BUG: 32 STRESST rows from load testing were opened as paper positions."""
    from app.services.signal_quality import is_seed_signal
    for t in ("STRESST", "TESTTICK", "stresst"):
        assert is_seed_signal(_sig(ticker=t, raw_message="BUY @ 50")) is True
    assert is_seed_signal(_sig(ticker="SBER", raw_message="BUY @ 300")) is False


def test_position_size_makes_a_stop_cost_exactly_the_risk_budget():
    """The whole point of fixed-risk sizing: a stop-out costs the risk, no matter
    how wide the stop is. A 1% stop and a 10% stop must cost the same money."""
    from app.services.position_sizing import position_size
    for stop in (99.0, 95.0, 90.0):
        s = position_size(100_000, 100.0, stop)
        loss = s["position"] * (stop - 100.0) / 100.0
        if not s["position_capped"]:
            assert abs(loss) == pytest.approx(1000.0, rel=0.01)


def test_paid_subscriptions_are_off():
    """Owner's directive: no money until there is a profitable measured record."""
    from app.config import settings
    assert settings.paid_subscriptions_enabled is False


# ── The MT5 bridge spends the LLM key, so the port must not be open ───────

@pytest.mark.asyncio
async def test_bridge_refuses_public_bind_without_token(monkeypatch):
    """Every `analyze` command bills the platform's OpenRouter key. Binding a
    public interface with no shared secret publishes an open LLM proxy."""
    from app.services import mt5_bridge
    monkeypatch.setattr(mt5_bridge, "BRIDGE_TOKEN", "")
    with pytest.raises(mt5_bridge.BridgeAuthError):
        await mt5_bridge.start_mt5_server("0.0.0.0", 8791)


def test_bridge_token_comparison_is_constant_time():
    from app.services import mt5_bridge
    import inspect
    src = inspect.getsource(mt5_bridge._token_ok)
    assert "compare_digest" in src, "token check must not be a plain =="


def test_ea_sends_the_auth_field():
    """The server rejects messages without `auth`, so the EA has to send it."""
    ea = (Path(__file__).resolve().parents[2] / "mt5" / "WEF_Bridge.mq5").read_text(encoding="utf-8")
    assert "BridgeToken" in ea
    assert '\\"auth\\":' in ea, "the analyze request must carry the token"


def test_bridge_has_a_per_connection_llm_budget():
    from app.services import mt5_bridge
    assert 0 < mt5_bridge.MAX_LLM_CALLS_PER_CONN <= 1000
    assert mt5_bridge.MAX_LLM_CALLS_WINDOW_SEC > 0


# ── The daily briefing must not tell VIP that the good stuff is in VIP ────

def test_briefing_texts_differ_per_channel():
    """Both channels used to get the identical message, so VIP subscribers were told
    the strong signals are in the channel they were already reading."""
    import scripts.morning_overview as mo
    d = _briefing_facts()
    assert mo.build_vip(d) != mo.build_free(d)
    assert "Что в VIP" not in mo.build_vip(d)
    assert "Что в VIP" in mo.build_free(d)


def test_briefing_states_the_current_vip_rule():
    """"WEF 70%+" stopped being true: exclusivity is the absolute cut-off OR the top
    percentile, and 70 alone covered ~6% of signals."""
    import scripts.morning_overview as mo
    from app.config import settings
    free = mo.build_free(_briefing_facts())
    assert f"{100 - settings.free_teaser_percentile}%" in free
    assert str(settings.free_teaser_max_wef) in free


def test_briefing_hides_a_low_confidence_regime():
    """A verdict at 24% confidence was published as a heading. Below the floor the
    block is omitted entirely rather than dressed up."""
    import scripts.morning_overview as mo
    low = {**_briefing_facts(), "regime": "low_volatility", "regime_conf": 0.24}
    assert mo.flow_block(low) == []
    high = {**_briefing_facts(), "regime": "low_volatility", "regime_conf": 0.8}
    block = "\n".join(mo.flow_block(high))
    # ...and when shown, it must not pass itself off as a statement about the market.
    assert "не по рынку" in block


def test_briefing_labels_the_change_window():
    """Binance change_pct is a rolling 24h figure; MOEX has no change field, so it is
    derived from the session open. Two different metrics, so two different labels."""
    import scripts.morning_overview as mo
    crypto = mo._fmt({"price": 77000.0, "change_pct": 8.6}, window="за 24ч")
    moex = mo._fmt({"price": 269.8, "open": 271.5}, " ₽")
    assert "за 24ч" in crypto
    assert "с откр." in moex
    # A -0.04% move must not render as "-0.0%".
    assert "-0.0%" not in mo._fmt({"price": 100.0, "open": 100.04})


def test_briefing_number_format_keeps_punctuation():
    """The thousands separator swap ate sentence commas twice before."""
    import scripts.morning_overview as mo
    assert mo._num(208400) == "208 400"
    assert mo._num(-1000, signed=True) == "-1 000"
    d = _briefing_facts()
    assert "закрыто 0," in mo.build_vip(d) or "закрыто 0\n" in mo.build_vip(d)


def _briefing_facts() -> dict:
    """Minimal fact set matching gather()'s shape, so the builders can be unit-tested
    without network or database access."""
    return {
        "min_sample": 30,
        "btc": {"price": 77000.0, "change_pct": 8.6},
        "eth": {"price": 2386.0, "change_pct": 5.0},
        "moex": {"SBER": {"price": 269.8, "open": 271.5}},
        "fg_val": 72, "fg_cls": "Greed",
        "active": 24, "new_24h": 4, "closed_total": 11,
        "closed_24h": [{"ticker": "HEI", "won": False, "pct": -1.7}],
        "regime": None, "regime_conf": 0.0,
        "paper": [{"account": "Основной 100k ₽", "currency": "RUB",
                   "open_trades": 5, "closed_trades": 0, "pnl_money": 0.0}],
    }


# ── The LLM parser must not be re-billed for the same message ─────────────

def test_ledger_tries_each_message_once(tmp_path):
    """The backfill re-reads the same posts ~48 times before they age out of the
    48h window. Without a ledger one unparseable message would cost 48 LLM calls,
    against a free tier of 50 requests per day in total."""
    from app.services.llm_parse_ledger import ParseLedger
    p = str(tmp_path / "ledger.json")

    first = ParseLedger(path=p, max_per_run=10)
    for mid in range(1, 4):
        assert first.should_try("chan", mid)
        first.mark("chan", mid)
    first.save()
    assert first.used == 3

    # Second run over the identical messages must spend nothing.
    second = ParseLedger(path=p, max_per_run=10)
    for mid in range(1, 4):
        assert not second.should_try("chan", mid)
    assert second.used == 0 and second.skipped_seen == 3


def test_ledger_enforces_the_per_run_budget(tmp_path):
    from app.services.llm_parse_ledger import ParseLedger
    led = ParseLedger(path=str(tmp_path / "l.json"), max_per_run=2)
    tried = [mid for mid in range(10) if led.should_try("c", mid) and not led.mark("c", mid)]
    assert len(tried) == 2, "budget must cap calls within one run"
    assert led.skipped_budget == 8


def test_ledger_with_zero_budget_blocks_everything(tmp_path):
    """Free tier without credits allows 50 requests/day for the whole platform, so
    the operator must be able to switch the fallback off entirely."""
    from app.services.llm_parse_ledger import ParseLedger
    led = ParseLedger(path=str(tmp_path / "l.json"), max_per_run=0)
    assert led.should_try("c", 1) is False


def test_ledger_prunes_entries_older_than_the_window(tmp_path):
    import time
    from app.services.llm_parse_ledger import KEEP_HOURS, ParseLedger
    p = str(tmp_path / "l.json")
    led = ParseLedger(path=p, max_per_run=5)
    led._attempts["c:old"] = time.time() - (KEEP_HOURS + 1) * 3600
    led._attempts["c:new"] = time.time()
    led.save()
    reloaded = ParseLedger(path=p, max_per_run=5)
    assert "c:old" not in reloaded._attempts, "ledger would grow without bound"
    assert "c:new" in reloaded._attempts


@pytest.mark.parametrize("raw,want", [
    ("LUKOIL", "LKOH"),        # model emits the transliterated company name
    ("Лукойл", "LKOH"),        # ...or the Russian name
    ("SBERBANK", "SBER"),
    ("Газпром", "GAZP"),
    ("YANDEX", "YDEX"),
    ("BITCOIN", "BTCUSDT"),
    ("SBER", "SBER"),          # already a ticker — unchanged
    ("BR-9.26", "BR-9.26"),    # FORTS code must survive
])
def test_llm_ticker_is_resolved_to_an_exchange_symbol(raw, want):
    """The LLM returns whatever the message called the instrument. "Лукойл" came
    back as LUKOIL, which no price feed knows — so no candles, no ATR and no TP/SL
    monitoring, exactly the silent-no-data failure seen with BR-8.26."""
    from app.services.telegram import _resolve_ticker
    assert _resolve_ticker(raw) == want


def test_resolved_llm_tickers_route_to_a_price_source():
    from app.services.backtesting_real import detect_source
    from app.services.telegram import _resolve_ticker
    for name in ("LUKOIL", "Сбер", "ROSNEFT", "BITCOIN"):
        assert detect_source(_resolve_ticker(name)) in ("moex", "binance", "stocks")


def test_backfill_uses_the_llm_fallback():
    """BUG: tg_backfill.py is what runs on cron, and it did `continue` when the
    regex failed — so the repaired LLM parser never ran on the reliable path."""
    src = (Path(__file__).resolve().parents[1] / "scripts" / "tg_backfill.py").read_text(encoding="utf-8")
    assert "parse_with_llm" in src
    assert "ledger.should_try" in src, "every call must go through the budget"
    assert "MAX_LLM_PARSE_PER_RUN" in src


# ── MT5 signals go through the same gate as everything else ───────────────

@pytest.mark.parametrize("raw,want", [
    ("EURUSD.m", "EURUSD"),      # broker suffix
    ("EURUSDm", "EURUSD"),       # trailing micro letter
    ("GBPUSD-ECN", "GBPUSD"),
    ("XAUUSD.raw", "XAUUSD"),
    ("GOLD", "XAUUSD"),          # alias the price feed does not know
    ("BTCUSD", "BTCUSDT"),
    ("SBER", "SBER"),
    ("BR-9.26", "BR-9.26"),      # FORTS code must survive intact
])
def test_mt5_symbol_normalisation(raw, want):
    """An unrecognised ticker silently yields no candles — no chart, no ATR, no
    TP/SL monitoring. Broker decoration would produce exactly that."""
    from app.services.mt5_signals import normalize_symbol
    assert normalize_symbol(raw) == want


@pytest.mark.asyncio
async def test_mt5_hold_is_not_stored(db: AsyncSession):
    """A decision not to trade is not a signal; storing it would put level-less
    rows into the table the track record counts."""
    from app.services.mt5_signals import ingest
    out = await ingest(db, symbol="SBER", action="hold", price=274.71,
                       tp=None, sl=None, confidence=0.3, broadcast=False)
    assert out["stored"] is False


@pytest.mark.asyncio
async def test_mt5_signal_gets_atr_stop_from_the_terminal(db: AsyncSession):
    """The bridge already computed ATR from the terminal's own candles. Refetching
    from another feed would size the stop off data the trade never executes against."""
    from app.services.mt5_signals import ingest
    out = await ingest(db, symbol="EURUSD.m", action="buy", price=1.0842,
                       tp=1.0855, sl=1.0838,           # stop 0.04%, far inside noise
                       confidence=0.72,
                       indicators={"price": 1.0842, "atr_pct": 0.62},
                       broadcast=False)
    assert out["stored"] and out["ticker"] == "EURUSD"
    dist = abs(out["entry"] - out["sl"]) / out["entry"]
    assert dist >= 0.0062, f"stop {dist:.4%} is still inside one ATR"
    assert any("шум" in n for n in out["notes"]), out["notes"]


@pytest.mark.asyncio
async def test_mt5_provider_is_not_seed(db: AsyncSession):
    """It must count in rankings and in the landing-page totals as a real source."""
    from app.services.mt5_signals import get_or_create_provider
    p = await get_or_create_provider(db)
    assert p.is_seed is False
    assert p.source.value == "mt5"
    # Idempotent: a second call must not create a duplicate provider.
    again = await get_or_create_provider(db)
    assert again.id == p.id


def test_model_confidence_is_stored_but_not_the_wef_score():
    """The model's self-assessment is recorded separately and deliberately kept out
    of the score until scripts/wef_validation.py shows it predicts something."""
    from app.models.signal import Signal as S
    cols = {c.name for c in S.__table__.columns}
    assert "source_confidence" in cols and "ai_confidence" in cols
    rating = (Path(__file__).resolve().parents[1] / "app" / "services" / "ai_rating.py").read_text(encoding="utf-8")
    assert "source_confidence" not in rating, "not a WEF factor until it is validated"


def test_ea_trades_on_the_quality_gate_not_model_confidence():
    ea = (Path(__file__).resolve().parents[2] / "mt5" / "WEF_Bridge.mq5").read_text(encoding="utf-8")
    assert "PublishToPlatform" in ea
    assert 'verdict == "SKIP"' in ea, "the gate verdict must gate the trade"
    assert "confidence >= 0.6" not in ea, "model self-assessment must not trigger trades"


# ── Rankings must not be built from demo fixtures ─────────────────────────

def test_seed_providers_are_flagged():
    """Every provider carrying a win rate was a seed fixture with a Sharpe of
    3-13, and the leaderboard consisted entirely of them."""
    import inspect
    from app.services import seed_data
    src = inspect.getsource(seed_data)
    assert "is_seed=True" in src, "seeded providers must be marked"


def test_provider_rankings_exclude_seed():
    from pathlib import Path as _P
    root = _P(__file__).resolve().parents[1]
    for rel in ("app/api/providers.py", "app/api/ai_chat.py", "app/services/email_digest.py"):
        src = (root / rel).read_text(encoding="utf-8")
        if "win_rate.desc()" not in src:
            continue
        assert "is_seed.is_(False)" in src, f"{rel} ranks providers without excluding seed"


# ── Regime detection was called through a method that does not exist ──────

def test_regime_detector_has_no_detect_regime_method():
    """`detect_regime()` was called in three places; the real API is
    `await detect(db)`. The digest swallowed the AttributeError and reported
    "unknown" every week; the chat endpoint returned 500."""
    from app.services.quant.regime import regime_detector
    assert not hasattr(regime_detector, "detect_regime")
    assert hasattr(regime_detector, "detect")


def test_no_caller_uses_the_nonexistent_regime_method():
    root = Path(__file__).resolve().parents[1]
    for rel in ("app/main.py", "app/api/ai_chat.py", "app/services/email_digest.py"):
        src = (root / rel).read_text(encoding="utf-8")
        for line in src.splitlines():
            if "detect_regime(" in line and not line.strip().startswith("#"):
                pytest.fail(f"{rel} still calls detect_regime(): {line.strip()}")


# ── The assistant must not invent numbers or give advice ──────────────────

def test_assistant_rejects_ungrounded_numbers():
    from app.services.ai_assistant import _ungrounded_numbers
    facts = {"вход": 283.98, "цель": 306.7}
    assert not _ungrounded_numbers("Вход 283.98, цель 306.7", facts)
    assert "999.5" in _ungrounded_numbers("Цель на самом деле 999.5", facts)


def test_assistant_rejects_investment_advice():
    from app.services.ai_assistant import _looks_like_advice
    assert _looks_like_advice("Рекомендую купить сейчас")
    assert _looks_like_advice("Стоит купить на этих уровнях")
    assert not _looks_like_advice("Закрытых сделок 7, статистики недостаточно")


def test_assistant_accepts_russian_thousands_separator():
    """The model writes 208<U+202F>400. Read as two tokens it matched nothing in
    the facts, so every answer containing money fell back to the template."""
    from app.services.ai_assistant import _ungrounded_numbers
    facts = {"вложено_всего": 208400.0}
    for sep in (" ", " ", " ", " "):
        assert not _ungrounded_numbers(f"Вложено 208{sep}400 ₽", facts), repr(sep)


def test_assistant_rejects_degenerate_output():
    """A dashboard answer came back as several hundred exclamation marks and passed
    every content check: long enough, no advice, no numbers to be ungrounded."""
    from app.services.ai_assistant import _is_degenerate
    assert _is_degenerate("!" * 300)
    assert _is_degenerate("=" * 60)
    assert _is_degenerate("")
    assert not _is_degenerate("Активных сигналов 10, закрытых сделок 8 — этого мало.")


# ── Nothing user-facing may be counted from demo fixtures ─────────────────

@pytest.mark.asyncio
async def test_landing_stats_count_only_real_rows(client, db: AsyncSession):
    """The landing page advertised 1436 signals (120 real), 34 providers (14 real)
    and 76 strategies — 66 of which were two hardcoded constants — plus a literal
    telegram_messages=10044 presented as a live figure."""
    from sqlalchemy import func
    from app.models.provider import Provider

    data = (await client.get("/api/v1/public/stats")).json()
    assert "telegram_messages" not in data, "hardcoded 10044 must not be published"

    # Every published count must be a real count, so none may exceed the table.
    rows_sig = (await db.execute(select(func.count(Signal.id)))).scalar() or 0
    rows_prov = (await db.execute(select(func.count(Provider.id)))).scalar() or 0
    assert data["signals"] <= rows_sig
    assert data["providers"] <= rows_prov


def test_landing_stats_have_no_hardcoded_inventory():
    src = (Path(__file__).resolve().parents[1] / "app" / "api" / "public.py").read_text(encoding="utf-8")
    body = src[src.index('@router.get("/stats")'):]
    body = body[:body.index('@router.get', 10)]
    assert "mt5_count = 50" not in body and "tv_count = 16" not in body
    assert '"telegram_messages"' not in body
    assert "is_seed.is_(False)" in body and "not_seed" in body


def test_screener_excludes_seed_and_gates_win_rate():
    src = (Path(__file__).resolve().parents[1] / "app" / "api" / "screener.py").read_text(encoding="utf-8")
    assert "not_seed()" in src, "screener ranks the same tickers seed_data generates"
    assert "MIN_SAMPLE" in src, "per-ticker win rate needs a sample floor"


@pytest.mark.asyncio
async def test_unified_marketplace_invents_no_ratings(client, auth_headers: dict):
    """The page the marketplace actually calls built its own dicts and bypassed the
    _enrich_strategy fix. Two inventions reached the UI from there: a star rating
    computed as ai_score x 5 from a seeded provider, and `reviews` that was really
    the signal count — nobody had reviewed anything."""
    d = (await client.get("/api/v1/strategies/unified-marketplace",
                          headers=auth_headers)).json()
    assert "notice_ru" in d and "stats_as_of" in d
    for item in d["items"]:
        if item["source"] == "provider":
            assert item["rating"] is None, "platform strategies have no reviews"
            assert item["reviews"] is None
            if item.get("is_demo"):
                for k in ("win_rate", "sharpe_ratio", "ai_score", "subscriber_count"):
                    assert item[k] is None, f"demo row leaks {k}"
        elif item["source"] == "mt5":
            # A real MQL5 rating is allowed, but only with its snapshot date.
            if item.get("rating"):
                assert item.get("stats_as_of"), "undated rating reads as current"
                assert item.get("stats_are_live") is False


def test_advisor_stats_carry_a_snapshot_date():
    """rating/reviews are a hand-copied MQL5 snapshot that was never refreshed while
    the marketplace sorted by them."""
    from app.api.advisors import STATS_AS_OF, _stats_notice
    from datetime import date
    date.fromisoformat(STATS_AS_OF)          # must be a real date
    n = _stats_notice()
    assert n["stats_are_live"] is False
    assert STATS_AS_OF in n["stats_notice_ru"]
    assert n["stats_age_days"] is not None and n["stats_age_days"] >= 0


def test_marketplace_hides_fabricated_metrics():
    """Ten published strategies all belong to seed providers, and claimed 38-134
    subscribers each on a platform with twelve users."""
    src = (Path(__file__).resolve().parents[1] / "app" / "api" / "strategies.py").read_text(encoding="utf-8")
    assert "is_demo" in src
    assert 'data["subscriber_count"] = None' in src, "fabricated social proof must not ship"


def test_portfolio_win_rate_is_none_without_trades():
    """A literal 0 rendered as "win rate 0%", which reads as losing every trade."""
    src = (Path(__file__).resolve().parents[1] / "app" / "api" / "portfolio.py").read_text(encoding="utf-8")
    assert "else None" in src


def test_migration_backfills_scalar_defaults():
    """ALTER TABLE ADD COLUMN leaves existing rows NULL while `default=` only fires
    on insert, so a new flag excluded every pre-existing row instead of none."""
    from importlib.util import module_from_spec, spec_from_file_location
    path = Path(__file__).resolve().parents[1] / "scripts" / "migrate_schema.py"
    src = path.read_text(encoding="utf-8")
    assert "_default_literal" in src
    assert "IS NULL" in src, "existing rows must be backfilled, not left NULL"


# ── Config wiring that silently disabled a whole feature ──────────────────

def test_llm_settings_are_declared_in_config():
    """BUG: the code read os.environ, so the .env key never reached the parser
    and the LLM fallback silently never ran."""
    from app.config import settings
    assert hasattr(settings, "openrouter_api_key")
    assert hasattr(settings, "llm_model") and settings.llm_model


# ── No third-party attribution obligations in the UI ──────────────────────

def test_no_tradingview_widgets_remain():
    """TradingView's free widgets require a visible attribution link; the badge sat
    on top of the prices, and hiding it with CSS would breach their terms. So the
    widgets were replaced by our own components over data we already fetch."""
    import re
    front = Path(__file__).resolve().parents[2] / "frontend" / "src"
    offenders = []
    for path in front.rglob("*.tsx"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "s3.tradingview.com" in line and not line.lstrip().startswith(("*", "//", "/*")):
                offenders.append(f"{path.name}: {line.strip()[:70]}")
    assert not offenders, offenders


def test_lightweight_charts_is_gone():
    """Apache-2.0, but its terms additionally demand a user-facing TradingView link,
    rendered by `attributionLogo` (on by default). ECharts carries no such
    user-facing requirement."""
    import json
    pkg = json.loads((Path(__file__).resolve().parents[2] / "frontend" / "package.json")
                     .read_text(encoding="utf-8"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    assert "lightweight-charts" not in deps
    assert "echarts" in deps


def test_heatmap_serves_every_market_with_a_price():
    """CustomHeatmap renders t.price in each tile, and the MOEX branch read
    `last_price` — a key the service never returns — so every MOEX tile showed 0."""
    src = (Path(__file__).resolve().parents[1] / "app" / "api" / "public.py").read_text(encoding="utf-8")
    body = src[src.index('@router.get("/heatmap")'):]
    body = body[:body.index("@router.get", 10)] if "@router.get" in body[10:] else body
    assert '"last_price"' not in body
    assert body.count('"price"') >= 3, "all three markets must supply a price"


def test_econ_calendar_calls_primary_sources_only():
    """Aggregators were rejected: paid/key-gated with attribution terms, or scraping
    investing.com against its terms. Checks the hosts actually requested, not the
    prose — the module names those aggregators on purpose, to say why they are out."""
    import re
    src = (Path(__file__).resolve().parents[1] / "app" / "services" / "econ_calendar.py").read_text(encoding="utf-8")
    hosts = set(re.findall(r'https?://([a-z0-9.\-]+)', src))
    banned = {"investing.com", "tradingeconomics.com", "eodhd.com",
              "financialmodelingprep.com", "site.financialmodelingprep.com",
              "ohlc.dev"}
    assert not (hosts & banned), hosts & banned
    # Requested hosts must all be the institutions that publish the data.
    assert any("cbr" in h for h in hosts)
    assert any("moex" in h for h in hosts)
    assert any("stlouisfed" in h for h in hosts)


@pytest.mark.asyncio
async def test_econ_calendar_declares_missing_sources(client):
    """A missing source and an empty calendar look identical unless one is stated."""
    d = (await client.get("/api/v1/public/econ-calendar")).json()
    assert "sources" in d and "notes" in d
    from app.config import settings
    if not settings.fred_api_key:
        assert any("FRED" in n for n in d["notes"]), "silent US gap"


# ── Crypto data must not hang off a single exchange ───────────────────────

@pytest.mark.asyncio
async def test_crypto_price_falls_back_to_the_other_exchange(monkeypatch):
    """Every crypto quote used to come from Binance alone: one block or outage there
    and the signal loses its price, its ATR and its monitoring."""
    from app.services import live_price as L

    async def dead(_t):
        return None

    async def alive(_t):
        return {"ticker": _t, "price": 1.0, "source": "Bybit"}

    monkeypatch.setattr(L, "_binance_price", dead)
    monkeypatch.setattr(L, "_bybit_price", alive)
    got = await L._crypto_price("BTCUSDT")
    assert got and got["source"] == "Bybit"

    # Both down must be None, not a fabricated zero.
    monkeypatch.setattr(L, "_bybit_price", dead)
    assert await L._crypto_price("BTCUSDT") is None


@pytest.mark.asyncio
async def test_crypto_price_respects_the_primary_setting(monkeypatch):
    from app.services import live_price as L

    async def b(_t):
        return {"ticker": _t, "price": 1.0, "source": "Binance"}

    async def y(_t):
        return {"ticker": _t, "price": 1.0, "source": "Bybit"}

    monkeypatch.setattr(L, "_binance_price", b)
    monkeypatch.setattr(L, "_bybit_price", y)
    monkeypatch.setattr(L, "CRYPTO_PRIMARY", "bybit")
    assert (await L._crypto_price("BTCUSDT"))["source"] == "Bybit"
    monkeypatch.setattr(L, "CRYPTO_PRIMARY", "binance")
    assert (await L._crypto_price("BTCUSDT"))["source"] == "Binance"


def test_bybit_percent_is_scaled_from_a_fraction():
    """Bybit's price24hPcnt is 0.0145 for a 1.45% move. Passed through unscaled it
    would understate every crypto change by 100x."""
    import inspect
    from app.services import live_price as L
    src = inspect.getsource(L._bybit_price)
    assert 'price24hPcnt", 0) or 0) * 100' in src


def test_crypto_candles_have_a_fallback():
    """Candles feed the ATR that sizes every stop; one source meant a silent zero."""
    from app.services import backtesting_real as B
    assert hasattr(B, "fetch_bybit_candles") and hasattr(B, "fetch_crypto_candles")
    src = (Path(__file__).resolve().parents[1] / "app" / "services" / "backtesting_real.py").read_text(encoding="utf-8")
    assert "fetch_crypto_candles(ticker, date_from, date_to)" in src, \
        "detect_source=binance must route through the fallback"


def test_bybit_candles_are_oldest_first():
    """Bybit returns newest-first; every caller assumes oldest-first, so an
    unreversed list would make ATR and charts read the series backwards."""
    import inspect
    from app.services import backtesting_real as B
    assert "candles.reverse()" in inspect.getsource(B.fetch_bybit_candles)


def test_both_crypto_exchanges_are_health_monitored():
    """With a fallback in place, which exchange is down is the difference between a
    slowdown and an outage — so both must be visible."""
    from app.services.health_monitor import health_monitor
    assert "binance" in health_monitor.sources
    assert "bybit" in health_monitor.sources


# ── A connected exchange account must not trade real money by default ─────

def test_exchange_accounts_default_to_testnet():
    from app.models.exchange_account import ExchangeAccount
    col = ExchangeAccount.__table__.columns["is_testnet"]
    assert col.default.arg is True, "a new account must not be able to place a real order"


def test_bybit_testnet_uses_a_separate_host():
    from app.services.exchanges.bybit import (BYBIT_BASE_URL, BYBIT_TESTNET_URL,
                                              BybitAdapter)
    assert BYBIT_TESTNET_URL != BYBIT_BASE_URL
    assert str(BybitAdapter("k", "s", testnet=True).client.base_url).startswith(BYBIT_TESTNET_URL)
    assert str(BybitAdapter("k", "s").client.base_url).startswith(BYBIT_BASE_URL)


def test_testnet_account_never_gets_a_live_only_adapter():
    """An adapter with no testnet mode, handed live keys by an account marked
    virtual, would place real orders while the UI said otherwise."""
    from app.models.exchange_account import ExchangeAccount, ExchangeName
    from app.services.execution import _get_adapter, encrypt_value
    a = ExchangeAccount(user_id=None, exchange=ExchangeName.TINKOFF, label="probe",
                        api_key_encrypted=encrypt_value("k"),
                        api_secret_encrypted=encrypt_value("s"))
    a.is_testnet = True
    assert type(_get_adapter(a)).__name__ == "DemoAdapter"


# ── A health check must not fail on its own probe ─────────────────────────

def test_telegram_health_probes_the_bot_api_not_a_datacenter_ip():
    """The check replaced its URL with https://149.154.167.50:443 — a Telegram
    datacenter, which speaks MTProto and presents no certificate for that address.
    It therefore reported "degraded / CERTIFICATE_VERIFY_FAILED" permanently while
    posting to both channels worked, and dragged `overall` down with it."""
    src = (Path(__file__).resolve().parents[1] / "app" / "services" / "health_monitor.py").read_text(encoding="utf-8")
    # Executable lines only — the module names that IP on purpose, to record why it
    # is wrong. Checking the prose would flag the explanation itself.
    code = [ln for ln in src.splitlines() if not ln.lstrip().startswith("#")]
    assert not [ln for ln in code if "149.154.167.50" in ln], \
        "a DC IP is not an HTTP health endpoint"
    assert any("api.telegram.org" in ln for ln in code)


@pytest.mark.asyncio
async def test_telegram_health_never_leaks_the_bot_token():
    """The probe URL carries the token; the reported url must not."""
    from app.services.health_monitor import health_monitor
    from app.config import settings
    s = await health_monitor.check_source("telegram")
    if settings.telegram_bot_token:
        assert settings.telegram_bot_token not in (s.url or "")
        assert "<token>" in s.url


@pytest.mark.asyncio
async def test_telegram_health_is_ok_when_the_api_answers():
    """Posting works, so the source must not report a problem."""
    from app.services.health_monitor import health_monitor
    s = await health_monitor.check_source("telegram")
    assert s.status in ("ok", "degraded")
    if s.status == "degraded":
        # Only an actionable reason is acceptable — not a broken probe.
        assert "token" in (s.last_error or "").lower() or s.latency_ms >= 3000, s.last_error


# ── Channel posts must not promote circumventing a block ──────────────────

def test_access_note_does_not_advise_circumvention():
    """ст. 13.41 КоАП (in force since March 2024) penalises *promoting* means of
    circumventing restrictions, and a channel post is a public promotion. The note
    may state that the site is unreachable; it may not tell readers what to install."""
    from app.services.signal_chart import PLATFORM_ACCESS_NOTE
    low = PLATFORM_ACCESS_NOTE.lower()
    for banned in ("vpn", "прокси", "proxy", "обход", "зеркал", "tor"):
        assert banned not in low, f"note promotes circumvention: {banned}"
    # ...and it must offer the lawful alternative instead of just apologising.
    assert "канал" in low


def test_posts_carry_the_access_note_while_the_host_is_unreachable():
    root = Path(__file__).resolve().parents[1] / "scripts"
    for name in ("lesson_post.py", "morning_overview.py"):
        src = (root / name).read_text(encoding="utf-8")
        assert "PLATFORM_ACCESS_NOTE" in src, name


def _lesson_post_module():
    """Import scripts/lesson_post.py — its entrypoint is guarded, so this is safe."""
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "scripts" / "lesson_post.py"
    spec = importlib.util.spec_from_file_location("lesson_post_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_full_article_fits_telegram_limits():
    """The note promises the full text in the channel, so it has to be publishable:
    Telegram rejects anything over 4096 characters."""
    from app.models.lesson import Lesson, LessonTopic
    from app.services.lesson_seed import LESSONS
    mod = _lesson_post_module()

    for spec in LESSONS:
        lesson = Lesson(slug=spec["slug"], title=spec["title"],
                        topic=LessonTopic(spec["topic"]), teaser=spec["teaser"],
                        body=spec["body"], position=spec["position"])
        parts = mod.build_full_posts(lesson)
        assert parts, spec["slug"]
        for part in parts:
            assert len(part) <= mod.TG_LIMIT, f"{spec['slug']}: {len(part)} chars"
        assert len(mod.build_post(lesson)) <= mod.TG_LIMIT, spec["slug"]


def test_markdown_to_telegram_escapes_and_drops_unsupported():
    """An unescaped '<' makes Telegram reject the whole message; tables and fences
    have no equivalent in its HTML subset."""
    mod = _lesson_post_module()
    md = "\n".join([
        "# Заголовок",
        "## Раздел",
        "| a | b |",
        "|---|---|",
        "| 1 | 2 |",
        "- пункт",
        "**жирный** и `код` и 5 < 6",
        "```",
        "block",
        "```",
    ])
    out = mod.md_to_telegram(md)
    assert "# Заголовок" not in out and "|---|" not in out
    assert "<b>Раздел</b>" in out and "• пункт" in out
    assert "5 &lt; 6" in out, "raw < would break the message"
    assert "```" not in out
    assert "a · b" in out, "table rows should survive as text"


# ── Per-signal historical check must not become a success probability ─────

def test_breakeven_rate_matches_the_geometry():
    """4:2 needs a third of trades to work; 1:2 needs two thirds. This is the number
    a historical hit rate has to be compared against — a rate quoted alone says
    nothing (see the lesson on win rate)."""
    from app.services.signal_geometry import breakeven_hit_rate
    assert breakeven_hit_rate(4, 2) == pytest.approx(33.3, abs=0.1)
    assert breakeven_hit_rate(1, 1) == pytest.approx(50.0, abs=0.1)
    assert breakeven_hit_rate(1, 2) == pytest.approx(66.7, abs=0.1)


@pytest.mark.asyncio
async def test_geometry_withholds_the_rate_on_a_small_sample(monkeypatch):
    """A hit rate over a handful of setups is noise, so it is not reported at all —
    the same rule as the track record and the screener."""
    from app.services import signal_geometry as G

    async def few(*_a, **_k):
        return [{"open": 100, "high": 101, "low": 99, "close": 100} for _ in range(20)]

    import app.services.backtesting_real as B
    monkeypatch.setattr(B, "fetch_candles", few)
    r = await G.geometry_hit_rate("TEST", "buy")
    assert r["enough_data"] is False
    assert r["hit_rate_pct"] is None
    assert r["min_occurrences"] == G.MIN_OCCURRENCES


@pytest.mark.asyncio
async def test_geometry_counts_the_stop_when_both_levels_hit_in_one_bar(monkeypatch):
    """Intraday order is unknown. Assuming the favourable level would flatter every
    result, so a bar touching both counts as a stop."""
    from app.services import signal_geometry as G
    import app.services.backtesting_real as B

    # Flat history to establish an ATR, then one bar spanning both levels.
    bars = [{"open": 100, "high": 101, "low": 99, "close": 100} for _ in range(80)]
    bars.append({"open": 100, "high": 130, "low": 70, "close": 100})
    bars += [{"open": 100, "high": 101, "low": 99, "close": 100} for _ in range(40)]

    async def hist(*_a, **_k):
        return bars

    monkeypatch.setattr(B, "fetch_candles", hist)
    r = await G.geometry_hit_rate("TEST", "buy")
    assert r["hit_stop"] >= 1, "a bar touching both must not count as a target"


@pytest.mark.asyncio
async def test_geometry_endpoint_states_what_it_does_not_measure(client):
    """Published as a success probability this would be exactly the kind of claim
    the project has spent the session removing."""
    d = (await client.get("/api/v1/public/geometry-baseline?ticker=SBER")).json()
    assert "does_not_measure" in d and "правило входа" in d["does_not_measure"]
    assert "breakeven_pct" in d
    if d["hit_rate_pct"] is not None:
        assert d["vs_breakeven_pp"] == pytest.approx(
            d["hit_rate_pct"] - d["breakeven_pct"], abs=0.11)


def test_caption_omits_geometry_on_a_small_sample():
    """The baseline line must not appear at all below the sample floor — a rate over
    five setups presented in a paid signal card is exactly the wrong thing."""
    from app.services.signal_chart import build_caption
    cap = build_caption("X", "buy", 100, 110, 95, 60, trend="unknown",
                        recent_change=0.0,
                        geometry={"enough_data": False, "hit_rate_pct": None,
                                  "tp_mult": 4, "sl_mult": 2, "occurrences": 5,
                                  "reached_target": 3})
    assert "История инструмента" not in cap


def test_caption_geometry_line_names_random_entry():
    """Phrasing matters: without «при случайном входе» the number reads as this
    signal's win probability, which the walk cannot support."""
    from app.services.signal_chart import build_caption
    cap = build_caption("SBER", "buy", 300, 330, 285, 68, trend="unknown",
                        recent_change=0.0,
                        geometry={"enough_data": True, "hit_rate_pct": 36.3,
                                  "breakeven_pct": 33.3, "tp_mult": 4, "sl_mult": 2,
                                  "occurrences": 300, "reached_target": 109})
    assert "при случайном входе" in cap
    assert "Безубыточная доля" in cap


def test_caption_says_geometry_is_unprofitable_when_below_breakeven():
    """GAZP measures 31.7% against a 33.3% breakeven. Reporting that as a positive
    would invert its meaning."""
    from app.services.signal_chart import build_caption
    cap = build_caption("GAZP", "buy", 83, 90, 80, 68, trend="unknown",
                        recent_change=0.0,
                        geometry={"enough_data": True, "hit_rate_pct": 31.7,
                                  "breakeven_pct": 33.3, "tp_mult": 4, "sl_mult": 2,
                                  "occurrences": 379, "reached_target": 120})
    assert "убыточна" in cap


# ── One auth key, one connection ──────────────────────────────────────────

def test_in_app_telethon_worker_is_off_by_default():
    """The worker and scripts/tg_backfill.py share winextraflow_bot.session. The
    backfill works on a copy, but a copy carries the same auth key, and two live
    connections leaving through different SOCKS5 exit IPs make Telegram revoke it:

        AuthKeyDuplicatedError: used under two different IP addresses simultaneously

    That happened on 2026-09-01 and stopped ingestion for a week. Recovery needs a
    phone and an SMS code, so the default must keep them from ever overlapping."""
    from app.config import Settings
    assert Settings.model_fields["telegram_worker_enabled"].default is False


def test_worker_startup_is_gated_on_the_flag():
    src = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(encoding="utf-8")
    assert "settings.telegram_worker_enabled and settings.telegram_api_id" in src, \
        "the worker must not start on api_id alone"


# ── EV must come from a measured win rate, or not be shown ────────────────

@pytest.mark.asyncio
async def test_win_rate_is_withheld_below_the_sample_floor(db: AsyncSession):
    """EV, Profit Factor and Kelly are all functions of the win rate. It used to be
    a constant — main.py had `win_rate = 0.60` and signal_chart.py assumed
    0.65/0.55/0.45 by trend — while the measured record was 0 wins in 11 trades."""
    from app.services.measured_stats import measured_win_rate
    wr = await measured_win_rate(db)
    assert wr["rate"] is None or wr["enough_data"], \
        "a rate must never be returned below the floor"
    if not wr["enough_data"]:
        assert wr["rate"] is None


@pytest.mark.asyncio
async def test_expert_metrics_refuse_to_guess(db: AsyncSession):
    from app.services.measured_stats import expert_metrics
    s = _sig()
    m = await expert_metrics(db, s, None)
    if not m["available"]:
        assert "reason" in m
        for k in ("ev_per_trade_pct", "profit_factor", "kelly_half_pct"):
            assert m.get(k) is None, f"{k} leaked without a measured rate"


def test_caption_hides_ev_block_without_measurement():
    """A figure derived from an assumption and printed as a calculation is worse
    than no figure: the reader cannot tell which it is."""
    from app.services.signal_chart import build_caption
    cap = build_caption("SBER", "buy", 300, 330, 285, 68, trend="unknown",
                        recent_change=0.0,
                        expert={"verdict": "GOOD", "metrics_available": False,
                                "metrics_reason": "Мат. ожидание не рассчитано: "
                                                  "измеренных сделок 11, нужно 30."})
    for tag in ("EV:", "Profit Factor", "Kelly"):
        assert tag not in cap, f"{tag} shown without a measured win rate"
    assert "не рассчитано" in cap


def test_caption_shows_ev_block_when_measured():
    """The guard must not suppress real figures once the sample exists."""
    from app.services.signal_chart import build_caption
    cap = build_caption("SBER", "buy", 300, 330, 285, 68, trend="unknown",
                        recent_change=0.0,
                        expert={"verdict": "GOOD", "metrics_available": True,
                                "ev_per_trade_pct": 1.4, "profit_factor": 1.7,
                                "kelly_half_pct": 2.2, "edge_pct": 3.1})
    assert "EV:" in cap and "Profit Factor" in cap and "Kelly" in cap


def test_no_assumed_win_rate_feeds_the_pipeline():
    """The 0.60 constant must not reach the card again."""
    root = Path(__file__).resolve().parents[1] / "app"
    pipe = (root / "services" / "signal_pipeline.py").read_text(encoding="utf-8")
    assert "measured_stats" in pipe, "pipeline must source metrics from measurement"
    assert 'expert.get("ev_per_trade_pct")' not in pipe, \
        "the recommendation engine's assumed EV must not be forwarded"


@pytest.mark.asyncio
async def test_recommendations_prefer_measured_atr(monkeypatch):
    """VOLATILITY_MAP is hand-written and off by up to a third (SBER 2.5% assumed
    vs 1.65% actual); every stop and target derives from it."""
    src = (Path(__file__).resolve().parents[1] / "app" / "services" / "quant"
           / "recommendations.py").read_text(encoding="utf-8")
    assert "atr_pct" in src, "measured ATR must be preferred"
    i = src.index("base_vol = None")
    j = src.index("VOLATILITY_MAP.get(ticker, 2.5)", i)
    assert "atr_pct" in src[i:j], "the table must be the fallback, not the default"
