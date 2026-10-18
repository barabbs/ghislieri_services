"""One-off import of v0.5 data into the v1 database.

    uv run tools/migrate_v05.py OLD_DATA_DIR NEW_DB [--dry-run]

OLD_DATA_DIR is the v0.5 data directory (production: /var/opt/ghislieri_services). NEW_DB is the
v1 database file; it is created if missing. Running it twice is safe: existing rows are kept.
"""

import argparse
import datetime as dt
import re
import sqlite3
import sys
from pathlib import Path

from ghislieri import clock, db, events, meals, users

# v0.5 groups that are states, not memberships.
LEGACY_STATE_GROUPS = {"signup", "inactive"}
YEAR_GROUP = re.compile(r"^\D*((?:19|20)\d\d)$")  # "2019", "year.2019", "anno_2019", ...


def import_users(conn: sqlite3.Connection, old_db: Path) -> list[str]:
    report = []
    old = sqlite3.connect(f"file:{old_db}?mode=ro", uri=True)
    old.row_factory = sqlite3.Row
    for row in old.execute("SELECT * FROM students"):
        uid = row["user_id"]
        groups = {g for g in (row["groups"] or "").split(",") if g}
        if not (row["name"] or "").strip() or not (row["surname"] or "").strip():
            report.append(f"skipped {uid}: incomplete signup (no name/surname)")
            continue
        if "signup" in groups:
            status = "pending"
        elif "inactive" in groups:
            status = "blocked"
        else:
            status = "active"
        year = None
        for g in sorted(groups):
            if m := YEAR_GROUP.match(g):
                year = int(m.group(1))
                groups.discard(g)
        gender = row["gender"] if row["gender"] in ("M", "F") else None
        if users.get(conn, uid):
            report.append(f"kept {uid}: already imported")
            continue
        with db.transaction(conn):
            conn.execute(
                "INSERT INTO users (id, name, surname, gender, email, enrollment_year, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    uid,
                    row["name"].strip(),
                    row["surname"].strip(),
                    gender,
                    row["email"],
                    year,
                    status,
                    clock.iso(clock.now()),
                ),
            )
            for g in groups - LEGACY_STATE_GROUPS:
                users.add_group(conn, uid, g)
        if year is None and users.STUDENT in groups:
            report.append(f"note {uid}: student without a year group; set the enrollment year in the bot")
    return report


def import_meals(conn: sqlite3.Connection, reservations_dir: Path) -> list[str]:
    """v0.5 `.mr` files: date, opening date, then per meal: name, booked ids, un-booked ids."""
    report, meal_names = [], {"Pranzo": "lunch", "Cena": "dinner"}
    known_users = {r["id"] for r in conn.execute("SELECT id FROM users")}
    for path in sorted(reservations_dir.glob("Reservations_*.mr")):
        lines = path.read_text(encoding="utf-8").split("\n")
        day, opens_on = dt.date.fromisoformat(lines[0].strip()), dt.date.fromisoformat(lines[1].strip())
        meals.add_day(conn, day, opens_on)
        for i in range(2, len(lines) - 2, 3):
            meal = meal_names.get(lines[i].strip())
            if meal is None:
                continue
            for attending, ids in ((True, lines[i + 1]), (False, lines[i + 2])):
                for token in filter(None, ids.strip().split(",")):
                    uid = int(token)
                    if uid in known_users:
                        meals.set_booking(conn, day, meal, uid, attending)
        report.append(f"meal day {day} imported")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("old_data_dir", type=Path)
    parser.add_argument("new_db", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="import into memory and only print the report")
    args = parser.parse_args()
    old = args.old_data_dir
    conn = db.connect(":memory:" if args.dry_run else args.new_db)
    report = import_users(conn, old / "student_databaser" / "database.gsdb")
    report += import_meals(conn, old / "meals_management" / "reservations")
    for ical in sorted((old / "calendar_manager" / "calendars").glob("calendar_????-????.ical")):
        events.import_ical(conn, ical)
        report.append(f"calendar {ical.name} imported")
    if not args.dry_run:
        events.write_ics(conn, args.new_db.parent)
    print("\n".join(report))
    counts = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("users", "user_groups")}
    print(f"totals: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
