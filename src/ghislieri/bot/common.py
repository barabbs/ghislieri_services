"""Helpers shared by all dialogs."""

import contextlib
import html

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.kbd import Cancel, Keyboard, Start
from aiogram_dialog.widgets.text import Const

from .. import users
from ..app import App


class HomeSG(StatesGroup):
    main = State()


def app_of(manager: DialogManager) -> App:
    return manager.middleware_data["app"]


def user_of(manager: DialogManager) -> users.User | None:
    """The user behind the current update (loaded once per update by UserMiddleware)."""
    if "user" in manager.middleware_data:
        return manager.middleware_data["user"]
    tg_user = manager.middleware_data.get("event_from_user")
    if tg_user is None:
        return None
    return users.get(app_of(manager).conn, tg_user.id)


def esc(value: object) -> str:
    """Escape any user- or feed-provided value before putting it into an HTML message."""
    return html.escape(str(value), quote=False)


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
HOME = Start(Const("🏠 Home"), id="home", state=HomeSG.main, mode=StartMode.RESET_STACK)


async def tidy_input(message: Message, manager: DialogManager) -> None:
    """Delete the user's message and edit the menu in place, so the chat holds one live message."""
    with contextlib.suppress(TelegramBadRequest):
        await message.delete()
    manager.show_mode = ShowMode.EDIT


def person_name(text: str) -> str:
    """TextInput type_factory for names: trimmed, 1-60 characters, letters and a few separators."""
    value = " ".join(text.split())
    if not 0 < len(value) <= 60 or not all(c.isalpha() or c in " '-." for c in value):
        raise ValueError(text)
    return value
