"""Post an educational teaser to the channels, full text on the platform.

Fills the gap between signals: the channels had nothing else to publish except
signals and posts about the platform's own features, which gives a reader no reason
to come back and the platform no way to show what it does well. With 11 measured
trades that is method, not results — and every lesson is written from a mistake this
project made and measured, so nothing in them is a claim we cannot back.

Rotation: the least recently posted lesson goes next, so the whole library is used
before anything repeats.

Usage:
    python scripts/lesson_post.py --seed        # load/refresh the library
    python scripts/lesson_post.py --dry         # show what would be posted
    python scripts/lesson_post.py               # post the next lesson
    python scripts/lesson_post.py --slug=<slug>  # post a specific one
    python scripts/lesson_post.py --full --slug=<slug>   # whole article in-channel

--full exists because the teaser promises the full text in the channel for readers
who cannot open the site. That promise has to be keepable: nobody is told to install
anything to reach a page (ст. 13.41 КоАП penalises promoting circumvention), so the
material comes to them instead.
"""
import asyncio, os, sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.lesson import Lesson, LessonTopic
from app.services.lesson_seed import LESSONS
from app.services.signal_chart import PLATFORM_ACCESS_NOTE, PLATFORM_URL

# Telegram's text limit is 4096, but a teaser that needs scrolling is not a teaser.
MAX_TEASER = 900


async def seed() -> None:
    """Insert new lessons, refresh the text of existing ones by slug."""
    async with async_session() as db:
        existing = {l.slug: l for l in (await db.execute(select(Lesson))).scalars().all()}
        added = updated = 0
        for spec in LESSONS:
            row = existing.get(spec["slug"])
            if row:
                # Refresh content but keep posted_at and views — the rotation state
                # and the view counter are history, not content.
                row.title, row.teaser, row.body = spec["title"], spec["teaser"], spec["body"]
                row.topic = LessonTopic(spec["topic"])
                row.position = spec["position"]
                updated += 1
            else:
                db.add(Lesson(
                    slug=spec["slug"], title=spec["title"],
                    topic=LessonTopic(spec["topic"]), teaser=spec["teaser"],
                    body=spec["body"], position=spec["position"],
                ))
                added += 1
        await db.commit()
        print(f"Библиотека: добавлено {added}, обновлено {updated}, всего {len(LESSONS)}")


def build_post(lesson: Lesson) -> str:
    """Teaser + link. The link is the whole point, so it must not be buried."""
    url = f"{PLATFORM_URL}/learn?a={lesson.slug}"
    teaser = lesson.teaser.strip()
    if len(teaser) > MAX_TEASER:
        teaser = teaser[:MAX_TEASER].rsplit("\n", 1)[0].rstrip()
    return (
        f"📘 <b>{lesson.title}</b>\n\n"
        f"{teaser}\n\n"
        f"👉 <a href=\"{url}\">Читать полностью на платформе</a>\n"
        f"<i>{PLATFORM_ACCESS_NOTE}</i>\n\n"
        f"⚠️ Не является инвестиционной рекомендацией.\n"
        f"#обучение #WinExtraFlow"
    )


TG_LIMIT = 4096
# Leave room for the part counter and the disclaimer appended to the last chunk.
CHUNK = 3600


