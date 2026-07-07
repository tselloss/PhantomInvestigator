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
    assert jira.get_ticket("OPS-1").startswith("ERROR")


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
    result = jira.get_ticket("OPS-1")
    assert route.called
    assert "Checkout down" in result
    assert "still broken" in result
    assert "Open" in result


@respx.mock
def test_get_ticket_handles_http_error(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "https://example.atlassian.net")
    respx.get("https://example.atlassian.net/rest/api/3/issue/OPS-1").mock(return_value=httpx.Response(404))
    result = jira.get_ticket("OPS-1")
    assert result.startswith("ERROR")


def test_post_comment_requires_base_url(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "")
    assert jira.post_comment("OPS-1", "body").startswith("ERROR")


@respx.mock
def test_post_comment_sends_adf_payload(monkeypatch):
    monkeypatch.setattr(jira, "JIRA_BASE_URL", "https://example.atlassian.net")
    route = respx.post("https://example.atlassian.net/rest/api/3/issue/OPS-1/comment").mock(
        return_value=httpx.Response(201, json={})
    )
    result = jira.post_comment("OPS-1", "root cause: pool exhaustion")

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
    result = jira.post_comment("OPS-1", "body")
    assert result.startswith("ERROR")
