import structlog
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_request_log_omits_query_string():
    """The Jira webhook secret travels as a ?secret=... query param (Jira
    Cloud has no native payload signing -- see docs/decisions.md). The
    request-logging middleware in main.py must never log request.url (which
    includes the query string), only request.url.path."""
    with structlog.testing.capture_logs() as logs:
        client.post("/webhooks/jira?secret=verysecretvalue123", json={"issue": {}})

    request_logs = [e for e in logs if e.get("event") == "http.request"]
    assert request_logs
    for entry in request_logs:
        assert entry["path"] == "/webhooks/jira"
        assert "verysecretvalue123" not in str(entry)
