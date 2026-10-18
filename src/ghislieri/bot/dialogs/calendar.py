"""College calendar: day view, event details, new/edit/delete events, website sync."""

import datetime as dt
import re
from urllib.parse import urlsplit

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import ManagedTextInput, TextInput
from aiogram_dialog.widgets.kbd import Button, Row, Select, SwitchTo, Url
from aiogram_dialog.widgets.text import Const, Format

from ... import clock, events, users
from ...clock import MONTHS, WEEKDAYS, day_label
from ..common import BACK, ERROR, ItalianCalendar, app_of, esc, input_error, perm, tidy_input, user_of

ACCESS = None


class CalendarSG(StatesGroup):
    main = State()
    admin = State()  # entry point linked from the admin menu
    pick_day = State()
    event = State()
    delete = State()
    klass = State()
    cats = State()
    title = State()
    description = State()
    url = State()
    date = State()
    time = State()
    recap = State()


# Formatting


def _short(moment: dt.datetime) -> str:
    """ "gio 03 dic 2026, 21:00"."""
    return f"{WEEKDAYS[moment.weekday()][:3]} {moment:%d} {MONTHS[moment.month - 1][:3]} {moment.year}, {moment:%H:%M}"


def _hours(e: events.Event) -> str:
    if e.start.date() == e.end.date():
        return f"{e.start:%H:%M} - {e.end:%H:%M}"
    start, end = (f"{m:%d} {MONTHS[m.month - 1][:3]}, {m:%H:%M}" for m in (e.start, e.end))
    return f"{start} - {end}"


def _categories(keys) -> str:
    return " | ".join(
        f"{events.CATEGORIES[k][1]} {events.CATEGORIES[k][0].lower()}" for k in keys if k in events.CATEGORIES
    )


# Day view and details


def _day(manager: DialogManager) -> dt.date:
    return dt.date.fromisoformat(manager.dialog_data.get("day") or clock.today().isoformat())


def _event(manager: DialogManager) -> events.Event | None:
    """The selected event, if the user may see it (the id may come from crafted callback data)."""
    e, user = events.get(app_of(manager).conn, manager.dialog_data.get("event", 0)), user_of(manager)
    return e if e and user and events.can_see(user, e.cls) else None


async def day_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    user, day = user_of(dialog_manager), _day(dialog_manager)
    found = events.day_events(app_of(dialog_manager).conn, day, user)  # type: ignore[arg-type]
    rows = [
        (e.id, f"{e.symbol}    {f'{e.start:%H:%M}' if e.start.date() == day else '   ➤   '}    {e.title.upper()}")
        for e in found
    ]
    return {"day": day_label(day).capitalize(), "events": rows, "empty": not rows}


