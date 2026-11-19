"""The LLM fallback was wired up wrong in ways its own unit tests could not see.

tests/test_signal_integrity.py already proves the ledger class works — and it
does. It calls `save()` itself and then checks the next run skips what the
first one tried. Production never called `save()` at all, so the file was never
written, every run started from an empty ledger, and the "one attempt per
message, ever" guarantee the class exists to provide was never in force.

Measured 2026-11-18: 4,603 LLM calls in fifteen days against a free tier of 50
a day, every one of them a 404 from a withdrawn model, and
llm_parse_ledger.json did not exist on disk.

So these tests check the WIRING — that the caller uses the class correctly —
rather than the class. Two of them read the script's source. That is a weaker
instrument than exercising the call, and it is used deliberately: the call site
sits inside a 150-line `main()` that wants a database, a network, a Telegram
fetch and a live model before it reaches the line under test. A source check
that pins the call cannot prove the call works, but it does prove nobody
deleted it again, which is the failure that actually happened.
"""
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "tg_backfill.py"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_the_backfill_persists_every_llm_attempt():
    """An attempt that is not written down is an attempt that gets repeated.

    The free tier allows fifty calls a DAY in total, and the backfill re-reads
    the same 48-hour window every 30 minutes, so a ledger held only in memory
    is the same as no ledger.
    """
    src = _source()
    assert "ledger.save()" in src, (
        "tg_backfill отмечает попытки в журнале, но не сохраняет его — "
        "каждый прогон начнётся с пустого журнала и потратит квоту заново"
    )
    # Immediately after mark(), not at the end of the run: a killed run must
    # not be able to hand the same message back to the model.
    mark = src.index("ledger.mark(")
    save = src.index("ledger.save()", mark)
    between = src[mark:save]
    assert "parse_with_llm" not in between, (
        "журнал сохраняется уже после вызова модели — прогон, убитый между "
        "вызовом и записью, потратит ту же попытку ещё раз"
    )


def test_the_run_reports_what_the_fallback_did():
    """Silence and success looked identical for fifteen days."""
    src = _source()
    assert "ledger.summary()" in src, (
        "прогон не печатает итог LLM-парсера: 4603 отказа подряд прошли "
        "незамеченными именно поэтому"
    )


def test_a_rejection_never_claims_the_model_ran_when_it_did_not():
    """The rejection log is the evidence that the filter is worth anything.

    Writing "ни regex, ни LLM не разобрали" for a message the model never saw
    records our own outage as the source being unparseable — and that is the
    one question the log exists to answer.
    """
    src = _source()
    assert src.count('"ни regex, ни LLM не разобрали"') == 1, (
        "фраза должна остаться ровно одна — внутри ветки, где модель "
        "действительно вызвана"
    )
    claim = src.index('"ни regex, ни LLM не разобрали"')
    call = src.index("parse_with_llm(text)")
    assert call < claim, (
        "вердикт «LLM не разобрал» стоит раньше вызова модели — значит, он "
        "пишется и тогда, когда вызова не было"
    )
    for phrase in ("бюджет прогона", "уже пробовал"):
        assert phrase in src, (
            f"нет отдельной причины отказа «{phrase}»: пропуск по бюджету и "
            f"вердикт модели — разные факты, и их нельзя писать одной строкой"
        )


def test_seen_does_not_disturb_the_counters(tmp_path):
    """`seen` is asked AFTER `should_try` has already refused.

    If it counted, the run summary would report every skip twice and the
    budget diagnosis would be unreadable.
    """
    from app.services.llm_parse_ledger import ParseLedger

    led = ParseLedger(path=str(tmp_path / "l.json"), max_per_run=1)
    led.mark("chan", 1)
    before = (led.used, led.skipped_seen, led.skipped_budget)

    assert led.seen("chan", 1) is True
    assert led.seen("chan", 2) is False
    assert (led.used, led.skipped_seen, led.skipped_budget) == before


def test_seen_tells_a_budget_skip_apart_from_a_verdict(tmp_path):
    """The two reasons a message was not sent to the model are not the same.

    "Already tried" is a statement about the text. "No budget left" is a
    statement about us, and it means nobody has read the message yet — it must
    stay eligible for the next run.
    """
    from app.services.llm_parse_ledger import ParseLedger

    led = ParseLedger(path=str(tmp_path / "l.json"), max_per_run=1)
    assert led.should_try("c", "tried") is True
    led.mark("c", "tried")
    led.save()

    assert led.should_try("c", "tried") is False and led.seen("c", "tried")
    assert led.should_try("c", "unseen") is False and not led.seen("c", "unseen")
    assert led.skipped_budget == 1, "пропуск по бюджету должен считаться отдельно"

    # The budget is per RUN, so the message nobody read is still eligible later.
    nxt = __import__("app.services.llm_parse_ledger", fromlist=["ParseLedger"]) \
        .ParseLedger(path=str(tmp_path / "l.json"), max_per_run=1)
    assert nxt.should_try("c", "unseen") is True
    assert nxt.should_try("c", "tried") is False


def test_the_configured_model_is_not_the_withdrawn_one():
    """A guard against the exact outage, not against model choice in general.

    openai/gpt-oss-20b:free was withdrawn on 2026-11-04. OpenRouter answers
    404 "This model is unavailable for free" and suggests the PAID slug, so a
    copy-paste of its own advice would start spending money silently.
    """
    from app.config import settings

    dead = "openai/gpt-oss-20b:free"
    assert settings.llm_model != dead, (
        f"{dead} отозван — парсер будет отвечать 404 на каждый вызов"
    )
    assert settings.llm_model != "openai/gpt-oss-20b", (
        "это платный слог, который OpenRouter предлагает в тексте ошибки — "
        "подставлять его означает начать тратить деньги молча"
    )


def test_the_per_run_budget_can_be_set_from_the_env_file():
    """`os.getenv` never sees a value that lives only in .env.

    The file said LLM_PARSE_PER_RUN=1 — chosen deliberately for a tier that
    allows 50 calls a day — and the run used the hardcoded 10 anyway, 48 times
    a day. The knob has to be declared on Settings for the file to reach it.
    """
    from app.config import Settings

    assert hasattr(Settings(), "llm_parse_per_run"), (
        "бюджет не объявлен в Settings — значение из .env не будет прочитано"
    )
    src = SCRIPT.read_text(encoding="utf-8")
    assert "settings.llm_parse_per_run" in src, (
        "скрипт по-прежнему берёт бюджет только из os.getenv"
    )


@pytest.mark.parametrize("stage_value", ["parse"])
def test_parse_stage_still_exists_for_the_log(stage_value):
    """The reasons changed; the stage must not, or past rows stop comparing."""
    from app.models.rejected import RejectionStage

    assert RejectionStage.PARSE == stage_value
    assert stage_value in RejectionStage.ALL
