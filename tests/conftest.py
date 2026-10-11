"""Shared test fixtures.

Every test runs against a fresh temporary database. That costs a couple of hundred
milliseconds per test and buys the property that matters most in a health prototype:
no test can pass because of state another test left behind.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import repository as repo  # noqa: E402
from app.content_loader import load_knowledge  # noqa: E402
from app.db import connect, init_db, reset_db  # noqa: E402


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    init_db(path)
    return path


@pytest.fixture()
def conn(db_path: Path):
    connection = connect(db_path)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture()
def knowledge(conn):
    """A database with the real knowledge base loaded.

    Tests use the real content files rather than fixtures, so a broken source
    reference is caught by the test suite and not only by a human reading JSON.
    """
    report = load_knowledge(conn)
    assert not report.rejected_sources, report.rejected_sources
    assert not report.rejected_facts, report.rejected_facts
    return report


@pytest.fixture()
def user(conn) -> str:
    return repo.create_profile(
        conn, display_name="Test Person", age_band="65-74",
        reminder_time="08:00", is_simulated=True,
    )


@pytest.fixture()
def demo_user(conn):
    """The full fictional patient, for tests that need a realistic record."""
    from app.demo.seed import seed_demo

    return seed_demo(conn)
