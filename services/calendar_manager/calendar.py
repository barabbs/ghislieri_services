from . import var
import arrow as ar
from time import time
import os, ics
import datetime as dt
from modules import utility as utl

import logging

log = logging.getLogger(__name__)

BEGIN_AFTER_END = "End must be after begin"


class EventNotInRange(Exception):
    IT_MSG = "L'evento non è dell'anno corrente"

    def __init__(self, evstart):
        super(EventNotInRange, self).__init__(f"Event with start {evstart} not in calendar range")


class EventEndBeforeStart(Exception):
    IT_MSG = "L'oraio di fine è precedente a quello di inizio"

    def __init__(self, evstart, evend):
        super(EventEndBeforeStart, self).__init__(f"Event has end {evend} before start {evstart}")


class EventDuplicateUID(Exception):
    def __init__(self, uid):
        super(EventDuplicateUID, self).__init__(f"Event with uid {uid} is a duplicate")


class EventUIDNotFound(Exception):
    IT_MSG = "L'evento con il dato uid non è stato trovato"

    def __init__(self, uid):
        super(EventUIDNotFound, self).__init__(f"Event with uid {uid} not found")


def get_calendar_name():
    year = (ar.now() - var.CALENDAR_SHIFT).year
    return year, (ar.Arrow(year, 1, 1) + var.CALENDAR_SHIFT, ar.Arrow(year + 1, 1, 1) + var.CALENDAR_SHIFT)


def get_event_daily_recap(event, day):
    ev_dict = {"date": event.begin.format('dddd DD MMM YYYY', locale='it').capitalize(),
               "name": event.name.upper(),
               "recap_h": event.begin.format('HH:mm') if event.begin.floor('day') == day else "   ➤   ",
               "start_h": event.begin.format('HH:mm') if event.begin.floor('day') == event.end.floor('day') else event.begin.format('DD MMM, HH:mm', locale='it') + " ",
               "end_h": event.end.format('HH:mm') if event.begin.floor('day') == event.end.floor('day') else " " + event.end.format('DD MMM, HH:mm', locale='it'),
               "description": event.description.replace("\xa0", "\n") if event.description is not None else "",
               "has_url": event.url is not None,
               "hidden_url": f'<a href="{event.url}"> </a>',
               "url": event.url,
               "uid": event.uid}
    for key, sym in var.CATEGORIES_BY_CLASS[event.classification].items():
        if key in event.categories:
            ev_dict['symbol'] = sym[1]
            break
    else:
        ev_dict['symbol'] = var.DEFAULT_SYMBOL
    ev_dict['categories'] = " | ".join(f"{var.ALL_CATEGORIES[k][1]} {var.ALL_CATEGORIES[k][0].lower()}" for k in event.categories)
    return ev_dict


class Calendar(ics.Calendar):
    def __init__(self):
        self.year, self.range = get_calendar_name()
        self.filepath = os.path.join(var.CALENDARS_DIR, f"{var.CALENDAR_NAME}{self.year}-{self.year + 1}{var.CALENDAR_EXT}")
        self.calendar = None
        self._load_calendar()

    def _load_calendar(self):
        try:
            with open(self.filepath, 'r') as file:
                super(Calendar, self).__init__(file.read(), **var.CALENDAR_DEFAULTS)
        except FileNotFoundError:
            super(Calendar, self).__init__(**var.CALENDAR_DEFAULTS)
            # self.extra.append(var.CALENDAR_TIMEZONE)

    def get_event_from_uid(self, uid):
        try:
            return next(filter(lambda e: e.uid == uid, self.events))
        except StopIteration:
            raise EventUIDNotFound

    def add_event(self, autocorrect=False, **kwargs):
        if "organizer" in kwargs:
            kwargs["organizer"]["email"] = kwargs["organizer"].get("email", "NONE") or "NONE"
            kwargs["organizer"] = ics.Organizer(**kwargs["organizer"])
        if "uid" not in kwargs and "id" not in kwargs:
            kwargs["id"] = str(int(time()))
        if "id" in kwargs:
            kwargs["uid"] = kwargs["classification"] + var.UID_SEPARATOR + kwargs.pop("id")
        if "created" not in kwargs:
            kwargs["created"] = ar.now().replace(tzinfo="utc")
        try:
            event = ics.Event(**kwargs)
        except ValueError as err:
            if autocorrect and str(err) == BEGIN_AFTER_END:
                log.warning(f"Autocorrecting event {kwargs['begin']} - {kwargs['end']}  |  {kwargs['name']}")
                kwargs.pop("end")
                kwargs["duration"] = var.AUTOCORRECT_DEFAULT_DURATION
                event = ics.Event(**kwargs)
            else:
                raise EventEndBeforeStart
        if event.begin < self.range[0] or event.begin > self.range[1]:
            raise EventNotInRange(event.begin)
        if any(ev.uid == event.uid for ev in self.events):
            raise EventDuplicateUID(event.uid)  # TODO: Update if modification time is newer?
        self.events.add(event)
        log.info(f"Event added:  {event.begin.format('YYYY-MM-DD HH:mm:ss ZZ')} - {event.end.format('YYYY-MM-DD HH:mm:ss ZZ')}  |  {event.name}")

    def edit_event(self, **kwargs):
        if ar.get(kwargs["begin"]) < self.range[0] or ar.get(kwargs["begin"]) > self.range[1]:
            raise EventNotInRange(ar.get(kwargs["begin"]))
        if ar.get(kwargs["end"]) < ar.get(kwargs["begin"]):
            raise EventEndBeforeStart
        kwargs["last_modified"] = ar.now().replace(tzinfo="utc")
        event = self.get_event_from_uid(kwargs["uid"])
        event.__dict__.update(kwargs)
        log.info(f"Event edited:  {event.begin.format('YYYY-MM-DD HH:mm:ss ZZ')} - {event.end.format('YYYY-MM-DD HH:mm:ss ZZ')}  |  {event.name}")

    def remove_event(self, uid):
        event = self.get_event_from_uid(uid)
        self.events.remove(event)
        log.info(f"Event removed:  {event.begin.format('YYYY-MM-DD HH:mm:ss ZZ')} - {event.end.format('YYYY-MM-DD HH:mm:ss ZZ')}  |  {event.name}")

    def save(self):
        with open(self.filepath + ".temp", 'w') as file:
            file.writelines(self.serialize_iter())
        os.rename(self.filepath + ".temp", self.filepath)
        self._load_calendar()

    def get_day_events(self, day, classes):
        if day is None:
            day = ar.now().replace(tzinfo="utc").floor("day")
        else:
            day = ar.get(day, "YYYY-MM-DD")
            if day < self.range[0]:
                day = self.range[0]
            elif day > self.range[1]:
                day = self.range[1]
        events = tuple(get_event_daily_recap(event, day) for event in self.timeline.on(day, strict=False) if event.classification in classes)
        no_event = f"\n\n{var.NO_EVENT_FOR_DAY}" if len(events) == 0 else ""
        day_text = f"<b>{day.format('dddd DD MMMM YYYY', locale='it').capitalize()}</b>" + no_event
        return {"day": day_text, "events": events, "prev": day.shift(days=-1).format("YYYY-MM-DD"), "next": day.shift(days=1).format("YYYY-MM-DD")}
