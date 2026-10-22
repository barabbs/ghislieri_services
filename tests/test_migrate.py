import datetime as dt
import importlib.util
import sqlite3
from pathlib import Path

from ghislieri import meals, users

spec = importlib.util.spec_from_file_location("migrate_v05", Path(__file__).parent.parent / "tools" / "migrate_v05.py")
migrate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrate)


def test_import_users_and_meals(conn, tmp_path):
    old = sqlite3.connect(tmp_path / "database.gsdb")
    old.execute(
        "CREATE TABLE students (user_id INTEGER PRIMARY KEY, last_message_id INTEGER NOT NULL,"
        " name TEXT, surname TEXT, gender TEXT, email TEXT, groups TEXT)"
    )
    old.executemany(
        "INSERT INTO students VALUES (?, 1, ?, ?, ?, NULL, ?)",
        [
            (1, "Anna", "Verdi", "F", "student,calendar.sport,year.2021"),
            (2, None, None, None, "signup"),  # broken signup: skipped
            (3, "Carlo", "Neri", "X", "student,inactive"),
            (4, "Dora", "Blu", "F", "student,admin"),  # v0.5 calendar admin
        ],
    )
    old.commit()
    report = migrate.import_users(conn, tmp_path / "database.gsdb")
    a, c = users.get(conn, 1), users.get(conn, 3)
    assert (a.status, a.enrollment_year, a.groups) == ("active", 2021, {"student", "calendar.sport"})
    assert (c.status, c.gender, c.groups) == ("blocked", None, {"student"})
    assert users.get(conn, 2) is None and any("skipped 2" in line for line in report)
    assert users.get(conn, 4).groups == {"student", "calendar.admin"}

    res = tmp_path / "reservations"
    res.mkdir()
    (res / "Reservations_2030-01-05.mr").write_text("2030-01-05\n2029-12-31\nPranzo\n1,99\n3\nCena\n\n\n")
    migrate.import_meals(conn, res)
    day = dt.date(2030, 1, 5)
    rows = conn.execute("SELECT meal, user_id, attending FROM meal_bookings ORDER BY user_id").fetchall()
    assert [tuple(r) for r in rows] == [("lunch", 1, 1), ("lunch", 3, 0)]  # unknown user 99 dropped
    assert meals.opening_date(day) == dt.date(2029, 12, 31)
