"""Users, groups and permissions."""

import sqlite3
from dataclasses import dataclass, field

from . import clock
from .db import transaction

# Groups an admin can assign from the bot. Users may hold others (e.g. from the v0.5 import).
KNOWN_GROUPS = (
    "student",
    "alumnus",
    "master",
    "tester",
    "representative",
    "socials_rep",
    "calendar.admin",
    "calendar.sport",
    "calendar.cultural",
    "calendar.cultural.gs",
    "sci_tech",
    "biomed",
    "social_sci",
    "human_sci",
)
ADMIN = "master"
DEVELOPER = "tester"
STUDENT, ALUMNUS = "student", "alumnus"
# Students become alumni after this many academic years.
YEARS_AS_STUDENT = 6

PROFILE_FIELDS = ("name", "surname", "email", "gender", "enrollment_year")
GENDERS = {"M": "Maschile", "F": "Femminile"}


def year_label(year: int | None) -> str:
    """Academic year of enrollment, "2025/26"."""
    return f"{year}/{(year + 1) % 100:02}" if year else "non indicato"


def group_matches(held: str, required: str) -> bool:
    """True if holding `held` grants `required` ("calendar.sport" grants "calendar")."""
    return held == required or held.startswith(required + ".")


@dataclass(frozen=True)
class User:
    id: int
    name: str
    surname: str
    gender: str | None
    email: str | None
    enrollment_year: int | None
    status: str
    groups: frozenset[str] = field(default_factory=frozenset)

    @property
    def full_name(self) -> str:
        return f"{self.name} {self.surname}"

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def has(self, group: str) -> bool:
        return any(group_matches(g, group) for g in self.groups)

    @property
    def is_admin(self) -> bool:
        return self.has(ADMIN)


def _groups(conn: sqlite3.Connection, user_id: int) -> frozenset[str]:
    rows = conn.execute("SELECT name FROM user_groups WHERE user_id = ?", (user_id,))
    return frozenset(r["name"] for r in rows)


def _from_row(conn: sqlite3.Connection, row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        name=row["name"],
        surname=row["surname"],
        gender=row["gender"],
        email=row["email"],
        enrollment_year=row["enrollment_year"],
        status=row["status"],
        groups=_groups(conn, row["id"]),
    )


def get(conn: sqlite3.Connection, user_id: int) -> User | None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _from_row(conn, row) if row else None


def create_pending(conn: sqlite3.Connection, user_id: int, name: str, surname: str, gender: str | None) -> User:
    """Register a new user, waiting for admin approval. The enrollment year defaults to the current one."""
    year = clock.academic_year(clock.today())
    conn.execute(
        "INSERT INTO users (id, name, surname, gender, enrollment_year, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, 'pending', ?)",
        (user_id, name.strip(), surname.strip(), gender, year, clock.iso(clock.now())),
    )
    return get(conn, user_id)  # type: ignore[return-value]


def update_profile(conn: sqlite3.Connection, user_id: int, **values) -> None:
    bad = set(values) - set(PROFILE_FIELDS)
    if bad:
        raise ValueError(f"Not profile fields: {bad}")
    for column, value in values.items():  # column names come from PROFILE_FIELDS only
        conn.execute(f"UPDATE users SET {column} = ? WHERE id = ?", (value, user_id))


def set_status(conn: sqlite3.Connection, user_id: int, status: str) -> None:
    conn.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))


def mark_blocked(conn: sqlite3.Connection, user_id: int) -> None:
    """The user blocked the bot. They become active again on their next /start."""
    conn.execute("UPDATE users SET status = 'blocked' WHERE id = ? AND status = 'active'", (user_id,))


def add_group(conn: sqlite3.Connection, user_id: int, group: str) -> None:
    conn.execute("INSERT OR IGNORE INTO user_groups (user_id, name) VALUES (?, ?)", (user_id, group))


def remove_group(conn: sqlite3.Connection, user_id: int, group: str) -> None:
    conn.execute("DELETE FROM user_groups WHERE user_id = ? AND name = ?", (user_id, group))


def approve(conn: sqlite3.Connection, user_id: int, groups: tuple[str, ...] = (STUDENT,)) -> None:
    with transaction(conn):
        set_status(conn, user_id, "active")
        for g in groups:
            add_group(conn, user_id, g)


def delete(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def list_users(conn: sqlite3.Connection, group: str | None = None, status: str | None = "active") -> list[User]:
    """Users sorted by surname, optionally only those holding `group` (dotted match)."""
    sql, args = "SELECT * FROM users", []
    if status is not None:
        sql += " WHERE status = ?"
        args.append(status)
    rows = conn.execute(sql + " ORDER BY surname COLLATE NOCASE, name COLLATE NOCASE", args).fetchall()
    users = [_from_row(conn, r) for r in rows]
    return [u for u in users if group is None or u.has(group)]


def user_ids(conn: sqlite3.Connection, groups: tuple[str, ...]) -> list[int]:
    """Ids of active users holding any of `groups`, without duplicates."""
    return [u.id for u in list_users(conn) if any(u.has(g) for g in groups)]


def emails(conn: sqlite3.Connection, groups: tuple[str, ...]) -> list[str]:
    """Email addresses of active users holding any of `groups`."""
    return [u.email for u in list_users(conn) if u.email and any(u.has(g) for g in groups)]


def promote_alumni(conn: sqlite3.Connection, today=None) -> list[User]:
    """Move students who started YEARS_AS_STUDENT or more academic years ago to alumni."""
    year = clock.academic_year(today or clock.today())
    moved = [
        u
        for u in list_users(conn, STUDENT, status=None)
        if u.enrollment_year is not None and year - u.enrollment_year >= YEARS_AS_STUDENT
    ]
    with transaction(conn):
        for u in moved:
            remove_group(conn, u.id, STUDENT)
            add_group(conn, u.id, ALUMNUS)
    return moved
