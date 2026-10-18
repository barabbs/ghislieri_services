# meals_management

Source: `services/meals_management/` (`meals_management.py`, `reservation.py`, `var.py`).

## Purpose

Runs the college canteen ("mensa") features of the bot. Students book or cancel lunch and dinner on pre-defined days ("reservations"). Every morning the service emails the day's booking list (a PDF) to the porter's lodge and the `master` group. It sends a reminder to all students the day before a bookable day. Every hour it pulls the menu from a mailbox and converts it to a PNG that the bot shows as "today's menu". It also forwards canteen complaints ("segnalazioni") by email and bot notification.

## Requests API

All requests come from the bot's `.gsm` messages. No other service calls this one.

| Request | Args | Returns | What it does | Used by |
|---|---|---|---|---|
| `get_active_reservations` | `user_id` | tuple of `{"meal", "date" (date), "date_str", "reservation_str"}`, one per meal of each active reservation, sorted by date | Lists the bookable meals and the user's current state (🟢 booked / 🔴 not booked / ❔ never answered). | `messages/meals_management/reservation/reservations.gsm` |
| `toggle_meal_res` | `user_id`, `meal_dict` (an item returned by the request above) | `None` | Flips the user's booking for that meal (an unanswered meal becomes "booked") and saves the `.mr` file immediately. Raises `StopIteration` if the date is no longer active. | `reservation/reservations.gsm` |
| `get_all_res_dates` | none | list of `{"filename", "date_str"}` for **every** file in the reservations dir | Builds the admin date picker. | `admin/create_recap.gsm`, `admin/send_recap.gsm` |
| `create_recap` | `date_dict` (an item from above) | `None` | Regenerates `Recap_<date>.html/.pdf` on disk. Nothing is sent to the admin. | `admin/create_recap.gsm` |
| `send_recap` | `date_dict` | `None` | Regenerates the recap and emails it (manual re-send). | `admin/send_recap.gsm` |
| `download_menu` | none | `None` | Runs `_task_download_menu` on demand. | `admin/menu.gsm` |
| `get_todays_menu` | none | `{"exists": bool, "date_str", "filepath"}` | Tells the bot whether `Menu_<today>.png` exists and where it is. | `messages/meals_management/menu.gsm` (then `todays_menu/show.gsm` / `not_found.gsm`) |
| `new_report` | `user_id`, `student_infos` (dict), `report` (str), `photos` (tuple of paths) | `None` | Emails the complaint with the photos attached to groups `master` and `representative`, then notifies the same groups. `user_id` is unused. | `report/recap.gsm` |

Inherited from `BaseService`: `stop`, `get_statistics`.

## Scheduled tasks

None of these tasks uses the `@task` decorator (see Known issues).

| Task | Schedule | What it does |
|---|---|---|
| `_task_send_res_recap` | daily at `RESERV_EMAIL_SENDING_TIME` = 07:00:00 | Finds today's reservation in memory, then builds and emails the recap PDF. It does nothing if today has no reservation. Afterwards it **reloads all reservations from disk**, which is the only periodic reload. |
| `_task_send_notification` | daily at 12:00:00 and 19:00:00 | If tomorrow (`RESERV_NOTIFICATION_DAYS_BEFORE` = 1 day) has an active reservation, sends the reminder notification to group `student`. |
| `_task_download_menu` | every hour at minute 00 | Fetches unread attachments from IMAP folder `Meals/menu` through `email_service`. Each attachment goes LibreOffice → PDF → PNG (first page only, 150 dpi). The date comes from the attachment filename and is checked against the email date. Saves `menus/Menu_<YYYY-MM-DD>.png`, then deletes the attachment and the intermediate PDF. |
| `_task_update_statistics` | hourly (inherited) | Statistics bookkeeping. |

## `_update` loop

Not overridden. Nothing runs outside tasks and requests.

## Reservation lifecycle

- **The service never creates reservations.** A reservation exists only if someone has put a `Reservations_<date>.mr` file in the reservations dir. Today that is done by hand with the untracked `create_meal_reservations.py`, which writes one file per Saturday and Sunday, each opening on the Monday before.
- `Reservation.load_from_file` (`reservation.py:17-34`) returns "active" when `from_date <= (now - 7h).date() < date`. A reservation therefore opens at 07:00 on `from_date` and closes at 07:00 on its own `date` (`TIMELIMIT` = 7 h).
- Only active reservations are kept in memory (`self.reservations`). That set is filled at startup and at 07:00 by `_task_send_res_recap`. A file added during the day stays invisible until the next 07:00 or a restart.

