"""Entry point: `ghislieri` (or `python -m ghislieri`)."""

import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from . import __version__, bot, clock, db, jobs, log
from .app import App
from .notify import Notifier
from .settings import Settings, check_production_guard

logger = logging.getLogger("ghislieri")


async def run(settings: Settings) -> None:
    check_production_guard(settings)
    conn = db.connect(settings.db_path)
    tg = Bot(settings.bot_token.get_secret_value(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await tg.get_me()
    logger.info("Ghislieri %s starting as @%s (env=%s)", __version__, me.username, settings.env)
    if settings.alert_chat_id:
        log.add_telegram_alerts(tg, settings.alert_chat_id)
    scheduler = AsyncIOScheduler(timezone=clock.TZ, job_defaults={"coalesce": True, "misfire_grace_time": 3600})
    app = App(settings=settings, conn=conn, bot=tg, notifier=Notifier(tg, conn), scheduler=scheduler)
    dp = bot.build_dispatcher(app)
    jobs.setup(app)
    scheduler.start()
    app.notifier.start()
    try:
        await dp.start_polling(tg, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await app.notifier.stop()
        await tg.session.close()
        conn.close()
        logger.info("Stopped")


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    log.setup(settings.log_level)
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
