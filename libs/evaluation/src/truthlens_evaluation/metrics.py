from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score


def compute_binary_metrics(y_true: list[int], y_score: list[float], threshold: float = 0.5) -> dict[str, Any]:
    predictions = [int(score >= threshold) for score in y_score]
    metrics: dict[str, Any] = {
        "precision": round(float(precision_score(y_true, predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, predictions, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, predictions, zero_division=0)), 4),
        "positive_rate": round(float(np.mean(predictions)), 4) if predictions else 0.0,
    }
    if len(set(y_true)) > 1:
        metrics["roc_auc"] = round(float(roc_auc_score(y_true, y_score)), 4)
        metrics["pr_auc"] = round(float(average_precision_score(y_true, y_score)), 4)
    else:
        metrics["roc_auc"] = None
        metrics["pr_auc"] = None
    return metrics
