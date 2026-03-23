from pathlib import Path

import pytest

from truthlens_data_pipeline.paths import read_json, read_jsonl, repo_root
from truthlens_model_serving import describe_model
from truthlens_trainer.pipeline import run_pipeline
from truthlens_trainer.simulate import main as simulate_main
from truthlens_trainer.train import main as train_main


def test_pipeline_creates_build_outputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    result = run_pipeline(run_id="discovery-test-latest", build_id="build-test-latest")

    assert result["build_manifest"]["counts"]["train"] > 0
    assert result["build_manifest"]["counts"]["validation"] > 0
    assert result["build_manifest"]["counts"]["test"] > 0
    assert result["audit_report"]["training_gate_passed"] is True
    normalized_rows = read_jsonl(repo_root() / "datasets/interim/normalized/discovery-test-latest.jsonl")
    latest_annotation_batch = read_json(repo_root() / "datasets/labels/annotation_batches/latest.json")
    assert all("transcript_mismatch_score" in row["features"] for row in normalized_rows)
    assert all("repeat_template_rate" in row["history"]["channel_history_features"] for row in normalized_rows)
    assert latest_annotation_batch["run_id"] == "discovery-test-latest"
    assert "queue_reason" in latest_annotation_batch["review_queue"][0]
    assert "channel_name" in latest_annotation_batch["review_queue"][0]


def test_training_and_simulation_generate_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    run_pipeline(run_id="discovery-test-latest", build_id="build-test-latest")
    train_main()
    simulate_main()

    model_info = describe_model()
    model_dir = repo_root() / "artifacts/trained_models/latest"
    eval_report = read_json(repo_root() / "artifacts/eval_runs/build-test-latest.json")
    simulation_report = read_json(repo_root() / "artifacts/eval_runs/build-test-latest-simulation.json")
    drift_report = read_json(repo_root() / "artifacts/drift_reports/build-test-latest.json")

    assert model_info["mode"] == "trained"
    assert model_info["artifact_status"] == "compatible"
    assert "runtime_library_versions" in model_info
    assert "training_library_versions" in model_info
    assert model_dir.joinpath("model_bundle.pkl").exists()
    assert model_dir.joinpath("model_info.json").exists()
    assert (repo_root() / "artifacts/eval_runs").exists()
    assert (repo_root() / "artifacts/drift_reports").exists()
    assert "calibration_error" in model_info
    assert "per_head_metrics" in model_info
    assert "confusion_matrix" in model_info
    assert "validation_calibration_error" in eval_report
    assert "calibration_error" in eval_report
    assert "policy" in simulation_report
    assert "bellman_state_values" in simulation_report
    assert "replay_summary" in simulation_report
    assert simulation_report["replay_summary"]["steps"] > 0
    assert "retraining_recommended" in drift_report
    assert "label_distribution_shift" in drift_report
