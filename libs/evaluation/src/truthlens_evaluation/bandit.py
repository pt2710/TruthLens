from __future__ import annotations

from typing import Any

import numpy as np

from .rl import ACTIONS, _reward

FEATURE_ORDER = [
    "bias",
    "score",
    "uncertainty",
    "prior_flags",
    "repeat_template_rate",
    "transcript_mismatch_score",
]


def _context_vector(row: dict[str, float | int]) -> np.ndarray:
    return np.asarray(
        [
            1.0,
            float(row["score"]),
            float(row["uncertainty"]),
            min(float(row.get("prior_flags", 0.0)) / 5.0, 1.0),
            float(row.get("repeat_template_rate", 0.0)),
            float(row.get("transcript_mismatch_score", 0.0)),
        ],
        dtype=float,
    )


def run_contextual_bandit(
    rows: list[dict[str, float | int]],
    *,
    alpha: float = 0.65,
) -> dict[str, Any]:
    dimension = len(FEATURE_ORDER)
    covariance = {action: np.eye(dimension, dtype=float) for action in ACTIONS}
    response = {action: np.zeros(dimension, dtype=float) for action in ACTIONS}
    action_counts = {action: 0 for action in ACTIONS}
    rewards: list[float] = []
    trace: list[dict[str, Any]] = []

    for row in rows:
        x = _context_vector(row)
        best_action = "none"
        best_score = float("-inf")

        for action in ACTIONS:
            inverse_covariance = np.linalg.inv(covariance[action])
            theta = inverse_covariance @ response[action]
            exploration_bonus = alpha * float(np.sqrt(x @ inverse_covariance @ x))
            upper_confidence = float(theta @ x) + exploration_bonus
            if upper_confidence > best_score:
                best_score = upper_confidence
                best_action = action

        reward = _reward(best_action, int(row["label"]), float(row["uncertainty"]))
        covariance[best_action] += np.outer(x, x)
        response[best_action] += reward * x
        action_counts[best_action] += 1
        rewards.append(reward)

        if len(trace) < 10:
            trace.append(
                {
                    "score": round(float(row["score"]), 4),
                    "uncertainty": round(float(row["uncertainty"]), 4),
                    "label": int(row["label"]),
                    "action": best_action,
                    "reward": round(reward, 4),
                }
            )

    policy_weights = {
        action: [
            round(float(value), 4)
            for value in (np.linalg.inv(covariance[action]) @ response[action]).tolist()
        ]
        for action in ACTIONS
    }

    return {
        "steps": len(rows),
        "alpha": alpha,
        "feature_order": FEATURE_ORDER,
        "average_reward": round(sum(rewards) / max(len(rewards), 1), 4),
        "action_counts": action_counts,
        "policy_weights": policy_weights,
        "trace_sample": trace,
    }


def recommend_bandit_threshold_adjustments(bandit_summary: dict[str, Any]) -> dict[str, float]:
    steps = max(int(bandit_summary.get("steps", 0)), 1)
    action_counts = {
        action: int(bandit_summary.get("action_counts", {}).get(action, 0))
        for action in ACTIONS
    }
    mild_rate = (action_counts["none"] + action_counts["badge"]) / steps
    severe_rate = (action_counts["ask-report"] + action_counts["hide"]) / steps
    moderate_rate = action_counts["blur"] / steps
    badge_offset = round(max(-0.05, min(0.05, (mild_rate - severe_rate) * 0.04)), 3)
    blur_offset = round(max(-0.04, min(0.04, (moderate_rate - severe_rate) * 0.03)), 3)
    report_offset = round(max(-0.05, min(0.05, (mild_rate - severe_rate) * 0.05)), 3)
    hide_offset = round(max(-0.05, min(0.05, (mild_rate - severe_rate) * 0.05)), 3)
    return {
        "badge_threshold_offset": badge_offset,
        "blur_threshold_offset": blur_offset,
        "report_prompt_threshold_offset": report_offset,
        "hide_threshold_offset": hide_offset,
    }
