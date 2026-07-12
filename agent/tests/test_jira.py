import json

import httpx
import respx

from tools import jira

ADF_DESCRIPTION = {
    "type": "doc",
    "version": 1,
    "content": [
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Checkout is"},
                {"type": "text", "text": "returning 500s."},
            ],
        },
    ],
}


def test_extract_text_walks_nested_adf():
    assert jira._extract_text(ADF_DESCRIPTION) == "Checkout is returning 500s."


def test_extract_text_handles_plain_string():
    assert jira._extract_text("already plain") == "already plain"


def test_extract_text_handles_empty():
    assert jira._extract_text(None) == ""


def test_get_ticket_requires_base_url(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "")
    assert jira.get_ticket("OPS-1", 1).startswith("ERROR")


def test_get_ticket_returns_demo_data_when_demo_mode_enabled(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "")
    monkeypatch.setattr(jira.users, "get_demo_mode", lambda user_id: True)
    result = jira.get_ticket("OPS-1", 1)
    assert "DEMO DATA" in result
    assert "OPS-1" in result


@respx.mock
def test_get_ticket_formats_fields(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "https://example.atlassian.net")
    route = respx.get("https://example.atlassian.net/rest/api/3/issue/OPS-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "fields": {
                    "summary": "Checkout down",
                    "status": {"name": "Open"},
                    "created": "2026-07-01T00:00:00.000+0000",
                    "description": ADF_DESCRIPTION,
                    "comment": {"comments": [{"body": "still broken"}]},
                }
            },
        )
    )
    result = jira.get_ticket("OPS-1", 1)
    assert route.called
    assert "Checkout down" in result
    assert "still broken" in result
    assert "Open" in result


@respx.mock
def test_get_ticket_handles_http_error(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "https://example.atlassian.net")
    respx.get("https://example.atlassian.net/rest/api/3/issue/OPS-1").mock(return_value=httpx.Response(404))
    result = jira.get_ticket("OPS-1", 1)
    assert result.startswith("ERROR")


def test_get_ticket_passes_deployment_id_to_config(monkeypatch):
    captured = {}

    def fake_config(user_id, deployment_id=None, client_id=None):
        captured["deployment_id"] = deployment_id
        return {"base_url": "", "email": "", "api_token": ""}

    monkeypatch.setattr(jira, "_config", fake_config)
    jira.get_ticket("OPS-1", 1, deployment_id=42)
    assert captured["deployment_id"] == 42


def test_post_comment_passes_deployment_id_to_config(monkeypatch):
    captured = {}

    def fake_config(user_id, deployment_id=None, client_id=None):
        captured["deployment_id"] = deployment_id
        return {"base_url": "", "email": "", "api_token": ""}

    monkeypatch.setattr(jira, "_config", fake_config)
    jira.post_comment("OPS-1", "body", 1, deployment_id=42)
    assert captured["deployment_id"] == 42


def test_issue_url_builds_browse_link(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "https://example.atlassian.net")
    assert jira.issue_url("OPS-1", 1) == "https://example.atlassian.net/browse/OPS-1"


def test_issue_url_none_when_no_base_url(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "")
    assert jira.issue_url("OPS-1", 1) is None


def test_post_comment_returns_demo_data_when_demo_mode_enabled(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "")
    monkeypatch.setattr(jira.users, "get_demo_mode", lambda user_id: True)
    result = jira.post_comment("OPS-1", "body", 1)
    assert "demo mode" in result
    assert "OPS-1" in result


def test_post_comment_requires_base_url(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "")
    assert jira.post_comment("OPS-1", "body", 1).startswith("ERROR")


@respx.mock
def test_post_comment_sends_adf_payload(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "https://example.atlassian.net")
    route = respx.post("https://example.atlassian.net/rest/api/3/issue/OPS-1/comment").mock(
        return_value=httpx.Response(201, json={})
    )
    result = jira.post_comment("OPS-1", "root cause: pool exhaustion", 1)

    assert route.called
    sent_body = json.loads(route.calls[0].request.content)
    assert sent_body["body"]["type"] == "doc"
    assert sent_body["body"]["content"][0]["content"][0]["text"] == "root cause: pool exhaustion"
    assert "Comment posted" in result


@respx.mock
def test_post_comment_handles_http_error(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "https://example.atlassian.net")
    monkeypatch.setattr("tools._http.time.sleep", lambda s: None)
    respx.post("https://example.atlassian.net/rest/api/3/issue/OPS-1/comment").mock(return_value=httpx.Response(500))
    result = jira.post_comment("OPS-1", "body", 1)
    assert result.startswith("ERROR")


def test_list_recent_issues_returns_empty_when_not_configured(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "")
    assert jira.list_recent_issues(1) == []


def test_list_recent_issues_returns_demo_data_when_demo_mode_enabled(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "")
    monkeypatch.setattr(jira.users, "get_demo_mode", lambda user_id: True)
    result = jira.list_recent_issues(1)
    assert result[0]["source"] == "jira"


@respx.mock
def test_list_recent_issues_formats_results(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "https://example.atlassian.net")
    route = respx.get("https://example.atlassian.net/rest/api/3/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "issues": [
                    {
                        "key": "OPS-1",
                        "fields": {
                            "summary": "Checkout down",
                            "status": {"name": "Open"},
                            "created": "2026-07-10T14:11:00.000+0000",
                            "issuetype": {"name": "Bug"},
                        },
                    }
                ]
            },
        )
    )
    result = jira.list_recent_issues(1)
    assert route.called
    assert result == [
        {
            "source": "jira", "id": "OPS-1", "title": "Checkout down", "type": "Bug", "status": "Open",
            "updated": "2026-07-10T14:11:00.000+0000", "url": "https://example.atlassian.net/browse/OPS-1",
        }
    ]


@respx.mock
def test_list_recent_issues_handles_http_error(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "https://example.atlassian.net")
    respx.get("https://example.atlassian.net/rest/api/3/search").mock(return_value=httpx.Response(500))
    assert jira.list_recent_issues(1) == []


def test_list_recent_issues_passes_client_id_to_config(monkeypatch):
    captured = {}

    def fake_config(user_id, deployment_id=None, client_id=None):
        captured["client_id"] = client_id
        return {"base_url": "", "email": "", "api_token": ""}

    monkeypatch.setattr(jira, "_config", fake_config)
    jira.list_recent_issues(1, client_id=7)
    assert captured["client_id"] == 7
