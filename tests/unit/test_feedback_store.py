from pathlib import Path

import pytest

from truthlens_data_pipeline.paths import repo_root
from truthlens_model_serving import (
    append_browser_observation,
    append_feedback_event,
    append_score_event,
    load_browser_observations,
    load_feedback_events,
    summarize_browser_observations,
    summarize_feedback_events,
)


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


def test_browser_observations_are_persisted_to_sqlite_and_jsonl(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    append_browser_observation(
        {
            "observation_id": "obs-1",
            "item_id": "item-1",
            "item_hash": "sig-1",
            "title_snapshot": "Breaking thumbnail packaging",
            "channel_name": "Signal Watch",
            "channel_url": "https://www.youtube.com/@signalwatch",
            "link_url": "https://www.youtube.com/watch?v=item-1",
            "thumbnail_ref": "https://i.ytimg.com/vi/item-1/hqdefault.jpg",
            "description_snapshot": "Description",
            "transcript_excerpt": "Transcript",
            "metadata": {"duration_seconds": 120},
            "runtime_context": {
                "surface": "extension-feed",
                "review_requested": False,
                "source_provenance": "/",
            },
            "distilled_features": {
                "card_index": 0,
                "link_kind": "watch",
                "has_thumbnail": True,
                "has_description_snapshot": True,
                "has_transcript_excerpt": True,
                "title_token_count": 3,
                "description_token_count": 1,
                "channel_known": True,
                "duration_seconds": 120,
            },
            "score_snapshot": {
                "risk_score": 0.74,
                "calibrated_score": 0.71,
                "uncertainty": 0.21,
                "recommended_action": "ask-report",
                "content_class": "news",
                "content_class_confidence": 0.64,
                "explanation_id": "exp-1",
            },
            "provenance": {
                "observed_at": "2026-04-06T10:00:00Z",
                "collector": "extension-dom",
                "collector_version": "extension-runtime",
                "session_id": "session-1",
                "page_url": "https://www.youtube.com/",
                "source_path": "/",
            },
        }
    )

    db_path = repo_root() / "artifacts" / "reports" / "feedback_events.sqlite3"
    jsonl_path = repo_root() / "artifacts" / "reports" / "browser_observations.jsonl"
    rows = load_browser_observations()
    summary = summarize_browser_observations(rows)

    assert db_path.exists()
    assert jsonl_path.exists()
    assert len(rows) == 1
    assert rows[0]["observation_id"] == "obs-1"
    assert summary["total_observations"] == 1
    assert summary["surface_counts"]["extension-feed"] == 1


def test_feedback_summary_computes_channel_trust_score_from_scored_items(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    for index in range(10):
        append_score_event(
            {
                "item_id": f"scored-{index}",
                "channel_name": "Signal Watch",
                "model_version": "test-model",
                "policy_version": "test-policy",
                "recommended_action": "ask-report" if index < 6 else "none",
                "risk_score": 0.82 if index < 6 else 0.18,
                "confidence": 0.76,
                "uncertainty": 0.24,
                "explanation_id": f"exp-score-{index}",
                "timestamp": f"2026-03-23T10:{index:02d}:00Z",
            }
        )

    for index in range(6):
        append_feedback_event(
            {
                "item_id": f"scored-{index}",
                "item_hash": None,
                "channel_name": "Signal Watch",
                "model_version": "test-model",
                "policy_version": "test-policy",
                "action_shown": "ask-report",
                "user_action": "confirm-report",
                "explanation_id": f"exp-feedback-{index}",
                "before_score": 0.82,
                "after_score": 0.82,
                "timestamp": f"2026-03-23T11:{index:02d}:00Z",
                "manual_report": {
                    "target_url": f"https://www.youtube.com/watch?v=scored-{index}",
                    "title_snapshot": "Signal Watch upload",
                    "issues": [
                        {
                            "issue_type": "title",
                            "comment": "The title appears misleading relative to the available context.",
                        }
                    ],
                    "requested_outcome": "moderate",
                    "optimize_requested": False,
                    "optimize_applied": False,
                    "report_text": "Please moderate the misleading metadata on this upload.",
                },
            }
        )

    rows = load_feedback_events()
    summary = summarize_feedback_events(rows)
    channel = summary["channel_profiles"]["signal watch"]

    assert channel["scored_item_count"] == 10
    assert channel["reported_item_count"] == 6
    assert channel["moderate_request_count"] == 6
    assert channel["trust_score"] < 5.0


def test_feedback_summary_rewards_confirmed_transparent_feedback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    for index in range(4):
        append_score_event(
            {
                "item_id": f"transparent-{index}",
                "channel_name": "Context First Media",
                "model_version": "test-model",
                "policy_version": "test-policy",
                "recommended_action": "none",
                "risk_score": 0.16,
                "confidence": 0.84,
                "uncertainty": 0.16,
                "explanation_id": None,
                "timestamp": f"2026-03-23T12:{index:02d}:00Z",
            }
        )
        append_feedback_event(
            {
                "item_id": f"transparent-{index}",
                "item_hash": None,
                "channel_name": "Context First Media",
                "model_version": "test-model",
                "policy_version": "test-policy",
                "action_shown": "none",
                "user_action": "confirm-transparent",
                "explanation_id": None,
                "before_score": 0.16,
                "after_score": 0.12,
                "timestamp": f"2026-03-23T12:{index:02d}:30Z",
                "manual_report": {
                    "workflow_mode": "verify-transparent",
                    "target_url": f"https://www.youtube.com/watch?v=transparent-{index}",
                    "title_snapshot": "Transparent upload",
                    "issues": [
                        {
                            "issue_type": "title",
                            "comment": "The title appears consistent with the visible context.",
                        }
                    ],
                    "requested_outcome": "moderate",
                    "optimize_requested": False,
                    "optimize_applied": False,
                    "report_text": "Transparency verification: the visible packaging appears consistent.",
                },
            }
        )

    summary = summarize_feedback_events(load_feedback_events())
    channel = summary["channel_profiles"]["context first media"]

    assert channel["transparent_count"] == 4
    assert channel["trust_score"] > 6.0


def test_feedback_summary_ignores_unknown_channel_profiles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    append_score_event(
        {
            "item_id": "unknown-score-1",
            "channel_name": "Unknown channel",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "recommended_action": "badge",
            "risk_score": 0.42,
            "confidence": 0.61,
            "uncertainty": 0.39,
            "explanation_id": None,
            "timestamp": "2026-03-23T13:00:00Z",
        }
    )
    append_feedback_event(
        {
            "item_id": "unknown-feedback-1",
            "item_hash": None,
            "channel_name": "Unknown channel",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "action_shown": "badge",
            "user_action": "confirm-report",
            "explanation_id": None,
            "before_score": 0.42,
            "after_score": 0.42,
            "timestamp": "2026-03-23T13:01:00Z",
        }
    )

    summary = summarize_feedback_events(load_feedback_events())

    assert "unknown channel" not in summary["channel_profiles"]
