from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from truthlens_api.main import app
from truthlens_data_pipeline.paths import read_json, read_jsonl
from truthlens_trainer.pipeline import run_pipeline


client = TestClient(app)


def test_annotation_review_flow_persists_adjudications(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    run_pipeline(run_id="integration-review-run", build_id="integration-review-build")

    latest_response = client.get("/annotation-batch/latest")

    assert latest_response.status_code == 200
    batch_payload = latest_response.json()
    review_item = batch_payload["review_queue"][0]

    save_response = client.post(
        "/annotation-batch/adjudications",
        json={
            "run_id": batch_payload["run_id"],
            "reviewer": "integration-bot",
            "decisions": [
                {
                    "item_id": review_item["item_id"],
                    "queue_name": "review",
                    "resolution": "confirmed-risk",
                    "content_class": review_item.get("content_class", "unknown"),
                    "label_overrides": {
                        "clickbait": True,
                        "deceptive_divergence": True,
                    },
                    "bias_review_required": True,
                    "note": "Escalated because the packaging remains misleading in context.",
                }
            ],
        },
    )

    assert save_response.status_code == 200
    save_payload = save_response.json()
    adjudication_path = tmp_path / save_payload["adjudication_path"]
    gold_path = tmp_path / save_payload["gold_path"]
    assert adjudication_path.exists()
    assert gold_path.exists()

    adjudication_payload = read_json(adjudication_path)
    gold_rows = read_jsonl(gold_path)
    assert adjudication_payload["summary"]["saved_count"] == 1
    assert adjudication_payload["adjudications"][0]["reviewer"] == "integration-bot"
    assert gold_rows[0]["labels"]["clickbait"] is True
    assert gold_rows[0]["labels"]["deceptive_divergence"] is True

    refreshed_response = client.get("/annotation-batch/latest")

    assert refreshed_response.status_code == 200
    refreshed_payload = refreshed_response.json()
    refreshed_item = next(
        item for item in refreshed_payload["review_queue"] if item["item_id"] == review_item["item_id"]
    )
    assert refreshed_payload["adjudication_summary"]["saved_count"] == 1
    assert refreshed_item["adjudication"]["resolution"] == "confirmed-risk"
