from truthlens_evaluation import (
    build_q_table,
    compute_binary_metrics,
    confusion_counts,
    derive_policy,
    estimate_state_values,
    expected_calibration_error,
    recommend_bandit_threshold_adjustments,
    run_contextual_bandit,
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
