"""WinExtraFlow Telegram Bot — content publishing + user onboarding funnel.

Features:
1. User funnel: /start → experience → stats → CTA → follow-ups
2. /publish {day} — publish Wave 1 post for a specific day
3. /schedule — view full content plan
4. /custom {text} — publish custom message
5. Auto-forward: messages with #repost or #aigc from channels → AI Growth Club
6. /market — quick market pulse (Fear & Greed + BTC price)

Usage:
    python bot.py

Requires: BOT_TOKEN, CHANNEL_SIGNALS_ID, CHANNEL_VIP_ID, GROUP_AIGC_ID in .env
Bot must be admin in all channels/groups.
"""

import os
import logging
from dotenv import load_dotenv
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler,
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_SIGNALS_ID = int(os.getenv("CHANNEL_SIGNALS_ID", "0"))
CHANNEL_VIP_ID = int(os.getenv("CHANNEL_VIP_ID", "0"))
GROUP_AIGC_ID = int(os.getenv("GROUP_AIGC_ID", "0"))
FORWARD_TAGS = [t.strip() for t in os.getenv("FORWARD_TAGS", "#repost,#aigc").split(",")]
CHANNEL_SIGNALS_LINK = os.getenv("CHANNEL_SIGNALS_LINK", "https://t.me/winextraflow")
PROMO_CODE = os.getenv("PROMO_CODE", "AIGROWTH14")
SITE_URL = os.getenv("SITE_URL", "https://winextraflow-agc.vercel.app")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# ═══ FUNNEL STATES ═══
EXPERIENCE, SHOW_STATS = range(2)

# ═══ WAVE 1 CONTENT (8 posts, 28 days) ═══

WAVE1 = {
    1: {
        "title": "Манифест",
        "channel": "both",
        "text": """Мы посчитали.

Средний трейдер проверяет 5-7 Telegram каналов,
3 сайта с аналитикой и 2 биржи каждое утро.

Это 40+ минут — до того как он откроет первую сделку.

Мы создали WinExtraFlow — AI-платформу
для торговых сигналов, которая делает это за тебя.

150+ AI-компонентов анализируют 9 факторов
и выдают один WEF Score: от 0 до 100.

Покупать или нет — решаешь ты.
Но теперь у тебя есть данные, а не интуиция.

Подпишись. Первый сигнал — уже послезавтра.

Чем торгуешь? MOEX, крипто или forex?

→ winextraflow.com

#repost #aigc #winextraflow""",
    },
    3: {
        "title": "WEF Score",
        "channel": "signals",
        "text": """Ты получил сигнал: BUY BTCUSDT.

Что обычно делаешь?
Смотришь график. Проверяешь RSI. Читаешь чат.
И через 15 минут входишь на эмоции.

Вот что делает WinExtraFlow за 2 секунды:

✓ Проверяет провайдера: win rate 72%, Sharpe 1.8
✓ Считает Risk/Reward: 1:2.3
✓ Определяет режим рынка: восходящий тренд
✓ Выдаёт TP1/TP2/TP3 + SL + размер позиции

Результат: WEF Score 87%

Попробовать бесплатно → winextraflow.com
Промокод AIGROWTH14 — 14 дней Premium.

#repost #aigc #winextraflow""",
    },
    5: {
        "title": "Опрос",
        "channel": "growth",
        "text": """Быстрый вопрос:

Как ты сейчас оцениваешь сигналы перед входом в сделку?

📊 Смотрю график и RSI/MACD
💬 Доверяю каналу/провайдеру
🤖 Использую AI/бота
🎲 На ощущениях

Результаты — через 2 дня.

#repost #aigc""",
    },
    7: {
        "title": "Утро инвестора MOEX",
        "channel": "signals",
        "text": """Типичное утро инвестора MOEX:

09:00 — открываешь терминал
09:30 — проверяешь 3 Telegram канала
10:20 — пытаешься понять: рынок растёт или падает?
10:40 — решаешь "подожду до обеда"
14:00 — рынок уже ушёл.

В WinExtraFlow ты видишь одну страницу:
— Режим рынка MOEX + 27 тикеров live
— AI-оценка каждого сигнала
— Тепловая карта по секторам

5 минут вместо 2 часов.

→ winextraflow.com

#repost #aigc #winextraflow""",
    },
    9: {
        "title": "Копитрейдинг",
        "channel": "growth",
        "text": """"Я не умею торговать. Но хочу зарабатывать на рынке."

Копитрейдинг — для тебя:

1. Выбери провайдера по WEF Score
2. Подключи биржу (9 бирж: Binance, Bybit, Tinkoff...)
3. Система копирует сделки автоматически

77 стратегий. 50 MT5 советников. 16 TradingView стратегий.

Начать бесплатно → winextraflow.com

#repost #aigc #winextraflow""",
    },
    12: {
        "title": "9 факторов WEF Score",
        "channel": "both",
        "text": """WEF Score проверяет 9 факторов:

1. Risk Management — есть ли TP/SL?
2. Risk/Reward Ratio
3. Provider History — win rate
4. Signal Frequency — спам-фильтр
5. Sharpe Ratio
6. Profit Factor
7. Max Drawdown
8. Time Decay
9. Signal Completeness

200 AI-компонентов. 99 источников. За 2 секунды.

Промокод AIGROWTH14 — 14 дней бесплатно.
→ winextraflow.com

⚠️ Не является инвестиционной рекомендацией.

#repost #aigc #winextraflow""",
    },
    14: {
        "title": "Утро трейдера",
        "channel": "signals",
        "text": """Утро трейдера с WinExtraFlow:

🟢 BUY SBER 312.50 | WEF 87% | TP 340 SL 298
🟢 BUY BTCUSDT 67,200 | WEF 74%
🔴 SELL EURUSD 1.0892 | WEF 62%

MOEX: Восходящий тренд (78%)
Crypto: Боковик (64%)

AI: "14 сигналов по SBER за 30 дней. Win Rate: 72%. Уклон: сильный бычий."

Попробовать → winextraflow.com

#repost #aigc #winextraflow""",
    },
    28: {
        "title": "Финальный оффер",
        "channel": "both",
        "text": """За месяц:
— 1 284 сигнала с AI-оценкой
— 77 стратегий на маркетплейсе
— 200 AI-компонентов из 99 источников

Последний день промокода AIGROWTH14.
14 дней Premium бесплатно.

От 1 490 ₽/мес ($16 Pro) или 2 990 ₽/мес ($33 Premium).
Сейчас — бесплатно.

→ winextraflow.com

Оплата: карты РФ (СБП 0.7%) / Visa-MC / крипто (USDT 0.4%)

⚠️ Не является инвестиционной рекомендацией.

#repost #aigc #winextraflow""",
    },
}


