"""College calendar: events, permissions, sync from the college website, iCalendar export and import."""

import asyncio
import datetime as dt
import html
import logging
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import aiohttp
import feedparser
import icalendar
from apscheduler.triggers.cron import CronTrigger

from . import clock, users
from .app import App

log = logging.getLogger(__name__)

CLASSES = {"cultural": "🏛  Culturale", "sport": "⚽️  Sport", "college": "🔥  Collegiale", "misc": "🗄️  Altro"}
# key: (label, symbol, scope). Holders of "calendar.<scope>" may use the category; the scope's first
# part is the class it belongs to ("cultural.gs" categories are for Ghislieri Scienza only).
CATEGORIES = {
    "gs": ("Ghislieri Scienza", "🔬", "cultural.gs"),
    "phg": ("Philosophicum Ghislieri", "🏛", "cultural.phg"),
    "bardi": ("Bardi Ghisleriani", "🎻", "cultural.bardi"),
    "conference": ("Conferenza", "🗣", "cultural"),
    "class": ("Corso", "📚", "cultural"),
    "meeting": ("Incontro", "👥", "cultural"),
    "concert": ("Concerto", "🎼", "cultural"),
    "sci_tech": ("Scienze e Tecnologie", "📐", "cultural"),
    "biomed": ("Scienze Biomediche", "🧬", "cultural"),
    "social_sci": ("Scienze Sociali", "⚖️", "cultural"),
    "human_sci": ("Scienze Umane", "🏺", "cultural"),
    "football": ("Calcio", "⚽️", "sport"),
    "basketball": ("Basket", "🏀", "sport"),
    "volleyball": ("Pallavolo", "🏐", "sport"),
    "othersport": ("Altri Sport", "🏃‍♂️", "sport"),
    "party": ("Party", "🎊", "college"),
    "happyhour": ("Aperitivo", "🍸", "college"),
    "goliardic": ("Goliardia", "👺", "college"),
    "formal": ("Festa Collegiale", "🥂", "misc"),
    "maintenance": ("Manutenzione", "🧰", "misc"),
    "other": ("Altro", "📌", "misc"),
}
# Holders may create events of every class and edit or delete any event (v0.5 group "admin").
CALENDAR_ADMIN = "calendar.admin"
# Classes only some groups may see (the others are visible to every active user).
RESTRICTED = {"college": (users.ADMIN, users.STUDENT)}
DEFAULT_SYMBOL, CANCELLED_SYMBOL = "📌", "❌"
DEFAULT_DURATION = dt.timedelta(hours=2)
MAX_TITLE, MAX_DESCRIPTION = 200, 2000

FEED_URL = "https://www.ghislieri.it/feed/?post_type=ajde_events"
# The feed lists 10 events per page, newest post first; earlier pages were imported by previous runs.
FEED_PAGES = 3
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=30)
# PRODID written by the v0.5 bot, whose times are Rome wall-clock times mislabelled as UTC.
LEGACY_PRODID = "Ghislieri Services Calendar"
ICS_FILE = "calendar.ics"


@dataclass(frozen=True)
class Event:
    id: int
    uid: str
    title: str
    description: str
    url: str | None
    start: dt.datetime  # Europe/Rome
    end: dt.datetime
    cls: str
    categories: tuple[str, ...]
    status: str
    creator_id: int | None
    source: str

    @property
    def cancelled(self) -> bool:
        return self.status == "cancelled"

    @property
    def symbol(self) -> str:
        if self.cancelled:
            return CANCELLED_SYMBOL
        return next((CATEGORIES[c][1] for c in self.categories if c in CATEGORIES), DEFAULT_SYMBOL)


def _from_row(row: sqlite3.Row) -> Event:
    return Event(
        id=row["id"],
        uid=row["uid"],
        title=row["title"],
        description=row["description"],
        url=row["url"],
        start=clock.parse(row["starts_at"]).astimezone(clock.TZ),
        end=clock.parse(row["ends_at"]).astimezone(clock.TZ),
        cls=row["class"],
        categories=tuple(c for c in row["categories"].split(",") if c),
        status=row["status"],
        creator_id=row["creator_id"],
        source=row["source"],
    )


# Permissions


def can_see(user: users.User, cls: str) -> bool:
    return cls not in RESTRICTED or any(user.has(g) for g in RESTRICTED[cls])


def _manages_calendar(user: users.User) -> bool:
    return user.is_admin or user.has(CALENDAR_ADMIN)


