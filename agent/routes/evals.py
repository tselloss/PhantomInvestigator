"""Trigger/inspect the demo-app eval harness from the operator UI. Runs the
same harness as `make evals`, just reachable from the Demo & testing page."""
import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks

router = APIRouter(prefix="/evals")

RESULTS_DIR = Path(__file__).resolve().parent.parent / "evals" / "results"


def _run_evals_background():
    from evals.run import main as run_evals_main

    run_evals_main()


@router.post("/run")
def trigger_evals(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_evals_background)
    return {"started": True}


@router.get("/latest")
def latest_eval():
    if not RESULTS_DIR.exists():
        return {"available": False}
    files = sorted(RESULTS_DIR.glob("eval_*.json"))
    if not files:
        return {"available": False}

    latest = files[-1]
    records = json.loads(latest.read_text())

    summary = {}
    for record in records:
        fault = record.get("fault")
        entry = summary.setdefault(fault, {"runs": 0, "category_matches": 0})
        entry["runs"] += 1
        if record.get("category_match"):
            entry["category_matches"] += 1

    return {"available": True, "filename": latest.name, "summary": summary}
