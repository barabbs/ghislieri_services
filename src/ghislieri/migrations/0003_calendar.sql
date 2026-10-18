-- College calendar events. Owned by ghislieri.events.
-- starts_at/ends_at are UTC ISO 8601 ("2026-12-03T20:00:00+00:00"), so text order is time order;
-- the bot shows them in Europe/Rome time.

CREATE TABLE events (
    id          INTEGER PRIMARY KEY,
    uid         TEXT NOT NULL UNIQUE,              -- iCalendar UID: "cultural/<site slug>", "<class>/<time>"
    title       TEXT NOT NULL CHECK (trim(title) <> ''),
    description TEXT NOT NULL DEFAULT '',
    url         TEXT,
    starts_at   TEXT NOT NULL,
    ends_at     TEXT NOT NULL CHECK (ends_at > starts_at),
    class       TEXT NOT NULL CHECK (class IN ('cultural', 'sport', 'college', 'misc')),
    categories  TEXT NOT NULL DEFAULT '',          -- comma-separated keys of events.CATEGORIES
    status      TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled')),
    creator_id  INTEGER REFERENCES users (id) ON DELETE SET NULL,
    -- rss: from the college website, refreshed by the sync. bot: created or edited in the bot,
    -- never touched by the sync.
    source      TEXT NOT NULL CHECK (source IN ('rss', 'bot')),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX events_starts_at ON events (starts_at);