def classes_for(user: users.User) -> list[str]:
    """Classes the user may create events in."""
    return [c for c in CLASSES if _manages_calendar(user) or user.has(f"calendar.{c}")]


def categories_for(user: users.User, cls: str) -> list[str]:
    return [
        key
        for key, (_, _, scope) in CATEGORIES.items()
        if scope.split(".")[0] == cls and (_manages_calendar(user) or user.has(f"calendar.{scope}"))
    ]


def can_edit(user: users.User, event: Event) -> bool:
    """Admins edit every event; others only the ones they created, while they hold the class."""
    return _manages_calendar(user) or (event.creator_id == user.id and event.cls in classes_for(user))


# Queries and changes


def get(conn: sqlite3.Connection, event_id: int) -> Event | None:
    row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return _from_row(row) if row else None


def day_events(conn: sqlite3.Connection, day: dt.date, user: users.User) -> list[Event]:
    """Events overlapping `day` (Rome time) that `user` may see, by start time."""
    begin = dt.datetime.combine(day, dt.time(), clock.TZ)
    end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(), clock.TZ)
    rows = conn.execute(
        "SELECT * FROM events WHERE starts_at < ? AND ends_at > ? ORDER BY starts_at, id",
        (clock.utc_iso(end), clock.utc_iso(begin)),
    )
    return [e for e in map(_from_row, rows) if can_see(user, e.cls)]


def validate(title: str, start: dt.datetime | None, end: dt.datetime | None, categories: list[str]) -> str | None:
    """Italian error message for an incomplete event, or None."""
    if not title.strip():
        return "Titolo dell'evento mancante"
    if start is None or end is None:
        return "Orario dell'evento mancante"
    if end <= start:
        return "L'orario di fine è precedente a quello di inizio"
    if not categories:
        return "Aggiungi almeno una categoria"
    return None


def create(
    conn: sqlite3.Connection,
    *,
    title: str,
    description: str,
    url: str | None,
    start: dt.datetime,
    end: dt.datetime,
    cls: str,
    categories: list[str],
    creator_id: int | None,
) -> int:
    now = clock.iso(clock.now())
    cur = conn.execute(
        "INSERT INTO events (uid, title, description, url, starts_at, ends_at, class, categories, creator_id,"
        " source, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'bot', ?, ?)",
        (
            f"{cls}/{time.time_ns()}",  # v0.5 bot uids were "<class>/<unix time>"
            title.strip(),
            description.strip(),
            url,
            clock.utc_iso(start),
            clock.utc_iso(end),
            cls,
            ",".join(categories),
            creator_id,
            now,
            now,
        ),
    )
    log.info("Event %d created by %s: %s", cur.lastrowid, creator_id, title)
    return cur.lastrowid  # type: ignore[return-value]


def update(
    conn: sqlite3.Connection,
    event_id: int,
    *,
    title: str,
    description: str,
    url: str | None,
    start: dt.datetime,
    end: dt.datetime,
    categories: list[str],
    status: str,
) -> None:
    """Edits made in the bot win over the website: the event becomes "bot" and the sync leaves it alone."""
    conn.execute(
        "UPDATE events SET title = ?, description = ?, url = ?, starts_at = ?, ends_at = ?, categories = ?,"
        " status = ?, source = 'bot', updated_at = ? WHERE id = ?",
        (
            title.strip(),
            description.strip(),
            url,
            clock.utc_iso(start),
            clock.utc_iso(end),
            ",".join(categories),
            status,
            clock.iso(clock.now()),
            event_id,
        ),
    )
    log.info("Event %d updated: %s", event_id, title)


def delete(conn: sqlite3.Connection, event_id: int) -> None:
    conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    log.info("Event %d deleted", event_id)


def _upsert(conn: sqlite3.Connection, values: dict, source: str, overwrite: bool) -> bool:
    """Insert by uid. With `overwrite`, also refresh an existing event from the same source. True if changed."""
    now = clock.iso(clock.now())
    on_conflict = (
        "DO UPDATE SET title = excluded.title, description = excluded.description, url = excluded.url,"
        " starts_at = excluded.starts_at, ends_at = excluded.ends_at, status = excluded.status,"
        " updated_at = excluded.updated_at"
        " WHERE events.source = excluded.source AND (title, description, url, starts_at, ends_at, status)"
        " IS NOT (excluded.title, excluded.description, excluded.url, excluded.starts_at, excluded.ends_at,"
        " excluded.status)"
        if overwrite
        else "DO NOTHING"
    )
    cur = conn.execute(
        "INSERT INTO events (uid, title, description, url, starts_at, ends_at, class, categories, status, source,"
        " created_at, updated_at) VALUES (:uid, :title, :description, :url, :starts_at, :ends_at, :class,"
        f" :categories, :status, :source, :now, :now) ON CONFLICT (uid) {on_conflict}",
        {**values, "source": source, "now": now},
    )
    return cur.rowcount > 0


