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


def test_get_work_item_returns_demo_data_when_demo_mode_enabled(monkeypatch):
    monkeypatch.setattr(ado, "AZURE_DEVOPS_ORG", "")
    monkeypatch.setattr(ado.users, "get_demo_mode", lambda user_id: True)
    result = ado.get_work_item(42, 1)
    assert "DEMO DATA" in result
    assert "42" in result


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


def test_post_comment_returns_demo_data_when_demo_mode_enabled(monkeypatch):
    monkeypatch.setattr(ado, "AZURE_DEVOPS_PAT", "")
    monkeypatch.setattr(ado.users, "get_demo_mode", lambda user_id: True)
    result = ado.post_comment(42, "body", 1)
    assert "demo mode" in result
    assert "42" in result


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


def test_get_recent_commits_requires_config(monkeypatch):
    monkeypatch.setattr(ado, "AZURE_DEVOPS_ORG", "")
    assert ado.get_recent_commits(1).startswith("ERROR")


def test_get_recent_commits_returns_demo_data_when_demo_mode_enabled(monkeypatch):
    monkeypatch.setattr(ado, "AZURE_DEVOPS_ORG", "")
    monkeypatch.setattr(ado.users, "get_demo_mode", lambda user_id: True)
    assert "DEMO DATA" in ado.get_recent_commits(1)


@respx.mock
def test_get_recent_commits_formats_across_repos(monkeypatch):
    _configure(monkeypatch)
    respx.get("https://dev.azure.com/contoso/MyProject/_apis/git/repositories").mock(
        return_value=httpx.Response(200, json={"value": [{"id": "r1", "name": "checkout-service"}]})
    )
    respx.get("https://dev.azure.com/contoso/MyProject/_apis/git/repositories/r1/commits").mock(
        return_value=httpx.Response(200, json={"value": [
            {"commitId": "a1b2c3d4e5", "author": {"name": "jdoe", "date": "2026-07-10T14:02:11Z"}, "comment": "trim idle DB connections"},
        ]})
    )
    result = ado.get_recent_commits(1)
    assert "checkout-service" in result
    assert "a1b2c3d" in result
    assert "trim idle DB connections" in result


@respx.mock
def test_get_recent_commits_skips_repo_that_errors(monkeypatch):
    _configure(monkeypatch)
    respx.get("https://dev.azure.com/contoso/MyProject/_apis/git/repositories").mock(
        return_value=httpx.Response(200, json={"value": [
            {"id": "r1", "name": "broken-repo"}, {"id": "r2", "name": "ok-repo"},
        ]})
    )
    respx.get("https://dev.azure.com/contoso/MyProject/_apis/git/repositories/r1/commits").mock(
        return_value=httpx.Response(500)
    )
    respx.get("https://dev.azure.com/contoso/MyProject/_apis/git/repositories/r2/commits").mock(
        return_value=httpx.Response(200, json={"value": [
            {"commitId": "f9e8d7c6b5", "author": {"name": "asmith", "date": "2026-07-09T09:00:00Z"}, "comment": "ok"},
        ]})
    )
    result = ado.get_recent_commits(1)
    assert "ok-repo" in result
    assert "broken-repo" not in result


@respx.mock
def test_get_recent_commits_detects_expired_pat_html_response(monkeypatch):
    _configure(monkeypatch)
    respx.get("https://dev.azure.com/contoso/MyProject/_apis/git/repositories").mock(
        return_value=httpx.Response(203, content=b"<html>sign in</html>", headers={"content-type": "text/html"})
    )
    result = ado.get_recent_commits(1)
    assert result.startswith("ERROR")
    assert "PAT expired or missing required scopes" in result


def test_get_recent_builds_requires_config(monkeypatch):
    monkeypatch.setattr(ado, "AZURE_DEVOPS_ORG", "")
    assert ado.get_recent_builds(1).startswith("ERROR")


def test_get_recent_builds_returns_demo_data_when_demo_mode_enabled(monkeypatch):
    monkeypatch.setattr(ado, "AZURE_DEVOPS_ORG", "")
    monkeypatch.setattr(ado.users, "get_demo_mode", lambda user_id: True)
    assert "DEMO DATA" in ado.get_recent_builds(1)


@respx.mock
def test_get_recent_builds_formats_results(monkeypatch):
    _configure(monkeypatch)
    respx.get("https://dev.azure.com/contoso/MyProject/_apis/build/builds").mock(
        return_value=httpx.Response(200, json={"value": [
            {
                "id": 8842, "definition": {"name": "deploy-checkout-service"}, "status": "completed",
                "result": "succeeded", "sourceBranch": "refs/heads/main", "sourceVersion": "a1b2c3d4e5",
                "startTime": "2026-07-10T14:02:11Z",
            },
        ]})
    )
    result = ado.get_recent_builds(1, failed_only=True)
    assert "8842" in result
    assert "deploy-checkout-service" in result
    assert "a1b2c3d" in result


@respx.mock
def test_get_recent_builds_no_results(monkeypatch):
    _configure(monkeypatch)
    respx.get("https://dev.azure.com/contoso/MyProject/_apis/build/builds").mock(
        return_value=httpx.Response(200, json={"value": []})
    )
    result = ado.get_recent_builds(1)
    assert "No builds" in result


