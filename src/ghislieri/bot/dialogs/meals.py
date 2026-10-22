"""Canteen: meal bookings and reports; day management for admins."""

import datetime as dt
import logging

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, ContentType, Message
from aiogram_dialog import Dialog, DialogManager, ShowMode, Window
from aiogram_dialog.widgets.input import ManagedTextInput, MessageInput, TextInput
from aiogram_dialog.widgets.kbd import Button, Column, ScrollingGroup, Select, Start, SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from ... import clock, meals, users
from ...clock import day_label
from ..common import (
    BACK,
    ERROR,
    ItalianCalendar,
    app_of,
    clear_photos,
    collect_photo,
    esc,
    input_error,
    perm,
    text_of,
    tidy_input,
    user_of,
)

log = logging.getLogger(__name__)

ACCESS = users.STUDENT
ADMIN_ONLY = perm(users.ADMIN)

ICONS = {True: "🟢", False: "🔴", None: "❔"}
MAX_REPORT_LEN = 2000  # keeps the admin notification under Telegram's 4096 characters


class MealsSG(StatesGroup):
    main = State()
    report_text = State()
    report_photos = State()
    report_confirm = State()
    report_done = State()
    admin = State()  # entry point linked from the admin menu
    admin_add = State()
    admin_day = State()
    admin_remove = State()


# Bookings


async def main_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    app, user = app_of(dialog_manager), user_of(dialog_manager)
    items = []
    for day in meals.open_days(app.conn):
        answers = meals.answers(app.conn, user.id, day) if user else {}
        for meal in meals.MEALS:
            label = f"{day_label(day, short=True)} · {meals.MEAL_NAMES[meal]} {ICONS[answers.get(meal)]}"
            items.append((f"{day.isoformat()}_{meal}", label))
    return {"meals": items, "any_open": bool(items)}


async def on_meal(query: CallbackQuery, widget, manager: DialogManager, item_id: str) -> None:
    app, uid = app_of(manager), query.from_user.id
    day_text, _, meal = item_id.partition("_")
    try:
        day = dt.date.fromisoformat(day_text)
    except ValueError:
        return
    if meals.toggle(app.conn, day, meal, uid) is None:
        await query.answer("⏰ Le prenotazioni per questo giorno sono chiuse.", show_alert=True)
    elif meals.answered_all(app.conn, uid, day):
        app.notifier.retract("meal_reminder", day.isoformat(), uid)


# Reports


async def on_report_text(message: Message, widget: ManagedTextInput, manager: DialogManager, value: str) -> None:
    manager.dialog_data["report"] = value
    await tidy_input(message, manager)
    await manager.switch_to(MealsSG.report_photos)


async def report_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    data = dialog_manager.dialog_data
    return {
        "error": data.pop("error", ""),
        "report": esc(data.get("report", "")),
        "photos": len(data.get("photos", [])),
        "result": data.get("result", ""),
    }


