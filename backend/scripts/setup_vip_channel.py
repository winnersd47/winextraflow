"""One-time VIP channel setup: description + reactions + pinned legend.

Uses the admin user session (@winnersd95). Idempotent-ish (re-pins a fresh legend).
Usage: python scripts/setup_vip_channel.py
"""
import asyncio, os, sys, shutil
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from telethon import TelegramClient
from telethon.tl.functions.messages import EditChatAboutRequest, SetChatAvailableReactionsRequest
from telethon.tl.types import ChatReactionsSome, ReactionEmoji
from app.config import settings

PLATFORM = "https://winextraflow.pages.dev"

ABOUT = (
    "AI-сигналы: MOEX, крипто, форекс, акции США. WEF Score по 9 факторам, "
    "TP/SL, экспертный анализ, графики. Платформа: winextraflow.pages.dev. "
    "Не является инвестиционной рекомендацией."
)

LEGEND = f"""📊 <b>WinExtraFlow VIP — как читать сигналы</b>

🟢 BUY / 🔴 SELL — направление сделки
<b>WEF Score (0–100%)</b> — оценка качества по 9 факторам: риск-менеджмент, R:R, история провайдера, Sharpe, Profit Factor, просадка, частота, полнота, тайминг.

<b>Уровни:</b>
📍 Вход — цена входа
🎯 Цель (TP) — фиксация прибыли
🛑 Стоп (SL) — ограничение убытка
⚖️ R:R — риск/прибыль (≥1.5 — хорошо, ≥2 — отлично)

<b>Вердикт:</b> ОТЛИЧНЫЙ ✅ / ХОРОШИЙ ✅ / СРЕДНИЙ ⚠️ / РИСКОВАННЫЙ ⚠️

<b>Экспертный анализ:</b> EV (мат. ожидание), Profit Factor, Kelly (размер позиции), пирамидинг, Edge.

🔔 Сигналы с WEF ≥ 80% приходят со звуком, остальные — тихо.
👍 🔥 📈 🚀 — ставьте реакции

⚠️ <b>Не является индивидуальной инвестиционной рекомендацией.</b> Торговля сопряжена с риском потери капитала.

🔗 Платформа: {PLATFORM}"""


def _proxy():
    if settings.socks5_host and settings.socks5_port:
        import socks
        return (socks.SOCKS5, settings.socks5_host, int(settings.socks5_port), True,
                settings.socks5_user or None, settings.socks5_pass or None)
    return None


async def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    work = os.path.join(base, "wef_setup.session")
    shutil.copyfile(os.path.join(base, "winextraflow_bot.session"), work)
    client = TelegramClient(work, int(settings.telegram_api_id), settings.telegram_api_hash, proxy=_proxy())
    await client.connect()
    chan = await client.get_entity(int(settings.telegram_vip_channel_id))

    # 1. Description
    try:
        await client(EditChatAboutRequest(peer=chan, about=ABOUT))
        print("[OK] Описание канала установлено")
    except Exception as e:
        print(f"[FAIL] Описание: {e}")

    # 2. Reactions
    try:
        reactions = ChatReactionsSome(reactions=[ReactionEmoji(emoticon=e) for e in ["👍", "🔥", "📈", "🚀", "❤️"]])
        await client(SetChatAvailableReactionsRequest(peer=chan, available_reactions=reactions))
        print("[OK] Реакции включены: 👍 🔥 📈 🚀 ❤️")
    except Exception as e:
        print(f"[FAIL] Реакции: {e}")

    # 3. Pinned legend
    try:
        msg = await client.send_message(chan, LEGEND, parse_mode="HTML", link_preview=False)
        await client.pin_message(chan, msg, notify=False)
        print(f"[OK] Легенда отправлена и закреплена (msg {msg.id})")
    except Exception as e:
        print(f"[FAIL] Легенда: {e}")

    await client.disconnect()
    try: os.remove(work)
    except OSError: pass
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
