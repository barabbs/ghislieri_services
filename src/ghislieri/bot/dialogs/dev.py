"""Developer tools and features not yet released."""

import datetime as dt
import logging

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Row, ScrollingGroup, Select, SwitchTo, Url
from aiogram_dialog.widgets.text import Const, Format

from ... import __version__, clock, log
from ..common import BACK, app_of, esc

ACCESS = "tester"

TEXT_LIMIT = 3800  # Telegram allows 4096 characters, leave room for the header


class DevSG(StatesGroup):
    main = State()
    services = State()
    supersega = State()
    errors = State()
    error = State()
    info = State()


def _time(record: logging.LogRecord) -> str:
    return dt.datetime.fromtimestamp(record.created, clock.TZ).strftime("%d/%m %H:%M:%S")


def error_detail(record: logging.LogRecord) -> str:
    """The formatted record with its traceback, escaped; the start is cut to fit one message."""
    text = logging.Formatter("%(message)s").format(record)
    while len(esc(text)) > TEXT_LIMIT:
        text = text[len(text) // 10 :]
    return f"<b>{_time(record)}</b>  <code>{esc(record.name)}</code>\n\n<pre>{esc(text)}</pre>"


async def errors_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    records = list(reversed(log.recent_errors))
    return {
        "errors": [(str(id(r)), f"{_time(r)} {r.name}: {r.getMessage()}"[:60]) for r in records],
        "count": len(records),
    }


async def error_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    wanted = dialog_manager.dialog_data.get("error_id")
    record = next((r for r in log.recent_errors if str(id(r)) == wanted), None)
    return {"detail": error_detail(record) if record else "Errore non più disponibile."}


async def on_error(query: CallbackQuery, widget, manager: DialogManager, item_id: str) -> None:
    manager.dialog_data["error_id"] = item_id
    await manager.switch_to(DevSG.error)


async def info_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    app = app_of(dialog_manager)
    statuses = app.conn.execute("SELECT status, count(*) AS n FROM users GROUP BY status ORDER BY status").fetchall()
    pending = app.conn.execute("SELECT count(*) FROM deliveries WHERE state = 'pending'").fetchone()[0]
    return {
        "version": __version__,
        "env": app.settings.env,
        "users": "\n".join(f"    {r['status']}: {r['n']}" for r in statuses) or "    nessuno",
        "pending": pending,
    }


TO_MAIN = SwitchTo(Const("↩️ Indietro"), id="to_main", state=DevSG.main)

dialog = Dialog(
    Window(
        Const("🧪    <b>Sviluppo</b>"),
        Row(
            SwitchTo(Const("📍    Prenota Servizi"), id="services", state=DevSG.services),
            SwitchTo(Const("⚽    SuperSega"), id="supersega", state=DevSG.supersega),
        ),
        Row(
            SwitchTo(Const("⚠️    Errori recenti"), id="errors", state=DevSG.errors),
            SwitchTo(Const("ℹ️    Info"), id="info", state=DevSG.info),
        ),
        BACK,
        state=DevSG.main,
    ),
    # Legacy menu, not released: kept for developers until the service is rebuilt.
    Window(
        Const("📆    <b>Prenota Servizi</b>"),
        Url(
            Const("⚽️    Campetto    🎾"),
            Const(
                "https://docs.google.com/spreadsheets/d/1RYa6c-XFP4OnfNmixJt9J0aVFMm2-F3debBzjVxFPHU/edit?usp=sharing"
            ),
        ),
        TO_MAIN,
        state=DevSG.services,
    ),
    # Legacy notification sent at the start of each SuperSega season; kept only as a reference text.
    Window(
        Const(
            "<i>Notifica legacy (v0.5), non viene inviata.</i>\n\n"
            "⚽⚽⚽    <b>SuperSega</b>    ⚽⚽⚽\n\n🎊    Inizia una <b>nuova stagione</b>!!!    🎊\n\n"
            "Per <u>tutti gli aggiornamenti</u> segui il canale <i>SuperSega Live</i>!"
        ),
        Url(Const("⚽️    SuperSega Live"), Const("https://t.me/+5f5d1aHWstBjMjY0")),
        TO_MAIN,
        state=DevSG.supersega,
    ),
    Window(
        Format("⚠️    <b>Errori recenti</b>: {count}"),
        ScrollingGroup(
            Select(
                Format("{item[1]}"),
                id="err",
                item_id_getter=lambda item: item[0],
                items="errors",
                on_click=on_error,
            ),
            id="errors_scroll",
            width=1,
            height=8,
            hide_on_single_page=True,
        ),
        TO_MAIN,
        state=DevSG.errors,
        getter=errors_getter,
    ),
    Window(
        Format("{detail}"),
        SwitchTo(Const("↩️ Elenco"), id="to_errors", state=DevSG.errors),
        state=DevSG.error,
        getter=error_getter,
    ),
    Window(
        Format(
            "ℹ️    <b>Info</b>\n\nVersione: <code>{version}</code>\nAmbiente: <code>{env}</code>\n\n"
            "Utenti:\n{users}\n\nNotifiche in coda: {pending}"
        ),
        TO_MAIN,
        state=DevSG.info,
        getter=info_getter,
    ),
)
