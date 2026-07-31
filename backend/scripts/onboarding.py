"""Onboarding series for VIP subscribers — 4 lessons, one per day.

Retention problem this addresses: a new subscriber sees a signal card full of
Kelly / EV / Profit Factor and has no idea how to act on it. These lessons teach
exactly how to use what the channel publishes.

Usage:
  python scripts/onboarding.py list
  python scripts/onboarding.py show 2
  python scripts/onboarding.py send 2            # -> VIP channel
  python scripts/onboarding.py dm <chat_id> 2    # -> one user personally
  python scripts/onboarding.py next              # rotates through the series
"""
import asyncio, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from app.config import settings

P = "https://winextraflow.pages.dev"
DIS = "⚠️ Не является инвестиционной рекомендацией."
STATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "onboarding_state.json")

LESSONS = [
    {
        "key": "day1_read",
        "title": "День 1 — как читать сигнал",
        "text": f"""👋 <b>Добро пожаловать в VIP. Урок 1 из 4</b>

Разберём карточку сигнала по строкам.

<b>Заголовок</b>
🟢 BUY SBER | WEF 71% — направление, инструмент и оценка качества по 9 факторам.

<b>Уровни</b>
📍 Вход — цена, от которой считается сделка
🎯 Цель (TP) — где фиксируем прибыль
🛑 Стоп (SL) — где признаём, что не сработало
⚖️ R:R — во сколько раз потенциал больше риска

<b>Правило одной строки:</b> если R:R ниже 1:1.5 — сделка не стоит риска, мы такие не публикуем.

<b>Вердикт</b>
ОТЛИЧНЫЙ / ХОРОШИЙ — сигнал по тренду
СРЕДНИЙ — боковик, входим меньшим объёмом
РИСКОВАННЫЙ — против тренда, 25% от обычного размера

Завтра: сколько денег ставить на сделку.

🔗 {P}

{DIS}
#обучение #WinExtraFlow""",
    },
    {
        "key": "day2_size",
        "title": "День 2 — размер позиции",
        "text": f"""📏 <b>Урок 2 из 4 — сколько ставить</b>

Самая частая причина потери депозита — не плохие сигналы, а слишком большой объём.

<b>Базовое правило: риск 1–2% депозита на сделку.</b>

Как считать размер:
<code>Объём = (Депозит × Риск%) / |Вход − Стоп|</code>

Пример: депозит 100 000 ₽, риск 1%, вход 300, стоп 285.
Риск на акцию = 15 ₽ → объём = 1000 / 15 ≈ 66 акций.

<b>Kelly в карточке</b> — это математически оптимальная доля от депозита при вашей статистике. Мы показываем половинный Kelly: кривая депозита ровнее, риск разорения ниже.

Если в карточке «Kelly 8%» — это верхняя граница для сильного сигнала, а не рекомендация ставить 8% всегда.

<b>При вердикте РИСКОВАННЫЙ делите размер на 4.</b>

Завтра: что делать после входа.

🔗 {P}

{DIS}
#обучение #WinExtraFlow""",
    },
    {
        "key": "day3_manage",
        "title": "День 3 — ведение сделки",
        "text": f"""🎯 <b>Урок 3 из 4 — что делать после входа</b>

<b>1. Вход частями (пирамидинг)</b>
Если в карточке «Пирамидинг: 3 уровня»:
• 50% объёма — сразу по рынку
• 30% — когда цена прошла треть пути к цели
• 20% — на две трети пути

Так средняя цена лучше, а если сигнал не пошёл — потеряна только первая часть.

<b>2. Стоп в безубыток</b>
Прошли 40% пути до цели — переносим стоп на цену входа. Дальше сделка не может стать убыточной.

<b>3. Не двигайте стоп против себя</b>
Расширить стоп «чтобы не выбило» — самый дорогой рефлекс в трейдинге. Стоп двигается только в сторону прибыли.

<b>4. Мы сообщаем результат</b>
Когда цена доходит до цели или стопа — в канал приходит пост с фактическим результатом.

Завтра: как проверить нас.

🔗 {P}

{DIS}
#обучение #WinExtraFlow""",
    },
    {
        "key": "day4_verify",
        "title": "День 4 — как нас проверять",
        "text": f"""🔍 <b>Урок 4 из 4 — доверяй, но проверяй</b>

Мы не просим верить на слово.

<b>Публичный журнал сделок</b>
{P}/track-record — все закрытые сигналы построчно: инструмент, вход, WEF, исход, результат.

<b>Что мы делаем принципиально:</b>
• Результат считаем по уровню закрытия (TP/SL), а не по текущей цене
• Демо-данные в статистику не включаем
• Агрегированную доходность не публикуем, пока сделок мало — на малой выборке проценты не значат ничего
• Раз в неделю показываем, сколько сигналов <b>отклонили</b> и почему

<b>Как читать любого поставщика сигналов:</b>
Просите полный журнал сделок. Если показывают только «win rate 95%» без списка сделок и без средних убытков — цифра ничего не стоит.

Спасибо, что с нами. Вопросы — просто напишите в ответ.

🔗 {P}

{DIS}
#обучение #WinExtraFlow""",
    },
]


def _state() -> dict:
    if os.path.exists(STATE):
        try:
            with open(STATE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"sent": []}


def _save(st: dict):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


async def _send(chat_id: str, text: str) -> bool:
    token = settings.telegram_bot_token
    if not token or not chat_id:
        print("(bot/chat not configured)"); return False
    body = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                       "disable_notification": True,
                       "disable_web_page_preview": True}).encode("utf-8")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         content=body, headers={"Content-Type": "application/json; charset=utf-8"})
    ok = r.json().get("ok", False)
    print("  sent" if ok else f"  failed: {r.text[:160]}")
    return ok


async def main():
    a = sys.argv[1:]
    cmd = a[0] if a else "list"

    if cmd == "list":
        st = _state()
        print(f"Onboarding series — {len(LESSONS)} lessons (sent: {len(st['sent'])})\n")
        for i, l in enumerate(LESSONS, 1):
            print(f"  [{'✔' if l['key'] in st['sent'] else ' '}] {i}. {l['title']}")
        return

    if cmd == "show" and len(a) > 1:
        print(LESSONS[int(a[1]) - 1]["text"]); return

    if cmd == "send" and len(a) > 1:
        l = LESSONS[int(a[1]) - 1]
        print(f"Sending: {l['title']}")
        await _send(settings.telegram_vip_channel_id, l["text"])
        st = _state()
        if l["key"] not in st["sent"]:
            st["sent"].append(l["key"]); _save(st)
        return

    if cmd == "dm" and len(a) > 2:
        l = LESSONS[int(a[2]) - 1]
        print(f"DM {a[1]}: {l['title']}")
        await _send(a[1], l["text"])
        return

    if cmd == "next":
        st = _state()
        nxt = next((l for l in LESSONS if l["key"] not in st["sent"]), None)
        if not nxt:
            print("Series complete — nothing to send (reset onboarding_state.json to repeat)")
            return
        print(f"Sending: {nxt['title']}")
        await _send(settings.telegram_vip_channel_id, nxt["text"])
        st["sent"].append(nxt["key"]); _save(st)
        return

    print(__doc__)


asyncio.run(main())
