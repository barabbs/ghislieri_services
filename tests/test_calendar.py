import datetime as dt

from aiogram_dialog.test_tools.keyboard import InlineButtonTextLocator as Btn
from conftest import client, make_user

from ghislieri import clock, db, events, users


def at(day: str, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime.combine(dt.date.fromisoformat(day), dt.time(hour, minute), clock.TZ)


def add(conn, title="Evento", start=None, end=None, cls="cultural", categories=("conference",), creator_id=None):
    start = start or at("2026-03-28", 21)
    return events.create(
        conn,
        title=title,
        description="",
        url=None,
        start=start,
        end=end or start + dt.timedelta(hours=2),
        cls=cls,
        categories=list(categories),
        creator_id=creator_id,
    )


def titles(conn, day, user):
    return [e.title for e in events.day_events(conn, dt.date.fromisoformat(day), user)]


def test_day_events(conn):
    student = make_user(conn, 1, users.STUDENT)
    alumnus = make_user(conn, 2, users.ALUMNUS)
    add(conn, "Late", at("2026-03-28", 23, 30), at("2026-03-29", 1))  # crosses midnight and the DST change
    add(conn, "Early", at("2026-03-29", 0, 15), at("2026-03-29", 3))  # 02:00-03:00 does not exist that night
    add(conn, "Party", at("2026-03-29", 22), cls="college", categories=("party",))
    add(conn, "Next day", at("2026-03-30", 0))
    assert titles(conn, "2026-03-28", student) == ["Late"]
    assert titles(conn, "2026-03-29", student) == ["Late", "Early", "Party"]
    assert titles(conn, "2026-03-29", alumnus) == ["Late", "Early"]  # college events are for students only
    early = events.day_events(conn, dt.date(2026, 3, 29), student)[1]
    assert early.start.utcoffset() == dt.timedelta(hours=1) and early.end.utcoffset() == dt.timedelta(hours=2)
    assert events.validate("x", at("2026-03-29", 10), at("2026-03-29", 9), ["conference"])  # end before start


def test_permissions(conn):
    admin = make_user(conn, 1, users.ADMIN)
    sport = make_user(conn, 2, "calendar.sport")
    gs = make_user(conn, 3, "calendar.cultural.gs")
    student = make_user(conn, 4, users.STUDENT)
    assert events.classes_for(admin) == list(events.CLASSES)
    assert events.classes_for(sport) == ["sport"]
    assert events.classes_for(gs) == ["cultural"]
    assert events.classes_for(student) == []
    assert "gs" in events.categories_for(gs, "cultural") and "gs" not in events.categories_for(admin, "sport")
    assert events.categories_for(sport, "sport") == ["football", "basketball", "volleyball", "othersport"]

    own = events.get(conn, add(conn, cls="sport", categories=("football",), creator_id=sport.id))
    other = events.get(conn, add(conn, cls="sport", categories=("football",), creator_id=gs.id))
    assert events.can_edit(sport, own) and not events.can_edit(sport, other)
    assert events.can_edit(admin, other) and not events.can_edit(student, own)
    users.remove_group(conn, sport.id, "calendar.sport")
    assert not events.can_edit(users.get(conn, sport.id), own)


FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><title>Events</title>
<item><title>Fisica &amp; poesia: &lt;una&gt; conferenza</title>
<link>https://www.ghislieri.it/events/fisica-e-poesia/</link>
<dc:creator><![CDATA[Redazione]]></dc:creator><pubDate>Thu, 15 Oct 2026 13:36:45 +0000</pubDate>
<guid isPermaLink="false">https://www.ghislieri.it/?post_type=ajde_events&#038;p=1234</guid>
<description><![CDATA[Gioved\xc3\xac 3 dicembre, alle ore 21, in Aula Magna [&#8230;]]]></description></item>
<item><title>Senza link</title><guid>x</guid></item>
</channel></rss>"""

PAGE = """<html><body><div class="related" data-event_id="999" data-time="1-2"></div>
<div id="event_1234_0" class="eventon_list_event evo_eventtop scheduled  event" data-event_id="1234"
 data-ri="0r" data-time="1796328000-1796338740" itemscope></div></body></html>"""


def test_feed_parsing_and_store(conn):
    [item] = events.parse_feed(FEED)
    assert item.uid == "cultural/fisica-e-poesia" and item.post_id == "1234"
    assert item.title == "Fisica & poesia: <una> conferenza"
    assert item.description == "Giovedì 3 dicembre, alle ore 21, in Aula Magna…"
    start, end, status = events.parse_event_page(PAGE, item.post_id)
    assert (start, end, status) == (at("2026-12-03", 21), at("2026-12-03", 23, 59), "confirmed")
    assert events.parse_event_page(PAGE.replace("scheduled", "cancelled"), "1234")[2] == "cancelled"
    assert events.parse_event_page("<html></html>", "1234") is None

    assert events.store_feed_event(conn, item, start, end, status)
    assert not events.store_feed_event(conn, item, start, end, status)  # idempotent
    assert events.store_feed_event(conn, item, start, end, "cancelled")  # the website changed it
    [e] = events.day_events(conn, start.date(), make_user(conn, 1, users.STUDENT))
    assert (e.source, e.status, e.cls, e.url) == ("rss", "cancelled", "cultural", item.url)
    # Once edited in the bot, the website no longer overwrites it.
    events.update(conn, e.id, title="Corretto", description="", url=None, start=start, end=end,
                  categories=["gs"], status="confirmed")  # fmt: skip
    assert not events.store_feed_event(conn, item, start, end, "cancelled")
    assert events.get(conn, e.id).title == "Corretto"


LEGACY = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:Ghislieri Services Calendar\r\n"
    "BEGIN:VEVENT\r\nUID:sport/1700000000\r\nSUMMARY:Torneo\r\nDTSTART:20230716T210000Z\r\nDURATION:PT2H\r\n"
    "CATEGORIES:football,unknown\r\nCLASS:sport\r\nSTATUS:TENTATIVE\r\nORGANIZER;CN=Someone:mailto:NONE\r\n"
    "END:VEVENT\r\n"
    "BEGIN:VEVENT\r\nUID:cultural/una-conferenza\r\nSUMMARY:Conferenza\r\nDESCRIPTION:Testo\r\n"
    "DTSTART:20230116T210000Z\r\nDTEND:20230116T200000Z\r\nCATEGORIES:conference\r\nCLASS:cultural\r\n"
    "STATUS:CANCELLED\r\nURL:https://example.org/c\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
)


def test_legacy_import_and_ics_round_trip(conn, tmp_path, settings):
    legacy = tmp_path / "calendar_2022-2023.ical"
    legacy.write_text(LEGACY)
    assert events.import_ical(conn, legacy) == 2
    assert events.import_ical(conn, legacy) == 0  # idempotent
    rows = {r["uid"]: dict(r) for r in conn.execute("SELECT * FROM events")}
    torneo, conf = rows["sport/1700000000"], rows["cultural/una-conferenza"]
    # v0.5 stored Rome wall-clock time with a Z: 21:00 in July is 19:00 UTC.
    assert (torneo["starts_at"], torneo["ends_at"]) == ("2023-07-16T19:00:00+00:00", "2023-07-16T21:00:00+00:00")
    assert (torneo["source"], torneo["categories"], torneo["status"]) == ("bot", "football", "confirmed")
    assert (conf["source"], conf["status"], conf["url"]) == ("rss", "cancelled", "https://example.org/c")
    assert conf["ends_at"] == "2023-01-16T22:00:00+00:00"  # end before start: two hours, as in v0.5

    add(conn, "Festa <privata>", cls="college", categories=("party",))
    events.write_ics(conn, settings.data_dir)
    exported = (settings.data_dir / events.ICS_FILE).read_bytes()
    assert b"privata" not in exported  # college events are not public
    copy = tmp_path / "copy.ics"
    copy.write_bytes(exported)
    other = db.connect(":memory:")
    assert events.import_ical(other, copy) == 2
    columns = "uid, title, description, url, starts_at, ends_at, class, categories, status, source"
    query = f"SELECT {columns} FROM events WHERE class <> 'college' ORDER BY uid"
    assert [tuple(r) for r in other.execute(query)] == [tuple(r) for r in conn.execute(query)]


async def test_create_event_flow(dp, app, message_manager):
    make_user(app.conn, 5, users.STUDENT, name="Lia", surname="Neri")
    plain = client(dp, app, 5)
    await plain.send("/start")
    await plain.click(message_manager.last_message(), Btn("🗓   Calendario"))
    assert "Nessun evento" in message_manager.last_message().text
    assert Btn("🆕    Nuovo evento").find_button(message_manager.last_message()) is None

    make_user(app.conn, 7, "calendar.sport")
    c = client(dp, app, 7)
    await c.send("/start")
    await c.click(message_manager.last_message(), Btn("🗓   Calendario"))
    await c.click(message_manager.last_message(), Btn("🆕    Nuovo evento"))
    keyboard = message_manager.last_message().reply_markup.inline_keyboard
    assert [row[0].text for row in keyboard] == [events.CLASSES["sport"], "↩️ Indietro"]  # only their class
    await c.click(message_manager.last_message(), Btn(events.CLASSES["sport"]))
    await c.click(message_manager.last_message(), Btn("✔️ Avanti"))  # no category yet: refused
    assert "categorie" in message_manager.last_message().text
    await c.click(message_manager.last_message(), Btn(".*Calcio.*"))
    await c.click(message_manager.last_message(), Btn("✔️ Avanti"))
    await c.send("Torneo <di> calcio")
    await c.click(message_manager.last_message(), Btn("⏭ Nessuna descrizione"))
    today = clock.today()
    day = today.replace(day=2 if today.day == 1 else 1)
    await c.click(message_manager.last_message(), Btn(f"{day:%d}"))
    await c.send("25:00")
    assert "Scrivi l'orario come" in message_manager.last_message().text  # bad time: asked again
    await c.send("21.30")
    recap = message_manager.last_message().text
    assert "Torneo &lt;di&gt; calcio" in recap and "⚽️" in recap and "21:30" in recap
    await c.click(message_manager.last_message(), Btn("➕ Aggiungi"))

    [e] = events.day_events(app.conn, day, users.get(app.conn, 7))
    assert (e.title, e.cls, e.categories, e.creator_id, e.source) == (
        "Torneo <di> calcio", "sport", ("football",), 7, "bot"
    )  # fmt: skip
    assert (e.start, e.end) == (at(day.isoformat(), 21, 30), at(day.isoformat(), 23, 30))
    assert "Torneo &lt;di&gt; calcio" in message_manager.last_message().text  # the event's page
    assert Btn("✏️    Modifica").find_button(message_manager.last_message())
    assert b"Torneo <di> calcio" in (app.settings.data_dir / events.ICS_FILE).read_bytes()

    # The creator cancels the event, then deletes it.
    await c.click(message_manager.last_message(), Btn("✏️    Modifica"))
    await c.click(message_manager.last_message(), Btn("🚦 Stato: .*"))
    await c.click(message_manager.last_message(), Btn("✅ Salva"))
    assert events.get(app.conn, e.id).cancelled and "CANCELLATO" in message_manager.last_message().text
    await c.click(message_manager.last_message(), Btn("🗑️    Elimina"))
    await c.click(message_manager.last_message(), Btn("✔️"))
    assert events.get(app.conn, e.id) is None
