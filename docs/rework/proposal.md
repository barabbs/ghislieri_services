# Rework proposal

Status: draft for discussion (2026-10-18). Library versions and sources are in [research.md](research.md). Problems in the current code are listed in each service doc under "Known issues".

## 1. Why change

The current design (v0.5.x) works, but has structural problems:

- **Dead Telegram library.** python-telegram-bot 13.14 is sync, targets Bot API 6.x and gets no updates. It imports `imghdr`, so it cannot run on Python 3.13+. The project is stuck on Python 3.12.
- **Process model is heavier than the work.** Eight `multiprocessing` processes spin at 16 Hz and talk through blocking pipes. All the work is I/O-bound and small. Calls are synchronous: a 60 s `lp` call or a slow IMAP login blocks the bot. Two services that call each other can deadlock.
- **Hand-made message DSL.** About 110 JSON `.gsm` files describe menus with stringly-typed actions (`["REQ", "service", "r_type", {...}]`), `str.format` templating and `$` indirection. Nothing checks them: today four files declare a `code` that doesn't match their path, and a group name typo (`socials_rep` vs `social_rep`) breaks a notification (see [bot/messages.md](../bot/messages.md)). User text that contains `{` breaks the templating.
- **Errors are invisible.** Exceptions become files in `data/errors/`. Nobody is notified. Several scheduled tasks lack `@task`, so one exception kills the process and the job is lost until the next run.
- **Storage is scattered.** SQLite for students, then custom text formats for reservations (`.mr`), notifications backup, feedback, eduroam reports, Facebook post history, statistics. No locking, no schema, no migrations.
- **Secrets and config are files with custom extensions.** Production versus debug is a `-d` flag. Forgetting `-d` on a dev machine runs the production bot.
- **Security holes** reachable by students or by email senders:
  - `printer_service.py:41`: shell injection through the page-list text (any `student`).
  - `modules/utility.py:156`: shell injection through an email attachment filename (LibreOffice call).
  - `email_service.py:85-93`: path traversal through an attachment filename.
  - `components.py:220-224`: a button press is not re-checked against the button's whitelist, so a crafted callback can trigger hidden buttons (for example calendar edit/delete).
  - Unescaped user text in HTML messages in several places.
- **External integrations have rotted.** Facebook removed the Groups API in 2024 and `mbasic.facebook.com` is being shut down, so `channels_manager` is living on borrowed time. `pdfkit` depends on wkhtmltopdf, which is archived.

## 2. Target design

One asyncio process. The services stay as separate Python modules with clear boundaries, but they call each other as plain `async` functions.

```
src/ghislieri/
  __main__.py        entry point: load settings, set up logging, start bot + scheduler
  settings.py        pydantic-settings: env vars / .env / podman secrets
  db.py              SQLite connection, schema migrations (PRAGMA user_version)
  logging.py         dictConfig + Telegram admin-alert handler
  scheduler.py       APScheduler AsyncIOScheduler, Europe/Rome, all cron jobs
  services/          domain logic, no Telegram code
    students.py  calendar.py  meals.py  printing.py  email.py  submissions.py
  bot/               aiogram 3 + aiogram-dialog
    dialogs/         one module per area (home, calendar, meals, print, settings, admin, ...)
    middlewares.py   loads the DB user + permissions into every update
    notifications.py broadcasts, live-message replacement via BgManager
tests/
deploy/              Containerfile, quadlet units, example .env
tools/               data migration from v0.5, reservation generator
```

### 2.1 Telegram: aiogram 3 + aiogram-dialog

- aiogram 3.31 is current with Bot API 10.3. It has routers, middlewares and a typed `CallbackData` factory.
- aiogram-dialog maps closely onto today's DSL: one live message edited in place, a window stack, `ScrollingGroup` for paging, `Calendar` for date picking, `when=` for permission-filtered buttons, `TextInput`/`MessageInput` for answers, photos and files.
- Menus become Python code: type-checked, testable, and renderable to an HTML preview for review.
- Notifications use `BgManager` to replace a user's idle menu with the notification, like today.
- The trade-off: menus are no longer editable as JSON by non-programmers. In practice they were edited by the maintainer anyway.
- Alternative: python-telegram-bot 22 (async, JobQueue, persistence and rate limiter included), but with no dialog framework. We would keep a custom menu engine. Not recommended.

### 2.2 Process model and scheduling

- One process, one event loop. Blocking libraries (IMAP/SMTP, Google API, pdf2image, `lp`) run in `asyncio.to_thread` or `asyncio.create_subprocess_exec`, with timeouts.
- APScheduler 3.11 `AsyncIOScheduler` with `CronTrigger` in `Europe/Rome` for: meal recap 07:00, reminders 12:00 and 19:00, menu download hourly, calendar RSS sync 03:00. APScheduler 4 is still alpha.
- Every job goes through one wrapper that logs and alerts on failure. A job failure never stops the process.
- The supervisor, pipes, statistics and the `restart_service` request disappear. Podman restarts the container if the process dies.

