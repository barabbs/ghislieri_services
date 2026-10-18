from aiogram.types import InlineKeyboardButton, Message
from aiogram_dialog.test_tools.keyboard import InlineButtonTextLocator as Btn
from conftest import client, make_user

from ghislieri import clock, users
from ghislieri.bot.dialogs import admin
from ghislieri.notify import OpenCallback


class Crafted:
    """Locator returning a button with arbitrary callback data, as a modified client could send."""

    def __init__(self, data: str):
        self.data = data

    def find_button(self, message):
        return InlineKeyboardButton(text="x", callback_data=self.data)


async def open_admin(dp, app, message_manager, uid=99):
    c = client(dp, app, uid)
    await c.send("/start")
    await c.click(message_manager.last_message(), Btn("🔓    Admin"))
    return c


def last(message_manager):
    return message_manager.last_message()


async def test_student_detail_actions(dp, app, message_manager):
    make_user(app.conn, 99, users.ADMIN, name="Ada", surname="Admin")
    make_user(app.conn, 7, users.STUDENT, "legacy_group", name="Luca", surname="Bianchi")
    make_user(app.conn, 8, users.STUDENT, name="Anna", surname="Verdi")
    c = await open_admin(dp, app, message_manager)
    await c.click(last(message_manager), Btn("👥 Studenti"))
    await c.send("bian")  # search by surname
    assert Btn("Bianchi Luca").find_button(last(message_manager))
    assert not Btn("Verdi Anna").find_button(last(message_manager))
    await c.click(last(message_manager), Btn("Bianchi Luca"))

    await c.click(last(message_manager), Btn("👥 Gruppi"))
    await c.click(last(message_manager), Btn("⬜ representative"))
    await c.click(last(message_manager), Btn("✅ legacy_group"))  # unknown groups can be removed too
    assert users.get(app.conn, 7).groups == {users.STUDENT, "representative"}
    await c.click(last(message_manager), Btn("✔️ Fatto"))

    await c.click(last(message_manager), Btn("🚫 Disabilita"))
    assert users.get(app.conn, 7).status == "disabled"
    await c.click(last(message_manager), Btn("✅ Riabilita"))
    assert users.get(app.conn, 7).status == "active"

    await c.click(last(message_manager), Btn("❌ Elimina"))
    assert users.get(app.conn, 7) is not None  # only after confirming
    await c.click(last(message_manager), Btn("❌ Sì, elimina"))
    assert users.get(app.conn, 7) is None


async def test_compose_and_send(dp, app, message_manager):
    make_user(app.conn, 99, users.ADMIN, name="Ada", surname="Admin")
    make_user(app.conn, 1, users.STUDENT)
    make_user(app.conn, 2, "calendar.sport", surname="Neri")
    make_user(app.conn, 3, users.ALUMNUS, surname="Gialli")
    make_user(app.conn, 4, users.STUDENT, surname="Blu", status="disabled")
    c = await open_admin(dp, app, message_manager)
    await c.click(last(message_manager), Btn("📣 Notifiche"))
    await c.click(last(message_manager), Btn("✏️ Nuova notifica"))
    await c.send("Cena di <gala> stasera")
    await c.click(last(message_manager), Btn(r"👥 Destinatari \(0\)"))
    await c.click(last(message_manager), Btn("student"))
    await c.click(last(message_manager), Btn("calendar.sport"))
    await c.click(last(message_manager), Btn("✔️ Fatto"))
    await c.click(last(message_manager), Btn("🔔 Con suono"))
    await c.click(last(message_manager), Btn("24 h"))
    await c.click(last(message_manager), Btn("⬜ Apri il bot"))
    await c.click(last(message_manager), Btn("👀 Anteprima"))
    assert "Cena di &lt;gala&gt; stasera" in last(message_manager).text
    await c.click(last(message_manager), Btn("📤 Invia"))
    assert "inviata a 2 utenti" in last(message_manager).text

    await app.notifier.drain()
    sent = {m.chat_id: m for m in app.bot.sent() if m.chat_id != 99}
    assert set(sent) == {1, 2}
    assert all(m.disable_notification for m in sent.values())
    assert sent[1].text == "Cena di &lt;gala&gt; stasera"
    assert sent[1].reply_markup.inline_keyboard[0][0].callback_data == OpenCallback(state="HomeSG:main").pack()
    row = app.conn.execute("SELECT kind, created_at, expires_at FROM notifications").fetchone()
    hours = (clock.parse(row["expires_at"]) - clock.parse(row["created_at"])).total_seconds() / 3600
    assert (row["kind"], hours) == ("custom", 24)


async def test_update_announcement(dp, app, message_manager):
    make_user(app.conn, 99, users.ADMIN, name="Ada", surname="Admin")
    make_user(app.conn, 1, users.STUDENT)
    c = await open_admin(dp, app, message_manager)
    await c.click(last(message_manager), Btn("📣 Notifiche"))
    await c.click(last(message_manager), Btn("🆕 Annuncia aggiornamento"))
    await c.click(last(message_manager), Btn("📤 Invia"))
    await app.notifier.drain()
    [m] = app.bot.sent(1)
    assert "Nuovo Aggiornamento" in m.text and m.disable_notification


async def test_non_admin_cannot_open(dp, app, message_manager):
    make_user(app.conn, 5, users.STUDENT)
    c = client(dp, app, 5)
    # A crafted notification button: the core refuses it.
    note = Message.model_validate({"message_id": 1, "date": 0, "chat": {"id": 5, "type": "private"}, "text": "x"})
    await c.click(note, Crafted(OpenCallback(state=admin.AdminSG.main.state).pack()))
    assert message_manager.sent_messages == []
    # A crafted press of the hidden "Admin" button of the home menu: the dialog refuses to start.
    await c.send("/start")
    home = last(message_manager)
    intent = home.reply_markup.inline_keyboard[0][0].callback_data.split("\x1d")[0]
    await c.click(home, Crafted(f"{intent}\x1dadmin"))
    assert "Admin" not in last(message_manager).text


async def test_demoted_admin_cannot_approve(dp, app, message_manager):
    make_user(app.conn, 99, users.ADMIN, name="Ada", surname="Admin")
    make_user(app.conn, 7, name="Luca", surname="Bianchi", status="pending")
    c = await open_admin(dp, app, message_manager)
    await c.click(last(message_manager), Btn(r"📝 Registrazioni \(1\)"))
    await c.click(last(message_manager), Btn("Bianchi Luca"))
    users.remove_group(app.conn, 99, users.ADMIN)  # demoted while the menu is open
    await c.click(last(message_manager), Btn("✅ Approva come studente"))
    assert users.get(app.conn, 7).status == "pending"


async def test_group_chats_ignored(dp, app, message_manager):
    from aiogram_dialog.test_tools import BotClient

    make_user(app.conn, 5, users.STUDENT)
    await BotClient(dp, user_id=5, chat_id=-100, chat_type="group", bot=app.bot).send("/start")
    assert message_manager.sent_messages == []
