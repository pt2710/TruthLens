from pathlib import Path

import pytest

from truthlens_data_pipeline.paths import read_jsonl, repo_root
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
    assert all("transcript_mismatch_score" in row["features"] for row in normalized_rows)
    assert all("repeat_template_rate" in row["history"]["channel_history_features"] for row in normalized_rows)


def test_training_and_simulation_generate_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    run_pipeline(run_id="discovery-test-latest", build_id="build-test-latest")
    train_main()
    simulate_main()

    model_info = describe_model()
    model_dir = Path("artifacts/trained_models/latest")

    assert model_info["mode"] == "trained"
    assert model_dir.joinpath("model_bundle.pkl").exists()
    assert model_dir.joinpath("model_info.json").exists()
    assert Path("artifacts/eval_runs").exists()
    assert Path("artifacts/drift_reports").exists()
