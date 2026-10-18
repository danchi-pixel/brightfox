"""Local dates. Each family has its own time zone; the browser may send its own "today", which is only
trusted within a day of the family's date (so a changed clock can't dodge Foxy's daily limit)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

DEFAULT_TZ = "Europe/Ljubljana"


def family_tz(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def local_today(tz_name: str | None, override: str | None = None) -> date:
    here = datetime.now(family_tz(tz_name)).date()
    if override:
        try:
            d = date.fromisoformat(override)
        except ValueError:
            return here
        if abs((d - here).days) <= 1:
            return d
    return here


def iso(v: datetime | date | None) -> str | None:
    """ISO text for the API. Timestamps are stored in UTC, but SQLite hands them back without a zone, so add
    it (otherwise the browser would read them as local time). Plain dates stay plain."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return (v.astimezone(timezone.utc) if v.tzinfo else v.replace(tzinfo=timezone.utc)).isoformat()
    return v.isoformat()