## Inter-service calls and notifications

| Target | Request | When |
|---|---|---|
| `email_service` | `send_email(sender, groups=("master",), receivers=(<porter's lodge address>,), subject, text="", attachments=(recap.pdf,))` | recap, at 07:00 or `send_recap` |
| `email_service` | `send_email(sender, groups=("master","representative"), subject, text, attachments=photos)` | `new_report` |
| `email_service` | `download_attachments(mailbox="Meals/menu")` → list of `{"filepath", "date"}` | `_task_download_menu` |
| `student_databaser` | `get_chats(group="student", sort=True)` | building a recap |
| `ghislieri_bot` | `add_notification(groups=("student",), n_type="meals", msg_code="meals_management.reservation.reminder", notify=True, enabled_time={"hours": 7}, data={"reservation_day_notif": <date str>})` | reminder at 12:00 and 19:00 |
| `ghislieri_bot` | `add_notification(groups=("master","representative"), n_type="meal_report", msg_code="notifications.admin.new_meal_report", notify=True, data={"report": {"date", "user", "report", "n_photos"}})` | `new_report` |

## Data and files

Data dir: `/var/opt/ghislieri_services/meals_management`, or `./data/meals_management` with `-d` (relative to the CWD).

| Path | Written by | Format |
|---|---|---|
| `reservations/Reservations_<YYYY-MM-DD>.mr` | external script (create), service (`Reservation.save`) | Plain text, see below |
| `reservations/*.mr.temp` | `Reservation.save` | Temporary file, renamed over the `.mr` file (atomic save) |
| `recaps/Recap_<YYYY-MM-DD>.html` / `.pdf` | `Reservation.create_recap` | Rendered recap. Overwritten on regeneration, never deleted. |
| `recap_html_template.mrtm` | maintained by hand | Jinja2 HTML template, see below |
| `menus/Menu_<YYYY-MM-DD>.png` | `_task_download_menu` | First page of the menu at 150 dpi. Never deleted (the dev copy is ~186 MB). |
| `menus_old/` | nobody (code) | Old PNGs, not referenced by code |
| `reports/Meal_Report_<user_id>_<date>[_N].jpg` | **the bot** (`PHOTO_ANS` in `report/photo.gsm`, `report/add_photos.gsm`) | Complaint photos. They are emailed but never deleted. |

Attachments are downloaded to `email_service`'s attachment dir. LibreOffice writes the PDF next to them, with `HOME=/tmp/ghislieri_services`.

### `.mr` reservation file

```
2030-01-05        <- date of the meals (YYYY-MM-DD)
2029-12-31        <- from_date: booking opens at 07:00 of this day
Pranzo            <- meal name (var.MEALS)
111,222           <- comma-separated user_ids that booked (True)
333               <- user_ids that explicitly un-booked (False)
Cena
111
                  <- empty line = nobody
```

The file holds one block of three lines per meal: name, True ids, False ids. The line order follows `var.POSSIBLE_RESERVATIONS = (True, False)`. A user missing from both lines is "unanswered". An empty line, or any line with a non-integer token, is skipped completely (`reservation.py:29-32`).

### Recap template (`.mrtm`)

A Jinja2 template rendered with:
- `date_str`: e.g. `"SABATO 05 gennaio 2030"`;
- `reservations`: one entry per gender in `GENDERS = ("M","F")`. Each entry holds two columns (lists of students), and each student is a `get_chats` dict plus `meals` (True/False/None per meal) and `indic` (`"X"` or `""` per meal);
- `totals`: `{"Pranzo": [M, F, total], "Cena": [M, F, total]}`.

The template hardcodes the meal names and the gender indexes `[0]`, `[1]`, `[2]`. `pdfkit` (wkhtmltopdf) renders the HTML to PDF.

### Menu filenames

