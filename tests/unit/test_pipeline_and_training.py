from pathlib import Path

from truthlens_model_serving import describe_model
from truthlens_trainer.pipeline import run_pipeline
from truthlens_trainer.simulate import main as simulate_main
from truthlens_trainer.train import main as train_main


def test_pipeline_creates_build_outputs() -> None:
    result = run_pipeline()

    assert result["build_manifest"]["counts"]["train"] > 0
    assert result["build_manifest"]["counts"]["validation"] > 0
    assert result["build_manifest"]["counts"]["test"] > 0
    assert result["audit_report"]["training_gate_passed"] is True


def test_training_and_simulation_generate_artifacts() -> None:
    run_pipeline()
    train_main()
    simulate_main()

    model_info = describe_model()
    model_dir = Path("artifacts/trained_models/latest")

    assert model_info["mode"] == "trained"
    assert model_dir.joinpath("model_bundle.pkl").exists()
    assert model_dir.joinpath("model_info.json").exists()
    assert Path("artifacts/eval_runs").exists()
    assert Path("artifacts/drift_reports").exists()
