"""Read-only access to stored diagnostic bundles, for incidents on
infrastructure the agent has no direct query access to. Unlike loki.py's
live LogQL search, this searches static text captured at upload time."""
import re

import diagnostics as store


def search_diagnostic_bundle(deployment_id: int, query: str, user_id: int) -> str:
    bundles = store.list_bundles(deployment_id, user_id)
    if not bundles:
        return f"No diagnostic bundles uploaded for deployment {deployment_id}."

    try:
        pattern = re.compile(query, re.IGNORECASE)
    except re.error:
        pattern = re.compile(re.escape(query), re.IGNORECASE)

    matches = []
    for bundle in bundles:
        for field in ("logs_excerpt", "metrics_excerpt", "config_excerpt", "screenshot_excerpt"):
            for line in (bundle.get(field) or "").splitlines():
                if pattern.search(line):
                    matches.append(f"[{bundle['filename']}:{field}] {line}")

    if not matches:
        return f"No matches for {query!r} in {len(bundles)} uploaded bundle(s) for deployment {deployment_id}."
    return "\n".join(matches[:50])


def get_diagnostic_bundle_summary(deployment_id: int, user_id: int) -> str:
    bundles = store.list_bundles(deployment_id, user_id)
    if not bundles:
        return f"No diagnostic bundles uploaded for deployment {deployment_id}."

    lines = [f"{len(bundles)} bundle(s) uploaded for deployment {deployment_id}:"]
    for b in bundles:
        lines.append(
            f"- {b['filename']} (uploaded {b['uploaded_at']}): "
            f"logs={'yes' if b['logs_excerpt'] else 'no'}, "
            f"metrics={'yes' if b['metrics_excerpt'] else 'no'}, "
            f"config={'yes' if b['config_excerpt'] else 'no'}, "
            f"screenshot={'yes' if b.get('screenshot_excerpt') else 'no'}, "
            f"manifest={b['extracted_manifest'] or 'none'}"
        )
    return "\n".join(lines)
