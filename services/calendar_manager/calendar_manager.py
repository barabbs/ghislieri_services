from modules.base_service import BaseService
from modules.service_pipe import Request
from . import var
from .calendar import Calendar, EventNotInRange, EventDuplicateUID
from . import rssfeed

import logging, os

log = logging.getLogger(__name__)


def check_event_kwargs(kwargs):
    for k, s in (("name", "Titolo"), ("begin", "Orario di inizio"), ("end", "Orario di fine")):
        if kwargs[k] is None:
            return {"ok": False, "text": f"{s} dell'evento mancante"}
    cats = tuple(filter(lambda x: x['sel'], kwargs["categories"]))
    if len(cats) == 0:
        return {"ok": False, "text": "Aggiungi almeno una categoria"}
    kwargs["categories"] = list(c["name"] for c in cats)


def _get_categories(categories=None, permissions=None, selected=None):
    if categories is None:
        if len(var.AUTH_GROUPS.intersection(permissions)) > 0:
            classes = var.CATEGORIES_BY_CLASS.keys()
        else:
            classes = (g[9:] for g in filter(lambda x: x[:9] == "calendar.", permissions))
        return {"text": "---",
                "cats": sum((list({"name": k, "text": s[0], "sym": s[1], "sel": False, "sel_text": ""} for k, s in var.CATEGORIES_BY_CLASS[cl].items()) for cl in classes), start=list())}
    else:
        for c in categories:
            if c["name"] in selected:
                c["sel"] = not c["sel"]
                c["sel_text"] = "☑️" if c["sel"] else ""
        return {"text": "".join((x["sym"] for x in filter(lambda x: x['sel'], categories))), "cats": categories}


def _get_event_dict(event, permissions):
    return {"uid": event.uid,
            "name": event.name,
            "description": event.description,
            "begin": {
                "dt": event.begin.format(),
                "short": event.begin.format('ddd DD MMM YYYY, HH:mm', locale='it'),
                "status": None
            },
            "end": {
                "dt": event.end.format(),
                "short": event.end.format('ddd DD MMM YYYY, HH:mm', locale='it'),
                "status": None
            },
            "url": event.url,
            "categories": _get_categories(categories=_get_categories(permissions=permissions)["cats"], selected=event.categories),
            "status": {"st": event.status,
                       "text": var.STATUS_TEXTS[event.status]},
            "classification": var.CLASSIFICATION_TEXTS[event.classification]
            }


class CalendarManager(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        super(CalendarManager, self).__init__(*args, **kwargs)
        self.calendar = None
        self.load_calendar()

    def _load_tasks(self):
        self.scheduler.every().day.at(var.RSSFEED_UPDATE_TIME).do(self._task_update_rssfeed)
        super(CalendarManager, self)._load_tasks()

    def load_calendar(self):  # TODO: NEEDED??????
        self.calendar = Calendar()

    # Requests
    def _request_add_event(self, **kwargs):
        check = check_event_kwargs(kwargs)
        if check is not None:
            return check
        try:
            self.calendar.add_event(**kwargs)
        except Exception as err:
            return {"ok": False, "text": getattr(err, "IT_MSG", str(err))}
        self.calendar.save()
        return {"ok": True, "text": ""}

    def _request_get_event_dict(self, uid, permissions):
        event = self.calendar.get_event_from_uid(uid)
        return _get_event_dict(event, permissions)

    def _request_edit_event(self, **kwargs):
        check = check_event_kwargs(kwargs)
        if check is not None:
            return check
        try:
            self.calendar.edit_event(**kwargs)
        except Exception as err:
            return {"ok": False, "text": getattr(err, "IT_MSG", str(err))}
        self.calendar.save()
        return {"ok": True, "text": ""}

    def _request_remove_event(self, uid):
        try:
            self.calendar.remove_event(uid)
        except Exception as err:
            return {"ok": False, "text": getattr(err, "IT_MSG", str(err))}
        self.calendar.save()
        return {"ok": True, "text": ""}

    def _request_get_categories(self, categories=None, permissions=None, selected=None):
        return _get_categories(categories, permissions, (selected["name"],) if selected is not None else None)

    def _request_get_day_events(self, day, permissions):
        classes = tuple(c for c, p in var.CLASSES_AUTHORIZATIONS.items() if (p[0] is None or len(p[0].intersection(permissions)) > 0) and (p[1] is None or len(p[1].intersection(permissions)) == 0))
        return self.calendar.get_day_events(day, classes)

    def _request_update_rssfeed(self):
        self._task_update_rssfeed()

    # Tasks

    def _task_update_rssfeed(self):
        log.info("Updating events from RSSFeed...")
        errors = 0
        for event in rssfeed.get_events():
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
        self.load_calendar()
        log.info("RSSFeed update finished")


SERVICE_CLASS = CalendarManager
