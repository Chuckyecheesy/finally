"""Profile repository tests."""

import pytest

from app.db import (
    DEFAULT_CASH_BALANCE,
    DEFAULT_USER_ID,
    ProfileNotFoundError,
    get_cash_balance,
    get_profile,
    update_cash_balance,
)

pytestmark = pytest.mark.usefixtures("temp_db")


def test_seeded_profile_starts_with_default_cash():
    profile = get_profile()

    assert profile.id == DEFAULT_USER_ID
    assert profile.cash_balance == DEFAULT_CASH_BALANCE
    assert profile.created_at


def test_update_cash_balance_persists():
    updated = update_cash_balance(DEFAULT_USER_ID, 4200.5)

    assert updated.cash_balance == 4200.5
    assert get_cash_balance() == 4200.5


def test_unknown_user_raises():
    with pytest.raises(ProfileNotFoundError):
        get_profile("nobody")

    with pytest.raises(ProfileNotFoundError):
        update_cash_balance("nobody", 1.0)
