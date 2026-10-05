"""Lessons API — public, no auth.

Public on purpose: these articles are the funnel. A Telegram teaser links here, and
requiring a login to read the rest would end the funnel at the door.

There is deliberately no dynamic route on the frontend: the static export cannot
build `/learn/[slug]` (the same limitation that keeps `/dashboard/signals/[id]` out
of the Pages build), so one page reads `?a=<slug>` and fetches by slug.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.lesson import Lesson, LessonTopic

router = APIRouter()

TOPIC_RU = {
    LessonTopic.RISK: "Риск",
    LessonTopic.METHOD: "Методика",
    LessonTopic.STATISTICS: "Статистика",
    LessonTopic.MARKETS: "Рынки",
}


def _card(l: Lesson) -> dict:
    return {
        "slug": l.slug,
        "title": l.title,
        "topic": l.topic.value,
        "topic_ru": TOPIC_RU.get(l.topic, l.topic.value),
        "teaser": l.teaser,
        "views": l.views,
    }


@router.get("")
async def list_lessons(db: AsyncSession = Depends(get_db)):
    """All published lessons, in rotation order."""
    rows = (await db.execute(
        select(Lesson).where(Lesson.is_published.is_(True))
        .order_by(Lesson.position)
    )).scalars().all()
    return {"lessons": [_card(l) for l in rows], "total": len(rows)}


@router.get("/{slug}")
async def get_lesson(slug: str, db: AsyncSession = Depends(get_db)):
    """One lesson with its full text. Counts a view."""
    l = (await db.execute(
        select(Lesson).where(Lesson.slug == slug, Lesson.is_published.is_(True))
    )).scalar_one_or_none()
    if not l:
        raise HTTPException(404, "Материал не найден")
    l.views = (l.views or 0) + 1
    await db.commit()
    return {**_card(l), "body": l.body}
