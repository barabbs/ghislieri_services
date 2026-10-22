# ghislieri_services rewrite: stack research (2026-10-18)

Versions were checked on 2026-10-18 against the PyPI JSON API (`https://pypi.org/pypi/<pkg>/json`), GitHub releases and python.org, unless a line says otherwise. Facts marked "UNVERIFIED" could not be confirmed from a primary source.

## 0. Scope

Web research on library and platform options for the rework, as of 2026-10-18. Findings about the current code are in the service and bot docs, not here. Items marked UNVERIFIED could not be confirmed from a primary source.

## 1. Python, uv, containers

**CPython releases**
- 3.15.0 was released on 2026-10-09. 3.14.8 (2026-09-30) is the latest 3.14 patch. 3.16.0a1 came out on 2026-10-13.
  - Sources: https://www.python.org/downloads/ and https://endoflife.date/python
- 3.14 gets bugfix releases until 2027-10, then security fixes until 2030-10. 3.13 left bugfix support on 2026-10-01.

**Which version to target: 3.14**
- Rationale: `aiogram 3.31.0` declares `Requires-Python <3.15,>=3.10` and pins `pydantic<2.14`.
- PTB 22.8 lists 3.15 only as beta support.
- Use 3.14 now and move to 3.15 in about 6 months, once aiogram lifts its cap.
- In `pyproject.toml`: `requires-python = ">=3.14"` plus `.python-version` containing `3.14`.
  - Verified: uv ignores the dependency's upper bound and resolves aiogram 3.31.0, aiogram-dialog 2.6.0 and pydantic 2.13.5 under `>=3.14`.

**uv** (latest 0.13.1, 2026-10-14)
- Managed Pythons come from python-build-standalone. The `x86_64-unknown-linux-gnu` builds need glibc 2.17 or newer, so they run on both RHEL 9 (glibc 2.34) and Arch.
  - Source: https://gregoryszorc.com/docs/python-build-standalone/main/running.html
- Use the baseline `x86_64` build (the default), not `x86_64_v3`, unless you know the server CPU supports it.

**How uv venvs reference their interpreter** (verified locally)
- `uv venv -p 3.13` links `.venv/bin/python` to `~/.local/share/uv/python/cpython-3.13-linux-x86_64-gnu/bin/python3.13`. That path is a minor-version symlink to `cpython-3.13.12-...`.
- `uv python upgrade` replaces patch releases transparently, and pacman never touches these files, so the venv survives Arch system upgrades.
- Pinning a patch version (`-p 3.13.12`) links to that exact directory, so you lose transparent upgrades.
- Pointing at the system interpreter (`-p /usr/bin/python3.14`) gives `home=/usr/bin`. That venv breaks on the next Arch minor-version bump, the same way the current one did.
- Source: https://docs.astral.sh/uv/concepts/python-versions/ ("Automatic upgrades for virtual environments are implemented using a directory with the Python minor version"; this applies only to uv-managed Pythons).

**Settings**
- `python-preference` (env `UV_PYTHON_PREFERENCE`) accepts `managed` (the default; prefers managed but still uses a suitable system Python before downloading one), `only-managed`, `system` and `only-system`.
- Newer flags: `--managed-python` / `UV_MANAGED_PYTHON=1` requires a managed Python, and `--no-managed-python` disables it.
- Recommendation for Arch: add `python-preference = "only-managed"` to `~/.config/uv/uv.toml`, or export `UV_MANAGED_PYTHON=1`.
- `uv venv` has no `--copies` option. `--relocatable` only makes the venv's scripts and activators movable; the interpreter is still a symlink, so it does not protect against a system Python upgrade. A managed Python does.
- `.venv` is disposable anyway: `uv sync` recreates it in seconds.
- Env-var reference: https://docs.astral.sh/uv/reference/environment/

**Base image options**
- `python:3.14-slim` (Debian trixie; tags `3.14.8-slim-trixie` and `3.15-slim` exist on Docker Hub).
  - Small and the best documented with uv.
  - `apt` provides `poppler-utils` (needed by pdf2image), `cups-client` (provides `lp`) and the WeasyPrint libraries.
