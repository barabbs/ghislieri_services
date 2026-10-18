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
from ..common import BACK, HOME, app_of, esc, tidy_input, user_of

log = logging.getLogger(__name__)

ACCESS = "student"

# Per-user state kept outside dialog_data: updates of one user run concurrently (an album is
# several messages at once) and dialog_data is saved only when each handler ends, so updates
# would overwrite each other's changes.
_photos: dict[int, list[str]] = {}  # Telegram file_ids of the photos being collected
_sending: set[int] = set()  # users whose photos are being emailed


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


def text_of(limit: int):
    """TextInput type_factory: trimmed, non-empty, at most `limit` characters."""

    def factory(text: str) -> str:
        value = text.strip()
        if not 0 < len(value) <= limit:
            raise ValueError(text)
        return value

    return factory


async def on_bad_text(message: Message, widget: ManagedTextInput, manager: DialogManager, error) -> None:
    await tidy_input(message, manager)
    manager.dialog_data["error"] = "⚠️ Testo vuoto o troppo lungo."


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
    data["thanks"] = "Grazie per la segnalazione! 😄"
    await manager.switch_to(SubmissionsSG.done)


# Socials


async def on_photo(message: Message, widget: MessageInput, manager: DialogManager) -> None:
    photos = _photos.setdefault(message.chat.id, [])
    if len(photos) >= submissions.MAX_PHOTOS:
        manager.dialog_data["error"] = f"⚠️ Massimo {submissions.MAX_PHOTOS} foto."
    else:
        photos.append(message.photo[-1].file_id)  # type: ignore[index]  # largest size
    await tidy_input(message, manager)


async def on_not_photo(message: Message, widget: MessageInput, manager: DialogManager) -> None:
    await tidy_input(message, manager)
    manager.dialog_data["error"] = "⚠️ Invia una <b>foto</b> (non come file)."


async def on_clear_photos(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    _photos.pop(query.from_user.id, None)


async def on_send_social(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    data, user = manager.dialog_data, user_of(manager)
    assert user is not None
    # Dialog data is saved only when the handler ends, so it cannot stop a double tap.
    if user.id in _sending:
        await query.answer("Invio già in corso")
        return
    _sending.add(user.id)
    await query.answer("📤 Invio in corso…")
    try:
        await submissions.social_submission(app_of(manager), user, data["description"], _photos.get(user.id, []))
    except Exception:
        log.exception("Social submission by %s failed", user.id)
        data["error"] = "⚠️ Invio non riuscito, riprova più tardi."
        return
    finally:
        _sending.discard(user.id)
    _photos.pop(user.id, None)
    data["thanks"] = "Grazie per il materiale! 😄"
    await manager.switch_to(SubmissionsSG.done)


async def on_start_photos(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    _photos.pop(query.from_user.id, None)


async def getter(dialog_manager: DialogManager, **kwargs) -> dict:
    data = dialog_manager.dialog_data
    return {
        "error": data.pop("error", ""),
        "defaults": list(enumerate(submissions.DEFAULT_EDUROAM_REPORTS)),
        "report": esc(data.get("report", "")),
        "place": esc(data.get("place", "")),
        "note": esc(data.get("note", "")),
        "n_photos": len(_photos.get(dialog_manager.middleware_data["event_from_user"].id, [])),
        "description": esc(data.get("description", "")),
        "thanks": data.get("thanks", ""),
    }


ERROR = Format("\n{error}", when="error")


def _back(state: State) -> SwitchTo:
    return SwitchTo(Const("↩️ Indietro"), id=f"back_{state.state.split(':')[1]}", state=state)


dialog = Dialog(
    Window(
        Const("📩    <b>Invia segnalazioni e materiali</b>"),
        SwitchTo(Const("📣    Foto per Socials"), id="socials", state=SubmissionsSG.photos, on_click=on_start_photos),
        SwitchTo(Const("📶    Segnalazione Eduroam"), id="eduroam", state=SubmissionsSG.report),
        BACK,
        state=SubmissionsSG.main,
    ),
    Window(
        Const("Seleziona una <b>segnalazione</b> o <u>inviane una nuova</u>"),
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
        TextInput(id="report", type_factory=text_of(500), on_success=on_text, on_error=on_bad_text),
        _back(SubmissionsSG.main),
        state=SubmissionsSG.report,
        getter=getter,
    ),
    Window(
        Const("In che stanza o zona del Collegio?"),
        ERROR,
        TextInput(id="place", type_factory=text_of(200), on_success=on_text, on_error=on_bad_text),
        _back(SubmissionsSG.report),
        state=SubmissionsSG.place,
        getter=getter,
    ),
    Window(
        Const("Note eventuali"),
        ERROR,
        Button(Const("Nessuna nota"), id="no_note", on_click=on_no_note),
        TextInput(id="note", type_factory=text_of(1000), on_success=on_text, on_error=on_bad_text),
        _back(SubmissionsSG.place),
        state=SubmissionsSG.note,
        getter=getter,
    ),
    Window(
        Format("{report}\n\n<code>Luogo </code>{place}\n<code>Note  </code>{note}\n\n\n✉️  Inviare la segnalazione?"),
        Row(
            Button(Const("✔️"), id="send_report", on_click=on_send_report),
            SwitchTo(Const("❌"), id="cancel_report", state=SubmissionsSG.main),
        ),
        state=SubmissionsSG.eduroam_recap,
        getter=getter,
    ),
    Window(
        Const("📸    Invia la <b>foto</b>", when=lambda d, w, m: not d["n_photos"]),
        Format(
            "📸    Invia altre <b>foto</b>  ({n_photos} ricevute)\n\n<i>Premi <u>Termina</u> quando finito</i>.",
            when="n_photos",
        ),
        ERROR,
        MessageInput(on_photo, content_types=ContentType.PHOTO),
        MessageInput(on_not_photo),
        SwitchTo(Const("Termina"), id="photos_done", state=SubmissionsSG.description, when="n_photos"),
        Button(Const("🗑    Elimina le foto"), id="clear", on_click=on_clear_photos, when="n_photos"),
        _back(SubmissionsSG.main),
        state=SubmissionsSG.photos,
        getter=getter,
    ),
    Window(
        Const("<u>Invia</u> una <b>descrizione</b> delle foto"),
        ERROR,
        TextInput(id="description", type_factory=text_of(1000), on_success=on_text, on_error=on_bad_text),
        _back(SubmissionsSG.photos),
        state=SubmissionsSG.description,
        getter=getter,
    ),
    Window(
        Format("{description}\n\n<i>{n_photos} foto</i>\n\n\n✉️  Inviare le foto?"),
        ERROR,
        Row(
            Button(Const("✔️"), id="send_social", on_click=on_send_social),
            SwitchTo(Const("❌"), id="cancel_social", state=SubmissionsSG.main),
        ),
        state=SubmissionsSG.social_recap,
        getter=getter,
    ),
    Window(Format("{thanks}"), HOME, state=SubmissionsSG.done, getter=getter),
)
