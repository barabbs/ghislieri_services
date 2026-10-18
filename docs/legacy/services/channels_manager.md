# channels_manager

Source: `services/channels_manager/` (`channels_manager.py`, `facebook_scraping.py`, `var.py`).

## Purpose

Mirrors a private Facebook group onto a Telegram channel. Every 15 minutes the service scrapes the group's latest posts from `mbasic.facebook.com`, logged in with a stored session cookie. Each post it has not seen before is published to the channel through the bot: the text first, then the first image as a reply when there is one. Posts already handled are recorded in a history file.

## Requests API

The service defines no `_request_*` methods of its own. Only the inherited `stop` and `get_statistics` exist. Nothing in `messages/` or `services/` calls it, and it is **not** listed in the admin services menu (`messages/admin/services/menu.gsm`), so it cannot be restarted or inspected from the bot.

## Scheduled tasks

| Task | Schedule | What it does |
|---|---|---|
| `_task_check_facebook_posts` (`@task`) | `every(15).minutes.at(":12")`, i.e. every 15 minutes at second 12 | Scrapes up to `MAX_PAGES_SCRAPED` = 3 group pages. For every post id not in `post_history` it fetches the post and calls `_send_post`. Exceptions are caught and logged to `data/errors`. |
| `_task_update_statistics` | hourly (inherited) | Statistics bookkeeping. |

## `_update` loop

Not overridden. The scrape runs inside the task and blocks the service loop until it finishes.

## Scraping flow (`facebook_scraping.py`)

1. `GET https://mbasic.facebook.com/groups/<group_id>?<paging>` with header `cookie: <stored cookies>`.
2. Post ids come from `<a>Full Story</a>` links (`href.split("/")[6]`). The next page comes from `<a>See more posts</a>`.
3. For each post, `GET .../permalink/<post_id>`. The author comes from the first `<h3><a>`. The text comes from the `<p>` elements under `#m_story_permalink_view`, or a fixed `div` path when there are none.
4. Inline CSS classes are mapped to bold, italic or underline by parsing the page's `<style>` with `tinycss2`. `<br>` becomes a newline, `<blockquote>` and links are kept, and Facebook's `l.php` outbound redirect links are dropped. The text is HTML-escaped.
5. If the post links to a `/photo.php?` page, that page is fetched and the `<img>` at a fixed `div` depth is downloaded as bytes.

The post dict is `{"post_id": int, "author": str (upper-case), "time": str, "text": str, ["img": bytes]}`. `time` is scraped but never used.

## Inter-service calls

| Target | Request | Returns |
|---|---|---|
| `ghislieri_bot` | `send_message(chat_id=<channel id>, disable_web_page_preview=True, text=FACEBOOK_POST_MSG.format(**post))` (HTML parse mode) | message id |
| `ghislieri_bot` | `send_photo(chat_id=<channel id>, photo=<bytes>, reply_to_message_id=<text msg id>)` | message id |

No notifications are sent.

## Data and files

Data dir: `/var/opt/ghislieri_services/channels_manager`, or `./data/channels_manager` with `-d`. All three files are **secrets or configuration**: do not commit them.

| File | Format |
|---|---|
| `facebook_coords.fbck` | JSON: `{"group_id": 1234567890, "cookies": "c_user=...; xs=...; ..."}`. The cookie string is sent verbatim as the `cookie` header. It is a logged-in Facebook session and must be refreshed by hand when it expires. |
| `channel_id.cmid` | A single integer: the Telegram chat id of the target channel (e.g. `-1001234567890`). |
| `facebook_posts.fbpst` | Append-only CSV with no header, one line per published post: `<post_id>,<text_msg_id>[,<photo_msg_id>]`. Only the first column is read back (to build the history set). |

## External dependencies

- Python: `requests`, `beautifulsoup4` (`html.parser`), `tinycss2`.
- External service: scraping of `mbasic.facebook.com`, Facebook's no-JavaScript mobile site. Access uses a real user's session cookies; there is no official API. Facebook has been retiring `mbasic`, so check that it still responds before relying on this service.

## Known issues / smells

- **The config is read at import time.** `CHANNEL_ID` (`channels_manager.py:22`) and `COORDS` (`facebook_scraping.py:16`) are module-level reads. If a file is missing, importing the service fails and with it the whole application (`modules/ghislieri_services.py:29`). Changes take effect only on re-import (restart or `restart_service`).
- **Very fragile scraping.** The code relies on English link texts (`"Full Story"`, `"See more posts"`, `facebook_scraping.py:114, 117`), a fixed URL segment index (`:114`), and long fixed DOM paths (`root.div.div.contents[1]...`, `:83, 93, 97, 101`). It assumes a `<style>` in `<head>` (`:47`) and an `href` on every `<a>` (`:70`). Any markup change raises, and the error repeats every 15 minutes.
- **A single bad post blocks the rest.** The generator stops at the first exception, so later posts are never checked (`facebook_scraping.py:110-117`). On the last page it still looks for "See more posts"; if the link is missing, `None["href"]` raises a `TypeError` (`:117`).
- **No HTTP timeouts** (`facebook_scraping.py:27, 80, 84`). A hung request freezes the service. The process stays alive, so `_task_check_services` never restarts it.
- **Duplicate posts.** The history is written only after both sends succeed (`channels_manager.py:45-47`). If `send_message` works but `send_photo` fails, the text is posted again on the next run.
- **No rate limiting.** A backlog is posted in a burst. The error log already shows `telegram.error.RetryAfter` flood-control errors from this task, and every retry repeats the duplicate problem above.
- **Unescaped author.** `author` is not HTML-escaped (`facebook_scraping.py:92`), and link `href`s are inserted into the attribute without escaping (`:72-73`). Both are rendered in Telegram HTML mode. The logs contain `Can't parse entities` errors, from before text escaping was added.
- No length check against Telegram's 4096-character limit. `{author:<100}` also pads every header to 100 characters (`var.py:19`). A post that is too long fails on every run, forever.
- The group id is hardcoded in the "see on Facebook" link (`var.py:23`), duplicating `group_id` in `facebook_coords.fbck`.
- Posts are published in the order the scraped pages list them. There is no sorting by time.
- `post_history` grows without bound in memory and on disk. That is harmless at the current volume.
