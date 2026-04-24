from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _repo_root(repo_root: Path | None = None) -> Path:
    return repo_root or Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _relative_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def evaluate_benchmark_freshness(repo_root: Path | None = None) -> dict[str, Any]:
    root = _repo_root(repo_root)
    summary_path = root / "docs/benchmarks/latest/benchmark_summary.json"
    latest_build_manifest_path = root / "datasets/manifests/builds/latest.json"
    latest_operator_manifest_path = root / "datasets/manifests/operator_feedback/latest.json"

    summary = _read_json(summary_path)
    latest_build_manifest = _read_json(latest_build_manifest_path)
    latest_operator_manifest = _read_json(latest_operator_manifest_path)

    artifact_paths = dict(summary.get("artifact_paths", {}))
    artifact_timestamps = dict(summary.get("artifact_timestamps", {}))
    reasons: list[str] = []

    summary_build_id = summary.get("build_id")
    latest_build_id = latest_build_manifest.get("build_id")
    if summary_build_id != latest_build_id:
        reasons.append(
            f"Latest build manifest is {latest_build_id}, but committed benchmark summary is {summary_build_id}."
        )

    referenced_build_manifest_rel = artifact_paths.get("build_manifest")
    if referenced_build_manifest_rel:
        referenced_build_manifest = _read_json(root / referenced_build_manifest_rel)
        if referenced_build_manifest.get("build_id") != latest_build_id:
            reasons.append(
                "Benchmark summary references an older build manifest than datasets/manifests/builds/latest.json."
            )

    operator_run_id = latest_operator_manifest.get("run_id")
    summary_operator_manifest_rel = artifact_paths.get("operator_feedback_manifest")
    if summary_operator_manifest_rel:
        referenced_operator_manifest = _read_json(root / summary_operator_manifest_rel)
        if referenced_operator_manifest.get("run_id") != operator_run_id:
            reasons.append(
                "Benchmark summary references an older operator feedback manifest than datasets/manifests/operator_feedback/latest.json."
            )

    expected_adjudication_rel = (
        f"datasets/manifests/operator_feedback/adjudication/{operator_run_id}.json"
        if operator_run_id
        else None
    )
    expected_gold_rel = (
        f"datasets/manifests/operator_feedback/gold/{operator_run_id}.jsonl"
        if operator_run_id
        else None
    )
    if expected_adjudication_rel and artifact_paths.get("operator_adjudication") != expected_adjudication_rel:
        reasons.append(
            "Benchmark summary operator adjudication path does not match the current latest operator run."
        )
    if expected_gold_rel and artifact_paths.get("operator_gold") != expected_gold_rel:
        reasons.append(
            "Benchmark summary operator gold path does not match the current latest operator run."
        )

    latest_operator_generated_at = _parse_timestamp(latest_operator_manifest.get("generated_at"))
    summary_operator_generated_at = _parse_timestamp(
        artifact_timestamps.get("operator_feedback_manifest")
    )
    if (
        latest_operator_generated_at is not None
        and summary_operator_generated_at is not None
        and latest_operator_generated_at > summary_operator_generated_at
    ):
        reasons.append(
            "Latest operator feedback manifest is newer than the operator manifest timestamp recorded in the benchmark summary."
        )

    latest_build_generated_at = _parse_timestamp(latest_build_manifest.get("generated_at"))
    summary_generated_at = _parse_timestamp(summary.get("generated_at"))
    if (
        latest_build_generated_at is not None
        and summary_generated_at is not None
        and latest_build_generated_at > summary_generated_at
    ):
        reasons.append(
            "Latest build manifest is newer than the committed benchmark summary generation time."
        )

    outcome = "no-op" if not reasons else "refresh-required"
    return {
        "status": "up_to_date" if not reasons else "stale",
        "gate_outcome": outcome,
        "requires_refresh": bool(reasons),
        "latest_committed_benchmark_truth": {
            "build_id": summary_build_id,
            "model_version": summary.get("model_version"),
            "benchmark_summary_path": _relative_path(root, summary_path),
        },
        "latest_creator_operator_truth": {
            "run_id": operator_run_id,
            "manifest_path": _relative_path(root, latest_operator_manifest_path),
            "selected_count": latest_operator_manifest.get("selected_count"),
        },
        "latest_build_truth": {
            "build_id": latest_build_id,
            "build_manifest_path": _relative_path(root, latest_build_manifest_path),
        },
        "reasons": reasons,
    }


def _format_result(result: dict[str, Any]) -> str:
    lines = [
        "TruthLens benchmark freshness gate",
        f"- Status: {result['status']}",
        f"- Gate outcome: {result['gate_outcome']}",
        f"- Latest committed benchmark build_id: {result['latest_committed_benchmark_truth']['build_id']}",
        f"- Latest operator run_id: {result['latest_creator_operator_truth']['run_id']}",
        f"- Latest build manifest build_id: {result['latest_build_truth']['build_id']}",
    ]
    if result["reasons"]:
        lines.append("- Refresh reasons:")
        lines.extend([f"  - {reason}" for reason in result["reasons"]])
    else:
        lines.append("- No newer committed creator/operator benchmark truth was detected.")
    return "\n".join(lines)


def main() -> None:
    result = evaluate_benchmark_freshness()
    print(_format_result(result))
    if result["requires_refresh"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
