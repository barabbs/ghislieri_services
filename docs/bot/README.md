# Ghislieri Bot

The Telegram front end of Ghislieri Services. It lives in `services/ghislieri_bot/` and runs as one of the
`BaseService` processes started by `main.py` (see `modules/base_service.py`). It uses python-telegram-bot 13.x.

| File | Role |
|---|---|
| `ghislieri_bot.py` | `GhislieriBot` service: inter-service requests (`_request_*`), the periodic sync task, statistics, stop/exit hooks. |
| `bot.py` | `Bot` (subclass of `telegram.Bot`): update handlers, message loading, chat registry, sending/editing/deleting, signup, shutdown. |
| `chat.py` | `Chat`: one per user. Holds the session stack, session data, groups/permissions, `last_interaction`. |
| `message.py` | `Message`: one per `.gsm` file. Holds components and the message-level whitelist/blacklist. |
| `components.py` | Components (TEXT, KEYBOARD, ...), keyboard parts, actions, `format_data`. |
| `notifications.py` | `NotificationCenter` and `Notification`. |
| `var.py` | Paths and constants (timeouts, special message codes, separators). |

The message format is documented in [messages.md](messages.md).

## Process and threads

`GhislieriBot.run()` creates the `Bot` inside the service process, then enters the normal `BaseService` loop.
The process has three threads that matter:

1. **Service loop (main thread)**: runs scheduled tasks and serves requests from other services
   (`add_notification`, `edit_groups`, `expire_notification`, `remove_chat`, `save_feedback`, `send_message`,
   `send_photo`, plus `stop` and `get_statistics` from `BaseService`).
2. **Updater polling thread**: fetches updates from Telegram (`updater.start_polling()`).
3. **Dispatcher thread**: runs every handler, one update at a time (no `run_async`).

Every user interaction, and the periodic sync, runs in the dispatcher thread, so those are serialized.
Service requests run in the main thread at the same time. See *Known issues* for the resulting races.

Startup (`Bot.__init__`, `bot.py:70`): wait until `api.telegram.org` answers, read the token file, register
handlers, load all messages from `messages/` (`var.MESSAGES_DIR`, relative to the working directory), load all
active chats from `student_databaser.get_chats`, load the notification backup, start polling, and queue a
first sync. Command-line flags: `-d` switches to the debug data directory, debug token, 10 s sync interval and
30 s session timeout; `--no_sync` disables syncing (and makes `student_databaser` use a different database file).

## Update handlers

Registered in `_load_handlers` (`bot.py:91`). The first matching handler wins.

| Handler | Matches | What it does |
|---|---|---|
| `_chat_sync_handler` | `ChatSyncUpdate` (internal) | Syncs every chat (see *Sessions*). |
| `_remove_chat_handler` | `RemoveChatUpdate` (internal) | Hard-removes a chat (queued by the `remove_chat` request). |
| `_start_command_handler` | `/start` | Resets the session and sends a **new** live message. |
| `_keyboard_handler` | callback query | `chat.reply('KEYBOARD', callback=data)`. |
| `_photo_handler` | photo | `chat.reply('PHOTO_ANS', photo=largest size)`. |
| `_file_handler` | document | `chat.reply('FILE_ANS', file=document)`. |
| `_answer_handler` | text (includes commands other than `/start`) | `chat.reply('ANSWER', answer=message.text_html)`. |
| `_delete_handler` | anything else | Nothing except deletion. |

Every user-sent message (command, text, photo, file, sticker, ...) is queued for deletion, and every handler
ends with `_dispatch_message`, which re-renders the current message. `chat.reply(component, ...)` only acts
when the current message has that component, so input the message does not expect is just deleted.

`_error_handler` (`bot.py:105`): on "Timed out" it blocks in `wait_for_internet()`; on connection-lost errors it
returns silently; otherwise it logs and writes an error file through `utl.log_error`.

## The single live message

Each user sees one bot message (the *live message*), whose id is `chat.last_message_id`. The id is persisted
in the `student_databaser` database (`set_chat_last_message_id`) every time a new live message is sent, so it
survives restarts.

