from fastapi.testclient import TestClient

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
    }
    if payload["recommended_action"] != "none":
        assert payload["reasons"]


def test_feedback_endpoint_accepts_event() -> None:
    response = client.post(
        "/feedback",
        json={
            "item_id": "item-1",
            "item_hash": None,
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
