-- Users, groups, notifications, submissions.
-- Timestamps are ISO 8601 strings with UTC offset; dates are YYYY-MM-DD.

CREATE TABLE users (
    id              INTEGER PRIMARY KEY,               -- Telegram user id
    name            TEXT NOT NULL CHECK (trim(name) <> ''),
    surname         TEXT NOT NULL CHECK (trim(surname) <> ''),
    gender          TEXT CHECK (gender IN ('M', 'F')),
    email           TEXT,
    enrollment_year INTEGER,                           -- start of first academic year (2019 = 2019/20)
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'active', 'blocked', 'disabled')),
    created_at      TEXT NOT NULL
);

-- Dotted names: membership of "calendar.cultural.gs" implies "calendar.cultural" and "calendar".
CREATE TABLE user_groups (
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name    TEXT NOT NULL CHECK (name <> ''),
    PRIMARY KEY (user_id, name)
) WITHOUT ROWID;

CREATE TABLE notifications (
    id         INTEGER PRIMARY KEY,
    kind       TEXT NOT NULL,          -- e.g. "custom", "meal_reminder", "registration"
    ref        TEXT,                   -- what it is about, e.g. a date or a user id
    text       TEXT NOT NULL,          -- Telegram HTML
    buttons    TEXT,                   -- JSON list of {"text", "state"} or {"text", "url"}
    silent     INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT                    -- messages are deleted after this time
);
CREATE INDEX notifications_kind_ref ON notifications (kind, ref);

CREATE TABLE deliveries (
    notification_id INTEGER NOT NULL REFERENCES notifications (id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL,
    state           TEXT NOT NULL DEFAULT 'pending'
                    CHECK (state IN ('pending', 'sent', 'failed', 'retracted')),
    message_id      INTEGER,
    PRIMARY KEY (notification_id, user_id)
) WITHOUT ROWID;
CREATE INDEX deliveries_pending ON deliveries (state) WHERE state = 'pending';
CREATE INDEX deliveries_user ON deliveries (user_id, state);

-- Things users send to the college: feedback, eduroam reports, social posts, canteen reports.
CREATE TABLE submissions (
    id         INTEGER PRIMARY KEY,
    kind       TEXT NOT NULL,
    user_id    INTEGER REFERENCES users (id) ON DELETE SET NULL,
    payload    TEXT NOT NULL,          -- JSON; photos are stored as Telegram file_ids
    created_at TEXT NOT NULL
);
