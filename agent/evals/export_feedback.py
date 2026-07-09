"""Exports operator feedback on wrong/partially-wrong postmortems, so it
doesn't just sit in the reviewed flag doing nothing -- turning it into new
eval fixtures or prompt fixes is a manual step for a human to do afterward,
not an automatic retraining pipeline (there's no fine-tuning here, this app
is BYOK against foundation-model APIs).

Usage: python -m evals.export_feedback <owner_user_id>
(mirrors rag.ingest's `make ingest USER_ID=1` pattern -- see Makefile)
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import investigations

OUT_DIR = Path(__file__).resolve().parent / "feedback"


def export(owner_user_id: int) -> Path:
    items = investigations.list_with_feedback(owner_user_id)
    records = [
        {
            "investigation_id": item["id"],
            "alert_text": item["alert_text"],
            "postmortem": (item.get("result") or {}).get("postmortem"),
            "feedback_rating": item["feedback_rating"],
            "feedback_notes": item["feedback_notes"],
            "created_at": item["created_at"].isoformat() if item["created_at"] else None,
        }
        for item in items
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"feedback_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(records, indent=2))
    return out_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m evals.export_feedback <owner_user_id>", file=sys.stderr)
        sys.exit(1)

    path = export(int(sys.argv[1]))
    count = len(json.loads(path.read_text()))
    print(f"Exported {count} rated investigation(s) to {path}")