# Website sync. The feed (EventON plugin on WordPress) no longer carries the event dates, so each
# event page is fetched too: its event element has data-time="<start>-<end>" in Unix seconds.


@dataclass(frozen=True)
class FeedItem:
    uid: str
    title: str
    description: str
    url: str
    post_id: str


def parse_feed(data: bytes) -> list[FeedItem]:
    items = []
    for entry in feedparser.parse(data).entries:
        url = entry.get("link", "")
        post_id = re.search(r"[?&]p=(\d+)", entry.get("id", ""))
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        if not (url.startswith("https://") and post_id and slug and entry.get("title")):
            log.warning("Skipping feed entry without link, id or title: %r", entry.get("id"))
            continue
        summary = html.unescape(re.sub(r"<[^>]+>", "", entry.get("summary", "")))
        summary = re.sub(r"\s*\[…\]\s*$", "…", " ".join(summary.split()))
        items.append(FeedItem(f"cultural/{slug}", entry.title.strip(), summary, url, post_id.group(1)))
    return items


def parse_event_page(page: str, post_id: str) -> tuple[dt.datetime, dt.datetime, str] | None:
    """(start, end, status) from an event page, or None if the page has no dates for that event."""
    tag = re.search(rf'<[^>]*\bdata-event_id="{post_id}"[^>]*>', page)
    times = tag and re.search(r'\bdata-time="(\d+)-(\d+)"', tag.group(0))
    if not times:
        return None
    start, end = (dt.datetime.fromtimestamp(int(t), clock.TZ) for t in times.groups())
    if end <= start:
        end = start + DEFAULT_DURATION
    classes = re.search(r'\bclass="([^"]*)"', tag.group(0))  # type: ignore[union-attr]
    off = classes and {"cancelled", "postponed"} & set(classes.group(1).split())
    return start, end, "cancelled" if off else "confirmed"


def store_feed_event(conn: sqlite3.Connection, item: FeedItem, start: dt.datetime, end: dt.datetime, status: str):
    """Insert or refresh a website event. Never touches events created or edited in the bot."""
    values = {
        "uid": item.uid,
        "title": item.title[:MAX_TITLE],
        "description": item.description[:MAX_DESCRIPTION],
        "url": item.url,
        "starts_at": clock.utc_iso(start),
        "ends_at": clock.utc_iso(end),
        "class": "cultural",
        "categories": "conference",
        "status": status,
    }
    return _upsert(conn, values, "rss", overwrite=True)


async def _get(session: aiohttp.ClientSession, url: str) -> bytes:
    async with session.get(url, timeout=HTTP_TIMEOUT) as resp:
        resp.raise_for_status()
        return await resp.read()


async def sync(conn: sqlite3.Connection, pages: int = FEED_PAGES) -> tuple[int, int]:
    """Import the latest website events. Returns (changed, failed). Raises if the feed itself is unreachable."""
    changed = failed = 0
    async with aiohttp.ClientSession(headers={"User-Agent": "GhislieriBot/1.0"}) as session:
        for page in range(1, pages + 1):
            try:
                data = await _get(session, FEED_URL if page == 1 else f"{FEED_URL}&paged={page}")
            except aiohttp.ClientResponseError as err:
                if page > 1 and err.status == 404:  # WordPress answers 404 past the last page
                    break
                raise
            items = await asyncio.to_thread(parse_feed, data)
            if not items:
                break
            for item in items:
                try:
                    dates = parse_event_page((await _get(session, item.url)).decode(errors="replace"), item.post_id)
                    if dates is None:
                        raise ValueError("no data-time on the event page")
                except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                    log.warning("Calendar sync: skipping %s: %s", item.url, err)
                    failed += 1
                    continue
                changed += store_feed_event(conn, item, *dates)
    log.info("Calendar sync: %d events new or changed, %d failed", changed, failed)
    return changed, failed


