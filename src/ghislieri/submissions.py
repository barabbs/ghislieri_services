"""Things users send to the college: eduroam reports, photos for the socials, feedback on the bot."""

import html
import io
import json
import logging
import sqlite3

from . import clock, mail, users
from .app import App

log = logging.getLogger(__name__)

SOCIALS_REP = "socials_rep"
DEFAULT_EDUROAM_REPORTS = (
    "Il wi-fi non si connette",
    "Nessuna connessione ad Internet, ma al wi-fi sì",
)
MAX_PHOTOS = 20  # keeps the email well under Gmail's 25 MB


def _esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def add(conn: sqlite3.Connection, kind: str, user_id: int, payload: dict) -> int:
    cur = conn.execute(
        "INSERT INTO submissions (kind, user_id, payload, created_at) VALUES (?, ?, ?, ?)",
        (kind, user_id, json.dumps(payload, ensure_ascii=False), clock.iso(clock.now())),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def eduroam_report(app: App, user: users.User, report: str, place: str, note: str) -> int:
    sid = add(app.conn, "eduroam_report", user.id, {"report": report, "place": place, "note": note})
    app.notifier.send_to_groups(
        (users.ADMIN,),
        "📶    <b>Nuova Segnalazione Eduroam</b>\n\n"
        f"<code>Studente </code>{_esc(user.full_name)}\n\n"
        f"<code>Problema </code><b>{_esc(report)}</b>\n"
        f"<code>Luogo    </code><b>{_esc(place)}</b>\n"
        f"<code>Note     </code><b>{_esc(note)}</b>",
        kind="eduroam_report",
        ref=str(sid),
    )
    return sid


async def social_submission(app: App, user: users.User, description: str, photo_ids: list[str]) -> int:
    """Email the photos to the socials team, then store and notify. Raises if the email fails."""
    groups = (users.ADMIN, SOCIALS_REP)
    photos = []
    for i, file_id in enumerate(photo_ids, start=1):
        buf = await app.bot.download(file_id, destination=io.BytesIO())
        assert buf is not None
        photos.append((f"foto_{i}.jpg", buf.getvalue(), "image/jpeg"))
    date = clock.now().strftime("%d/%m/%Y %H:%M")
    await mail.send(
        app.settings,
        to=[u.email for u in users.list_users(app.conn) if u.email and any(u.has(g) for g in groups)],
        subject=f"Foto per Socials di {user.full_name}",
        body=f"Nuove foto per Socials inviate da {user.full_name} in data {date}\n\n"
        f"---- Descrizione:\n{description}\n\nn° {len(photos)} foto allegate",
        attachments=photos,
    )
    sid = add(app.conn, "social", user.id, {"description": description, "photos": photo_ids})
    app.notifier.send_to_groups(
        groups,
        "📣    <b>Nuove Foto per Socials</b>\n\n"
        f"<code>Studente </code>{_esc(user.full_name)}\n\n"
        f"<code>Descriz. </code><b>{_esc(description)}</b>\n\n"
        f"<code>N° Foto  </code><i>{len(photos)}</i> (inviate per email)",
        kind="social",
        ref=str(sid),
    )
    return sid


def feedback(app: App, user: users.User, text: str) -> int:
    sid = add(app.conn, "feedback", user.id, {"text": text})
    app.notifier.send_to_groups(
        (users.ADMIN,),
        f"💬    <b>Feedback sul bot</b> da {_esc(user.full_name)}\n\n{_esc(text)}",
        kind="feedback",
        ref=str(sid),
        silent=True,
    )
    return sid
