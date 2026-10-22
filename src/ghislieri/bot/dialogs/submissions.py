"""Content submissions: eduroam reports, photos for the college's social media."""

import logging

from aiogram.enums import ContentType
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import ManagedTextInput, MessageInput, TextInput
from aiogram_dialog.widgets.kbd import Button, Group, Row, Select, SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from ... import submissions
from ..common import (
    BACK,
    ERROR,
    HOME,
    app_of,
    clear_photos,
    collect_photo,
    esc,
    input_error,
    text_of,
    tidy_input,
    user_of,
)

log = logging.getLogger(__name__)

ACCESS = "student"


class SubmissionsSG(StatesGroup):
    main = State()
    report = State()
    place = State()
    note = State()
    eduroam_recap = State()
    photos = State()
    description = State()
    social_recap = State()
    done = State()


async def on_text(message: Message, widget: ManagedTextInput, manager: DialogManager, value: str) -> None:
    """Stores the answer under the input's id and moves to the next step."""
    await tidy_input(message, manager)
    manager.dialog_data[widget.widget.widget_id] = value
    await manager.next()


# Eduroam


async def on_default_report(query: CallbackQuery, widget, manager: DialogManager, item_id: int) -> None:
    manager.dialog_data["report"] = submissions.DEFAULT_EDUROAM_REPORTS[item_id]
    await manager.next()


async def on_no_note(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    manager.dialog_data["note"] = "-"
    await manager.next()


async def on_send_report(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    data, user = manager.dialog_data, user_of(manager)
    assert user is not None
    submissions.eduroam_report(app_of(manager), user, data["report"], data["place"], data["note"])
    data["thanks"] = "✅ Segnalazione inviata. Grazie!"
    await manager.switch_to(SubmissionsSG.done)


# Socials


async def on_send_social(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    data, user = manager.dialog_data, user_of(manager)
    assert user is not None
    await query.answer("📤 Invio in corso…")
    try:
        await submissions.social_submission(app_of(manager), user, data["description"], data.get("photos", []))
    except Exception:
        log.exception("Social submission by %s failed", user.id)
        data["error"] = "⚠️ Invio non riuscito, riprova più tardi."
        return
    data.pop("photos", None)
    data["thanks"] = "✅ Foto inviate. Grazie!"
    await manager.switch_to(SubmissionsSG.done)


async def getter(dialog_manager: DialogManager, **kwargs) -> dict:
    data = dialog_manager.dialog_data
    return {
        "error": data.pop("error", ""),
        "defaults": list(enumerate(submissions.DEFAULT_EDUROAM_REPORTS)),
        "report": esc(data.get("report", "")),
        "place": esc(data.get("place", "")),
        "note": esc(data.get("note", "")),
        "n_photos": len(data.get("photos", [])),
        "description": esc(data.get("description", "")),
        "thanks": data.get("thanks", ""),
    }


BAD_TEXT = input_error("⚠️ Testo vuoto o troppo lungo.")


def _back(state: State) -> SwitchTo:
    return SwitchTo(Const("↩️ Indietro"), id=f"back_{state.state.split(':')[1]}", state=state)


dialog = Dialog(
    Window(
        Const("📩 <b>Invia Contenuti</b>"),
        SwitchTo(Const("📣 Foto per Socials"), id="socials", state=SubmissionsSG.photos, on_click=clear_photos),
        SwitchTo(Const("📶 Segnalazione Eduroam"), id="eduroam", state=SubmissionsSG.report),
        BACK,
        state=SubmissionsSG.main,
    ),
    Window(
        Const("📶 <b>Segnalazione Eduroam</b>\n\nScegli il problema, o scrivilo tu."),
        ERROR,
        Group(
            Select(
                Format("{item[1]}"),
                id="default",
                item_id_getter=lambda item: item[0],
                items="defaults",
                type_factory=int,
                on_click=on_default_report,
            ),
            width=1,
        ),
        TextInput(id="report", type_factory=text_of(500), on_success=on_text, on_error=BAD_TEXT),
        _back(SubmissionsSG.main),
        state=SubmissionsSG.report,
        getter=getter,
    ),
    Window(
        Const("📍 Scrivi la stanza o la zona del Collegio."),
        ERROR,
        TextInput(id="place", type_factory=text_of(200), on_success=on_text, on_error=BAD_TEXT),
        _back(SubmissionsSG.report),
        state=SubmissionsSG.place,
        getter=getter,
    ),
    Window(
        Const("📝 Aggiungi una nota, se vuoi."),
        ERROR,
        Button(Const("⏭ Nessuna nota"), id="no_note", on_click=on_no_note),
        TextInput(id="note", type_factory=text_of(1000), on_success=on_text, on_error=BAD_TEXT),
        _back(SubmissionsSG.place),
        state=SubmissionsSG.note,
        getter=getter,
    ),
    Window(
        Format(
            "📶 <b>Segnalazione Eduroam</b>\n\n"
            "<b>Problema</b>: {report}\n<b>Luogo</b>: {place}\n<b>Note</b>: {note}\n\nInviare la segnalazione?"
        ),
        Row(
            Button(Const("📤 Invia"), id="send_report", on_click=on_send_report),
            SwitchTo(Const("✖️ Annulla"), id="cancel_report", state=SubmissionsSG.main),
        ),
        state=SubmissionsSG.eduroam_recap,
        getter=getter,
    ),
    Window(
        Const("📣 <b>Foto per Socials</b>\n\nInvia una o più foto.", when=lambda d, w, m: not d["n_photos"]),
        Format(
            "📣 <b>Foto per Socials</b>\n\n📸 Foto ricevute: {n_photos}. Inviane altre o premi Avanti.",
            when="n_photos",
        ),
        ERROR,
        MessageInput(collect_photo(submissions.MAX_PHOTOS), content_types=ContentType.PHOTO),
        MessageInput(input_error("⚠️ Invia una foto (non come file).")),
        SwitchTo(Const("➡️ Avanti"), id="photos_done", state=SubmissionsSG.description, when="n_photos"),
        Button(Const("🗑 Elimina le foto"), id="clear", on_click=clear_photos, when="n_photos"),
        _back(SubmissionsSG.main),
        state=SubmissionsSG.photos,
        getter=getter,
    ),
    Window(
        Const("✏️ Scrivi una breve <b>descrizione</b> delle foto."),
        ERROR,
        TextInput(id="description", type_factory=text_of(1000), on_success=on_text, on_error=BAD_TEXT),
        _back(SubmissionsSG.photos),
        state=SubmissionsSG.description,
        getter=getter,
    ),
    Window(
        Format("📣 <b>Foto per Socials</b>\n\n{description}\n\n📸 Foto: {n_photos}\n\nInviare le foto?"),
        ERROR,
        Row(
            Button(Const("📤 Invia"), id="send_social", on_click=on_send_social),
            SwitchTo(Const("✖️ Annulla"), id="cancel_social", state=SubmissionsSG.main),
        ),
        state=SubmissionsSG.social_recap,
        getter=getter,
    ),
    Window(Format("{thanks}"), HOME, state=SubmissionsSG.done, getter=getter),
)