async def on_shift(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    step = -1 if button.widget_id == "prev" else 1
    manager.dialog_data["day"] = (_day(manager) + dt.timedelta(days=step)).isoformat()


async def on_pick_day(query: CallbackQuery, widget, manager: DialogManager, day: dt.date) -> None:
    manager.dialog_data["day"] = day.isoformat()
    await manager.switch_to(CalendarSG.main)


async def on_select_event(query: CallbackQuery, widget, manager: DialogManager, item_id: int) -> None:
    manager.dialog_data["event"] = item_id
    await manager.switch_to(CalendarSG.event)


def _can_create(data: dict, widget, manager: DialogManager) -> bool:
    user = user_of(manager)
    return user is not None and user.is_active and bool(events.classes_for(user))


async def event_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    e, user = _event(dialog_manager), user_of(dialog_manager)
    if e is None:
        return {"found": False, "text": "Evento non trovato.", "url": "", "can_edit": False, "title": ""}
    text = f"<b><u>{esc(e.title)}</u></b>\n\n"
    if e.cancelled:
        text += f"{events.CANCELLED_SYMBOL}  <code>EVENTO CANCELLATO</code>  {events.CANCELLED_SYMBOL}\n\n"
    text += f"📅    <code>{day_label(e.start.date()).capitalize()}</code>\n🕔    <code>{_hours(e)}</code>"
    if e.categories:
        text += f"\n\n<i>{esc(_categories(e.categories))}</i>"
    if e.description:
        text += f"\n\n{esc(e.description)}"
    return {
        "found": True,
        "text": text,
        "title": esc(e.title),
        "url": e.url if e.url and e.url.startswith(("https://", "http://")) else "",  # Telegram rejects others
        "can_edit": user is not None and events.can_edit(user, e),
    }


async def on_delete(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    app, e, user = app_of(manager), _event(manager), user_of(manager)
    if e and user and events.can_edit(user, e):
        events.delete(app.conn, e.id)
        events.write_ics(app.conn, app.settings.data_dir)
        await query.answer(f"✅ Evento {e.title[:100]} rimosso!")
    await manager.switch_to(CalendarSG.main)


# New/edit wizard. The event being written lives in dialog_data["form"].


def _form(manager: DialogManager) -> dict:
    return manager.dialog_data["form"]


async def on_new(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    manager.dialog_data["form"] = {
        "id": None,
        "cls": None,
        "categories": [],
        "options": [],
        "title": "",
        "description": "",
        "url": None,
        "start": None,
        "end": None,
        "status": "confirmed",
        "review": False,
    }
    await manager.switch_to(CalendarSG.klass)


async def on_edit(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    e, user = _event(manager), user_of(manager)
    if e is None or user is None or not events.can_edit(user, e):
        return
    # Keep the event's categories even if the editor could not choose them.
    options = set(events.categories_for(user, e.cls)) | set(e.categories)
    manager.dialog_data["form"] = {
        "id": e.id,
        "cls": e.cls,
        "categories": list(e.categories),
        "options": [k for k in events.CATEGORIES if k in options],
        "title": e.title,
        "description": e.description,
        "url": e.url,
        "start": e.start.isoformat(),
        "end": e.end.isoformat(),
        "status": e.status,
        "review": True,
    }
    await manager.switch_to(CalendarSG.recap)


async def class_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    user = user_of(dialog_manager)
    return {"classes": [(c, events.CLASSES[c]) for c in events.classes_for(user)] if user else []}  # type: ignore[arg-type]


async def on_class(query: CallbackQuery, widget, manager: DialogManager, cls: str) -> None:
    user = user_of(manager)
    if user is None or cls not in events.classes_for(user):
        return
    form = _form(manager)
    form.update(cls=cls, options=events.categories_for(user, cls), categories=[])
    await manager.switch_to(CalendarSG.cats)


async def form_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    form = _form(dialog_manager)
    start = form["start"] and dt.datetime.fromisoformat(form["start"])
    end = form["end"] and dt.datetime.fromisoformat(form["end"])
    picked = form["categories"]
    return {
        "editing": form["id"] is not None,
        "new": form["id"] is None,
        "cls": events.CLASSES.get(form["cls"], ""),
        "cats": [
            (k, f"{events.CATEGORIES[k][1]}    {events.CATEGORIES[k][0]}   {'☑️' if k in picked else ''}")
            for k in form["options"]
        ],
        "symbols": "".join(events.CATEGORIES[k][1] for k in picked if k in events.CATEGORIES) or "---",
        "title": esc(form["title"]) or "---",
        "description": esc(form["description"]),
        "url": esc(form["url"] or "---"),
        "start": _short(start) if start else "--:--",
        "end": _short(end) if end else "--:--",
        "status": "🔴  Cancellato" if form["status"] == "cancelled" else "🟢  Confermato",
        "field": "inizio" if dialog_manager.dialog_data.get("field") == "start" else "fine",
        "error": dialog_manager.dialog_data.pop("error", ""),
    }


async def _advance(manager: DialogManager, next_state: State) -> None:
    await manager.switch_to(CalendarSG.recap if _form(manager)["review"] else next_state)


async def on_category(query: CallbackQuery, widget, manager: DialogManager, key: str) -> None:
    form = _form(manager)
    if key in form["options"]:
        picked = set(form["categories"]) ^ {key}
        form["categories"] = [k for k in form["options"] if k in picked]


async def on_categories_done(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    if not _form(manager)["categories"]:
        await query.answer("Aggiungi almeno una categoria")
        return
    await _advance(manager, CalendarSG.title)


def _title(text: str) -> str:
    value = " ".join(text.split())
    if not 0 < len(value) <= events.MAX_TITLE:
        raise ValueError(text)
    return value


def _description(text: str) -> str:
    value = text.strip()
    if len(value) > events.MAX_DESCRIPTION:
        raise ValueError(text)
    return value


def _url(text: str) -> str:
    value = text.strip()
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc or len(value) > 500 or " " in value:
        raise ValueError(text)
    return value


def _time(text: str) -> dt.time:
    match = re.fullmatch(r"(\d{1,2})(?:[:.](\d{2}))?", text.strip())
    if not match:
        raise ValueError(text)
    return dt.time(int(match[1]), int(match[2] or 0))  # raises ValueError if out of range


NEXT = {"title": CalendarSG.description, "description": CalendarSG.date, "url": CalendarSG.recap}


async def on_text(message: Message, widget: ManagedTextInput, manager: DialogManager, value) -> None:
    await tidy_input(message, manager)
    _form(manager)[widget.widget.widget_id] = value
    await _advance(manager, NEXT[widget.widget.widget_id])


async def on_clear(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    """ "No description" / "no link" buttons."""
    field = button.widget_id.removeprefix("no_")
    _form(manager)[field] = "" if field == "description" else None
    await _advance(manager, NEXT[field])


async def on_pick_field(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    manager.dialog_data["field"] = button.widget_id.removeprefix("edit_")
    await manager.switch_to(CalendarSG.date)


async def on_pick_date(query: CallbackQuery, widget, manager: DialogManager, day: dt.date) -> None:
    manager.dialog_data["date"] = day.isoformat()
    await manager.switch_to(CalendarSG.time)


async def on_time(message: Message, widget: ManagedTextInput, manager: DialogManager, value: dt.time) -> None:
    await tidy_input(message, manager)
    form, field = _form(manager), manager.dialog_data.get("field", "start")
    moment = dt.datetime.combine(dt.date.fromisoformat(manager.dialog_data["date"]), value, clock.TZ)
    form[field] = moment.isoformat()
    if field == "start" and (not form["end"] or dt.datetime.fromisoformat(form["end"]) <= moment):
        form["end"] = (moment + events.DEFAULT_DURATION).isoformat()
    form["review"] = True
    await manager.switch_to(CalendarSG.recap)


async def on_status(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    form = _form(manager)
    form["status"] = "confirmed" if form["status"] == "cancelled" else "cancelled"


async def on_save(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    app, user, form = app_of(manager), user_of(manager), _form(manager)
    if user is None:
        return
    if form["id"] is None:
        allowed = form["cls"] in events.classes_for(user)
    else:
        e = events.get(app.conn, form["id"])
        allowed = e is not None and events.can_edit(user, e)
    if not allowed or not set(form["categories"]) <= set(form["options"]):
        await query.answer("Non hai i permessi per questo evento", show_alert=True)
        await manager.switch_to(CalendarSG.main)
        return
    start = form["start"] and dt.datetime.fromisoformat(form["start"])
    end = form["end"] and dt.datetime.fromisoformat(form["end"])
    error = events.validate(form["title"], start, end, form["categories"])
    if error:
        manager.dialog_data["error"] = f"⚠️ {error}"
        return
    fields = dict(title=form["title"], description=form["description"], url=form["url"], start=start, end=end)
    if form["id"] is None:
        event_id = events.create(app.conn, **fields, cls=form["cls"], categories=form["categories"], creator_id=user.id)
        await query.answer("✅ Evento aggiunto!")
    else:
        event_id = form["id"]
        events.update(app.conn, event_id, **fields, categories=form["categories"], status=form["status"])
        await query.answer("✅ Evento aggiornato!")
    events.write_ics(app.conn, app.settings.data_dir)
    manager.dialog_data.update(event=event_id, day=start.date().isoformat())  # type: ignore[union-attr]
    await manager.switch_to(CalendarSG.event)


# Where "back" leads while filling in a new event (once on the recap, it leads back there).
PREVIOUS = {
    CalendarSG.cats.state: CalendarSG.klass,
    CalendarSG.title.state: CalendarSG.cats,
    CalendarSG.description.state: CalendarSG.title,
    CalendarSG.date.state: CalendarSG.description,
    CalendarSG.url.state: CalendarSG.recap,
}


async def on_form_back(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    await _advance(manager, PREVIOUS[manager.current_context().state.state])


FORM_BACK = Button(Const("↩️ Indietro"), id="form_back", on_click=on_form_back)


async def on_cancel_form(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    await manager.switch_to(CalendarSG.main if _form(manager)["id"] is None else CalendarSG.event)


# Admin

SYNC_NOW = "calendar_sync_now"  # job id


async def on_sync(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    app = app_of(manager)
    if events.syncing or app.scheduler.get_job(SYNC_NOW):
        await query.answer("⏳ Aggiornamento già in corso.")
        return
    # Run in the scheduler: the sync takes a while, and failures get logged and alerted like the nightly run.
    app.scheduler.add_job(events.sync_job, args=[app, query.from_user.id], id=SYNC_NOW)
    await query.answer("🔄 Aggiornamento avviato: riceverai un messaggio al termine.")


async def admin_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    row = (
        app_of(dialog_manager)
        .conn.execute("SELECT count(*) AS n, max(updated_at) AS last FROM events WHERE source = 'rss'")
        .fetchone()
    )
    last = clock.parse(row["last"]).astimezone(clock.TZ) if row["last"] else None
    return {"rss": row["n"], "last": _short(last) if last else "mai"}


dialog = Dialog(
    Window(
        Format("📅    <b>{day}</b>"),
        Const("\nNessun evento programmato", when="empty"),
        Select(
            Format("{item[1]}"),
            id="ev",
            item_id_getter=lambda item: item[0],
            items="events",
            type_factory=int,
            on_click=on_select_event,
        ),
        Row(
            Button(Const("◀"), id="prev", on_click=on_shift),
            SwitchTo(Const("📆 Vai alla data"), id="to_pick_day", state=CalendarSG.pick_day),
            Button(Const("▶"), id="next", on_click=on_shift),
        ),
        Button(Const("🆕    Nuovo evento"), id="new", on_click=on_new, when=_can_create),
        BACK,
        state=CalendarSG.main,
        getter=day_getter,
    ),
    Window(
        Const("🗓️    <b>Admin Calendario</b>"),
        Format("\nEventi dal sito: {rss}\nUltima modifica dal sito: {last}"),
        Button(Const("🔄 Aggiorna dal sito"), id="sync", on_click=on_sync, when=perm(users.ADMIN)),
        BACK,
        state=CalendarSG.admin,
        getter=admin_getter,
    ),
    Window(
        Const("📅️    Scegli la <b>data</b> da visualizzare"),
        ItalianCalendar(id="day_picker", on_click=on_pick_day),
        SwitchTo(Const("↩️ Indietro"), id="pick_back", state=CalendarSG.main),
        state=CalendarSG.pick_day,
    ),
    Window(
        Format("{text}"),
        Url(Const("🔗    Visita link"), Format("{url}"), when="url"),
        Row(
            Button(Const("✏️    Modifica"), id="edit", on_click=on_edit),
            SwitchTo(Const("🗑️    Elimina"), id="to_delete", state=CalendarSG.delete),
            when="can_edit",
        ),
        SwitchTo(Const("↩️ Indietro"), id="event_back", state=CalendarSG.main),
        state=CalendarSG.event,
        getter=event_getter,
    ),
    Window(
        Format("🗑❓    Vuoi davvero <b>eliminare</b> l'evento <b>{title}</b>?"),
        Row(
            Button(Const("✔️"), id="delete", on_click=on_delete, when="can_edit"),
            SwitchTo(Const("❌"), id="delete_no", state=CalendarSG.event),
        ),
        state=CalendarSG.delete,
        getter=event_getter,
    ),
    Window(
        Const("🆕    Seleziona la <b>classe</b> dell'evento"),
        Select(Format("{item[1]}"), id="cls", item_id_getter=lambda item: item[0], items="classes", on_click=on_class),
        SwitchTo(Const("↩️ Indietro"), id="cls_back", state=CalendarSG.main),
        state=CalendarSG.klass,
        getter=class_getter,
    ),
    Window(
        Const("#️⃣    Seleziona le <b>categorie</b> dell'evento"),
        Select(Format("{item[1]}"), id="cat", item_id_getter=lambda item: item[0], items="cats", on_click=on_category),
        Row(FORM_BACK, Button(Const("✔️ Avanti"), id="cats_done", on_click=on_categories_done)),
        state=CalendarSG.cats,
        getter=form_getter,
    ),
    Window(
        Const("✏️    Inserisci il <b>titolo</b> dell'evento"),
        ERROR,
        TextInput(
            id="title",
            type_factory=_title,
            on_success=on_text,
            on_error=input_error(f"⚠️ Il titolo deve avere da 1 a {events.MAX_TITLE} caratteri."),
        ),
        FORM_BACK,
        state=CalendarSG.title,
        getter=form_getter,
    ),
    Window(
        Const("✏️    Inserisci la <b>descrizione</b> dell'evento"),
        ERROR,
        TextInput(
            id="description",
            type_factory=_description,
            on_success=on_text,
            on_error=input_error(f"⚠️ La descrizione può avere al massimo {events.MAX_DESCRIPTION} caratteri."),
        ),
        Row(FORM_BACK, Button(Const("⏭ Nessuna descrizione"), id="no_description", on_click=on_clear)),
        state=CalendarSG.description,
        getter=form_getter,
    ),
    Window(
        Const("🔗    Inserisci il <b>link</b> dell'evento"),
        ERROR,
        TextInput(
            id="url",
            type_factory=_url,
            on_success=on_text,
            on_error=input_error("⚠️ Inserisci un link valido che inizi con https://"),
        ),
        Row(FORM_BACK, Button(Const("🗑 Nessun link"), id="no_url", on_click=on_clear)),
        state=CalendarSG.url,
        getter=form_getter,
    ),
    Window(
        Format("📅    Scegli la <b>data di {field}</b> dell'evento"),
        ItalianCalendar(id="date_picker", on_click=on_pick_date),
        FORM_BACK,
        state=CalendarSG.date,
        getter=form_getter,
    ),
    Window(
        Format("🕓️    Scrivi l'<b>orario di {field}</b> dell'evento (es. 21:00)"),
        ERROR,
        TextInput(
            id="time", type_factory=_time, on_success=on_time, on_error=input_error("⚠️ Scrivi l'orario come 21:00.")
        ),
        SwitchTo(Const("📅 Cambia data"), id="time_back", state=CalendarSG.date),
        state=CalendarSG.time,
        getter=form_getter,
    ),
    Window(
        Const("🆕    <b>Nuovo evento</b>", when="new"),
        Const("✏️    <b>Modifica evento</b>", when="editing"),
        Format(
            "\n<b>CLASSE</b>    {cls}\n\n{symbols}    <b>{title}</b>\n\n"
            "<b>Inizio</b>    <code>{start}</code>\n<b>Fine</b>      <code>{end}</code>\n\n"
            "<i>{description}</i>\n\n<b>Link</b>      {url}"
        ),
        Format("<b>Stato</b>     {status}", when="editing"),
        ERROR,
        Row(
            SwitchTo(Const("✏️ Titolo"), id="edit_title", state=CalendarSG.title),
            SwitchTo(Const("✏️ Descrizione"), id="edit_description", state=CalendarSG.description),
        ),
        Row(
            Button(Const("🕓 Inizio"), id="edit_start", on_click=on_pick_field),
            Button(Const("🕓 Fine"), id="edit_end", on_click=on_pick_field),
        ),
        Row(
            SwitchTo(Const("🔗 Link"), id="edit_url", state=CalendarSG.url),
            SwitchTo(Const("#️⃣ Categorie"), id="edit_cats", state=CalendarSG.cats),
        ),
        Button(Format("🚦 Stato: {status}"), id="status", on_click=on_status, when="editing"),
        Row(
            Button(Const("❌ Annulla"), id="cancel", on_click=on_cancel_form),
            Button(Const("➕ Aggiungi"), id="add", on_click=on_save, when="new"),
            Button(Const("✅ Salva"), id="save", on_click=on_save, when="editing"),
        ),
        state=CalendarSG.recap,
        getter=form_getter,
    ),
)
