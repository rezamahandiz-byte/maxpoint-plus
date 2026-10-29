"""Best-effort online clock validation with a safe offline fallback.

The app never attempts to change Android/Windows system time. It keeps a
small in-app offset based on an HTTPS server Date header and falls back to the
local device clock whenever the network is unavailable.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
import time

from core import models

TEHRAN = ZoneInfo("Asia/Tehran")
OFFSET_KEY = "clock_sync_offset_seconds"
LAST_SYNC_KEY = "clock_sync_last_utc"
STATUS_KEY = "clock_sync_status"
TAMPER_FLAG_KEY = "clock_tamper_detected"  # [Ch12]

# [Ch12] Monotonic clock tracking for tampering detection
_last_monotonic: float | None = None
_last_wallclock: float | None = None


def _check_clock_jump() -> bool:
    """[Ch12] Detect if the wall clock jumped backward or drifted significantly.
    Uses time.monotonic() as reference — it cannot be set by the user.
    Returns True if tampering is suspected.
    """
    global _last_monotonic, _last_wallclock
    now_mono = time.monotonic()
    now_wall = time.time()

    if _last_monotonic is not None:
        mono_delta = now_mono - _last_monotonic
        wall_delta = now_wall - _last_wallclock
        # If wall clock went backward, or drift > 60 seconds
        if wall_delta < -1 or abs(wall_delta - mono_delta) > 60:
            _last_monotonic = now_mono
            _last_wallclock = now_wall
            models.set_setting(TAMPER_FLAG_KEY, "1")
            return True

    _last_monotonic = now_mono
    _last_wallclock = now_wall
    return False


def is_clock_tampered() -> bool:
    """[Ch12] Check if clock tampering was detected since last app start."""
    return models.get_setting(TAMPER_FLAG_KEY, "0") == "1"


def clear_tamper_flag() -> None:
    """[Ch12] Clear tamper flag after user acknowledges."""
    models.set_setting(TAMPER_FLAG_KEY, "0")


def _saved_offset() -> float:
    try:
        last = models.get_setting(LAST_SYNC_KEY, "") or ""
        synced = datetime.fromisoformat(last)
        if synced.tzinfo is None:
            synced = synced.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - synced.astimezone(timezone.utc)).total_seconds()
        if age > 36 * 3600 or age < -300:
            return 0.0
        return float(models.get_setting(OFFSET_KEY, "0") or 0)
    except Exception:
        return 0.0


def now_utc() -> datetime:
    return datetime.fromtimestamp(time.time() + _saved_offset(), tz=timezone.utc)


def now_local() -> datetime:
    return now_utc().astimezone(TEHRAN)


def sync_status() -> tuple[str, str]:
    last = models.get_setting(LAST_SYNC_KEY, "") or ""
    status = models.get_setting(STATUS_KEY, "offline") or "offline"
    if last:
        try:
            parsed = datetime.fromisoformat(last)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            local = parsed.astimezone(TEHRAN)
            return status, local.strftime("%H:%M")
        except Exception:
            pass
    return "offline", "—"


async def sync_once() -> bool:
    """Try HTTPS Date headers; return False quietly when offline."""
    try:
        import httpx
        urls = (
            "https://www.cloudflare.com/cdn-cgi/trace",
            "https://www.google.com/generate_204",
            "https://www.microsoft.com/",
        )
        async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
            for url in urls:
                try:
                    response = await client.get(url)
                    raw = response.headers.get("date")
                    if not raw:
                        continue
                    server = parsedate_to_datetime(raw)
                    if server.tzinfo is None:
                        server = server.replace(tzinfo=timezone.utc)
                    offset = server.timestamp() - time.time()
                    # Reject implausible differences; they usually mean a proxy's bad header.
                    if abs(offset) > 7 * 24 * 3600:
                        continue
                    models.set_setting(OFFSET_KEY, f"{offset:.3f}")
                    models.set_setting(LAST_SYNC_KEY, datetime.now(timezone.utc).isoformat(timespec="seconds"))
                    models.set_setting(STATUS_KEY, "online")
                    return True
                except Exception:
                    continue
    except Exception:
        pass
    models.set_setting(STATUS_KEY, "offline")
    return False


async def periodic_sync(ctx=None) -> None:
    """Sync immediately, then every 30 minutes; network errors are non-fatal.
    [Ch12] Also checks for clock tampering on each iteration."""
    while True:
        ok = False
        try:
            _check_clock_jump()  # [Ch12] tampering detection
            ok = await sync_once()
            if ok and ctx is not None and getattr(ctx, "current_tab", -1) == 0:
                try:
                    ctx.refresh()
                except Exception:
                    pass
        except Exception:
            ok = False
        # Retry quickly while offline so reconnecting is detected without a restart.
        await asyncio.sleep(30 * 60 if ok else 2 * 60)
