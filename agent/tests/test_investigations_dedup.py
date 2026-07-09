import investigations


class _FakeConn:
    """Records the SQL/params find_recent_duplicate issued and returns a
    canned fetchone() result -- checks the branching/params logic without
    needing a real Postgres to parse the query against."""

    def __init__(self, fetchone_result=None):
        self.fetchone_result = fetchone_result
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

    def fetchone(self):
        return self.fetchone_result


def test_find_recent_duplicate_matches_on_source_ref_when_present(monkeypatch):
    fake = _FakeConn(fetchone_result=None)
    monkeypatch.setattr(investigations, "_connect", lambda: fake)

    investigations.find_recent_duplicate("jira", "OPS-1", 42, "checkout down", 1)

    assert "source_ref = %s" in fake.last_query
    assert "alert_text = %s" not in fake.last_query
    assert fake.last_params == ("jira", "OPS-1", 1, investigations.DEDUP_COOLDOWN_MINUTES)


def test_find_recent_duplicate_matches_on_alert_text_without_source_ref(monkeypatch):
    fake = _FakeConn(fetchone_result=None)
    monkeypatch.setattr(investigations, "_connect", lambda: fake)

    investigations.find_recent_duplicate("manual", None, 42, "checkout down", 1)

    assert "alert_text = %s" in fake.last_query
    assert fake.last_params == ("manual", "checkout down", 1, 42, investigations.DEDUP_COOLDOWN_MINUTES)


def test_find_recent_duplicate_respects_custom_cooldown(monkeypatch):
    fake = _FakeConn(fetchone_result=None)
    monkeypatch.setattr(investigations, "_connect", lambda: fake)

    investigations.find_recent_duplicate("jira", "OPS-1", None, "x", 1, cooldown_minutes=30)

    assert fake.last_params == ("jira", "OPS-1", 1, 30)


def test_find_recent_duplicate_returns_none_when_no_match(monkeypatch):
    fake = _FakeConn(fetchone_result=None)
    monkeypatch.setattr(investigations, "_connect", lambda: fake)
    assert investigations.find_recent_duplicate("jira", "OPS-1", None, "x", 1) is None


def test_find_recent_duplicate_returns_existing_row_as_dict(monkeypatch):
    row = tuple(99 if col == "id" else None for col in investigations._COLUMNS)
    fake = _FakeConn(fetchone_result=row)
    monkeypatch.setattr(investigations, "_connect", lambda: fake)

    result = investigations.find_recent_duplicate("jira", "OPS-1", None, "x", 1)
    assert result["id"] == 99
