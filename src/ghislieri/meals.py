"""Canteen: bookable meal days, bookings, reminders, the daily recap and canteen reports."""

import asyncio
import datetime as dt
import logging
import sqlite3
from dataclasses import dataclass

import jinja2
from apscheduler.triggers.cron import CronTrigger

from . import clock, mail, submissions, users
from .app import App
from .db import transaction
from .notify import DISMISS, Button, esc

log = logging.getLogger(__name__)

MEALS = ("lunch", "dinner")
MEAL_NAMES = {"lunch": "Pranzo", "dinner": "Cena"}
# Booking for a day opens at this hour of its opening date and closes at this hour of the day itself.
CUTOFF = dt.time(7)

# Academic year calendar: weekends from SEASON_START to SEASON_END, plus these holidays (month, day)
# and their "ponte" days, minus the Christmas break.
SEASON_START, SEASON_END = (9, 8), (7, 31)
HOLIDAYS = ((11, 1), (4, 25), (6, 2))
CHRISTMAS_BREAK = ((12, 23), (1, 6))

REPRESENTATIVE = "representative"
MAX_REPORT_PHOTOS = 10
# State opened by the reminder button (bot.dialogs.meals.MealsSG.main; imported there would be circular).
BOOKING_STATE = "MealsSG:main"

# Calendar


def opening_date(day: dt.date) -> dt.date:
    """Monday of the week containing day - 2 (weekends open on their Monday, a Monday "ponte" a week before)."""
    d = day - dt.timedelta(days=2)
    return d - dt.timedelta(days=d.weekday())


def academic_year_days(start_year: int) -> list[dt.date]:
    """Meal days of the academic year starting in `start_year`."""
    first, last = dt.date(start_year, *SEASON_START), dt.date(start_year + 1, *SEASON_END)
    days = {first + dt.timedelta(days=i) for i in range((last - first).days + 1)}
    days = {d for d in days if d.weekday() >= 5}
    for month, mday in HOLIDAYS:
        holiday = dt.date(start_year if month >= SEASON_START[0] else start_year + 1, month, mday)
        days.add(holiday)
        if holiday.weekday() == 1:  # Tuesday: the Monday before is a "ponte"
            days.add(holiday - dt.timedelta(days=1))
        elif holiday.weekday() == 3:  # Thursday: the Friday after
            days.add(holiday + dt.timedelta(days=1))
    (bm, bd), (em, ed) = CHRISTMAS_BREAK
    break_start, break_end = dt.date(start_year, bm, bd), dt.date(start_year + 1, em, ed)
    return sorted(d for d in days if first <= d <= last and not break_start <= d <= break_end)


def add_day(conn: sqlite3.Connection, day: dt.date, opens_on: dt.date | None = None) -> bool:
    """Make `day` bookable. Returns False if it already was (nothing is changed then)."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO meal_days (day, opens_on) VALUES (?, ?)",
        (day.isoformat(), (opens_on or opening_date(day)).isoformat()),
    )
    return cur.rowcount == 1


def remove_day(conn: sqlite3.Connection, day: dt.date) -> None:
    """Delete the day with all its bookings."""
    conn.execute("DELETE FROM meal_days WHERE day = ?", (day.isoformat(),))


def create_academic_year(conn: sqlite3.Connection, start_year: int, today: dt.date) -> list[dt.date]:
    """Add the year's days after `today` that are missing. Returns the days added."""
    with transaction(conn):
        return [d for d in academic_year_days(start_year) if d > today and add_day(conn, d)]


# Bookings


def closes_at(day: dt.date) -> dt.datetime:
    return dt.datetime.combine(day, CUTOFF, clock.TZ)


def _window_date(now: dt.datetime) -> dt.date:
    """Day `d` is open iff opens_on <= _window_date(now) < d (the window turns at 07:00)."""
    return (now - dt.timedelta(hours=CUTOFF.hour)).date()


def set_booking(conn: sqlite3.Connection, day: dt.date, meal: str, user_id: int, attending: bool) -> None:
    conn.execute(
        "INSERT INTO meal_bookings (day, meal, user_id, attending) VALUES (?, ?, ?, ?)"
        " ON CONFLICT (day, meal, user_id) DO UPDATE SET attending = excluded.attending",
        (day.isoformat(), meal, user_id, int(attending)),
    )


def open_days(conn: sqlite3.Connection, now: dt.datetime | None = None) -> list[dt.date]:
    w = _window_date(now or clock.now()).isoformat()
    rows = conn.execute("SELECT day FROM meal_days WHERE opens_on <= ? AND day > ? ORDER BY day", (w, w))
    return [dt.date.fromisoformat(r["day"]) for r in rows]


def is_open(conn: sqlite3.Connection, day: dt.date, now: dt.datetime | None = None) -> bool:
    return day in open_days(conn, now)