- `ghcr.io/astral-sh/uv:python3.14-trixie-slim`: the same base with uv preinstalled. Convenient as the builder stage.
- UBI9: `registry.access.redhat.com/ubi9/python-314` and `ubi9/python-314-minimal` exist in the Red Hat catalog, plus python-312. No python-313 image was found.
  - UNVERIFIED: whether `poppler-utils` and `cups-client` are available from the UBI repos. They are RHEL AppStream packages, and UBI ships only a subset.
  - Source: https://catalog.redhat.com/en/software/containers/ubi9/python-314/690b0a9fcfc8d02bfb0d341e
- **Recommendation:** `python:3.14-slim-trixie` for both builder and runtime, with the uv binary copied in. Podman on RHEL runs Debian-based images without problems.

**Official uv container pattern** (https://docs.astral.sh/uv/guides/integration/docker/; podman/buildah honour `RUN --mount=type=cache|bind`):

```dockerfile
FROM python:3.14-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0 UV_NO_DEV=1
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-editable

FROM python:3.14-slim-trixie
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils cups-client && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
CMD ["ghislieri"]
```

- Use the same Python image in both stages: the venv links to `/usr/local/bin/python`. The alternative is a uv-managed Python in the builder, copied to the same path in the runtime image.
- To pin the uv image by digest, use `ghcr.io/astral-sh/uv:0.13.1@sha256:...`.
- **Printing from a container:** set `CUPS_SERVER=/run/cups/cups.sock` and bind-mount the host socket (`Volume=/run/cups/cups.sock:/run/cups/cups.sock`). With SELinux on RHEL this probably needs `:z` or a policy tweak (UNVERIFIED; test on the server).
- **Deploy with a Quadlet `.container` unit** (podman >= 4.4; RHEL 9.2+ ships it). Use the `Secret=` and `EnvironmentFile=` keys, plus `AutoUpdate=registry` if you push images.
  - Source: https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html

## 2. Telegram libraries

**Bot API:** latest is 10.3 (2026-08-24). Source: https://core.telegram.org/bots/api-changelog

**python-telegram-bot 22.8** (2026-06-12; supports Bot API 10.0, so it lags 10.3)
- Source: https://docs.python-telegram-bot.org/en/stable/changelog.html
- Fully asyncio since v20, built around `Application`/`ApplicationBuilder`.
- Built-in pieces:
  - `ConversationHandler`
  - `JobQueue` (extra `[job-queue]`, which wraps APScheduler `<3.12`)
  - `PicklePersistence`/`BasePersistence`
  - `AIORateLimiter` (extra `[rate-limiter]`)
  - `arbitrary_callback_data` (extra `[callback-data]`): stores any Python object behind a UUID in an LRU cache, persisted only if you use persistence.
- v13: the last release line was 13.x (13.13 in 2022-06, your installed 13.14 is later). No formal EOL notice was found (UNVERIFIED), but it gets no updates and targets Bot API 6.x; treat it as dead. Upgrading 13 to 22 is effectively a rewrite (sync to async).
- In 2026-03, maintainership passed from Bibo-Joshi to Poolitzer and harshil21. The project is active (29.5k stars, pushed today).

**aiogram 3.31.0** (2026-08-25; supports Bot API 10.3; Python 3.10–3.14)
- Sources: https://github.com/aiogram/aiogram and https://docs.aiogram.dev
- Features:
  - `Router`s and outer/inner middlewares
  - magic filters (`F.data == ...`)
  - FSM (`StatesGroup` with Memory or Redis storage)
  - typed `CallbackData` factory: `class MenuCb(CallbackData, prefix="m"): action: str; page: int`, then `.pack()` and the `MenuCb.filter(F.action=="x")` filter
  - i18n via gettext or Fluent
  - Scenes, available since 3.2 and still marked "experimental": https://docs.aiogram.dev/en/latest/dispatcher/finite_state_machine/scene.html
- No built-in scheduler and no rate limiter. Catch `TelegramRetryAfter` yourself.
- No built-in SQL FSM storage. The options are `MemoryStorage`, `RedisStorage`, or a small custom `BaseStorage`.

**pyTelegramBotAPI 4.37.1** (2026-10-17; Bot API 10.3)
- Simple decorator API with sync and async variants and a basic state storage. The ecosystem is smaller and has no dialog framework.

**Recommendation: aiogram 3 + aiogram-dialog.** Reasons:
- aiogram-dialog maps almost 1:1 onto the existing handmade DSL (section 3).
- The `CallbackData` factory removes manual `CALLBACK_SEP` string parsing.
- Routers give a clean admin/user split. A middleware can inject the DB user and permissions.
- It is current with the Bot API.

**Alternative: PTB 22**, if you prefer its documentation and batteries (JobQueue, persistence, rate limiter) and are willing to keep a custom menu engine.

**Broadcast load:** sending to about 300 users is trivial. Telegram's guidance is to stay under roughly 30 messages per second (https://core.telegram.org/bots/faq). A loop with `await asyncio.sleep(0.05)` that handles RetryAfter is enough.

## 3. Menu/dialog framework

**aiogram-dialog 2.6.0** (2026-03-22; requires `aiogram>=3.14`, jinja2 and cachetools)
- Sources: https://github.com/Tishka17/aiogram_dialog and https://aiogram-dialog.readthedocs.io
- Maintenance: last commit 2026-06-15, about 900 stars, 41 open issues, releases every few months. The main maintainer is Tishka17, so the bus factor is small but the project is active.

**What it provides**
- `Dialog`s made of `Window`s, each window tied to an FSM state. By default the dialog renders one message and edits it in place (`ShowMode`).
- An intent/task stack: `Start`, `Cancel`, `Back`, `SwitchTo`, plus `StartMode` and `LaunchMode`, including subdialogs that return results.
- Text widgets: `Const`, `Format`, `Jinja`, `Case`, `List`, `Multi`.
- Keyboard widgets:
  - `Button`, `Url`, `Row`/`Column`/`Group`
  - `Select`, `Radio`, `Multiselect`, `Checkbox`, `Toggle`, `Counter`
  - `ScrollingGroup` and `ListGroup` with pager widgets (pagination)
  - `Calendar` and `TimeSelect`
  - `CopyText`
- Input: `TextInput` (typed, with a parser) and `MessageInput` (photos and files).
- `when=` on any widget for conditional or permission-filtered buttons, fed from window `getter`s. Version 2.6 added a global getter.
- `BgManager` updates a user's dialog from background tasks, such as a notification arriving.
- i18n works through a custom Text widget; see `example/i18n` (Fluent) in the repo.
- Dev tools: state-diagram rendering and an HTML preview of all windows.

**Fit with the existing DSL**
| Existing DSL | aiogram-dialog equivalent |
|---|---|
| JSON message codes | Windows |
| `NEW`/`BACK`/`HOME` | `SwitchTo`/`Start`/`Back`/`Cancel`, or a `StartMode.RESET_STACK` home |
| `PAGE` | `ScrollingGroup` |
| date picker | `Calendar` |
| permission checks | `when=` plus a middleware |
| `REQ` | getter/`on_click` calling the service function directly |
| 600 s session timeout | dialog reset |

- Verdict: yes, it is a good replacement. The menus become Python instead of JSON (type-checked, and less code).
- Caveat: dialog state lives in FSM storage. With `MemoryStorage`, a restart loses stacks and old buttons raise `UnknownIntent`. Handle that with an error handler that restarts the home dialog, which matches the current session-expiry behaviour. Add Redis or a custom SQLite `BaseStorage` only if this becomes a problem.

**PTB equivalents:** none of comparable maturity found (not exhaustive). `ConversationHandler` plus your own rendering is the PTB way.

## 4. Scheduling and process model

**APScheduler**
- Stable is 3.11.3 (2026-06-28). The 4.0 line is still alpha: 4.0.0a6 from 2025-04, and the README says "do NOT use this release in production!"
- Source: https://github.com/agronholm/apscheduler
- PTB's JobQueue pins `apscheduler<3.12`.

**aiogram + APScheduler pattern:** create an `AsyncIOScheduler()` in `on_startup`, `scheduler.add_job(fn, CronTrigger(hour=7, timezone=ZoneInfo("Europe/Rome")), kwargs={"bot": bot})`, then `scheduler.start()`.
- Don't persist jobs (no jobstore). Rebuild schedules at startup, and keep one-off notifications in the DB.
- Lazier alternative for about 8 fixed periodic tasks: a few `asyncio` loops (`while True: await work(); await asyncio.sleep(...)`). Use APScheduler 3.11 once cron-style times or DST matter.

**Process model: a single asyncio process replaces multiprocessing + Pipes.** The services are I/O-bound (Telegram, HTTP, IMAP, Google APIs, `lp`), so the "RPC" becomes plain `await service.func()` calls. That removes the pipe protocol, the serialization and the per-process error files. Blocking libraries stay usable:
- google-api-python-client, imaplib and smtplib: `await asyncio.to_thread(...)`
- pdf2image: shells out to poppler, so it also goes through `to_thread`
- `lp`: `asyncio.create_subprocess_exec`
- Wrap each periodic task in `try/except Exception: log.exception(...)` so one failure doesn't kill the loop. This replaces the current decorator.

## 5. Persistence

**Versions:** SQLAlchemy 2.1.5 (2.1.0 GA 2026-09-24; requires Python >=3.11), Alembic 1.20.0, SQLModel 0.0.48 (still 0.x), aiosqlite 0.22.1.

**Recommendation for about 300 users and a few tables:** one SQLite file in WAL mode (`PRAGMA journal_mode=WAL`) with stdlib `sqlite3`.
- Calls take microseconds, so calling them synchronously from async code is fine at this scale.
- Migrations: a list of SQL scripts gated by `PRAGMA user_version`, about 10 lines of code. Alembic is not needed.
- Do a one-shot import script from the JSON files.
- Upgrade path, if queries grow or you want an ORM: SQLAlchemy 2.1 (typed `Mapped[]` models) with Alembic. Skip SQLModel, which is pre-1.0 and adds a layer.
- Back up with `sqlite3 db ".backup ..."` or the `VACUUM INTO` statement on a timer.
- `student_databaser` already uses `sqlite3`, so this extends existing practice.

## 6. Config and secrets

**pydantic-settings 2.16.0** (2026-10-14; requires pydantic >=2.7, compatible with aiogram's `<2.14` cap)
- `BaseSettings` with `env_prefix="GHIS_"`, `env_file=".env"` (dev), `secrets_dir="/run/secrets"` (podman), and `SecretStr` for tokens.
- Docs: https://docs.pydantic.dev/latest/concepts/pydantic_settings/

**Podman secrets**
- Create with `printf %s "$TOKEN" | podman secret create ghis_bot_token -`.
- Reference in Quadlet as `Secret=ghis_bot_token,type=env,target=GHIS_BOT_TOKEN`, or mount it as a file under `/run/secrets/`.

**Production token guard** (robust, lightweight)
1. Use two different bots from @BotFather. The dev machine's `.env` holds only the test bot token. The production token exists only as a podman secret on the server and is never stored in the repo or on the laptop.
2. At startup, call `await bot.get_me()` and refuse to start if `me.username != settings.expected_bot_username`. Set `GHIS_EXPECTED_BOT_USERNAME` in the Quadlet unit on prod and in `.env` on dev. This catches swapped tokens in either direction.
3. Optional: also require `GHIS_ENV=prod` to enable side-effecting services (printing, sending email, broadcasts).
4. Machine-id or hostname checks add little once step 1 holds. Skipped.

Note: two pollers on the same token produce a 409 Conflict from `getUpdates`, so accidental prod-token use from dev would visibly break prod.

## 7. Logging and errors

- **stdlib `logging`** configured with `logging.config.dictConfig`, logging to stderr. Under Quadlet/systemd, stdout and stderr go to journald (`journalctl -u ghislieri`, `podman logs`). There is no need for file handlers or per-service error files.
- **Admin alerts:** a roughly 20-line `logging.Handler` (level ERROR) that POSTs `sendMessage` to an admin chat with httpx. Put it behind stdlib `QueueHandler`/`QueueListener` so logging never blocks the event loop.
  - Python 3.12+ `dictConfig` can configure `QueueHandler` with a listener directly.
  - Rate-limit or deduplicate, for example one message per identical error per 10 minutes.
- **structlog 26.1.0** is good for JSON or key-value logs but unnecessary here.
- **loguru 0.7.3**: last release 2024-12. It works, but it is a parallel logging world. Skip it.
- **Optional Sentry:** `sentry-sdk` 2.72.0 works with self-hosted GlitchTip (v6.1.8, 2026-06; https://glitchtip.com). Adopt it only if Telegram alerts prove too noisy or too thin. Probably YAGNI for this project.

## 8. Other dependencies

| Package | Latest | Notes |
|---|---|---|
| google-api-python-client | 2.201.0 (2026-09-30) | Sync. Wrap calls in `to_thread`. |
| google-auth-oauthlib | 1.5.0 | Alongside google-auth 2.62.0. |
| httpx | 0.28.1 (2024-12) | Still the stable release. 1.0.dev6 (2026-08) is a pre-release, so pin `<0.29`, as PTB does. aiogram uses aiohttp 3.14.5, so httpx is only needed for scraping and the alert handler. `aiohttp` could replace it and save a dependency. |
| beautifulsoup4 | 4.15.0 | |
| Jinja2 | 3.1.6 | |
| pdf2image | 1.17.0 (2024-01) | Stale but working; needs poppler. Alternative: pypdfium2 5.14.0, pure wheels with no system dependency: `pdf.render(...).to_pil()`. |
| pdfkit | 1.0.0 (2021) | wkhtmltopdf is archived. Replace with weasyprint 70.0. |
| rapidfuzz | 3.14.6 | Drop thefuzz 0.22.1, which is only a wrapper around rapidfuzz. |
| feedparser | 6.0.14 (2026-07) | |
| ics | 0.7.3 (2026-04) | Slow-moving. icalendar 7.3.0 is the better-maintained alternative. |
| arrow | 1.4.0 (2025-10) | Replaceable with stdlib `datetime` + `zoneinfo.ZoneInfo("Europe/Rome")`. The `tzdata` package is only needed in slim images without system tzdata; Debian slim includes tzdata (UNVERIFIED for trixie-slim; add `tzdata` 2026.5 to be safe). |
| whenever | 0.11.0 | Nice but pre-1.0. Not needed. |
| emoji | 2.16.0 | Plain Unicode literals probably suffice. |
| schedule | 1.2.2 | Drop it (section 4). |
| tornado | | Only a PTB 13 dependency. Gone after the rewrite. |

**Facebook**
- **The Groups API is gone.** Meta deprecated it in Graph API v19.0, and it was removed for all versions on 2024-04-22.
  - Sources: https://developers.facebook.com/docs/graph-api/changelog/version19.0/ and https://developers.facebook.com/community/threads/2076398286093257/
- The Pages API needs a Page access token, App Review, and for public data of other pages the "Page Public Content Access" feature (https://developers.facebook.com/docs/pages-api/overview). It does not cover groups.
- The scraping target is in doubt: `curl -I https://mbasic.facebook.com/` now returns a 302 with `refsrc=deprecated` in the redirect URL, so mbasic appears deprecated. No official announcement was found (UNVERIFIED).
- Cookie scraping also violates Meta's ToS and breaks often.
- `facebook-sdk` 3.1.0 (2018) is dead. `python-facebook-api` 0.24.0 (2026-02) is maintained but cannot read groups.
- **Recommendation:** drop Facebook ingestion. Replace it with admins forwarding or posting through the bot's admin panel.

**Gmail SMTP/IMAP with a password:** "less secure apps" are gone, but app passwords still work with 2-Step Verification (third-party sources only; Google's own page was not checked). The robust option is OAuth2 XOAUTH2 or the Gmail API, reusing the existing google-auth setup.

## 9. Tooling

**uv init layout**
- `uv init --app` in uv 0.13 now creates a packaged src layout, verified locally. Output: `src/<pkg>/__init__.py`, `[project.scripts] <name> = "<pkg>:main"` and the `uv_build>=0.13.1,<0.14.0` build backend. This is identical to `--package`.
- Use it, keep `uv.lock` committed, and put dev tools under `[dependency-groups] dev = [...]`.
- Docs: https://docs.astral.sh/uv/concepts/projects/init/

**Tool versions**
- ruff 0.17.1 (2026-10-15): `ruff check` plus `ruff format`, which replace black, isort and flake8.
- pytest 9.1.1. Add `pytest-asyncio` if handlers are tested.
- pre-commit 4.7.0: ruff hooks from `astral-sh/ruff-pre-commit`, plus `uv-lock` from `astral-sh/uv-pre-commit`.
- mypy 2.4.0 (2026-10-01) is the stable type checker.
- ty 0.0.89 (2026-10-16) is officially "in beta" with "no stable API; breaking changes ... may occur between any two versions". Source: https://github.com/astral-sh/ty
  - Recommendation: use ty in the editor/LSP for speed, and mypy in CI if you want a gate. For a ~3k-line project, ty alone is acceptable if you accept churn.

**Suggested layout**

```
pyproject.toml  uv.lock  .python-version  Containerfile  deploy/ghislieri.container
src/ghislieri/__init__.py (main)  config.py  db.py  bot/ (routers, dialogs)  services/ (calendar.py, email.py, printer.py, meals.py, feeds.py)
tests/
```
