"""Time helpers. The college runs on Europe/Rome time."""

import datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Rome")

# The academic year rolls over on this day (month, day): users and meal days are updated then.
ACADEMIC_YEAR_ROLLOVER = (8, 15)


def now() -> dt.datetime:
    return dt.datetime.now(TZ)


def today() -> dt.date:
    return now().date()


def academic_year(day: dt.date) -> int:
    """Start year of the academic year containing `day` (2025-09-01 -> 2025, 2026-03-01 -> 2025)."""
    return day.year if (day.month, day.day) >= ACADEMIC_YEAR_ROLLOVER else day.year - 1


def iso(moment: dt.datetime) -> str:
    return moment.isoformat(timespec="seconds")


def parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text)