`utl.get_date_from_filename(filename, sugg)` (`modules/utility.py:99-132`) takes the first number in the filename as the day. It accepts that day only if it falls 0–5 days after the email date. The month normally comes from the email date and only rolls forward when the day wraps. A second number or the Italian month name only produces warnings. Examples it handles: `28feb.docx`, `Menu 3 marzo.docx`.

## External dependencies

- Python: `jinja2`, `pdfkit`, `pdf2image` (and Pillow), `schedule`.
- System binaries: **wkhtmltopdf** (pdfkit), **poppler** `pdftoppm` (pdf2image), **libreoffice** (headless, `modules/utility.py:154-158`).
- How menus arrive: the canteen emails them as attachments (usually `.docx`) to the service mailbox. A mail rule or a person must file them in the IMAP folder `Meals/menu`. `email_service` fetches the `UNSEEN` messages, and fetching marks them as seen.
- How recaps leave: SMTP through `email_service`, to a hardcoded porter's-lodge address plus the `master` group.

## Known issues / smells

- **Tasks are not wrapped in `@task`.** An exception in any `_task_*` escapes `schedule.run_pending()` and ends `BaseService.run` (`modules/base_service.py:154-168`), which kills the process. `_task_check_services` restarts it within 5 min, but the job for that time is lost. Examples: a LibreOffice timeout (`subprocess.TimeoutExpired`), a missing PDF (`pdf2image` error), or `student_databaser` failing. A failed 07:00 recap is not retried and also skips the reservation reload (`meals_management.py:98-105`).
- **A menu can be lost silently.** The email is already marked seen, and the attachment and PDF are deleted even when the date cannot be read (`meals_management.py:124-127`). After a crash the attachment stays on disk and is never retried.
- **Shell injection.** `convert_docx_to_pdf` runs `libreoffice ... '{filename}'` with `shell=True` (`modules/utility.py:156`). The filename comes from an email attachment, so anyone who can send mail into `Meals/menu` controls it. The subprocess return code is never checked either.
- **Every attachment goes to LibreOffice**, whatever its type (no extension filter, `meals_management.py:116-119`), and only page 1 is kept.
- **Date parsing bugs** (`modules/utility.py:114, 132`). The year always comes from the email, so a menu dated early January but sent in December lands in the wrong year. The day is not checked against the month length (e.g. day 30 with an email from Feb 26 makes `dt.date` raise `ValueError`, which is not `DateNotInterpreted`, and crashes the task).
- **Stale in-memory state.** `.mr` files added or changed on disk are picked up only at 07:00 or on restart (`meals_management.py:28-33, 105`).
- `get_all_res_dates` lists the whole directory, including past dates, and calls `strptime` on every name. A leftover `.mr.temp` or any other file makes it raise (`meals_management.py:63-64`); `_load_reservations` does filter `.temp` (`:30`).
- `create_recap` (admin "Create Recap") only writes files on the server and returns nothing, so the admin never sees the result (`meals_management.py:68-71`).
- The recap silently leaves out students whose `gender` is not `"M"`/`"F"` (e.g. unset) (`reservation.py:72-73`).
- `jinja2.Template` runs without autoescape, so student names go into the HTML raw (`reservation.py:63`). The template has `<tr>` where `</tr>` belongs and a stray comma in `class="res",` (`recap_html_template.mrtm`).
- `toggle` does not re-check the time window. Membership in the in-memory set is the only guard (`reservation.py:45-50`).
- `_request_new_report` ignores `user_id` (`meals_management.py:86`).
- Hardcoded values in `var.py`: the porter's-lodge receiver (`var.py:41`), a personal address used as the DEBUG receiver (`var.py:61`), the mailbox name, the times, `TIMELIMIT`, and the Italian meal names (also hardcoded in the template).
- Dead code: `var.RECAP_EXT` (`var.py:19`) and `utl.get_date_from_filename_old` (`modules/utility.py:135`).
- Nothing ever cleans up `menus/`, `recaps/` or `reports/`.
- `_task_download_menu` blocks the service loop for up to 15 s per attachment. Bot requests to this service, such as booking, wait during that time.
- Cross-cutting (bot side): user-typed text such as the report is passed through `str.format` by `format_data` (`services/ghislieri_bot/components.py:22`), so a `{` in a report breaks the request. The admin notification text also inserts it without HTML-escaping.
