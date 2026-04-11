from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from truthlens_data_pipeline.paths import read_json
from truthlens_evaluation import apply_runtime_promotion, build_runtime_governance_summary
from truthlens_model_serving.registry import ARCHITECTURE_PLAN_VERSION, HEAD_SPEC_VERSION


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _seed_runtime_artifacts(root: Path, *, build_id: str = "build-governance") -> None:
    now = datetime.now(timezone.utc).isoformat()
    _write_json(
        root / "datasets/manifests/builds/latest.json",
        {
            "build_id": build_id,
            "counts": {"train": 110, "validation": 44, "test": 44},
        },
    )
    _write_json(
        root / "artifacts/trained_models/latest/model_info.json",
        {
            "build_id": build_id,
            "model_version": f"baseline-v1-{build_id}",
            "trained_at": now,
            "head_spec_version": HEAD_SPEC_VERSION,
            "architecture_plan_version": ARCHITECTURE_PLAN_VERSION,
        },
    )
    _write_json(
        root / "artifacts/eval_runs" / f"{build_id}.json",
        {
            "build_id": build_id,
            "sample_count": 44,
            "metrics": {"precision": 0.91, "recall": 0.93, "f1": 0.92},
            "validation_metrics": {"precision": 0.9, "recall": 0.9, "f1": 0.9},
            "calibration_error": 0.21,
        },
    )
    _write_json(
        root / "artifacts/eval_runs" / f"{build_id}-bseo-report.json",
        {
            "build_id": build_id,
            "best_objective": 0.81,
            "best_performance": {
                "benign_false_positive_rate": 0.0,
            },
        },
    )
    _write_json(
        root / "artifacts/eval_runs" / f"{build_id}-bseo-lineage.json",
        [{"candidate_id": f"g{i}", "accepted": True, "objective": 0.75 + i / 1000.0} for i in range(24)],
    )
    _write_json(
        root / "artifacts/eval_runs" / f"{build_id}-mutation-bias-atlas.json",
        {
            "status": "clustered",
            "usable_mutations": 36,
            "clusters": [{"cluster_id": 0, "size": 12, "average_delta_f": 0.03, "average_delta_b": -0.01}],
        },
    )
    _write_json(
        root / "configs/thresholds/bseo-policy.json",
        {
            "policy_version": "bseo-control-policy-v1",
            "generated_at": now,
            "build_id": build_id,
            "head_spec_version": HEAD_SPEC_VERSION,
            "architecture_plan_version": ARCHITECTURE_PLAN_VERSION,
            "control_genome": {"global_thresholds": {"badge_threshold": 0.3}},
        },
    )
    _write_json(
        root / "configs/thresholds/runtime-policy.json",
        {
            "policy_mode": "threshold-default",
            "rl_min_confidence": 0.72,
            "rl_max_uncertainty": 0.35,
            "rl_artifact_max_age_hours": 168,
        },
    )


def test_runtime_governance_recommends_shadow_but_blocks_live_without_shadow_history(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    _seed_runtime_artifacts(tmp_path)

    summary = build_runtime_governance_summary()

    assert summary["promotion"]["shadow_eligible"] is True
    assert summary["promotion"]["recommended_mode"] == "bseo-shadow"
    assert summary["promotion"]["live_eligible"] is False
    assert "insufficient-shadow-observation-history" in summary["promotion"]["live_blockers"]


def test_runtime_governance_falls_back_to_latest_eval_artifact_without_build_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    _seed_runtime_artifacts(tmp_path, build_id="build-latest-fallback")
    (tmp_path / "datasets/manifests/builds/latest.json").unlink()

    summary = build_runtime_governance_summary()

    assert summary["build_id"] is None
    assert summary["dataset"]["eval_sample_count"] == 44
    assert summary["artifacts"]["bseo_policy"]["available"] is True


def test_apply_runtime_promotion_auto_writes_bseo_shadow_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    _seed_runtime_artifacts(tmp_path)

    summary = apply_runtime_promotion(mode="auto")
    runtime_policy = read_json(tmp_path / "configs/thresholds/runtime-policy.json")
    governance_latest = read_json(tmp_path / "artifacts/reports/runtime-governance-latest.json")

    assert summary["promotion"]["applied_mode"] == "bseo-shadow"
    assert runtime_policy["policy_mode"] == "bseo-shadow"
    assert runtime_policy["rl_min_confidence"] == runtime_policy["bseo_min_confidence"]
    assert governance_latest["runtime_policy"]["configured_mode"] == "bseo-shadow"


def test_runtime_governance_recommends_live_when_live_guardrails_clear(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    _seed_runtime_artifacts(tmp_path, build_id="build-live-ready")
    _write_jsonl(
        tmp_path / "artifacts/reports/score_events.jsonl",
        [
            {
                "item_id": f"item-{index}",
                "channel_name": "Signal Watch Europe",
                "model_version": "baseline-v1-build-live-ready",
                "policy_version": "bseo-control-policy-v1-shadow",
                "recommended_action": "ask-report",
                "risk_score": 0.81,
                "confidence": 0.84,
                "uncertainty": 0.18,
                "explanation_id": f"exp-{index}",
                "timestamp": "2026-04-11T06:00:00+00:00",
            }
            for index in range(240)
        ],
    )

    summary = build_runtime_governance_summary()
    auto_summary = apply_runtime_promotion(mode="auto")
    runtime_policy = read_json(tmp_path / "configs/thresholds/runtime-policy.json")

    assert summary["promotion"]["live_eligible"] is True
    assert summary["promotion"]["recommended_mode"] == "bseo-live"
    assert auto_summary["promotion"]["applied_mode"] == "bseo-live"
    assert runtime_policy["policy_mode"] == "bseo-live"
