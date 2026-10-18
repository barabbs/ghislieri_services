"""Remote printing: the user sends a PDF, picks the options and prints it."""

import logging
import tempfile
from pathlib import Path

from aiogram.enums import ContentType
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import ManagedTextInput, MessageInput, TextInput
from aiogram_dialog.widgets.kbd import Button, Group, Row, Select, SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from ... import printing
from ..common import BACK, ERROR, HOME, app_of, esc, input_error, tidy_input

log = logging.getLogger(__name__)

ACCESS = "student"


class PrintingSG(StatesGroup):
    main = State()
    options = State()
    copies = State()
    pages = State()
    sides = State()
    number_up = State()
    confirm = State()
    done = State()


def _options(manager: DialogManager) -> printing.PrintOptions:
    return printing.PrintOptions(**manager.dialog_data.get("options", {}))


def _set(manager: DialogManager, **values) -> None:
    manager.dialog_data["options"] = {**manager.dialog_data.get("options", {}), **values}


async def on_document(message: Message, widget: MessageInput, manager: DialogManager) -> None:
    await tidy_input(message, manager)
    doc = message.document
    assert doc is not None
    if doc.mime_type != "application/pdf":
        manager.dialog_data["error"] = "⚠️ Il file deve essere in formato <u>.pdf</u>."
    elif (doc.file_size or 0) > printing.MAX_FILE_SIZE:
        manager.dialog_data["error"] = "⚠️ Il file è troppo grande (massimo 20 MB)."
    else:
        manager.dialog_data.update(file_id=doc.file_id, file_name=doc.file_name or "documento.pdf", options={})
        await manager.switch_to(PrintingSG.options)


async def on_copies(event: Message | CallbackQuery, widget, manager: DialogManager, value: int) -> None:
    """From a number button or typed in."""
    if isinstance(event, Message):
        await tidy_input(event, manager)
    _set(manager, copies=value)
    await manager.switch_to(PrintingSG.options)


def _copies(text: str) -> int:
    value = int(text)
    if not 1 <= value <= printing.MAX_COPIES:
        raise ValueError(text)
    return value


async def on_pages(message: Message, widget: ManagedTextInput, manager: DialogManager, value: str) -> None:
    await tidy_input(message, manager)
    _set(manager, pages=value)
    await manager.switch_to(PrintingSG.options)


