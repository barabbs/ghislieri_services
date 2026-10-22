import datetime as dt
import json

import pytest
from aiogram_dialog.test_tools.keyboard import InlineButtonTextLocator as Btn
from conftest import client, make_user

from ghislieri import clock, meals, users

D = dt.date
SAT = D(2030, 1, 5)  # opens on Monday 2029-12-31


def at(day: dt.date, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(hour, minute), clock.TZ)


@pytest.fixture
def friday_noon(monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: at(D(2030, 1, 4), 12))


def test_academic_year_2025():
    days = meals.academic_year_days(2025)
    assert days[0] == D(2025, 9, 13) and days[-1] == D(2026, 7, 26)
    assert D(2025, 11, 1) in days and D(2025, 10, 31) not in days and D(2025, 11, 3) not in days  # Saturday
    assert D(2026, 6, 2) in days and D(2026, 6, 1) in days  # Tuesday: Monday ponte
    assert D(2026, 4, 25) in days and D(2026, 4, 24) not in days  # Saturday
    assert not [d for d in days if D(2025, 12, 23) <= d <= D(2026, 1, 6)]
    assert all(d.weekday() >= 5 for d in days if d not in (D(2026, 6, 1), D(2026, 6, 2)))
    # 2029-11-01 is a Thursday: Friday ponte.
    assert D(2029, 11, 2) in meals.academic_year_days(2029)


def test_opening_date():
    assert meals.opening_date(D(2026, 10, 24)) == D(2026, 10, 19)  # Saturday
    assert meals.opening_date(D(2026, 10, 25)) == D(2026, 10, 19)  # Sunday
    assert meals.opening_date(D(2026, 6, 1)) == D(2026, 5, 25)  # Monday ponte: the previous Monday
    assert meals.opening_date(D(2029, 11, 2)) == D(2029, 10, 29)  # Friday ponte


def test_create_academic_year_idempotent(conn):
    make_user(conn, 1, users.STUDENT)
    meals.add_day(conn, D(2025, 9, 13))
    meals.set_booking(conn, D(2025, 9, 13), "lunch", 1, True)
    added = meals.create_academic_year(conn, 2025, today=D(2025, 9, 1))
    assert len(added) == len(meals.academic_year_days(2025)) - 1
    assert meals.create_academic_year(conn, 2025, today=D(2025, 9, 1)) == []
    assert meals.answers(conn, 1, D(2025, 9, 13)) == {"lunch": True}
    # Days already past are not created.
    meals.remove_day(conn, D(2025, 9, 14))
    assert meals.create_academic_year(conn, 2025, today=D(2025, 9, 20)) == []


def test_toggle_window(conn):
    make_user(conn, 1, users.STUDENT)
    meals.add_day(conn, SAT)
    assert meals.toggle(conn, SAT, "lunch", 1, now=at(D(2029, 12, 31), 6, 59)) is None
    monday = at(D(2029, 12, 31), 7)
    assert [meals.toggle(conn, SAT, "lunch", 1, now=monday) for _ in range(3)] == [True, False, True]
    assert meals.toggle(conn, SAT, "brunch", 1, now=monday) is None
    assert meals.toggle(conn, SAT, "dinner", 1, now=at(SAT, 6, 59)) is True
    assert meals.toggle(conn, SAT, "dinner", 1, now=at(SAT, 7)) is None
    assert meals.answers(conn, 1, SAT) == {"lunch": True, "dinner": True}


async def test_reminder_and_booking_dialog(dp, app, message_manager, friday_noon):
    for uid in (1, 2, 3):
        make_user(app.conn, uid, users.STUDENT, surname=f"S{uid}")
    make_user(app.conn, 4, users.ALUMNUS)
    meals.add_day(app.conn, SAT)
    for meal in meals.MEALS:
        meals.set_booking(app.conn, SAT, meal, 1, False)
    meals.set_booking(app.conn, SAT, "lunch", 2, True)

    assert meals.reminder_recipients(app.conn, SAT) == [2, 3]
    await meals.remind(app)
    await app.notifier.drain()
    assert sorted(m.chat_id for m in app.bot.sent()) == [2, 3]

    c = client(dp, app, 3)
    await c.send("/start")
    await c.click(message_manager.last_message(), Btn(".*Mensa"))
    assert "SAB 05 gen · Pranzo ❔" in str(message_manager.last_message().reply_markup)
    await c.click(message_manager.last_message(), Btn(".*Pranzo.*"))
    await c.click(message_manager.last_message(), Btn(".*Cena.*"))
    await c.click(message_manager.last_message(), Btn(".*Cena.*"))
    assert meals.answers(app.conn, 3, SAT) == {"lunch": True, "dinner": False}
    assert "SAB 05 gen · Cena 🔴" in str(message_manager.last_message().reply_markup)
    states = dict(
        app.conn.execute(
            "SELECT d.user_id, d.state FROM deliveries d JOIN notifications n ON n.id = d.notification_id"
            " WHERE n.kind = 'meal_reminder'"
        ).fetchall()
    )
    assert states == {2: "sent", 3: "retracted"}


