"""Scheduled jobs. APScheduler logs a failing job at ERROR (so it is alerted) and keeps running."""

import logging

from apscheduler.triggers.cron import CronTrigger

from . import clock, events, meals, users
from .app import App

log = logging.getLogger(__name__)


async def academic_year_rollover(app: App) -> None:
    moved = users.promote_alumni(app.conn)
    log.info("Academic year rollover: %d students moved to alumni", len(moved))
    if moved:
        names = "\n".join(f"• {u.full_name}" for u in moved)
        app.notifier.send_to_groups(
            (users.ADMIN,), f"🎓 Passati ad alumni ({len(moved)}):\n{names}", kind="rollover", silent=True
        )


async def expire_notifications(app: App) -> None:
    app.notifier.expire()


def setup(app: App) -> None:
    month, day = clock.ACADEMIC_YEAR_ROLLOVER
    app.scheduler.add_job(academic_year_rollover, CronTrigger(month=month, day=day, hour=0, minute=30), args=[app])
    app.scheduler.add_job(expire_notifications, CronTrigger(minute="*/5"), args=[app])
    meals.schedule(app)
    events.schedule(app)
