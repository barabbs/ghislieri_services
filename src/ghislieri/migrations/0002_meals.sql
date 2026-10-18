-- Meals: bookable days and bookings. Owned by ghislieri.meals.

-- Booking for `day` is open from 07:00 of `opens_on` until 07:00 of `day`.
CREATE TABLE meal_days (
    day      TEXT PRIMARY KEY,
    opens_on TEXT NOT NULL CHECK (opens_on < day)
) WITHOUT ROWID;

-- A missing row means the user has not answered for that meal yet.
CREATE TABLE meal_bookings (
    day       TEXT NOT NULL REFERENCES meal_days (day) ON DELETE CASCADE,
    meal      TEXT NOT NULL CHECK (meal IN ('lunch', 'dinner')),
    user_id   INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    attending INTEGER NOT NULL CHECK (attending IN (0, 1)),
    PRIMARY KEY (day, meal, user_id)
) WITHOUT ROWID;
CREATE INDEX meal_bookings_user ON meal_bookings (user_id, day);