# ═══ USER FUNNEL ═══

async def funnel_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: greet user and ask about trading experience."""
    name = update.effective_user.first_name or "трейдер"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Уже торгую", callback_data="exp_active")],
        [InlineKeyboardButton("🔰 Хочу начать", callback_data="exp_newbie")],
        [InlineKeyboardButton("🔍 Ищу хорошие сигналы", callback_data="exp_signals")],
    ])
    await update.message.reply_text(
        f"👋 {name}, привет!\n\n"
        f"WinExtraFlow — AI-платформа торговых сигналов.\n"
        f"200+ AI-компонентов, 99 источников, один WEF Score.\n\n"
        f"Скажи, чтобы я показал самое нужное 👇",
        reply_markup=keyboard,
    )
    return EXPERIENCE


async def _platform_stats() -> dict:
    """Live numbers from the platform's own track record.

    Read at call time, never written into the text. Hardcoded figures are how
    this block came to claim "274 сигнала, 94.8% в плюс" while the database held
    28 closed trades and 10 wins — a number that was wrong the day it was typed
    and got wronger every day after.

    `/track-record/summary` already answers honestly: below MIN_SAMPLE closed
    trades it returns `enough_data: false` and the sentence explaining why,
    which is the same rule the website and the signal cards follow.
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(f"{API_URL}/api/v1/track-record/summary")
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        logger.warning(f"track-record unavailable: {e}")
    return {}


