# calendar_manager

Code: `services/calendar_manager/` (`calendar_manager.py`, `calendar.py`, `rssfeed.py`, `var.py`)

## Purpose

`calendar_manager` keeps the college events calendar for the current academic year as one iCalendar file. Bot users with the right groups can add, edit and remove events. The calendar view shows each day's events, filtered by the viewer's groups. Once a day the service also imports events from the college website's RSS feed. Events have a **classification** (`cultural`, `sport`, `college`, `misc`; stored in the iCal `CLASS` field) and one or more **categories** (stored in `CATEGORIES`, e.g. `conference`, `football`, `party`). Both are listed in `var.CATEGORIES_BY_CLASS`.

## Requests API

| Request | Args | Returns | What it does | Used by |
|---|---|---|---|---|
| `add_event` | kwargs: `name`, `description`, `begin`, `end`, `url`, `categories` (list of category dicts from `get_categories`), `classification`, `status`, `organizer` (`{"common_name", "email"}`), optionally `id`/`uid`/`created` | `{"ok": bool, "text": str}` | Checks that `name`, `begin` and `end` are set and that at least one category is selected (`check_event_kwargs`). Builds an `ics.Event` with uid `<classification>/<id>`, where `id` defaults to `int(time())`. Rejects events outside the academic-year range and duplicate uids, then saves. On error, `text` is the exception's Italian `IT_MSG` if it has one, otherwise `str(err)`. | `messages/calendar_manager/new_event/recap.gsm` (`status="CONFIRMED"`, organizer = the user's name and email) |
| `get_event_dict` | `uid`, `permissions` | dict: `uid`, `name`, `description`, `begin`/`end` (`{"dt", "short", "status"}`), `url`, `categories` (`{"text", "cats"}` with the event's categories pre-selected), `status` (`{"st", "text"}`), `classification` (display text) | Prepares an event for the edit flow. | `messages/calendar_manager/event_details.gsm`, `event_details_url.gsm` (stored as `edit_event`) |
| `edit_event` | kwargs: `uid`, `name`, `description`, `begin`, `end`, `url`, `categories`, `status` | `{"ok", "text"}` | Same checks as `add_event`, plus a range check and an end-before-begin check. It then `setattr`s every kwarg on the existing event, sets `last_modified`, and saves. | `messages/calendar_manager/edit_event/recap.gsm` |
| `remove_event` | `uid` | `{"ok", "text"}` | Deletes the event and saves. | `messages/calendar_manager/delete_event/main.gsm` |
| `get_categories` | `categories=None`, `permissions=None`, `selected=None` (a category dict, only `["name"]` is used) | `{"text": <selected symbols or "---">, "cats": [{"name", "text", "sym", "sel", "sel_text"}, ...]}` | Without `categories`, builds the list of categories the user may use. Members of `master`/`admin` get every class. Others get the classes named by their `calendar.<class>` groups. With `categories` and `selected`, it toggles the selected category and returns the updated list. | `messages/calendar_manager/menu.gsm` (initial list), `new_event/select_cat.gsm`, `edit_event/select_cat.gsm` (toggle) |
| `get_day_events` | `day` (`"YYYY-MM-DD"` or `None` for today), `permissions` | `{"day": <HTML header>, "events": (recap dicts...), "prev": "YYYY-MM-DD", "next": "YYYY-MM-DD"}` | Lists the events that overlap `day` (`timeline.on(day, strict=False)`), keeping only classifications the viewer may see under `var.CLASSES_AUTHORIZATIONS` (`college` is limited to `master`/`student`). A `day` outside the year range is clamped to the range. Each recap dict has `date`, `name`, `recap_h`, `start_h`, `end_h`, `description`, `has_url`, `hidden_url`, `url`, `uid`, `cancelled`, `symbol`, `categories`. | `messages/calendar_manager/calendar.gsm` |
| `update_rssfeed` | none | `None` | Runs `_task_update_rssfeed` right away. | `messages/calendar_manager/admin/menu.gsm` (`master` only) |

`stop` and `get_statistics` are inherited from `BaseService`.

Permissions in the bot: the "add event" button in `menu.gsm` needs `master`, `admin` or `calendar`. Each class in `new_event/select_class.gsm` needs `master` or `calendar.<class>`. The edit and delete buttons in `event_details*.gsm` need `master` or `admin`.

## Scheduled tasks

| Task | Schedule | What it does |
|---|---|---|
| `_task_update_rssfeed` | daily at `var.RSSFEED_UPDATE_TIME` (`"03:00"`) | Walks pages 1..`RSSFEED_MAX_PAGES` (100) of `RSSFEED_LINK` (the ghislieri.it `ajde_events` feed) and calls `add_event(autocorrect=True, ...)` for each entry. Out-of-range and duplicate-uid errors are counted. After `RSSFEED_MAX_ERRORS` (5) in a row it stops. It then saves and rebuilds the `Calendar` object, which is also how it switches to a new academic-year file. |
| `_task_update_statistics` | hourly (inherited) | Statistics bookkeeping. |

RSS mapping (`rssfeed.py`): `title` becomes `name`. The text of the first `<p>` in `summary` becomes `description`. `link` becomes `url`. The last non-empty URL path segment becomes `id`, so the uid is `cultural/<slug>`. Custom fields `startdate`/`enddate` become `begin`/`end`. `published` becomes `created`. `author` becomes the organizer's `common_name`, and categories come from `RSSFEED_CATEGORIES_BY_AUTHOR` (default `("conference",)`). Defaults: `status="TENTATIVE"`, `classification="cultural"`. With `autocorrect`, an event whose end is before its begin gets a duration of 2 h instead.

## `_update` loop

Not overridden.

## Inter-service calls

None. The service sends no requests and no notifications.

## Data & files

Data dir: `/var/opt/ghislieri_services/calendar_manager/`, or `./data/calendar_manager/` with `-d`.

- `calendars/calendar_<Y>-<Y+1>.ical` is the iCalendar (RFC 5545) file for the active academic year. It is written by `ics` 0.7.x. `Y` = `(now - 32 weeks).year`. The year range is `[Jan 1 Y + 32 weeks, Jan 1 Y+1 + 32 weeks)`, which starts around 12-13 August. A missing file is created empty on the first save.
- `calendars/calendar_<...>.ical.temp` is a temporary file used during save. It is written, then `os.rename`d over the real file (atomic).
- Other files in `calendars/` (`*_bckp.ical`, `test*.ical`) are manual leftovers. The code ignores them.

Each `VEVENT` looks like this (placeholder values):

```
BEGIN:VEVENT
UID:cultural/some-event-slug          (or e.g. sport/1700000000 for bot-created events)
SUMMARY:Event title
DESCRIPTION:Free text
DTSTART:20231016T190000Z
DTEND:20231016T210000Z                 (or DURATION:PT2H when autocorrected)
CATEGORIES:conference
CLASS:cultural
STATUS:TENTATIVE | CONFIRMED | CANCELLED
URL:https://example.org/event
ORGANIZER;CN=Display Name:mailto:someone@example.org   (mailto:NONE when there is no email)
DTSTAMP:...   LAST-MODIFIED:... (after edits)
END:VEVENT
```

The service needs no credentials.

## External dependencies

- `ics` (0.7.2 in `.venv`) parses and serializes the calendar and provides `timeline.on`.
- `arrow` handles dates and Italian-locale formatting.
- `feedparser` fetches and parses the RSS feed over HTTPS, with no auth.
- `beautifulsoup4` (`html.parser`) extracts text from the feed summary.
- External endpoint: `https://www.ghislieri.it/feed/?post_type=ajde_events&paged={page}`.

## Known issues / smells

- `services/calendar_manager/calendar_manager.py:122`: `_task_update_rssfeed` lacks the `@task` decorator. Any unexpected error (network, missing feed field, the summary below) escapes `run()` and kills the service process, which the supervisor in `modules/ghislieri_services.py:82` then restarts.
- `services/calendar_manager/rssfeed.py:14`: `BeautifulSoup(...).p.get_text()` raises `AttributeError` when a summary has no `<p>`. `e['enddate']`, `e['startdate']` and `e['author']` (`:16-22`) raise `KeyError` when the field is missing. One bad entry aborts the whole import.
- `rssfeed.py:7-8`: `feedparser.parse` has no timeout, and all 100 pages are fetched unless the error limit triggers first. A manual `update_rssfeed` blocks the calling bot for the whole import, because pipe requests are synchronous.
- `services/calendar_manager/calendar.py:95`: `raise EventUIDNotFound` is missing its required `uid` argument, so a lookup miss raises `TypeError` instead of the intended exception. Affects `get_event_dict`, `edit_event` and `remove_event` with a stale uid.
- `calendar.py:131-132`: `edit_event` sets attributes in kwarg order, so `begin` is set before `end`. With `ics` 0.7.2 the `begin` setter raises `ValueError('Begin must be before end')` if the new begin is after the old end. Moving an event to a later date therefore fails with an English error.
- `calendar.py:120`: duplicate uids are rejected and never updated, so changes made to an event on the website are never imported (TODO in the code).
- `calendar.py:102`: the bot-created event id is `int(time())`. Two events created in the same second with the same classification collide.
- `calendar.py:29-31`: `EventDuplicateUID` has no `IT_MSG`, so users see the English message.
- HTML injection and broken messages: `calendar.py:49,53,55` and `calendar_manager.py:39-52` put the event `name`, `description` and `url` unescaped into messages sent with `parse_mode=HTML` (e.g. `messages/calendar_manager/event_details.gsm:5`). A `<` or `&` in a user-entered or RSS title can make Telegram reject the message, and lets event creators inject markup. In `hidden_url` (`calendar.py:55`), a `"` in the URL breaks the attribute.
- `calendar.py:72` and `calendar_manager.py:55-56` index `var.ALL_CATEGORIES`, `var.STATUS_TEXTS` and `var.CLASSIFICATION_TEXTS` directly. An event with an unknown category, status or class (e.g. from a hand-edited `.ical`) raises `KeyError` and breaks that day's view.
- Time zones: `calendar.py:106,129,148` use `ar.now().replace(tzinfo="utc")`, which relabels local wall-clock time as UTC. Bot input is parsed with `ar.get` and also ends up as UTC. `var.TIMEZONE = "Europe/Rome"` (`var.py:25`) is never used. This only works as long as every source makes the same "local time stored as Z" assumption.
- `calendar_manager.py:27`: categories come from `calendar.*` groups after `extend_groups`. A user in `calendar.cultural.gs` also gets the generic `cultural` categories. A group `calendar.<x>` with an unknown `<x>` raises `KeyError` (`:29`). The category list built in `menu.gsm` covers all of the user's classes, not just the chosen classification, so the categories and `CLASS` of an event can disagree.
- `calendar_manager.py:53`: `get_event_dict` builds the category list from the editor's permissions, so categories outside them are silently dropped when the event is saved again.
- `calendar_manager.py:72`: `load_calendar` is marked `# TODO: NEEDED??????`. It is also the only point where the year file switches, so after mid-August the old year stays active until the next 03:00 import or a restart.
- `calendar.py:43`: `get_calendar_name` returns `(year, range)`, not a name.
- Dead code: `calendar.py:80` (`self.calendar`), `var.py:2-4` (imports only used by the commented-out timezone block), `var.py:18` (`TEMP_EXT`; `save` hardcodes `".temp"`), `var.py:25` (`TIMEZONE`), `var.py:59-74`, and `var.py:80` (`EVENT_LINK_TEXT`).
- Hardcoded values: the feed URL, author-to-category map (`var.py:90-91`), schedule time and permission sets all live in `var.py`.
- Privacy: bot-created events store the creator's full name and email in `ORGANIZER` (`messages/calendar_manager/new_event/recap.gsm`), inside a file that is otherwise public information.
