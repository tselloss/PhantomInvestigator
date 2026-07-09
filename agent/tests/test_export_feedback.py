import json
from datetime import datetime, timezone

import investigations
from evals import export_feedback


def test_export_writes_rated_investigations_to_json(tmp_path, monkeypatch):
    monkeypatch.setattr(export_feedback, "OUT_DIR", tmp_path)
    items = [
        {
            "id": 3, "alert_text": "checkout down",
            "result": {"postmortem": {"title": "Pool exhaustion", "confidence": 0.8}},
            "feedback_rating": "incorrect", "feedback_notes": "wrong root cause",
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        },
    ]
    monkeypatch.setattr(investigations, "list_with_feedback", lambda owner_user_id: items)

    out_path = export_feedback.export(1)

    assert out_path.parent == tmp_path
    records = json.loads(out_path.read_text())
    assert records == [{
        "investigation_id": 3,
        "alert_text": "checkout down",
        "postmortem": {"title": "Pool exhaustion", "confidence": 0.8},
        "feedback_rating": "incorrect",
        "feedback_notes": "wrong root cause",
        "created_at": "2026-01-01T00:00:00+00:00",
    }]


def test_export_handles_no_rated_investigations(tmp_path, monkeypatch):
    monkeypatch.setattr(export_feedback, "OUT_DIR", tmp_path)
    monkeypatch.setattr(investigations, "list_with_feedback", lambda owner_user_id: [])

    out_path = export_feedback.export(1)

    assert json.loads(out_path.read_text()) == []
