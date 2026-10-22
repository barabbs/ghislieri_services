# printer_service

Code: `services/printer_service/` (`printer_service.py`, `var.py`)

## Purpose

`printer_service` lets students print PDFs sent to the bot. The bot saves each uploaded file to disk. This service then runs the CUPS `lp` command once per file against the machine's **default printer**, passing the user's chosen options (copies, page range, sides, pages per sheet). The service does not configure the printer. That is done in CUPS, through the web UI at `http://<host>:631` or with `lpadmin`/`lpoptions`.

## Requests API

| Request | Args | Returns | What it does | Used by |
|---|---|---|---|---|
| `print_files` | `filepaths` (list of absolute paths), `copies=1`, `page_list=None` (e.g. `"1,3-5"`), `**kwargs` (each non-`None` pair becomes `-o key=value`) | `{"ok": True, "text": ""}`, or `{"ok": False, "text": <Italian message + lp stderr>}` | For each file, runs `lp -n <copies> [-o k=v ...] -t "ghislieri_services <timestamp>" [-P <page_list>] "<basename>"` with `shell=True`, `cwd` set to the file's directory and a 60 s timeout. If `copies` is not an int, it falls back to 1. It stops at the first failure. | `messages/printer_service/printing.gsm`, called with `filepaths=$print_job.files`, `copies`, `page_list`, `sides` (`one-sided` / `two-sided-long-edge` / `two-sided-short-edge`) and `number-up` (`null`/2/4/6/9/16) |

`stop` and `get_statistics` are inherited from `BaseService`.

The bot flow works like this. `printer_service.send_file` accepts `application/pdf` uploads and saves them as `<data>/printer_service/files/print_<datetime>_<user_id>.pdf`. `set_copies` and `set_page_list` take **free-text** answers from the user. `set_sides` and `set_number_up` are buttons. On failure, `error.gsm` shows `print_result.text`. The menu entry in `messages/home.gsm` is limited to group `student`.

## Scheduled tasks

None of its own, only the inherited hourly `_task_update_statistics`.

## `_update` loop

Not overridden.

## Inter-service calls

None. The service sends no requests and no notifications.

## Data & files

Data dir: `/var/opt/ghislieri_services/printer_service/`, or `./data/printer_service/` with `-d`.

| Path | Purpose |
|---|---|
| `files/print_<YYYY-MM-DD HH:MM:SS>_<user_id>.pdf` | Uploaded PDFs. The **bot** writes them (`ghislieri_bot/components.py:135`, path from `send_file.gsm`). Nothing deletes them. `var.FILES_DIR` names this directory, but the service never uses it. |
| `printer_address.txt` | One line with a printer address. It is read only by the unused `get_printer_address()` (the call in `__init__` is commented out), so it is dead config. |

The service needs no credentials.

## External dependencies

- The system binary `lp` (CUPS client), with a **default destination** configured for the service user (`lpadmin -d <printer>` or `lpoptions -d`).
- A CUPS server that supports `-o sides=...`, `-o number-up=...` and `-P <page-list>`.
- Python standard library only (`subprocess`).

## Known issues / smells

- **Shell injection (critical)**, `services/printer_service/printer_service.py:32,41`: `page_list` is free text typed by any `student` user (`messages/printer_service/set_page_list.gsm:38-39`). It is interpolated unquoted into a `shell=True` command, so an answer like `1; <any command>` runs as the service user. The `**kwargs` option keys and values (`:29-31`) and the filename (`:41`, double quotes do not stop `$(...)`) take the same path into the shell, though today they come from buttons and bot-generated names. Build an argument list and drop `shell=True`.
- `printer_service.py:33-36`: only `ValueError` is caught, so `copies=None` raises `TypeError`. There is no upper or lower bound, so any user can ask for thousands of copies.
- `printer_service.py:38-48`: on a failure part-way through a multi-file job, the earlier files are already printed, and the error does not say which file failed.
- `printer_service.py:41-42`: the call is synchronous with a timeout of up to 60 s per file, and the pipe request blocks the calling bot process for that time.
- The service never checks that a file is a PDF or lies under `files/`. It prints any path it is given. The `application/pdf` check is only the Telegram MIME type the client claims (`send_file.gsm`).
- `printer_service.py:45` together with `messages/printer_service/error.gsm:5`: `lp` stderr is shown unescaped in an HTML-mode message.
- Privacy and disk: uploaded documents, with the user id in the filename, pile up forever in `files/`.
- Dead code: `get_printer_address` (`printer_service.py:12-14`) and `printer_address.txt`, the commented call (`:24`), `var.FILEPATH_PRINTER_ADDRESS` and `var.FILES_DIR` (`var.py:10,13`), and the unused `Request` import (`:2`). `opt_agrs` (`:28`) is a typo.
- `printer_service.py:40`: the full shell command is logged at INFO, including the user-supplied arguments.