`_dispatch_message(chat, edit=True)` (`bot.py:252`):

1. Render: `chat.get_message_content()` checks permissions (see below) and builds
   `{'text', 'parse_mode': HTML, 'reply_markup'}` plus an optional `photo` entry.
2. If the message has a PHOTO component, send the photo as a separate message, remember its id for deletion on
   the **next** dispatch, and force step 3 to send instead of edit.
3. If `edit` is true (and no photo): `edit_message_text` on the live message.
   - "Message to edit not found": send a new live message silently.
   - "Message is not modified": ignored.
   - Any other `BadRequest` is re-raised.
4. Otherwise send a new live message (`_send_message`): the old live message is added to `msg_to_delete`, the new
   id is saved in the database and in the chat. A send without `disable_notification` pushes a notification
   to the user. That is how notifications with `notify: true` reach users.
5. Delete everything in `msg_to_delete` (the user's own messages and old live messages).
   - "Message to delete not found": logged.
   - "Message can't be deleted for everyone" (older than 48 h): the bot tries to edit the text to
     "Puoi eliminare questo messaggio" ("you can delete this message"). This fails silently for messages the user sent.
6. `msg_to_delete` becomes the list from step 2 (the photo message, if any).

`telegram.error.Unauthorized` (the user blocked the bot) soft-removes the chat: the database row gets the
`inactive` group and the chat is dropped from memory.

Other services can send plain messages through the `send_message` / `send_photo` requests
(`bot.request_send_message`). Those messages are not tracked or deleted. `channels_manager` uses them to post to a channel.

## Callback data

Each keyboard button (except URL buttons) gets `callback_data`:

```
<time_str>:<message code>:<part flag>:<key id>
```

- `time_str`: last 6 digits of `int(time() * 10)`, generated once per render (`components.py:161`). It is
  **never checked**. It only makes each render's markup different, so edits rarely hit "not modified".
- `message code`: the `code` declared inside the `.gsm` file, not its path.
- `part flag`: `b` buttons, `o` options, `d` datetime, `n` navigation.
- `key id`: the button `id`, the option index on the current page, or a datetime key (`date`, `hour`, `-`, `+`,
  `null`, a day/hour/minute number).

`Keyboard.act` (`components.py:165`) splits on `:`, ignores the callback if the code differs from the current
message's code, then hands it to the part with that flag, which finds the key by id.

**64-byte limit.** Telegram rejects `callback_data` longer than 64 bytes, and the whole `send_message` /
`edit_message_text` call fails with `BadRequest`, so the user's screen does not update. The fixed overhead is 10
bytes, so **`len(code) + len(id)` must stay ≤ 54 bytes (UTF-8)**. The longest current value is 58 bytes
(`notifications.admin.google_credentials_login` + `home`). Deeper folders, longer file names or longer ids cut
into the remaining 6 bytes. Ids and codes must not contain `:`.

## Sessions

A chat's session is a stack (`chat.session`, a list of `Message` objects). The top is the current message.
`NEW` pushes, `BACK n` pops, `HOME` resets. Session data (`chat.data`) is a `dotdict` shared by every message of the session.
Sessions live only in memory and are lost on restart.

`reset_session(msg_code=None)` (`chat.py:80`):

- With `msg_code`: the session becomes `[msg_code]`, data is reset, `last_interaction = False`. Used for the
  authorization error and shutdown messages. Returns `notify=False`.
- Without: if the NotificationCenter has a pending notification for the user, the session becomes
  `[notification.msg_code]`, data is reset and merged with `notification.data`, and `last_interaction` becomes the
  `Notification`. Returns `notification.notify`.
- Otherwise, if `last_interaction is True` (already idle at home), nothing happens and it returns `None`.
- Otherwise the session becomes `[home]`, data is reset, `last_interaction = True`. Returns `False`.

Resetting data keeps only `user_id`, `infos`, `groups`, `permissions` (`chat.py:74`).

### `last_interaction` states

| Value | Meaning | Expired at sync? |
|---|---|---|
| `0` | Fresh chat after startup | Yes, at the first sync |
| `True` | Idle at home after a reset | Always (so each sync checks for new notifications) |
| `False` | Session set explicitly (auth error, shutdown) | Never |
| `int` timestamp | Time of the user's last handled input (`reply`) | After `SESSION_TIMEOUT_SECONDS` (600 s; 30 s with `-d`) |
| `Notification` | Showing a notification the user has not touched yet | When the notification expires |

### Sync

`GhislieriBot` schedules `bot.sync()` every `BOT_SYNC_SECONDS_INTERVAL` (60 s; 10 s with `-d`). `sync()` puts a
`ChatSyncUpdate` (its `update_id` is the current time) on the updater queue, so the sync runs in the dispatcher
thread between user updates. For each chat whose session is expired, `chat.sync()` calls `reset_session()`.
If it returns a bool, the bot dispatches with `edit = not notify`. So notifications with `notify: true` arrive
as a new, pushed message. Everything else edits the live message in place.

Consequences: a notification is shown only at a reset point (a sync while the session is expired, a `HOME`
action, or `/start`). A user who keeps interacting gets it after going home or after 10 minutes of inactivity.
The first sync after startup resets every chat.

## Notifications

`NotificationCenter` (`notifications.py`) keeps a list of `Notification` objects. Other services (and messages
through `REQ ghislieri_bot add_notification`) add them with:

```
add_notification(users=None, groups=None, n_type, msg_code, notify, data=None,
                 start_time=None, end_time=None, enabled_time={"hours": 12})
```

- `groups` are expanded to user ids with `student_databaser.get_chats(group=g)` and merged with `users`
  (`ghislieri_bot.py:25`). Extra keyword arguments are accepted and ignored.
- `start_time`: string `YYYY-MM-DD HH:MM:SS`, default now. The notification is not delivered before it.
- `end_time`: string, `False` (never expires by time) or `True` (expired). Default:
  `start_time + timedelta(**enabled_time)`.
- `n_type` is only stored and logged. Nothing reads it.

Lifecycle:

- **Delivery**: `get_notification(user_id)` returns the first active notification (users left and not expired) that
  contains the user, and removes the user from it (`check_user`). Each user sees each notification once.
- **Expiry**: time-based, or `expire()` (sets `end_time = True`). The `expire_notification(user_id)` request expires
  the notification the user is currently viewing, if `last_interaction` is a `Notification`. An expired
  notification is not delivered to remaining users, and a chat still viewing it resets at the next sync.
- **Shutdown**: users currently viewing a notification are put back into it (`chat.stop()`), so they see it again
  after the restart.
- **Backup**: on exit, active notifications are written as JSON to
  `<DATA_DIR>/notifications/notifications_bckp.gbnb`. At startup the file is loaded and deleted. Notification
  `data` must therefore be JSON-serializable. Nothing is saved if the process dies without a clean exit.

Notification targets used in the code base: `welcome.checking`, `welcome.thank_you`,
`notifications.admin.check_subscription` (signup), `notifications.update`, `notifications.new_channel_message`,
`notifications.supersega_season`, `notifications.custom` (admin menu),
`meals_management.reservation.reminder`, `notifications.admin.new_meal_report` (meals_management),
`notifications.admin.new_eduroam_report`, `notifications.admin.new_social_submission` (content_submitter).

## Permissions and groups

A user's groups come from the database (comma-separated column). `utl.extend_groups` adds every dotted prefix:
`{"calendar.sport"}` gives permissions `{"calendar.sport", "calendar"}`. Membership in a subgroup implies
membership in its ancestors, not the other way round.

A `whitelist` passes if it shares at least one entry with the permissions. A `blacklist` fails if it shares any
entry. Both are optional and both must pass.

- **Message level** (`Message.check_permission`): checked on every render (`Chat.check_auth`, `chat.py:27`). On
  failure the session is reset to `utility.auth`, `auth_error.code` is set, and the error is logged.
- **Key level** (`Key._check_permission`): only hides the button. Pressing it is **not** re-checked (see *Known issues*).

Group names that appear in the code and messages: `signup` (new, unverified user), `inactive` (soft-removed,
excluded from `get_chats`), `student`, `alumnus`, `master` (administrator), `admin`, `representative`,
`socials_rep` / `social_rep` (inconsistent, see messages.md), `calendar`, `calendar.cultural|sport|college|misc`,
`sci_tech`, `biomed`, `social_sci`, `human_sci`. The admin "edit group" list comes from
`student_databaser/groups.gsgr`.

Admins change groups with `REQ ghislieri_bot edit_groups`. This updates the database and then the in-memory chat
(`chat.set_groups`), so the change applies immediately.

## Signup flow

1. Any update from an unknown user id triggers `_new_student_signup` (`bot.py:219`). The bot sends "Starting..."
   (this becomes the live message), calls `student_databaser.new_chat` (inserts the row with group `signup`, or
   re-enables a soft-removed user by dropping `inactive`), creates the `Chat`, resets the session, and raises
   `NewUser`. The handler catches it, skips the user's input and dispatches.
2. `home` shows `signup` users only the "Iscriviti!" (sign up) button → `welcome.welcome` → `welcome.insert_surname` →
   `welcome.insert_name`. Each answer is saved with `edit_student_info`. After the name, the bot adds a
   notification for the user (`welcome.checking`, `end_time: false`) and goes `HOME`, which shows it at once.
3. `welcome.checking`'s TEXT action adds `notifications.admin.check_subscription` for group `master`
   (`end_time: false`, data `new_sub = {user_id, infos}`).
4. A master approves: `set_gender` (`edit_student_info gender`) → `set_group` (pick `student` or `alumnus`):
   `edit_groups add`, `edit_groups rm signup`, add notification `welcome.thank_you` for the user,
   `expire_notification` for the user, `HOME`. Rejecting calls `remove_chat`: the live message is deleted and the
   database row is hard-deleted.
5. At the next sync the user's expired `welcome.checking` is replaced by `welcome.thank_you` (pushed).

## Removal

- `remove_chat` request (admin or signup rejection): queued as `RemoveChatUpdate` so it runs in the dispatcher
  thread. It deletes the live message, calls `remove_user(hard_remove=True)` and drops the chat.
- `Unauthorized` while sending: `remove_user(hard_remove=False)` (adds `inactive`). The live message is not deleted.

## Shutdown

`ghislieri_services` sends `stop` to every service. In the bot process (main thread):

1. `GhislieriBot._stop` → `bot.stop()` (`bot.py:334`): for each chat, put back a notification it is viewing, reset
   the session to `utility.bot_shutdown` (no keyboard, `last_interaction = False`) and edit the live message.
2. The service keeps answering requests until the global stop event is set.
3. `_exit` → `bot.exit()`: save the notification backup, then `updater.stop()`.

After a restart, every chat starts with `last_interaction = 0`, so the first sync edits the shutdown message
back to `home` (or a pending notification).

## Known issues / smells

Line numbers refer to the files at the time of writing.

**Blocking calls in the dispatcher thread** (all users wait):
- Every `REQ` is a synchronous pipe round-trip (`components.py:57-60`). Slow services block everyone: printing
  (`lp`), `update_rssfeed`, `download_menu` (IMAP + LibreOffice + PDF render), emails sent by the report flows.
- `FILE_ANS` / `PHOTO_ANS` downloads run inline (`components.py:135`, `components.py:150`).
- `_error_handler` calls `wait_for_internet()` on timeouts (`bot.py:109`). It loops forever, and `requests.get`
  has no timeout (`bot.py:46`).
- Sync and shutdown make one API call per chat, back to back (`bot.py:124-127`, `bot.py:335-338`), with no
  rate limiting.

**Error handling**
- Telegram errors are recognized by exact message strings (`bot.py:16-23`, `bot.py:107-112`, `bot.py:277-280`,
  `bot.py:302-305`). Any wording change in the API breaks this.
- An exception for one chat during sync aborts the sync for all remaining chats (`bot.py:124-127`). Causes include a
  `BadRequest` re-raised at `bot.py:308`, an HTML parse error, or a failing TEXT `REQ`.
- Exceptions from services are re-raised in the bot (`modules/service_pipe.py:19-20`) and abort the handler. The user
  sees no feedback. `utility.error` / `ERROR_MESSAGE_CODE` (`var.py:33`) exist but are never used.
- Callback queries are never answered (`bot.py:141-147`), so Telegram clients show a loading indicator after each press.
- In PTB 13, `MessageHandler` also matches edited messages. For an edited message `update.message` is `None`, so
  `bot.py:152` (and the other handlers that read `update.message`) raise `AttributeError`.
- A notification is consumed (`check_user`, `notifications.py:57-61`) before it is rendered. If the render fails,
  the notification is lost for that user.

**Security / correctness**
- Key `whitelist`/`blacklist` only hide buttons. `Buttons.act` (`components.py:220-224`) runs a key's actions
  without checking permissions, and Telegram warns that modified clients can send arbitrary `callback_data`.
  Targets that rely on hidden buttons have no message whitelist. Examples: `calendar_manager.new_event.*`,
  `calendar_manager.edit_event.*`, `calendar_manager.delete_event.main`, and `admin.*` sub-messages (the last
  are protected only because their parent `admin.menu` is whitelisted, and the msg_code check blocks jumping).
- Format-string injection: `format_data` calls `str.format(**data)` on the *value* behind a `$` reference
  (`components.py:19`). User text or service strings that contain `{`/`}` raise errors, or get substituted when sent
  through `$` (for example event names in `calendar_manager.*.recap`, feedback, reports). `str.format` also allows
  attribute traversal (`{infos.__class__...}`).
- Unescaped HTML: strings from services are inserted into `parse_mode=HTML` text without escaping. Examples: log
  lines (`_request_get_log`, `modules/ghislieri_services.py:65-69`; errors are escaped), RSS event fields, and
  notification data. A stray `<` or `&` makes the edit fail. User answers come from `text_html` (`bot.py:152`),
  which PTB escapes. They are stored as HTML.
- TEXT/PHOTO actions run on every render (`components.py:101-103`), so side-effecting `REQ`s repeat. For example
  `welcome.checking` adds another admin notification each time it is re-rendered, such as on every message the
  user sends while waiting.
- `check_subscription` goes to every master with `end_time: false` and is never expired, so every master gets it
  even after one has handled it.
- Datetime picker default: local time labelled as UTC (`components.py:290`).
- `minute_inc` is parsed but unused (`components.py:273`). `EDIT_MSG_NOT_TEXT` (`bot.py:19`) and `Bot.expire_notification`
  (`bot.py:228`) are unused.
- The token is read with `readline()` without stripping (`bot.py:39`).
- `_load_messages` loads every file, not only `.gsm`, and keys it by the text before the first dot (`bot.py:196`).
  A message's declared `code` is not checked against its path (four files disagree, see messages.md).

**Threads and races**
- `add_notification`, `expire_notification` and `edit_groups` (`ghislieri_bot.py:25-37`) run in the service thread and
  mutate `NotificationCenter`, `Chat.groups/permissions/data` and `Notification` state while the dispatcher reads them.
- `get_chat_from_id` (`bot.py:217`) and `get_chats_stats` (`bot.py:231-241`) iterate `self.chats` from the service
  thread while the dispatcher may add or remove chats (`bot.py:224`, `bot.py:247`). That can raise "Set changed size
  during iteration".
- `bot.stop()` runs in the service thread while polling and dispatching continue until `bot.exit()`
  (`bot.py:334-343`). A user update during shutdown can overwrite the shutdown message.

**Scaling / hygiene**
- O(n) chat lookup for every update (`bot.py:217`). A dict keyed by `user_id` would do.
- The notification list is never pruned (`notifications.py:16-25`). Each lookup scans every notification ever added
  since the last restart.
- The notification backup is written only on a clean exit (`notifications.py:43-44`).
- Personal data in logs: `Chat.__str__` (`chat.py:141-142`) includes name and surname. It is used in log lines and
  error files (`bot.py:256`, `bot.py:269`, `bot.py:278`, `bot.py:287`).
