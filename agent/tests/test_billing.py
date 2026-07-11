import billing


def test_check_budget_allows_when_no_limit_set(monkeypatch):
    monkeypatch.setattr(billing.users, "get_user_by_id", lambda user_id: {"monthly_limit_usd": None})
    monkeypatch.setattr(billing.investigations, "monthly_cost_usd", lambda user_id: 999.0)

    result = billing.check_budget(1)
    assert result == {"allowed": True, "spent_usd": 999.0, "limit_usd": None}


def test_check_budget_allows_when_under_limit(monkeypatch):
    monkeypatch.setattr(billing.users, "get_user_by_id", lambda user_id: {"monthly_limit_usd": 10.0})
    monkeypatch.setattr(billing.investigations, "monthly_cost_usd", lambda user_id: 5.0)

    result = billing.check_budget(1)
    assert result == {"allowed": True, "spent_usd": 5.0, "limit_usd": 10.0}


def test_check_budget_blocks_when_at_or_over_limit(monkeypatch):
    monkeypatch.setattr(billing.users, "get_user_by_id", lambda user_id: {"monthly_limit_usd": 10.0})
    monkeypatch.setattr(billing.investigations, "monthly_cost_usd", lambda user_id: 10.0)

    result = billing.check_budget(1)
    assert result == {"allowed": False, "spent_usd": 10.0, "limit_usd": 10.0}


def test_check_budget_treats_missing_user_as_unlimited(monkeypatch):
    monkeypatch.setattr(billing.users, "get_user_by_id", lambda user_id: None)
    monkeypatch.setattr(billing.investigations, "monthly_cost_usd", lambda user_id: 5.0)

    result = billing.check_budget(1)
    assert result["allowed"] is True
    assert result["limit_usd"] is None
