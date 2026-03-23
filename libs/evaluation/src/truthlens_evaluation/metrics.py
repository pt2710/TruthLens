from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score


def compute_binary_metrics(y_true: list[int], y_score: list[float], threshold: float = 0.5) -> dict[str, Any]:
    predictions = [int(score >= threshold) for score in y_score]
    tp = sum(1 for truth, prediction in zip(y_true, predictions, strict=True) if truth == 1 and prediction == 1)
    tn = sum(1 for truth, prediction in zip(y_true, predictions, strict=True) if truth == 0 and prediction == 0)
    fp = sum(1 for truth, prediction in zip(y_true, predictions, strict=True) if truth == 0 and prediction == 1)
    fn = sum(1 for truth, prediction in zip(y_true, predictions, strict=True) if truth == 1 and prediction == 0)
    metrics: dict[str, Any] = {
        "precision": round(float(precision_score(y_true, predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, predictions, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, predictions, zero_division=0)), 4),
        "positive_rate": round(float(np.mean(predictions)), 4) if predictions else 0.0,
        "false_positive_rate": round(fp / max(fp + tn, 1), 4),
        "false_negative_rate": round(fn / max(fn + tp, 1), 4),
    }
    if len(set(y_true)) > 1:
        metrics["roc_auc"] = round(float(roc_auc_score(y_true, y_score)), 4)
        metrics["pr_auc"] = round(float(average_precision_score(y_true, y_score)), 4)
    else:
        metrics["roc_auc"] = None
        metrics["pr_auc"] = None
    return metrics


def confusion_counts(y_true: list[int], y_score: list[float], threshold: float = 0.5) -> dict[str, int]:
    predictions = [int(score >= threshold) for score in y_score]
    return {
        "tp": sum(1 for truth, prediction in zip(y_true, predictions, strict=True) if truth == 1 and prediction == 1),
        "tn": sum(1 for truth, prediction in zip(y_true, predictions, strict=True) if truth == 0 and prediction == 0),
        "fp": sum(1 for truth, prediction in zip(y_true, predictions, strict=True) if truth == 0 and prediction == 1),
        "fn": sum(1 for truth, prediction in zip(y_true, predictions, strict=True) if truth == 1 and prediction == 0),
    }


def expected_calibration_error(y_true: list[int], y_score: list[float], bins: int = 10) -> float:
    if not y_score:
        return 0.0
    truths = np.asarray(y_true, dtype=float)
    scores = np.asarray(y_score, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    error = 0.0
    for lower, upper in zip(edges[:-1], edges[1:], strict=True):
        if upper == 1.0:
            mask = (scores >= lower) & (scores <= upper)
        else:
            mask = (scores >= lower) & (scores < upper)
        if not np.any(mask):
            continue
        bucket_scores = scores[mask]
        bucket_truths = truths[mask]
        bucket_confidence = float(np.mean(bucket_scores))
        bucket_accuracy = float(np.mean(bucket_truths))
        error += abs(bucket_accuracy - bucket_confidence) * (len(bucket_scores) / len(scores))
    return round(float(error), 4)
