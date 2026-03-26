from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

from fastapi.testclient import TestClient

from truthlens_api.main import app
from truthlens_data_pipeline.paths import ensure_dir
from truthlens_trainer.pipeline import run_pipeline
from truthlens_trainer.simulate import main as simulate_main
from truthlens_trainer.train import main as train_main


def _score_payload() -> dict[str, Any]:
    return {
        "item_id": "smoke-item-1",
        "title": "Breaking orbital weather bulletin shocks viewers",
        "thumbnail_ref": None,
        "transcript_excerpt": "This clip reviews launch cadence and observational weather patterns.",
        "metadata": {
            "view_count": 14000,
            "like_count": 950,
        },
        "channel": {
            "channel_name": "Smoke Test Channel",
            "prior_flags": 2,
            "channel_history_features": {
                "channel_risk_mean": 0.58,
                "repeat_template_rate": 0.44,
                "recent_upload_velocity": 0.31,
                "engagement_anomaly": 1.14,
            },
        },
    }


def _run_smoke(smoke_root: Path) -> dict[str, Any]:
    previous_repo_root = os.getenv("TRUTHLENS_REPO_ROOT")
    os.environ["TRUTHLENS_REPO_ROOT"] = str(smoke_root)
    try:
        run_pipeline(run_id="smoke-discovery", build_id="smoke-build")
        train_main()
        simulate_main()

        with TestClient(app) as client:
            health_response = client.get("/health")
            ready_response = client.get("/ready")
            model_response = client.get("/model-info")
            policy_response = client.get("/policy-info")
            score_response = client.post("/score-item", json=_score_payload())
            batch_response = client.post("/batch-score", json={"items": [_score_payload()]})
            feedback_response = client.post(
                "/feedback",
                json={
                    "item_id": "smoke-item-1",
                    "item_hash": None,
                    "channel_name": "Smoke Test Channel",
                    "model_version": model_response.json().get("model_version", "unknown"),
                    "policy_version": policy_response.json().get("policy_version", "unknown"),
                    "action_shown": score_response.json()["recommended_action"],
                    "user_action": "report",
                    "explanation_id": score_response.json().get("explanation_id"),
                    "before_score": score_response.json()["risk_score"],
                    "after_score": min(float(score_response.json()["risk_score"]) + 0.1, 1.0),
                    "timestamp": "2026-03-26T10:00:00Z",
                },
            )
            metrics_response = client.get("/metrics")

        report = {
            "smoke_root": str(smoke_root),
            "build_id": "smoke-build",
            "endpoints": {
                "health": health_response.json(),
                "ready": ready_response.json(),
                "model_info": {
                    "mode": model_response.json().get("mode"),
                    "artifact_status": model_response.json().get("artifact_status"),
                    "model_version": model_response.json().get("model_version"),
                },
                "policy_info": {
                    "policy_version": policy_response.json().get("policy_version"),
                    "thresholds": policy_response.json().get("effective_thresholds"),
                },
                "score_item": {
                    "recommended_action": score_response.json().get("recommended_action"),
                    "risk_score": score_response.json().get("risk_score"),
                    "explanation_id": score_response.json().get("explanation_id"),
                },
                "batch_score_count": len(batch_response.json().get("results", {})),
                "feedback_status": feedback_response.json().get("status"),
                "metrics_contains_score_total": "truthlens_score_events_total" in metrics_response.text,
            },
            "artifacts": {
                "model_bundle": str(smoke_root / "artifacts" / "trained_models" / "latest" / "model_bundle.pkl"),
                "simulation_report": str(smoke_root / "artifacts" / "eval_runs" / "smoke-build-simulation.json"),
                "drift_report": str(smoke_root / "artifacts" / "drift_reports" / "smoke-build.json"),
            },
        }
        report_dir = ensure_dir(smoke_root / "artifacts" / "reports")
        report_path = report_dir / "smoke-summary.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
        report["report_path"] = str(report_path)
        return report
    finally:
        if previous_repo_root is None:
            os.environ.pop("TRUTHLENS_REPO_ROOT", None)
        else:
            os.environ["TRUTHLENS_REPO_ROOT"] = previous_repo_root


def run_smoke(smoke_root: Path | None = None) -> dict[str, Any]:
    if smoke_root is not None:
        return _run_smoke(smoke_root.resolve())
    return _run_smoke(Path(mkdtemp(prefix="truthlens-smoke-")))


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
