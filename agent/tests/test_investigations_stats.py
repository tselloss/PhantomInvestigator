"""Covers investigations.stats()'s day-bucketing for the dashboard sparkline
-- the SQL only returns rows that exist, so the zero-fill-every-day logic is
the part actually worth testing (a quiet day must still appear as a 0, not
a missing point)."""
from datetime import datetime, timedelta, timezone

import investigations as store


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        return self

    def fetchall(self):
        return self._rows


def test_stats_zero_fills_days_with_no_investigations(monkeypatch):
    today = datetime.now(timezone.utc)
    rows = [
        ("done", {"usage": {"cost_usd": 0.5}}, today),
        ("done", {"usage": {"cost_usd": 0.25}}, today - timedelta(days=2)),
    ]
    monkeypatch.setattr(store, "_connect", lambda: _FakeConn(rows))

    result = store.stats(owner_user_id=1, days=7)

    assert len(result["daily"]) == 7
    assert result["daily"][-1]["date"] == today.date().isoformat()
    assert result["daily"][-1]["count"] == 1
    assert result["daily"][-3]["count"] == 1
    # every other day in the window had no investigations
    other_days = [d for i, d in enumerate(result["daily"]) if i not in (4, 6)]
    assert all(d["count"] == 0 for d in other_days)
    assert result["total"] == 2
    assert result["total_cost_usd"] == 0.75


def test_stats_daily_is_ordered_oldest_to_newest(monkeypatch):
    monkeypatch.setattr(store, "_connect", lambda: _FakeConn([]))

    result = store.stats(owner_user_id=1, days=3)

    dates = [d["date"] for d in result["daily"]]
    assert dates == sorted(dates)
    assert len(dates) == 3
