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
    run_bseo_search,
    run_contextual_bandit,
    run_evolutionary_search,
    run_policy_replay,
    run_threshold_sweep,
    search_threshold_family,
)
from truthlens_model_serving import predict_item_signals
from truthlens_model_serving.registry import ARCHITECTURE_PLAN_VERSION, HEAD_SPEC_VERSION
from truthlens_shared_schemas.contracts import ChannelInfo, ItemMetadata, RuntimeContext, ScoreItemRequest


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


def _score_request_from_record(record: dict[str, Any]) -> ScoreItemRequest:
    thumbnail_path = repo_root() / str(record.get("thumbnail_path", ""))
    thumbnail_ref = str(thumbnail_path) if thumbnail_path.exists() else None
    metadata = dict(record.get("metadata", {}))
    history = dict(record.get("history", {}))
    history_features = dict(history.get("channel_history_features", {}))
    return ScoreItemRequest(
        item_id=str(record["item_id"]),
        title=str(record["title"]),
        thumbnail_ref=thumbnail_ref,
        description_snapshot=str(record.get("description", "") or "") or None,
        transcript_excerpt=str(record.get("transcript_excerpt", "") or "") or None,
        metadata=ItemMetadata(
            upload_time=str(metadata.get("upload_time", "") or "") or None,
            duration_seconds=metadata.get("duration_seconds"),
            view_count=metadata.get("view_count"),
            like_count=metadata.get("like_count"),
        ),
        channel=ChannelInfo(
            channel_name=str(record.get("channel_name", "Unknown channel")),
            prior_flags=int(history.get("prior_flags", 0)),
            channel_history_features=history_features,
        ),
        runtime_context=RuntimeContext(
            surface="trainer",
            review_requested=False,
            source_provenance=str(record.get("source_url", "") or "") or None,
        ),
    )


def main() -> None:
    manifest = load_latest_build_manifest()
    train_rows = read_jsonl(repo_root() / manifest["artifacts"]["train"])
    test_rows = read_jsonl(repo_root() / manifest["artifacts"]["test"])

    score_rows: list[dict[str, Any]] = []
    for row in test_rows:
        signals = predict_item_signals(_score_request_from_record(row))
        feature_summary = dict(signals.feature_summary)
        score_rows.append(
            {
                "score": float(signals.calibrated_score),
                "uncertainty": float(signals.uncertainty),
                "label": _label(row),
                "prior_flags": int(feature_summary.get("prior_flags", row["history"].get("prior_flags", 0))),
                "repeat_template_rate": float(
                    feature_summary.get(
                        "repeat_template_rate",
                        row["history"]["channel_history_features"].get("repeat_template_rate", 0.0),
                    )
                ),
                "channel_risk_mean": float(
                    feature_summary.get(
                        "channel_risk_mean",
                        row["history"]["channel_history_features"].get("channel_risk_mean", 0.0),
                    )
                ),
                "transcript_mismatch_score": float(
                    feature_summary.get(
                        "transcript_mismatch_score",
                        row["features"].get("transcript_mismatch_score", 0.0),
                    )
                ),
                "raw_transcript_mismatch_score": float(
                    feature_summary.get(
                        "raw_transcript_mismatch_score",
                        row["features"].get("raw_transcript_mismatch_score", 0.0),
                    )
                ),
                "sensational_count": float(feature_summary.get("token_hits", row["features"].get("sensational_count", 0.0))),
                "content_class": str(feature_summary.get("content_class", row["features"].get("content_class", "unknown"))),
                "content_class_confidence": float(
                    feature_summary.get(
                        "content_class_confidence",
                        row["features"].get("content_class_confidence", 0.0),
                    )
                ),
                "music_likelihood": float(
                    feature_summary.get(
                        "music_likelihood",
                        row["history"]["channel_history_features"].get("music_likelihood", 0.0),
                    )
                ),
                "bias_primitives": dict(
                    feature_summary.get("bias_primitives", row["features"].get("bias_primitives", {}))
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
    bseo_search = run_bseo_search(score_rows, seed_thresholds=thresholds)
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
        "bseo_search": {
            "policy_version": bseo_search["policy_version"],
            "best_candidate_id": bseo_search["best_candidate_id"],
            "best_objective": bseo_search["best_objective"],
            "recommended_thresholds": bseo_search["recommended_thresholds"],
            "best_performance": bseo_search["best_performance"],
            "best_bias_signature": bseo_search["best_bias_signature"],
            "history": bseo_search["history"],
            "mutation_bias_atlas": bseo_search["mutation_bias_atlas"],
        },
        "contextual_bandit": contextual_bandit,
        "bandit_threshold_adjustments": bandit_threshold_adjustments,
    }
    (eval_dir / f"{manifest['build_id']}-simulation.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    bseo_report_path = eval_dir / f"{manifest['build_id']}-bseo-report.json"
    bseo_lineage_path = eval_dir / f"{manifest['build_id']}-bseo-lineage.json"
    bseo_atlas_path = eval_dir / f"{manifest['build_id']}-mutation-bias-atlas.json"
    bseo_report_path.write_text(
        json.dumps(
            {
                "build_id": manifest["build_id"],
                "generated_at": manifest["generated_at"],
                "policy_version": bseo_search["policy_version"],
                "best_candidate_id": bseo_search["best_candidate_id"],
                "best_objective": bseo_search["best_objective"],
                "recommended_thresholds": bseo_search["recommended_thresholds"],
                "best_theta": bseo_search["best_theta"],
                "best_performance": bseo_search["best_performance"],
                "best_bias_signature": bseo_search["best_bias_signature"],
                "baseline": bseo_search["baseline"],
                "history": bseo_search["history"],
                "lineage_log_path": str(bseo_lineage_path.relative_to(repo_root())).replace("\\", "/"),
                "mutation_bias_atlas_path": str(bseo_atlas_path.relative_to(repo_root())).replace("\\", "/"),
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    bseo_lineage_path.write_text(
        json.dumps(bseo_search["lineage_logs"], indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    bseo_atlas_path.write_text(
        json.dumps(bseo_search["mutation_bias_atlas"], indent=2, ensure_ascii=True),
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
    (thresholds_dir / "bseo-policy.json").write_text(
        json.dumps(
            {
                "policy_version": bseo_search["policy_version"],
                "generated_at": manifest["generated_at"],
                "build_id": manifest["build_id"],
                "head_spec_version": HEAD_SPEC_VERSION,
                "architecture_plan_version": ARCHITECTURE_PLAN_VERSION,
                **bseo_search["policy_artifact"],
                "lineage_log_path": str(bseo_lineage_path.relative_to(repo_root())).replace("\\", "/"),
                "mutation_bias_atlas_path": str(bseo_atlas_path.relative_to(repo_root())).replace("\\", "/"),
                "report_path": str(bseo_report_path.relative_to(repo_root())).replace("\\", "/"),
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    (thresholds_dir / "rl-policy.json").write_text(
        json.dumps(
            {
                "policy_version": "rl-action-policy-v1",
                "generated_at": manifest["generated_at"],
                "build_id": manifest["build_id"],
                "head_spec_version": HEAD_SPEC_VERSION,
                "architecture_plan_version": ARCHITECTURE_PLAN_VERSION,
                "policy": policy,
                "q_table": q_table,
                "bellman_state_values": state_values,
                "replay_summary": replay_summary,
                "recommended_thresholds": thresholds,
                "evolutionary_search": evolutionary_search,
                "contextual_bandit": contextual_bandit,
                "bandit_threshold_adjustments": bandit_threshold_adjustments,
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    print(manifest["build_id"])


if __name__ == "__main__":
    main()
