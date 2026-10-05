"""Educational articles: a Telegram teaser plus the full text on the platform.

The channels currently have nothing to post except signals and posts about the
platform's own features. That gives a reader no reason to come back between
signals, and it gives the platform no way to show what it actually does well —
which, with 11 measured trades, is method rather than results.

Every lesson here is written from something this project got wrong and measured:
stops tighter than one ATR, analyst targets published as trades, win rates computed
over three closed trades. That is content the platform can back up, unlike the
"87% win rate" material competitors publish.

`teaser` is what goes to Telegram (kept under the caption limit); `body` is the
full markdown served from the platform.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LessonTopic(str, enum.Enum):
    RISK = "risk"                 # position sizing, stops, R:R
    METHOD = "method"             # how signals are filtered and scored
    STATISTICS = "statistics"     # sample size, what a win rate does not mean
    MARKETS = "markets"           # instrument and data specifics


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Stable url key — the Telegram link points at ?a=<slug>, so renaming a slug
    # breaks every post already published. Treat it as permanent.
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    topic: Mapped[LessonTopic] = mapped_column(Enum(LessonTopic), default=LessonTopic.METHOD)

    # Telegram teaser: one idea, ends on the question the article answers.
    teaser: Mapped[str] = mapped_column(Text)
    # Full article, markdown.
    body: Mapped[str] = mapped_column(Text)

    # Rotation order for the Telegram scheduler.
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set when the teaser goes out, so the rotation does not repeat a lesson before
    # it has been through the whole library.
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    views: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())
