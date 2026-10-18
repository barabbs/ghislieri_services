"""Notifications: standalone bot messages sent to many users, tracked so they can be retracted.

A notification never replaces the user's menu message. It is a separate message, optionally with
buttons that open a dialog. Each (notification, user) pair is a row in `deliveries`, so sending
survives restarts and a message can be deleted later (when it expires, or when it no longer
applies, e.g. the user has already booked their meals).

All sending goes through one background worker, rate-limited well below Telegram's ~30 msg/s,
so a broadcast never stalls the handlers that answer users.
"""

import asyncio
import contextlib
import datetime as dt
import json
import logging
import sqlite3
from dataclasses import asdict, dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from . import clock, users

log = logging.getLogger(__name__)

SEND_INTERVAL = 1 / 20  # seconds between messages


class OpenCallback(CallbackData, prefix="open", sep="|"):
    """Button on a notification. `state` is a dialog state ("MealsSG:days"); empty means dismiss."""

    state: str


@dataclass(frozen=True)
class Button:
    text: str
    state: str = ""  # dialog state to open, e.g. MealsSG.days.state
    url: str | None = None


DISMISS = Button("✖️ Chiudi")


def _keyboard(buttons: list[Button]) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    rows = [
        [
            InlineKeyboardButton(text=b.text, url=b.url)
            if b.url
            else InlineKeyboardButton(text=b.text, callback_data=OpenCallback(state=b.state).pack())
        ]
        for b in buttons
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


class Notifier:
    def __init__(self, bot: Bot, conn: sqlite3.Connection):
        self.bot, self.conn = bot, conn
        self._queue: asyncio.Queue[tuple[int, int]] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._deletions: set[asyncio.Task] = set()

    # Lifecycle

    def start(self) -> None:
        """Start the worker and resume deliveries left pending by a previous run."""
        for row in self.conn.execute("SELECT notification_id, user_id FROM deliveries WHERE state = 'pending'"):
            self._queue.put_nowait((row["notification_id"], row["user_id"]))
        self._worker = asyncio.create_task(self._run(), name="notifier")

    async def stop(self) -> None:
        if self._worker:
            self._worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker

    async def drain(self) -> None:
        """Wait until everything queued so far is sent (used by tests and admin tools)."""
        await self._queue.join()

    # API

    def send(
        self,
        user_ids: list[int],
        text: str,
        *,
        kind: str,
        ref: str | None = None,
        buttons: list[Button] | None = None,
        silent: bool = False,
        expires_at: dt.datetime | None = None,
        replace: bool = True,
    ) -> int:
        """Queue `text` (Telegram HTML) for `user_ids`. Returns the notification id.

        With `replace`, earlier notifications with the same kind and ref are retracted first for
        these users, so a second reminder replaces the first instead of piling up.
        """
        if replace:
            for uid in user_ids:
                self.retract(kind, ref, uid)
        cur = self.conn.execute(
            "INSERT INTO notifications (kind, ref, text, buttons, silent, created_at, expires_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                kind,
                ref,
                text,
                json.dumps([asdict(b) for b in buttons or []]),
                int(silent),
                clock.iso(clock.now()),
                clock.iso(expires_at) if expires_at else None,
            ),
        )
        nid = cur.lastrowid
        assert nid is not None
        self.conn.executemany(
            "INSERT OR IGNORE INTO deliveries (notification_id, user_id) VALUES (?, ?)",
            [(nid, uid) for uid in dict.fromkeys(user_ids)],
        )
        for uid in dict.fromkeys(user_ids):
            self._queue.put_nowait((nid, uid))
        log.info("Notification %s (%s %s) queued for %d users", nid, kind, ref, len(user_ids))
        return nid

    def send_to_groups(self, groups: tuple[str, ...], text: str, **kwargs) -> int:
        return self.send(users.user_ids(self.conn, groups), text, **kwargs)

    def retract(self, kind: str, ref: str | None, user_id: int | None = None) -> None:
        """Withdraw notifications of `kind`/`ref` (for one user or all). Sent messages are deleted."""
        sql = (
            "SELECT d.notification_id, d.user_id, d.message_id, d.state FROM deliveries d"
            " JOIN notifications n ON n.id = d.notification_id"
            " WHERE n.kind = ? AND n.ref IS ? AND d.state IN ('pending', 'sent')"
        )
        args: list = [kind, ref]
        if user_id is not None:
            sql += " AND d.user_id = ?"
            args.append(user_id)
        for row in self.conn.execute(sql, args).fetchall():
            self._retract_row(row)

    def retract_delivery(self, user_id: int, message_id: int) -> None:
        """Mark the delivery behind a notification message as handled (the user opened or closed it)."""
        self.conn.execute(
            "UPDATE deliveries SET state = 'retracted' WHERE user_id = ? AND message_id = ?",
            (user_id, message_id),
        )

    def expire(self) -> None:
        """Retract every notification past its expiry time. Run periodically."""
        rows = self.conn.execute(
            "SELECT d.notification_id, d.user_id, d.message_id, d.state FROM deliveries d"
            " JOIN notifications n ON n.id = d.notification_id"
            " WHERE n.expires_at IS NOT NULL AND n.expires_at <= ? AND d.state IN ('pending', 'sent')",
            (clock.iso(clock.now()),),
        ).fetchall()
        for row in rows:
            self._retract_row(row)

    # Internals

    def _retract_row(self, row: sqlite3.Row) -> None:
        self.conn.execute(
            "UPDATE deliveries SET state = 'retracted' WHERE notification_id = ? AND user_id = ?",
            (row["notification_id"], row["user_id"]),
        )
        if row["state"] == "sent" and row["message_id"]:
            task = asyncio.create_task(self._delete(row["user_id"], row["message_id"]))
            self._deletions.add(task)
            task.add_done_callback(self._deletions.discard)

    async def _delete(self, chat_id: int, message_id: int) -> None:
        # Messages older than 48 h cannot be deleted; nothing to do about it.
        with contextlib.suppress(TelegramBadRequest, TelegramForbiddenError):
            await self.bot.delete_message(chat_id=chat_id, message_id=message_id)

    async def _run(self) -> None:
        while True:
            nid, uid = await self._queue.get()
            try:
                await self._deliver(nid, uid)
            except Exception:
                log.exception("Delivering notification %s to %s failed", nid, uid)
                self._set(nid, uid, "failed")
            finally:
                self._queue.task_done()
            await asyncio.sleep(SEND_INTERVAL)

    def _set(self, nid: int, uid: int, state: str, message_id: int | None = None) -> None:
        self.conn.execute(
            "UPDATE deliveries SET state = ?, message_id = coalesce(?, message_id)"
            " WHERE notification_id = ? AND user_id = ?",
            (state, message_id, nid, uid),
        )

    async def _deliver(self, nid: int, uid: int) -> None:
        row = self.conn.execute(
            "SELECT n.*, d.state FROM notifications n JOIN deliveries d ON d.notification_id = n.id"
            " WHERE n.id = ? AND d.user_id = ?",
            (nid, uid),
        ).fetchone()
        if row is None or row["state"] != "pending":
            return  # retracted meanwhile
        if row["expires_at"] and clock.parse(row["expires_at"]) <= clock.now():
            self._set(nid, uid, "retracted")
            return
        markup = _keyboard([Button(**b) for b in json.loads(row["buttons"] or "[]")])
        while True:
            try:
                msg = await self.bot.send_message(
                    chat_id=uid,
                    text=row["text"],
                    reply_markup=markup,
                    disable_notification=bool(row["silent"]),
                )
                break
            except TelegramRetryAfter as e:
                log.warning("Rate limited by Telegram, waiting %s s", e.retry_after)
                await asyncio.sleep(e.retry_after)
            except TelegramForbiddenError:
                log.info("User %s blocked the bot; marking as blocked", uid)
                users.mark_blocked(self.conn, uid)
                self._set(nid, uid, "failed")
                return
        # The notification may have been retracted while we were sending.
        state = self.conn.execute(
            "SELECT state FROM deliveries WHERE notification_id = ? AND user_id = ?", (nid, uid)
        ).fetchone()["state"]
        if state == "retracted":
            await self._delete(uid, msg.message_id)
        else:
            self._set(nid, uid, "sent", msg.message_id)
