# Development

## Setup

The project uses [uv](https://docs.astral.sh/uv/). `pyproject.toml` asks for a uv-managed Python 3.14, so `.venv` does not break when the system Python is upgraded.

```sh
uv sync                     # installs Python 3.14 if needed, creates .venv
cp deploy/ghislieri.env.example .env
# edit .env: GS_ENV=dev, GS_BOT_TOKEN=<test bot token>, GS_DATA_DIR=var, GS_ALERT_CHAT_ID=<your id>
uv run ghislieri            # runs the bot on the test token
```

WeasyPrint (meal recap PDF) needs Pango installed on the system (`pacman -S pango`, `apt install libpango-1.0-0 libpangoft2-1.0-0`).

The bot refuses to start with the production token on a development machine (see [architecture.md](architecture.md#configuration)). In dev mode, email is only logged unless `GS_MAIL_DEV_REDIRECT` is set, and print jobs are only logged.

To play with real data, import a copy of the v0.5 data into the dev database:

```sh
uv run tools/migrate_v05.py <copy of old data dir> var/ghislieri.sqlite3
```

The test bot can only message users who started it, so other users in the copy are not bothered; deliveries to them fail and they are marked `blocked`.

## Checks

```sh
uv run pytest -q
uv run ruff check src tests tools
uv run ruff format src tests tools
```

CI (`.github/workflows/ci.yml`) runs the same checks and builds the container image.

Tests run offline. Dialog flows use `aiogram_dialog.test_tools` (`BotClient` + `MockMessageManager`), with a recording fake bot for everything else (`tests/conftest.py`). See `tests/test_signup.py` for a complete flow.

## Conventions

- Domain logic and SQL in `src/ghislieri/<domain>.py`, menus in `src/ghislieri/bot/dialogs/<area>.py`.
- Italian for user-facing text, English for code, comments and logs.
- Escape every user- or website-provided string with `esc` (`notify.esc`, re-exported by `bot.common`) before putting it in a message (messages use HTML).
- Protect privileged buttons with `when=perm(group)`; it is enforced on presses too. A data-based `when=` is not an access check.
- Blocking work goes to `asyncio.to_thread` or `asyncio.create_subprocess_exec`, always with a timeout; never `shell=True`.
- Keep Telegram file ids instead of files on disk.
- Schema changes: add `src/ghislieri/migrations/NNNN_<name>.sql`; never edit an applied migration.
- Notifications: give each a `kind` and, when it is about something specific, a `ref`, so it can be replaced or retracted.
- Scheduled jobs: `CronTrigger(..., timezone=clock.TZ)` (a hand-built trigger otherwise uses the host's time zone) and make them idempotent.

## Releasing

1. Update `version` in `pyproject.toml` (the bot reads it from the package metadata), run `uv lock`, and add the user-facing notes to `src/ghislieri/changelog.md`.
2. Merge to `main`, then deploy (see [deployment.md](deployment.md)).
3. Optionally announce it from the bot: Admin → Notifiche → Annuncia aggiornamento.
