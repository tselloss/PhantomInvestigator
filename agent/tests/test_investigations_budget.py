import investigations


class _FakeConn:
    """Records the SQL/params monthly_cost_usd issued and returns canned
    fetchall() rows -- same style as test_investigations_dedup.py's
    _FakeConn, checking the query shape without needing a real Postgres."""

    def __init__(self, fetchall_result=None):
        self.fetchall_result = fetchall_result or []
        self.last_query = None
        self.last_params = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.last_query = " ".join(sql.split())
        self.last_params = params
        return self

    def fetchall(self):
        return self.fetchall_result


def test_monthly_cost_usd_scopes_to_current_calendar_month(monkeypatch):
    fake = _FakeConn(fetchall_result=[])
    monkeypatch.setattr(investigations, "_connect", lambda: fake)

    investigations.monthly_cost_usd(1)

    assert "date_trunc('month', now())" in fake.last_query
    assert "owner_user_id = %s" in fake.last_query
    assert fake.last_params == (1,)


def test_monthly_cost_usd_sums_cost_across_rows(monkeypatch):
    rows = [
        ({"usage": {"cost_usd": 0.5}},),
        ({"usage": {"cost_usd": 0.25}},),
    ]
    fake = _FakeConn(fetchall_result=rows)
    monkeypatch.setattr(investigations, "_connect", lambda: fake)

    assert investigations.monthly_cost_usd(1) == 0.75


def test_monthly_cost_usd_ignores_rows_with_no_result(monkeypatch):
    rows = [(None,), ({},), ({"usage": {"cost_usd": 1.0}},)]
    fake = _FakeConn(fetchall_result=rows)
    monkeypatch.setattr(investigations, "_connect", lambda: fake)

    assert investigations.monthly_cost_usd(1) == 1.0


def test_monthly_cost_usd_zero_when_no_investigations(monkeypatch):
    fake = _FakeConn(fetchall_result=[])
    monkeypatch.setattr(investigations, "_connect", lambda: fake)

    assert investigations.monthly_cost_usd(1) == 0.0
