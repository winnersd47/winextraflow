"""Feature-post library — content that explains the platform's real tools.

Each post describes a capability that actually exists in the project (verified
against the code): WEF Score, quality gate, backtesting, regime engine, Kelly
sizing, screener, heatmap, AI chat, portfolio/journal, alerts, multi-market
coverage, evolutionary architecture, channel parsing, MT5 bridge, copy trading,
payments, referrals.

No performance promises — only tooling descriptions.

Usage:
  python scripts/feature_posts.py list             # show all posts
  python scripts/feature_posts.py show 3           # preview one
  python scripts/feature_posts.py send 3           # -> free channel
  python scripts/feature_posts.py send 3 --vip     # -> VIP too
  python scripts/feature_posts.py next             # send next unposted (rotates)
"""
import asyncio, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from app.config import settings

P = "https://winextraflow.pages.dev"
DIS = "⚠️ Не является инвестиционной рекомендацией."
STATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "feature_post_state.json")

POSTS: list[dict] = [
    {
        "key": "wef_score",
        "title": "WEF Score — как мы оцениваем сигнал",
        "text": f"""📊 <b>WEF Score: девять факторов вместо интуиции</b>

Каждый сигнал получает одну цифру от 0 до 100. За ней — девять проверок:

1️⃣ Риск-менеджмент — есть ли стоп
2️⃣ Risk/Reward — оправдан ли риск
3️⃣ История провайдера — что он давал раньше
4️⃣ Sharpe Ratio — доходность на единицу риска
5️⃣ Profit Factor — прибыль против убытков
6️⃣ Максимальная просадка
7️⃣ Time Decay — не устарел ли сигнал
8️⃣ Частота сигналов — не спам ли это
9️⃣ Полнота — есть ли вход, цель и стоп

Одна цифра вместо чтения семи каналов.

💎 Сигналы с WEF 70%+ публикуются только в VIP.

🔗 {P}

{DIS}
#winextraflow #WEFScore""",
    },
    {
        "key": "quality_gate",
        "title": "Фильтр качества — 7 проверок",
        "text": f"""🛡 <b>Что происходит с сигналом до публикации</b>

Сигнал не попадает в канал, пока не пройдёт семь проверок:

✅ Есть цель (TP)
✅ Есть стоп (SL)
✅ R:R не ниже 1:1.5
✅ WEF Score не ниже 50%
✅ Провайдер с адекватной историей
✅ Нет дубля по этому тикеру
✅ Цена входа актуальна рынку

Не прошёл — не публикуем. Даже если тикер популярный.

Раз в неделю показываем, сколько сигналов отклонили и почему.

🔗 {P}

{DIS}
#winextraflow #качество""",
    },
    {
        "key": "backtest",
        "title": "Бэктест на реальных свечах",
        "text": f"""🔬 <b>Бэктест на реальных данных, а не на картинках</b>

Любую стратегию можно прогнать на настоящих исторических свечах:

📈 Данные: MOEX ISS, Binance, Yahoo Finance
🕯 Проход бар за баром — как срабатывали TP и SL
🎲 Монте-Карло: 1000 перестановок сделок
📊 Сравнение с Buy &amp; Hold — обогнали рынок или нет
💸 С учётом комиссии и размера позиции
🗓 Разбивка по месяцам

Стратегия без бэктеста — это гипотеза, а не стратегия.

🔗 {P}

{DIS}
#winextraflow #бэктест""",
    },
    {
        "key": "regime",
        "title": "Режимы рынка и выбор стратегии",
        "text": f"""🧭 <b>Одна стратегия не работает всегда</b>

Платформа определяет режим рынка и подбирает подход под него:

↗️ Тренд + низкая волатильность → Dual Momentum, полный размер
↗️ Тренд + высокая волатильность → пробой с трейлингом, размер 50%
↔️ Боковик + низкая волатильность → парный арбитраж
↔️ Боковик + высокая волатильность → сократить позиции
↘️ Даунтренд → осторожно с покупками, отскок отдельной стратегией

12 сочетаний режима и волатильности — под каждое свой размер позиции и множитель стопа.

🔗 {P}

{DIS}
#winextraflow #режимрынка""",
    },
    {
        "key": "kelly",
        "title": "Kelly — сколько ставить на сделку",
        "text": f"""🎲 <b>Сколько ставить: 2% или 10%?</b>

Формула Келли считает оптимальный размер позиции из вашей статистики:

Kelly = WR − (1 − WR) / R

Где WR — доля прибыльных, R — отношение среднего профита к среднему убытку.

На практике берут <b>половину Келли</b> — кривая депозита ровнее, риск разорения ниже.

В каждом сигнале мы показываем: полный Келли, половинный и итоговый размер с поправкой на режим рынка.

Слишком большая позиция убивает депозит даже на прибыльной стратегии.

🔗 {P}

{DIS}
#winextraflow #рискменеджмент""",
    },
    {
        "key": "ev_math",
        "title": "Почему R:R важнее винрейта",
        "text": f"""🧮 <b>90% прибыльных сделок — и минус на счёте</b>

Такое бывает. Считаем математическое ожидание:

EV = (WR × средний профит) − (LR × средний убыток)

Пример A: WR 60%, профит +3%, убыток −2%
EV = 1.8 − 0.8 = <b>+1.0%</b> ✅

Пример B: WR 70%, профит +1%, убыток −3%
EV = 0.7 − 0.9 = <b>−0.2%</b> ❌

Во втором случае вы правы чаще — и всё равно в минусе.

Поэтому мы не публикуем сигналы с R:R ниже 1:1.5.

🔗 {P}

{DIS}
#winextraflow #математика""",
    },
    {
        "key": "screener",
        "title": "Скринер по рынкам",
        "text": f"""🔎 <b>Скринер: найти идею до того, как она станет очевидной</b>

Сканирует рынки по техническим условиям:

• Перепроданность и перекупленность (RSI)
• Отклонение от средней (Z-score)
• Пробои уровней
• Аномальный объём
• Положение относительно SMA

Рынки: MOEX, криптовалюта, форекс, акции США.

Не «топ-10 монет», а конкретные условия, которые вы задаёте.

🔗 {P}

{DIS}
#winextraflow #скринер""",
    },
    {
        "key": "heatmap",
        "title": "Тепловая карта MOEX",
        "text": f"""🗺 <b>Весь рынок на одном экране</b>

Тепловая карта показывает, что происходит с MOEX прямо сейчас:

🟩 Зелёные — растут
🟥 Красные — падают
📦 Размер блока — капитализация
🏭 Группировка по секторам: нефтегаз, банки, металлурги, ритейл, IT

Видно сразу: падает весь рынок или только ваша бумага. Это разные ситуации и разные решения.

🔗 {P}

{DIS}
#winextraflow #MOEX""",
    },
    {
        "key": "ai_chat",
        "title": "AI-чат по тикеру",
        "text": f"""🤖 <b>Спросить про тикер — как у аналитика</b>

Встроенный AI-чат отвечает по данным платформы:

• «Что по SBER?» — режим, сигналы, WEF
• «Стоит ли брать BTC сейчас?» — контекст рынка
• «Что такое Profit Factor?» — объяснит без воды

Отвечает не выдумками, а тем, что реально есть в базе: сигналы, рейтинги, режим рынка, статистика провайдеров.

🔗 {P}

{DIS}
#winextraflow #AI""",
    },
    {
        "key": "portfolio",
        "title": "Портфель и журнал сделок",
        "text": f"""📁 <b>Портфель и журнал: где утекает прибыль</b>

<b>Портфель:</b>
• Позиции и распределение по активам
• Кривая капитала
• P&amp;L по месяцам

<b>Журнал сделок:</b>
• Каждая сделка с причиной входа
• Win Rate, средний профит и убыток
• Статистика по тикерам и стратегиям

Большинство теряет не на плохих сигналах, а потому что не ведёт учёт и повторяет одну ошибку.

🔗 {P}

{DIS}
#winextraflow #портфель""",
    },
    {
        "key": "alerts",
        "title": "Оповещения по ценам",
        "text": f"""🔔 <b>Не сидеть в терминале весь день</b>

Оповещения срабатывают, когда цена дошла до вашего уровня:

• Выше / ниже заданной цены
• Изменение на % за период
• Уведомление в Telegram

Плюс автоматический контроль открытых сигналов: платформа сама следит, дошла ли цена до цели или до стопа, и сообщает результат.

🔗 {P}

{DIS}
#winextraflow #оповещения""",
    },
    {
        "key": "markets",
        "title": "Пять рынков в одном месте",
        "text": f"""🌍 <b>Пять рынков — один интерфейс</b>

🇷🇺 <b>Акции MOEX</b> — Сбер, Газпром, Лукойл и другие
🇺🇸 <b>Акции США</b> — NVDA, AAPL, COIN
₿ <b>Криптовалюта</b> — BTC, ETH, альткоины
💱 <b>Форекс</b> — EUR/USD, GBP/USD, USD/RUB
🛢 <b>Фьючерсы MOEX</b> — нефть Brent, золото, индексы

Цены берутся из первоисточников: MOEX ISS, Binance, Yahoo Finance, CoinGecko.

Один WEF Score работает на всех рынках одинаково.

🔗 {P}

{DIS}
#winextraflow #рынки""",
    },
    {
        "key": "evolution",
        "title": "Эволюционная архитектура",
        "text": f"""🧬 <b>Система, которая дописывает себя</b>

Внутри платформы — 228 аналитических компонентов, собранных из 108 источников: научные статьи, исследования по квант-трейдингу, публикации MQL5.

Как это работает:
• Читаем новые исследования
• Извлекаем работающие идеи
• Добавляем как компонент к одной из 7 ветвей стратегий
• Компонент проходит путь: planned → emerging → active

Рынок меняется — набор инструментов меняется вместе с ним.

🔗 {P}

{DIS}
#winextraflow #эволюция""",
    },
    {
        "key": "parsing",
        "title": "Как мы собираем сигналы",
        "text": f"""📡 <b>13 каналов под наблюдением</b>

Платформа читает Telegram-каналы и вытаскивает сигналы автоматически:

• Распознаёт форматы: русские рекомендации, крипто-диапазоны, фьючерсы MOEX
• Отбрасывает рекламу, «итоги месяца» и разговоры
• Проверяет актуальность цены — старый пост из истории не станет сигналом
• Прогоняет через WEF Score и фильтр качества

Плюс поиск новых источников по пяти рынкам: система сама находит каналы и оценивает, годятся ли их сигналы.

🔗 {P}

{DIS}
#winextraflow #автоматизация""",
    },
    {
        "key": "mt5",
        "title": "Мост в MetaTrader 5",
        "text": f"""🔌 <b>MetaTrader 5 + AI</b>

Терминал считает индикаторы и отдаёт данные, AI принимает решение:

MT5 → локальный сервер → модель → решение → обратно в MT5

Что внутри:
• Индикаторы на NumPy: SMA, EMA, MACD, RSI, ATR, Боллинджер
• Пакетная обработка 8–10 инструментов
• Расчёт размера позиции по риску
• Режим «только алерты» или автоторговля

API-ключи остаются на сервере — в коде советника их нет.

🔗 {P}

{DIS}
#winextraflow #MT5""",
    },
    {
        "key": "payments",
        "title": "Оплата и тарифы",
        "text": f"""💳 <b>Оплата так, как удобно</b>

🇷🇺 <b>Карты РФ и СБП</b> — ЮKassa
₿ <b>Криптовалюта</b> — USDT, BTC
🌍 <b>Visa / Mastercard</b> — для оплаты из-за рубежа

Три тарифа: Free, Pro, Premium. Годовая подписка выгоднее месячной.

Реферальная программа: приводите друга — бонусные дни Premium получаете оба.

Возврат в течение 14 дней по политике возврата.

🔗 {P}

{DIS}
#winextraflow #тарифы""",
    },
]


