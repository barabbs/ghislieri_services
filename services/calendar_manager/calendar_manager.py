from modules.base_service import BaseService
from modules.service_pipe import Request
from . import var
from .calendar import Calendar, EventNotInRange, EventDuplicateUID
from .rssfeed import RSSFeed

import logging, os

log = logging.getLogger(__name__)


class CalendarManager(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        super(CalendarManager, self).__init__(*args, **kwargs)
        self.calendar = Calendar()
        self.rssfeed = RSSFeed()
        # self._task_update_rssfeed()

    def _load_tasks(self):
        self.scheduler.every().day.at(var.RSSFEED_UPDATE_TIME).do(self._task_update_rssfeed)
        super(CalendarManager, self)._load_tasks()

    def load_calendar(self):  # TODO: NEEDED??????
        self.calendar = Calendar()

    # Requests

    def _request_get_calendar_range(self):
        return self.calendar.get_calendar_range()

    def _request_get_day_events(self, day_num):
        return self.calendar.get_day_events(day_num)

    def _request_update_rssfeed(self):
        self._task_update_rssfeed()

    # Tasks

    def _task_update_rssfeed(self):
        log.info("Updating events from RSSFeed...")
        errors = 0
        for event in self.rssfeed.get_events():
            try:
                self.calendar.add_event(autocorrect=True, **event)
            except (EventNotInRange, EventDuplicateUID) as err:
                log.debug(str(err))
                errors += 1
                if errors >= var.RSSFEED_MAX_ERRORS:
                    break
            else:
                errors = 0
        self.calendar.save()
        log.info("RSSFeed update finished")


SERVICE_CLASS = CalendarManager
