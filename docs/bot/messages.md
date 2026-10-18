# Bot message format (`.gsm`)

Every screen the bot can show is a JSON file under `messages/`. At startup `Bot._load_messages` reads the whole
tree. Folders become namespaces, and the file name up to its first `.` becomes the leaf. So
`messages/calendar_manager/new_event/main.gsm` is reached as `calendar_manager.new_event.main`. That dotted
path is what `NEW`, notification `msg_code`s and the special codes in `var.py` refer to.

How messages are rendered and how sessions work is explained in [README.md](README.md).
The implementation is in `services/ghislieri_bot/message.py` and `components.py`.

## File structure

```json
{
  "code": "calendar_manager.new_event.main",
  "whitelist": ["master"],
  "blacklist": ["signup"],
  "components": { "TEXT": {...}, "KEYBOARD": {...}, "ANSWER": {...} }
}
```

| Key | Required | Meaning |
|---|---|---|
| `code` | yes | Message code used in callback data, in the "wrong msg_code" check and in auth-error reports. It **should equal the dotted path**. Nothing enforces it (see Appendix C). |
| `components` | yes | Object mapping component type to its definition. One of each type at most. |
| `whitelist` | no | List of groups. The user needs at least one of them. |
| `blacklist` | no | List of groups. The user must have none of them. |

The permission check runs on every render of the message. See README, *Permissions and groups*.

Components are rendered **in the order they appear in the JSON**. That order matters: a TEXT action that loads
data with `REQ` must come before the KEYBOARD that displays it. By convention TEXT is first.

## Components

### When actions run

| Component | Actions run |
|---|---|
| TEXT, PHOTO | On **every render** of the message, before formatting. Every key press, every message the user sends, and every reset re-renders. |
| ANSWER, FILE_ANS, PHOTO_ANS | When the user sends text / a document / a photo while this message is current. |
| Keyboard key / option / datetime | When the key is pressed. |

KEYBOARD itself has no `actions`.

### TEXT

| Key | Required | Notes |
|---|---|---|
| `text` | yes | HTML (`parse_mode=HTML`), formatted with `format_data`. |
| `actions` | no | Run on every render. |

Every message needs a TEXT, because the live message is a text message. All 111 files have one.

### PHOTO

| Key | Required | Notes |
|---|---|---|
| `filepath` | yes | Path of the image on the server, formatted (`$` allowed). |
| `caption` | no | Formatted. Default none. |
| `actions` | no | Run on every render. |

The photo is sent as a separate message above the live message, and the live message is sent again (not
edited). The photo is deleted at the next dispatch.

### ANSWER

| Key | Required | Notes |
|---|---|---|
| `ans_data_key` | yes | Formatted. The user's text (`message.text_html`, HTML) is stored there. |
| `actions` | no | Run after storing. |

Without an ANSWER component, text the user sends is deleted and ignored.

### FILE_ANS

| Key | Required | Notes |
|---|---|---|
| `filepath` | yes | List of path segments, each formatted, joined under the global data dir (`/var/opt/ghislieri_services`, or `./data` with `-d`). If the name exists, `_1`, `_2`, ... is appended. |
| `paths_data_key` | no | Formatted. The saved path is appended (`+= (path,)`), so the key must already hold a list or tuple. Initialize it with `SAVE key []`. |
| `mime_types` | no | List of accepted MIME types. Default: any. Other files are silently ignored (no actions run). |
| `actions` | no | Run after a successful download. |

Before the download, `data["datetime"]` (`YYYY-MM-DD HH:MM:SS`) and `data["date"]` (`YYYY-MM-DD`) are set, so
`filepath` can use `{datetime}` / `{date}`.

### PHOTO_ANS

Same keys as FILE_ANS. `mime_types` is ignored. The largest available size of the photo is saved.

### KEYBOARD

An object whose keys are keyboard *parts*: `buttons`, `options`, `datetime`, `navigation`. Any other key fails
at load time. Each part appears at most once. Rows are emitted in the JSON order of the parts.

#### Keys (used by `buttons`; the other parts build them internally)

| Key | Required | Notes |
|---|---|---|
| `text` | yes | Formatted (`$` allowed). |
| `id` | yes | Unique within the part (the first match wins). No `:`. Counts toward the 64-byte callback limit. |
| `url` | no | Formatted. Makes it a URL button with no callback, so its actions never run. |
| `whitelist`, `blacklist` | no | Hide the key from users who fail the check. **Display only**: pressing is not re-checked. |
| `actions` | no | Run in order when pressed. |

