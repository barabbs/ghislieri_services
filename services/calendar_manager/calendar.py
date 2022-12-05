from . import var
import arrow as ar
import os, ics
import datetime as dt
from modules import utility as utl

import logging

log = logging.getLogger(__name__)

BEGIN_AFTER_END = "End must be after begin"


class EventNotInRange(Exception):
    def __init__(self, evstart):
        super(EventNotInRange, self).__init__(f"Event with start {evstart} not in calendar range")


class EventDuplicateUID(Exception):
    def __init__(self, uid):
        super(EventDuplicateUID, self).__init__(f"Event with uid {uid} is a duplicate")


def get_calendar_name():
    year = (ar.now() - var.CALENDAR_SHIFT).year
    return year, (ar.Arrow(year, 1, 1) + var.CALENDAR_SHIFT, ar.Arrow(year + 1, 1, 1) + var.CALENDAR_SHIFT)


def get_event_dict(event, day):
    ev_dict = {"date": event.begin.format('dddd DD MMM YYYY', locale='it').capitalize(),
               "name": event.name.upper(),
               "recap_h": event.begin.format('HH:mm') if event.begin.floor('day') == day else "   ➤   ",
               "start_h": event.begin.format('HH:mm') if event.begin.floor('day') == event.end.floor('day') else event.begin.format('DD MMM, HH:mm', locale='it') + " ",
               "end_h": event.end.format('HH:mm') if event.begin.floor('day') == event.end.floor('day') else " " + event.end.format('DD MMM, HH:mm', locale='it'),
               "description": event.description.replace("\xa0", "\n") if event.url is None else "",
               "has_url": event.url is not None,
               "hidden_url": "" if event.url is None else f'<a href="{event.url}"> </a>',
               "url": event.url}
    for key, sym in var.SYMBOL_BY_CATEGORY.items():
        if key in event.categories:
            ev_dict['symbol'] = sym
            break
    else:
        ev_dict['symbol'] = var.DEFAULT_SYMBOL
    return ev_dict


class Calendar(ics.Calendar):
    def __init__(self):
        self.year, self.range = get_calendar_name()
        self.filepath = os.path.join(var.CALENDARS_DIR, f"{var.CALENDAR_NAME}{self.year}-{self.year + 1}{var.CALENDAR_EXT}")
        try:
            with open(self.filepath, 'r') as file:
                super(Calendar, self).__init__(file.read(), **var.CALENDAR_DEFAULTS)
        except FileNotFoundError:
            super(Calendar, self).__init__(**var.CALENDAR_DEFAULTS)
            self.extra.append(var.CALENDAR_TIMEZONE)

    def add_event(self, autocorrect=False, **kwargs):
        if "organizer" in kwargs:
            kwargs["organizer"]["email"] = kwargs["organizer"].get("email", "NONE")
            kwargs["organizer"] = ics.Organizer(**kwargs["organizer"])
        if "id" in kwargs:
            kwargs["uid"] = kwargs["classification"] + var.UID_SEPARATOR + kwargs.pop("id")
        try:
            event = ics.Event(**kwargs)
        except ValueError as err:
            if autocorrect and str(err) == BEGIN_AFTER_END:
                log.warning(f"Autocorrecting event {kwargs['begin']} - {kwargs['end']}  |  {kwargs['name']}")
                kwargs.pop("end")
                kwargs["duration"] = var.AUTOCORRECT_DEFAULT_DURATION
                event = ics.Event(**kwargs)
            else:
                raise
        log.debug(f"{event.begin.format('YYYY-MM-DD HH:mm:ss ZZ')} - {event.end.format('YYYY-MM-DD HH:mm:ss ZZ')}  |  {event.name}")
        if event.begin < self.range[0] or event.begin > self.range[1]:
            raise EventNotInRange(event.begin)
        if any(ev.uid == event.uid for ev in self.events):
            raise EventDuplicateUID(event.uid)  # TODO: Update if modification time is newer?
        self.events.add(event)
        log.info(f"Evento aggiunto:  {event.begin.format('YYYY-MM-DD HH:mm:ss ZZ')} - {event.end.format('YYYY-MM-DD HH:mm:ss ZZ')}  |  {event.name}")

    def save(self):
        with open(self.filepath + ".temp", 'w') as file:
            file.writelines(self.serialize_iter())
        os.rename(self.filepath + ".temp", self.filepath)

    def get_calendar_range(self):
        return {'day_num': (ar.now() - self.range[0]).days, 'day_max': 365}

    def get_day_events(self, day_num):
        day = self.range[0] + dt.timedelta(days=day_num)
        events = tuple(get_event_dict(event, day) for event in self.timeline.on(day, strict=False))
        no_event = f"\n\n{var.NO_EVENT_FOR_DAY}" if len(events) == 0 else ""
        day_text = f"<b>{day.format('dddd DD MMMM YYYY', locale='it').capitalize()}</b>" + no_event
        return {"day": day_text, "events": events}