def md_to_telegram(md: str) -> str:
    """Markdown -> the small HTML subset Telegram accepts.

    Telegram supports no headings, tables or lists, so those become plain text with
    bold and bullets. Escaping runs first: an unescaped "<" in the source would make
    Telegram reject the whole message.
    """
    import re

    out: list[str] = []
    for raw in md.split("\n"):
        line = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if line.startswith("# "):
            continue                       # the title is the post's own heading
        if line.startswith("## "):
            out.append(f"\n<b>{line[3:]}</b>")
            continue
        if line.startswith("### "):
            out.append(f"\n<b>{line[4:]}</b>")
            continue
        if line.startswith("```"):
            continue                       # fences dropped; content kept as text
        if line.startswith("|"):
            # Table row -> "cell · cell", separators skipped entirely.
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            line = " · ".join(cells)
        line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
        line = re.sub(r"`(.+?)`", r"<code>\1</code>", line)
        line = re.sub(r"^[-*] ", "• ", line)
        out.append(line)
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def build_full_posts(lesson: Lesson) -> list[str]:
    """The whole article for the channel, split to fit Telegram's limit.

    This is what makes the note in the teaser ("полный текст публикуем здесь же")
    a real option rather than a polite phrase: a reader who cannot reach the site
    still gets the material, and no one is told to install anything.
    """
    body = md_to_telegram(lesson.body)
    head = f"📘 <b>{lesson.title}</b>\n\n"
    tail = ("\n\n⚠️ Не является инвестиционной рекомендацией."
            "\n#обучение #WinExtraFlow")

    budget = CHUNK - len(head) - len(tail)
    chunks: list[str] = []
    rest = body
    while rest:
        if len(rest) <= budget:
            chunks.append(rest)
            break
        cut = rest.rfind("\n\n", 0, budget)
        if cut < budget // 2:
            cut = rest.rfind("\n", 0, budget)
        if cut <= 0:
            cut = budget
        chunks.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()

    posts = []
    for i, ch in enumerate(chunks, 1):
        counter = f" ({i}/{len(chunks)})" if len(chunks) > 1 else ""
        posts.append(f"📘 <b>{lesson.title}</b>{counter}\n\n{ch}"
                     + (tail if i == len(chunks) else ""))
    return posts


async def pick(db, slug: str | None) -> Lesson | None:
    """The chosen lesson, or the least recently posted one."""
    if slug:
        return (await db.execute(
            select(Lesson).where(Lesson.slug == slug)
        )).scalar_one_or_none()
    rows = (await db.execute(
        select(Lesson).where(Lesson.is_published.is_(True))
    )).scalars().all()
    if not rows:
        return None
    # Never-posted first (by position), then oldest posted.
    never = sorted([l for l in rows if not l.posted_at], key=lambda l: l.position)
    if never:
        return never[0]
    return sorted(rows, key=lambda l: l.posted_at)[0]


async def send(text: str) -> bool:
    token = settings.telegram_bot_token
    if not token:
        print("BOT_TOKEN не задан")
        return False
    ok_any = False
    for chat in (settings.telegram_free_channel_id, settings.telegram_vip_channel_id):
        if not chat:
            continue
        body = {"chat_id": chat, "text": text, "parse_mode": "HTML",
                # The teaser's value is the link; a preview card of our own page
                # helps rather than clutters.
                "disable_web_page_preview": False,
                "disable_notification": True}
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                             content=__import__("json").dumps(body).encode("utf-8"),
                             headers={"Content-Type": "application/json; charset=utf-8"})
        got = r.json().get("ok", False)
        ok_any = ok_any or got
        print(f"  {chat}: {'отправлено' if got else 'ошибка ' + r.text[:120]}")
        await asyncio.sleep(1)
    return ok_any


async def main():
    if "--seed" in sys.argv:
        await seed()
        return

    slug = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--slug=")), None)
    dry = "--dry" in sys.argv

    async with async_session() as db:
        lesson = await pick(db, slug)
        if not lesson:
            print("Материалов нет — сначала: python scripts/lesson_post.py --seed")
            return
        full = "--full" in sys.argv
        parts = build_full_posts(lesson) if full else [build_post(lesson)]
        print(f"{'=' * 60}\n{lesson.slug}  (позиция {lesson.position}, "
              f"публиковалась: {lesson.posted_at or 'ни разу'})"
              f"{'  [полный текст]' if full else ''}\n{'=' * 60}")
        for i, p in enumerate(parts, 1):
            if len(parts) > 1:
                print(f"\n--- часть {i}/{len(parts)}, {len(p)} символов ---")
            print(p)
            if len(p) > TG_LIMIT:
                print(f"!! часть {i} длиннее лимита Telegram ({len(p)} > {TG_LIMIT})")
        if dry:
            print("\n(--dry: не отправлено)")
            return
        sent = False
        for p in parts:
            sent = await send(p) or sent
            await asyncio.sleep(1)
        if sent and not full:
            # Only the teaser advances the rotation: publishing the full text is a
            # follow-up to a teaser already out, not a new item in the queue.
            lesson.posted_at = datetime.now(timezone.utc)
            await db.commit()
            print(f"\nОтмечено как опубликованное: {lesson.slug}")


# Guarded so the module can be imported — the post builders are unit-tested, and
# an unguarded asyncio.run would try to publish on import.
if __name__ == "__main__":
    asyncio.run(main())
