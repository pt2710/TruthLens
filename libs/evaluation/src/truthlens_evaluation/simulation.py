from __future__ import annotations

from typing import Any

from truthlens_evaluation.metrics import compute_binary_metrics


def _intervention_cost(threshold: float, predictions: list[int], labels: list[int]) -> float:
    cost = 0.0
    for prediction, label in zip(predictions, labels, strict=True):
        if prediction and not label:
            cost += 1.4 + threshold * 0.5
        elif not prediction and label:
            cost += 1.1
        elif prediction and label:
            cost -= 0.8
    return round(cost, 4)


def run_threshold_sweep(labels: list[int], scores: list[float]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for threshold in [round(value / 100.0, 2) for value in range(20, 95, 5)]:
        predictions = [int(score >= threshold) for score in scores]
        metrics = compute_binary_metrics(labels, scores, threshold=threshold)
        rows.append(
            {
                "threshold": threshold,
                **metrics,
                "intervention_cost": _intervention_cost(threshold, predictions, labels),
            }
        )
    return rows
