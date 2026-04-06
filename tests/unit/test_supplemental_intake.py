from __future__ import annotations

from pathlib import Path

import pytest

from truthlens_data_pipeline.paths import write_json
from truthlens_dataset_governance import build_supplemental_candidate_batch
from truthlens_model_serving import append_browser_observation, append_feedback_event


def test_supplemental_candidate_batch_derives_split_safe_candidates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    write_json(
        tmp_path / "datasets/labels/annotation_batches/latest.json",
        {
            "run_id": "review-run",
            "generated_at": "2026-04-06T10:00:00Z",
            "review_queue": [],
            "hard_negative_queue": [],
            "disagreement_queue": [],
            "annotator_notes_fields": [],
            "source_batch_path": "datasets/labels/annotation_batches/review-run.json",
        },
    )
    write_json(
        tmp_path / "datasets/manifests/builds/latest.json",
        {
            "build_id": "build-test",
            "run_id": "review-run",
        },
    )
    append_browser_observation(
        {
            "observation_id": "obs-1",
            "item_id": "watch-1",
            "item_hash": "sig-1",
            "title_snapshot": "Breaking update on transfer talks",
            "channel_name": "Signal Watch",
            "channel_url": "https://www.youtube.com/@signalwatch",
            "link_url": "https://www.youtube.com/watch?v=watch-1",
            "thumbnail_ref": "https://i.ytimg.com/vi/watch-1/hqdefault.jpg",
            "description_snapshot": "Latest transfer discussion",
            "transcript_excerpt": "Latest transfer discussion",
            "metadata": {"duration_seconds": 90},
            "runtime_context": {
                "surface": "extension-feed",
                "review_requested": False,
                "source_provenance": "/feed/subscriptions",
            },
            "distilled_features": {
                "card_index": 1,
                "link_kind": "watch",
                "has_thumbnail": True,
                "has_description_snapshot": True,
                "has_transcript_excerpt": True,
                "title_token_count": 5,
                "description_token_count": 3,
                "channel_known": True,
                "duration_seconds": 90,
            },
            "score_snapshot": {
                "risk_score": 0.72,
                "calibrated_score": 0.69,
                "uncertainty": 0.28,
                "recommended_action": "ask-report",
                "content_class": "news",
                "content_class_confidence": 0.66,
                "explanation_id": "exp-1",
            },
            "provenance": {
                "observed_at": "2026-04-06T10:01:00Z",
                "collector": "extension-dom",
                "collector_version": "extension-runtime",
                "session_id": "session-1",
                "page_url": "https://www.youtube.com/feed/subscriptions",
                "source_path": "/feed/subscriptions",
            },
        }
    )
    append_feedback_event(
        {
            "feedback_id": "feedback-1",
            "item_id": "watch-1",
            "item_hash": None,
            "observation_id": "obs-1",
            "channel_name": "Signal Watch",
            "model_version": "extension-runtime",
            "policy_version": "adaptive-threshold-v1",
            "action_shown": "ask-report",
            "user_action": "confirm-report",
            "explanation_id": "exp-1",
            "before_score": 0.72,
            "after_score": 0.72,
            "timestamp": "2026-04-06T10:02:00Z",
            "runtime_context": {
                "surface": "extension-feed",
                "review_requested": False,
                "source_provenance": "/feed/subscriptions",
            },
            "manual_report": {
                "workflow_mode": "report",
                "target_url": "https://www.youtube.com/watch?v=watch-1",
                "title_snapshot": "Breaking update on transfer talks",
                "issues": [
                    {
                        "issue_type": "title",
                        "comment": "The packaging overstates the factual certainty.",
                    }
                ],
                "requested_outcome": "moderate",
                "optimize_requested": False,
                "optimize_applied": False,
                "report_text": "Please review the misleading packaging.",
            },
        }
    )

    payload = build_supplemental_candidate_batch("review-run")

    assert payload["summary"]["candidate_count"] == 1
    candidate = payload["supplemental_candidates"]["review_queue"][0]
    assert candidate["origin"] == "supplemental-intake"
    assert candidate["split_safety"]["eligible_for_training"] is False
    assert candidate["split_safety"]["split_status"] == "blocked-until-ingestion"
    assert candidate["feedback_summary"]["risk_event_count"] == 1
    assert "browser-observation" in candidate["provenance"]["candidate_sources"]
