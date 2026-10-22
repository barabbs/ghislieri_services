"""Time helpers. The college runs on Europe/Rome time."""

import datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Rome")

# The academic year rolls over on this day (month, day): users and meal days are updated then.
ACADEMIC_YEAR_ROLLOVER = (8, 15)

WEEKDAYS = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")
MONTHS = (
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
)  # fmt: skip


def now() -> dt.datetime:
    return dt.datetime.now(TZ)


def today() -> dt.date:
    return now().date()


def academic_year(day: dt.date) -> int:
    """Start year of the academic year containing `day` (2025-09-01 -> 2025, 2026-03-01 -> 2025)."""
    return day.year if (day.month, day.day) >= ACADEMIC_YEAR_ROLLOVER else day.year - 1


def iso(moment: dt.datetime) -> str:
    return moment.isoformat(timespec="seconds")


def utc_iso(moment: dt.datetime) -> str:
    """Stored form of instants that are compared: UTC, so that text order is time order."""
    return iso(moment.astimezone(dt.UTC))


def parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text)


def day_label(day: dt.date, short: bool = False) -> str:
    """ "SAB 05 gen" (short) or "sabato 05 gennaio 2030"."""
    if short:
        return f"{WEEKDAYS[day.weekday()][:3].upper()} {day:%d} {MONTHS[day.month - 1][:3]}"
    return f"{WEEKDAYS[day.weekday()]} {day:%d} {MONTHS[day.month - 1]} {day.year}"
