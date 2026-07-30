"""Signal video clip — vertical 9:16 animated chart for Telegram stories/posts.

Renders an MP4: candles draw in progressively, then Entry/TP/SL levels appear,
then the verdict/WEF overlay. Branded dark theme, no external services.

Public entry: `make_clip()` -> mp4 path; `broadcast_clip()` -> send to channel.
Optional avatar overlay (PNG with alpha) via AVATAR_PATH env / arg.
"""

import logging
import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.services.backtesting_real import fetch_candles
from app.services.signal_chart import _instrument, NAME_MAP, PLATFORM_URL

logger = logging.getLogger(__name__)

W, H = 720, 1280          # 9:16 vertical
FPS = 24
BG = "#0a1628"


def _find_ffmpeg() -> str | None:
    """Locate ffmpeg (PATH or the winget install location)."""
    from shutil import which
    p = which("ffmpeg")
    if p:
        return p
    guess = os.path.expanduser(
        r"~\AppData\Local\Microsoft\WinGet\Packages"
        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        r"\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
    )
    return guess if os.path.exists(guess) else None


async def make_clip(ticker: str, action: str, entry: float, tp: float, sl: float,
                    wef: int, verdict: str = "", strategy: str = "",
                    days: int = 60, avatar_path: str | None = None,
                    hide_levels: bool = False) -> str | None:
    """Render a vertical animated MP4 for one signal. Returns path or None.

    hide_levels=True renders the free-channel teaser: candles + WEF only, with no
    level lines, no price labels and no y-axis prices — so the entry/TP/SL stay
    exclusive to VIP.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import animation

    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    date_to = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    candles = await fetch_candles(ticker, date_from, date_to)
    if not candles:
        logger.info(f"No candles for clip {ticker}")
        return None

    o, h, l, c = [], [], [], []
    for k in candles:
        if k.get("close") is None:
            continue
        o.append(k.get("open", 0)); h.append(k.get("high", 0))
        l.append(k.get("low", 0)); c.append(k.get("close", 0))
    if len(c) < 10:
        return None
    n = len(c)

    is_buy = action.lower() == "buy"
    rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
    name = NAME_MAP.get(ticker.upper(), ticker.upper())
    _, _, asset_type, currency = _instrument(ticker)
    price_fmt = ",.2f" if entry >= 1 else ",.5f"

    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor=BG)
    # chart occupies the middle band; header/footer are text zones
    ax = fig.add_axes([0.10, 0.34, 0.86, 0.40])
    ax.set_facecolor(BG)

    if hide_levels:
        # Teaser: scale to the candles only — including a hidden far-away target
        # would squash the price action into a corner.
        lo, hi = min(l) * 0.98, max(h) * 1.02
    else:
        lo = min(min(l), sl, tp) * 0.985
        hi = max(max(h), tp, sl) * 1.015
    ax.set_xlim(-1, n + 4)
    ax.set_ylim(lo, hi)
    ax.tick_params(colors="#64748b", labelsize=7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#1e3a5f"); ax.spines["left"].set_color("#1e3a5f")
    ax.grid(axis="y", color="#1e3a5f", alpha=0.25)
    ax.set_xticks([])

    # ── static text ──
    arrow = "BUY" if is_buy else "SELL"
    acc = "#10b981" if is_buy else "#ef4444"
    fig.text(0.5, 0.955, f"{arrow}  {ticker}", ha="center", color=acc, fontsize=34, fontweight="bold")
    fig.text(0.5, 0.918, f"{name} · {asset_type}", ha="center", color="#94a3b8", fontsize=13)
    head = f"WEF Score {wef}%" if hide_levels else f"WEF Score {wef}%   ·   R:R 1:{rr:.1f}"
    fig.text(0.5, 0.885, head, ha="center", color="#14b8a6", fontsize=17, fontweight="bold")
    fig.text(0.5, 0.045, "WinExtraFlow", ha="center", color="#14b8a6", fontsize=15, fontweight="bold")
    fig.text(0.5, 0.021, PLATFORM_URL.replace("https://", ""), ha="center", color="#64748b", fontsize=11)
    fig.text(0.5, 0.005, "Не является инвестиционной рекомендацией", ha="center", color="#475569", fontsize=8)

    # Teaser: no prices anywhere on the frame (y-axis included)
    if hide_levels:
        ax.set_yticklabels([])
        fig.text(0.5, 0.255, "Уровни входа, цели и стопа", ha="center",
                 color="#94a3b8", fontsize=15)
        fig.text(0.5, 0.213, "в VIP-канале", ha="center", color="#14b8a6",
                 fontsize=17, fontweight="bold")

    # dynamic text handles (levels + verdict), filled during animation
    t_entry = fig.text(0.10, 0.285, "", color="#3b82f6", fontsize=15, fontweight="bold")
    t_tp = fig.text(0.10, 0.245, "", color="#10b981", fontsize=15, fontweight="bold")
    t_sl = fig.text(0.10, 0.205, "", color="#ef4444", fontsize=15, fontweight="bold")
    t_verdict = fig.text(0.5, 0.135, "", ha="center", color="#e2e8f0", fontsize=15, fontweight="bold")
    t_strategy = fig.text(0.5, 0.100, "", ha="center", color="#94a3b8", fontsize=12)

    # optional avatar (bottom-right)
    if avatar_path and os.path.exists(avatar_path):
        try:
            import matplotlib.image as mpimg
            img = mpimg.imread(avatar_path)
            ax_av = fig.add_axes([0.68, 0.055, 0.28, 0.16], anchor="SE", zorder=10)
            ax_av.imshow(img)
            ax_av.axis("off")
        except Exception as e:
            logger.debug(f"avatar overlay skipped: {e}")

    draw_frames = 48          # candles drawing in
    hold_frames = 34          # levels + verdict reveal / hold
    total = draw_frames + hold_frames

    def frame(i):
        # candles progressively — clear previous frame's artists
        for art in list(ax.lines) + list(ax.collections):
            art.remove()
        upto = min(n, max(3, int(n * min(1.0, (i + 1) / draw_frames))))
        for k in range(upto):
            col = "#10b981" if c[k] >= o[k] else "#ef4444"
            ax.plot([k, k], [l[k], h[k]], color=col, linewidth=1.0)
            ax.plot([k, k], [min(o[k], c[k]), max(o[k], c[k])], color=col, linewidth=3.4)

        # levels appear after the draw phase (skipped entirely in teaser mode)
        if not hide_levels:
            if i >= draw_frames * 0.62:
                ax.axhline(entry, color="#3b82f6", ls="--", lw=1.6, alpha=0.9)
                t_entry.set_text(f"Вход   {entry:{price_fmt}} {currency}")
            if i >= draw_frames * 0.78:
                ax.axhline(tp, color="#10b981", ls=":", lw=1.6, alpha=0.9)
                pct = abs(tp - entry) / entry * 100
                t_tp.set_text(f"Цель   {tp:{price_fmt}}  (+{pct:.1f}%)")
            if i >= draw_frames * 0.9:
                ax.axhline(sl, color="#ef4444", ls=":", lw=1.6, alpha=0.9)
                pct = abs(entry - sl) / entry * 100
                t_sl.set_text(f"Стоп   {sl:{price_fmt}}  (-{pct:.1f}%)")
        if i >= draw_frames and verdict:
            t_verdict.set_text(f"Вердикт: {verdict}")
        if i >= draw_frames + 6 and strategy:
            t_strategy.set_text(strategy)
        return []

    suffix = "_teaser" if hide_levels else ""
    out = os.path.join(tempfile.gettempdir(), f"wef_clip_{ticker}{suffix}.mp4")
    ff = _find_ffmpeg()
    try:
        anim = animation.FuncAnimation(fig, frame, frames=total, interval=1000 / FPS, blit=False)
        if ff:
            matplotlib.rcParams["animation.ffmpeg_path"] = ff
            anim.save(out, writer=animation.FFMpegWriter(fps=FPS, bitrate=2400,
                                                        extra_args=["-pix_fmt", "yuv420p"]))
        else:
            out = out.replace(".mp4", ".gif")
            anim.save(out, writer=animation.PillowWriter(fps=12))
    except Exception as e:
        logger.error(f"clip render failed for {ticker}: {e}")
        plt.close(fig)
        return None
    plt.close(fig)
    return out


def build_clip_caption(ticker: str, action: str, entry: float, tp: float, sl: float,
                       wef: int, teaser: bool = False) -> str:
    """Short caption for the clip (full for VIP, teaser for the free channel)."""
    arrow = "\U0001f7e2" if action.lower() == "buy" else "\U0001f534"
    name = NAME_MAP.get(ticker.upper(), ticker.upper())
    _, _, asset_type, currency = _instrument(ticker)
    rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
    fmt = ",.2f" if entry >= 1 else ",.5f"
    tag = f"#{ticker} #WinExtraFlow"

    if teaser:
        return (
            f"{arrow} {action.upper()} {ticker} — WEF {wef}%\n"
            f"\U0001f3e6 {name} · {asset_type}\n\n"
            f"<b>Подробности сделки — в VIP-канале:</b>\n"
            f"• Цена входа, цель и стоп\n"
            f"• Соотношение риск/прибыль\n"
            f"• Размер позиции по Kelly\n"
            f"• Мат. ожидание и Profit Factor\n"
            f"• План входа частями (пирамидинг)\n"
            f"• Где торговать инструмент\n\n"
            f"\U0001f48e Сигналы с WEF 70%+ в общий канал не попадают — "
            f"только в VIP.\n\n"
            f"\U0001f4f2 {PLATFORM_URL}\n\n"
            f"⚠️ Не является инвестиционной рекомендацией.\n{tag}"
        )
    return (
        f"{arrow} {action.upper()} {ticker} — WEF {wef}%\n"
        f"\U0001f3e6 {name} · {asset_type}\n\n"
        f"\U0001f4cd Вход: {entry:{fmt}} {currency}\n"
        f"\U0001f3af Цель: {tp:{fmt}}\n"
        f"\U0001f6d1 Стоп: {sl:{fmt}}\n"
        f"⚖️ R:R 1:{rr:.1f}\n\n"
        f"\U0001f4f2 Полный разбор: {PLATFORM_URL}\n\n"
        f"⚠️ Не является инвестиционной рекомендацией.\n{tag}"
    )


MAX_CAPTION = 1024  # Telegram limit for media captions


async def broadcast_clip(ticker: str, action: str, entry: float, tp: float, sl: float,
                         wef: int, verdict: str = "", strategy: str = "",
                         chat_id: str | None = None, teaser: bool = False,
                         avatar_path: str | None = None, clip_path: str | None = None,
                         caption: str | None = None) -> bool:
    """Render (or reuse) a clip and send it as a video to a channel.

    `caption` overrides the default (used to attach the full expert description).
    """
    token = settings.telegram_bot_token
    chat_id = chat_id or settings.telegram_vip_channel_id
    if not token or not chat_id:
        logger.info(f"Clip skipped (no token/channel) for {ticker}")
        return False

    path = clip_path or await make_clip(ticker, action, entry, tp, sl, wef, verdict, strategy,
                                        avatar_path=avatar_path)
    if not path or not os.path.exists(path):
        return False

    caption = caption or build_clip_caption(ticker, action, entry, tp, sl, wef, teaser=teaser)
    if len(caption) > MAX_CAPTION:
        # Trim on a line boundary, keep the disclaimer/link tail readable
        caption = caption[:MAX_CAPTION - 60].rsplit("\n", 1)[0] + f"\n\n\U0001f4f2 {PLATFORM_URL}"
    method = "sendVideo" if path.endswith(".mp4") else "sendAnimation"
    field = "video" if path.endswith(".mp4") else "animation"
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            with open(path, "rb") as f:
                resp = await client.post(
                    f"https://api.telegram.org/bot{token}/{method}",
                    data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML",
                          "disable_notification": "true", "supports_streaming": "true"},
                    files={field: (os.path.basename(path), f, "video/mp4")},
                )
        ok = resp.json().get("ok", False)
        if not ok:
            logger.error(f"Clip send failed for {ticker}: {resp.text[:200]}")
        return ok
    except Exception as e:
        logger.error(f"Clip send error for {ticker}: {e}")
        return False
