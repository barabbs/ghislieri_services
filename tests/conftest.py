import datetime as dt
import itertools
from typing import Any

import pytest
from aiogram.methods import AnswerCallbackQuery, DeleteMessage, SendMessage, TelegramMethod
from aiogram.types import Chat, Message
from aiogram_dialog.test_tools import BotClient, MockMessageManager
from aiogram_dialog.test_tools.bot_client import FakeBot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ghislieri import bot, clock, db, users
from ghislieri.app import App
from ghislieri.notify import Notifier
from ghislieri.settings import Settings


class RecordingBot(FakeBot):
    """Offline bot: records every API call and returns plausible results."""

    def __init__(self):
        self.calls: list[TelegramMethod] = []
        self._ids = itertools.count(1000)

    def sent(self, chat_id: int | None = None) -> list[SendMessage]:
        return [c for c in self.calls if isinstance(c, SendMessage) and chat_id in (None, c.chat_id)]

    async def __call__(self, method: TelegramMethod[Any], request_timeout: int | None = None) -> Any:
        self.calls.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=next(self._ids),
                date=dt.datetime.now(),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text,
            )
        if isinstance(method, (DeleteMessage, AnswerCallbackQuery)):
            return True
        return True


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def settings(tmp_path):
    return Settings(bot_token="2142935745:test", data_dir=tmp_path, _env_file=None)  # type: ignore[call-arg]


@pytest.fixture
async def app(conn, settings):
    tg = RecordingBot()
    notifier = Notifier(tg, conn)
    notifier.start()
    a = App(settings=settings, conn=conn, bot=tg, notifier=notifier, scheduler=AsyncIOScheduler(timezone=clock.TZ))
    yield a
    await notifier.stop()


@pytest.fixture
def message_manager():
    return MockMessageManager()


@pytest.fixture
def dp(app, message_manager):
    yield bot.build_dispatcher(app, message_manager=message_manager)
    for module in bot.MODULES:  # dialogs are module-level routers; free them for the next test
        module.dialog._parent_router = None


def make_user(conn, uid: int, *groups: str, name="Mario", surname="Rossi", gender="M", status="active"):
    users.create_pending(conn, uid, name, surname, gender)
    if status == "active":
        users.approve(conn, uid, groups)
    else:
        users.set_status(conn, uid, status)
    return users.get(conn, uid)


def client(dp, app, uid: int) -> BotClient:
    return BotClient(dp, user_id=uid, chat_id=uid, bot=app.bot)
