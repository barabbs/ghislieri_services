import json
import logging
import sys

import pytest
from aiogram_dialog.test_tools.keyboard import InlineButtonTextLocator as Btn
from conftest import client, make_user

from ghislieri import printing, submissions, users
from ghislieri.bot.dialogs import dev, settings


def test_lp_args():
    opts = printing.PrintOptions(copies=2, sides="one-sided", number_up=4, pages=" 1, 3-5 ")
    assert printing.build_lp_args("/tmp/x.pdf", opts, "office") == [
        "lp", "-d", "office", "-n", "2", "-o", "sides=one-sided", "-o", "number-up=4",
        "-P", "1,3-5", "-t", "Ghislieri Bot", "--", "/tmp/x.pdf",
    ]  # fmt: skip
    assert "-P" not in printing.build_lp_args("x.pdf", printing.PrintOptions())
    for bad in (
        printing.PrintOptions(copies=0),
        printing.PrintOptions(copies=21),
        printing.PrintOptions(sides="one-sided; rm -rf /"),
        printing.PrintOptions(number_up=3),
        printing.PrintOptions(pages="1;id"),
    ):
        with pytest.raises(ValueError):
            printing.build_lp_args("x.pdf", bad)


@pytest.mark.parametrize(
    "text", ["", "1;id", "1 && reboot", "$(id)", "`id`", "1,", "-3", "1--2", "5-3", "0", "1\n2", "١", "1" * 101]
)
def test_page_list_rejects(text):
    with pytest.raises(ValueError):
        printing.parse_page_list(text)


async def test_print_dev_only_logs(settings, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    await printing.print_pdf(settings, tmp_path / "a.pdf", printing.PrintOptions())
    assert "Not printing" in caplog.text


async def test_eduroam_flow(dp, app, message_manager):
    make_user(app.conn, 99, users.ADMIN, name="Ada", surname="Admin")
    make_user(app.conn, 7, users.STUDENT, name="Luca", surname="Bianchi")
    c = client(dp, app, 7)
    await c.send("/start")
    await c.click(message_manager.last_message(), Btn("📩    Invia Contenuti"))
    await c.click(message_manager.last_message(), Btn("📶    Segnalazione Eduroam"))
    await c.click(message_manager.last_message(), Btn(submissions.DEFAULT_EDUROAM_REPORTS[0]))
    await c.send("Stanza <42>")
    await c.click(message_manager.last_message(), Btn("Nessuna nota"))
    assert "Stanza &lt;42&gt;" in message_manager.last_message().text
    await c.click(message_manager.last_message(), Btn("✔️"))
    assert "Grazie" in message_manager.last_message().text

    row = app.conn.execute("SELECT * FROM submissions").fetchone()
    assert (row["kind"], row["user_id"]) == ("eduroam_report", 7)
    assert json.loads(row["payload"]) == {
        "report": submissions.DEFAULT_EDUROAM_REPORTS[0],
        "place": "Stanza <42>",
        "note": "-",
    }
    await app.notifier.drain()
    [alert] = app.bot.sent(99)
    assert "Stanza &lt;42&gt;" in alert.text and "Luca Bianchi" in alert.text


async def test_feedback_stored(app):
    make_user(app.conn, 99, users.ADMIN)
    user = make_user(app.conn, 7, users.STUDENT)
    submissions.feedback(app, user, "<b>rotto</b>")
    row = app.conn.execute("SELECT kind, payload FROM submissions").fetchone()
    assert row["kind"] == "feedback" and json.loads(row["payload"]) == {"text": "<b>rotto</b>"}
    await app.notifier.drain()
    [alert] = app.bot.sent(99)
    assert "&lt;b&gt;rotto" in alert.text and alert.disable_notification


async def test_profile_edit(dp, app, message_manager):
    make_user(app.conn, 7)
    c = client(dp, app, 7)
    await c.send("/start")
    await c.click(message_manager.last_message(), Btn("🔧    Impostazioni"))
    await c.click(message_manager.last_message(), Btn("👤    Profilo"))
    await c.click(message_manager.last_message(), Btn("✏️ Email"))
    await c.send("not-an-email")
    assert "non valido" in message_manager.last_message().text
    await c.send(" luca@example.com ")
    assert "luca@example.com" in message_manager.last_message().text
    await c.click(message_manager.last_message(), Btn("✏️ Nome"))
    await c.send("<script>")
    assert "solo lettere" in message_manager.last_message().text
    await c.send("Gian Luca")
    u = users.get(app.conn, 7)
    assert (u.name, u.email) == ("Gian Luca", "luca@example.com")


def test_changelog_has_current_version():
    assert settings.changelog_notes(settings.release())


def test_error_detail_fits():
    try:
        raise RuntimeError("<" * 10_000)
    except RuntimeError:
        record = logging.makeLogRecord({"name": "x", "msg": "boom", "levelno": logging.ERROR})
        record.exc_info = sys.exc_info()
    text = dev.error_detail(record)
    assert len(text) < 4096 and "<<" not in text


async def test_print_flow(dp, app, message_manager, caplog, monkeypatch):
    from aiogram.types import Document, Message, Update

    async def download(file_id, destination, **kwargs):
        destination.write_bytes(b"%PDF-1.7 fake")

    monkeypatch.setattr(app.bot, "download", download, raising=False)
    make_user(app.conn, 7, users.STUDENT)
    c = client(dp, app, 7)
    await c.send("/start")
    await c.click(message_manager.last_message(), Btn("🖨    Stampa"))

    def doc(mime: str) -> Update:
        message = Message(
            message_id=c._new_message_id(), date=0, chat=c.chat, from_user=c.user,
            document=Document(file_id="F1", file_unique_id="U1", file_name="a.pdf", mime_type=mime, file_size=10),
        )  # fmt: skip
        return Update(update_id=c._new_update_id(), message=message)

    await dp.feed_update(app.bot, doc("image/png"))
    assert "formato" in message_manager.last_message().text
    await dp.feed_update(app.bot, doc("application/pdf"))
    await c.click(message_manager.last_message(), Btn("COPIE    1"))
    await c.click(message_manager.last_message(), Btn("3"))
    await c.click(message_manager.last_message(), Btn("PAGINE    Tutte"))
    await c.send("1;reboot")
    assert "non valido" in message_manager.last_message().text
    await c.send("2-4")
    await c.click(message_manager.last_message(), Btn("📑 Stampa"))
    assert "Pagine: <b>2-4</b>" in message_manager.last_message().text
    caplog.set_level(logging.INFO)
    await c.click(message_manager.last_message(), Btn("✔️"))
    assert "successo" in message_manager.last_message().text
    assert "'-n', '3'" in caplog.text and "'-P', '2-4'" in caplog.text
