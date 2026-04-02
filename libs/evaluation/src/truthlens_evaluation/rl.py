from __future__ import annotations

from typing import Any

ACTIONS = ["none", "badge", "blur", "ask-report", "hide"]


def state_key_for_score(score: float, uncertainty: float) -> str:
    score_bucket = min(int(score * 4), 3)
    uncertainty_bucket = min(int(uncertainty * 4), 3)
    return f"s{score_bucket}:u{uncertainty_bucket}"


def _state_key(score: float, uncertainty: float) -> str:
    return state_key_for_score(score, uncertainty)


def _reward(action: str, label: int, uncertainty: float) -> float:
    if action == "none":
        return 1.0 if label == 0 else -1.1
    if action == "badge":
        return 0.4 if label == 0 else 1.2 - uncertainty
    if action == "blur":
        return -0.3 if label == 0 else 1.9 - uncertainty
    if action == "ask-report":
        return -0.8 if label == 0 else 2.4 - uncertainty
    return -1.2 if label == 0 else 2.0 - uncertainty


def build_q_table(
    rows: list[dict[str, float | int]],
    *,
    alpha: float = 0.35,
    gamma: float = 0.9,
) -> dict[str, dict[str, float]]:
    q_table: dict[str, dict[str, float]] = {}
    visits: dict[str, dict[str, int]] = {}

    for index, row in enumerate(rows):
        state = _state_key(float(row["score"]), float(row["uncertainty"]))
        q_table.setdefault(state, {action: 0.0 for action in ACTIONS})
        visits.setdefault(state, {action: 0 for action in ACTIONS})
        next_state = None
        if index + 1 < len(rows):
            next_row = rows[index + 1]
            next_state = _state_key(float(next_row["score"]), float(next_row["uncertainty"]))
            q_table.setdefault(next_state, {action: 0.0 for action in ACTIONS})
            visits.setdefault(next_state, {action: 0 for action in ACTIONS})

        for action in ACTIONS:
            reward = _reward(action, int(row["label"]), float(row["uncertainty"]))
            next_best = max(q_table[next_state].values()) if next_state is not None else 0.0
            target = reward + (gamma * next_best)
            visits[state][action] += 1
            learning_rate = alpha / (1.0 + (visits[state][action] - 1) * 0.25)
            current_value = q_table[state][action]
            q_table[state][action] = round(current_value + learning_rate * (target - current_value), 4)

    return q_table


def derive_policy(q_table: dict[str, dict[str, float]]) -> dict[str, str]:
    return {
        state: max(action_values, key=lambda action: action_values[action])
        for state, action_values in q_table.items()
    }


def estimate_state_values(q_table: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        state: round(max(action_values.values()), 4)
        for state, action_values in q_table.items()
    }


def run_policy_replay(
    rows: list[dict[str, float | int]],
    q_table: dict[str, dict[str, float]],
    *,
    gamma: float = 0.9,
) -> dict[str, Any]:
    policy = derive_policy(q_table)
    action_counts = {action: 0 for action in ACTIONS}
    discounted_return = 0.0
    rewards: list[float] = []
    correct_interventions = 0
    unnecessary_interventions = 0

    for index, row in enumerate(rows):
        state = _state_key(float(row["score"]), float(row["uncertainty"]))
        action = policy.get(state, "none")
        reward = _reward(action, int(row["label"]), float(row["uncertainty"]))
        rewards.append(reward)
        action_counts[action] += 1
        discounted_return += (gamma**index) * reward

        intervention = action != "none"
        label = int(row["label"])
        if intervention and label == 1:
            correct_interventions += 1
        if intervention and label == 0:
            unnecessary_interventions += 1

    total_steps = len(rows)
    return {
        "steps": total_steps,
        "average_reward": round(sum(rewards) / max(total_steps, 1), 4),
        "discounted_return": round(discounted_return, 4),
        "action_counts": action_counts,
        "correct_interventions": correct_interventions,
        "unnecessary_interventions": unnecessary_interventions,
        "intervention_rate": round(sum(action_counts[action] for action in ACTIONS if action != "none") / max(total_steps, 1), 4),
    }
