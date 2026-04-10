from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from truthlens_api.main import app
from truthlens_data_pipeline.paths import read_json, read_jsonl
from truthlens_trainer.pipeline import run_pipeline


client = TestClient(app)


def test_browser_observation_and_feedback_become_supplemental_adjudication(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    run_pipeline(run_id="integration-supplemental-run", build_id="integration-supplemental-build")

    observation_response = client.post(
        "/browser-observation",
        json={
            "observation_id": "obs-supp-1",
            "item_id": "watch-supp-1",
            "item_hash": "sig-supp-1",
            "title_snapshot": "Breaking update on transfer talks",
            "channel_name": "Signal Watch",
            "channel_url": "https://www.youtube.com/@signalwatch",
            "link_url": "https://www.youtube.com/watch?v=watch-supp-1",
            "thumbnail_ref": "https://i.ytimg.com/vi/watch-supp-1/hqdefault.jpg",
            "description_snapshot": "Latest transfer discussion",
            "transcript_excerpt": "Latest transfer discussion",
            "metadata": {"duration_seconds": 90},
            "runtime_context": {
                "surface": "extension-feed",
                "review_requested": False,
                "source_provenance": "/feed/subscriptions",
            },
            "distilled_features": {
                "card_index": 2,
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
                "risk_score": 0.74,
                "calibrated_score": 0.71,
                "uncertainty": 0.26,
                "recommended_action": "ask-report",
                "content_class": "news",
                "content_class_confidence": 0.67,
                "explanation_id": "exp-supp-1",
            },
            "provenance": {
                "observed_at": "2026-04-06T10:01:00Z",
                "collector": "extension-dom",
                "collector_version": "extension-runtime",
                "session_id": "session-1",
                "page_url": "https://www.youtube.com/feed/subscriptions",
                "source_path": "/feed/subscriptions",
            },
        },
    )
    assert observation_response.status_code == 200

    feedback_response = client.post(
        "/feedback",
        json={
            "feedback_id": "feedback-supp-1",
            "item_id": "watch-supp-1",
            "item_hash": None,
            "observation_id": "obs-supp-1",
            "channel_name": "Signal Watch",
            "model_version": "extension-runtime",
            "policy_version": "adaptive-threshold-v1",
            "action_shown": "ask-report",
            "user_action": "confirm-report",
            "explanation_id": "exp-supp-1",
            "before_score": 0.74,
            "after_score": 0.74,
            "timestamp": "2026-04-06T10:02:00Z",
            "runtime_context": {
                "surface": "extension-feed",
                "review_requested": False,
                "source_provenance": "/feed/subscriptions",
            },
            "manual_report": {
                "workflow_mode": "report",
                "target_url": "https://www.youtube.com/watch?v=watch-supp-1",
                "title_snapshot": "Breaking update on transfer talks",
                "selected_tags": ["Clickbait"],
                "collection_scope": {
                    "scope_type": "mix",
                    "scope_id": "RD-watch-supp-1",
                    "collection_title": "Signal Watch Mix",
                    "source_item_id": "watch-supp-1",
                    "source_link_url": "https://www.youtube.com/watch?v=watch-supp-1&list=RD-watch-supp-1",
                    "trigger_origin": "collection-preview",
                    "apply_to_all": True,
                    "resolved_member_count": 2,
                    "unresolved_member_count": 0,
                    "member_items": [
                        {
                            "item_id": "watch-supp-1",
                            "title_snapshot": "Breaking update on transfer talks",
                            "channel_name": "Signal Watch",
                            "link_url": "https://www.youtube.com/watch?v=watch-supp-1&list=RD-watch-supp-1",
                            "thumbnail_ref": "https://i.ytimg.com/vi/watch-supp-1/hqdefault.jpg",
                            "resolved": True,
                        }
                    ],
                },
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
        },
    )
    assert feedback_response.status_code == 200

    latest_response = client.get("/annotation-batch/latest")
    assert latest_response.status_code == 200
    batch_payload = latest_response.json()
    supplemental_item = next(
        item for item in batch_payload["review_queue"] if item["item_id"] == "watch-supp-1"
    )
    assert supplemental_item["origin"] == "supplemental-intake"
    assert supplemental_item["selected_tags"] == ["Clickbait"]
    assert supplemental_item["collection_scope"]["scope_type"] == "mix"
    assert supplemental_item["split_safety"]["eligible_for_training"] is False
    assert batch_payload["supplemental_summary"]["candidate_count"] >= 1

    save_response = client.post(
        "/annotation-batch/adjudications",
        json={
            "run_id": batch_payload["run_id"],
            "reviewer": "integration-bot",
            "decisions": [
                {
                    "item_id": "watch-supp-1",
                    "queue_name": "review",
                    "resolution": "confirmed-risk",
                    "content_class": "news",
                    "label_overrides": {
                        "clickbait": True,
                        "deceptive_divergence": True,
                    },
                    "bias_review_required": True,
                    "note": "Supplemental runtime signal confirms misleading factual framing.",
                }
            ],
        },
    )

    assert save_response.status_code == 200
    save_payload = save_response.json()
    supplemental_adjudication_path = tmp_path / save_payload["supplemental_adjudication_path"]
    supplemental_gold_path = tmp_path / save_payload["supplemental_gold_path"]
    assert supplemental_adjudication_path.exists()
    assert supplemental_gold_path.exists()

    adjudication_payload = read_json(supplemental_adjudication_path)
    gold_rows = read_jsonl(supplemental_gold_path)
    assert adjudication_payload["summary"]["saved_count"] == 1
    assert gold_rows[0]["split_safety"]["eligible_for_training"] is False
    assert gold_rows[0]["labels"]["deceptive_divergence"] is True
