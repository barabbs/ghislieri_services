"""Settings: profile, feedback, about, changelog."""

import re
from importlib import resources

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import ManagedTextInput, TextInput
from aiogram_dialog.widgets.kbd import Button, Row, SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from ... import __version__, submissions, users
from ..common import BACK, ERROR, HOME, NAME_ERROR, app_of, esc, input_error, person_name, text_of, tidy_input, user_of

ACCESS = None


class SettingsSG(StatesGroup):
    main = State()
    profile = State()
    edit = State()
    feedback = State()
    feedback_done = State()
    about = State()
    changelog = State()


def release() -> str:
    """The version without dev/pre-release suffixes ("1.0.0.dev0" -> "1.0.0")."""
    return re.match(r"\d+(\.\d+)*", __version__).group()  # type: ignore[union-attr]


def changelog_notes(version: str) -> str:
    """The notes under "## <version>" in changelog.md (empty if there are none)."""
    text = resources.files("ghislieri").joinpath("changelog.md").read_text(encoding="utf-8")
    sections = dict(re.findall(r"^## (\S+)\n(.*?)(?=^## |\Z)", text, re.M | re.S))
    return sections.get(version, "").strip()


def email_address(text: str) -> str:
    value = text.strip()
    if len(value) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s.]+", value):
        raise ValueError(text)
    return value


# Editable profile fields: label, prompt, validator, error.
FIELDS = {
    "name": ("Nome", "il nuovo <b>Nome</b>", person_name, NAME_ERROR),
    "surname": ("Cognome", "il nuovo <b>Cognome</b>", person_name, NAME_ERROR),
    "email": ("Email", "la nuova <b>Email</b>", email_address, "⚠️ Indirizzo email non valido."),
}


async def on_edit(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    manager.dialog_data["field"] = button.widget_id.removeprefix("edit_")
    await manager.switch_to(SettingsSG.edit)


async def on_value(message: Message, widget: ManagedTextInput, manager: DialogManager, text: str) -> None:
    await tidy_input(message, manager)
    field = manager.dialog_data["field"]
    _, _, validate, error = FIELDS[field]
    try:
        value = validate(text)
    except ValueError:
        manager.dialog_data["error"] = error
        return
    users.update_profile(app_of(manager).conn, message.from_user.id, **{field: value})  # type: ignore[union-attr]
    await manager.switch_to(SettingsSG.profile)


async def on_feedback(message: Message, widget: ManagedTextInput, manager: DialogManager, text: str) -> None:
    await tidy_input(message, manager)
    user = user_of(manager)
    assert user is not None
    submissions.feedback(app_of(manager), user, text)
    await manager.switch_to(SettingsSG.feedback_done)


async def profile_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    # Fresh from the database: a handler may have just changed it in this same update.
    user = users.get(app_of(dialog_manager).conn, dialog_manager.middleware_data["event_from_user"].id)
    assert user is not None
    return {
        "name": esc(user.name),
        "surname": esc(user.surname),
        "email": esc(user.email or "non indicata"),
        "gender": users.GENDERS.get(user.gender or "", "non indicato"),
        "year": users.year_label(user.enrollment_year),
    }


async def getter(dialog_manager: DialogManager, **kwargs) -> dict:
    data = dialog_manager.dialog_data
    field = FIELDS.get(data.get("field", ""))
    return {
        "error": data.pop("error", ""),
        "prompt": field[1] if field else "",
        "version": release(),
        "changelog": esc(changelog_notes(release())[:3500] or "Nessuna novità."),
    }


TO_MAIN = SwitchTo(Const("↩️ Indietro"), id="to_main", state=SettingsSG.main)

dialog = Dialog(
    Window(
        Const("🔧    <b>Impostazioni</b>"),
        SwitchTo(Const("👤    Profilo"), id="profile", state=SettingsSG.profile),
        SwitchTo(Const("💬    Segnalazioni e Suggerimenti"), id="feedback", state=SettingsSG.feedback),
        Row(
            SwitchTo(Const("🆕️    Changelog"), id="changelog", state=SettingsSG.changelog),
            SwitchTo(Const("ℹ️    Info"), id="about", state=SettingsSG.about),
        ),
        BACK,
        state=SettingsSG.main,
    ),
    Window(
        Format(
            "👤    <b>Profilo</b>\n\n<b>Nome</b>: {name}\n<b>Cognome</b>: {surname}\n<b>Email</b>: {email}\n"
            "<b>Genere</b>: {gender}\n<b>Anno di ingresso</b>: {year}\n\n"
            "<i>Per correggere genere o anno di ingresso contatta un amministratore.</i>"
        ),
        Row(
            Button(Const("✏️ Nome"), id="edit_name", on_click=on_edit),
            Button(Const("✏️ Cognome"), id="edit_surname", on_click=on_edit),
            Button(Const("✏️ Email"), id="edit_email", on_click=on_edit),
        ),
        TO_MAIN,
        state=SettingsSG.profile,
        getter=profile_getter,
    ),
    Window(
        Format("✏️ Inserisci {prompt}"),
        ERROR,
        TextInput(id="value", on_success=on_value),
        SwitchTo(Const("↩️ Indietro"), id="to_profile", state=SettingsSG.profile),
        state=SettingsSG.edit,
        getter=getter,
    ),
    Window(
        Const("Scrivi il <b>problema</b> riscontrato o il <b>suggerimento</b> per il bot"),
        ERROR,
        TextInput(
            id="feedback_in",
            type_factory=text_of(3000),  # the admin notification must fit in one message
            on_success=on_feedback,
            on_error=input_error("⚠️ Testo vuoto o troppo lungo (massimo 3000 caratteri)."),
        ),
        TO_MAIN,
        state=SettingsSG.feedback,
        getter=getter,
    ),
    Window(Const("Grazie per la segnalazione! 😄"), HOME, state=SettingsSG.feedback_done),
    Window(
        Format(
            "<b>Ghislieri Bot</b> 🤖\nversione {version}\n\n<i>Developed by Barabba</i>\n\n"
            "Codice sorgente: https://github.com/barabbs/ghislieri_services"
        ),
        TO_MAIN,
        state=SettingsSG.about,
        getter=getter,
    ),
    Window(
        Format("<b>Changelog</b>    -    versione {version}\n\n{changelog}"),
        TO_MAIN,
        state=SettingsSG.changelog,
        getter=getter,
    ),
)
