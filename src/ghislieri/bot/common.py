"""Helpers shared by all dialogs."""

import contextlib

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.kbd import Calendar, CalendarConfig, CalendarScope, Cancel, Keyboard, Start
from aiogram_dialog.widgets.kbd.calendar_kbd import CalendarDaysView, CalendarMonthView, CalendarYearsView
from aiogram_dialog.widgets.text import Const, Format, Text

from .. import clock, users
from ..app import App
from ..notify import esc as esc  # re-exported for the dialogs


class HomeSG(StatesGroup):
    main = State()


def app_of(manager: DialogManager) -> App:
    return manager.middleware_data["app"]


def user_of(manager: DialogManager) -> users.User | None:
    """The user behind the current update, as loaded by UserMiddleware when the update arrived."""
    return manager.middleware_data.get("user")


def perm(group: str | None):
    """`when=` predicate: show (and accept presses of) a widget only for holders of `group`.

    `None` means any active user. It is also an access check: see `enforce_access_on_press`.
    """

    def predicate(data: dict, widget, manager: DialogManager) -> bool:
        user = user_of(manager)
        return user is not None and user.is_active and (group is None or user.has(group))

    predicate.access_check = True  # type: ignore[attr-defined]
    return predicate


perm_active = perm(None)


def admin_filter(event, user: users.User | None = None) -> bool:
    """Router filter for admin-only dialogs: refuses non-admins, e.g. demoted while the menu is open."""
    return user is not None and user.is_active and user.is_admin


def enforce_access_on_press() -> None:
    """Make aiogram-dialog refuse presses on keyboards hidden by a `perm(...)` condition.

    aiogram-dialog checks `when=` only when drawing the keyboard, not when a callback arrives, and
    a modified client can send the callback data of a hidden button. Every keyboard (including
    groups, whose children are processed through this method) goes through Keyboard.process_callback.
    """
    if getattr(Keyboard.process_callback, "access_checked", False):
        return
    original = Keyboard.process_callback

    async def process_callback(self, callback, dialog, manager):
        if getattr(self.condition, "access_check", False) and not self.condition({}, self, manager):
            return False
        return await original(self, callback, dialog, manager)

    process_callback.access_checked = True  # type: ignore[attr-defined]
    Keyboard.process_callback = process_callback  # type: ignore[method-assign]


async def go_home(manager: DialogManager, show_mode: ShowMode = ShowMode.AUTO) -> None:
    await manager.start(HomeSG.main, mode=StartMode.RESET_STACK, show_mode=show_mode)


BACK = Cancel(Const("↩️ Indietro"))
HOME = Start(Const("🏠 Menu"), id="home", state=HomeSG.main, mode=StartMode.RESET_STACK)


async def tidy_input(message: Message, manager: DialogManager) -> None:
    """Delete the user's message and edit the menu in place, so the chat holds one live message."""
    with contextlib.suppress(TelegramBadRequest):
        await message.delete()
    manager.show_mode = ShowMode.EDIT


ERROR = Format("\n{error}", when="error")  # shows dialog_data["error"], popped by the window's getter


def input_error(text: str):
    """on_error/MessageInput handler: delete the user's message and show `text` in the menu."""

    async def handler(message: Message, widget, manager: DialogManager, *error) -> None:
        await tidy_input(message, manager)
        manager.dialog_data["error"] = text

    return handler


def text_of(limit: int):
    """TextInput type_factory: trimmed, non-empty, at most `limit` characters."""

    def factory(text: str) -> str:
        value = text.strip()
        if not 0 < len(value) <= limit:
            raise ValueError(text)
        return value

    return factory


def collect_photo(limit: int):
    """MessageInput handler adding the photo to dialog_data["photos"] (Telegram file_ids)."""

    async def handler(message: Message, widget, manager: DialogManager) -> None:
        photos = manager.dialog_data.setdefault("photos", [])
        if len(photos) < limit:
            photos.append(message.photo[-1].file_id)  # type: ignore[index]  # largest size
        else:
            manager.dialog_data["error"] = f"⚠️ Puoi allegare al massimo {limit} foto."
        await tidy_input(message, manager)

    return handler


async def clear_photos(query: CallbackQuery, widget, manager: DialogManager) -> None:
    manager.dialog_data.pop("photos", None)


NAME_ERROR = "⚠️ Usa solo lettere, massimo 60 caratteri."


def person_name(text: str) -> str:
    """TextInput type_factory for names: trimmed, 1-60 characters, letters and a few separators."""
    value = " ".join(text.split())
    if not 0 < len(value) <= 60 or not all(c.isalpha() or c in " '-." for c in value):
        raise ValueError(text)
    return value


class _DateText(Text):
    def __init__(self, render):
        super().__init__()
        self.render = render

    async def _render_text(self, data, manager: DialogManager) -> str:
        return self.render(data["date"])


def _month(d) -> str:
    return clock.MONTHS[d.month - 1]


class ItalianCalendar(Calendar):
    """Calendar in Rome time, with Italian month and weekday names (the stock one follows the host locale)."""

    def __init__(self, id: str, on_click, when=None):
        super().__init__(id, on_click=on_click, config=CalendarConfig(timezone=clock.TZ), when=when)  # type: ignore[arg-type]

    def _init_views(self):
        cb = self._item_callback_data
        return {
            CalendarScope.DAYS: CalendarDaysView(
                cb,
                weekday_text=_DateText(lambda d: clock.WEEKDAYS[d.weekday()][:3]),
                header_text=_DateText(lambda d: f"🗓 {_month(d)} {d.year}"),
                next_month_text=_DateText(lambda d: f"{_month(d)} {d.year} >>"),
                prev_month_text=_DateText(lambda d: f"<< {_month(d)} {d.year}"),
            ),
            CalendarScope.MONTHS: CalendarMonthView(
                cb, month_text=_DateText(_month), this_month_text=_DateText(lambda d: f"[ {_month(d)} ]")
            ),
            CalendarScope.YEARS: CalendarYearsView(cb),
        }
