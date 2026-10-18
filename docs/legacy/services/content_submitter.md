# content_submitter

Source: `services/content_submitter/` (`content_submitter.py`, `var.py`).

## Purpose

Collects two kinds of student submissions from the bot and passes them to the people in charge:
- **Eduroam (Wi-Fi) problem reports.** Each one is saved as a file and sent as a bot notification to the `master` group.
- **Photos for the college's social media.** These are emailed with the photos attached, and a notification goes to the `master` and `socials_rep` groups.

The service has no state of its own beyond the list of default report texts, which it loads at startup.

## Requests API

| Request | Args | Returns | What it does | Used by |
|---|---|---|---|---|
| `get_default_eduroam_reports` | none | tuple of `{"report": str}`, one per line of the `.erdr` file | Fills the list of ready-made problem descriptions. The student can also type a new one. | `messages/content_submitter/eduroam_report/report.gsm` |
| `new_eduroam_report` | `user_id`, `student_infos` (dict with at least `name`, `surname`), `report`, `place`, `note` (str) | `None` | Writes an `.errp` file and notifies `master`. | `eduroam_report/recap.gsm` |
| `new_socials_submission` | `user_id`, `student_infos`, `description` (str), `photos` (tuple of paths) | `None` | Emails the photos to the `master` and `socials_rep` groups and notifies the same groups. `user_id` is unused. | `socials/recap.gsm` |

Inherited from `BaseService`: `stop`, `get_statistics`. The service is listed in the bot's admin services menu (`messages/admin/services/menu.gsm`).

## Scheduled tasks

Only the inherited `_task_update_statistics`, which runs hourly.

## `_update` loop

Not overridden.

## Inter-service calls and notifications

| Target | Request | When |
|---|---|---|
| `ghislieri_bot` | `add_notification(groups=("master",), n_type="content_submitter", msg_code="notifications.admin.new_eduroam_report", notify=True, end_time=False, data={"report": {"time", "user", "report", "place", "note"}})`. `end_time=False` means the notification never expires on its own. | `new_eduroam_report` |
| `email_service` | `send_email(sender="Servizio Social Submissions", groups=("master","socials_rep"), subject, text, attachments=photos)` | `new_socials_submission` |
| `ghislieri_bot` | `add_notification(groups=("master","socials_rep"), n_type="social_submission", msg_code="notifications.admin.new_social_submission", notify=True, data={"submission": {"date", "user", "description", "n_photos"}})` | `new_socials_submission` |

## Data and files

Data dir: `/var/opt/ghislieri_services/content_submitter`, or `./data/content_submitter` with `-d`.

| Path | Written by | Format |
|---|---|---|
| `default_eduroam_reports.erdr` | maintained by hand | UTF-8 text, one default report per line. Read once in `__init__`, so edits need a restart. |
| `eduroam_reports/<user_id> - <YYYY-MM-DD HH:MM:SS>.errp` | `new_eduroam_report` | See below. Never deleted. |
| `socials_submissions/Social_Submission_<user_id>_<date>[_N].jpg` | **the bot** (`PHOTO_ANS` in `socials/photo.gsm`, `socials/add_photos.gsm`) | The submitted photos. They are emailed but never deleted. |

`.errp` file:

```
name=Mario
surname=Rossi
user_id=123456789
time=2030-01-05 12:34:56

PLACE:	 <place text>
REPORT:	 <report text>
NOTE:	 <note text>
```

## External dependencies

None beyond the other services (`email_service` for SMTP, `ghislieri_bot` for notifications).

## Known issues / smells

- **Duplicated methods.** `_request_get_default_eduroam_reports` and `_request_new_eduroam_report` are each defined twice (`content_submitter.py:20-30` and `:32-42`). The second definition silently overrides the first. Delete one copy.
- If `default_eduroam_reports.erdr` is missing, `__init__` raises (`content_submitter.py:17`). Services are built in the parent process (`modules/ghislieri_services.py:30`), so the whole application fails to start, or `_task_check_services` fails when it tries to restart the service.
- A trailing empty line in the `.erdr` file becomes an empty option (`split("\n")`, `content_submitter.py:18`).
- `.errp` filenames have one-second resolution: two reports from the same user in the same second overwrite each other (`content_submitter.py:26`).
- Submitted text is stored and forwarded unescaped. The admin notification texts insert it into Telegram HTML, so a `<` in a report can make the notification fail. The bot also runs user text through `str.format` (`services/ghislieri_bot/components.py:22`), so a `{` breaks the request.
- If an email fails, nobody finds out. `email_service._send_email` catches and logs every exception, and the user still gets "thank you".
- Nothing ever deletes the submitted photos (`socials_submissions/`) or `.errp` files.
- Hardcoded group names and the Italian email subject and body (`var.py:16-23`).
