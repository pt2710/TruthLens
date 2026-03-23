from __future__ import annotations

import json
from typing import Any

from truthlens_data_pipeline.paths import read_jsonl, repo_root
from truthlens_dataset_governance import load_latest_build_manifest
from truthlens_evaluation import build_drift_report, build_q_table, run_threshold_sweep, search_threshold_family


def _label(record: dict[str, Any]) -> int:
    return int(
        any(
            bool(record["labels"].get(name, False))
            for name in [
                "clickbait",
                "misleading_thumbnail",
                "misleading_title",
                "fearbait",
                "ai_mass_spam",
            ]
        )
    )


def main() -> None:
    manifest = load_latest_build_manifest()
    train_rows = read_jsonl(repo_root() / manifest["artifacts"]["train"])
    test_rows = read_jsonl(repo_root() / manifest["artifacts"]["test"])

    score_rows: list[dict[str, float | int]] = []
    for row in test_rows:
        score = float(row["metadata"].get("weak_label_score", 0.0))
        uncertainty = 1.0 - min(score + 0.25, 0.98)
        score_rows.append({"score": score, "uncertainty": uncertainty, "label": _label(row)})

    sweep = run_threshold_sweep(
        labels=[int(row["label"]) for row in score_rows],
        scores=[float(row["score"]) for row in score_rows],
    )
    q_table = build_q_table(score_rows)
    thresholds = search_threshold_family(sweep)
    drift_report = build_drift_report(train_rows, test_rows)

    eval_dir = repo_root() / "artifacts" / "eval_runs"
    drift_dir = repo_root() / "artifacts" / "drift_reports"
    eval_dir.mkdir(parents=True, exist_ok=True)
    drift_dir.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "build_id": manifest["build_id"],
        "threshold_sweep": sweep,
        "q_table": q_table,
        "recommended_thresholds": thresholds,
    }
    (eval_dir / f"{manifest['build_id']}-simulation.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    (drift_dir / f"{manifest['build_id']}.json").write_text(
        json.dumps(drift_report, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    thresholds_path = repo_root() / "configs" / "thresholds" / "default.json"
    thresholds_path.write_text(json.dumps(thresholds, indent=2, ensure_ascii=True), encoding="utf-8")
    print(manifest["build_id"])


if __name__ == "__main__":
    main()
