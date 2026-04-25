from __future__ import annotations

from pathlib import Path

import pytest

from truthlens_data_pipeline.paths import read_json
from truthlens_evaluation import render_benchmark_bundle


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(__import__("json").dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(__import__("json").dumps(row, sort_keys=True) for row in rows),
        encoding="utf-8",
    )


def _seed_common_artifacts(root: Path) -> None:
    _write_json(
        root / "artifacts/trained_models/latest/model_info.json",
        {
            "build_id": "build-test",
            "model_version": "baseline-v1-build-test",
            "trained_at": "2026-04-06T10:00:00+00:00",
            "head_spec_version": "2026-03-23",
            "metrics": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
            "per_head_metrics": {
                "text": {"metrics": {"precision": 0.4, "recall": 0.9, "f1": 0.55}, "calibration_error": 0.41},
                "vision": {"metrics": {"precision": 0.8, "recall": 1.0, "f1": 0.89}, "calibration_error": 0.21},
            },
        },
    )
    _write_json(
        root / "artifacts/eval_runs/build-test.json",
        {
            "build_id": "build-test",
            "sample_count": 4,
            "metrics": {"precision": 1.0, "recall": 1.0, "f1": 1.0, "roc_auc": 1.0, "pr_auc": 1.0},
            "validation_metrics": {
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "roc_auc": 1.0,
                "pr_auc": 1.0,
            },
            "calibration_error": 0.0,
            "validation_calibration_error": 0.0,
            "confusion_matrix": {"tp": 1, "tn": 3, "fp": 0, "fn": 0},
        },
    )
    _write_json(
        root / "artifacts/eval_runs/build-test-simulation.json",
        {
            "build_id": "build-test",
            "threshold_sweep": [
                {"threshold": 0.2, "f1": 1.0, "intervention_cost": -0.8},
                {"threshold": 0.8, "f1": 1.0, "intervention_cost": -0.8},
            ],
            "recommended_thresholds": {
                "badge_threshold": 0.2,
                "blur_threshold": 0.45,
                "report_prompt_threshold": 0.65,
                "hide_threshold": 0.8,
            },
        },
    )
    _write_json(
        root / "artifacts/drift_reports/build-test.json",
        {
            "reference_count": 12,
            "current_count": 4,
            "title_length_shift": 1.0,
            "sensational_count_shift": -0.5,
            "label_rate_shift": -0.5,
        },
    )
    _write_json(root / "configs/thresholds/default.json", {"badge_threshold": 0.2, "blur_threshold": 0.45, "report_prompt_threshold": 0.65, "hide_threshold": 0.8})
    _write_json(
        root / "configs/thresholds/runtime-policy.json",
        {"policy_mode": "threshold-default", "rl_min_confidence": 0.72, "rl_max_uncertainty": 0.35, "rl_artifact_max_age_hours": 168},
    )


def test_render_benchmark_bundle_surfaces_caveats_and_fail_soft_assets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    _seed_common_artifacts(tmp_path)

    summary = render_benchmark_bundle()
    output_root = tmp_path / "docs/benchmarks/latest"
    benchmark_summary = read_json(output_root / "benchmark_summary.json")

    assert benchmark_summary["sample_count"] == 4
    assert any("only 4" in caveat for caveat in benchmark_summary["caveats"])
    assert any("No committed configs/thresholds/bseo-policy.json" in caveat for caveat in benchmark_summary["caveats"])
    assert (output_root / "benchmark_summary.md").exists()
    assert (output_root / "assets/overall_metrics_table.md").exists()
    assert (output_root / "assets/train_validation_eval_overview.svg").exists()
    assert (output_root / "assets/training_loss_curve.svg").exists()
    assert (output_root / "assets/training_accuracy_curve.svg").exists()
    assert (output_root / "assets/policy_mode_comparison.svg").exists()
    assert (output_root / "assets/runtime_governance.svg").exists()
    assert (output_root / "assets/observation_feedback_intake.svg").exists()
    assert (output_root / "interactive/metrics_dashboard.html").exists()
    assert (output_root / "interactive/runtime_governance_dashboard.html").exists()
    assert "Shadow observation count" in (output_root / "benchmark_summary.md").read_text(encoding="utf-8")
    assert "metric-grid" in (output_root / "interactive/metrics_dashboard.html").read_text(encoding="utf-8")
    assert "Data unavailable for this visualization" in (output_root / "assets/bseo_bias_profile.svg").read_text(encoding="utf-8")
    assert "Data unavailable for this visualization" in (output_root / "assets/training_loss_curve.svg").read_text(encoding="utf-8")
    assert "Data unavailable for this visualization" in (output_root / "assets/training_accuracy_curve.svg").read_text(encoding="utf-8")
    assert summary["runtime_truth"]["configured_policy_mode"] == "threshold-default"
    assert summary["runtime_governance"]["promotion"]["recommended_mode"] == "threshold-default"
    assert summary["supplemental_intake"]["browser_observations"]["total_observations"] == 0


