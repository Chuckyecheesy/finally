"""Fixtures for repository tests: an initialized, seeded temp database."""

import pytest

from app.db import init_db
from app.db.connection import DB_PATH_ENV


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the repository at a fresh SQLite file and initialize it.

    Yields the path so a test can assert on the file itself if it needs to.
    """
    path = tmp_path / "finally.db"
    monkeypatch.setenv(DB_PATH_ENV, str(path))
    init_db()
    return path
