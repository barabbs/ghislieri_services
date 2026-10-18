"""Signup of new users. The account is created only when every field is filled in."""

import sqlite3

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import ManagedTextInput, TextInput
from aiogram_dialog.widgets.kbd import Button, Row, SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from ... import users
from ...notify import Button as NotifButton
from ..common import app_of, esc, go_home, person_name, tidy_input, user_of
from .registrations import RegistrationsSG

ACCESS = None


class SignupSG(StatesGroup):
    surname = State()
    name = State()
    gender = State()
    confirm = State()
    waiting = State()


async def on_text(message: Message, widget: ManagedTextInput, manager: DialogManager, value: str) -> None:
    manager.dialog_data[widget.widget.widget_id] = value
    await tidy_input(message, manager)
    if {"surname", "name", "gender"} <= manager.dialog_data.keys():  # editing from the recap
        await manager.switch_to(SignupSG.confirm)
    else:
        await manager.next()


async def on_bad_name(message: Message, widget: ManagedTextInput, manager: DialogManager, error: ValueError) -> None:
    await tidy_input(message, manager)
    manager.dialog_data["error"] = "⚠️ Usa solo lettere, massimo 60 caratteri."


async def on_gender(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    manager.dialog_data["gender"] = button.widget_id
    await manager.switch_to(SignupSG.confirm)


async def on_confirm(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    app, data = app_of(manager), manager.dialog_data
    try:
        user = users.create_pending(app.conn, query.from_user.id, data["name"], data["surname"], data["gender"])
    except sqlite3.IntegrityError:  # already registered (e.g. double tap)
        await manager.switch_to(SignupSG.waiting)
        return
    app.notifier.send_to_groups(
        (users.ADMIN,),
        f"🆕 Nuova registrazione: <b>{esc(user.full_name)}</b>",
        kind="registration",
        ref=str(user.id),
        buttons=[NotifButton("👀 Vedi registrazioni", RegistrationsSG.list.state)],
    )
    await manager.switch_to(SignupSG.waiting)


async def on_refresh(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    user = users.get(app_of(manager).conn, query.from_user.id)
    if user and user.is_active:
        await go_home(manager)
    else:
        await query.answer("Registrazione ancora in attesa di approvazione")


async def getter(dialog_manager: DialogManager, **kwargs) -> dict:
    data = dialog_manager.dialog_data
    return {
        "error": data.pop("error", ""),
        "name": esc(data.get("name", "")),
        "surname": esc(data.get("surname", "")),
        "gender": {"M": "Maschile", "F": "Femminile"}.get(data.get("gender", ""), ""),
    }


async def waiting_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    user = user_of(dialog_manager)
    return {"name": esc(user.name) if user else ""}


dialog = Dialog(
    Window(
        Const("👋 Benvenuto/a nel bot del <b>Collegio Ghislieri</b>!\n\nPer iscriverti scrivi il tuo <b>cognome</b>."),
        Format("{error}", when="error"),
        TextInput(id="surname", type_factory=person_name, on_success=on_text, on_error=on_bad_name),
        state=SignupSG.surname,
        getter=getter,
    ),
    Window(
        Const("Ora scrivi il tuo <b>nome</b>."),
        Format("{error}", when="error"),
        TextInput(id="name", type_factory=person_name, on_success=on_text, on_error=on_bad_name),
        state=SignupSG.name,
        getter=getter,
    ),
    Window(
        Const("Seleziona il <b>genere</b> (serve per le liste della mensa)."),
        Row(
            Button(Const("Maschile"), id="M", on_click=on_gender),
            Button(Const("Femminile"), id="F", on_click=on_gender),
        ),
        state=SignupSG.gender,
    ),
    Window(
        Format("Controlla i tuoi dati:\n\n<b>Cognome</b>: {surname}\n<b>Nome</b>: {name}\n<b>Genere</b>: {gender}"),
        Button(Const("✅ Conferma"), id="confirm", on_click=on_confirm),
        Row(
            SwitchTo(Const("✏️ Cognome"), id="edit_surname", state=SignupSG.surname),
            SwitchTo(Const("✏️ Nome"), id="edit_name", state=SignupSG.name),
            SwitchTo(Const("✏️ Genere"), id="edit_gender", state=SignupSG.gender),
        ),
        state=SignupSG.confirm,
        getter=getter,
    ),
    Window(
        Format(
            "⏳ Grazie {name}! La tua registrazione è stata inviata.\n\n"
            "Riceverai un messaggio appena un amministratore l'avrà approvata."
        ),
        Button(Const("🔄 Aggiorna"), id="refresh", on_click=on_refresh),
        state=SignupSG.waiting,
        getter=waiting_getter,
    ),
)
