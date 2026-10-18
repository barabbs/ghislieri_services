"""SQLite access. Schema changes are numbered SQL files in migrations/, applied in order."""

import logging
import sqlite3
from importlib import resources
from pathlib import Path

log = logging.getLogger(__name__)


def connect(path: Path | str) -> sqlite3.Connection:
    """Open the database and bring the schema up to date.

    The connection is used only from the event-loop thread. Queries touch a few hundred rows,
    so running them synchronously costs less than handing them to a thread.
    """
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, autocommit=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    files = sorted(
        (f for f in resources.files("ghislieri.migrations").iterdir() if f.name.endswith(".sql")),
        key=lambda f: f.name,
    )
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, file in enumerate(files, start=1):
        if version <= current:
            continue
        log.info("Applying migration %s", file.name)
        try:
            conn.executescript(f"BEGIN;\n{file.read_text()}\n;PRAGMA user_version = {version};\nCOMMIT;")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise


class transaction:
    """`with transaction(conn): ...` groups several statements atomically."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def __enter__(self) -> sqlite3.Connection:
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, exc, tb) -> None:
        self.conn.execute("ROLLBACK" if exc_type else "COMMIT")
