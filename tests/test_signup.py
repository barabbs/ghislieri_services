from aiogram_dialog.test_tools.keyboard import InlineButtonTextLocator as Btn

from conftest import client, make_user
from ghislieri import users


async def test_signup_and_approval(dp, app, message_manager):
    make_user(app.conn, 99, users.ADMIN, name="Ada", surname="Admin")
    new = client(dp, app, 7)
    await new.send("/start")
    assert "cognome" in message_manager.last_message().text
    await new.send("Bianchi")
    await new.send("  Luca  ")
    await new.click(message_manager.last_message(), Btn("Maschile"))
    assert "Bianchi" in message_manager.last_message().text
    await new.click(message_manager.last_message(), Btn("✅ Conferma"))
    assert "inviata" in message_manager.last_message().text
    u = users.get(app.conn, 7)
    assert (u.name, u.surname, u.gender, u.status) == ("Luca", "Bianchi", "M", "pending")

    await app.notifier.drain()
    [alert] = app.bot.sent(99)
    assert "Luca Bianchi" in alert.text

    # The admin uses the bot normally, then opens the registrations from the notification button.
    admin = client(dp, app, 99)
    await admin.send("/start")
    assert "Collegio Ghislieri" in message_manager.last_message().text
    from aiogram.types import Message

    note = Message.model_validate(
        {"message_id": 1000, "date": 0, "chat": {"id": 99, "type": "private"}, "text": alert.text,
         "reply_markup": alert.reply_markup.model_dump()}
    )
    await admin.click(note, Btn("👀 Vedi registrazioni"))
    await admin.click(message_manager.last_message(), Btn("Bianchi Luca"))
    await admin.click(message_manager.last_message(), Btn("✅ Approva come studente"))
    u = users.get(app.conn, 7)
    assert u.status == "active" and u.groups == {users.STUDENT}

    await app.notifier.drain()
    assert any("approvata" in m.text for m in app.bot.sent(7))
    # The admin's registration alert was retracted.
    state = app.conn.execute(
        "SELECT d.state FROM deliveries d JOIN notifications n ON n.id = d.notification_id"
        " WHERE n.kind = 'registration' AND d.user_id = 99"
    ).fetchone()["state"]
    assert state == "retracted"


async def test_invalid_name_rejected(dp, app, message_manager):
    c = client(dp, app, 8)
    await c.send("/start")
    await c.send("x" * 80)
    assert "60 caratteri" in message_manager.last_message().text
    assert users.get(app.conn, 8) is None


async def test_pending_user_sees_waiting(dp, app, message_manager):
    make_user(app.conn, 5, status="pending")
    c = client(dp, app, 5)
    await c.send("/start")
    assert "inviata" in message_manager.last_message().text
