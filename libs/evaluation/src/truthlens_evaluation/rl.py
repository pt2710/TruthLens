from __future__ import annotations

ACTIONS = ["none", "badge", "blur", "ask-report", "hide"]


def _state_key(score: float, uncertainty: float) -> str:
    score_bucket = min(int(score * 4), 3)
    uncertainty_bucket = min(int(uncertainty * 4), 3)
    return f"s{score_bucket}:u{uncertainty_bucket}"


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


def build_q_table(rows: list[dict[str, float | int]]) -> dict[str, dict[str, float]]:
    buckets: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        state = _state_key(float(row["score"]), float(row["uncertainty"]))
        buckets.setdefault(state, {action: [] for action in ACTIONS})
        for action in ACTIONS:
            buckets[state][action].append(
                _reward(action, int(row["label"]), float(row["uncertainty"]))
            )
    q_table: dict[str, dict[str, float]] = {}
    for state, action_rewards in buckets.items():
        q_table[state] = {
            action: round(sum(rewards) / max(len(rewards), 1), 4)
            for action, rewards in action_rewards.items()
        }
    return q_table
