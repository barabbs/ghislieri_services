"""Telegram front end: aiogram dispatcher, dialogs, entry points and error handling."""

import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, ExceptionTypeFilter
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.types import CallbackQuery, ErrorEvent, Message, TelegramObject
from aiogram_dialog import DialogManager, ShowMode, StartMode, setup_dialogs
from aiogram_dialog.api.exceptions import OutdatedIntent, UnknownIntent, UnknownState
from aiogram_dialog.manager.message_manager import MessageManager

from .. import menus, users
from ..app import App
from ..notify import OpenCallback
from .common import HomeSG, enforce_access_on_press, go_home
from .dialogs import (
    admin,
    calendar,
    channels,
    home,
    meals,
    printing,
    registrations,
    settings,
    signup,
    submissions,
)

log = logging.getLogger(__name__)

# Every dialog module exposes `dialog` and `ACCESS` (group needed to open it; None = any active user).
MODULES = (
    home,
    signup,
    registrations,
    admin,
    calendar,
    meals,
    printing,
    submissions,
    settings,
    channels,
)


class UserMiddleware(BaseMiddleware):
    """Loads the sender's DB record into `data["user"]` and enforces account status."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        app: App = data["app"]
        tg_user = data.get("event_from_user")
        user = users.get(app.conn, tg_user.id) if tg_user else None
        if user and user.status == "blocked":  # they unblocked the bot
            users.set_status(app.conn, user.id, "active")
            user = users.get(app.conn, user.id)
        if user and user.status == "disabled":
            return None
        data["user"] = user
        return await handler(event, data)


def _state_index() -> dict[str, tuple[Any, str | None]]:
    """Maps "SG:state" strings to (State, ACCESS) for notification buttons."""
    index = {}
    for module in MODULES:
        for window in module.dialog.windows.values():
            state = window.get_state()
            index[state.state] = (state, module.ACCESS)
    return index


class TrackingMessageManager:
    """aiogram-dialog's message manager, also remembering each chat's menu message in the DB."""

    def __init__(self, conn, inner):
        self.conn, self.inner = conn, inner

    async def show_message(self, bot, new_message, old_message):
        shown = await self.inner.show_message(bot, new_message, old_message)
        menus.remember(self.conn, shown.chat.id, shown.message_id)
        return shown

    def __getattr__(self, name):
        return getattr(self.inner, name)


def build_dispatcher(app: App, message_manager=None) -> Dispatcher:
    """`message_manager` is replaced only in tests (aiogram_dialog.test_tools.MockMessageManager)."""
    enforce_access_on_press()
    # Isolation: one user's updates are handled one at a time (photo albums, double taps).
    isolation = SimpleEventIsolation()
    dp = Dispatcher(storage=MemoryStorage(), events_isolation=isolation, app=app)
    dp.update.outer_middleware(UserMiddleware())
    # The bot works in private chats only; anything from groups and channels is ignored.
    dp.message.filter(F.chat.type == "private")
    dp.callback_query.filter(F.message.chat.type == "private")
    states = _state_index()

    entry = Router(name="entry")

    async def drop_menu(chat_id: int) -> None:
        """Delete the chat's previous menu (aiogram-dialog no longer knows it after a restart)."""
        if old := menus.forget(app.conn, chat_id):
            await app.notifier.delete_message(chat_id, old)

    @entry.message(CommandStart())
    async def on_start(message: Message, dialog_manager: DialogManager, user: users.User | None):
        with contextlib.suppress(TelegramBadRequest):
            await message.delete()
        await drop_menu(message.chat.id)
        if user is None:
            await dialog_manager.start(
                signup.SignupSG.surname, mode=StartMode.RESET_STACK, show_mode=ShowMode.DELETE_AND_SEND
            )
        elif user.status == "pending":
            await dialog_manager.start(
                signup.SignupSG.waiting, mode=StartMode.RESET_STACK, show_mode=ShowMode.DELETE_AND_SEND
            )
        else:
            await go_home(dialog_manager, ShowMode.DELETE_AND_SEND)

    @entry.callback_query(OpenCallback.filter())
    async def on_open(
        query: CallbackQuery,
        callback_data: OpenCallback,
        dialog_manager: DialogManager,
        user: users.User | None,
    ):
        """A button on a notification: delete the notification, open the dialog in a new message.

        The dialog opens on top of the home menu, so its "back" button leads there.

        Only buttons of a notification actually delivered to this user open anything, so crafted
        callback data cannot reach a dialog the user was not invited to.
        """
        await query.answer()
        if not isinstance(query.message, Message):
            return
        allowed = app.notifier.delivered_buttons(query.from_user.id, query.message.message_id)
        app.notifier.retract_delivery(query.from_user.id, query.message.message_id)
        with contextlib.suppress(TelegramBadRequest):
            await query.message.delete()
        state, access = states.get(callback_data.state, (None, None))
        if (
            state is None
            or callback_data.state not in allowed
            or user is None
            or not user.is_active
            or (access and not user.has(access))
        ):
            return
        await drop_menu(query.from_user.id)
        if state is HomeSG.main:
            await go_home(dialog_manager, ShowMode.DELETE_AND_SEND)
        else:
            await go_home(dialog_manager, ShowMode.NO_UPDATE)
            await dialog_manager.start(state, show_mode=ShowMode.DELETE_AND_SEND)

    fallback = Router(name="fallback")

    @fallback.message()
    async def on_stray_message(message: Message, dialog_manager: DialogManager, user: users.User | None):
        """A message outside any dialog (e.g. after a restart): behave like /start."""
        await on_start(message, dialog_manager, user)

    @fallback.callback_query()
    async def on_stray_callback(query: CallbackQuery, dialog_manager: DialogManager):
        await query.answer("Menu scaduto")
        await drop_menu(query.from_user.id)
        await go_home(dialog_manager, ShowMode.DELETE_AND_SEND)

    @dp.errors(ExceptionTypeFilter(UnknownIntent, OutdatedIntent, UnknownState))
    async def on_stale_menu(event: ErrorEvent, dialog_manager: DialogManager):
        """Buttons of a menu from before a restart: open a fresh home menu."""
        if event.update.callback_query:
            with contextlib.suppress(TelegramBadRequest):
                await event.update.callback_query.answer("Menu scaduto, ecco quello nuovo")
        await go_home(dialog_manager, ShowMode.DELETE_AND_SEND)

    @dp.errors()
    async def on_error(event: ErrorEvent, dialog_manager: DialogManager):
        log.error("Error handling update %s", event.update.update_id, exc_info=event.exception)
        with contextlib.suppress(Exception):
            if event.update.callback_query:
                await event.update.callback_query.answer("⚠️ Qualcosa è andato storto", show_alert=True)
            await go_home(dialog_manager, ShowMode.DELETE_AND_SEND)

    dp.include_router(entry)
    for module in MODULES:
        dp.include_router(module.dialog)
    dp.include_router(fallback)
    setup_dialogs(
        dp,
        message_manager=TrackingMessageManager(app.conn, message_manager or MessageManager()),
        events_isolation=isolation,
    )
    return dp
