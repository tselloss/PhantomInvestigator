import httpx
import respx

from tools import azure_devops as ado


def _configure(monkeypatch):
    monkeypatch.setattr(ado, "AZURE_DEVOPS_ORG", "contoso")
    monkeypatch.setattr(ado, "AZURE_DEVOPS_PROJECT", "MyProject")
    monkeypatch.setattr(ado, "AZURE_DEVOPS_PAT", "pat-token")


def test_strip_html_removes_tags_and_collapses_whitespace():
    assert ado._strip_html("<div><p>Checkout is</p>\n<p>returning 500s.</p></div>") == "Checkout is returning 500s."


def test_strip_html_handles_none():
    assert ado._strip_html(None) == ""


def test_get_work_item_requires_config(monkeypatch):
    monkeypatch.setattr(ado, "AZURE_DEVOPS_ORG", "")
    assert ado.get_work_item(42, 1).startswith("ERROR")


@respx.mock
def test_get_work_item_formats_fields(monkeypatch):
    _configure(monkeypatch)
    respx.get("https://dev.azure.com/contoso/MyProject/_apis/wit/workitems/42").mock(
        return_value=httpx.Response(
            200,
            json={
                "fields": {
                    "System.WorkItemType": "Bug",
                    "System.Title": "Checkout down",
                    "System.State": "Active",
                    "System.CreatedDate": "2026-07-01T00:00:00Z",
                    "System.Description": "<div>Users can't checkout</div>",
                }
            },
        )
    )
    respx.get("https://dev.azure.com/contoso/MyProject/_apis/wit/workItems/42/comments").mock(
        return_value=httpx.Response(200, json={"comments": [{"text": "still broken"}]})
    )
    result = ado.get_work_item(42, 1)
    assert "Checkout down" in result
    assert "Bug" in result
    assert "Users can't checkout" in result
    assert "still broken" in result


@respx.mock
def test_get_work_item_handles_http_error(monkeypatch):
    _configure(monkeypatch)
    respx.get("https://dev.azure.com/contoso/MyProject/_apis/wit/workitems/42").mock(return_value=httpx.Response(404))
    result = ado.get_work_item(42, 1)
    assert result.startswith("ERROR")


@respx.mock
def test_get_work_item_tolerates_comments_endpoint_failure(monkeypatch):
    _configure(monkeypatch)
    respx.get("https://dev.azure.com/contoso/MyProject/_apis/wit/workitems/42").mock(
        return_value=httpx.Response(
            200,
            json={"fields": {"System.WorkItemType": "Task", "System.Title": "Investigate", "System.State": "New"}},
        )
    )
    respx.get("https://dev.azure.com/contoso/MyProject/_apis/wit/workItems/42/comments").mock(
        return_value=httpx.Response(500)
    )
    result = ado.get_work_item(42, 1)
    assert "Investigate" in result
    assert not result.startswith("ERROR")


def test_post_comment_requires_config(monkeypatch):
    monkeypatch.setattr(ado, "AZURE_DEVOPS_PAT", "")
    assert ado.post_comment(42, "root cause: pool exhaustion", 1).startswith("ERROR")


@respx.mock
def test_post_comment_sends_text_payload(monkeypatch):
    _configure(monkeypatch)
    route = respx.post("https://dev.azure.com/contoso/MyProject/_apis/wit/workItems/42/comments").mock(
        return_value=httpx.Response(200, json={})
    )
    result = ado.post_comment(42, "root cause: pool exhaustion", 1)
    assert route.called
    assert "Comment posted" in result


@respx.mock
def test_post_comment_handles_http_error(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr("tools._http.time.sleep", lambda s: None)
    respx.post("https://dev.azure.com/contoso/MyProject/_apis/wit/workItems/42/comments").mock(
        return_value=httpx.Response(500)
    )
    result = ado.post_comment(42, "body", 1)
    assert result.startswith("ERROR")


def test_get_work_item_passes_deployment_id_to_config(monkeypatch):
    captured = {}

    def fake_config(user_id, deployment_id=None, client_id=None):
        captured["deployment_id"] = deployment_id
        return {"organization": "", "project": "", "pat": ""}

    monkeypatch.setattr(ado, "_config", fake_config)
    ado.get_work_item(42, 1, deployment_id=7)
    assert captured["deployment_id"] == 7


def test_post_comment_passes_deployment_id_to_config(monkeypatch):
    captured = {}

    def fake_config(user_id, deployment_id=None, client_id=None):
        captured["deployment_id"] = deployment_id
        return {"organization": "", "project": "", "pat": ""}

    monkeypatch.setattr(ado, "_config", fake_config)
    ado.post_comment(42, "body", 1, deployment_id=7)
    assert captured["deployment_id"] == 7
