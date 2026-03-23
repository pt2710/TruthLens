from truthlens_evaluation import compute_binary_metrics, confusion_counts, expected_calibration_error


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
