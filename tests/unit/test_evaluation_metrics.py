from truthlens_evaluation import (
    build_q_table,
    compute_binary_metrics,
    confusion_counts,
    derive_policy,
    estimate_state_values,
    expected_calibration_error,
    recommend_bandit_threshold_adjustments,
    run_bseo_search,
    run_contextual_bandit,
    run_evolutionary_search,
    run_policy_replay,
)


def test_metrics_include_error_rates_and_confusion_counts() -> None:
    labels = [1, 1, 0, 0]
    scores = [0.9, 0.4, 0.7, 0.2]

    metrics = compute_binary_metrics(labels, scores, threshold=0.5)
    confusion = confusion_counts(labels, scores, threshold=0.5)

    assert metrics["false_positive_rate"] == 0.5
    assert metrics["false_negative_rate"] == 0.5
    assert confusion == {"tp": 1, "tn": 1, "fp": 1, "fn": 1}


def test_expected_calibration_error_is_bounded() -> None:
    labels = [1, 0, 1, 0, 1]
    scores = [0.95, 0.8, 0.6, 0.35, 0.2]

    error = expected_calibration_error(labels, scores, bins=5)

    assert 0.0 <= error <= 1.0


def test_q_learning_outputs_policy_state_values_and_replay_metrics() -> None:
    rows = [
        {"score": 0.88, "uncertainty": 0.08, "label": 1},
        {"score": 0.72, "uncertainty": 0.11, "label": 1},
        {"score": 0.31, "uncertainty": 0.22, "label": 0},
        {"score": 0.18, "uncertainty": 0.18, "label": 0},
    ]

    q_table = build_q_table(rows)
    policy = derive_policy(q_table)
    state_values = estimate_state_values(q_table)
    replay = run_policy_replay(rows, q_table)

    assert q_table
    assert policy
    assert state_values
    assert replay["steps"] == len(rows)
    assert 0.0 <= replay["intervention_rate"] <= 1.0
    assert sum(replay["action_counts"].values()) == len(rows)


def test_contextual_bandit_outputs_weights_and_adjustments() -> None:
    rows = [
        {
            "score": 0.88,
            "uncertainty": 0.08,
            "label": 1,
            "prior_flags": 3,
            "repeat_template_rate": 0.61,
            "transcript_mismatch_score": 0.74,
        },
        {
            "score": 0.72,
            "uncertainty": 0.11,
            "label": 1,
            "prior_flags": 2,
            "repeat_template_rate": 0.45,
            "transcript_mismatch_score": 0.55,
        },
        {
            "score": 0.31,
            "uncertainty": 0.22,
            "label": 0,
            "prior_flags": 0,
            "repeat_template_rate": 0.08,
            "transcript_mismatch_score": 0.12,
        },
        {
            "score": 0.18,
            "uncertainty": 0.18,
            "label": 0,
            "prior_flags": 0,
            "repeat_template_rate": 0.04,
            "transcript_mismatch_score": 0.06,
        },
    ]

    bandit = run_contextual_bandit(rows)
    adjustments = recommend_bandit_threshold_adjustments(bandit)

    assert bandit["steps"] == len(rows)
    assert bandit["feature_order"]
    assert set(adjustments.keys()) == {
        "badge_threshold_offset",
        "blur_threshold_offset",
        "report_prompt_threshold_offset",
        "hide_threshold_offset",
    }


def test_evolutionary_search_returns_threshold_history() -> None:
    rows = [
        {"score": 0.88, "uncertainty": 0.08, "label": 1},
        {"score": 0.72, "uncertainty": 0.11, "label": 1},
        {"score": 0.31, "uncertainty": 0.22, "label": 0},
        {"score": 0.18, "uncertainty": 0.18, "label": 0},
    ]

    result = run_evolutionary_search(rows, generations=3, population_size=8)

    assert result["best_thresholds"]["badge_threshold"] < result["best_thresholds"]["hide_threshold"]
    assert len(result["history"]) == 3
    assert result["population_size"] == 8


def test_bseo_search_returns_policy_artifacts_and_bias_atlas() -> None:
    rows = [
        {
            "score": 0.88,
            "uncertainty": 0.08,
            "label": 1,
            "prior_flags": 3,
            "repeat_template_rate": 0.61,
            "channel_risk_mean": 0.74,
            "transcript_mismatch_score": 0.76,
            "raw_transcript_mismatch_score": 0.78,
            "sensational_count": 3,
            "content_class": "news",
            "content_class_confidence": 0.88,
            "bias_primitives": {
                "sensational_weight": 0.7,
                "crossmodal_rigidity": 0.72,
                "channel_prior_dependency": 0.68,
                "genre_confusion": 0.12,
                "uncertainty_calibration": 0.08,
            },
        },
        {
            "score": 0.74,
            "uncertainty": 0.16,
            "label": 0,
            "prior_flags": 0,
            "repeat_template_rate": 0.05,
            "channel_risk_mean": 0.08,
            "transcript_mismatch_score": 0.28,
            "raw_transcript_mismatch_score": 0.52,
            "sensational_count": 0,
            "content_class": "music",
            "content_class_confidence": 0.9,
            "bias_primitives": {
                "sensational_weight": 0.1,
                "crossmodal_rigidity": 0.22,
                "channel_prior_dependency": 0.08,
                "genre_confusion": 0.1,
                "uncertainty_calibration": 0.06,
            },
        },
        {
            "score": 0.66,
            "uncertainty": 0.21,
            "label": 1,
            "prior_flags": 1,
            "repeat_template_rate": 0.22,
            "channel_risk_mean": 0.32,
            "transcript_mismatch_score": 0.54,
            "raw_transcript_mismatch_score": 0.55,
            "sensational_count": 1,
            "content_class": "documentary",
            "content_class_confidence": 0.77,
            "bias_primitives": {
                "sensational_weight": 0.28,
                "crossmodal_rigidity": 0.52,
                "channel_prior_dependency": 0.26,
                "genre_confusion": 0.18,
                "uncertainty_calibration": 0.11,
            },
        },
        {
            "score": 0.29,
            "uncertainty": 0.24,
            "label": 0,
            "prior_flags": 0,
            "repeat_template_rate": 0.03,
            "channel_risk_mean": 0.04,
            "transcript_mismatch_score": 0.14,
            "raw_transcript_mismatch_score": 0.18,
            "sensational_count": 0,
            "content_class": "gaming",
            "content_class_confidence": 0.76,
            "bias_primitives": {
                "sensational_weight": 0.08,
                "crossmodal_rigidity": 0.18,
                "channel_prior_dependency": 0.05,
                "genre_confusion": 0.2,
                "uncertainty_calibration": 0.1,
            },
        },
    ]

    result = run_bseo_search(rows, generations=3, population_size=8)

    assert result["policy_version"] == "bseo-control-policy-v1"
    assert "control_genome" in result["policy_artifact"]
    assert "recommended_thresholds" in result["policy_artifact"]
    assert result["best_performance"]["detection_quality"] >= 0.0
    assert result["mutation_bias_atlas"]["status"] in {"sparse", "clustered"}
    assert result["lineage_logs"]
