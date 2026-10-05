"""Find the chat id the watchdog should report to.

The watchdog tries the bot first, but the bot can only write to a chat id it has
been given, and `ADMIN_TELEGRAM_CHAT_ID` was never set. Its only fallback was the
Telethon user session writing to Saved Messages — which is the same session the
signal pipeline uses, so when that session broke the watchdog lost its voice at
exactly the moment it had something to report. The pipeline had been dead for a
month before anyone noticed.

Run this once, send the bot any message, and put the printed id in .env.

Usage:
    python scripts/tg_find_admin_chat.py          # wait up to 120s for a message
    python scripts/tg_find_admin_chat.py --wait 300
"""
import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

from app.config import settings


async def main():
    wait = 120
    if "--wait" in sys.argv:
        wait = int(sys.argv[sys.argv.index("--wait") + 1])

    token = settings.telegram_bot_token
    if not token:
        print("TELEGRAM_BOT_TOKEN не задан в .env")
        return 1

    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"https://api.telegram.org/bot{token}/getMe")
        j = r.json()
        if not j.get("ok"):
            print(f"Токен не работает: {j.get('description')}")
            return 1
        username = j["result"]["username"]

        hook = (await c.get(
            f"https://api.telegram.org/bot{token}/getWebhookInfo"
        )).json().get("result", {})
        if hook.get("url"):
            print(f"ВНИМАНИЕ: установлен webhook ({hook['url']}). Пока он стоит, "
                  f"getUpdates не отдаёт сообщения — снимите его или возьмите "
                  f"chat id из webhook-обработчика.")
            return 1

        print(f"Бот: @{username}")
        print(f"\nОткройте https://t.me/{username} и отправьте ему любое "
              f"сообщение — например «/start».")
        print(f"Жду до {wait} секунд…\n")

        deadline = asyncio.get_event_loop().time() + wait
        offset = None
        seen: dict[int, tuple] = {}
        while asyncio.get_event_loop().time() < deadline:
            params = {"timeout": 20}
            if offset is not None:
                params["offset"] = offset
            try:
                r = await c.get(f"https://api.telegram.org/bot{token}/getUpdates",
                                params=params, timeout=30)
                ups = r.json().get("result", [])
            except httpx.TimeoutException:
                continue

            for u in ups:
                offset = u["update_id"] + 1
                msg = (u.get("message") or u.get("channel_post")
                       or u.get("my_chat_member") or {})
                ch = msg.get("chat") or {}
                if not ch.get("id"):
                    continue
                name = (ch.get("title") or ch.get("username")
                        or ch.get("first_name") or "")
                seen[ch["id"]] = (ch.get("type"), name)

            private = [(i, v) for i, v in seen.items() if v[0] == "private"]
            if private:
                cid, (_, name) = private[0]
                print(f"Нашёл личный чат: {cid}  ({name})\n")
                print("Добавьте в backend/.env:")
                print(f"    ADMIN_TELEGRAM_CHAT_ID={cid}")
                print("\nПроверить: python scripts/watchdog.py")
                return 0

        if seen:
            print("Личного чата не было, но бот видел эти чаты:")
            for cid, (t, n) in seen.items():
                print(f"    {cid}  {t}  {n}")
            print("\nОтчёты сторожа лучше слать в личку, а не в канал.")
        else:
            print("Сообщений не пришло. Проверьте, что пишете именно "
                  f"@{username}, и что бот не заблокирован.")
        return 1


sys.exit(asyncio.run(main()))
