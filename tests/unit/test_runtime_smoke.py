from pathlib import Path

from truthlens_trainer.smoke import run_smoke


def test_runtime_smoke_runs_end_to_end(tmp_path: Path) -> None:
    summary = run_smoke(tmp_path / "smoke-root")

    assert summary["endpoints"]["health"]["status"] == "ok"
    assert summary["endpoints"]["ready"]["ready"] is True
    assert summary["endpoints"]["batch_score_count"] == 1
    assert summary["endpoints"]["feedback_status"] == "accepted"
    assert summary["endpoints"]["metrics_contains_score_total"] is True
    assert Path(summary["artifacts"]["model_bundle"]).exists()
    assert Path(summary["artifacts"]["simulation_report"]).exists()
    assert Path(summary["artifacts"]["drift_report"]).exists()
    assert Path(summary["report_path"]).exists()