#### `buttons` (flag `b`)

A list of rows, each a list of keys. Rows that end up empty (all keys hidden) are dropped.

#### `options` (flag `o`)

One key per element of a list held in session data. Selecting one stores that element and runs the actions.

| Key | Required | Notes |
|---|---|---|
| `text` | yes | Key label template. Formatted with a copy of the session data **updated with the option's own fields**, so each option must be a dict. |
| `opt_data_key` | yes | Formatted. Data key holding the list of options. |
| `ans_data_key` | yes | Formatted. The selected option (the original dict) is stored here. |
| `page_data_keys` | no | `[page_key, max_key]`, **not formatted**. Enables paging. `page_key` starts at 1 if missing. `max_key` is recomputed on every render as `ceil(len / (w*h))`. |
| `page_shape` | no | `[w, h]` = columns × rows per page. Default `[1, 100]`. |
| `actions` | no | Run after storing the selection. |

Key ids are the index on the current page. Without `page_data_keys` only the first `w*h` options are shown.
Pair paging with a `navigation` `arrows` or `pages` generator that uses the same two keys.

#### `datetime` (flag `d`)

A date/time picker that stores its state in one data key.

| Key | Required | Notes |
|---|---|---|
| `type` | yes | `datetime`, `date` or `time`. |
| `ans_data_key` | yes | Formatted. Holds the state dict below. |
| `minute_inc` | no | Parsed (default 15) but **unused**. Minutes always go in steps of 5. |
| `actions` | no | Run after **every** picker press. |

State dict: `{"dt": ISO string, "status": ..., "date": "YYYY-MM-DD", "time": "HH:mm", "text": long Italian
format, "short": short Italian format}`. If the key is missing, or `dt` is null or unparsable, it is initialized
to the current hour (local time labelled as UTC).

| `status` | Keys shown | Press → |
|---|---|---|
| `null` | Date label (id `date`, if type has a date) and time label (id `hour`, if type has a time) | status becomes the pressed id |
| `"date"` | `◀` (`-`), month label (`null`), `▶` (`+`), then a month grid (blank cells are `null`) | arrows change month (stay in `date`); a day sets the day → `null` |
| `"hour"` | 4 × 6 grid `00`–`23` | sets hour → `"minute"` |
| `"minute"` | 2 × 6 grid `:00`–`:55` | sets minute → `null` |

Keys with id `null` do nothing. The messages that use the picker add their own ✔/❌ buttons to confirm or reset.

#### `navigation` (flag `n`)

A list of rows. Each row is a list of generator specs `[name, *args]`. The keys produced by all specs in a row
are put on one row.

| Generator | Args | Keys (id: action) |
|---|---|---|
| `back` | `[text="↩️ Back"]` | `back`: `BACK` |
| `home` | `[text="🏠 Home"]` | `home`: `HOME` |
| `arrows` | `page_data_keys` | `arrow_l`: `PAGE keys -1`; `arrow_r`: `PAGE keys +1` |
| `pages` | `page_data_keys` | as `arrows`, plus a middle `page_counter` showing `{page} / {max}` that does `SAVE page_key 1` |

Example: `[[["arrows", ["p", "p_max"]]], [["back"]]]` is one row of arrows and one row with Back.

## Actions

An action is a JSON list `[NAME, arg1, arg2, ...]`. Missing trailing arguments take their defaults. All
arguments go through `format_data` when the action runs, unless noted.

| Action | Arguments | Effect |
|---|---|---|
| `NEW` | `code`, `condition_key=null`, `else_code=null` | Push message `code`. With `condition_key` (**not formatted**), push `code` if `data[condition_key]` is truthy, else `else_code`. Unknown codes raise `KeyError`. |
| `BACK` | `n=1` | Pop `n` messages. Popping the whole stack breaks the session (`IndexError` on the next render). |
| `HOME` | none | `reset_session()`: next pending notification, else `home`. Session data is reset. |
| `REQ` | `service`, `r_type`, `send_data={}`, `recv_key=null` | Synchronous call `service._request_<r_type>(**send_data)`. If `recv_key` is set, the return value is stored there. Exceptions from the service abort the whole update. |
| `SAVE` | `key`, `value` | `data[key] = value`. |
| `PAGE` | `[page_key, max_key]`, `increment` | `page = (page + increment - 1) % max + 1`, which wraps around. `max == 0` raises `ZeroDivisionError`. |

