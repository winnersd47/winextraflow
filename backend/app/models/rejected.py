"""What the pipeline turned down, kept so the filter can be judged.

The platform's whole claim is selection: it relays other people's signals
through a filter and says the filter is worth paying for. That claim was
unmeasurable in principle, because the pipeline discarded every candidate it
refused before writing anything — `continue`, and the evidence is gone.

Counted 2026-11-05: 194 real signals stored, exactly ONE of them carrying a
quality-gate rejection. Not because almost nothing is rejected, but because
almost every rejection happens earlier, in scripts/tg_backfill.py, and leaves
no trace. You cannot show that what you kept was better than what you dropped
when only what you kept exists.

A row here is a candidate that looked like a signal and did not become one.
With the levels as they were parsed, it can be replayed against real candles
later, exactly like a published signal — which is the comparison that answers
"does the filter add anything", and the only one that does.

Deliberately NOT stored: messages that never looked like a signal at all.
Those are chat, not rejections, and keeping them would bury the question in
noise.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String

from app.database import Base


class RejectionStage:
    """Where a candidate died. Values are stored as plain strings."""

    PARSE = "parse"          # looked like a signal, no parser could read it
    DUPLICATE = "duplicate"  # same ticker+direction from this source, recently
    LEVELS = "levels"        # entry/target/stop could not be made usable
    QUALITY = "quality"      # the gate refused the finished geometry
    EVOLUTION = "evolution"  # the strategy verdict said SKIP

    ALL = (PARSE, DUPLICATE, LEVELS, QUALITY, EVOLUTION)


class RejectedCandidate(Base):
    __tablename__ = "rejected_candidates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Where it came from. `channel` is the username, the same key providers are
    # resolved by since the move off Telethon.
    channel = Column(String, nullable=True, index=True)
    provider_id = Column(String, nullable=True, index=True)
    # The post's own id ("channel/12345"), so one message cannot be recorded
    # twice when the backfill re-reads the window — it re-reads it ~48 times.
    message_id = Column(String, nullable=True, index=True, unique=True)

    stage = Column(String, nullable=False, index=True)
    reason = Column(String, nullable=True)

    # As parsed, before anything was corrected — None where parsing failed.
    # These are what make a row replayable; without them it is only a count.
    ticker = Column(String, nullable=True, index=True)
    action = Column(String, nullable=True)
    entry_price = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)

    # Enough of the post to re-read it by hand, and to re-parse it later with a
    # better parser: today's regexes miss most RU prose, so a PARSE row is as
    # much a record of our own limits as of the source's.
    raw_message = Column(String, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        index=True)
