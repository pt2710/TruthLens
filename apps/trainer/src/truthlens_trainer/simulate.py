from __future__ import annotations

import json
from typing import Any

from truthlens_data_pipeline.paths import ensure_dir, read_jsonl, repo_root
from truthlens_dataset_governance import load_latest_build_manifest
from truthlens_evaluation import (
    build_drift_report,
    build_q_table,
    derive_policy,
    estimate_state_values,
    recommend_bandit_threshold_adjustments,
    run_contextual_bandit,
    run_evolutionary_search,
    run_policy_replay,
    run_threshold_sweep,
    search_threshold_family,
)


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
        score_rows.append(
            {
                "score": score,
                "uncertainty": uncertainty,
                "label": _label(row),
                "prior_flags": int(row["history"].get("prior_flags", 0)),
                "repeat_template_rate": float(
                    row["history"]["channel_history_features"].get("repeat_template_rate", 0.0)
                ),
                "transcript_mismatch_score": float(
                    row["features"].get("transcript_mismatch_score", 0.0)
                ),
            }
        )

    sweep = run_threshold_sweep(
        labels=[int(row["label"]) for row in score_rows],
        scores=[float(row["score"]) for row in score_rows],
    )
    q_table = build_q_table(score_rows)
    policy = derive_policy(q_table)
    state_values = estimate_state_values(q_table)
    replay_summary = run_policy_replay(score_rows, q_table)
    thresholds = search_threshold_family(sweep)
    evolutionary_search = run_evolutionary_search(score_rows, seed_thresholds=thresholds)
    thresholds = evolutionary_search["best_thresholds"]
    contextual_bandit = run_contextual_bandit(score_rows)
    bandit_threshold_adjustments = recommend_bandit_threshold_adjustments(contextual_bandit)
    drift_report = build_drift_report(train_rows, test_rows)

    eval_dir = repo_root() / "artifacts" / "eval_runs"
    drift_dir = repo_root() / "artifacts" / "drift_reports"
    eval_dir.mkdir(parents=True, exist_ok=True)
    drift_dir.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "build_id": manifest["build_id"],
        "threshold_sweep": sweep,
        "q_table": q_table,
        "policy": policy,
        "bellman_state_values": state_values,
        "replay_summary": replay_summary,
        "recommended_thresholds": thresholds,
        "evolutionary_search": evolutionary_search,
        "contextual_bandit": contextual_bandit,
        "bandit_threshold_adjustments": bandit_threshold_adjustments,
    }
    (eval_dir / f"{manifest['build_id']}-simulation.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    (drift_dir / f"{manifest['build_id']}.json").write_text(
        json.dumps(drift_report, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    thresholds_dir = ensure_dir(repo_root() / "configs" / "thresholds")
    thresholds_path = thresholds_dir / "default.json"
    thresholds_path.write_text(json.dumps(thresholds, indent=2, ensure_ascii=True), encoding="utf-8")
    (thresholds_dir / "evolutionary-search.json").write_text(
        json.dumps(evolutionary_search, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    (thresholds_dir / "contextual-bandit.json").write_text(
        json.dumps(bandit_threshold_adjustments, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print(manifest["build_id"])


if __name__ == "__main__":
    main()