async def test_report(dp, app, message_manager, friday_noon):
    make_user(app.conn, 9, users.ADMIN, name="Ada", surname="Admin")
    make_user(app.conn, 3, users.STUDENT, name="Luca", surname="Bianchi")
    c = client(dp, app, 3)
    await c.send("/start")
    await c.click(message_manager.last_message(), Btn(".*Mensa"))
    assert "non ci sono prenotazioni aperte" in message_manager.last_message().text
    await c.click(message_manager.last_message(), Btn(".*Segnalazione"))
    await c.send("Pasta <fredda>")
    await c.click(message_manager.last_message(), Btn(".*Avanti"))
    assert "Pasta &lt;fredda&gt;" in message_manager.last_message().text
    await c.click(message_manager.last_message(), Btn(".*Invia"))
    assert "Grazie" in message_manager.last_message().text
    row = app.conn.execute("SELECT user_id, payload FROM submissions WHERE kind = 'meal_report'").fetchone()
    assert row["user_id"] == 3 and json.loads(row["payload"]) == {"text": "Pasta <fredda>", "photos": []}
    await app.notifier.drain()
    [alert] = app.bot.sent(9)
    assert "Luca Bianchi" in alert.text and "Pasta &lt;fredda&gt;" in alert.text


async def test_admin_remove_day(dp, app, message_manager, friday_noon):
    make_user(app.conn, 9, users.ADMIN, users.STUDENT, name="Ada", surname="Admin")
    meals.add_day(app.conn, SAT)
    meals.set_booking(app.conn, SAT, "lunch", 9, True)
    c = client(dp, app, 9)
    await c.send("/start")
    await c.click(message_manager.last_message(), Btn(".*Mensa"))
    await c.click(message_manager.last_message(), Btn(".*Gestione"))
    await c.click(message_manager.last_message(), Btn("SAB 05 gen · pranzo 1.*"))
    await c.click(message_manager.last_message(), Btn(".*Elimina giorno"))
    assert "1 prenotazioni" in message_manager.last_message().text
    await c.click(message_manager.last_message(), Btn(".*Sì, elimina"))
    assert meals.get_day(app.conn, SAT) is None
    assert app.conn.execute("SELECT count(*) FROM meal_bookings").fetchone()[0] == 0
    # A student without admin rights sees nothing in the admin window.
    make_user(app.conn, 5, users.STUDENT)
    s = client(dp, app, 5)
    await s.send("/start")
    await s.click(message_manager.last_message(), Btn(".*Mensa"))
    assert "Gestione" not in str(message_manager.last_message().reply_markup)


def test_recap_grouping(conn):
    make_user(conn, 1, users.STUDENT, name="Anna", surname="Verdi", gender="F")
    make_user(conn, 2, users.STUDENT, name="Marco", surname="Neri", gender="M")
    make_user(conn, 3, users.STUDENT, name="Sam", surname="O'Brien & Co", gender=None)
    make_user(conn, 4, users.ALUMNUS, gender="M")
    meals.add_day(conn, SAT)
    for uid, meal in ((1, "lunch"), (2, "lunch"), (2, "dinner"), (3, "dinner"), (4, "lunch")):
        meals.set_booking(conn, SAT, meal, uid, True)
    meals.set_booking(conn, SAT, "dinner", 1, False)
    recap = meals.build_recap(conn, SAT)
    assert list(recap.groups) == ["Maschi", "Femmine", "Genere non indicato"]
    assert recap.groups["Genere non indicato"] == [meals.RecapRow("O'Brien & Co", "Sam", (False, True))]
    assert recap.totals["lunch"] == {"Maschi": 1, "Femmine": 1, "Genere non indicato": 0, "total": 2}
    assert recap.totals["dinner"]["total"] == 2
    html = meals.recap_html(recap)
    assert "SABATO 05 GENNAIO 2030" in html and "O&#39;Brien &amp; Co" in html
    assert meals.recap_pdf(recap).startswith(b"%PDF")


async def test_reminder_button_opens_over_home(dp, app, message_manager, friday_noon):
    from aiogram.types import Message

    make_user(app.conn, 3, users.STUDENT)
    meals.add_day(app.conn, SAT)
    await meals.remind(app)
    await app.notifier.drain()
    [sent] = app.bot.sent(3)
    note = Message.model_validate(
        {"message_id": 1000, "date": 0, "chat": {"id": 3, "type": "private"}, "text": sent.text,
         "reply_markup": sent.reply_markup.model_dump()}
    )  # fmt: skip
    c = client(dp, app, 3)
    await c.click(note, Btn(".*Prenota ora.*"))
    [menu] = message_manager.sent_messages  # one live menu: the home one is not drawn
    assert "Tocca un pasto" in menu.text
    await c.click(message_manager.last_message(), Btn(".*Indietro"))  # back leads to the home menu
    assert "Collegio Ghislieri" in message_manager.last_message().text
