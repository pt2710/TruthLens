from fastapi.testclient import TestClient
import pytest
from pathlib import Path

from truthlens_api.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_info_endpoints() -> None:
    model_response = client.get("/model-info")
    policy_response = client.get("/policy-info")

    assert model_response.status_code == 200
    assert "mode" in model_response.json()

    assert policy_response.status_code == 200
    assert "effective_thresholds" in policy_response.json()


def test_score_item_contract() -> None:
    response = client.post(
        "/score-item",
        json={
            "item_id": "item-1",
            "title": "Breaking aliens confirmed",
            "thumbnail_ref": None,
            "metadata": {},
            "channel": {
                "channel_name": "TruthLens Test",
                "prior_flags": 1,
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {
        "risk_score",
        "confidence",
        "uncertainty",
        "recommended_action",
        "reasons",
        "explanation_id",
        "explanation_summary",
        "evidence",
    }
    if payload["recommended_action"] != "none":
        assert payload["reasons"]
        assert payload["explanation_id"]
        assert payload["explanation_summary"]
        assert payload["evidence"]


def test_feedback_endpoint_accepts_event() -> None:
    response = client.post(
        "/feedback",
        json={
            "item_id": "item-1",
            "item_hash": None,
            "channel_name": "TruthLens Test",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "action_shown": "badge",
            "user_action": "not-misleading",
            "explanation_id": None,
            "before_score": 0.61,
            "after_score": 0.32,
            "timestamp": "2026-03-23T10:00:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_feedback_summary_endpoint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    client.post(
        "/feedback",
        json={
            "item_id": "item-1",
            "item_hash": None,
            "channel_name": "Signal Watch",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "action_shown": "badge",
            "user_action": "report",
            "explanation_id": None,
            "before_score": 0.61,
            "after_score": 0.81,
            "timestamp": "2026-03-23T10:00:00Z",
        },
    )
    client.post(
        "/feedback",
        json={
            "item_id": "item-2",
            "item_hash": None,
            "channel_name": "Signal Watch",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "action_shown": "blur",
            "user_action": "not-misleading",
            "explanation_id": None,
            "before_score": 0.55,
            "after_score": 0.21,
            "timestamp": "2026-03-23T10:05:00Z",
        },
    )

    response = client.get("/feedback-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_events"] == 2
    assert payload["action_counts"]["report"] == 1
    assert payload["action_counts"]["not-misleading"] == 1
    assert payload["top_channels"][0]["channel_name"] == "Signal Watch"


def test_muted_channel_forces_hide() -> None:
    response = client.post(
        "/score-item",
        json={
            "item_id": "item-muted",
            "title": "Calm telescope update",
            "thumbnail_ref": None,
            "transcript_excerpt": "A calm telescope update with cited methods and no urgent claim.",
            "metadata": {},
            "channel": {
                "channel_name": "Muted Channel",
                "prior_flags": 0,
                "channel_history_features": {},
            },
            "user_context": {
                "strict_mode": False,
                "muted_channels": ["Muted Channel"],
                "prior_corrections": 0,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommended_action"] == "hide"
    assert any("locally muted" in reason.lower() for reason in payload["reasons"])
    assert payload["explanation_id"]
    assert payload["explanation_summary"]


def test_transcript_mismatch_surfaces_reasoning() -> None:
    response = client.post(
        "/score-item",
        json={
            "item_id": "item-mismatch",
            "title": "Breaking aliens confirmed over Europe",
            "thumbnail_ref": None,
            "transcript_excerpt": "This segment calmly reviews telescope maintenance and launch cadence.",
            "metadata": {
                "view_count": 12000,
                "like_count": 900,
            },
            "channel": {
                "channel_name": "Signal Watch Europe",
                "prior_flags": 3,
                "channel_history_features": {
                    "channel_risk_mean": 0.72,
                    "repeat_template_rate": 0.61,
                    "recent_upload_velocity": 0.58,
                    "engagement_anomaly": 1.22,
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(
        "transcript" in reason.lower() or "framing mismatch" in reason.lower()
        for reason in payload["reasons"]
    )
    assert any(entry["kind"] == "transcript" for entry in payload["evidence"])
