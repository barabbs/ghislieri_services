"""Scheduled jobs. APScheduler logs a failing job at ERROR (so it is alerted) and keeps running."""

import logging

from apscheduler.triggers.cron import CronTrigger

from . import clock, events, meals, users
from .app import App
from .notify import esc

log = logging.getLogger(__name__)


async def academic_year_rollover(app: App) -> None:
    moved = users.promote_alumni(app.conn)
    log.info("Academic year rollover: %d students moved to alumni", len(moved))
    if moved:
        text = f"🎓 Passati ad alumni ({len(moved)}):"
        for i, u in enumerate(moved):
            line = f"\n• {esc(u.full_name)}"
            if len(text) + len(line) > 4000:  # Telegram's limit is 4096 characters
                text += f"\n… e altri {len(moved) - i}"
                break
            text += line
        app.notifier.send_to_groups((users.ADMIN,), text, kind="rollover", silent=True)


async def expire_notifications(app: App) -> None:
    app.notifier.expire()


def setup(app: App) -> None:
    month, day = clock.ACADEMIC_YEAR_ROLLOVER
    app.scheduler.add_job(
        academic_year_rollover, CronTrigger(month=month, day=day, hour=0, minute=30, timezone=clock.TZ), args=[app]
    )
    app.scheduler.add_job(expire_notifications, CronTrigger(minute="*/5", timezone=clock.TZ), args=[app])
    meals.schedule(app)
    events.schedule(app)
