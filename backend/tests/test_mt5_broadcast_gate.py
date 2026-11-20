"""A decision from the terminal is stored; whether it is published is a choice.

The strategy advisors fire on a timer. WEF_Common.mqh defaults CheckInterval to
300 seconds, so a terminal left open on a demo account over a weekend produces
hundreds of decisions from rules with no record behind them — WEF_S1 carries
"3 signals, 0 closed" in its own header, and five of the seven labels have
fewer than five closed trades.

Before this gate existed, `_handle_signal` called `ingest` without naming
`broadcast`, which defaults to True. Attaching an advisor for a shakedown run
therefore pushed machine-generated setups at real subscribers and wrote them
into the track record that is supposed to judge those same advisors.

Storing is not the problem and must keep working: a stored signal is rated and
replayed against candles exactly like a published one, which is how a strategy
earns the right to be published later.
"""
import inspect

import pytest

import app.services.mt5_bridge as bridge


def test_publication_is_off_until_switched_on():
    """The safe direction is the default.

    A flag that must be remembered before a demo run is a flag that will be
    forgotten during one.
    """
    from app.config import Settings

    assert Settings().mt5_broadcast_enabled is False, (
        "по умолчанию мост не должен публиковать: у советников нет измеренной "
        "истории, а терминал на демо-счёте шлёт решения по таймеру"
    )


def test_both_paths_through_the_handler_respect_the_gate():
    """Two kinds of sender reach `ingest`, and both had to be covered.

    S1..S6 send a decision with no candles; WEF_Bridge and S7 send candles and
    let the platform decide. They are separate branches, so a gate applied to
    one of them only would leak through the other.
    """
    src = inspect.getsource(bridge._handle_signal)
    assert src.count("broadcast=settings.mt5_broadcast_enabled") == 2, (
        "обе ветки _handle_signal (готовое решение и решение модели) должны "
        "передавать флаг в ingest — иначе одна из них публикует молча"
    )
    assert "broadcast=True" not in src


def test_ingest_still_accepts_the_flag():
    """Pins the parameter this gate depends on."""
    from app.services.mt5_signals import ingest

    params = inspect.signature(ingest).parameters
    assert "broadcast" in params, "ingest потерял параметр broadcast"
    assert params["broadcast"].default is True, (
        "менять умолчание самого ingest не нужно — его зовут и другие пути; "
        "решение принимается в мосте"
    )


@pytest.mark.asyncio
async def test_a_stored_signal_is_not_silently_dropped(monkeypatch):
    """Not publishing must not become not recording.

    The whole point of the gate is that the outcome stays measurable: if a
    decision vanished instead of being stored, the advisor could never
    accumulate the record that would justify publishing it.
    """
    seen = {}

    async def _fake_ingest(db, **kw):
        seen.update(kw)
        return {"stored": True, "ticker": kw.get("symbol")}

    import app.services.mt5_signals as sigs
    monkeypatch.setattr(sigs, "ingest", _fake_ingest)

    class _Session:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *a):
            return False

    import app.database as dbmod
    monkeypatch.setattr(dbmod, "async_session", lambda: _Session())
    monkeypatch.setattr(bridge.settings, "mt5_broadcast_enabled", False)

    out = await bridge._handle_signal({
        "cmd": "signal", "ticker": "EURUSD", "action": "buy",
        "price": 1.1192, "tp": 1.1250, "sl": 1.1150,
        "strategy_id": 1, "strategy": "Trend Following",
        "reasoning": "EMA12>26",
    })

    assert out.get("stored") is True, "решение должно сохраняться и без публикации"
    assert seen.get("broadcast") is False, "флаг не доехал до ingest"
    assert out.get("broadcast_enabled") is False, (
        "ответ советнику должен сообщать режим: иначе в журнале терминала "
        "«сохранено» и «опубликовано» выглядят одинаково"
    )