def answers(conn: sqlite3.Connection, user_id: int, day: dt.date) -> dict[str, bool]:
    """The user's answers for `day`, by meal (unanswered meals are missing)."""
    rows = conn.execute(
        "SELECT meal, attending FROM meal_bookings WHERE user_id = ? AND day = ?", (user_id, day.isoformat())
    )
    return {r["meal"]: bool(r["attending"]) for r in rows}


def toggle(
    conn: sqlite3.Connection, day: dt.date, meal: str, user_id: int, now: dt.datetime | None = None
) -> bool | None:
    """Book an unanswered meal, or flip an answered one. Returns the new state, None if booking is closed."""
    if meal not in MEALS or not is_open(conn, day, now):
        return None
    attending = not answers(conn, user_id, day).get(meal, False)
    set_booking(conn, day, meal, user_id, attending)
    return attending


def answered_all(conn: sqlite3.Connection, user_id: int, day: dt.date) -> bool:
    return answers(conn, user_id, day).keys() >= set(MEALS)


def reminder_recipients(conn: sqlite3.Connection, day: dt.date) -> list[int]:
    """Active students who have not answered every meal of `day`."""
    done = {
        r["user_id"]
        for r in conn.execute(
            "SELECT user_id FROM meal_bookings WHERE day = ? GROUP BY user_id HAVING count(*) = ?",
            (day.isoformat(), len(MEALS)),
        )
    }
    return [uid for uid in users.user_ids(conn, (users.STUDENT,)) if uid not in done]


@dataclass(frozen=True)
class DaySummary:
    day: dt.date
    opens_on: dt.date
    booked: dict[str, int]  # meal -> number of students attending

    @property
    def total(self) -> int:
        return sum(self.booked.values())


def summaries(conn: sqlite3.Connection, first: dt.date, last: dt.date = dt.date.max) -> list[DaySummary]:
    rows = conn.execute(
        "SELECT d.day, d.opens_on,"
        " count(b.user_id) FILTER (WHERE b.meal = 'lunch' AND b.attending) AS lunch,"
        " count(b.user_id) FILTER (WHERE b.meal = 'dinner' AND b.attending) AS dinner"
        " FROM meal_days d LEFT JOIN meal_bookings b ON b.day = d.day"
        " WHERE d.day BETWEEN ? AND ? GROUP BY d.day ORDER BY d.day",
        (first.isoformat(), last.isoformat()),
    )
    return [
        DaySummary(dt.date.fromisoformat(r["day"]), dt.date.fromisoformat(r["opens_on"]), {m: r[m] for m in MEALS})
        for r in rows
    ]


def get_day(conn: sqlite3.Connection, day: dt.date) -> DaySummary | None:
    found = summaries(conn, day, day)
    return found[0] if found else None


# Recap

GENDER_GROUPS = (("M", "Maschi"), ("F", "Femmine"), (None, "Genere non indicato"))


@dataclass(frozen=True)
class RecapRow:
    surname: str
    name: str
    attending: tuple[bool, ...]  # per meal, in MEALS order


@dataclass(frozen=True)
class Recap:
    day: dt.date
    groups: dict[str, list[RecapRow]]  # label -> students; "non indicato" only when not empty
    totals: dict[str, dict[str, int]]  # meal -> label -> attending, plus "total"


def build_recap(conn: sqlite3.Connection, day: dt.date) -> Recap:
    booked = {
        (r["user_id"], r["meal"])
        for r in conn.execute("SELECT user_id, meal FROM meal_bookings WHERE day = ? AND attending", (day.isoformat(),))
    }
    students = users.list_users(conn, users.STUDENT)
    groups: dict[str, list[RecapRow]] = {}
    for gender, label in GENDER_GROUPS:
        rows = [
            RecapRow(u.surname, u.name, tuple((u.id, m) in booked for m in MEALS))
            for u in students
            if u.gender == gender or (gender is None and u.gender not in ("M", "F"))
        ]
        if rows or gender is not None:
            groups[label] = rows
    totals = {}
    for i, meal in enumerate(MEALS):
        totals[meal] = {label: sum(r.attending[i] for r in rows) for label, rows in groups.items()}
        totals[meal]["total"] = sum(totals[meal].values())
    return Recap(day, groups, totals)


_templates = jinja2.Environment(loader=jinja2.PackageLoader("ghislieri"), autoescape=True)


def recap_html(recap: Recap) -> str:
    columns = []  # (label, students): each group in two columns, four columns per row, as on the legacy sheet
    for label, rows in recap.groups.items():
        half = (len(rows) + 1) // 2
        columns += [(label, c) for c in (rows[:half], rows[half:]) if c]
    return _templates.get_template("meals_recap.html").render(
        title=clock.day_label(recap.day).upper(), columns=columns, recap=recap, meals=MEALS, meal_names=MEAL_NAMES
    )