### 2.3 Storage: one SQLite database

- One file, WAL mode, stdlib `sqlite3` (through a thread, or `aiosqlite`). Schema versioned with `PRAGMA user_version` and plain SQL migration files.
- Tables (first cut): `users`, `user_groups` (proper many-to-many instead of a comma string), `meals`, `meal_reservations`, `notifications`, `notification_recipients`, `feedback`, `eduroam_reports`, `submissions`.
- Calendars can stay `.ics` files if the college shares them; otherwise move events to a table and export `.ics`.
- `tools/migrate_v05.py` imports the current `.gsdb`, `.mr` files and pending notifications once.
- SQLAlchemy/Alembic only if the schema grows a lot. For about 300 users it would be overhead.

### 2.4 Configuration and the production token

- `pydantic-settings` reads env vars (prefix `GS_`) and an optional `.env` file. Production secrets are podman secrets passed as env vars.
- `GS_ENV` is `dev` (default) or `prod`. Dev never reads a production secret, because the production token exists only on the server.
- Guard: at startup the bot calls `getMe` and compares the username with `GS_EXPECTED_BOT_USERNAME`. In `dev` the expected username is the test bot. On mismatch the process refuses to start. This catches a production token copied into a dev `.env`, and a test token deployed to production.
- Optional second check: in `prod`, require a marker that exists only on the server, for example `/etc/ghislieri/prod` mounted into the container.

### 2.5 Logging and error reporting

- Standard `logging`, configured once with `dictConfig`, writing to stderr. Podman sends it to journald, so `journalctl` and `podman logs` work and rotation is handled.
- A `TelegramAlertHandler` at level ERROR sends a short message (service, exception, first traceback lines) to an admin chat. It runs behind a `QueueHandler` so it never blocks, and it rate-limits identical messages.
- The bot keeps an admin "recent errors" view, fed from an in-memory ring buffer or a small table, instead of browsing log files.
- Optional later: Sentry or self-hosted GlitchTip.

### 2.6 Other changes

- Python 3.14 with uv-managed interpreters. The `.venv` then no longer breaks on Arch upgrades.
- `arrow` → stdlib `datetime` + `zoneinfo`. `thefuzz` → `rapidfuzz` directly.
- `pdfkit`/wkhtmltopdf → WeasyPrint for the meal recap PDF.
- `pdf2image`/poppler → `pypdfium2` (no system binary), if the container image stays small.
- `lp` called with an argument list, page list validated with a regex.
- Gmail: keep IMAP/SMTP with an app password, or move to the Gmail API with the OAuth client already in use for Google. Decision needed (see below).
- HTML escaping of every user- or feed-provided string, in one helper.
- Tooling: ruff (lint + format), pytest, pre-commit, mypy in CI. GitHub Actions: lint, tests, build container.
- Deployment files in the repo: `deploy/Containerfile` (official uv multi-stage pattern, `python:3.14-slim`) and a Quadlet `.container` unit for RHEL 9.

## 3. Migration plan

Each step ends with a working bot on the test token.

1. **Skeleton.** `src/` layout, settings, logging, DB with migrations, aiogram bot with the home menu and the token guard. Containerfile + quadlet.
2. **Users.** Signup, profile, groups and permissions, admin student management. Migration script for `.gsdb`.
3. **Notifications.** Broadcast engine, custom admin notifications, live-message replacement.
4. **Meals.** Menu download and rendering, reservations, reminders, recap PDF and email. Migration for `.mr`.
5. **Calendar.** Day view, add/edit/delete events, RSS sync.
6. **Printing, submissions, feedback, settings, changelog.**
7. **Cutover.** Run the new version against a copy of the production data. Migrate. Switch the production container. Keep v0.5 image for rollback.

## 4. Quick fixes for production now

These are small and independent of the rework. They can go to `main` as a hotfix if wanted:

- Printer shell injection (`printer_service.py:32,41`): call `lp` with an argument list, validate the page list.
- LibreOffice shell injection (`modules/utility.py:156`): argument list instead of `shell=True`.
- Attachment path traversal (`email_service.py:85-93`): use `os.path.basename` and a safe name.
- Button whitelist bypass (`components.py:220-224`): check the key's permission in `Buttons.act`.

## 5. Decisions for the maintainer

1. Rewrite (this proposal) or incremental upgrade of the current design?
2. Facebook → Telegram channel bridge: drop it (APIs gone), replace it with "admins post through the bot", or keep scraping until it breaks?
3. Gmail: app password (as now) or Gmail API with OAuth?
4. Are the JSON menus ever edited by anyone other than the maintainer? (If yes, aiogram-dialog in Python is a loss for them.)
5. Calendar: is the `.ics` file shared outside the bot (for example subscribed in calendar apps)?
6. Which features are unused and can go (statistics view, log browsing, services reservation, Supersega)?
