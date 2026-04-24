from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts/benchmark_freshness_gate.py"
_SPEC = spec_from_file_location("truthlens_benchmark_freshness_gate", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
evaluate_benchmark_freshness = _MODULE.evaluate_benchmark_freshness


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows),
        encoding="utf-8",
    )


def _write_fixture_repo(
    root: Path,
    *,
    summary_build_id: str,
    latest_build_id: str,
    summary_operator_run_id: str,
    latest_operator_run_id: str,
    summary_operator_manifest_ts: str,
    latest_operator_manifest_ts: str,
) -> None:
    summary = {
        "generated_at": "2026-04-23T17:19:57.991263+00:00",
        "build_id": summary_build_id,
        "model_version": f"baseline-v1-{summary_build_id}",
        "artifact_paths": {
            "operator_feedback_manifest": "datasets/manifests/operator_feedback/latest.json",
            "operator_adjudication": f"datasets/manifests/operator_feedback/adjudication/{summary_operator_run_id}.json",
            "operator_gold": f"datasets/manifests/operator_feedback/gold/{summary_operator_run_id}.jsonl",
            "build_manifest": "datasets/manifests/builds/latest.json",
        },
        "artifact_timestamps": {
            "operator_feedback_manifest": summary_operator_manifest_ts,
        },
    }
    build_manifest = {
        "build_id": latest_build_id,
        "generated_at": "2026-04-23T17:15:04.403861+00:00",
    }
    operator_manifest = {
        "run_id": latest_operator_run_id,
        "generated_at": latest_operator_manifest_ts,
        "selected_count": 53,
    }
    adjudication_payload = {
        "run_id": latest_operator_run_id,
        "generated_at": latest_operator_manifest_ts,
        "summary": {"saved_count": 53},
    }

    _write_json(root / "docs/benchmarks/latest/benchmark_summary.json", summary)
    _write_json(root / "datasets/manifests/builds/latest.json", build_manifest)
    _write_json(root / "datasets/manifests/operator_feedback/latest.json", operator_manifest)
    _write_json(
        root / f"datasets/manifests/operator_feedback/adjudication/{summary_operator_run_id}.json",
        {"run_id": summary_operator_run_id},
    )
    _write_json(
        root / f"datasets/manifests/operator_feedback/adjudication/{latest_operator_run_id}.json",
        adjudication_payload,
    )
    _write_jsonl(
        root / f"datasets/manifests/operator_feedback/gold/{summary_operator_run_id}.jsonl",
        [{"feedback_id": "old"}],
    )
    _write_jsonl(
        root / f"datasets/manifests/operator_feedback/gold/{latest_operator_run_id}.jsonl",
        [{"feedback_id": "new"}],
    )


def test_benchmark_freshness_gate_passes_for_current_repo_truth() -> None:
    result = evaluate_benchmark_freshness()

    assert result["status"] == "up_to_date"
    assert result["gate_outcome"] == "no-op"
    assert result["requires_refresh"] is False


def test_benchmark_freshness_gate_fails_when_newer_operator_truth_exists(tmp_path: Path) -> None:
    _write_fixture_repo(
        tmp_path,
        summary_build_id="build-1",
        latest_build_id="build-2",
        summary_operator_run_id="discovery-20260423090000-operator-feedback",
        latest_operator_run_id="discovery-20260423100000-operator-feedback",
        summary_operator_manifest_ts="2026-04-23T09:00:00+00:00",
        latest_operator_manifest_ts="2026-04-23T10:00:00+00:00",
    )

    result = evaluate_benchmark_freshness(tmp_path)

    assert result["status"] == "stale"
    assert result["gate_outcome"] == "refresh-required"
    assert result["requires_refresh"] is True
    assert any("Latest build manifest is build-2" in reason for reason in result["reasons"])
    assert any(
        "operator adjudication path" in reason.lower()
        or "operator feedback manifest is newer" in reason.lower()
        for reason in result["reasons"]
    )
