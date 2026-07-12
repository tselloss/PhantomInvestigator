"""Turns a finished investigation's proposed_fix_files (if any) into a
pending_fix_action awaiting operator approval -- the code-fix analog of the
pending_action dict routes/webhooks.py builds for a ticket comment (see
schemas.Postmortem.proposed_fix_files, tools/github_actions.py). Kept in its
own module rather than investigations.py (pure persistence, no external API
calls) or duplicated between webhooks.py and main.py, which both need it.

Two independent gates decide whether a proposal is even attempted:
1. The deployment must have a github_repo and a non-empty
   allowed_base_branches -- auto-fix PRs are opt-in per deployment (see
   clients.py), so a deployment that never configured this is a silent
   no-op, same as today.
2. Every proposed file path must be one the model actually read in full via
   get_file_contents THIS run (loop.py's files_read) -- if even one path is
   missing, the WHOLE proposal is dropped rather than silently trimmed,
   since a partial multi-file fix looks identical to a complete one in the
   diff an operator reviews."""
import difflib

from tools import github_actions


def _pr_title(pm: dict) -> str:
    return f"Phantom Investigator fix: {pm['title']}"[:250]


def _pr_body(pm: dict) -> str:
    return (
        f"Automated fix proposed by Phantom Investigator.\n\n"
        f"Root cause ({pm['confidence']:.0%} confidence): {pm['root_cause']}\n\n"
        f"{pm['suggested_fix']}\n\n"
        "Review the diff before merging -- this PR was opened after operator approval "
        "but its content was not independently tested."
    )


def build_pending_fix_action(
    pm: dict | None, deployment: dict | None, files_read: list[str], owner_user_id: int
) -> dict | None:
    """None unless every gate above passes. On success, fetches each file's
    CURRENT content fresh (never reused from the loop -- see files_read's
    docstring in loop.py for why trace/loop state can't stand in for a live
    read) against the deployment's first allowed branch, and computes a
    unified diff via stdlib difflib purely for the approval UI to display.
    Returns {"type": "github_pr", "repo", "allowed_base_branches",
    "default_branch", "files": [{"path", "content", "diff"}], "pr_title",
    "pr_body"} or None."""
    if not pm:
        return None
    proposed = pm.get("proposed_fix_files")
    if not proposed:
        return None
    if not deployment:
        return None
    repo = deployment.get("github_repo")
    allowed = deployment.get("allowed_base_branches") or []
    if not repo or not allowed:
        return None

    read_set = set(files_read or [])
    if any(f["path"] not in read_set for f in proposed):
        return None

    base_branch = allowed[0]
    files = []
    for f in proposed:
        current = github_actions.get_file_contents(
            repo, f["path"], base_branch, owner_user_id, deployment_id=deployment["id"]
        )
        if current.startswith("ERROR"):
            # Can't safely diff/commit against a file we can't currently
            # read (deleted/renamed since the model saw it, token scope
            # changed, etc.) -- same drop-the-whole-proposal rule as above.
            return None
        diff = "\n".join(difflib.unified_diff(
            current.splitlines(), f["content"].splitlines(),
            fromfile=f["path"], tofile=f["path"], lineterm="",
        ))
        files.append({"path": f["path"], "content": f["content"], "diff": diff})

    return {
        "type": "github_pr",
        "repo": repo,
        "allowed_base_branches": allowed,
        "default_branch": base_branch,
        "files": files,
        "pr_title": _pr_title(pm),
        "pr_body": _pr_body(pm),
    }
