"""Shared runtime objects, handed to every handler and dialog as `app`."""

import asyncio
import datetime as dt
import sqlite3
from dataclasses import dataclass, field

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from . import clock
from .notify import Notifier
from .settings import Settings

RESTART = 75  # exit code that makes systemd start the bot again (Restart=on-failure)


@dataclass
class App:
    settings: Settings
    conn: sqlite3.Connection
    bot: Bot
    notifier: Notifier
    scheduler: AsyncIOScheduler
    started_at: dt.datetime = field(default_factory=clock.now)
    exit_code: int = 0
    stopping: asyncio.Event = field(default_factory=asyncio.Event)

    def request_stop(self, exit_code: int = 0) -> None:
        """Stop polling and shut down cleanly; the process then exits with `exit_code`."""
        self.exit_code = exit_code
        self.stopping.set()