def _state() -> dict:
    if os.path.exists(STATE):
        try:
            with open(STATE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"posted": []}


def _save(st: dict):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


async def _send(chat_id: str, text: str) -> bool:
    token = settings.telegram_bot_token
    if not token or not chat_id:
        print("(bot not configured)"); return False
    body = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
            "disable_notification": True, "disable_web_page_preview": True}
    data = json.dumps(body).encode("utf-8")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         content=data, headers={"Content-Type": "application/json; charset=utf-8"})
    ok = r.json().get("ok", False)
    print("  sent" if ok else f"  failed: {r.text[:160]}")
    return ok


async def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "list"

    if cmd == "list":
        st = _state()
        print(f"{len(POSTS)} feature posts (posted: {len(st['posted'])})\n")
        for i, p in enumerate(POSTS, 1):
            mark = "✔" if p["key"] in st["posted"] else " "
            print(f"  [{mark}] {i:2}. {p['title']}")
        return

    if cmd == "show" and len(args) > 1:
        print(POSTS[int(args[1]) - 1]["text"]); return

    if cmd == "send" and len(args) > 1:
        p = POSTS[int(args[1]) - 1]
        print(f"Sending: {p['title']}")
        await _send(settings.telegram_free_channel_id, p["text"])
        if "--vip" in args:
            await asyncio.sleep(1)
            await _send(settings.telegram_vip_channel_id, p["text"])
        st = _state()
        if p["key"] not in st["posted"]:
            st["posted"].append(p["key"]); _save(st)
        return

    if cmd == "next":
        st = _state()
        nxt = next((p for p in POSTS if p["key"] not in st["posted"]), None)
        if not nxt:  # all posted -> start over
            st["posted"] = []; nxt = POSTS[0]
        print(f"Sending: {nxt['title']}")
        await _send(settings.telegram_free_channel_id, nxt["text"])
        st["posted"].append(nxt["key"]); _save(st)
        return

    print(__doc__)


asyncio.run(main())
