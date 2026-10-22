"""Admin menu: students, notifications, system tools, links to the registrations, meals and calendar admin."""

import datetime as dt
import html
import logging
import re

from aiogram.enums import ContentType
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, ShowMode, Window
from aiogram_dialog.widgets.input import ManagedTextInput, MessageInput, TextInput
from aiogram_dialog.widgets.kbd import (
    Button,
    Checkbox,
    CurrentPage,
    Group,
    Multiselect,
    NextPage,
    PrevPage,
    Radio,
    Row,
    ScrollingGroup,
    Select,
    Start,
    StubScroll,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Const, Format

from ... import __version__, clock, log, notify, users
from ...app import RESTART
from ...notify import Button as NotifButton
from ..common import BACK, ERROR, HomeSG, admin_filter, app_of, esc, tidy_input
from . import calendar, meals, printing, settings
from .registrations import RegistrationsSG

ACCESS = users.ADMIN

logger = logging.getLogger(__name__)

MAX_TEXT = 3500  # leaves room for the preview footer within Telegram's 4096 characters
TEXT_LIMIT = 3800  # system pages: Telegram allows 4096 characters, leave room for the header

STATUSES = {"active": "attivi", "blocked": "bloccati", "disabled": "disabilitati"}
STATUS_LABELS = {
    "active": "attivo",
    "blocked": "ha bloccato il bot",
    "disabled": "disabilitato",
    "pending": "in attesa",
}
# At most 48 h: older messages cannot be deleted by the bot.
EXPIRIES = (("0", "mai"), ("12", "12 h"), ("24", "24 h"), ("48", "48 h"))

KIND_LABELS = {
    "custom": "📣 Avviso",
    "update": "🆕 Aggiornamento",
    "registration": "📝 Registrazione",
    "signup_result": "📝 Esito registrazione",
    "rollover": "🎓 Passaggio ad alumni",
    "calendar": "🗓 Calendario",
    "meal_reminder": "🍽 Promemoria mensa",
    "meal_calendar": "🍽 Calendario mensa",
    "meal_report": "🍽 Segnalazione mensa",
    "eduroam_report": "📶 Segnalazione eduroam",
    "social": "📸 Post social",
    "feedback": "💬 Feedback",
}
DELIVERY_LABELS = {"pending": "in coda", "sent": "inviate", "failed": "non riuscite", "retracted": "ritirate"}
# Keyed by APScheduler's func_ref; tests check that every scheduled job has a label.
JOB_LABELS = {
    "ghislieri.meals:daily_recap": "🍽 Riepilogo pasti",
    "ghislieri.meals:remind": "🔔 Promemoria mensa",
    "ghislieri.meals:yearly_calendar": "🗓 Giorni mensa dell'anno",
    "ghislieri.jobs:academic_year_rollover": "🎓 Passaggio ad alumni",
    "ghislieri.events:sync_job": "🔄 Sincronizzazione calendario",
    "ghislieri.jobs:expire_notifications": "⏳ Scadenza notifiche",
}


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
    active = State()
    active_detail = State()
    active_retract = State()
    system = State()
    errors = State()
    error = State()
    logs = State()
    info = State()
    jobs = State()
    job = State()
    job_run = State()
    restart = State()
    shutdown = State()
    bye = State()
    legacy = State()


def _when(moment: dt.datetime) -> str:
    """ "SAB 25 ott 21:00", in Rome time."""
    local = moment.astimezone(clock.TZ)
    return f"{clock.day_label(local.date(), short=True)} {local:%H:%M}"


async def flash_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    return {"flash": dialog_manager.dialog_data.pop("flash", "")}


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
        await query.answer("⚠️ Non puoi disabilitare il tuo account.")
        return
    users.set_status(app_of(manager).conn, u.id, "active" if u.status == "disabled" else "disabled")


async def on_delete(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    u = _student(manager)
    if u and u.id == query.from_user.id:
        await query.answer("⚠️ Non puoi eliminare il tuo account.")
        await manager.switch_to(AdminSG.student)
        return
    if u:
        users.delete(app_of(manager).conn, u.id)
        await query.answer(f"✅ {u.full_name} eliminato/a.")
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
        await query.answer("⚠️ Non puoi toglierti i permessi di admin.")
    else:
        users.remove_group(conn, u.id, group)


# Notifications


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
        manager.dialog_data["error"] = f"⚠️ Testo troppo lungo: accorcialo a {MAX_TEXT} caratteri."
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
            f"Suono: {'no' if c['silent'] else 'sì'} · scadenza: {expiry}\n"
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
    text = f"🎉 <b>Nuovo aggiornamento</b>\n\nVersione {version}"
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
        buttons=[NotifButton("🆕 Novità", settings.SettingsSG.changelog.state)],
        silent=True,
    )
    manager.dialog_data["flash"] = f"✅ Aggiornamento annunciato a {len(ids)} utenti."
    await manager.switch_to(AdminSG.notify)


# Active notifications


def plain(text: str) -> str:
    """Telegram HTML as plain text (tags dropped, entities decoded): escape it again before display."""
    return html.unescape(re.sub(r"<[^>]*>", "", text))


async def active_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    rows = notify.active(app_of(dialog_manager).conn)
    items = []
    for n in rows:
        preview = " ".join(plain(n["text"]).split())
        preview = preview if len(preview) <= 30 else preview[:29] + "…"
        label = KIND_LABELS.get(n["kind"], n["kind"])
        items.append((n["id"], f"{label} · {_when(clock.parse(n['created_at']))} · {preview}"))
    return {"notifications": items, "count": len(items), "flash": dialog_manager.dialog_data.pop("flash", "")}


def _active(manager: DialogManager):
    nid = manager.dialog_data.get("nid")
    return next((n for n in notify.active(app_of(manager).conn) if n["id"] == nid), None)


async def active_detail_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    n = _active(dialog_manager)
    if n is None:
        return {"found": False}
    counts = notify.delivery_counts(app_of(dialog_manager).conn, n["id"])
    text = plain(n["text"])
    if len(text) > 3000:
        text = text[:3000] + "…"
    return {
        "found": True,
        "title": esc(KIND_LABELS.get(n["kind"], n["kind"])),
        "kind": esc(n["kind"]),
        "ref": esc(n["ref"] or "—"),
        "created": _when(clock.parse(n["created_at"])),
        "expires": _when(clock.parse(n["expires_at"])) if n["expires_at"] else "nessuna",
        "counts": " · ".join(f"{label} {counts[s]}" for s, label in DELIVERY_LABELS.items() if counts.get(s)),
        "text": esc(text),
    }


async def on_active(query: CallbackQuery, widget, manager: DialogManager, item_id: int) -> None:
    manager.dialog_data["nid"] = item_id
    await manager.switch_to(AdminSG.active_detail)


async def on_retract(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    n = _active(manager)
    if n is not None:
        app_of(manager).notifier.retract_notification(n["id"])
        logger.info("Notification %s retracted by admin %s", n["id"], query.from_user.id)
    manager.dialog_data["flash"] = "✅ Notifica ritirata."
    await manager.switch_to(AdminSG.active)


# System


def _time(record: logging.LogRecord) -> str:
    return f"{dt.datetime.fromtimestamp(record.created, clock.TZ):%d/%m %H:%M:%S}"


def error_detail(record: logging.LogRecord) -> str:
    """The formatted record with its traceback, escaped; the start is cut to fit one message."""
    text = logging.Formatter("%(message)s").format(record)
    while len(esc(text)) > TEXT_LIMIT:
        text = text[len(text) // 10 :]
    return f"⚠️ <b>{_time(record)}</b> <code>{esc(record.name)}</code>\n\n<pre>{esc(text)}</pre>"


async def errors_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    records = list(reversed(log.recent_errors))
    return {
        "errors": [(str(id(r)), f"{_time(r)} {r.name}: {r.getMessage()}"[:60]) for r in records],
        "count": len(records),
    }


async def error_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    wanted = dialog_manager.dialog_data.get("error_id")
    record = next((r for r in log.recent_errors if str(id(r)) == wanted), None)
    return {"detail": error_detail(record) if record else "⚠️ Errore non più disponibile."}


async def on_error(query: CallbackQuery, widget, manager: DialogManager, item_id: str) -> None:
    manager.dialog_data["error_id"] = item_id
    await manager.switch_to(AdminSG.error)


def log_pages(lines: list[str], limit: int = TEXT_LIMIT) -> list[str]:
    """Escaped lines grouped into pages of at most `limit` characters."""
    pages, page = [], ""
    for line in map(esc, lines):
        if page and len(page) + 1 + len(line) > limit:
            pages.append(page)
            page = line
        else:
            page = f"{page}\n{line}" if page else line
    return [*pages, page] if page else []


async def logs_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    pages = log_pages(list(reversed(log.recent_lines))) or ["Nessuna riga."]
    page = min(await dialog_manager.find("log_scroll").get_page(), len(pages) - 1)
    return {"log": pages[page], "pages": len(pages)}


async def on_refresh_logs(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    await manager.find("log_scroll").set_page(0)


def _duration(delta: dt.timedelta) -> str:
    hours, minutes = divmod(int(delta.total_seconds()) // 60, 60)
    days, hours = divmod(hours, 24)
    return f"{days} g {hours} h {minutes} min" if days else f"{hours} h {minutes} min"


async def system_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    app = app_of(dialog_manager)
    return {"version": __version__, "uptime": _duration(clock.now() - app.started_at)}


async def info_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    app = app_of(dialog_manager)
    conn = app.conn
    statuses = conn.execute("SELECT status, count(*) AS n FROM users GROUP BY status ORDER BY status").fetchall()
    pending = conn.execute("SELECT count(*) FROM deliveries WHERE state = 'pending'").fetchone()[0]
    size = conn.execute("PRAGMA page_count").fetchone()[0] * conn.execute("PRAGMA page_size").fetchone()[0]
    return {
        "version": __version__,
        "env": app.settings.env,
        "started": _when(app.started_at),
        "uptime": _duration(clock.now() - app.started_at),
        "users": "\n".join(f"• {STATUS_LABELS.get(r['status'], r['status'])}: {r['n']}" for r in statuses)
        or "• nessuno",
        "pending": pending,
        "size": f"{size / 1e6:.1f} MB",
    }


def _job_label(job) -> str:
    return JOB_LABELS.get(job.func_ref, job.name)


def _next_run(job) -> str:
    moment = getattr(job, "next_run_time", None)  # unset until the scheduler starts, None if paused
    return _when(moment) if moment else "in pausa"


async def jobs_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    jobs = app_of(dialog_manager).scheduler.get_jobs()
    return {
        "jobs": [(j.id, f"{_job_label(j)} · {_next_run(j)}") for j in jobs],
        "count": len(jobs),
        "flash": dialog_manager.dialog_data.pop("flash", ""),
    }


async def on_job(query: CallbackQuery, widget, manager: DialogManager, item_id: str) -> None:
    manager.dialog_data["job_id"] = item_id
    await manager.switch_to(AdminSG.job)


async def job_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    job = app_of(dialog_manager).scheduler.get_job(dialog_manager.dialog_data.get("job_id", ""))
    if job is None:
        return {"found": False}
    return {"found": True, "label": _job_label(job), "next": _next_run(job), "trigger": esc(job.trigger)}


async def on_run_job(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    job = app_of(manager).scheduler.get_job(manager.dialog_data.get("job_id", ""))
    if job is None:
        manager.dialog_data["flash"] = "⚠️ Job non trovato: forse è stato rimosso."
    else:
        # After this run the trigger computes the next regular time, so the schedule is unchanged.
        job.modify(next_run_time=clock.now())
        logger.info("Job %s started by admin %s", job.func_ref, query.from_user.id)
        manager.dialog_data["flash"] = f"✅ Avviato: {_job_label(job)}. L'esito è nei log."
    await manager.switch_to(AdminSG.jobs)


async def on_stop(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    restart = button.widget_id == "do_restart"
    manager.dialog_data["bye"] = "🔄 Riavvio in corso…" if restart else "⏹ Bot arrestato."
    await manager.switch_to(AdminSG.bye)
    await manager.show()  # now: stopping closes the bot's session
    manager.show_mode = ShowMode.NO_UPDATE
    logger.info("%s requested by admin %s", "Restart" if restart else "Stop", query.from_user.id)
    app_of(manager).request_stop(RESTART if restart else 0)


async def bye_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    return {"bye": dialog_manager.dialog_data.get("bye", "")}


def _back(state: State, id: str) -> SwitchTo:
    return SwitchTo(Const("↩️ Indietro"), id=id, state=state)


TO_MAIN = _back(AdminSG.main, "to_main")
TO_NOTIFY = _back(AdminSG.notify, "to_notify")
TO_SYSTEM = _back(AdminSG.system, "to_system")
FLASH = Format("\n{flash}", when="flash")

dialog = Dialog(
    Window(
        Const("🔓 <b>Admin</b>\n\nScegli cosa gestire."),
        Start(Format("📝 Registrazioni ({pending})"), id="registrations", state=RegistrationsSG.list),
        Row(
            SwitchTo(Const("👥 Studenti"), id="students", state=AdminSG.students),
            SwitchTo(Const("📣 Notifiche"), id="notify", state=AdminSG.notify),
        ),
        Row(
            Start(Const("🍽 Mensa"), id="meals", state=meals.MealsSG.admin),
            Start(Const("🗓 Calendario"), id="calendar", state=calendar.CalendarSG.admin),
        ),
        SwitchTo(Const("🛠 Sistema"), id="system", state=AdminSG.system),
        BACK,
        state=AdminSG.main,
        getter=main_getter,
    ),
    # Students
    Window(
        Format("👥 <b>Studenti</b>\n\n{count} {status}, gruppo {group}."),
        Format("🔎 Cognome con «{search}»", when="search"),
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
            Button(Format("🔁 Stato: {status}"), id="status_filter", on_click=on_status_filter),
            SwitchTo(Format("👥 Gruppo: {group}"), id="group_filter", state=AdminSG.students_group),
        ),
        Button(Const("✖️ Annulla ricerca"), id="clear_search", on_click=on_clear_search, when="search"),
        TextInput(id="search", on_success=on_search),
        TO_MAIN,
        state=AdminSG.students,
        getter=students_getter,
    ),
    Window(
        Const("👥 <b>Gruppo</b>\n\nScegli il gruppo da mostrare."),
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
            "👤 <b>{name} {surname}</b>\n\n"
            "Genere: {gender}\n"
            "Ingresso: {year}\n"
            "Stato: {status}\n"
            "Gruppi: <i>{groups}</i>",
            when="found",
        ),
        Const("⚠️ Utente non trovato.", when=lambda d, w, m: not d["found"]),
        Group(
            Row(
                Button(Const("◀️ Anno"), id="year_dec", on_click=on_year),
                Button(Const("Anno ▶️"), id="year_inc", on_click=on_year),
                Button(Const("⚧ Genere"), id="gender", on_click=on_gender),
            ),
            SwitchTo(Const("👥 Gruppi"), id="to_groups", state=AdminSG.student_groups),
            Button(Format("{toggle}"), id="toggle_status", on_click=on_toggle_status),
            SwitchTo(Const("🗑 Elimina"), id="to_delete", state=AdminSG.student_delete),
            when="found",
        ),
        _back(AdminSG.students, "to_list"),
        state=AdminSG.student,
        getter=student_getter,
    ),
    Window(
        Format("👥 <b>Gruppi di {name}</b>\n\nTocca un gruppo per aggiungerlo o toglierlo."),
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
        _back(AdminSG.student, "groups_done"),
        state=AdminSG.student_groups,
        getter=student_groups_getter,
    ),
    Window(
        Format(
            "🗑 <b>Elimina utente</b>\n\nVuoi eliminare <b>{name} {surname}</b>? Non si può annullare.",
            when="found",
        ),
        Button(Const("✅ Conferma"), id="delete", on_click=on_delete, when="found"),
        SwitchTo(Const("✖️ Annulla"), id="keep", state=AdminSG.student),
        state=AdminSG.student_delete,
        getter=student_getter,
    ),
    # Notifications
    Window(
        Const("📣 <b>Notifiche</b>\n\nScrivi una notifica, annuncia un aggiornamento o ritira una notifica inviata."),
        FLASH,
        Button(Const("✏️ Nuova notifica"), id="new_notification", on_click=on_new_notification),
        SwitchTo(Const("🆕 Annuncia aggiornamento"), id="to_update", state=AdminSG.update),
        SwitchTo(Const("📬 Notifiche attive"), id="to_active", state=AdminSG.active),
        TO_MAIN,
        state=AdminSG.notify,
        getter=flash_getter,
    ),
    Window(
        Const("✏️ <b>Nuova notifica</b>\n\nScrivi il testo. Grassetto, corsivo e link restano."),
        ERROR,
        MessageInput(on_notification_text, content_types=ContentType.TEXT),
        TO_NOTIFY,
        state=AdminSG.notify_text,
        getter=notify_text_getter,
    ),
    Window(
        Format("📣 <b>Nuova notifica</b>\n\n{summary}\n\nScegli destinatari e opzioni, poi apri l'anteprima."),
        SwitchTo(Format("👥 Destinatari ({groups_count})"), id="to_targets", state=AdminSG.notify_groups),
        Row(
            Checkbox(Const("🔔 Con suono"), Const("🔕 Silenziosa"), id="push", default=True),
            Checkbox(Const("✅ Apri il bot"), Const("⬜ Apri il bot"), id="open_bot"),
        ),
        Radio(
            Format("🔘 {item[1]}"),
            Format("{item[1]}"),
            id="expiry",
            item_id_getter=lambda item: item[0],
            items="items_expiry",
        ),
        Row(
            SwitchTo(Const("✏️ Modifica testo"), id="edit_text", state=AdminSG.notify_text),
            SwitchTo(Const("👀 Anteprima"), id="to_preview", state=AdminSG.notify_preview, when="has_groups"),
        ),
        TO_NOTIFY,
        state=AdminSG.notify_options,
        getter=notify_options_getter,
    ),
    Window(
        Const("👥 <b>Destinatari</b>\n\nScegli almeno un gruppo."),
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
        _back(AdminSG.notify_options, "targets_done"),
        state=AdminSG.notify_groups,
        getter=notify_groups_getter,
    ),
    Window(
        Format("{text}\n\n—— fine notifica ——\n\n{summary}\nUtenti raggiunti: {recipients}"),
        Button(Const("📤 Invia"), id="send", on_click=on_send_notification, when="has_groups"),
        SwitchTo(Const("✏️ Modifica"), id="back_options", state=AdminSG.notify_options),
        state=AdminSG.notify_preview,
        getter=notify_options_getter,
    ),
    Window(
        Format("{text}\n\n—— fine notifica ——\n\nInvio silenzioso a {recipients} utenti attivi."),
        Button(Const("📤 Invia"), id="send_update", on_click=on_send_update),
        TO_NOTIFY,
        state=AdminSG.update,
        getter=update_getter,
    ),
    # Active notifications
    Window(
        Const("📬 <b>Notifiche attive</b>\n"),
        Const("Tocca una notifica per vederla o ritirarla.", when="count"),
        Const("✅ Nessuna notifica in invio o da ritirare.", when=lambda d, w, m: not d["count"]),
        FLASH,
        ScrollingGroup(
            Select(
                Format("{item[1]}"),
                id="notification",
                item_id_getter=lambda item: item[0],
                items="notifications",
                type_factory=int,
                on_click=on_active,
            ),
            id="active_scroll",
            width=1,
            height=8,
            hide_on_single_page=True,
        ),
        TO_NOTIFY,
        state=AdminSG.active,
        getter=active_getter,
    ),
    Window(
        Format(
            "📬 <b>{title}</b>\n\n"
            "Tipo: <code>{kind}</code> · rif. <code>{ref}</code>\n"
            "Creata: {created} · scadenza: {expires}\n"
            "Messaggi: {counts}\n\n"
            "<blockquote>{text}</blockquote>",
            when="found",
        ),
        Const("⚠️ Notifica non più attiva.", when=lambda d, w, m: not d["found"]),
        SwitchTo(Const("🗑 Ritira"), id="to_retract", state=AdminSG.active_retract, when="found"),
        _back(AdminSG.active, "to_active_list"),
        state=AdminSG.active_detail,
        getter=active_detail_getter,
    ),
    Window(
        Const("🗑 <b>Ritira notifica</b>\n\nVuoi ritirarla per tutti? I messaggi già inviati vengono eliminati."),
        Button(Const("✅ Conferma"), id="retract", on_click=on_retract),
        SwitchTo(Const("✖️ Annulla"), id="keep_notification", state=AdminSG.active_detail),
        state=AdminSG.active_retract,
    ),
    # System
    Window(
        Format("🛠 <b>Sistema</b>\n\nVersione {version}, attivo da {uptime}."),
        Row(
            SwitchTo(Const("⚠️ Errori recenti"), id="errors", state=AdminSG.errors),
            SwitchTo(Const("📜 Log recenti"), id="logs", state=AdminSG.logs),
        ),
        Row(
            SwitchTo(Const("ℹ️ Info"), id="info", state=AdminSG.info),
            SwitchTo(Const("⏰ Job pianificati"), id="jobs", state=AdminSG.jobs),
        ),
        Row(
            SwitchTo(Const("🔄 Riavvia bot"), id="restart", state=AdminSG.restart),
            SwitchTo(Const("⏹ Arresta bot"), id="shutdown", state=AdminSG.shutdown),
        ),
        SwitchTo(Const("🗄 Legacy"), id="legacy", state=AdminSG.legacy),
        TO_MAIN,
        state=AdminSG.system,
        getter=system_getter,
    ),
    Window(
        Const("⚠️ <b>Errori recenti</b>\n"),
        Const("Tocca un errore per vederne il dettaglio.", when="count"),
        Const("✅ Nessun errore dall'avvio.", when=lambda d, w, m: not d["count"]),
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
        TO_SYSTEM,
        state=AdminSG.errors,
        getter=errors_getter,
    ),
    Window(
        Format("{detail}"),
        _back(AdminSG.errors, "to_errors"),
        state=AdminSG.error,
        getter=error_getter,
    ),
    Window(
        Format("📜 <b>Log recenti</b>, dal più nuovo\n\n<pre>{log}</pre>"),
        StubScroll(id="log_scroll", pages="pages"),
        Row(
            PrevPage(scroll="log_scroll", text=Const("◀️")),
            CurrentPage(scroll="log_scroll", text=Format("{current_page1}/{pages}")),
            NextPage(scroll="log_scroll", text=Const("▶️")),
            when=lambda d, w, m: d["pages"] > 1,
        ),
        Button(Const("🔄 Aggiorna"), id="refresh_logs", on_click=on_refresh_logs),
        TO_SYSTEM,
        state=AdminSG.logs,
        getter=logs_getter,
    ),
    Window(
        Format(
            "ℹ️ <b>Info</b>\n\n"
            "Versione: <code>{version}</code> · ambiente: <code>{env}</code>\n"
            "Avviato: {started} ({uptime} fa)\n"
            "Database: {size}\n"
            "Notifiche in coda: {pending}\n\n"
            "Utenti:\n{users}"
        ),
        TO_SYSTEM,
        state=AdminSG.info,
        getter=info_getter,
    ),
    Window(
        Const("⏰ <b>Job pianificati</b>\n\nOgni job con la prossima esecuzione. Tocca un job per eseguirlo subito."),
        FLASH,
        Group(
            Select(
                Format("{item[1]}"),
                id="job",
                item_id_getter=lambda item: item[0],
                items="jobs",
                on_click=on_job,
            ),
            width=1,
        ),
        TO_SYSTEM,
        state=AdminSG.jobs,
        getter=jobs_getter,
    ),
    Window(
        Format(
            "⏰ <b>{label}</b>\n\nProssima esecuzione: {next}\nPianificazione: <code>{trigger}</code>", when="found"
        ),
        Const("⚠️ Job non trovato.", when=lambda d, w, m: not d["found"]),
        SwitchTo(Const("▶️ Esegui ora"), id="to_run", state=AdminSG.job_run, when="found"),
        _back(AdminSG.jobs, "to_jobs"),
        state=AdminSG.job,
        getter=job_getter,
    ),
    Window(
        Format(
            "▶️ <b>Esegui ora</b>\n\nVuoi eseguire subito «{label}»? Le esecuzioni pianificate restano.", when="found"
        ),
        Button(Const("✅ Conferma"), id="run_job", on_click=on_run_job, when="found"),
        SwitchTo(Const("✖️ Annulla"), id="keep_job", state=AdminSG.job),
        state=AdminSG.job_run,
        getter=job_getter,
    ),
    Window(
        Const(
            "🔄 <b>Riavvia bot</b>\n\n"
            "Il bot si chiude e riparte da solo in pochi secondi. I menu aperti scadono, "
            "le notifiche in coda partono dopo il riavvio."
        ),
        Button(Const("✅ Conferma"), id="do_restart", on_click=on_stop),
        SwitchTo(Const("✖️ Annulla"), id="keep_running", state=AdminSG.system),
        state=AdminSG.restart,
    ),
    Window(
        Const(
            "⏹ <b>Arresta bot</b>\n\n"
            "Il bot si ferma e non risponde più a nessuno, e i job pianificati non partono.\n"
            "⚠️ Dopo l'arresto si può riavviare solo dal server (<code>systemctl start ghislieri</code>)."
        ),
        Button(Const("✅ Conferma"), id="do_shutdown", on_click=on_stop),
        SwitchTo(Const("✖️ Annulla"), id="keep_on", state=AdminSG.system),
        state=AdminSG.shutdown,
    ),
    Window(Format("{bye}"), state=AdminSG.bye, getter=bye_getter),
    Window(
        Const("🗄 <b>Legacy</b>\n\nFunzioni mantenute ma non più in uso, visibili solo agli admin."),
        Start(Const("🖨 Stampa"), id="printing", state=printing.PrintingSG.main),
        TO_SYSTEM,
        state=AdminSG.legacy,
    ),
)
dialog.callback_query.filter(admin_filter)
dialog.message.filter(admin_filter)
