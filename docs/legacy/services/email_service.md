# email_service

Code: `services/email_service/` (`email_service.py`, `var.py`)

## Purpose

`email_service` is the project's only gateway to email. It sends plain-text emails, optionally with file attachments, through Gmail SMTP. It also downloads the attachments of unread emails from a Gmail IMAP folder. It logs in with a username and password stored in a local file. An older Gmail-API/OAuth2 implementation is still in the file, fully commented out.

## Requests API

| Request | Args | Returns | What it does | Used by |
|---|---|---|---|---|
| `send_email` | `sender` (str, used as `From:` header **and** SMTP envelope sender), `receivers=None` (iterable of addresses), `groups=None` (iterable of group names), `subject`, `text`, `attachments=None` (iterable of local file paths) | `None` | If `groups` is given, adds the non-null `email` of every active user in each group (via `student_databaser.get_chats`) to `receivers`. It then builds a MIME message (`text/plain` body, each attachment as `application/<file extension>`) and sends it through `SMTP_SSL` to `smtp.gmail.com`. Errors are logged and written to a `.gser` file, but not returned. | `meals_management/meals_management.py:46` (daily reservation recap PDF), `meals_management.py:91` (meal report with photos), `content_submitter/content_submitter.py:49` (social submission with photos). Sender, groups and receivers come from those services' `*_EMAIL_METADATA` in `var.py`. |
| `download_attachments` | `mailbox="INBOX"` (IMAP folder or Gmail label) | `list` of `{"date": "YYYY-MM-DD HH:MM:SS", "filepath": <saved path>}` | Logs in over `IMAP4_SSL` to `imap.gmail.com`, selects `mailbox` and searches `UNSEEN`. For each message, newest first, it fetches `RFC822`, which also marks it as read. It saves every part that has a filename to `attachments/<filename>`, adding `_1`, `_2`, ... if the name is taken. `date` is the email's `Date:` header. Errors are logged, and whatever was collected so far is returned. | `meals_management/meals_management.py:115` (`mailbox="Meals/menu"`, downloads the weekly menu `.docx` files) |

`stop` and `get_statistics` are inherited from `BaseService`. No `.gsm` message calls this service directly.

## Scheduled tasks

None of its own, only the inherited hourly `_task_update_statistics`. Callers trigger the work, e.g. `meals_management._task_download_menu`.

## `_update` loop

Not overridden.

## Inter-service calls

- `student_databaser.get_chats(group=g)`, once per group in `send_email(groups=...)` (`email_service.py:110`). The call is made synchronously from inside a request handler.
- No notifications are sent. `var.GOOGLE_CREDENTIALS_NOTIFICATION_DATA` (`msg_code` `notifications.admin.google_credentials_login`) was used only by the commented-out OAuth code.

## Data & files

Data dir: `/var/opt/ghislieri_services/email_service/`, or `./data/email_service/` with `-d`.

| Path | Format / purpose |
|---|---|
| `email_credentials_file.escr` | **Required.** One line, `username,password` (e.g. `someone@example.org,app-password`). Read once at start-up by `readline().split(",")`. It must have no trailing newline, and the password must not contain a comma. |
| `attachments/` | Downloaded attachments, saved under their original filename. Nothing ever cleans them up. |
| `google_credentials.json` | Leftover OAuth "installed app" client secret (`{"installed": {client_id, client_secret, ...}}`). Only the commented-out code used it. It should be removed from the data dir. |
| `google_token.json` | (Deprecated) the OAuth token path. It is not used. |

## External dependencies

- Standard library only: `smtplib`, `imaplib`, `email`.
- External services: Gmail SMTP (`smtp.gmail.com:465`, SSL) and IMAP (`imap.gmail.com:993`, SSL). The hosts are hardcoded in `var.py:23`.
- Auth: plain `LOGIN` with the credentials above. Gmail accepts this only with an App Password (2-Step Verification on) or an equivalent, since Google disabled "less secure app" access. The OAuth2 Gmail-API path (`google-auth`, `google-auth-oauthlib`, `googleapiclient`, `InstalledAppFlow.run_local_server`) is commented out (`email_service.py:14-20, 118-203`).
- The `Meals/menu` mailbox must exist as an IMAP folder or Gmail label. Gmail filters presumably put messages there.

## Known issues / smells

- **Path traversal**, `services/email_service/email_service.py:85-93`: the attachment filename comes from the email (`get_filename()` plus `decode_header`) and is joined straight onto `ATTACHMENT_DIR`. A name like `../../x` or an absolute path writes anywhere the service user can write. Anyone able to get a mail into the monitored folder controls that name.
- `email_service.py:59-61` and `:95-97`: failures are swallowed. `send_email` always returns `None`, so callers (meal recap, reports) cannot tell that an email was not sent. `utl.log_error(err)` is called without `service=`, so `.gser` files do not say which service failed.
- `email_service.py:98-103`: if `select` or `login` failed, `imap_server.close()` raises `imaplib.IMAP4.error`, and only `UnboundLocalError` is caught, so the request still fails. The same pattern appears for SMTP at `:62-66`.
- `email_service.py:75-78`: fetching `RFC822` marks every unseen message as read, including messages without attachments and messages processed before a crash. Mail that hits an error part-way is never retried.
- `email_service.py:79`: an email without a `Date:` header makes `parsedate_to_datetime(None)` raise, which aborts the whole download.
- `email_service.py:87-88`: only the first `decode_header` chunk is used, so multi-chunk encoded filenames are truncated.
- `email_service.py:57`: `sender` is used as the SMTP envelope sender, but callers pass a display name such as "Servizio ..." rather than an address. This works only because Gmail rewrites the sender to the authenticated account.
- `email_service.py:40`: the `Content-Disposition` filename is unquoted, so names with spaces or non-ASCII characters are mangled. `filepath.split('/')` and `split('.')` (`:39`) are used instead of `os.path.basename` and `splitext`, so a file without an extension gets a bogus subtype.
- `email_service.py:110`: users in several groups are added once per group, so they receive duplicate `To:` entries. Every address goes into `To:`, which exposes all recipients to each other (no `Bcc`).
- `email_service.py:55,71`: there are no socket timeouts on `SMTP_SSL` or `IMAP4_SSL`. Because pipe requests are synchronous, a hung connection blocks the calling service indefinitely.
- `email_service.py:25-27,50`: credentials are read once in `__init__` from a plaintext file, so any change needs a service restart. A trailing newline would silently break login.
- Dead code: the OAuth2 class and imports (`email_service.py:14-20,118-203`), `var.py:15-20` (`GOOGLE_*`), and the `google_credentials.json` secret still sitting in the data dir.
