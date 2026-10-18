# Architecture (v1)

One Python process runs the Telegram bot and every scheduled job on a single asyncio event loop. State lives in one SQLite file. There are no worker processes and no internal RPC.

```
src/ghislieri/
  __main__.py     entry point: settings → guard → DB → bot → scheduler → polling
  settings.py     GS_* env vars / .env (pydantic-settings), production guard
  app.py          App: settings, conn, bot, notifier, scheduler (handed to every handler)
  db.py           SQLite connection + numbered migrations (migrations/*.sql)
  clock.py        Europe/Rome time, academic year
  log.py          logging to stderr, error alerts to Telegram, recent-errors buffer
  notify.py       notification engine
  mail.py         SMTP sending
  jobs.py         scheduler setup, core jobs (alumni rollover, notification expiry)
  users.py        users, groups, permissions
  meals.py        canteen: meal days, bookings, reminders, recap PDF, reports
  events.py       college calendar: events, website sync, ICS export
  printing.py     lp command
  submissions.py  eduroam reports, social posts, feedback
  templates/      Jinja2 templates (meal recap)
  bot/
    __init__.py   dispatcher, user middleware, /start, notification buttons, error handlers
    common.py     shared dialog helpers (permissions, escaping, navigation)
    dialogs/      one aiogram-dialog Dialog per area
```

Rule of thumb: domain modules (`meals.py`, `events.py`, ...) hold the logic and the SQL and know nothing about menus; `bot/dialogs/*` hold the menus and call the domain modules.

## Bot

Built on [aiogram 3](https://docs.aiogram.dev) and [aiogram-dialog](https://aiogram-dialog.readthedocs.io).

- **Dialogs.** Each area is a `Dialog` of `Window`s (`bot/dialogs/<area>.py`). Each module exports its `StatesGroup`, `dialog` and `ACCESS` (group needed to open it, `None` for any active user). Dialogs keep one live menu message per user and edit it in place; user text input is deleted after it is read (`common.tidy_input`).
- **Dialog state** is in memory (`MemoryStorage`). After a restart old buttons raise `UnknownIntent`; the error handler answers with a fresh home menu. This is deliberate: nothing in a menu is worth persisting.
- **Isolation.** `SimpleEventIsolation` handles one user's updates one at a time (photo albums, double taps), while different users are served concurrently.
- **User middleware** loads the sender's DB record into `user` for every update. Users who had blocked the bot become active again; `disabled` users are ignored.
- **Entry points** (`bot/__init__.py`): `/start` (signup, waiting screen, or home), notification buttons, and a fallback that treats stray messages as `/start`.

### Access control

- `users.User.has(group)` with dotted groups: holding `calendar.cultural.gs` grants `calendar.cultural` and `calendar`.
- `when=perm(group)` hides a widget **and** refuses its presses. aiogram-dialog itself only evaluates `when` while drawing the keyboard, so `common.enforce_access_on_press` patches `Keyboard.process_callback` to re-check `perm()` conditions on every press. Data-based `when=` conditions are not access checks: never use them to protect a privileged action.
- Notification buttons (`open|<state>`) only open a state that the notification behind that very message offered to that user, and only if the user holds the dialog's `ACCESS`.

## Database

`db.connect` opens the file (WAL mode, foreign keys on) and applies `migrations/NNNN_*.sql` whose number is above `PRAGMA user_version`, one transaction each. To change the schema, add a new numbered file; never edit an applied one.

The connection is used only from the event-loop thread. Queries touch at most a few hundred rows, so they run synchronously.

| Table | Content |
|---|---|
| `users` | Telegram id, name, surname, gender, email, `enrollment_year`, `status` (pending / active / blocked / disabled) |
| `user_groups` | (user, group) pairs |
| `notifications`, `deliveries` | notification text and buttons; per-user delivery state and message id |
| `submissions` | feedback, eduroam reports, social posts, canteen reports (JSON payload, photos as Telegram file ids) |
| `meal_days`, `meal_bookings` | bookable days with opening date; per user and meal: attending yes/no (no row = no answer) |
| `events` | calendar events (UTC times, class, categories, status, source rss/bot) |

## Notifications

A notification is a separate bot message, never the menu itself, so it cannot overwrite what the user is doing.

- `notifier.send(user_ids, text, kind=..., ref=..., buttons=..., silent=..., expires_at=...)` stores the notification and one `deliveries` row per user, then queues them.
- One background worker sends everything, about 20 messages per second, handling Telegram's `RetryAfter` and users who blocked the bot. Handlers never wait for a broadcast, so the bot stays responsive at reminder time. Pending deliveries are resumed after a restart.
- `kind` + `ref` identify what a notification is about (e.g. `meal_reminder` + a date). Sending again with the same pair replaces the earlier message (`replace=True`), and `retract(kind, ref, user_id)` deletes it, e.g. when a student has booked.
- A job retracts expired notifications every 5 minutes.

## Scheduled jobs

APScheduler `AsyncIOScheduler` in Europe/Rome. A failing job is logged at ERROR (and so alerted); the process keeps running. Jobs are idempotent.

| When | Job |
|---|---|
| every 5 min | expire notifications |
| daily 03:00 | calendar sync from the college website |
| daily 07:00 | meal recap PDF by email |
| daily 12:00, 19:00 | meal reminders for tomorrow |
| Aug 15 00:30 | students → alumni after 6 academic years |
| Aug 15 01:00 | meal days for the new academic year |

## Logging and errors

- Everything goes to stderr in one format; in production that is journald (`journalctl -u ghislieri`).
- Records at ERROR and above are also sent to `GS_ALERT_CHAT_ID` (repeats muted for 10 minutes) and kept in memory for the developer menu.
- Unhandled exceptions in handlers are logged, the user sees "Qualcosa è andato storto" and the home menu.

## Configuration

`settings.Settings` reads `GS_*` environment variables, and `.env` in the working directory for development. See `deploy/ghislieri.env.example`.

**Production guard** (`settings.check_production_guard`): the production bot's token only runs with `GS_ENV=prod` on a host that has `/etc/ghislieri/production`, and `GS_ENV=prod` only runs with the production bot's token.

In dev, email goes to `GS_MAIL_DEV_REDIRECT` or is only logged, and printing is only logged.