async def on_all_pages(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    _set(manager, pages=None)
    await manager.switch_to(PrintingSG.options)


async def on_sides(query: CallbackQuery, widget, manager: DialogManager, item_id: str) -> None:
    _set(manager, sides=item_id)
    await manager.switch_to(PrintingSG.options)


async def on_number_up(query: CallbackQuery, widget, manager: DialogManager, item_id: int) -> None:
    _set(manager, number_up=item_id)
    await manager.switch_to(PrintingSG.options)


async def on_print(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    app, data = app_of(manager), manager.dialog_data
    await query.answer("🖨 Stampa in corso…")
    try:
        with tempfile.TemporaryDirectory(prefix="ghislieri-print-") as tmp:
            path = Path(tmp) / "job.pdf"
            await app.bot.download(data["file_id"], destination=path, timeout=60)
            if not printing.is_pdf(path):
                raise printing.PrintError("il file non è un PDF valido")
            await printing.print_pdf(app.settings, path, _options(manager))
    except printing.PrintError as e:
        log.warning("Printing failed: %s", e)
        data["result"] = f"❌    Errore nella stampa del file\n\n⚠️    <b>{esc(e)}</b>"
    except Exception:
        log.exception("Printing failed")
        data["result"] = "❌    Errore nella stampa del file. Riprova più tardi."
    else:
        data["result"] = "✅    File stampato con <b>successo</b>!"
    await manager.switch_to(PrintingSG.done)


async def getter(dialog_manager: DialogManager, **kwargs) -> dict:
    data, opts = dialog_manager.dialog_data, _options(dialog_manager)
    return {
        "error": data.pop("error", ""),
        "file_name": esc(data.get("file_name", "")),
        "copies": opts.copies,
        "pages": opts.pages or "Tutte",
        "sides": printing.SIDES[opts.sides],
        "number_up": opts.number_up,
        "sides_list": list(printing.SIDES.items()),
        "number_up_list": printing.NUMBER_UP,
        "result": data.get("result", ""),
    }


TO_OPTIONS = SwitchTo(Const("↩️ Indietro"), id="to_options", state=PrintingSG.options)

dialog = Dialog(
    Window(
        Const("📑    Invia il <b>file</b> in formato <u>.pdf</u>"),
        ERROR,
        MessageInput(on_document, content_types=ContentType.DOCUMENT),
        MessageInput(input_error("⚠️ Invia il file come <b>documento</b> .pdf.")),
        BACK,
        state=PrintingSG.main,
        getter=getter,
    ),
    Window(
        Format("⚙️    <b>Opzioni</b> di stampa\n\n📄 {file_name}"),
        SwitchTo(Format("COPIE    {copies}"), id="copies", state=PrintingSG.copies),
        SwitchTo(Format("PAGINE    {pages}"), id="pages", state=PrintingSG.pages),
        SwitchTo(Format("FRONTE RETRO    {sides}"), id="sides", state=PrintingSG.sides),
        SwitchTo(Format("PAGINE PER FACCIATA    {number_up}"), id="number_up", state=PrintingSG.number_up),
        Row(
            SwitchTo(Const("↩️ Indietro"), id="to_main", state=PrintingSG.main),
            SwitchTo(Const("📑 Stampa"), id="to_confirm", state=PrintingSG.confirm),
        ),
        state=PrintingSG.options,
        getter=getter,
    ),
    Window(
        Const(f"🔢    Seleziona o scrivi il <b>numero di copie</b> (massimo {printing.MAX_COPIES})"),
        ERROR,
        Row(
            Select(
                Format("{item}"),
                id="c",
                item_id_getter=str,
                items=range(1, 6),
                type_factory=int,
                on_click=on_copies,
            )
        ),
        TextInput(
            id="copies_in",
            type_factory=_copies,
            on_success=on_copies,
            on_error=input_error(f"⚠️ Scrivi un numero da 1 a {printing.MAX_COPIES}."),
        ),
        TO_OPTIONS,
        state=PrintingSG.copies,
        getter=getter,
    ),
    Window(
        Const(
            "📑    Inserisci le <b>pagine da stampare</b>\n\n<u>es.</u>    <i>1,3-5,16</i>\n\n"
            "⚠️    In caso di <b>più pagine per facciata</b>, la selezione è sulle <b>facciate</b> "
            "e <b><u>non</u></b> sulle <b>pagine</b>."
        ),
        ERROR,
        Button(Const("Tutte le pagine"), id="all_pages", on_click=on_all_pages),
        TextInput(
            id="pages_in",
            type_factory=printing.parse_page_list,
            on_success=on_pages,
            on_error=input_error("⚠️ Formato non valido. Usa numeri, virgole e trattini, es. <i>1,3-5,16</i>."),
        ),
        TO_OPTIONS,
        state=PrintingSG.pages,
        getter=getter,
    ),
    Window(
        Const("📑    Seleziona il <b>fronte retro</b>"),
        Group(
            Select(
                Format("{item[1]}"),
                id="side",
                item_id_getter=lambda item: item[0],
                items="sides_list",
                on_click=on_sides,
            ),
            width=1,
        ),
        TO_OPTIONS,
        state=PrintingSG.sides,
        getter=getter,
    ),
    Window(
        Const("📑    Seleziona il numero di <b>pagine per facciata</b>"),
        Group(
            Select(
                Format("{item}"),
                id="nup",
                item_id_getter=str,
                items="number_up_list",
                type_factory=int,
                on_click=on_number_up,
            ),
            width=3,
        ),
        TO_OPTIONS,
        state=PrintingSG.number_up,
        getter=getter,
    ),
    Window(
        Format(
            "🖨️❓    Vuoi davvero procedere con la <b>stampa</b>?\n\n"
            "📄 {file_name}\n\nCopie: <b>{copies}</b>\nPagine: <b>{pages}</b>\n"
            "Fronte retro: <b>{sides}</b>\nPagine per facciata: <b>{number_up}</b>\n\n"
            "<i>L'operazione può richiedere <b>qualche momento</b></i>"
        ),
        Row(
            Button(Const("✔️"), id="print", on_click=on_print),
            TO_OPTIONS,
        ),
        state=PrintingSG.confirm,
        getter=getter,
    ),
    Window(
        Format("{result}"),
        SwitchTo(Const("🖨 Stampa un altro file"), id="again", state=PrintingSG.main),
        HOME,
        state=PrintingSG.done,
        getter=getter,
    ),
)
