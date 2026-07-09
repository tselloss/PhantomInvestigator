from unittest.mock import patch

from tools import diagnostics

BUNDLE = {
    "id": 1,
    "filename": "acme-bundle.zip",
    "uploaded_at": "2026-07-07T00:00:00Z",
    "logs_excerpt": "line one\nERROR pool exhausted\nline three",
    "metrics_excerpt": "cpu=99%",
    "config_excerpt": '{"version": "1.4.2"}',
    "extracted_manifest": {"version": "1.4.2"},
    "screenshot_excerpt": "Visible error: 502 Bad Gateway on checkout page",
}


def test_search_diagnostic_bundle_no_bundles():
    with patch.object(diagnostics.store, "list_bundles", return_value=[]):
        result = diagnostics.search_diagnostic_bundle(42, "error", 1)
    assert "No diagnostic bundles" in result


def test_search_diagnostic_bundle_finds_match():
    with patch.object(diagnostics.store, "list_bundles", return_value=[BUNDLE]):
        result = diagnostics.search_diagnostic_bundle(42, "pool exhausted", 1)
    assert "ERROR pool exhausted" in result
    assert "acme-bundle.zip" in result


def test_search_diagnostic_bundle_finds_match_in_screenshot_excerpt():
    with patch.object(diagnostics.store, "list_bundles", return_value=[BUNDLE]):
        result = diagnostics.search_diagnostic_bundle(42, "502 Bad Gateway", 1)
    assert "502 Bad Gateway" in result
    assert "acme-bundle.zip" in result


def test_search_diagnostic_bundle_no_match():
    with patch.object(diagnostics.store, "list_bundles", return_value=[BUNDLE]):
        result = diagnostics.search_diagnostic_bundle(42, "nonexistent-string", 1)
    assert "No matches" in result


def test_search_diagnostic_bundle_falls_back_on_bad_regex():
    """An invalid regex (unbalanced paren) must not crash the tool call --
    fall back to a literal substring match instead."""
    with patch.object(diagnostics.store, "list_bundles", return_value=[BUNDLE]):
        result = diagnostics.search_diagnostic_bundle(42, "pool exhausted(", 1)
    assert result == "No matches for 'pool exhausted(' in 1 uploaded bundle(s) for deployment 42."


def test_get_diagnostic_bundle_summary_no_bundles():
    with patch.object(diagnostics.store, "list_bundles", return_value=[]):
        result = diagnostics.get_diagnostic_bundle_summary(42, 1)
    assert "No diagnostic bundles" in result


def test_get_diagnostic_bundle_summary_lists_bundles():
    with patch.object(diagnostics.store, "list_bundles", return_value=[BUNDLE]):
        result = diagnostics.get_diagnostic_bundle_summary(42, 1)
    assert "acme-bundle.zip" in result
    assert "logs=yes" in result
    assert "screenshot=yes" in result
    assert "1.4.2" in result
