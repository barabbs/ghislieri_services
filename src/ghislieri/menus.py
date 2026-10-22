"""Each user's live menu message (the one aiogram-dialog edits in place).

The bot keeps one menu per chat: a new menu (/start) or a notification arriving while the menu
is idle deletes the old one, so chats don't fill up with stale menus.
"""

import datetime as dt
import sqlite3

from . import clock

# A menu untouched for this long is replaced by an incoming notification; a busier one is left alone.
IDLE = dt.timedelta(minutes=10)


def remember(conn: sqlite3.Connection, chat_id: int, message_id: int) -> None:
    conn.execute(
        "INSERT INTO menus (chat_id, message_id, shown_at) VALUES (?, ?, ?)"
        " ON CONFLICT (chat_id) DO UPDATE SET message_id = excluded.message_id, shown_at = excluded.shown_at",
        (chat_id, message_id, clock.utc_iso(clock.now())),
    )


def forget(conn: sqlite3.Connection, chat_id: int, idle: dt.timedelta | None = None) -> int | None:
    """Drop the chat's menu and return its message id; with `idle`, only if untouched that long."""
    sql, args = "DELETE FROM menus WHERE chat_id = ?", [chat_id]
    if idle is not None:
        sql += " AND shown_at <= ?"
        args.append(clock.utc_iso(clock.now() - idle))
    row = conn.execute(sql + " RETURNING message_id", args).fetchone()
    return row["message_id"] if row else None