Actions of one component run in list order. A common pattern is to `SAVE` some parameters and then `NEW` a
generic editor message that reads them (see `calendar_manager.new_event.main` → `edit_text`).

## Formatting: `format_data(raw, data)`

`components.py:15`. Applied recursively:

| `raw` | Result |
|---|---|
| string starting with `$` | `key = raw[1:].format(**data)`, then `format_data(data[key], data)`. Indirection: the result is the **value** stored at `key`, of any type, and is itself formatted again. |
| other string | `raw.format(**data)` (Python `str.format`). |
| dict | New plain dict with formatted keys and values. |
| list / tuple | **Tuple** of formatted items. |
| anything else (number, bool, null, set) | Unchanged. |

Inside `{...}` use item syntax for nesting: `{new_event[begin][short]}`. `{a.b}` is *attribute* access and fails on
dicts. Write `{{` / `}}` for literal braces. `$` paths use dots instead: `$new_event.begin.dt`. Both can be
combined: `"$infos.{edit_infos_key}"` first becomes `$infos.name`, then the value of `infos.name`.

Formatted: TEXT `text`, PHOTO `filepath`/`caption`, key `text`/`url`, `opt_data_key`, every `ans_data_key`,
FILE_ANS `filepath` segments and `paths_data_key`, and all action arguments except NEW's `condition_key`.
Not formatted: key `id`, options `page_data_keys`, datetime `type`.

### Session data (`dotdict`, `modules/utility.py`)

- `data["a.b.c"]` reads nested values: the key is split at the first dot and the rest is looked up in the child.
  This keeps working while each child is a `dotdict`. The last container may be a plain dict, but a plain dict
  higher up ends the chain.
- Assigning a dict through `data[...] = value` converts it to a `dotdict`, but only its top level.
  Notification data is merged with `dict.update` and stays plain. So with notification data, use at most
  `$x.y`.
- `data["a.b"] = v` creates `a` as a `dotdict` if it is missing.

Keys always present (they survive every reset):

| Key | Value |
|---|---|
| `user_id` | Telegram user id (int) |
| `infos` | dict `name`, `surname`, `gender`, `email` (values may be `null` for new users) |
| `groups` | set of the user's groups |
| `permissions` | set of groups plus all their dotted prefixes |

Sometimes present: the notification's `data` keys (when the session was started by a notification);
`auth_error.code` (in `utility.auth`); `datetime` / `date` (after a file or photo upload); paging keys created by
`options`. Everything else is whatever the session's actions stored.

## Examples (shortened)

**Paged list loaded by a request** (`admin/logs/list.gsm`):

```json
{
  "code": "admin.logs.list",
  "components": {
    "TEXT": {"text": "👥    Select <b>log</b>",
             "actions": [["REQ", "ghislieri_services", "get_logs", {}, "admin.logs_list"]]},
    "KEYBOARD": {
      "options": {"text": "{filename}", "opt_data_key": "admin.logs_list",
                  "ans_data_key": "admin.selected_log",
                  "page_data_keys": ["logs_list_page", "logs_list_page_max"], "page_shape": [1, 6],
                  "actions": [["SAVE", "logs_page", 1], ["NEW", "admin.logs.show"]]},
      "navigation": [[["arrows", ["logs_list_page", "logs_list_page_max"]]], [["back"]]]
    }
  }
}
```

**Generic text editor driven by session parameters** (`settings/profile/edit.gsm`). The calling button did
`SAVE edit_infos_key "name"`, `SAVE edit_infos_dialog "..."`, `NEW settings.profile.edit`:

```json
{
  "code": "settings.profile.edit",
  "components": {
    "TEXT": {"text": "✏️ Inserisci {edit_infos_dialog}"},
    "KEYBOARD": {"navigation": [[["back"]]]},
    "ANSWER": {"ans_data_key": "infos.{edit_infos_key}",
               "actions": [["REQ", "student_databaser", "edit_student_info",
                            {"user_id": "$user_id", "info": "$edit_infos_key",
                             "value": "$infos.{edit_infos_key}"}],
                           ["BACK"]]}
  }
}
```

**Date/time picker with confirm/reset** (`calendar_manager/new_event/edit_datetime.gsm`):