def _stats_lines(d: dict) -> str:
    """Format the record for a reader, including when there is not enough of it.

    Saying "we do not publish a win rate yet, and here is the threshold" is a
    stronger claim than any percentage: it tells the reader what the number
    would have to survive before it is shown to them.
    """
    if not d:
        return ("📊 Статистика сейчас недоступна — "
                "сервер не отвечает. Полный журнал: /track-record")

    closed = d.get("closed_trades", 0)
    if not d.get("enough_data"):
        return (
            f"📊 Закрытых сделок: {closed}\n\n"
            f"Доходность не публикуем, пока их меньше "
            f"{d.get('min_sample', 30)} — на меньшей выборке это шум, "
            f"а не результат.\n\n"
            f"Каналы, обещающие «97% в плюс», этого порога не ставят. "
            f"Мы ставим и ждём."
        )

    wr = d.get("win_rate_pct")
    avg = d.get("avg_result_pct")
    pf = d.get("profit_factor")
    out = [f"📊 Закрытых сделок: {closed}"]
    if wr is not None:
        out.append(f"Win rate: {wr}%")
    if avg is not None:
        out.append(f"Средний результат: {avg:+.2f}% на сделку")
    if pf is not None:
        out.append(f"Profit factor: {pf}")
    out.append("\nВключая убыточные. Журнал открыт: /track-record")
    return "\n".join(out)


