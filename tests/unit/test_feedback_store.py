from pathlib import Path

import pytest

from truthlens_data_pipeline.paths import repo_root
from truthlens_model_serving import append_feedback_event, load_feedback_events, summarize_feedback_events


def test_feedback_events_are_persisted_to_sqlite_and_jsonl(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    append_feedback_event(
        {
            "item_id": "item-1",
            "item_hash": None,
            "channel_name": "Signal Watch",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "action_shown": "badge",
            "user_action": "report",
            "explanation_id": "exp-1",
            "before_score": 0.61,
            "after_score": 0.81,
            "timestamp": "2026-03-23T10:00:00Z",
        }
    )

    db_path = repo_root() / "artifacts" / "reports" / "feedback_events.sqlite3"
    jsonl_path = repo_root() / "artifacts" / "reports" / "feedback_events.jsonl"
    rows = load_feedback_events()
    summary = summarize_feedback_events(rows)

    assert db_path.exists()
    assert jsonl_path.exists()
    assert len(rows) == 1
    assert rows[0]["explanation_id"] == "exp-1"
    assert summary["total_events"] == 1