def recap_pdf(recap: Recap) -> bytes:
    """Blocking: run in a thread."""
    import weasyprint  # slow to import, and needed once a day

    return weasyprint.HTML(string=recap_html(recap)).write_pdf()


async def render_recap(app: App, day: dt.date) -> tuple[str, bytes]:
    """(filename, PDF bytes) of the recap of `day`."""
    recap = build_recap(app.conn, day)
    pdf = await asyncio.wait_for(asyncio.to_thread(recap_pdf, recap), timeout=120)
    return f"Prenotazioni_{day.isoformat()}.pdf", pdf


async def send_recap(app: App, day: dt.date) -> None:
    """Email the recap of `day` to the porter's lodge and the admins. Raises on failure."""
    filename, pdf = await render_recap(app, day)
    await mail.send(
        app.settings,
        to=[*app.settings.meals_recap_to, *users.emails(app.conn, (users.ADMIN,))],
        subject=f"Prenotazione pasti {clock.day_label(day).upper()}",
        body=f"In allegato le prenotazioni dei pasti di {clock.day_label(day)}.",
        attachments=[(filename, pdf, "application/pdf")],
    )


# Reports ("segnalazioni")


async def submit_report(app: App, user: users.User, text: str, photos: list[str]) -> None:
    """Store a canteen report, notify admins and representatives, then email it.

    The report is saved and notified before the email, so an email failure (raised) loses nothing.
    """
    now = clock.now()
    sid = submissions.add(app.conn, "meal_report", user.id, {"text": text, "photos": photos})
    app.notifier.send_to_groups(
        (users.ADMIN, REPRESENTATIVE),
        "‼️    <b>Nuova Segnalazione Mensa</b>\n\n"
        f"<code>Data     </code>{now:%d/%m/%Y %H:%M}\n<code>Studente </code>{esc(user.full_name)}\n\n"
        f"<code>Report   </code><b>{esc(text)}</b>\n\n<code>N° Foto  </code><i>{len(photos)}</i>",
        kind="meal_report",
        ref=str(sid),
        buttons=[DISMISS],
    )
    attachments = await submissions.download_photos(app.bot, photos)
    await mail.send(
        app.settings,
        to=users.emails(app.conn, (users.ADMIN, REPRESENTATIVE)),
        subject=f"Segnalazione Mensa di {user.full_name}",
        body=f"Nuova segnalazione mensa di {user.full_name} in data {now:%d/%m/%Y}\n\n{text}\n\n"
        f"n° {len(photos)} foto allegate",
        attachments=attachments,
    )


# Jobs


async def remind(app: App) -> None:
    """Remind students who have not answered for tomorrow. The evening run replaces the noon one."""
    day = clock.today() + dt.timedelta(days=1)
    recipients = reminder_recipients(app.conn, day) if is_open(app.conn, day) else []
    if not recipients:
        return
    app.notifier.send(
        recipients,
        f"🍽❗️ <b>Prenotazione Pasti</b>\n\nHai prenotato per <i>{clock.day_label(day)}</i>?",
        kind="meal_reminder",
        ref=day.isoformat(),
        buttons=[Button("📆    Prenota ora!", BOOKING_STATE), DISMISS],
        expires_at=closes_at(day),
        replace=True,
    )


async def daily_recap(app: App) -> None:
    day = clock.today()
    if get_day(app.conn, day):
        await send_recap(app, day)
        log.info("Meal recap for %s sent", day)


async def yearly_calendar(app: App) -> None:
    today = clock.today()
    year = clock.academic_year(today)
    added = create_academic_year(app.conn, year, today)
    log.info("Meal calendar %d/%d: %d days added", year, year + 1, len(added))
    summary = (
        f"dal {clock.day_label(added[0])} al {clock.day_label(added[-1])}" if added else "erano già tutti presenti"
    )
    app.notifier.send_to_groups(
        (users.ADMIN,),
        f"🍽 Calendario mensa {year}/{year + 1}: {len(added)} giorni aggiunti ({summary}).",
        kind="meal_calendar",
        ref=str(year),
        silent=True,
        buttons=[DISMISS],
    )


def schedule(app: App) -> None:
    """Register this module's scheduled jobs."""
    month, day = clock.ACADEMIC_YEAR_ROLLOVER
    add = app.scheduler.add_job
    # Explicit time zone: a CronTrigger built by hand ignores the scheduler's and uses the host's.
    add(daily_recap, CronTrigger(hour=CUTOFF.hour, timezone=clock.TZ), args=[app])
    add(remind, CronTrigger(hour="12,19", timezone=clock.TZ), args=[app])
    add(yearly_calendar, CronTrigger(month=month, day=day, hour=1, timezone=clock.TZ), args=[app])
