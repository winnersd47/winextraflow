"""Export the lesson library to frontend/public/lessons.json.

The static export on Cloudflare Pages has no backend behind it, so `/learn` would
load and then fail to fetch anything — a page that opens and says "материал не
найден" is worse than a 404, because it looks like our content is broken rather than
missing.

Lessons are static articles: nothing about them needs a request. Baking them into
the build makes the Telegram funnel work before the VPS exists, and the page still
prefers the API when one is reachable (that path counts views).

Run as part of the frontend build — build-pages.bat calls it.
"""
import asyncio, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.api.lessons import TOPIC_RU
from app.database import async_session
from app.models.lesson import Lesson

OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend", "public", "lessons.json",
)


async def main():
    async with async_session() as db:
        rows = (await db.execute(
            select(Lesson).where(Lesson.is_published.is_(True)).order_by(Lesson.position)
        )).scalars().all()

    payload = {
        "lessons": [
            {
                "slug": l.slug,
                "title": l.title,
                "topic": l.topic.value,
                "topic_ru": TOPIC_RU.get(l.topic, l.topic.value),
                "teaser": l.teaser,
                "body": l.body,
                # Views are a live counter; a build-time snapshot would be a stale
                # number pretending to be current, so it is left out entirely.
            }
            for l in rows
        ],
        "total": len(rows),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"Выгружено материалов: {len(rows)} -> {OUT}")
    if not rows:
        print("ВНИМАНИЕ: библиотека пуста — сначала scripts/lesson_post.py --seed")


asyncio.run(main())
