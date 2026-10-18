"""Admin menu: students, notifications, links to the registrations, meals and calendar admin."""

import datetime as dt

from aiogram.enums import ContentType
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import ManagedTextInput, MessageInput, TextInput
from aiogram_dialog.widgets.kbd import (
    Button,
    Checkbox,
    Group,
    Multiselect,
    Radio,
    Row,
    ScrollingGroup,
    Select,
    Start,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Const, Format

from ... import clock, users
from ...notify import Button as NotifButton
from ..common import BACK, ERROR, HomeSG, admin_filter, app_of, esc, tidy_input
from . import calendar, meals, settings
from .registrations import RegistrationsSG

ACCESS = users.ADMIN

MAX_TEXT = 3500  # leaves room for the preview footer within Telegram's 4096 characters

STATUSES = {"active": "attivi", "blocked": "bloccati", "disabled": "disabilitati"}
STATUS_LABELS = {
    "active": "attivo",
    "blocked": "ha bloccato il bot",
    "disabled": "disabilitato",
    "pending": "in attesa",
}
# At most 48 h: older messages cannot be deleted by the bot.
EXPIRIES = (("0", "mai"), ("12", "12 h"), ("24", "24 h"), ("48", "48 h"))


class AdminSG(StatesGroup):
    main = State()
    students = State()
    students_group = State()
    student = State()
    student_groups = State()
    student_delete = State()
    notify = State()
    notify_text = State()
    notify_options = State()
    notify_groups = State()
    notify_preview = State()
    update = State()


# Main


async def main_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    return {"pending": len(users.list_users(app_of(dialog_manager).conn, status="pending"))}


# Students


async def students_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    data = dialog_manager.dialog_data
    status, group, search = data.get("status", "active"), data.get("group"), data.get("search", "")
    found = [
        u
        for u in users.list_users(app_of(dialog_manager).conn, group, status)
        if search.casefold() in u.surname.casefold()
    ]
    return {
        "students": [(u.id, f"{u.surname} {u.name}") for u in found],
        "count": len(found),
        "status": STATUSES[status],
        "group": esc(group or "tutti"),
        "search": esc(search),
    }


async def _first_page(manager: DialogManager) -> None:
    await manager.find("students_scroll").set_page(0)


async def on_search(message: Message, widget: ManagedTextInput, manager: DialogManager, value: str) -> None:
    manager.dialog_data["search"] = value.strip()[:60]
    await _first_page(manager)
    await tidy_input(message, manager)


async def on_clear_search(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    manager.dialog_data.pop("search", None)
    await _first_page(manager)


async def on_status_filter(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    order = list(STATUSES)
    current = manager.dialog_data.get("status", "active")
    manager.dialog_data["status"] = order[(order.index(current) + 1) % len(order)]
    await _first_page(manager)


async def on_group_filter(query: CallbackQuery, widget, manager: DialogManager, item_id: int) -> None:
    manager.dialog_data["group"] = users.KNOWN_GROUPS[item_id] if 0 <= item_id < len(users.KNOWN_GROUPS) else None
    await _first_page(manager)
    await manager.switch_to(AdminSG.students)


async def group_filter_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    return {"groups": [(-1, "Tutti"), *enumerate(users.KNOWN_GROUPS)]}


async def on_student(query: CallbackQuery, widget, manager: DialogManager, item_id: int) -> None:
    manager.dialog_data["uid"] = item_id
    await manager.switch_to(AdminSG.student)


def _student(manager: DialogManager) -> users.User | None:
    return users.get(app_of(manager).conn, manager.dialog_data.get("uid", 0))


async def student_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    u = _student(dialog_manager)
    if u is None:
        return {"found": False}
    return {
        "found": True,
        "toggle": "✅ Riabilita" if u.status == "disabled" else "🚫 Disabilita",
        "name": esc(u.name),
        "surname": esc(u.surname),
        "gender": users.GENDERS.get(u.gender or "", "non indicato"),
        "year": users.year_label(u.enrollment_year),
        "status": STATUS_LABELS.get(u.status, u.status),
        "groups": esc(", ".join(sorted(u.groups)) or "nessuno"),
    }


async def on_year(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    u = _student(manager)
    if u:
        year = u.enrollment_year or clock.academic_year(clock.today())
        step = -1 if button.widget_id == "year_dec" else 1
        users.update_profile(app_of(manager).conn, u.id, enrollment_year=year + step)


async def on_gender(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    u = _student(manager)
    if u:
        users.update_profile(app_of(manager).conn, u.id, gender="F" if u.gender == "M" else "M")


async def on_toggle_status(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    u = _student(manager)
    if u is None:
        return
    if u.id == query.from_user.id:
        await query.answer("Non puoi disabilitare te stesso")
        return
    users.set_status(app_of(manager).conn, u.id, "active" if u.status == "disabled" else "disabled")


async def on_delete(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    u = _student(manager)
    if u and u.id == query.from_user.id:
        await query.answer("Non puoi eliminare te stesso")
        await manager.switch_to(AdminSG.student)
        return
    if u:
        users.delete(app_of(manager).conn, u.id)
        await query.answer(f"{u.full_name} eliminato/a")
    await manager.switch_to(AdminSG.students)


def _group_choices(u: users.User) -> list[str]:
    """Known groups first, then any others the user holds (e.g. imported from v0.5)."""
    return [*users.KNOWN_GROUPS, *sorted(u.groups - set(users.KNOWN_GROUPS))]


async def student_groups_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    u = _student(dialog_manager)
    choices = _group_choices(u) if u else []
    # Items are indexes: unknown group names could overflow the 64-byte callback data.
    return {
        "name": esc(u.full_name) if u else "",
        "groups": [(i, ("✅ " if g in u.groups else "⬜ ") + g) for i, g in enumerate(choices)] if u else [],
    }


async def on_student_group(query: CallbackQuery, widget, manager: DialogManager, item_id: int) -> None:
    u = _student(manager)
    choices = _group_choices(u) if u else []
    if not 0 <= item_id < len(choices):
        return
    group, conn = choices[item_id], app_of(manager).conn
    if group not in u.groups:
        users.add_group(conn, u.id, group)
    elif u.id == query.from_user.id and group == users.ADMIN:
        await query.answer("Non puoi toglierti i permessi di admin")
    else:
        users.remove_group(conn, u.id, group)


# Notifications


async def notify_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    return {"flash": dialog_manager.dialog_data.pop("flash", "")}


async def on_new_notification(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    manager.dialog_data.pop("text", None)
    await manager.find("targets").reset_checked()
    await manager.find("expiry").set_checked("0")
    await manager.find("push").set_checked(True)
    await manager.find("open_bot").set_checked(False)
    await manager.switch_to(AdminSG.notify_text)


async def on_notification_text(message: Message, widget: MessageInput, manager: DialogManager) -> None:
    await tidy_input(message, manager)
    text = message.html_text  # keeps the admin's bold, links, etc.
    if len(text) > MAX_TEXT:
        manager.dialog_data["error"] = f"⚠️ Testo troppo lungo (massimo {MAX_TEXT} caratteri)."
        return
    manager.dialog_data["text"] = text
    await manager.switch_to(AdminSG.notify_options)


async def notify_text_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    return {"error": dialog_manager.dialog_data.pop("error", "")}


def _composed(manager: DialogManager) -> dict:
    groups = tuple(manager.find("targets").get_checked())
    hours = int(manager.find("expiry").get_checked() or 0)
    return {
        "text": manager.dialog_data.get("text", ""),
        "groups": groups,
        "silent": not manager.find("push").is_checked(),
        "expires_at": clock.now() + dt.timedelta(hours=hours) if hours else None,
        "buttons": [NotifButton("🏠 Apri il bot", HomeSG.main.state)] if manager.find("open_bot").is_checked() else [],
        "hours": hours,
    }


async def notify_options_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    c = _composed(dialog_manager)
    expiry = dict(EXPIRIES)[str(c["hours"])]
    return {
        "items_expiry": EXPIRIES,
        "groups_count": len(c["groups"]),
        "has_groups": bool(c["groups"]),
        "summary": (
            f"Destinatari: {esc(', '.join(c['groups']) or 'nessuno')}\n"
            f"Notifica: {'silenziosa' if c['silent'] else 'con suono'} · scadenza: {expiry}\n"
            f"Pulsante «Apri il bot»: {'sì' if c['buttons'] else 'no'}"
        ),
        "recipients": len(users.user_ids(app_of(dialog_manager).conn, c["groups"])),
        "text": c["text"],
    }


async def notify_groups_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    return {"groups": users.KNOWN_GROUPS}


async def on_send_notification(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    app, c = app_of(manager), _composed(manager)
    if not c["groups"] or not c["text"]:
        return
    count = len(users.user_ids(app.conn, c["groups"]))
    # replace=False: a new custom notification must not retract the previous ones.
    app.notifier.send_to_groups(
        c["groups"],
        c["text"],
        kind="custom",
        buttons=c["buttons"],
        silent=c["silent"],
        expires_at=c["expires_at"],
        replace=False,
    )
    manager.dialog_data.pop("text", None)
    manager.dialog_data["flash"] = f"✅ Notifica inviata a {count} utenti."
    await manager.switch_to(AdminSG.notify)


def update_text() -> str:
    """The update notice, with the current version's changelog notes."""
    version = settings.release()
    body = settings.changelog_notes(version)
    if len(body) > MAX_TEXT:
        body = body[:MAX_TEXT].rsplit("\n", 1)[0] + "\n…"
    text = f"🎉    <b>Nuovo Aggiornamento!</b>    🎉\n\nversione {version}"
    return text + "\n\n" + (esc(body) if body else "Scopri le novità nelle impostazioni.")


async def update_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    return {"text": update_text(), "recipients": len(users.list_users(app_of(dialog_manager).conn))}


async def on_send_update(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    app = app_of(manager)
    ids = [u.id for u in users.list_users(app.conn)]
    app.notifier.send(
        ids,
        update_text(),
        kind="update",
        ref=settings.release(),
        buttons=[NotifButton("🆕    Vedi le Novità", settings.SettingsSG.changelog.state)],
        silent=True,
    )
    manager.dialog_data["flash"] = f"✅ Aggiornamento annunciato a {len(ids)} utenti."
    await manager.switch_to(AdminSG.notify)


TO_MAIN = SwitchTo(Const("↩️ Indietro"), id="to_main", state=AdminSG.main)
TO_NOTIFY = SwitchTo(Const("↩️ Indietro"), id="to_notify", state=AdminSG.notify)

dialog = Dialog(
    Window(
        Const("🔓    <b>Admin</b>"),
        Start(Format("📝 Registrazioni ({pending})"), id="registrations", state=RegistrationsSG.list),
        Row(
            SwitchTo(Const("👥 Studenti"), id="students", state=AdminSG.students),
            SwitchTo(Const("📣 Notifiche"), id="notify", state=AdminSG.notify),
        ),
        Row(
            Start(Const("🍽️ Mensa"), id="meals", state=meals.MealsSG.admin),
            Start(Const("🗓 Calendario"), id="calendar", state=calendar.CalendarSG.admin),
        ),
        BACK,
        state=AdminSG.main,
        getter=main_getter,
    ),
    # Students
    Window(
        Format("👥 <b>Studenti</b> {status}, gruppo {group}: {count}"),
        Format("🔎 Cognome contiene «{search}»", when="search"),
        Const("Scrivi un cognome per cercare."),
        ScrollingGroup(
            Select(
                Format("{item[1]}"),
                id="student",
                item_id_getter=lambda item: item[0],
                items="students",
                type_factory=int,
                on_click=on_student,
            ),
            id="students_scroll",
            width=1,
            height=8,
            hide_on_single_page=True,
        ),
        Row(
            Button(Format("Stato: {status}"), id="status_filter", on_click=on_status_filter),
            SwitchTo(Format("Gruppo: {group}"), id="group_filter", state=AdminSG.students_group),
        ),
        Button(Const("✖️ Annulla ricerca"), id="clear_search", on_click=on_clear_search, when="search"),
        TextInput(id="search", on_success=on_search),
        TO_MAIN,
        state=AdminSG.students,
        getter=students_getter,
    ),
    Window(
        Const("Filtra per <b>gruppo</b>"),
        Group(
            Select(
                Format("{item[1]}"),
                id="filter_group",
                item_id_getter=lambda item: item[0],
                items="groups",
                type_factory=int,
                on_click=on_group_filter,
            ),
            width=2,
        ),
        state=AdminSG.students_group,
        getter=group_filter_getter,
    ),
    Window(
        Format(
            "<code>Nome     </code><b>{name}</b>\n"
            "<code>Cognome  </code><b>{surname}</b>\n"
            "<code>Genere   </code>{gender}\n"
            "<code>Ingresso </code>{year}\n"
            "<code>Stato    </code>{status}\n"
            "<code>Gruppi   </code><i>{groups}</i>",
            when="found",
        ),
        Const("Utente non trovato.", when=lambda d, w, m: not d["found"]),
        Group(
            Row(
                Button(Const("◀ anno"), id="year_dec", on_click=on_year),
                Button(Const("anno ▶"), id="year_inc", on_click=on_year),
                Button(Const("⚧ genere"), id="gender", on_click=on_gender),
            ),
            SwitchTo(Const("👥 Gruppi"), id="to_groups", state=AdminSG.student_groups),
            Button(Format("{toggle}"), id="toggle_status", on_click=on_toggle_status),
            SwitchTo(Const("❌ Elimina"), id="to_delete", state=AdminSG.student_delete),
            when="found",
        ),
        SwitchTo(Const("↩️ Elenco"), id="to_list", state=AdminSG.students),
        state=AdminSG.student,
        getter=student_getter,
    ),
    Window(
        Format("👥 Gruppi di <b>{name}</b>"),
        Group(
            Select(
                Format("{item[1]}"),
                id="student_group",
                item_id_getter=lambda item: item[0],
                items="groups",
                type_factory=int,
                on_click=on_student_group,
            ),
            width=2,
        ),
        SwitchTo(Const("✔️ Fatto"), id="groups_done", state=AdminSG.student),
        state=AdminSG.student_groups,
        getter=student_groups_getter,
    ),
    Window(
        Format("Eliminare definitivamente <b>{name} {surname}</b>?", when="found"),
        Button(Const("❌ Sì, elimina"), id="delete", on_click=on_delete, when="found"),
        SwitchTo(Const("↩️ No"), id="keep", state=AdminSG.student),
        state=AdminSG.student_delete,
        getter=student_getter,
    ),
    # Notifications
    Window(
        Const("📣    <b>Notifiche</b>"),
        Format("{flash}", when="flash"),
        Button(Const("✏️ Nuova notifica"), id="new_notification", on_click=on_new_notification),
        SwitchTo(Const("🆕 Annuncia aggiornamento"), id="to_update", state=AdminSG.update),
        TO_MAIN,
        state=AdminSG.notify,
        getter=notify_getter,
    ),
    Window(
        Const("✏️ Scrivi il testo della notifica. La formattazione viene mantenuta."),
        ERROR,
        MessageInput(on_notification_text, content_types=ContentType.TEXT),
        TO_NOTIFY,
        state=AdminSG.notify_text,
        getter=notify_text_getter,
    ),
    Window(
        Const("<b>Nuova notifica</b>\n"),
        Format("{summary}"),
        SwitchTo(Format("👥 Destinatari ({groups_count})"), id="to_targets", state=AdminSG.notify_groups),
        Row(
            Checkbox(Const("🔔 Con suono"), Const("🔕 Silenziosa"), id="push", default=True),
            Checkbox(Const("✅ Apri il bot"), Const("⬜ Apri il bot"), id="open_bot"),
        ),
        Const("\nScadenza:"),
        Radio(
            Format("🔘 {item[1]}"),
            Format("{item[1]}"),
            id="expiry",
            item_id_getter=lambda item: item[0],
            items="items_expiry",
        ),
        Row(
            SwitchTo(Const("✏️ Testo"), id="edit_text", state=AdminSG.notify_text),
            SwitchTo(Const("👀 Anteprima"), id="to_preview", state=AdminSG.notify_preview, when="has_groups"),
        ),
        TO_NOTIFY,
        state=AdminSG.notify_options,
        getter=notify_options_getter,
    ),
    Window(
        Const("👥 Scegli i <b>destinatari</b> (almeno un gruppo)"),
        Group(
            Multiselect(
                Format("✅ {item}"),
                Format("{item}"),
                id="targets",
                item_id_getter=lambda g: g,
                items="groups",
            ),
            width=2,
        ),
        SwitchTo(Const("✔️ Fatto"), id="targets_done", state=AdminSG.notify_options),
        state=AdminSG.notify_groups,
        getter=notify_groups_getter,
    ),
    Window(
        Format("{text}\n\n—— fine notifica ——\n{summary}\nUtenti raggiunti: {recipients}"),
        Button(Const("📤 Invia"), id="send", on_click=on_send_notification, when="has_groups"),
        SwitchTo(Const("↩️ Modifica"), id="back_options", state=AdminSG.notify_options),
        state=AdminSG.notify_preview,
        getter=notify_options_getter,
    ),
    Window(
        Format("{text}\n\n—— fine notifica ——\nInvio silenzioso a tutti gli utenti attivi: {recipients}"),
        Button(Const("📤 Invia"), id="send_update", on_click=on_send_update),
        TO_NOTIFY,
        state=AdminSG.update,
        getter=update_getter,
    ),
)
dialog.callback_query.filter(admin_filter)
dialog.message.filter(admin_filter)
