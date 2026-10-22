-- Each chat's live menu message, so it can be deleted when a newer one replaces it (also after a restart).
CREATE TABLE menus (
    chat_id    INTEGER PRIMARY KEY,
    message_id INTEGER NOT NULL,
    shown_at   TEXT NOT NULL          -- UTC
);
