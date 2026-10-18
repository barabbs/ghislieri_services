import datetime as dt

from aiogram.methods import DeleteMessage
from conftest import make_user

from ghislieri import clock, users


async def test_send_replace_retract(app):
    for uid in (1, 2):
        make_user(app.conn, uid, users.STUDENT)
    n = app.notifier
    n.send_to_groups((users.STUDENT,), "first", kind="reminder", ref="2030-01-05")
    await n.drain()
    assert len(app.bot.sent()) == 2
    # A second reminder with the same kind/ref replaces the first one.
    n.send([1], "second", kind="reminder", ref="2030-01-05")
    await n.drain()
    deletes = [c for c in app.bot.calls if isinstance(c, DeleteMessage)]
    assert [d.chat_id for d in deletes] == [1]
    n.retract("reminder", "2030-01-05", user_id=2)
    await n.drain()
    rows = app.conn.execute("SELECT user_id, state FROM deliveries ORDER BY notification_id, user_id").fetchall()
    assert [tuple(r) for r in rows] == [(1, "retracted"), (2, "retracted"), (1, "sent")]


async def test_expired_not_sent(app):
    make_user(app.conn, 1, users.STUDENT)
    app.notifier.send([1], "late", kind="x", expires_at=clock.now() - dt.timedelta(minutes=1))
    await app.notifier.drain()
    assert app.bot.sent() == []


async def test_blocked_user(app):
    from aiogram.exceptions import TelegramForbiddenError
    from aiogram.methods import SendMessage
    from conftest import RecordingBot

    class BlockedBot(RecordingBot):
        async def __call__(self, method, request_timeout=None):
            if isinstance(method, SendMessage):
                raise TelegramForbiddenError(method=method, message="Forbidden: bot was blocked by the user")
            return await super().__call__(method, request_timeout)

    make_user(app.conn, 1, users.STUDENT)
    app.notifier.bot = BlockedBot()
    app.notifier.send([1], "hi", kind="x")
    await app.notifier.drain()
    assert users.get(app.conn, 1).status == "blocked"


async def test_retries_and_utc_expiry(app, monkeypatch):
    from aiogram.exceptions import TelegramNetworkError
    from aiogram.methods import SendMessage
    from conftest import RecordingBot

    from ghislieri import notify

    class FlakyBot(RecordingBot):
        attempts, down = 0, False

        async def __call__(self, method, request_timeout=None):
            self.attempts += 1
            if self.down or self.attempts % 2:  # every other request fails as if the network dropped
                raise TelegramNetworkError(method=method, message="timeout")
            return await super().__call__(method, request_timeout)

    monkeypatch.setattr(notify, "RETRY_DELAYS", (0,))
    app.notifier.bot = bot = FlakyBot()
    make_user(app.conn, 1, users.STUDENT)
    now = clock.now()
    app.notifier.send([1], "hi", kind="x", expires_at=now + dt.timedelta(hours=1))
    await app.notifier.drain()
    row = app.conn.execute("SELECT d.state, n.expires_at FROM deliveries d JOIN notifications n").fetchone()
    assert row["state"] == "sent" and row["expires_at"].endswith("+00:00")
    # Expiry compares UTC instants; the deletion goes through the worker and is retried too.
    monkeypatch.setattr(clock, "now", lambda: now + dt.timedelta(hours=2))
    app.notifier.expire()
    await app.notifier.drain()
    assert [type(c) for c in bot.calls] == [SendMessage, DeleteMessage]
    # A request that keeps failing marks the delivery as failed after the last retry.
    bot.down = True
    app.notifier.send([1], "down", kind="y")
    await app.notifier.drain()
    assert app.conn.execute("SELECT state FROM deliveries WHERE notification_id = 2").fetchone()[0] == "failed"
