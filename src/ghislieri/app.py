"""Shared runtime objects, handed to every handler and dialog as `app`."""

import sqlite3
from dataclasses import dataclass

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .notify import Notifier
from .settings import Settings


@dataclass
class App:
    settings: Settings
    conn: sqlite3.Connection
    bot: Bot
    notifier: Notifier
    scheduler: AsyncIOScheduler
