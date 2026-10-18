"""Logging: everything to stderr (journald under podman), errors also to an admin Telegram chat."""

import asyncio
import collections
import html
import logging
import time

from aiogram import Bot

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

# Last errors, shown in the bot's developer menu.
recent_errors: collections.deque[logging.LogRecord] = collections.deque(maxlen=50)


class _RecentErrors(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        recent_errors.append(record)


class TelegramAlertHandler(logging.Handler):
    """Sends ERROR records to a Telegram chat. Never blocks, and mutes repeats for `mute` seconds."""

    def __init__(self, bot: Bot, chat_id: int, mute: float = 600):
        super().__init__(logging.ERROR)
        self.bot, self.chat_id, self.mute = bot, chat_id, mute
        self._last_sent: dict[tuple, float] = {}
        self._loop = asyncio.get_running_loop()
        self.setFormatter(logging.Formatter(FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("aiogram.event"):  # already reported by our own error handler
            return
        key = (record.name, record.msg, record.exc_info[0] if record.exc_info else None)
        now = time.monotonic()
        if now - self._last_sent.get(key, -self.mute) < self.mute:
            return
        self._last_sent[key] = now
        text = self.format(record)[-3500:]  # keep the end of the traceback, under Telegram's limit
        self._loop.call_soon_threadsafe(self._schedule, f"⚠️ <pre>{html.escape(text)}</pre>")

    def _schedule(self, text: str) -> None:
        self._loop.create_task(self._send(text))

    async def _send(self, text: str) -> None:
        try:
            await self.bot.send_message(self.chat_id, text)
        except Exception as e:  # must never raise into logging, nor log at ERROR (loop)
            logging.getLogger(__name__).warning("Could not send alert: %s", e)


def setup(level: str = "INFO") -> None:
    logging.basicConfig(level=level, format=FORMAT, force=True)
    handler = _RecentErrors(logging.ERROR)
    logging.getLogger().addHandler(handler)
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)  # one line per update otherwise
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def add_telegram_alerts(bot: Bot, chat_id: int) -> None:
    logging.getLogger().addHandler(TelegramAlertHandler(bot, chat_id))
