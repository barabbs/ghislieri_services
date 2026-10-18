# Development setup

## Environment

The project uses [uv](https://docs.astral.sh/uv/). It installs a uv-managed Python, so the virtual environment does not break when the system Python is upgraded.

```sh
uv sync            # creates .venv with Python 3.12 and the locked dependencies
uv run main.py -d student_databaser ghislieri_bot
```

The legacy code needs Python 3.12: python-telegram-bot 13 imports `imghdr`, which Python 3.13 removed. `pyproject.toml` also pins a few old transitive dependencies (TatSu, urllib3, setuptools) that the legacy stack needs.

## Debug mode

Always pass `-d` when running locally. Without it the program uses `/var/opt/ghislieri_services` and the **production** bot token.

With `-d`:

- the data directory is `./data`;
- the bot reads `data/ghislieri_bot/ghislieri_bot_token_test.gbtk` (the test bot);
- session timeout and chat sync interval are shorter.

`--no_sync` disables the periodic chat sync and switches `student_databaser` to `database_all_users.gsdb`.

## Which services are safe to run locally

- `student_databaser`, `ghislieri_bot`, `calendar_manager`: safe with the test token. The bot will message the users in the local database who also started the test bot.
- `email_service`, `meals_management`: log into the real Gmail account and mark menu emails as read. Avoid.
- `channels_manager`: scrapes Facebook with stored cookies and posts to the configured channel. Avoid.
- `printer_service`: prints on the default CUPS printer.

For experiments, copy the repository and `data/` to a scratch directory and run there, so the local data copy stays untouched.
