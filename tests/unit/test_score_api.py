from fastapi.testclient import TestClient

from truthlens_api.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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
