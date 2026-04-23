from pathlib import Path

import pytest

from truthlens_data_pipeline.paths import read_json, read_jsonl
from truthlens_dataset_governance import (
    ingest_operator_feedback_records,
    load_latest_operator_feedback_manifest,
    materialize_operator_feedback_artifacts,
)
from truthlens_model_serving import append_browser_observation, append_feedback_event


def _append_operator_observation(item_id: str) -> None:
    append_browser_observation(
        {
            "observation_id": "obs-operator-1",
            "item_id": item_id,
            "item_hash": "sig-operator-1",
            "title_snapshot": "Breaking aliens confirmed before the media deletes this",
            "channel_name": "AI Revolution",
            "channel_url": "https://www.youtube.com/@airevolution",
            "link_url": item_id,
            "thumbnail_ref": "https://i.ytimg.com/vi/operator-1/hqdefault.jpg",
            "description_snapshot": "The packaging overclaims certainty for a speculative topic.",
            "transcript_excerpt": "The host speculates heavily but frames the upload as confirmed truth.",
            "metadata": {"duration_seconds": 540, "view_count": 12000, "like_count": 640},
            "runtime_context": {
                "surface": "extension-watch",
                "review_requested": True,
                "source_provenance": "/watch",
            },
            "distilled_features": {
                "card_index": 0,
                "link_kind": "watch",
                "has_thumbnail": True,
                "has_description_snapshot": True,
                "has_transcript_excerpt": True,
                "title_token_count": 8,
                "description_token_count": 7,
                "channel_known": True,
                "duration_seconds": 540,
            },
            "score_snapshot": {
                "risk_score": 0.82,
                "calibrated_score": 0.79,
                "uncertainty": 0.14,
                "recommended_action": "ask-report",
                "content_class": "news",
                "content_class_confidence": 0.78,
                "explanation_id": "exp-operator-1",
            },
            "provenance": {
                "observed_at": "2026-04-23T10:00:00Z",
                "collector": "extension-dom",
                "collector_version": "extension-runtime",
                "session_id": "session-operator-1",
                "page_url": item_id,
                "source_path": "/watch",
            },
        }
    )


def _append_operator_feedback(item_id: str) -> None:
    append_feedback_event(
        {
            "feedback_id": "feedback-operator-1",
            "item_id": item_id,
            "item_hash": None,
            "observation_id": "obs-operator-1",
            "channel_name": "AI Revolution",
            "model_version": "extension-runtime",
            "policy_version": "adaptive-threshold-v1",
            "action_shown": "ask-report",
            "user_action": "confirm-report",
            "explanation_id": "exp-operator-1",
            "before_score": 0.82,
            "after_score": 0.82,
            "timestamp": "2026-04-23T10:02:00Z",
            "runtime_context": {
                "surface": "extension-watch",
                "review_requested": True,
                "source_provenance": "/watch",
            },
            "manual_report": {
                "workflow_mode": "report",
                "target_url": item_id,
                "title_snapshot": "Breaking aliens confirmed before the media deletes this",
                "selected_tags": ["Clickbait"],
                "issues": [
                    {
                        "issue_type": "thumbnail",
                        "comment": "The thumbnail frames speculation as established fact.",
                    },
                    {
                        "issue_type": "title",
                        "comment": "The title makes a false certainty claim.",
                    },
                ],
                "requested_outcome": "moderate",
                "optimize_requested": False,
                "optimize_applied": False,
                "report_text": "Please review the misleading packaging claims.",
            },
        }
    )


def test_operator_feedback_pipeline_backfills_legacy_creator_feedback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("TRUTHLENS_OPERATOR_MODE", "creator-operator")
    monkeypatch.setenv("TRUTHLENS_OPERATOR_ID", "creator-1")
    item_id = "https://www.youtube.com/watch?v=operator-1"
    _append_operator_observation(item_id)
    _append_operator_feedback(item_id)

    adjudication_payload = materialize_operator_feedback_artifacts("operator-run")
    latest_manifest = load_latest_operator_feedback_manifest()
    records, ingestion_manifest = ingest_operator_feedback_records(
        build_id="build-operator-test",
        run_id="discovery-operator-test",
    )

    assert adjudication_payload["summary"]["candidate_count"] == 1
    assert adjudication_payload["summary"]["confirmed_risk_count"] == 1
    assert latest_manifest is not None
    assert latest_manifest["selected_feedback_ids"] == ["feedback-operator-1"]
    assert latest_manifest["events"][0]["selection_reason"] == "curated-backfill"
    assert len(records) == 1
    assert ingestion_manifest["ingested_count"] == 1
    assert records[0]["provenance"]["origin"] == "supplemental-adjudicated"
    assert records[0]["labels"]["clickbait"] is True
    assert records[0]["labels"]["misleading_thumbnail"] is True
    assert records[0]["labels"]["misleading_title"] is True
    assert read_jsonl(tmp_path / "datasets/labels/operator_supplemental_gold/latest.jsonl")
    assert read_json(tmp_path / "datasets/manifests/operator_feedback/latest.json")["selected_count"] == 1


def test_operator_feedback_pipeline_does_not_promote_local_user_feedback_without_operator_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    monkeypatch.delenv("TRUTHLENS_OPERATOR_MODE", raising=False)
    monkeypatch.delenv("TRUTHLENS_OPERATOR_ID", raising=False)
    item_id = "https://www.youtube.com/watch?v=operator-1"
    _append_operator_observation(item_id)
    _append_operator_feedback(item_id)

    adjudication_payload = materialize_operator_feedback_artifacts("operator-run")
    latest_manifest = load_latest_operator_feedback_manifest()

    assert adjudication_payload["summary"]["candidate_count"] == 0
    assert latest_manifest is not None
    assert latest_manifest["selected_count"] == 0
