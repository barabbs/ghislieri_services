"""Helpers shared by all dialogs."""

import contextlib
import html

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.kbd import Cancel, Start
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

    `None` means any active user.
    aiogram-dialog ignores presses on hidden widgets, so this is also an access check.
    """

    def predicate(data: dict, widget, manager: DialogManager) -> bool:
        user = user_of(manager)
        return user is not None and user.is_active and (group is None or user.has(group))

    return predicate


def perm_active(data: dict, widget, manager: DialogManager) -> bool:
    """`when=` predicate for widgets every approved user may use."""
    user = user_of(manager)
    return user is not None and user.is_active


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
