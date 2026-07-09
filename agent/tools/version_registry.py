"""Version/drift lookups: what's on record for a deployment's version
history, and how its latest known build compares to the vendor's own
release catalog. Read-only against the clients.py registry for the first
two functions; record_version_fingerprint (used in black-box mode) is the
one write path, so reconstructed facts survive even a run that never
reaches submit_postmortem."""
import json

import clients


def get_deployment_profile(deployment_id: int, user_id: int) -> str:
    """Everything on record for a deployment: its latest version snapshot
    (self-reported, uploaded, or reconstructed) plus how many snapshots
    exist in total -- the first thing to check before assuming nothing is
    known about a deployment."""
    deployment = clients.get_deployment(deployment_id, user_id)
    if not deployment:
        return f"ERROR: no deployment with id {deployment_id}"

    client = clients.get_client(deployment["client_id"], user_id)
    client_name = client["name"] if client else "?"
    lines = [f"Deployment {deployment_id}: {client_name} / {deployment['label']} ({deployment['environment']})"]

    if deployment.get("github_repo"):
        lines.append(f"GitHub repo: {deployment['github_repo']} (use this for get_github_runs/get_github_run_logs/get_deploy_diff).")
    if deployment.get("jira_project_key"):
        lines.append(f"Jira project key: {deployment['jira_project_key']}.")

    snapshots = clients.list_snapshots(deployment_id, user_id)
    if not snapshots:
        lines.append("No version/build info known yet -- nothing self-reported, uploaded, or reconstructed for this deployment.")
        return "\n".join(lines)

    latest = snapshots[0]
    lines.append(
        f"Latest known: version={latest['app_version'] or 'unknown'}, build_sha={latest['build_sha'] or 'unknown'} "
        f"(source={latest['source']}, reported_at={latest['reported_at']}, confidence={latest['confidence']})"
    )
    if len(snapshots) > 1:
        lines.append(f"{len(snapshots)} snapshots on record for this deployment (most recent shown above).")
    return "\n".join(lines)


def diff_against_known_release(deployment_id: int, user_id: int) -> str:
    """Compares the deployment's latest snapshot manifest against the
    vendor's known_releases catalog and reports what deviates from stock."""
    snapshot = clients.get_latest_snapshot(deployment_id, user_id)
    if not snapshot:
        return f"No version snapshot on record for deployment {deployment_id} -- nothing to diff yet."

    release = clients.get_known_release_by_build_sha(snapshot["build_sha"]) if snapshot["build_sha"] else None
    if not release:
        matching = [r for r in clients.list_known_releases() if r["version"] == snapshot["app_version"]]
        release = matching[0] if matching else None

    if not release:
        return (
            f"Deployment {deployment_id} reports version={snapshot['app_version']!r}, "
            f"build_sha={snapshot['build_sha']!r}, which doesn't match any entry in the known_releases catalog -- "
            "either an unreleased/custom build, or the catalog is incomplete. Treat as deviating from stock "
            "until proven otherwise."
        )

    deviations = []
    if release["build_sha"] and snapshot["build_sha"] and release["build_sha"] != snapshot["build_sha"]:
        deviations.append(f"build_sha differs: stock={release['build_sha']}, deployment={snapshot['build_sha']}")

    snapshot_manifest = snapshot.get("manifest") or {}
    release_manifest = release.get("manifest") or {}
    applied_patches = snapshot_manifest.get("applied_patch_ids") or []
    if applied_patches:
        deviations.append(f"local patches applied on top of stock: {json.dumps(applied_patches)}")

    for key in sorted(set(snapshot_manifest) & set(release_manifest)):
        if key == "applied_patch_ids":
            continue
        if snapshot_manifest[key] != release_manifest[key]:
            deviations.append(f"manifest field '{key}' differs: stock={release_manifest[key]!r}, deployment={snapshot_manifest[key]!r}")

    exact_build_match = bool(snapshot["build_sha"]) and release["build_sha"] == snapshot["build_sha"]
    confidence = "high" if exact_build_match else "medium"

    if not deviations:
        return f"Deployment {deployment_id} matches known release {release['version']} ({confidence} confidence) -- no drift detected."
    return (
        f"Deployment {deployment_id} matches known release {release['version']} as a base ({confidence} confidence), "
        f"but deviates: {'; '.join(deviations)}"
    )


def record_version_fingerprint(
    deployment_id: int,
    probable_version: str | None,
    probable_build_sha: str | None,
    drift_notes: str,
    confidence: float,
    user_id: int,
    source_investigation_id: int | None = None,
) -> str:
    """Records a best-effort version/drift reconstruction for a deployment
    with no prior snapshot -- the black-box worst case. Call this as soon
    as any fact is established, not only at submit_postmortem time: the
    investigation can end early on the step/cost budget, and partial
    progress must still persist so the *next* incident for this deployment
    doesn't start from zero again."""
    try:
        notes = json.loads(drift_notes) if drift_notes else []
    except ValueError:
        notes = [drift_notes]

    snapshot = clients.record_snapshot(
        deployment_id,
        user_id,
        source="reconstructed",
        app_version=probable_version,
        build_sha=probable_build_sha,
        manifest={"drift_notes": notes},
        confidence=confidence,
        source_investigation_id=source_investigation_id,
    )
    return f"Recorded reconstructed snapshot {snapshot['id']} for deployment {deployment_id}: version={probable_version!r}, confidence={confidence}."