```json
{
  "code": "calendar_manager.new_event.edit_datetime",
  "components": {
    "TEXT": {"text": "🕓️    Inserisci l'orario di {edit_datetime_dialog} dell'evento"},
    "KEYBOARD": {
      "datetime": {"type": "datetime", "ans_data_key": "new_event.{edit_datetime_key}"},
      "buttons": [[
        {"text": "❌", "id": "back", "actions": [
          ["SAVE", "new_event.{edit_datetime_key}", {"dt": null, "status": null, "text": "--:--", "short": "--:--"}],
          ["BACK"]]},
        {"text": "✔", "id": "ok", "actions": [["BACK"]]}
      ]]
    }
  }
}
```

## Gotchas

- **`code` vs path.** Navigation uses the path, callbacks use `code`. A copied file with a stale `code` still
  loads, but the stale-callback check and auth-error reports use the wrong name (four files today, Appendix C).
- **64-byte callback data**: `len(code) + len(id)` ≤ 54 bytes. The longest today is 48 (58 bytes total).
- **TEXT actions repeat on every render.** Do not put side effects there (for example `add_notification`) unless
  repeats are harmless. `welcome.checking` does, and spams admins.
- **`$` re-formats strings.** `"$x"` runs `.format(**data)` on every string inside `data[x]`. If a user or service
  string contains `{` or `}` it raises, or worse, gets substituted. Plain templates like `"{x}"` do not re-format
  substituted values. `notifications.custom` relies on that double formatting on purpose (the admin's text may
  contain `{infos[name]}`).
- **Lists become tuples** after formatting. JSON `[]` in `SAVE` stores `()`.
- **Sets** (`groups`, `permissions`) print as Python reprs. Pass them to services with `"$permissions"`.
- **Options** must be dicts. Their fields shadow session keys in the label, and fields from the previous option
  leak into the next option's label if absent (`opt_data.update`).
- **HTML**: static text must escape `<`, `>`, `&`. Data from services is inserted unescaped, and a bad entity makes
  the whole edit fail.
- **Key whitelists are cosmetic.** Protect sensitive target messages with a message-level `whitelist`.
- **`HOME` may not lead home**: it shows the next pending notification first.
- `BACK n` must not exceed the stack depth. Flows that end with `BACK 3`/`BACK 4` depend on the exact path taken.
- Telegram limits the message text to 4096 characters (relevant for `admin.errors.show` and `settings.changelog`).

---

## Appendix A: message tree

111 files. Folders with a `menu` are entered from `home`. Restrictions are noted where a message has a whitelist.

**Root and utility**
- `home`: main menu. Buttons filtered by group (`signup` sees only "sign up"; `master` sees Admin).
- `utility.auth`: authorization error, shows the denied code.
- `utility.error`: generic error page (defined, never used by code).
- `utility.bot_shutdown`: shown to everyone on shutdown (no keyboard).

