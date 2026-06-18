"""Content API — manage and publish marketing posts to Telegram channels.

Channels:
- @WinExtraFlowSignals — signals + analytics
- AI Growth Club — marketing + education

Admin can: view schedule, preview posts, publish manually, publish by day.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user
from app.models.user import User, UserRole
from app.services.content_scheduler import get_post_for_day, get_full_schedule, WAVE1_POSTS
from app.services.telegram_bot import telegram_bot
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(403, "Admin only")
    return user


@router.get("/schedule")
async def content_schedule(admin: User = Depends(require_admin)):
    """View full Wave 1 content plan (28 days, 8 posts)."""
    return {
        "wave": 1,
        "total_posts": len(WAVE1_POSTS),
        "duration_days": 28,
        "channels": {
            "signals": "@WinExtraFlowSignals",
            "growth": "AI Growth Club",
        },
        "schedule": get_full_schedule(),
    }


@router.get("/preview/{day}")
async def preview_post(day: int, admin: User = Depends(require_admin)):
    """Preview posts for a specific day."""
    posts = get_post_for_day(day)
    if not posts:
        raise HTTPException(404, f"No posts for day {day}")
    return {
        "day": day,
        "posts": [
            {
                "channel": p.channel,
                "type": p.type,
                "title": p.title,
                "text": p.text,
                "text_length": len(p.text),
            }
            for p in posts
        ],
    }


@router.post("/publish/{day}")
async def publish_day(day: int, admin: User = Depends(require_admin)):
    """Publish all posts for a specific day to Telegram channels."""
    posts = get_post_for_day(day)
    if not posts:
        raise HTTPException(404, f"No posts for day {day}")

    results = []
    for post in posts:
        if not telegram_bot.enabled:
            results.append({"title": post.title, "sent": False, "error": "Bot not configured"})
            continue

        # Step 1: Publish to @WinExtraFlowSignals with #repost #aigc tags
        # (tags allow AI Growth Club aggregator to pick it up automatically)
        if settings.telegram_free_channel_id:
            tagged_text = post.text.rstrip() + "\n\n#repost #aigc #winextraflow"
            try:
                msg = await telegram_bot.send_to_channel(settings.telegram_free_channel_id, tagged_text)
                sent_signals = True
                logger.info(f"Published day {day} '{post.title}' to @WinExtraFlowSignals")

                # Step 2: Forward the message to AI Growth Club
                # (so it appears as forwarded from the channel)
                if settings.telegram_growth_group_id and msg and msg.get("result", {}).get("message_id"):
                    try:
                        await telegram_bot._call(
                            "forwardMessage",
                            chat_id=settings.telegram_growth_group_id,
                            from_chat_id=settings.telegram_free_channel_id,
                            message_id=msg["result"]["message_id"],
                        )
                        logger.info(f"Forwarded to AI Growth Club")
                    except Exception as e:
                        logger.warning(f"Forward to Growth Club failed: {e}")

            except Exception as e:
                sent_signals = False
                logger.error(f"Failed to publish to signals: {e}")

            results.append({
                "channel": "signals → growth (forward)",
                "title": post.title,
                "sent": sent_signals,
                "tags": "#repost #aigc #winextraflow",
            })

        # Also publish to VIP channel (without tags, instant)
        if post.channel in ("signals", "both") and settings.telegram_vip_channel_id:
            try:
                await telegram_bot.send_to_channel(settings.telegram_vip_channel_id, post.text)
                results.append({"channel": "vip", "title": post.title, "sent": True})
            except Exception as e:
                results.append({"channel": "vip", "title": post.title, "sent": False, "error": str(e)})

    return {"day": day, "results": results}


@router.post("/publish-custom")
async def publish_custom(
    text: str,
    channel: str = Query("both", description="signals, growth, or both"),
    admin: User = Depends(require_admin),
):
    """Publish a custom text to channels."""
    if len(text) < 10:
        raise HTTPException(400, "Text too short")
    if len(text) > 4096:
        raise HTTPException(400, "Text too long (Telegram limit 4096)")

    if not telegram_bot.enabled or not settings.telegram_free_channel_id:
        raise HTTPException(400, "Bot not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_FREE_CHANNEL_ID in .env")

    results = []

    # Publish to @WinExtraFlowSignals with tags
    tagged = text.rstrip() + "\n\n#repost #aigc #winextraflow" if channel in ("growth", "both") else text
    try:
        msg = await telegram_bot.send_to_channel(settings.telegram_free_channel_id, tagged)
        results.append({"channel": "signals", "sent": True, "tags": "#repost #aigc" if channel in ("growth", "both") else None})

        # Forward to AI Growth Club if tagged
        if channel in ("growth", "both") and settings.telegram_growth_group_id and msg and msg.get("result", {}).get("message_id"):
            try:
                await telegram_bot._call(
                    "forwardMessage",
                    chat_id=settings.telegram_growth_group_id,
                    from_chat_id=settings.telegram_free_channel_id,
                    message_id=msg["result"]["message_id"],
                )
                results.append({"channel": "growth (forwarded)", "sent": True})
            except Exception as e:
                results.append({"channel": "growth (forward)", "sent": False, "error": str(e)})
    except Exception as e:
        results.append({"channel": "signals", "sent": False, "error": str(e)})

    return {"results": results}
