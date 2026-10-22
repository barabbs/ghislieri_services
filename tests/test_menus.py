"""One live menu per chat: a new menu or a notification on an idle menu deletes the old one."""

from aiogram.methods import DeleteMessage
from conftest import client, make_user

from ghislieri import users


def deleted(app) -> list[int]:
    return [c.message_id for c in app.bot.calls if isinstance(c, DeleteMessage)]


def menu_id(app, uid: int) -> int:
    return app.conn.execute("SELECT message_id FROM menus WHERE chat_id = ?", (uid,)).fetchone()["message_id"]


async def test_start_replaces_previous_menu(dp, app, message_manager):
    make_user(app.conn, 5, users.STUDENT)
    c = client(dp, app, 5)
    await c.send("/start")
    first = menu_id(app, 5)
    await c.send("/start")
    assert first in deleted(app)
    assert menu_id(app, 5) != first


async def test_notification_replaces_only_idle_menu(dp, app, message_manager):
    for uid in (5, 6):
        make_user(app.conn, uid, users.STUDENT)
        await client(dp, app, uid).send("/start")
    busy, idle = menu_id(app, 5), menu_id(app, 6)
    app.conn.execute("UPDATE menus SET shown_at = '2000-01-01T00:00:00+00:00' WHERE chat_id = 6")
    app.notifier.send([5, 6], "ciao", kind="custom")
    await app.notifier.drain()
    assert idle in deleted(app) and busy not in deleted(app)
    # The notification carries a button back to the menu.
    [note] = app.bot.sent(6)
    assert note.reply_markup.inline_keyboard[0][0].text == "🏠 Menu"
