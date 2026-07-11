import pytest

import settings


def test_get_profile_reports_account_and_budget(monkeypatch):
    monkeypatch.setattr(
        settings.users, "get_user_by_id",
        lambda user_id: {"username": "alice", "email": "alice@example.com", "google_id": None, "demo_mode": False},
    )
    monkeypatch.setattr(
        settings.billing, "check_budget",
        lambda user_id: {"allowed": True, "spent_usd": 1.5, "limit_usd": 10.0},
    )

    profile = settings.get_profile(1)
    assert profile == {
        "username": "alice",
        "email": "alice@example.com",
        "sign_in_method": "password",
        "monthly_limit_usd": 10.0,
        "spent_this_month_usd": 1.5,
        "demo_mode": False,
    }


def test_get_profile_reports_google_sign_in(monkeypatch):
    monkeypatch.setattr(
        settings.users, "get_user_by_id",
        lambda user_id: {"username": "bob", "email": "bob@example.com", "google_id": "g-1"},
    )
    monkeypatch.setattr(
        settings.billing, "check_budget",
        lambda user_id: {"allowed": True, "spent_usd": 0.0, "limit_usd": None},
    )

    profile = settings.get_profile(1)
    assert profile["sign_in_method"] == "google"


def test_set_monthly_limit_delegates_to_users(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        settings.users, "update_monthly_limit",
        lambda user_id, limit_usd: captured.update(user_id=user_id, limit_usd=limit_usd),
    )
    monkeypatch.setattr(settings, "get_profile", lambda user_id: {"monthly_limit_usd": 5.0})

    result = settings.set_monthly_limit(1, 5.0)
    assert captured == {"user_id": 1, "limit_usd": 5.0}
    assert result == {"monthly_limit_usd": 5.0}


def test_set_monthly_limit_allows_clearing_to_none(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        settings.users, "update_monthly_limit",
        lambda user_id, limit_usd: captured.update(user_id=user_id, limit_usd=limit_usd),
    )
    monkeypatch.setattr(settings, "get_profile", lambda user_id: {"monthly_limit_usd": None})

    settings.set_monthly_limit(1, None)
    assert captured == {"user_id": 1, "limit_usd": None}


def test_set_monthly_limit_rejects_negative_value():
    with pytest.raises(ValueError):
        settings.set_monthly_limit(1, -1.0)


def test_get_profile_reports_demo_mode_when_enabled(monkeypatch):
    monkeypatch.setattr(
        settings.users, "get_user_by_id",
        lambda user_id: {"username": "alice", "email": None, "google_id": None, "demo_mode": True},
    )
    monkeypatch.setattr(
        settings.billing, "check_budget",
        lambda user_id: {"allowed": True, "spent_usd": 0.0, "limit_usd": None},
    )

    assert settings.get_profile(1)["demo_mode"] is True


def test_set_demo_mode_delegates_to_users(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        settings.users, "update_demo_mode",
        lambda user_id, enabled: captured.update(user_id=user_id, enabled=enabled),
    )
    monkeypatch.setattr(settings, "get_profile", lambda user_id: {"demo_mode": True})

    result = settings.set_demo_mode(1, True)
    assert captured == {"user_id": 1, "enabled": True}
    assert result == {"demo_mode": True}
