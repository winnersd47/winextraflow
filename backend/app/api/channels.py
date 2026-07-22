"""Channel Discovery API — search Telegram signal channels + manage monitoring.

  GET    /channels/markets                — available markets + query keywords
  GET    /channels/discovered             — last discovery results (all/one market)
  POST   /channels/discover               — run a fresh discovery (admin, heavy)
  GET    /channels/monitored              — channels currently parsed
  POST   /channels/monitored              — add a channel to monitoring (admin)
  DELETE /channels/monitored/{username}   — remove from monitoring (admin)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User, UserRole
from app.services import channel_discovery as cd

logger = logging.getLogger(__name__)
router = APIRouter()


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(403, "Admin access required")
    return user


class AddChannelReq(BaseModel):
    username: str


@router.get("/markets")
async def markets(user: User = Depends(get_current_user)):
    """Available markets and their search keywords."""
    return {
        "markets": [
            {"key": k, "queries": v, "label": {
                "moex": "MOEX / Акции РФ", "crypto": "Криптовалюта", "forex": "Форекс",
                "stocks_us": "Акции США", "commodities": "Сырьё (золото/нефть)",
            }.get(k, k)}
            for k, v in cd.MARKET_QUERIES.items()
        ]
    }


@router.get("/discovered")
async def discovered(market: str | None = Query(None), user: User = Depends(get_current_user)):
    """Last saved discovery results. Filter by market if given."""
    data = cd.load_results().get("markets", {})
    monitored = {m.lower() for m in cd.load_monitored()}
    if market:
        channels = data.get(market, [])
        for c in channels:
            c["monitored"] = c["username"].lower() in monitored
        return {"market": market, "channels": channels}
    # All markets — annotate monitored flag
    for m, channels in data.items():
        for c in channels:
            c["monitored"] = c["username"].lower() in monitored
    return {"markets": data}


@router.post("/discover")
async def run_discover(market: str | None = Query(None), admin: User = Depends(require_admin)):
    """Run a fresh discovery (uses the phone session; heavy). Admin only."""
    markets = [market] if market else None
    try:
        results = await cd.discover(markets)
        cd.save_results({**cd.load_results().get("markets", {}), **results} if market else results)
        total = sum(len(v) for v in results.values())
        ready = [c["username"] for v in results.values() for c in v if c["tier"] == "signals"]
        return {"ok": True, "total": total, "ready_to_monitor": ready, "markets": results}
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        raise HTTPException(500, f"Discovery failed: {e}")


@router.get("/monitored")
async def monitored(user: User = Depends(get_current_user)):
    """Channels currently monitored for signal parsing."""
    return {"channels": cd.load_monitored()}


@router.post("/monitored")
async def add_monitored(req: AddChannelReq, admin: User = Depends(require_admin)):
    """Add a channel to the monitored parse list."""
    channels = cd.add_monitored(req.username)
    return {"ok": True, "channels": channels}


@router.delete("/monitored/{username}")
async def remove_monitored(username: str, admin: User = Depends(require_admin)):
    """Remove a channel from the monitored parse list."""
    channels = cd.remove_monitored(username)
    return {"ok": True, "channels": channels}