syncing = False  # a sync is running (the admin's "update now" must not start a second one)


async def sync_job(app: App, notify_user: int | None = None) -> None:
    global syncing
    syncing = True
    try:
        changed, failed = await sync(app.conn)
    except Exception:
        if notify_user:
            app.notifier.send([notify_user], "⚠️ Aggiornamento del calendario dal sito non riuscito.", kind="calendar")
        raise
    finally:
        syncing = False
    write_ics(app.conn, app.settings.data_dir)
    if notify_user:
        text = f"🔄 Calendario aggiornato dal sito: {changed} eventi nuovi o modificati"
        app.notifier.send([notify_user], text + (f", {failed} non letti." if failed else "."), kind="calendar")


def schedule(app: App) -> None:
    app.scheduler.add_job(sync_job, CronTrigger(hour=3, minute=0, timezone=clock.TZ), args=[app], id="calendar_sync")


# iCalendar


def export_ics(conn: sqlite3.Connection) -> bytes:
    """The public calendar: every event except the restricted classes."""
    cal = icalendar.Calendar()
    cal.add("prodid", "-//Collegio Ghislieri//Calendario//IT")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Collegio Ghislieri")
    cal.add("x-wr-timezone", "Europe/Rome")
    for row in conn.execute("SELECT * FROM events ORDER BY starts_at, id"):
        e = _from_row(row)
        if e.cls in RESTRICTED:
            continue
        ev = icalendar.Event()
        ev.add("uid", e.uid)
        ev.add("summary", e.title)
        if e.description:
            ev.add("description", e.description)
        if e.url:
            ev.add("url", e.url)
        ev.add("dtstart", e.start.astimezone(dt.UTC))
        ev.add("dtend", e.end.astimezone(dt.UTC))
        ev.add("dtstamp", clock.parse(row["updated_at"]).astimezone(dt.UTC))
        ev.add("status", e.status.upper())
        if e.categories:
            ev.add("categories", list(e.categories))
        ev.add("x-ghislieri-class", e.cls)  # standard CLASS means access level, unknown values read as PRIVATE
        cal.add_component(ev)
    return cal.to_ical()


def write_ics(conn: sqlite3.Connection, data_dir: Path) -> None:
    path = data_dir / ICS_FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(export_ics(conn))
    os.replace(tmp, path)


def _local(value: dt.date, legacy: bool) -> dt.datetime:
    """An iCalendar date or time as Rome time. Legacy files stored Rome wall-clock times with a Z."""
    if not isinstance(value, dt.datetime):  # all-day
        return dt.datetime.combine(value, dt.time(), clock.TZ)
    if legacy or value.tzinfo is None:
        value = value.replace(tzinfo=clock.TZ)
    return value.astimezone(clock.TZ)


def import_ical(conn: sqlite3.Connection, path: Path | str) -> int:
    """One-off import of a v0.5 .ical file (or an export of ours). Existing uids are kept. Returns the new count."""
    cal = icalendar.Calendar.from_ical(Path(path).read_bytes())
    legacy = str(cal.get("prodid", "")) == LEGACY_PRODID
    added = 0
    for ev in cal.walk("VEVENT"):
        uid = str(ev.get("uid", ""))
        if not uid:
            continue
        start, end = (_local(v, legacy) for v in (ev.start, ev.end))
        if end <= start:
            end = start + DEFAULT_DURATION
        cls = str(ev.get("x-ghislieri-class") or ev.get("class") or "")
        cats = [str(c) for c in ev.categories if str(c) in CATEGORIES]
        values = {
            "uid": uid,
            "title": str(ev.get("summary", "")).strip()[:MAX_TITLE] or "Evento",
            "description": str(ev.get("description", "")).strip()[:MAX_DESCRIPTION],
            "url": str(ev["url"]) if ev.get("url") else None,
            "starts_at": clock.utc_iso(start),
            "ends_at": clock.utc_iso(end),
            "class": cls if cls in CLASSES else "cultural",  # v0.5 website events had no valid class
            "categories": ",".join(cats),
            "status": "cancelled" if str(ev.get("status", "")).upper() == "CANCELLED" else "confirmed",
        }
        # v0.5 bot events have uid "<class>/<unix time>"; the rest came from the website.
        source = "bot" if uid.rsplit("/", 1)[-1].isdigit() else "rss"
        added += _upsert(conn, values, source, overwrite=False)
    log.info("Imported %d events from %s", added, path)
    return added
