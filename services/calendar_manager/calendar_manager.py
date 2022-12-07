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
    def _request_add_event(self, **kwargs):
        for k, s in (("name", "Titolo"), ("begin", "Orario di inizio"), ("end", "Orario di fine")):
            if kwargs[k] is None:
                return {"ok": False, "text": f"{s} dell'evento mancante"}
        cats = tuple(filter(lambda x: x['sel'], kwargs["categories"]))
        if len(cats) == 0:
            return {"ok": False, "text": "Aggiungi almeno una categoria"}
        kwargs["categories"] = list(c["name"] for c in cats)
        try:
            self.calendar.add_event(**kwargs)
        except Exception as err:
            return {"ok": False, "text": getattr(err, "IT_MSG", str(err))}
        self.calendar.save()
        return {"ok": True, "text": ""}

    def _request_get_categories(self, categories=None, groups=None, selected=None):
        if categories is None:
            if len(var.AUTH_GROUPS.intersection(groups)) > 0:
                classes = var.CATEGORIES_BY_CLASS.keys()
            else:
                classes = (g[9:] for g in filter(lambda x: x[:9] == "calendar.", groups))
            return {"text": "---", "cats": sum((list({"name": k, "text": s[0], "sym": s[1], "sel": False, "sel_text": ""} for k, s in var.CATEGORIES_BY_CLASS[cl].items()) for cl in classes), start=list())}
        else:
            for s in categories:
                if s["name"] == selected["name"]:
                    s["sel"] = not s["sel"]
                    s["sel_text"] = "☑️" if s["sel"] else ""
            return {"text": "".join((x["sym"] for x in filter(lambda x: x['sel'], categories))), "cats": categories}

    def _request_get_day_events(self, day, permissions):
        classes = tuple(c for c,p in var.CLASSES_AUTHORIZATIONS.items() if (p[0] is None or len(p[0].intersection(permissions)) > 0) and (p[1] is None or len(p[1].intersection(permissions)) == 0))
        return self.calendar.get_day_events(day, classes)

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
