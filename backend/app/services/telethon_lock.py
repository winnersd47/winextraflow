"""One Telethon client at a time, across processes.

Why this exists
---------------
An auth key is the account's identity. Telegram revokes it with
`AuthKeyDuplicatedError` when it sees the same key connect from what look like
two different places — and this project arranged for exactly that in two ways at
once:

  * six scripts did `shutil.copyfile` on the .session file to dodge SQLite's
    writer lock (setup_vip_channel, set_avatar, tg_channels_report,
    tg_find_signals, watchdog). A copied session file is a copied auth key, not
    a separate login. Measured afterwards: all six session files on disk held
    the identical key, sha256 prefix 249340e7754c55bf.
  * the scheduled tasks overlap. The poller runs every 30 minutes, the monitor
    every hour, the watchdog daily; nothing stopped two of them connecting in
    the same second.

Separately each is survivable. Together, behind a SOCKS5 proxy whose exit
address can differ between connections, they revoked the key — and the signal
pipeline was dead for 37 days before anyone noticed, because the watchdog that
should have reported it was itself one of the copiers.

What to use instead
-------------------
Dodging the lock by copying the file is the thing that breaks. Wait for the real
client instead:

    from app.services.telethon_lock import telethon_session

    async with telethon_session("wef_backfill") as client:
        ...

The lock is advisory and process-wide, held in a lock file next to the session.
A stale lock from a killed process is broken after LOCK_TIMEOUT so a crash cannot
wedge the pipeline permanently.
"""

import asyncio
import contextlib
import logging
import os
import time

logger = logging.getLogger(__name__)

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Long enough for a full backfill pass, short enough that a crashed job does not
# block the next scheduled run for hours.
LOCK_TIMEOUT = 900          # seconds a held lock is believed
ACQUIRE_TIMEOUT = 120       # how long to wait for someone else to finish
POLL_INTERVAL = 2.0


def _lock_path(session: str) -> str:
    return os.path.join(BASE, f"{os.path.basename(session)}.lock")


def _read_lock(path: str) -> tuple[int, float] | None:
    try:
        with open(path, encoding="utf-8") as f:
            pid, ts = f.read().split(",", 1)
        return int(pid), float(ts)
    except (OSError, ValueError):
        return None


def _stale(path: str) -> bool:
    info = _read_lock(path)
    if info is None:
        return True
    pid, ts = info
    if time.time() - ts > LOCK_TIMEOUT:
        logger.warning(f"Telethon lock from pid {pid} is older than "
                       f"{LOCK_TIMEOUT}s — treating as stale")
        return True
    # A lock whose owner no longer exists is stale regardless of age.
    try:
        os.kill(pid, 0)
    except OSError:
        return True
    except Exception:
        pass
    return False


async def acquire(session: str, timeout: float = ACQUIRE_TIMEOUT) -> bool:
    """Take the lock for `session`, waiting up to `timeout` seconds."""
    path = _lock_path(session)
    deadline = time.monotonic() + timeout
    while True:
        try:
            # O_EXCL makes creation atomic: whoever wins creates the file.
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as f:
                f.write(f"{os.getpid()},{time.time()}")
            return True
        except FileExistsError:
            if _stale(path):
                with contextlib.suppress(OSError):
                    os.remove(path)
                continue
            if time.monotonic() >= deadline:
                holder = _read_lock(path)
                logger.error(
                    f"Telethon session {session} still held by pid "
                    f"{holder[0] if holder else '?'} after {timeout}s — giving up "
                    f"rather than connecting alongside it")
                return False
            await asyncio.sleep(POLL_INTERVAL)


def release(session: str) -> None:
    with contextlib.suppress(OSError):
        os.remove(_lock_path(session))


@contextlib.asynccontextmanager
async def telethon_session(session: str, *, timeout: float = ACQUIRE_TIMEOUT,
                           connect: bool = True):
    """Connected Telethon client holding the single-writer lock.

    Yields None when the lock cannot be taken, so the caller skips this run
    instead of connecting in parallel. Check for it:

        async with telethon_session("wef_backfill") as client:
            if client is None:
                return
    """
    from telethon import TelegramClient

    from app.config import settings

    got = await acquire(session, timeout)
    if not got:
        yield None
        return

    proxy = None
    if settings.socks5_host and settings.socks5_port:
        import socks
        proxy = (socks.SOCKS5, settings.socks5_host, int(settings.socks5_port),
                 True, settings.socks5_user or None, settings.socks5_pass or None)

    client = TelegramClient(os.path.join(BASE, session),
                            int(settings.telegram_api_id),
                            settings.telegram_api_hash, proxy=proxy)
    try:
        if connect:
            await client.connect()
        yield client
    finally:
        with contextlib.suppress(Exception):
            await client.disconnect()
        release(session)
