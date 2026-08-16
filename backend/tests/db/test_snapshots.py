"""Portfolio snapshot tests."""

import pytest

from app.db import list_snapshots, record_snapshot

pytestmark = pytest.mark.usefixtures("temp_db")


def test_empty_by_default():
    assert list_snapshots() == []


def test_record_returns_snapshot_and_persists():
    snapshot = record_snapshot(10000.0)

    assert snapshot.total_value == 10000.0
    assert snapshot.id
    assert list_snapshots() == [snapshot]


def test_listed_oldest_first():
    record_snapshot(3.0, recorded_at="2026-08-15T12:00:02+00:00")
    record_snapshot(1.0, recorded_at="2026-08-15T12:00:00+00:00")
    record_snapshot(2.0, recorded_at="2026-08-15T12:00:01+00:00")

    assert [s.total_value for s in list_snapshots()] == [1.0, 2.0, 3.0]


def test_since_filters_inclusively():
    for i in range(3):
        record_snapshot(float(i), recorded_at=f"2026-08-15T12:00:0{i}+00:00")

    values = [s.total_value for s in list_snapshots(since="2026-08-15T12:00:01+00:00")]
    assert values == [1.0, 2.0]


def test_limit_keeps_most_recent_but_stays_oldest_first():
    for i in range(5):
        record_snapshot(float(i), recorded_at=f"2026-08-15T12:00:0{i}+00:00")

    assert [s.total_value for s in list_snapshots(limit=2)] == [3.0, 4.0]


def test_scoped_per_user():
    record_snapshot(1.0)
    record_snapshot(2.0, user_id="other")

    assert [s.total_value for s in list_snapshots()] == [1.0]
    assert [s.total_value for s in list_snapshots(user_id="other")] == [2.0]
