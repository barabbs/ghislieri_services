# Architecture (legacy, v0.5.x)

This describes the system as it is on `main` (v0.5.2, last PR #63). The `rework` branch will change much of it; see [rework/proposal.md](rework/proposal.md).

## Overview

Ghislieri Services is one Python program that runs several independent *services* plus a Telegram bot front end. Students interact only with the bot; the bot calls the other services to read or change data.

```
main.py
 └─ GhislieriServices (modules/ghislieri_services.py)   ← supervisor, also a service
     ├─ student_databaser   (users, groups, chat state)
     ├─ calendar_manager    (college calendar, events)
     ├─ email_service       (mailbox polling, sending)
     ├─ printer_service     (print jobs via CUPS)
     ├─ meals_management    (menus, reservations, recaps)
     ├─ content_submitter   (eduroam reports, social media submissions)
     ├─ channels_manager    (Facebook page → Telegram channel)
     └─ ghislieri_bot       (Telegram bot, renders messages/*.gsm)
```

Each service is a separate OS process. They communicate only through request/response pipes.

## Startup

```
python main.py [-d] [--no_sync] <service> [<service> ...]
```

- Positional arguments are the services to start. The production unit (`ghislieri_services.service`) lists all eight.
- `-d` enables DEBUG mode: the data directory becomes `./data` instead of `/var/opt/ghislieri_services`, the bot uses the test token, and session/sync timeouts get shorter. DEBUG is read from `sys.argv` independently in `modules/var.py` and in every `services/*/var.py`.
- `--no_sync` disables the bot's periodic chat sync.

`main.py` configures the root logger (a new log file per start in `data/logs/`, plus stderr). It then builds `GhislieriServices` and calls `run()`.

## Services framework

### `BaseService` (`modules/base_service.py`)

Every service subclasses `BaseService`, which subclasses `multiprocessing.Process`. Its `run()` is a polling loop at 16 Hz (`SERVICE_UPDATE_INTERVAL = 0.0625` s):

1. `_update()`: per-service hook, empty by default.
2. `_execute_tasks()`: runs due jobs of a per-service [`schedule`](https://schedule.readthedocs.io) scheduler. Subclasses register jobs in `_load_tasks()`.
3. `_handle_requests()`: drains incoming requests from the service's pipe.

Conventions:

- Methods named `_request_<name>` are the service's RPC API. A request with `r_type="<name>"` calls the method through `getattr`.
- Methods named `_task_<name>` are scheduled jobs. The `@task` decorator logs exceptions and writes an error file instead of crashing the process.
- `_stop()` runs on a stop request. `_exit()` runs when the loop ends; the base version saves statistics.

Each service also keeps simple statistics: loop execution times, request counts and errors, and an hourly 24-slot history. They are saved to `data/statistics/<service>.gsst` on exit and reloaded (then deleted) on start. Admins see them in the bot.

### RPC (`modules/service_pipe.py`)

- `Request(service_name, r_type, *args, **kwargs)` is a plain picklable object.
- The parent creates one `ServicePipe` per service (a duplex `multiprocessing.Pipe` plus a `Lock`) before forking. Every process therefore holds every pipe.
- `send_request` takes the target pipe's lock, sends the request, and **blocks** until the result arrives. If the result is an `Exception`, it is re-raised in the caller.
- The target polls its end of the pipe in its loop and sends back the return value. A method may raise `NoResultRequest` when it has already replied by itself (for example `restart_service`).

Consequences: calls are synchronous. Latency is bounded below by the target's loop period. Two services calling each other at the same moment can deadlock.

### Supervisor (`modules/ghislieri_services.py`)

`GhislieriServices` is itself a `BaseService` (its loop runs in the main process). It:

- imports `services.<name>.<name>` and instantiates the module's `SERVICE_CLASS`;
- starts all processes, then checks every 5 minutes for dead ones and restarts them;
- exposes admin requests: `shutdown`, `restart_service` (stop, `importlib.reload`, start), `get_errors`, `get_error`, `get_logs`, `get_log` (paginated), `get_version` (reads the changelog in `data/changelogs/`);
- on exit sends `stop` to every service, sets the shared stop `Event`, and joins the processes.

## Configuration

There is no configuration file. Constants live in `modules/var.py` (version, directories, formats) and in each `services/<name>/var.py`. Secrets and runtime settings are files in the data directory: bot tokens (`*.gbtk`), Google credentials, email credentials, printer address, channel id, and others. See the per-service docs.

## Data directory

Production: `/var/opt/ghislieri_services/` (DEBUG: `./data/`). Layout:

| Path | Content |
|---|---|
| `logs/` | one log file per process start, `;`-separated fields |
| `errors/` | one `.gser` file per caught exception (header + traceback) |
| `statistics/` | `<service>.gsst` JSON, saved on shutdown |
| `changelogs/` | `changelog_<version>.gscl`, shown by the bot |
| `<service>/` | per-service data, see [services/](services/) |

All persistence is JSON or text files written in place. There is no database and no file locking.

## Logging and errors

- Standard `logging`, configured in `main.py`. Child processes inherit the handlers through `fork`.
- Caught exceptions are also written by `utility.log_error` as separate files in `errors/`. Admins can browse them from the bot.
- Nobody is notified actively. An admin must open the bot's error list to notice a failure.

## Telegram bot

See [bot/README.md](bot/README.md) for the bot runtime and [bot/messages.md](bot/messages.md) for the JSON message format.
