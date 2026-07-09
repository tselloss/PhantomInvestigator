from unittest.mock import patch

from tools import version_registry

DEPLOYMENT = {"id": 42, "client_id": 7, "label": "prod", "environment": "production"}
CLIENT = {"id": 7, "name": "Acme Corp"}


def test_get_deployment_profile_unknown_deployment():
    with patch.object(version_registry.clients, "get_deployment", return_value=None):
        result = version_registry.get_deployment_profile(42, 1)
    assert result.startswith("ERROR")


def test_get_deployment_profile_no_snapshots():
    with (
        patch.object(version_registry.clients, "get_deployment", return_value=DEPLOYMENT),
        patch.object(version_registry.clients, "get_client", return_value=CLIENT),
        patch.object(version_registry.clients, "list_snapshots", return_value=[]),
    ):
        result = version_registry.get_deployment_profile(42, 1)
    assert "Acme Corp / prod" in result
    assert "No version/build info known yet" in result


def test_get_deployment_profile_includes_repo_and_jira_key():
    deployment = {**DEPLOYMENT, "github_repo": "acme/widgets", "jira_project_key": "OPS"}
    with (
        patch.object(version_registry.clients, "get_deployment", return_value=deployment),
        patch.object(version_registry.clients, "get_client", return_value=CLIENT),
        patch.object(version_registry.clients, "list_snapshots", return_value=[]),
    ):
        result = version_registry.get_deployment_profile(42, 1)
    assert "GitHub repo: acme/widgets" in result
    assert "Jira project key: OPS" in result


def test_get_deployment_profile_with_snapshots():
    snapshots = [
        {"app_version": "1.4.2", "build_sha": "abc123", "source": "self_report", "reported_at": "t2", "confidence": None},
        {"app_version": "1.4.1", "build_sha": "abc000", "source": "reconstructed", "reported_at": "t1", "confidence": 0.5},
    ]
    with (
        patch.object(version_registry.clients, "get_deployment", return_value=DEPLOYMENT),
        patch.object(version_registry.clients, "get_client", return_value=CLIENT),
        patch.object(version_registry.clients, "list_snapshots", return_value=snapshots),
    ):
        result = version_registry.get_deployment_profile(42, 1)
    assert "1.4.2" in result
    assert "self_report" in result
    assert "2 snapshots on record" in result


def test_diff_against_known_release_no_snapshot():
    with patch.object(version_registry.clients, "get_latest_snapshot", return_value=None):
        result = version_registry.diff_against_known_release(42, 1)
    assert "nothing to diff yet" in result


def test_diff_against_known_release_no_matching_catalog_entry():
    snapshot = {"app_version": "9.9.9", "build_sha": "unknownsha", "manifest": {}}
    with (
        patch.object(version_registry.clients, "get_latest_snapshot", return_value=snapshot),
        patch.object(version_registry.clients, "get_known_release_by_build_sha", return_value=None),
        patch.object(version_registry.clients, "list_known_releases", return_value=[]),
    ):
        result = version_registry.diff_against_known_release(42, 1)
    assert "doesn't match any entry" in result
    assert "9.9.9" in result


def test_diff_against_known_release_exact_match_no_drift():
    snapshot = {"app_version": "1.4.2", "build_sha": "abc123", "manifest": {"config_schema_version": 3}}
    release = {"version": "1.4.2", "build_sha": "abc123", "manifest": {"config_schema_version": 3}}
    with (
        patch.object(version_registry.clients, "get_latest_snapshot", return_value=snapshot),
        patch.object(version_registry.clients, "get_known_release_by_build_sha", return_value=release),
    ):
        result = version_registry.diff_against_known_release(42, 1)
    assert "no drift detected" in result
    assert "high confidence" in result


def test_diff_against_known_release_detects_patches_and_config_drift():
    snapshot = {
        "app_version": "1.4.2",
        "build_sha": None,
        "manifest": {"config_schema_version": 4, "applied_patch_ids": ["hotfix-7"]},
    }
    release = {"version": "1.4.2", "build_sha": "abc123", "manifest": {"config_schema_version": 3}}
    with (
        patch.object(version_registry.clients, "get_latest_snapshot", return_value=snapshot),
        patch.object(version_registry.clients, "get_known_release_by_build_sha", return_value=None),
        patch.object(version_registry.clients, "list_known_releases", return_value=[release]),
    ):
        result = version_registry.diff_against_known_release(42, 1)
    assert "medium confidence" in result
    assert "hotfix-7" in result
    assert "config_schema_version" in result


def test_record_version_fingerprint_writes_reconstructed_snapshot():
    with patch.object(version_registry.clients, "record_snapshot", return_value={"id": 5}) as mock_record:
        result = version_registry.record_version_fingerprint(
            42, "1.4.x (probable)", None, '["missing rate limiter patch"]', 0.4, 1, source_investigation_id=99
        )
    assert "Recorded reconstructed snapshot 5" in result
    mock_record.assert_called_once_with(
        42,
        1,
        source="reconstructed",
        app_version="1.4.x (probable)",
        build_sha=None,
        manifest={"drift_notes": ["missing rate limiter patch"]},
        confidence=0.4,
        source_investigation_id=99,
    )
