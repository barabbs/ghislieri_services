# student_databaser

Code: `services/student_databaser/` (`student_databaser.py`, `var.py`)

## Purpose

`student_databaser` owns the user database. Each Telegram user who has started the bot ("chat") has one row holding their Telegram user id, the id of the last message the bot sent them, their personal info (name, surname, gender, email), and a comma-separated list of the groups they belong to. Groups act as permissions throughout the bot (message whitelists and blacklists, notification targets, calendar classes). The service holds one SQLite connection for its whole lifetime. Every other service reads or writes users only through this service's requests.

## Requests API

| Request | Args | Returns | What it does | Used by |
|---|---|---|---|---|
| `get_chats` | `group=None`, `sort=False`, `only_active=True` | `tuple` of chat dicts (see below) | Reads every row. Keeps only users in `group` if one is given. Drops users in group `inactive` unless `only_active=False`. If `sort` is set, sorts by surname (`None` surnames sort first). | `ghislieri_bot/bot.py:208` (loads all active chats), `ghislieri_bot/ghislieri_bot.py:28` (`add_notification` resolves `groups` to user ids), `email_service/email_service.py:110` (resolves `groups` to emails), `meals_management/reservation.py:66` (`group="student", sort=True`), `messages/admin/students/list.gsm` (`sort=true`) |
| `new_chat` | `user_id`, `last_message_id` (positional) | chat dict | Inserts a new row and adds the user to group `signup`. If the `user_id` already exists (`IntegrityError`), it instead removes group `inactive` and updates `last_message_id`. It does **not** add `signup` in that case. | `ghislieri_bot/bot.py:223` (unknown user writes to the bot) |
| `set_chat_last_message_id` | `user_id`, `last_message_id` | `None` | Updates `last_message_id`. | `ghislieri_bot/bot.py:314` |
| `edit_student_info` | `user_id`, `info` (column name), `value` | `None` | `UPDATE students SET <info> = ?`. The column name is interpolated into the SQL. | `messages/welcome/insert_name.gsm`, `welcome/insert_surname.gsm`, `settings/profile/edit.gsm` (`info` = `name`/`surname`/`email`, chosen by button), `notifications/admin/set_gender.gsm` (`gender` = `M`/`F`) |
| `get_groups` | none | `tuple` of `{"group": <name>}` | Returns the selectable group list from `groups.gsgr`, one dict per line. | `messages/admin/students/edit_group.gsm` |
| `edit_groups` | `user_id`, `group`, `edit` (`"add"` or `"rm"`) | `set` of the user's groups after the edit | Adds a group to the user or removes one, then writes the list back. | `ghislieri_bot/ghislieri_bot.py:36` (`ghislieri_bot.edit_groups` wraps it and also refreshes the bot's in-memory chat). The `.gsm` files call the bot's wrapper, not this request directly. |
| `remove_user` | `user_id`, `hard_remove=False` | `None` | Soft remove (the default) adds group `inactive`. `hard_remove=True` deletes the row. | `ghislieri_bot/bot.py:246` |

The `stop` and `get_statistics` requests are inherited from `BaseService`. `get_statistics` is used by `messages/admin/services/options.gsm`.

A chat dict, built by `get_chat_dict` (`student_databaser.py:14`), has this shape:

```python
{
    "user_id": 123456789,
    "last_message_id": 42,
    "student_infos": {"name": "Mario", "surname": "Rossi", "gender": "M", "email": "mario@example.org"},
    "groups": {"student", "calendar.sport"},   # a Python set (empty set if the column is NULL)
}
```

## Scheduled tasks

The service defines no `_task_*` methods of its own. It has only the inherited hourly `_task_update_statistics`.

## `_update` loop

Not overridden (no-op).

## Inter-service calls

None. The service sends no requests and no notifications.

## Data & files

Data dir: `/var/opt/ghislieri_services/student_databaser/`, or `./data/student_databaser/` with `-d`.

| File | Format |
|---|---|
| `database.gsdb` | **SQLite 3** database (not JSON). This is the default DB. |
| `database_all_users.gsdb` | Same schema. Used instead of `database.gsdb` when `--no_sync` is on argv (`var.py:13`). With that flag the bot also skips its periodic chat sync (`ghislieri_bot/bot.py:330`). |
| `database_old.gsdb`, `database_old2.gsdb` | Legacy files with an older schema (no `gender` column, a `permissions` column instead of `groups`, and a `permissions` table in `_old`). The code does not use them. |
| `groups.gsgr` | Plain text, one group name per line, e.g. `student`, `calendar.sport`, `calendar.cultural.gs`. This is only the list offered in the admin "edit group" menu. A user's groups are not validated against it. |

Schema of table `students` (columns are read **by position**, see `student_databaser.py:10-15`):

```sql
CREATE TABLE "students" (
    "user_id"         INTEGER NOT NULL UNIQUE,  -- Telegram user id, PRIMARY KEY
    "last_message_id" INTEGER NOT NULL,
    "name"            TEXT,
    "surname"         TEXT,
    "gender"          TEXT,                     -- "M" / "F"
    "email"           TEXT,
    "groups"          TEXT,                     -- comma-separated, e.g. "student,calendar.sport"
    PRIMARY KEY("user_id")
);
```

Group names are dotted. The bot expands them with `modules/utility.py:extend_groups`, so `calendar.cultural.gs` also grants `calendar` and `calendar.cultural`. Special groups in `var.py`: `inactive` (soft-deleted user) and `signup` (pending admin approval).

The service needs no config or credential files.

## External dependencies

Standard library only (`sqlite3`). The database file must already exist with the schema above, because the code never creates the table.

## Known issues / smells

- `services/student_databaser/student_databaser.py:40-43`: `groups` is a `set`, so `set.remove` raises `KeyError`, not `ValueError`. Removing a group the user lacks therefore fails the request instead of being ignored. One concrete path: a user re-enabled through `new_chat` never gets `signup` (`:65-70`), so `messages/notifications/admin/set_group.gsm` (`edit_groups ... "signup" "rm"`) raises.
- `student_databaser.py:31`: the column name (`attribute`) is put into the SQL with an f-string, so there is an SQL injection surface. Today it is only fed from fixed buttons and `.gsm` constants, but `edit_student_info` lets any caller overwrite any column, including `groups` and `user_id`.
- `student_databaser.py:15`: an empty `groups` string (left after removing a user's last group, `",".join(set())`) is read back as `{""}`, not as an empty set.
- `student_databaser.py:10-15`: `SELECT *` is mapped to fields by position (`chat[2:]`, `chat[-1]`), so any schema change (adding or reordering columns) silently corrupts the dicts.
- `student_databaser.py:35-36`: `_edit_group` on an unknown `user_id` fails with `TypeError` (`fetchone()` returns `None`).
- `student_databaser.py:82`: `get_groups` splits on `"\n"`, so a trailing newline in `groups.gsgr` adds an empty group `""` to the menu.
- `student_databaser.py:50-54`: every `get_chats` call loads the whole table and filters in Python. `add_notification` and `send_email` call it once per target group, and a user in several groups is returned once per group, so callers get duplicate recipients.
- `var.py:13-14`: the `--no_sync` flag silently switches to a different database file.
- Privacy: `database.gsdb` and the `_old` backups in the data dir hold personal data (names, emails, Telegram ids). There is no retention or cleanup.
- `student_databaser.py:2`: `Request` is imported but unused.