def test_render_benchmark_bundle_prefers_run_specific_operator_gold(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    _seed_common_artifacts(tmp_path)
    operator_run_id = "discovery-operator-current"
    _write_json(
        tmp_path / "datasets/manifests/operator_feedback/latest.json",
        {
            "run_id": operator_run_id,
            "generated_at": "2026-04-25T06:00:00+00:00",
            "selected_count": 1,
        },
    )
    _write_json(
        tmp_path / f"datasets/manifests/operator_feedback/adjudication/{operator_run_id}.json",
        {"run_id": operator_run_id, "summary": {"saved_count": 1}},
    )
    _write_json(
        tmp_path / "datasets/manifests/operator_feedback/adjudication/latest.json",
        {"run_id": operator_run_id, "summary": {"saved_count": 1}},
    )
    _write_jsonl(
        tmp_path / f"datasets/manifests/operator_feedback/gold/{operator_run_id}.jsonl",
        [{"feedback_id": "current"}],
    )
    _write_jsonl(
        tmp_path / "datasets/manifests/operator_feedback/gold/latest.jsonl",
        [{"feedback_id": "current"}],
    )

    summary = render_benchmark_bundle()

    assert (
        summary["artifact_paths"]["operator_adjudication"]
        == f"datasets/manifests/operator_feedback/adjudication/{operator_run_id}.json"
    )
    assert (
        summary["artifact_paths"]["operator_gold"]
        == f"datasets/manifests/operator_feedback/gold/{operator_run_id}.jsonl"
    )


def test_render_benchmark_bundle_uses_bseo_artifacts_when_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    _seed_common_artifacts(tmp_path)
    _write_json(
        tmp_path / "configs/thresholds/bseo-policy.json",
        {
            "build_id": "build-test",
            "head_spec_version": "2026-03-23",
            "control_genome": {"global_thresholds": {"badge_threshold": 0.2}},
        },
    )
    _write_json(
        tmp_path / "artifacts/eval_runs/build-test-bseo-lineage.json",
        [
            {"candidate_id": "g1-a", "generation": 1, "accepted": True, "objective": 0.82},
            {"candidate_id": "g1-b", "generation": 1, "accepted": True, "objective": 0.79},
        ],
    )
    _write_json(
        tmp_path / "artifacts/eval_runs/build-test-bseo-report.json",
        {
            "best_bias_signature": {
                "macro": {
                    "sensational_weight": 0.31,
                    "crossmodal_rigidity": 0.44,
                    "channel_prior_dependency": 0.38,
                    "genre_confusion": 0.22,
                    "uncertainty_calibration": 0.19,
                }
            }
        },
    )
    _write_json(
        tmp_path / "artifacts/eval_runs/build-test-mutation-bias-atlas.json",
        {
            "status": "clustered",
            "usable_mutations": 14,
            "clusters": [
                {"cluster_id": 0, "size": 4, "average_delta_f": 0.03, "average_delta_b": -0.01},
                {"cluster_id": 1, "size": 3, "average_delta_f": 0.02, "average_delta_b": -0.02},
            ],
        },
    )
    _write_json(
        tmp_path / "artifacts/eval_runs/build-test-training-history.json",
        {
            "build_id": "build-test",
            "baseline_heads": {
                "fit_label": "train",
                "eval_label": "validation",
                "heads": {
                    "text": [
                        {"iteration": 1, "train_loss": 0.69, "validation_loss": 0.67, "train_accuracy": 0.5, "validation_accuracy": 0.5},
                        {"iteration": 8, "train_loss": 0.42, "validation_loss": 0.48, "train_accuracy": 0.82, "validation_accuracy": 0.76},
                    ]
                },
                "aggregated": [
                    {"iteration": 1, "train_loss": 0.69, "validation_loss": 0.67, "train_accuracy": 0.5, "validation_accuracy": 0.5},
                    {"iteration": 8, "train_loss": 0.42, "validation_loss": 0.48, "train_accuracy": 0.82, "validation_accuracy": 0.76},
                ],
            },
            "fusion": {
                "fit_label": "validation",
                "eval_label": "test",
                "history": [
                    {"iteration": 1, "validation_loss": 0.61, "test_loss": 0.58, "validation_accuracy": 0.74, "test_accuracy": 0.75},
                    {"iteration": 8, "validation_loss": 0.38, "test_loss": 0.41, "validation_accuracy": 0.87, "test_accuracy": 0.84},
                ],
            },
        },
    )

    render_benchmark_bundle()
    output_root = tmp_path / "docs/benchmarks/latest"
    bias_svg = (output_root / "assets/bseo_bias_profile.svg").read_text(encoding="utf-8")
    atlas_svg = (output_root / "assets/mutation_bias_atlas.svg").read_text(encoding="utf-8")
    lineage_svg = (output_root / "assets/lineage_overview.svg").read_text(encoding="utf-8")
    governance_svg = (output_root / "assets/runtime_governance.svg").read_text(encoding="utf-8")
    loss_svg = (output_root / "assets/training_loss_curve.svg").read_text(encoding="utf-8")
    accuracy_svg = (output_root / "assets/training_accuracy_curve.svg").read_text(encoding="utf-8")
    bseo_dashboard = (output_root / "interactive/bseo_policy_dashboard.html").read_text(encoding="utf-8")

    assert "Data unavailable for this visualization" not in bias_svg
    assert "Data unavailable for this visualization" not in loss_svg
    assert "Data unavailable for this visualization" not in accuracy_svg
    assert "Train loss" in loss_svg
    assert "Validation accuracy" in accuracy_svg
    assert "Mutation bias atlas" in atlas_svg
    assert "Accepted lineage objective scores" in lineage_svg
    assert "Runtime governance summary" in governance_svg
    assert "BSEO macro bias profile" in bseo_dashboard