async def funnel_experience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle experience selection and show relevant stats."""
    query = update.callback_query
    await query.answer()
    exp = query.data

    if exp == "exp_active":
        text = (
            "🔥 Отлично — ты уже в теме.\n\n"
            "Проблема опытных трейдеров: 5-7 Telegram-каналов утром,\n"
            "3 сайта, 2 биржи — 40+ минут до первой сделки.\n\n"
            "📊 WEF Score делает это за 2 секунды:\n"
            "✅ Win rate провайдера — когда он измерен\n"
            "✅ Risk/Reward и безубыточная доля\n"
            "✅ Режим рынка\n"
            "✅ TP/SL + размер позиции от риска\n\n"
            + _stats_lines(await _platform_stats())
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🚀 Попробовать бесплатно ({PROMO_CODE})", url=SITE_URL)],
            [InlineKeyboardButton("📊 Подписаться на сигналы", url=CHANNEL_SIGNALS_LINK)],
        ])

    elif exp == "exp_newbie":
        text = (
            # "95% новичков теряют депозит" is a figure with no source that
            # every signal-selling funnel repeats, including the two audited
            # for this project. Removed rather than re-sourced: the honest
            # version of this screen is what the platform refuses to publish,
            # not a scarier statistic.
            "👍 Начать лучше с того, что можно проверить.\n\n"
            "Что делает платформа:\n"
            "1️⃣ Считает WEF Score по 9 факторам и показывает, "
            "сколько из них реально измерено\n"
            "2️⃣ Отклоняет сетапы, которым нужно больше 70% побед "
            "просто чтобы не терять\n"
            "3️⃣ Публикует результат каждой сделки — и прибыльной, "
            "и убыточной — ответом на сам сигнал\n\n"
            + _stats_lines(await _platform_stats()) + "\n\n"
            "Симулятор бесплатный: торговля на реальных котировках "
            "без денег."
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🎯 Начать бесплатно ({PROMO_CODE})", url=SITE_URL)],
            [InlineKeyboardButton("📊 Смотреть канал", url=CHANNEL_SIGNALS_LINK)],
        ])

    else:  # exp_signals
        text = (
            # The daily ✅/❌ table this replaced was copied, format and all,
            # from a binary-options funnel. Its arithmetic: at an 80% payout,
            # 274 signals at 94.8% compounds a deposit by ~9x per week and
            # 10^50 per year — more than all the money in the world. A claim
            # that cannot be true is not stronger marketing, it is the thing
            # this platform exists to filter out.
            "📊 Честная статистика — это та, которую можно проверить.\n\n"
            + _stats_lines(await _platform_stats()) + "\n\n"
            "Каждый сигнал — с входом, целью, стопом и расчётом позиции "
            "от риска. MOEX, крипто, forex, фьючерсы.\n\n"
            "Результат публикуется ответом на сам сигнал, "
            "независимо от того, в плюс он или в минус."
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Подписаться на канал", url=CHANNEL_SIGNALS_LINK)],
            [InlineKeyboardButton(f"🔓 Полный доступ ({PROMO_CODE})", url=SITE_URL)],
        ])

    await query.edit_message_text(text=text, reply_markup=keyboard)

    # Schedule follow-up after 24h if user doesn't convert
    context.job_queue.run_once(
        _followup_job,
        when=86400,  # 24 hours
        chat_id=query.message.chat_id,
        user_id=query.from_user.id,
        data={"exp": exp},
    )

    return ConversationHandler.END


async def _followup_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send follow-up message 24h after /start if user hasn't registered."""
    job = context.job
    exp = (job.data or {}).get("exp", "exp_signals")

    if exp == "exp_newbie":
        text = (
            "😳 Человек вступил — и сразу включился.\n"
            "В первый день получил первый результат 💲\n\n"
            "Без лишних сомнений. Просто начал — и увидел.\n\n"
            f"👉 Твоё место ещё свободно → {SITE_URL}\n"
            f"Промокод: {PROMO_CODE} — 14 дней бесплатно."
        )
    else:
        text = (
            f"📅 Сегодня новая торговая сессия.\n\n"
            f"Ты ещё не с нами? Самое время 👇\n"
            f"→ {SITE_URL}\n"
            f"Промокод {PROMO_CODE} — 14 дней Premium бесплатно."
        )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Активировать", url=SITE_URL)],
    ])
    try:
        await context.bot.send_message(
            chat_id=job.chat_id,
            text=text,
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.warning(f"Follow-up failed for {job.chat_id}: {e}")


# ═══ ADMIN COMMANDS ═══

async def cmd_start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin info command (only in group/channel or if args present)."""
    await update.message.reply_text(
        "🌊 WinExtraFlow Bot\n\n"
        "Команды:\n"
        "/publish {день} — опубликовать пост Wave 1\n"
        "/schedule — контент-план\n"
        "/custom {текст} — произвольный пост\n"
        "/test — тестовое сообщение\n"
        "/market — рыночный пульс"
    )


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["📋 Wave 1 — контент-план (28 дней)\n"]
    for day, post in sorted(WAVE1.items()):
        lines.append(f"  День {day} [{post['channel']}] — {post['title']}")
    lines.append(f"\n/publish {{день}} — опубликовать")
    await update.message.reply_text("\n".join(lines))


async def cmd_publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Укажи день: /publish 1")
        return

    try:
        day = int(context.args[0])
    except ValueError:
        await update.message.reply_text("День должен быть числом: /publish 1")
        return

    post = WAVE1.get(day)
    if not post:
        await update.message.reply_text(f"Нет поста для дня {day}. Доступные: {sorted(WAVE1.keys())}")
        return

    results = []

    # Publish to Signals channel
    if post["channel"] in ("signals", "both") and CHANNEL_SIGNALS_ID:
        try:
            msg = await context.bot.send_message(chat_id=CHANNEL_SIGNALS_ID, text=post["text"])
            results.append(f"✅ Signals: отправлено (msg_id: {msg.message_id})")

            # Forward to AI Growth Club
            if GROUP_AIGC_ID and any(tag in post["text"] for tag in FORWARD_TAGS):
                try:
                    await context.bot.forward_message(chat_id=GROUP_AIGC_ID, from_chat_id=CHANNEL_SIGNALS_ID, message_id=msg.message_id)
                    results.append("✅ AI Growth Club: переслано")
                except Exception as e:
                    results.append(f"❌ AI Growth Club: {e}")
        except Exception as e:
            results.append(f"❌ Signals: {e}")

    # Publish to VIP channel
    if post["channel"] in ("signals", "both") and CHANNEL_VIP_ID:
        try:
            # VIP gets clean text without tags
            clean = post["text"]
            for tag in FORWARD_TAGS + ["#winextraflow"]:
                clean = clean.replace(tag, "").strip()
            await context.bot.send_message(chat_id=CHANNEL_VIP_ID, text=clean)
            results.append("✅ VIP: отправлено")
        except Exception as e:
            results.append(f"❌ VIP: {e}")

    await update.message.reply_text(f"День {day} — {post['title']}\n\n" + "\n".join(results))


async def cmd_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if len(text) < 10:
        await update.message.reply_text("Текст слишком короткий. /custom {текст}")
        return

    tagged = text.rstrip() + "\n\n#repost #aigc #winextraflow"
    results = []

    if CHANNEL_SIGNALS_ID:
        try:
            msg = await context.bot.send_message(chat_id=CHANNEL_SIGNALS_ID, text=tagged)
            results.append(f"✅ Signals (msg_id: {msg.message_id})")

            if GROUP_AIGC_ID:
                try:
                    await context.bot.forward_message(chat_id=GROUP_AIGC_ID, from_chat_id=CHANNEL_SIGNALS_ID, message_id=msg.message_id)
                    results.append("✅ AI Growth Club (forwarded)")
                except Exception as e:
                    results.append(f"❌ Forward: {e}")
        except Exception as e:
            results.append(f"❌ Signals: {e}")

    await update.message.reply_text("Опубликовано:\n" + "\n".join(results))


async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🔧 Тест WinExtraFlow Bot\n\nПроверка подключения к каналам.\n\n#repost #aigc"
    results = []

    for name, cid in [("Signals", CHANNEL_SIGNALS_ID), ("VIP", CHANNEL_VIP_ID)]:
        if cid:
            try:
                msg = await context.bot.send_message(chat_id=cid, text=text)
                results.append(f"✅ {name}: OK (msg_id: {msg.message_id})")

                # Forward to group
                if name == "Signals" and GROUP_AIGC_ID:
                    try:
                        await context.bot.forward_message(chat_id=GROUP_AIGC_ID, from_chat_id=cid, message_id=msg.message_id)
                        results.append("✅ AI Growth Club: forwarded")
                    except Exception as e:
                        results.append(f"❌ Forward: {e}")
            except Exception as e:
                results.append(f"❌ {name}: {e}")

    await update.message.reply_text("Тест:\n" + "\n".join(results))


async def cmd_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick market pulse."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Fear & Greed
            fg = (await client.get("https://api.alternative.me/fng/?limit=1")).json()
            fg_val = fg["data"][0]["value"]
            fg_label = fg["data"][0]["value_classification"]

            # BTC price
            btc = (await client.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true")).json()
            btc_price = btc["bitcoin"]["usd"]
            btc_change = round(btc["bitcoin"]["usd_24h_change"], 1)

        await update.message.reply_text(
            f"📊 Market Pulse\n\n"
            f"Fear & Greed: {fg_val} ({fg_label})\n"
            f"BTC: ${btc_price:,.0f} ({btc_change:+.1f}%)\n\n"
            f"→ winextraflow.com"
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


# ═══ AUTO-FORWARD: channel posts with tags → AI Growth Club ═══

async def auto_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-forward channel posts containing #repost or #aigc to AI Growth Club."""
    if not update.channel_post or not GROUP_AIGC_ID:
        return

    text = update.channel_post.text or update.channel_post.caption or ""
    if any(tag in text.lower() for tag in FORWARD_TAGS):
        try:
            await context.bot.forward_message(
                chat_id=GROUP_AIGC_ID,
                from_chat_id=update.channel_post.chat_id,
                message_id=update.channel_post.message_id,
            )
            logger.info(f"Auto-forwarded message {update.channel_post.message_id} to AI Growth Club")
        except Exception as e:
            logger.error(f"Auto-forward failed: {e}")


# ═══ MAIN ═══

def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN not set in .env")
        return

    print(f"WinExtraFlow Bot starting...")
    print(f"  Signals: {CHANNEL_SIGNALS_ID}")
    print(f"  VIP: {CHANNEL_VIP_ID}")
    print(f"  AI Growth Club: {GROUP_AIGC_ID}")
    print(f"  Forward tags: {FORWARD_TAGS}")

    app = Application.builder().token(BOT_TOKEN).build()

    # User onboarding funnel (private chats only)
    funnel = ConversationHandler(
        entry_points=[CommandHandler("start", funnel_start, filters=filters.ChatType.PRIVATE)],
        states={
            EXPERIENCE: [CallbackQueryHandler(funnel_experience, pattern="^exp_")],
        },
        fallbacks=[],
        per_chat=True,
    )
    app.add_handler(funnel)

    # Admin commands (work everywhere)
    app.add_handler(CommandHandler("help", cmd_start_admin))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("publish", cmd_publish))
    app.add_handler(CommandHandler("custom", cmd_custom))
    app.add_handler(CommandHandler("test", cmd_test))
    app.add_handler(CommandHandler("market", cmd_market))

    # Auto-forward channel posts with tags
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, auto_forward))

    print("Bot running. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
