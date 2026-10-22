# Migrating data from v0.5

`tools/migrate_v05.py` imports the v0.5 data directory into a v1 database once. It can run again safely: existing rows are kept.

```sh
uv run tools/migrate_v05.py /path/to/old/data /path/to/ghislieri.sqlite3 --dry-run   # report only
uv run tools/migrate_v05.py /path/to/old/data /path/to/ghislieri.sqlite3
```

| v0.5 | v1 |
|---|---|
| `student_databaser/database.gsdb` | `users`, `user_groups` |
| group `signup` | status `pending` (shows up in the admin registrations queue) |
| group `inactive` | status `blocked` (reactivated when the user writes to the bot) |
| group `admin` (calendar admins) | group `calendar.admin` |
| groups that look like a year (`2019`, `year.2019`, ...) | `users.enrollment_year` |
| rows without name or surname (broken signups) | skipped, listed in the report |
| gender other than M/F | empty |
| `meals_management/reservations/*.mr` | `meal_days`, `meal_bookings` (bookings of unknown users dropped) |
| `calendar_manager/calendars/calendar_YYYY-YYYY.ical` | `events` (legacy local times are read correctly), then `calendar.ics` |

Not imported:

- pending notifications (transient);
- statistics, logs, error files;
- feedback, eduroam reports, canteen report photos (files on disk; keep the old directory as an archive);
- menus (the feature is gone), Facebook posts history (the bridge is gone).

The report lists students without a year: set their enrollment year from Admin → Studenti, or they will never be moved to alumni.

After the import, generate the meal days of the current academic year if they are missing: Mensa → ⚙️ Gestione → Genera anno accademico.