def test_search_work_items_rejects_empty_query(monkeypatch):
    _configure(monkeypatch)
    result = ado.search_work_items("   ", 1)
    assert result.startswith("ERROR")
    assert "empty" in result


def test_search_work_items_requires_config(monkeypatch):
    monkeypatch.setattr(ado, "AZURE_DEVOPS_ORG", "")
    assert ado.search_work_items("checkout", 1).startswith("ERROR")


def test_search_work_items_returns_demo_data_when_demo_mode_enabled(monkeypatch):
    monkeypatch.setattr(ado, "AZURE_DEVOPS_ORG", "")
    monkeypatch.setattr(ado.users, "get_demo_mode", lambda user_id: True)
    assert "DEMO DATA" in ado.search_work_items("checkout", 1)


@respx.mock
def test_search_work_items_formats_matches(monkeypatch):
    _configure(monkeypatch)
    respx.post("https://dev.azure.com/contoso/MyProject/_apis/wit/wiql").mock(
        return_value=httpx.Response(200, json={"workItems": [{"id": 4821}]})
    )
    respx.get("https://dev.azure.com/contoso/MyProject/_apis/wit/workitems").mock(
        return_value=httpx.Response(200, json={"value": [
            {"fields": {
                "System.Id": 4821, "System.Title": "Checkout down", "System.WorkItemType": "Bug",
                "System.State": "Active", "System.ChangedDate": "2026-07-10T14:11:00Z",
            }},
        ]})
    )
    result = ado.search_work_items("checkout", 1)
    assert "#4821" in result
    assert "Checkout down" in result


@respx.mock
def test_search_work_items_no_matches(monkeypatch):
    _configure(monkeypatch)
    respx.post("https://dev.azure.com/contoso/MyProject/_apis/wit/wiql").mock(
        return_value=httpx.Response(200, json={"workItems": []})
    )
    result = ado.search_work_items("nonexistent", 1)
    assert "No work items matching" in result


def test_list_recent_work_items_returns_empty_when_not_configured(monkeypatch):
    monkeypatch.setattr(ado, "AZURE_DEVOPS_ORG", "")
    assert ado.list_recent_work_items(1) == []


def test_list_recent_work_items_returns_demo_data_when_demo_mode_enabled(monkeypatch):
    monkeypatch.setattr(ado, "AZURE_DEVOPS_ORG", "")
    monkeypatch.setattr(ado.users, "get_demo_mode", lambda user_id: True)
    result = ado.list_recent_work_items(1)
    assert result[0]["source"] == "azure_devops"


@respx.mock
def test_list_recent_work_items_formats_results(monkeypatch):
    _configure(monkeypatch)
    route = respx.post("https://dev.azure.com/contoso/MyProject/_apis/wit/wiql").mock(
        return_value=httpx.Response(200, json={"workItems": [{"id": 4821}]})
    )
    respx.get("https://dev.azure.com/contoso/MyProject/_apis/wit/workitems").mock(
        return_value=httpx.Response(200, json={"value": [
            {"fields": {
                "System.Id": 4821, "System.Title": "Checkout down", "System.WorkItemType": "Bug",
                "System.State": "Active", "System.ChangedDate": "2026-07-10T14:11:00Z",
            }},
        ]})
    )
    result = ado.list_recent_work_items(1)
    assert route.called
    assert "CONTAINS WORDS" not in route.calls.last.request.content.decode()
    assert result == [
        {
            "source": "azure_devops", "id": 4821, "title": "Checkout down", "type": "Bug", "status": "Active",
            "updated": "2026-07-10T14:11:00Z",
            "url": "https://dev.azure.com/contoso/MyProject/_workitems/edit/4821",
        }
    ]


@respx.mock
def test_list_recent_work_items_no_results(monkeypatch):
    _configure(monkeypatch)
    respx.post("https://dev.azure.com/contoso/MyProject/_apis/wit/wiql").mock(
        return_value=httpx.Response(200, json={"workItems": []})
    )
    assert ado.list_recent_work_items(1) == []


@respx.mock
def test_list_recent_work_items_handles_http_error(monkeypatch):
    _configure(monkeypatch)
    respx.post("https://dev.azure.com/contoso/MyProject/_apis/wit/wiql").mock(return_value=httpx.Response(500))
    assert ado.list_recent_work_items(1) == []


def test_list_recent_work_items_passes_client_id_to_config(monkeypatch):
    captured = {}

    def fake_config(user_id, deployment_id=None, client_id=None):
        captured["client_id"] = client_id
        return {"organization": "", "project": "", "pat": ""}

    monkeypatch.setattr(ado, "_config", fake_config)
    ado.list_recent_work_items(1, client_id=7)
    assert captured["client_id"] == 7


@respx.mock
def test_search_work_items_escapes_single_quotes(monkeypatch):
    _configure(monkeypatch)
    route = respx.post("https://dev.azure.com/contoso/MyProject/_apis/wit/wiql").mock(
        return_value=httpx.Response(200, json={"workItems": []})
    )
    ado.search_work_items("O'Brien's checkout", 1)
    sent_query = route.calls.last.request.content.decode()
    assert "O''Brien''s checkout" in sent_query
