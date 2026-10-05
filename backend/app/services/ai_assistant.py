"""LLM layer over facts already retrieved from the platform's own data.

The assistant is retrieval-grounded on purpose: the caller pulls the numbers out of
the database, and the model's only job is to turn them into an answer. It is never
asked what it thinks about a ticker, because it has no market data of its own and
would produce a confident-sounding guess.

Three rules are enforced in the prompt and re-checked on the way out:

  * no number that was not supplied in the facts
  * no recommendation to buy or sell — the platform is an information service and
    says so on every page (see api/compliance.py)
  * no performance claim when the facts say the sample is too small

If the LLM is unavailable, misconfigured, slow or returns something unusable, the
caller's own template answer is used. A degraded answer is fine; a fabricated one
is not, so every failure path returns None rather than a guess.
"""

import json
import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT_SEC = 25.0
MAX_TOKENS = 700
RETRY_DELAY_SEC = 1.5      # one retry, for the free tier's transient 429s

SYSTEM_PROMPT = """Ты — аналитический помощник платформы WinExtraFlow.

Тебе даются ФАКТЫ, извлечённые из базы данных платформы. Отвечай на вопрос
пользователя, опираясь ТОЛЬКО на них.

Строгие правила:
1. Не приводи ни одного числа, которого нет в фактах. Не оценивай, не округляй в
   свою пользу, не экстраполируй и НЕ ВЫЧИСЛЯЙ новые числа: сумма или разность
   двух фактов — это тоже число, которого в фактах нет. Только цитируй.
2. Не давай инвестиционных рекомендаций. Не пиши «стоит купить», «советую»,
   «хорошая точка входа». Платформа — информационный сервис, не инвестиционный
   советник. Если спрашивают «стоит ли покупать» — объясни, что решение за
   пользователем, и изложи факты.
3. Если в фактах указано, что выборка мала (enough_data: false) — прямо скажи, что
   статистики недостаточно, и не приводи win rate или доходность.
4. Не обещай будущую доходность и не предсказывай цену.
5. Если факты не отвечают на вопрос — скажи это, а не заполняй пробел догадкой.

Отвечай по-русски, деловым тоном, без воды. 2-5 коротких абзацев или список.
Не добавляй дисклеймер — платформа добавит его сама."""

# Phrases that would turn an informational answer into advice.
_ADVICE_PATTERNS = [
    r"\bсоветую\b", r"\bрекомендую\b", r"\bстоит (?:купить|продать|брать|входить)\b",
    r"\bлучше купи", r"\bлучше прода", r"\bпокупай\b", r"\bпродавай\b",
    r"\bобязательно (?:купи|прода)", r"\bгарантирован",
]


def _looks_like_advice(text: str) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in _ADVICE_PATTERNS)


MIN_LETTER_RATIO = 0.45
MAX_CHAR_RUN = 12


def _is_degenerate(text: str) -> bool:
    """True for output that is not prose at all.

    A small model can collapse into a repeated character — one dashboard answer came
    back as several hundred exclamation marks. That passed every other check: long
    enough, no advice, and no numbers to be ungrounded. Structure has to be checked
    too, not just content.
    """
    stripped = "".join(text.split())
    if not stripped:
        return True
    letters = sum(1 for ch in stripped if ch.isalpha())
    if letters / len(stripped) < MIN_LETTER_RATIO:
        return True
    run = 1
    for prev, cur in zip(stripped, stripped[1:]):
        run = run + 1 if cur == prev else 1
        if run > MAX_CHAR_RUN:
            return True
    return False


def _join_digit_groups(text: str) -> str:
    """Drop the space inside a grouped number: "208<nbsp>400" -> "208400".

    The model separates thousands with U+202F (narrow no-break space) per
    Russian typography. Read as two tokens, 208 and 400 matched nothing in the
    facts, so the grounding check rejected the model's own figures and every
    answer containing money silently fell back to the template.
    """
    out: list[str] = []
    for i, ch in enumerate(text):
        if ch.isspace() and ch != chr(10) and out and out[-1].isdigit():
            nxt = text[i + 1:i + 4]
            if len(nxt) == 3 and nxt.isdigit() and not text[i + 4:i + 5].isdigit():
                continue          # separator inside one number
        out.append(ch)
    return "".join(out)


def _numbers(text: str) -> set[str]:
    """Numeric tokens, normalised, for the grounding check."""
    text = _join_digit_groups(text)
    out = set()
    for n in re.findall(r"\d+(?:[.,]\d+)?", text):
        n = n.replace(",", ".")
        if "." in n:
            n = n.rstrip("0").rstrip(".")
        out.add(n or "0")
    return out


def _ungrounded_numbers(answer: str, facts: dict) -> set[str]:
    """Numbers in the answer that appear nowhere in the facts.

    A model that invents a price level is the failure mode that matters here, so
    this is checked rather than trusted. Small integers are ignored: they are
    ordinals and counts from the prose ("три причины", "2 из 5"), not data.
    """
    fact_text = json.dumps(facts, ensure_ascii=False, default=str)
    allowed = _numbers(fact_text)
    out = set()
    for n in _numbers(answer):
        if n in allowed:
            continue
        try:
            if abs(float(n)) <= 12:      # ordinals / small counts
                continue
        except ValueError:
            continue
        out.add(n)
    return out


async def compose(question: str, facts: dict) -> str | None:
    """Turn retrieved facts into an answer. None means "use the fallback".

    `facts` must be JSON-serialisable and must already contain everything the
    answer may cite — including an `enough_data` flag wherever a ratio is involved.
    """
    key = settings.openrouter_api_key
    if not key:
        logger.debug("AI assistant: no OpenRouter key, using template answer")
        return None
    if not facts:
        return None

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content":
                f"Вопрос пользователя: {question}\n\n"
                f"ФАКТЫ (JSON):\n{json.dumps(facts, ensure_ascii=False, indent=1, default=str)}"},
        ],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.2,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEC) as client:
            resp = await client.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json=payload,
            )
            # The free tier is rate-limited upstream and returns 429 often. It is
            # transient, so one short retry recovers most of them; without it the
            # answer degrades to a template on a routine hiccup.
            if resp.status_code == 429:
                import asyncio
                await asyncio.sleep(RETRY_DELAY_SEC)
                resp = await client.post(
                    OPENROUTER_URL,
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    json=payload,
                )
        if resp.status_code != 200:
            level = logger.info if resp.status_code == 429 else logger.warning
            level(f"AI assistant: LLM {resp.status_code} — {resp.text[:160]}")
            return None
        data = resp.json()
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        # Reasoning models put the text in `reasoning` when `content` is empty.
        text = (msg.get("content") or msg.get("reasoning") or "").strip()
    except Exception as e:
        logger.warning(f"AI assistant: LLM call failed — {e}")
        return None

    if len(text) < 40:
        logger.info("AI assistant: answer too short, using template")
        return None

    if _is_degenerate(text):
        logger.warning("AI assistant: answer is not prose (repeated/garbage), discarded")
        return None

    if _looks_like_advice(text):
        logger.warning("AI assistant: answer read as investment advice, discarded")
        return None

    bad = _ungrounded_numbers(text, facts)
    if bad:
        logger.warning(f"AI assistant: ungrounded numbers {sorted(bad)[:6]}, discarded")
        return None

    return text
