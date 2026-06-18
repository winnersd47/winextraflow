"""Content Scheduler — automated posting to Telegram channels.

Manages two channels:
- @WinExtraFlowSignals — signals, analytics, market data
- AI Growth Club — marketing posts, education, community

Schedule: Wave 1 = 28 days, 8 posts + automated signals.
"""

import logging
from datetime import datetime, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ScheduledPost:
    day: int  # day of the wave (1-28)
    channel: str  # "signals" or "growth"
    type: str  # manifesto, education, poll, pain, demo, data, offer
    title: str
    text: str


# ═══ WAVE 1 CONTENT PLAN (28 days) ═══

WAVE1_POSTS: list[ScheduledPost] = [
    # Day 1 — Manifesto (both channels)
    ScheduledPost(
        day=1, channel="both", type="manifesto", title="Манифест",
        text="""Мы посчитали.

Средний трейдер проверяет 5-7 Telegram каналов,
3 сайта с аналитикой и 2 биржи каждое утро.

Это 40+ минут — до того как он откроет первую сделку.

А потом — ещё час на анализ:
"Этот сигнал хороший? А провайдер надёжный?
Стоит ли входить при текущем рынке?"

Мы создали WinExtraFlow — AI-платформу
для торговых сигналов, которая делает это за тебя.

Не очередной канал с сигналами.
Не ещё один скринер.

Единая система с AI-оценкой каждого сигнала.
150+ компонентов анализируют 9 факторов
и выдают один WEF Score: от 0 до 100.

Покупать или нет — решаешь ты.
Но теперь у тебя есть данные, а не интуиция.

Здесь будем делиться:
— реальные сигналы с AI-оценкой
— аналитика MOEX и крипто
— кейсы и обзоры стратегий
— обновления платформы

Подпишись. Первый сигнал — уже послезавтра.

Напиши в комментарии: чем торгуешь?
MOEX, крипто или forex?

→ winextraflow.com""",
    ),

    # Day 3 — WEF Score education (signals channel)
    ScheduledPost(
        day=3, channel="signals", type="education", title="WEF Score",
        text="""Ты получил сигнал: BUY BTCUSDT.

Что обычно делаешь?
Смотришь график. Проверяешь RSI. Читаешь чат.
Спрашиваешь "ну как, входим?"
И через 15 минут входишь на эмоции.

Вот что делает WinExtraFlow за 2 секунды:

✓ Проверяет провайдера: win rate 72%, Sharpe 1.8
✓ Считает Risk/Reward: 1:2.3
✓ Определяет режим рынка: восходящий тренд
✓ Проверяет частоту сигналов (спам-фильтр)
✓ Выдаёт TP1/TP2/TP3 + SL + размер позиции

Результат: WEF Score 87%
Значит: сильный сигнал. Входить можно.

Если WEF Score 34% — ты бы не увидел этот сигнал
в топе ленты. Слабые отсеиваются автоматически.

На платформе 1 284 сигнала
от 20 провайдеров прошли через этот фильтр.

Попробовать бесплатно →
winextraflow.com

Промокод AIGROWTH14 — 14 дней Premium.""",
    ),

    # Day 5 — Poll (growth channel)
    ScheduledPost(
        day=5, channel="growth", type="poll", title="Опрос",
        text="""Быстрый вопрос:

Как ты сейчас оцениваешь сигналы
перед входом в сделку?

📊 Смотрю график и RSI/MACD
💬 Доверяю каналу/провайдеру
🤖 Использую AI/бота
🎲 На ощущениях

Результаты — через 2 дня.
И покажем как 150+ AI-компонентов делают это за тебя.""",
    ),

    # Day 7 — MOEX investor pain (signals channel)
    ScheduledPost(
        day=7, channel="signals", type="pain", title="Утро инвестора",
        text="""Типичное утро инвестора MOEX:

09:00 — открываешь терминал, смотришь IMOEX
09:15 — проверяешь Сбер, Газпром, Лукойл
09:30 — открываешь 3 Telegram канала с сигналами
10:00 — читаешь РБК и Ведомости
10:20 — пытаешься понять: рынок растёт или падает?
10:40 — решаешь "подожду до обеда"
14:00 — обед. Рынок уже ушёл.

Знакомо?

В WinExtraFlow ты видишь одну страницу:

— Режим рынка MOEX: тренд вверх (уверенность 78%)
— 27 тикеров live: SBER, GAZP, LKOH и ещё 24
— 7 индексов: IMOEX, RTSI, MOEXBC...
— AI-оценка каждого сигнала: WEF Score
— Тепловая карта по секторам

Открыл → увидел → решил. 5 минут вместо 2 часов.

Сколько каналов с сигналами ты сейчас читаешь? Напиши число.""",
    ),

    # Day 9 — Copy trading (growth channel)
    ScheduledPost(
        day=9, channel="growth", type="education", title="Копитрейдинг",
        text=""""Я не умею торговать.
Но хочу зарабатывать на рынке."

Знакомо? Тогда копитрейдинг — для тебя.

Как это работает:

1. На WinExtraFlow есть провайдеры —
   опытные трейдеры с проверенной историей.

2. Ты выбираешь лучшего по WEF Score:
   win rate, Sharpe Ratio, средняя прибыль.

3. Подключаешь свою биржу (Binance, Bybit, OKX,
   MT5, Tinkoff — всего 9 бирж).

4. Когда провайдер делает сделку —
   система автоматически копирует её на твой счёт.

77 стратегий на маркетплейсе.
50 MT5 советников. 16 стратегий TradingView.

Начать бесплатно → winextraflow.com""",
    ),

    # Day 12 — Data/results (both)
    ScheduledPost(
        day=12, channel="both", type="data", title="9 факторов",
        text="""Вот сколько факторов проверяет WEF Score:

1. Risk Management — есть ли TP/SL?
2. Risk/Reward Ratio — стоит ли игра свеч?
3. Provider History — win rate провайдера
4. Signal Frequency — не спам ли это?
5. Sharpe Ratio — доход с поправкой на риск
6. Profit Factor — прибыль / убытки
7. Max Drawdown — максимальная просадка
8. Time Decay — свежесть данных провайдера
9. Signal Completeness — полнота информации

9 факторов. 200 AI-компонентов. 99 источников.
Автоматически. За 2 секунды.

Проверить на своих сигналах →
winextraflow.com

Промокод AIGROWTH14 — 14 дней бесплатно.

⚠️ Не является инвестиционной рекомендацией.""",
    ),

    # Day 14 — Demo morning (signals)
    ScheduledPost(
        day=14, channel="signals", type="demo", title="Утро трейдера",
        text="""Утро трейдера с WinExtraFlow:

07:00. Открываешь приложение.
Вместо 7 каналов — один экран.

// ЛЕНТА СИГНАЛОВ
🟢 BUY SBER 312.50 | WEF 87% | TP 340 SL 298
🟢 BUY BTCUSDT 67,200 | WEF 74% | TP 71,000 SL 65,500
🔴 SELL EURUSD 1.0892 | WEF 62% | TP 1.0810 SL 1.0935

// РЕЖИМ РЫНКА
MOEX: Восходящий тренд (78%)
Crypto: Боковик (64%)

// AI АССИСТЕНТ
"Стоит ли покупать SBER?"
→ "14 сигналов за 30 дней. 10 BUY, 4 SELL.
   WEF Score средний: 81%. Win Rate: 72%.
   Уклон: сильный бычий."

Три решения приняты до первого кофе.
Ни одного канала не открывал.

Попробовать бесплатно → winextraflow.com""",
    ),

    # Day 28 — Final offer (both)
    ScheduledPost(
        day=28, channel="both", type="offer", title="Финальный оффер",
        text="""Месяц назад мы открыли канал.

За это время:
— 1 284 сигнала прошли AI-оценку
— 77 стратегий на маркетплейсе
— 200 AI-компонентов из 99 источников
— 27 тикеров MOEX в реальном времени
— 9 бирж подключено

Сегодня последний день промокода AIGROWTH14.
14 дней Premium бесплатно. Без ограничений.

Все сигналы. AI-ассистент. Скринер.
Копитрейдинг. Торговый журнал. Портфель.

После — от 1 490 ₽/мес ($16 Pro) или 2 990 ₽/мес ($33 Premium).
Сейчас — бесплатно.

→ winextraflow.com

Оплата: карты РФ (СБП 0.7%) / Visa-MC в USD/EUR / крипто (USDT 0.4%)

⚠️ Не является инвестиционной рекомендацией.""",
    ),
]


def get_post_for_day(day: int) -> list[ScheduledPost]:
    """Get posts scheduled for a specific day of the wave."""
    return [p for p in WAVE1_POSTS if p.day == day]


def get_full_schedule() -> list[dict]:
    """Get the complete wave 1 schedule."""
    return [
        {
            "day": p.day,
            "channel": p.channel,
            "type": p.type,
            "title": p.title,
            "text_preview": p.text[:100] + "...",
            "text_length": len(p.text),
        }
        for p in WAVE1_POSTS
    ]