async def on_send_report(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    app, user, data = app_of(manager), user_of(manager), manager.dialog_data
    if user is None or "report" not in data:
        return
    text, photos = data.pop("report"), data.pop("photos", [])
    try:
        await meals.submit_report(app, user, text, photos)
        data["result"] = "✅ Segnalazione inviata. Grazie!"
    except Exception:
        log.exception("Sending the meal report of %s failed", user.id)
        data["result"] = "⚠️ Segnalazione inoltrata ai responsabili, ma l'email non è stata inviata."
    await manager.switch_to(MealsSG.report_done)


async def on_cancel_report(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    manager.dialog_data.clear()


# Admin


def _chosen_day(manager: DialogManager) -> dt.date | None:
    day = manager.dialog_data.get("day")
    return dt.date.fromisoformat(day) if day else None


async def admin_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    days = meals.summaries(app_of(dialog_manager).conn, clock.today())
    items = [
        (
            s.day.isoformat(),
            f"{day_label(s.day, short=True)} · pranzo {s.booked['lunch']} · cena {s.booked['dinner']}",
        )
        for s in days
    ]
    return {"days": items, "count": len(items)}


async def on_admin_day(query: CallbackQuery, widget, manager: DialogManager, item_id: str) -> None:
    manager.dialog_data["day"] = item_id
    await manager.switch_to(MealsSG.admin_day)


async def on_generate(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    today = clock.today()
    year = clock.academic_year(today)
    added = meals.create_academic_year(app_of(manager).conn, year, today)
    await query.answer(f"✅ Anno {year}/{year + 1}: {len(added)} giorni aggiunti.", show_alert=True)


async def on_add_date(query: CallbackQuery, widget, manager: DialogManager, day: dt.date) -> None:
    if day <= clock.today():
        await query.answer("⚠️ Scegli un giorno futuro.", show_alert=True)
        return
    if meals.add_day(app_of(manager).conn, day):
        opens = meals.opening_date(day)
        await query.answer(f"✅ Aggiunto {day_label(day)}: prenotazioni aperte dal {day_label(opens)}.")
    else:
        await query.answer("⚠️ Giorno già presente.")
    await manager.switch_to(MealsSG.admin)


async def day_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    day = _chosen_day(dialog_manager)
    summary = meals.get_day(app_of(dialog_manager).conn, day) if day else None
    if summary is None:
        return {"found": False, "label": "", "opens": "", "lunch": 0, "dinner": 0, "total": 0}
    return {
        "found": True,
        "label": day_label(summary.day),
        "opens": day_label(summary.opens_on),
        "lunch": summary.booked["lunch"],
        "dinner": summary.booked["dinner"],
        "total": summary.total,
    }


async def on_pdf(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    day, app = _chosen_day(manager), app_of(manager)
    if day is None:
        return
    filename, pdf = await meals.render_recap(app, day)
    await app.bot.send_document(query.from_user.id, BufferedInputFile(pdf, filename=filename))
    manager.show_mode = ShowMode.SEND  # keep the menu below the document


async def on_email(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    day = _chosen_day(manager)
    if day is None:
        return
    try:
        await meals.send_recap(app_of(manager), day)
    except Exception:
        log.exception("Re-sending the meal recap of %s failed", day)
        await query.answer("⚠️ Invio dell'email non riuscito.", show_alert=True)
        return
    await query.answer("✅ Email del recap inviata.")


async def on_remove(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    day, app = _chosen_day(manager), app_of(manager)
    if day:
        meals.remove_day(app.conn, day)
        app.notifier.retract("meal_reminder", day.isoformat())
        await query.answer(f"✅ {day_label(day)} eliminato.")
    await manager.switch_to(MealsSG.admin)


BACK_TO_ADMIN = SwitchTo(Const("↩️ Elenco"), id="to_admin", state=MealsSG.admin)

dialog = Dialog(
    Window(
        Const("🍽️ <b>Mensa</b>\n"),
        Const("Tocca un pasto per indicare se ci sarai:\n🟢 sì · 🔴 no · ❔ da indicare", when="any_open"),
        Const("Al momento non ci sono prenotazioni aperte.", when=lambda d, w, m: not d["any_open"]),
        Column(
            Select(
                Format("{item[1]}"),
                id="meal",
                item_id_getter=lambda item: item[0],
                items="meals",
                on_click=on_meal,
            ),
            when=perm(ACCESS),
        ),
        SwitchTo(Const("📝 Segnalazione"), id="report", state=MealsSG.report_text, when=perm(ACCESS)),
        Start(Const("⚙️ Gestione"), id="manage", state=MealsSG.admin, when=ADMIN_ONLY),
        BACK,
        state=MealsSG.main,
        getter=main_getter,
    ),
    Window(
        Const("📝 <b>Segnalazione mensa</b>\n\nScrivi cosa vuoi segnalare."),
        ERROR,
        TextInput(
            id="report_text",
            type_factory=text_of(MAX_REPORT_LEN),
            on_success=on_report_text,
            on_error=input_error(f"⚠️ La segnalazione deve avere al massimo {MAX_REPORT_LEN} caratteri."),
        ),
        SwitchTo(Const("↩️ Indietro"), id="report_back", state=MealsSG.main, on_click=on_cancel_report),
        state=MealsSG.report_text,
        getter=report_getter,
    ),
    Window(
        Const("📸 Se vuoi, invia una o più <b>foto</b>, poi premi Avanti.\n"),
        Format("Foto allegate: {photos}"),
        ERROR,
        MessageInput(collect_photo(meals.MAX_REPORT_PHOTOS), content_types=ContentType.PHOTO),
        MessageInput(input_error("⚠️ Invia una foto, oppure premi Avanti.")),
        SwitchTo(Const("➡️ Avanti"), id="photos_done", state=MealsSG.report_confirm),
        Button(Const("🗑 Elimina le foto"), id="clear_photos", on_click=clear_photos, when="photos"),
        SwitchTo(Const("↩️ Indietro"), id="photos_back", state=MealsSG.report_text),
        state=MealsSG.report_photos,
        getter=report_getter,
    ),
    Window(
        Format("📝 <b>Segnalazione mensa</b>\n\n{report}\n\n📸 Foto allegate: {photos}\n\nInviare la segnalazione?"),
        Button(Const("📤 Invia"), id="send_report", on_click=on_send_report),
        SwitchTo(Const("✖️ Annulla"), id="cancel_report", state=MealsSG.main, on_click=on_cancel_report),
        SwitchTo(Const("↩️ Indietro"), id="confirm_back", state=MealsSG.report_photos),
        state=MealsSG.report_confirm,
        getter=report_getter,
    ),
    Window(
        Format("{result}"),
        SwitchTo(Const("↩️ Indietro"), id="report_ok", state=MealsSG.main, on_click=on_cancel_report),
        state=MealsSG.report_done,
        getter=report_getter,
    ),
    Window(
        Const("⚙️ <b>Gestione Mensa</b>\n"),
        Format("Giorni prenotabili in programma: {count}\nTocca un giorno per il recap o per eliminarlo."),
        ScrollingGroup(
            Select(
                Format("{item[1]}"),
                id="admin_day",
                item_id_getter=lambda item: item[0],
                items="days",
                on_click=on_admin_day,
            ),
            id="admin_days",
            width=1,
            height=8,
            hide_on_single_page=True,
            when=ADMIN_ONLY,
        ),
        SwitchTo(Const("➕ Aggiungi giorno"), id="add_day", state=MealsSG.admin_add, when=ADMIN_ONLY),
        Button(Const("🗓 Genera anno accademico"), id="generate", on_click=on_generate, when=ADMIN_ONLY),
        BACK,
        state=MealsSG.admin,
        getter=admin_getter,
    ),
    Window(
        Const("➕ <b>Aggiungi giorno</b>\n\nScegli il giorno da rendere prenotabile."),
        ItalianCalendar(id="calendar", on_click=on_add_date, when=ADMIN_ONLY),
        BACK_TO_ADMIN,
        state=MealsSG.admin_add,
    ),
    Window(
        Format(
            "🍽️ <b>{label}</b>\n\nPrenotazioni aperte dal {opens} alle 07:00\nPranzo: {lunch}\nCena: {dinner}",
            when="found",
        ),
        Const("⚠️ Giorno non trovato.", when=lambda d, w, m: not d["found"]),
        Button(Const("📄 Recap PDF"), id="pdf", on_click=on_pdf, when=ADMIN_ONLY),
        Button(Const("✉️ Reinvia email recap"), id="email", on_click=on_email, when=ADMIN_ONLY),
        SwitchTo(Const("🗑 Elimina giorno"), id="to_remove", state=MealsSG.admin_remove, when=ADMIN_ONLY),
        BACK_TO_ADMIN,
        state=MealsSG.admin_day,
        getter=day_getter,
    ),
    Window(
        Format("🗑 Eliminare <b>{label}</b>?"),
        Format("\nVerranno cancellate anche le {total} prenotazioni.", when="total"),
        Button(Const("🗑 Sì, elimina"), id="remove", on_click=on_remove, when=ADMIN_ONLY),
        SwitchTo(Const("↩️ No"), id="keep", state=MealsSG.admin_day),
        state=MealsSG.admin_remove,
        getter=day_getter,
    ),
)
