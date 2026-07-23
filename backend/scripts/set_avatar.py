"""Generate a branded logo and set it as the VIP channel avatar.

Usage: python scripts/set_avatar.py
"""
import asyncio, os, sys, shutil
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from telethon import TelegramClient
from telethon.tl.functions.channels import EditPhotoRequest
from telethon.tl.types import InputChatUploadedPhoto
from app.config import settings


def make_logo(path: str):
    fig, ax = plt.subplots(figsize=(6.4, 6.4), facecolor="#0a1628")
    ax.set_facecolor("#0a1628")
    ax.set_xlim(0, 10); ax.set_ylim(0, 10)
    ax.axis("off")

    # Three stacked brand waves (teal), fading
    x = np.linspace(0, 10, 200)
    for i, (yc, alpha, lw) in enumerate([(6.2, 1.0, 6), (5.4, 0.5, 4), (4.6, 0.25, 3)]):
        y = yc + 0.7 * np.sin(x * 1.6)
        ax.plot(x, y, color="#14b8a6", alpha=alpha, linewidth=lw, solid_capstyle="round")

    # Rising bars (green) under the waves — signal/growth motif
    for i, h in enumerate([1.1, 1.8, 1.4, 2.4, 2.0, 3.0]):
        ax.bar(1.4 + i * 1.3, h, width=0.55, bottom=1.0, color="#10b981", alpha=0.85)

    # Text
    ax.text(5, 8.6, "WEF", ha="center", va="center", fontsize=64, fontweight="bold", color="#14b8a6")
    ax.text(5, 0.5, "WinExtraFlow", ha="center", va="center", fontsize=20, fontweight="bold", color="#e2e8f0")

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(path, dpi=100, facecolor="#0a1628")
    plt.close()


def _proxy():
    if settings.socks5_host and settings.socks5_port:
        import socks
        return (socks.SOCKS5, settings.socks5_host, int(settings.socks5_port), True,
                settings.socks5_user or None, settings.socks5_pass or None)
    return None


async def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logo = os.path.join(base, "wef_logo.png")
    make_logo(logo)
    print(f"Logo generated: {logo}")

    work = os.path.join(base, "wef_avatar.session")
    shutil.copyfile(os.path.join(base, "winextraflow_bot.session"), work)
    client = TelegramClient(work, int(settings.telegram_api_id), settings.telegram_api_hash, proxy=_proxy())
    await client.connect()
    chan = await client.get_entity(int(settings.telegram_vip_channel_id))
    try:
        uploaded = await client.upload_file(logo)
        await client(EditPhotoRequest(channel=chan, photo=InputChatUploadedPhoto(file=uploaded)))
        print("[OK] Аватар канала установлен")
    except Exception as e:
        print(f"[FAIL] Аватар: {e}")
    await client.disconnect()
    try: os.remove(work)
    except OSError: pass


if __name__ == "__main__":
    asyncio.run(main())