**welcome/**: signup for new users
- `welcome`: intro. `insert_surname`, `insert_name`: collect and save the name (declared codes clash, see C).
- `checking`: "verifying your account" notification. Its TEXT notifies masters.
- `thank_you`: approval notification.

**notifications/**: notification targets
- `update`: new version (button to `settings.changelog`). `new_channel_message`: link to a channel.
  `supersega_season`: tournament announcement. `custom`: text written by an admin.
- `admin.check_subscription` (master): approve/reject a signup. `admin.set_gender`, `admin.set_group` (master):
  approval steps.
- `admin.new_eduroam_report` (master), `admin.new_meal_report` (master, representative),
  `admin.new_social_submission` (master, social_rep): alerts from services.
- `admin.google_credentials_login` (master): Google login alert (only referenced by commented-out code).

**admin/** (entry `admin.menu`, master)
- `menu`: hub.
- `errors.list` / `errors.show`: browse error files.
- `logs.list` / `logs.show`: browse log files, paged.
- `notifications.menu` (master): send update / SuperSega notifications, open the channel picker or custom editor.
- `notifications.channel_select` (master): announce a new channel message to students.
- `notifications.custom.new` (master): draft editor. `insert_text`, `insert_receiver`, `insert_time`,
  `insert_notify`: field editors. `preview`: preview and send.
- `services.menu` (master): pick a service or shutdown. `services.options`: service stats and restart.
  `execs_stats`, `reqs_stats`: hourly histograms. `restart_service`, `shutdown`: confirmations.
- `students.list`: paged student list. `students.options`: details, remove, add/remove group.
  `students.edit_group`: group picker.

**calendar_manager/**
- `calendar`: events of a day, previous/next day, menu.
- `event_details`, `event_details_url`: event card (the second when the event has a link). Edit/delete keys shown
  to master/admin.
- `insert_date`: date picker to jump to a day (declared code is misspelled).
- `menu`: go to date, new event (master/admin/calendar), admin.
- `admin.menu` (master): import the RSS feed.
- `new_event.select_class`: event class, filtered by `calendar.*` groups. `new_event.main`: form.
  `edit_text`, `edit_datetime`, `select_cat`: field editors. `recap`: preview and submit. `confirmation`, `error`.
- `edit_event.*`: the same for an existing event, plus `select_status` (declared code clashes with `select_cat`).
- `delete_event.main`: confirm. `confirmation`, `error`.

**meals_management/**
- `menu`: reserve, today's menu, report, admin.
- `reservation.reservations`: toggle meal reservations. `reservation.reminder`: reminder notification.
- `todays_menu.show`: menu image (PHOTO). `todays_menu.not_found`.
- `report.report`, `photo`, `add_photos`, `recap`, `thank_you`: canteen report with photos.
- `admin.menu`, `admin.create_recap`, `admin.send_recap` (master): reservation recaps, menu download.

**content_submitter/**
- `menu`.
- `socials.photo`, `add_photos`, `description`, `recap`, `thank_you`: photos for the social media accounts.
- `eduroam_report.report`, `place`, `notes`, `recap`, `thank_you`: Wi-Fi problem report.

**printer_service/**
- `send_file`: upload a PDF (FILE_ANS). `options`: print settings. `set_copies`, `set_page_list`, `set_sides`,
  `set_number_up`: option editors. `printing`: confirm and print. `confirmation`, `error`.

**settings/**
- `menu`. `profile.menu` / `profile.edit`: edit name, surname, email. `feedback.feedback` / `thank_you`: send
  feedback. `changelog`. `about`.

**telegram_channels/**: `menu`, `sports`, `student_associations`: invite-link buttons.

**services_reservation/**: `menu`: link to an external booking sheet.

## Appendix B: REQ actions

59 `REQ` actions. `×n` means the same call appears n times in the file.

| Service | r_type | Message file (`messages/...`) |
|---|---|---|
| ghislieri_services | get_errors | admin/errors/list.gsm |
| ghislieri_services | get_error | admin/errors/show.gsm |
| ghislieri_services | get_logs | admin/logs/list.gsm |
| ghislieri_services | get_log | admin/logs/show.gsm |
| ghislieri_services | get_version | admin/notifications/menu.gsm, settings/about.gsm, settings/changelog.gsm |
| ghislieri_services | restart_service | admin/services/restart_service.gsm |
| ghislieri_services | shutdown | admin/services/shutdown.gsm |
| `$serv_name` (dynamic) | get_statistics | admin/services/options.gsm |
| ghislieri_bot | add_notification | admin/notifications/channel_select.gsm ×6, admin/notifications/menu.gsm ×2, admin/notifications/custom/preview.gsm, notifications/admin/set_group.gsm, welcome/checking.gsm, welcome/insert_name.gsm |
| ghislieri_bot | edit_groups | admin/students/edit_group.gsm, notifications/admin/set_group.gsm ×2 |
| ghislieri_bot | expire_notification | notifications/admin/set_group.gsm |
| ghislieri_bot | remove_chat | admin/students/options.gsm, notifications/admin/check_subscription.gsm |
| ghislieri_bot | save_feedback | settings/feedback/feedback.gsm |
| student_databaser | get_chats | admin/students/list.gsm |
| student_databaser | get_groups | admin/students/edit_group.gsm |
| student_databaser | edit_student_info | notifications/admin/set_gender.gsm ×2, settings/profile/edit.gsm, welcome/insert_name.gsm, welcome/insert_surname.gsm |
| calendar_manager | get_day_events | calendar_manager/calendar.gsm |
| calendar_manager | get_event_dict | calendar_manager/event_details.gsm, calendar_manager/event_details_url.gsm |
| calendar_manager | get_categories | calendar_manager/menu.gsm, calendar_manager/new_event/select_cat.gsm, calendar_manager/edit_event/select_cat.gsm |
| calendar_manager | add_event | calendar_manager/new_event/recap.gsm |
| calendar_manager | edit_event | calendar_manager/edit_event/recap.gsm |
| calendar_manager | remove_event | calendar_manager/delete_event/main.gsm |
| calendar_manager | update_rssfeed | calendar_manager/admin/menu.gsm |
| content_submitter | get_default_eduroam_reports | content_submitter/eduroam_report/report.gsm |
| content_submitter | new_eduroam_report | content_submitter/eduroam_report/recap.gsm |
| content_submitter | new_socials_submission | content_submitter/socials/recap.gsm |
| meals_management | get_active_reservations | meals_management/reservation/reservations.gsm |
| meals_management | toggle_meal_res | meals_management/reservation/reservations.gsm |
| meals_management | get_todays_menu | meals_management/menu.gsm |
| meals_management | get_all_res_dates | meals_management/admin/create_recap.gsm, meals_management/admin/send_recap.gsm |
| meals_management | create_recap | meals_management/admin/create_recap.gsm |
| meals_management | send_recap | meals_management/admin/send_recap.gsm |
| meals_management | download_menu | meals_management/admin/menu.gsm |
| meals_management | new_report | meals_management/report/recap.gsm |
| printer_service | print_files | printer_service/printing.gsm |

## Appendix C: cross-check results

Checked against the `_request_<r_type>` methods in `services/<service>/*.py`, `modules/ghislieri_services.py`
(service `ghislieri_services`) and `modules/base_service.py` (`stop`, `get_statistics` on every service).

**Method existence and signatures**: every static `REQ` resolves to an existing method, and its `send_data` keys
match the signature: all required parameters present, no unexpected keyword (or the method takes `**kwargs`).
No missing methods.

**Semantic mismatches**
1. `admin/services/options.gsm` → `restart_service` with `serv_name = ghislieri_services` deadlocks the master
   process. `_request_restart_service` sends `stop` to its own pipe and waits for an answer only it could give
   (`modules/ghislieri_services.py:43-46`).
2. `admin/services/menu.gsm` hard-codes 8 service names. `channels_manager` (started by the systemd unit) is
   missing, and choosing a service that was not started raises `KeyError` in `BaseService.send_request`.
3. Group name: content_submitter notifies `socials_rep` (`services/content_submitter/var.py:19`), but
   `notifications/admin/new_social_submission.gsm` whitelists `social_rep`. Members of `socials_rep` who are not
   `master` get the authorization error.
4. Custom notifications by user id never arrive. `insert_receiver` stores the typed text, a string, as
   `users = ("<id>",)`, while `Notification.check_user` compares against integer user ids. Only one receiver per
   field can be entered.
5. Admin "Remove group" (`edit_groups` with `edit: "rm"`) for a group the user does not have raises: `_edit_group`
   catches `ValueError`, but `set.remove` raises `KeyError` (`services/student_databaser/student_databaser.py:40-43`).
6. `edit_student_info`'s `info` is interpolated into the SQL column name
   (`services/student_databaser/student_databaser.py:31`). Today it only comes from fixed `SAVE` values.
7. `content_submitter.py` defines `_request_get_default_eduroam_reports` and `_request_new_eduroam_report` twice
   (lines 20-42). The second definition wins. Harmless.

**Broken references**
- `NEW` targets (119 actions, including `else_code`s): **none broken**. All are static and exist.
- `msg_code`s in `add_notification` calls (services' `var.py` files and messages): **none broken**:
  `meals_management.reservation.reminder`, `notifications.admin.new_meal_report`,
  `notifications.admin.new_eduroam_report`, `notifications.admin.new_social_submission`,
  `notifications.admin.google_credentials_login` (dead code only), `notifications.new_channel_message`,
  `notifications.update`, `notifications.supersega_season`, `notifications.custom`,
  `notifications.admin.check_subscription`, `welcome.checking`, `welcome.thank_you`. The special codes in
  `var.py` (`home`, `utility.error`, `utility.auth`, `utility.bot_shutdown`) exist.
- Declared `code` ≠ file path (navigation still works because it uses the path):

  | File | Declared code |
  |---|---|
  | `calendar_manager/insert_date.gsm` | `calendar_manager.insert_datae` |
  | `calendar_manager/edit_event/select_status.gsm` | `calendar_manager.edit_event.select_cat` (duplicate) |
  | `notifications/admin/set_group.gsm` | `notifications.admin.set_gender` (duplicate) |
  | `welcome/insert_surname.gsm` | `welcome.insert_name` (duplicate) |

  With a duplicated code, a stale callback from one message can be accepted by the other, and auth errors
  report the wrong code.
