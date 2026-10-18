import datetime as dt

import pytest

from conftest import make_user
from ghislieri import clock, users
from ghislieri.settings import ProductionGuardError, Settings, check_production_guard


def test_academic_year():
    assert clock.academic_year(dt.date(2025, 8, 14)) == 2024
    assert clock.academic_year(dt.date(2025, 8, 15)) == 2025
    assert clock.academic_year(dt.date(2026, 3, 1)) == 2025


def test_group_hierarchy(conn):
    u = make_user(conn, 1, "calendar.cultural.gs")
    assert u.has("calendar") and u.has("calendar.cultural") and u.has("calendar.cultural.gs")
    assert not u.has("calendar.sport") and not u.has("calendar.cult")


def test_names_cannot_be_empty(conn):
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        users.create_pending(conn, 1, "  ", "Rossi", "M")


def test_promote_alumni(conn):
    # A freshman of September 2019 becomes an alumnus on 2025-08-15, not before.
    make_user(conn, 1, users.STUDENT)
    users.update_profile(conn, 1, enrollment_year=2019)
    make_user(conn, 2, users.STUDENT)
    users.update_profile(conn, 2, enrollment_year=2020)
    assert users.promote_alumni(conn, dt.date(2025, 8, 14)) == []
    moved = users.promote_alumni(conn, dt.date(2025, 8, 15))
    assert [u.id for u in moved] == [1]
    assert users.get(conn, 1).groups == {users.ALUMNUS}
    assert users.get(conn, 2).groups == {users.STUDENT}


def test_production_guard(tmp_path):
    marker = tmp_path / "production"
    prod_token = "2137673445:x"
    dev = Settings(bot_token=prod_token, _env_file=None)  # type: ignore[call-arg]
    with pytest.raises(ProductionGuardError):
        check_production_guard(dev, marker)
    prod = Settings(bot_token=prod_token, env="prod", _env_file=None)  # type: ignore[call-arg]
    with pytest.raises(ProductionGuardError):  # no marker on this machine
        check_production_guard(prod, marker)
    marker.touch()
    check_production_guard(prod, marker)
    test_in_prod = Settings(bot_token="2142935745:x", env="prod", _env_file=None)  # type: ignore[call-arg]
    with pytest.raises(ProductionGuardError):
        check_production_guard(test_in_prod, marker)
    check_production_guard(Settings(bot_token="2142935745:x", _env_file=None), marker)  # type: ignore[call-arg]
