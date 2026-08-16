"""Fixtures for the LLM tests: a temp database, a primed price cache, mock mode on.

`LLM_MOCK=true` is autouse here so no test in this package can reach the network
even if it forgets to opt in.
"""

import pytest

from app.db import init_db
from app.db.connection import DB_PATH_ENV
from app.llm.mock import MOCK_ENV_VAR
from app.market import PriceCache


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setenv(MOCK_ENV_VAR, "true")


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv(DB_PATH_ENV, str(tmp_path / "finally.db"))
    init_db()
    return tmp_path


@pytest.fixture
def price_cache():
    cache = PriceCache()
    cache.update("AAPL", 100.0)
    cache.update("GOOGL", 200.0)
    cache.update("TSLA", 50.0)
    return cache
