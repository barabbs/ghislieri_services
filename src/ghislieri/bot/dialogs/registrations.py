"""Admin review of pending registrations."""

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Back, Button, Row, ScrollingGroup, Select, SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from ... import users
from ...notify import Button as NotifButton
from ..common import BACK, HomeSG, admin_filter, app_of, esc

ACCESS = users.ADMIN


class RegistrationsSG(StatesGroup):
    list = State()
    detail = State()
    reject = State()


def _pending(manager: DialogManager) -> users.User | None:
    user = users.get(app_of(manager).conn, manager.dialog_data.get("uid", 0))
    return user if user and user.status == "pending" else None


async def list_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    pending = users.list_users(app_of(dialog_manager).conn, status="pending")
    return {"pending": [(u.id, f"{u.surname} {u.name}") for u in pending], "count": len(pending)}


async def detail_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    user = _pending(dialog_manager)
    if user is None:
        return {"found": False, "name": "", "gender": "", "year": ""}
    return {
        "found": True,
        "name": esc(user.full_name),
        "gender": users.GENDERS.get(user.gender or "", "non indicato"),
        "year": users.year_label(user.enrollment_year),
    }


async def on_select(query: CallbackQuery, widget, manager: DialogManager, item_id: str) -> None:
    manager.dialog_data["uid"] = int(item_id)
    await manager.switch_to(RegistrationsSG.detail)


async def on_year(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    user = _pending(manager)
    if user and user.enrollment_year:
        step = -1 if button.widget_id == "year_dec" else 1
        users.update_profile(app_of(manager).conn, user.id, enrollment_year=user.enrollment_year + step)


async def on_gender(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    user = _pending(manager)
    if user:
        users.update_profile(app_of(manager).conn, user.id, gender="F" if user.gender == "M" else "M")


async def on_decide(query: CallbackQuery, button: Button, manager: DialogManager) -> None:
    """Approve as student or alumnus, or reject (the account is deleted)."""
    groups = {"approve_student": (users.STUDENT,), "approve_alumnus": (users.ALUMNUS,)}.get(button.widget_id)
    app, user = app_of(manager), _pending(manager)
    if user is None:
        await query.answer("Registrazione già gestita")
    elif groups is None:
        users.delete(app.conn, user.id)
        app.notifier.send(
            [user.id],
            "❌ La tua registrazione non è stata approvata. Per chiarimenti contatta la segreteria.",
            kind="signup_result",
        )
        await query.answer(f"Registrazione di {user.full_name} rifiutata")
    else:
        users.approve(app.conn, user.id, groups)
        app.notifier.send(
            [user.id],
            "✅ La tua registrazione è stata approvata! Benvenuto/a.",
            kind="signup_result",
            buttons=[NotifButton("🏠 Apri il menu", HomeSG.main.state)],
        )
        await query.answer(f"{user.full_name} approvato/a")
    if user:
        app.notifier.retract("registration", str(user.id))
    await manager.switch_to(RegistrationsSG.list)


dialog = Dialog(
    Window(
        Format("📝 <b>Registrazioni in attesa</b>: {count}"),
        Const("Nessuna registrazione da gestire.", when=lambda d, w, m: d["count"] == 0),
        ScrollingGroup(
            Select(
                Format("{item[1]}"),
                id="user",
                item_id_getter=lambda item: item[0],
                items="pending",
                type_factory=int,
                on_click=on_select,
            ),
            id="pending_scroll",
            width=1,
            height=8,
            hide_on_single_page=True,
        ),
        BACK,
        state=RegistrationsSG.list,
        getter=list_getter,
    ),
    Window(
        Format("👤 <b>{name}</b>\nGenere: {gender}\nAnno di ingresso: {year}", when="found"),
        Const("Registrazione già gestita.", when=lambda d, w, m: not d["found"]),
        Row(
            Button(Const("◀ anno"), id="year_dec", on_click=on_year),
            Button(Const("anno ▶"), id="year_inc", on_click=on_year),
            Button(Const("⚧ genere"), id="gender", on_click=on_gender),
            when="found",
        ),
        Button(Const("✅ Approva come studente"), id="approve_student", on_click=on_decide, when="found"),
        Button(Const("🎓 Approva come alumnus"), id="approve_alumnus", on_click=on_decide, when="found"),
        SwitchTo(Const("❌ Rifiuta"), id="to_reject", state=RegistrationsSG.reject, when="found"),
        SwitchTo(Const("↩️ Elenco"), id="to_list", state=RegistrationsSG.list),
        state=RegistrationsSG.detail,
        getter=detail_getter,
    ),
    Window(
        Format("Rifiutare ed eliminare la registrazione di <b>{name}</b>?"),
        Button(Const("❌ Sì, rifiuta"), id="reject", on_click=on_decide),
        Back(Const("↩️ No")),
        state=RegistrationsSG.reject,
        getter=detail_getter,
    ),
)
dialog.callback_query.filter(admin_filter)
dialog.message.filter(admin_filter)
