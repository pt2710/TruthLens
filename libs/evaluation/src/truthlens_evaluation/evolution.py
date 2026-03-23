from __future__ import annotations

from copy import deepcopy
from random import Random
from typing import Any


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def _resolve_action(score: float, thresholds: dict[str, float]) -> str:
    if score < thresholds["badge_threshold"]:
        return "none"
    if score < thresholds["blur_threshold"]:
        return "badge"
    if score < thresholds["report_prompt_threshold"]:
        return "blur"
    if score < thresholds["hide_threshold"]:
        return "ask-report"
    return "hide"


def _candidate_fitness(rows: list[dict[str, Any]], thresholds: dict[str, float]) -> tuple[float, dict[str, Any]]:
    rewards: list[float] = []
    action_counts = {"none": 0, "badge": 0, "blur": 0, "ask-report": 0, "hide": 0}
    for row in rows:
        action = _resolve_action(float(row["score"]), thresholds)
        action_counts[action] += 1
        label = int(row["label"])
        uncertainty = float(row["uncertainty"])
        if action == "none":
            reward = 1.0 if label == 0 else -1.2
        elif action == "badge":
            reward = 0.35 if label == 0 else 1.05 - uncertainty
        elif action == "blur":
            reward = -0.15 if label == 0 else 1.55 - uncertainty
        elif action == "ask-report":
            reward = -0.55 if label == 0 else 2.1 - uncertainty
        else:
            reward = -0.95 if label == 0 else 1.85 - uncertainty
        rewards.append(reward)

    intervention_rate = (
        sum(action_counts[action] for action in ["badge", "blur", "ask-report", "hide"]) / max(len(rows), 1)
    )
    fitness = round((sum(rewards) / max(len(rewards), 1)) - (intervention_rate * 0.12), 4)
    return fitness, {
        "average_reward": round(sum(rewards) / max(len(rewards), 1), 4),
        "intervention_rate": round(intervention_rate, 4),
        "action_counts": action_counts,
    }


def run_evolutionary_search(
    rows: list[dict[str, Any]],
    *,
    seed_thresholds: dict[str, float] | None = None,
    population_size: int = 18,
    generations: int = 7,
    seed: int = 42,
) -> dict[str, Any]:
    base = deepcopy(
        seed_thresholds
        or {
            "badge_threshold": 0.35,
            "blur_threshold": 0.60,
            "report_prompt_threshold": 0.80,
            "hide_threshold": 0.93,
        }
    )
    rng = Random(seed)

    def random_candidate() -> dict[str, float]:
        badge = _clip(base["badge_threshold"] + rng.uniform(-0.08, 0.08), 0.18, 0.55)
        blur = _clip(max(badge + 0.08, base["blur_threshold"] + rng.uniform(-0.08, 0.08)), 0.35, 0.82)
        report = _clip(
            max(blur + 0.08, base["report_prompt_threshold"] + rng.uniform(-0.07, 0.07)),
            0.55,
            0.94,
        )
        hide = _clip(max(report + 0.06, base["hide_threshold"] + rng.uniform(-0.05, 0.05)), 0.75, 0.99)
        return {
            "badge_threshold": round(badge, 3),
            "blur_threshold": round(blur, 3),
            "report_prompt_threshold": round(report, 3),
            "hide_threshold": round(hide, 3),
        }

    population = [base] + [random_candidate() for _ in range(max(population_size - 1, 1))]
    history: list[dict[str, Any]] = []

    for generation in range(generations):
        scored_population: list[dict[str, Any]] = []
        for candidate in population:
            fitness, metrics = _candidate_fitness(rows, candidate)
            scored_population.append(
                {
                    "generation": generation,
                    "fitness": fitness,
                    "thresholds": candidate,
                    **metrics,
                }
            )
        scored_population.sort(key=lambda item: float(item["fitness"]), reverse=True)
        elites = scored_population[:4]
        history.append(
            {
                "generation": generation,
                "best_fitness": elites[0]["fitness"],
                "best_thresholds": elites[0]["thresholds"],
            }
        )
        next_population = [dict(elite["thresholds"]) for elite in elites]
        while len(next_population) < population_size:
            parent_a = dict(rng.choice(elites)["thresholds"])
            parent_b = dict(rng.choice(elites)["thresholds"])
            child = {
                "badge_threshold": round(
                    _clip(
                        (parent_a["badge_threshold"] + parent_b["badge_threshold"]) / 2 + rng.uniform(-0.025, 0.025),
                        0.18,
                        0.55,
                    ),
                    3,
                ),
                "blur_threshold": 0.0,
                "report_prompt_threshold": 0.0,
                "hide_threshold": 0.0,
            }
            child["blur_threshold"] = round(
                _clip(
                    max(
                        child["badge_threshold"] + 0.08,
                        (parent_a["blur_threshold"] + parent_b["blur_threshold"]) / 2 + rng.uniform(-0.025, 0.025),
                    ),
                    0.35,
                    0.82,
                ),
                3,
            )
            child["report_prompt_threshold"] = round(
                _clip(
                    max(
                        child["blur_threshold"] + 0.08,
                        (parent_a["report_prompt_threshold"] + parent_b["report_prompt_threshold"]) / 2 + rng.uniform(-0.025, 0.025),
                    ),
                    0.55,
                    0.94,
                ),
                3,
            )
            child["hide_threshold"] = round(
                _clip(
                    max(
                        child["report_prompt_threshold"] + 0.06,
                        (parent_a["hide_threshold"] + parent_b["hide_threshold"]) / 2 + rng.uniform(-0.02, 0.02),
                    ),
                    0.75,
                    0.99,
                ),
                3,
            )
            next_population.append(child)
        population = next_population

    final_candidates: list[dict[str, Any]] = []
    for candidate in population:
        fitness, metrics = _candidate_fitness(rows, candidate)
        final_candidates.append(
            {
                "thresholds": candidate,
                "fitness": fitness,
                "metrics": metrics,
            }
        )
    best = max(final_candidates, key=lambda item: float(item["fitness"]))
    return {
        "best_thresholds": best["thresholds"],
        "best_fitness": best["fitness"],
        "best_metrics": best["metrics"],
        "population_size": population_size,
        "generations": generations,
        "history": history,
    }


def search_threshold_family(sweep_rows: list[dict[str, Any]]) -> dict[str, float]:
    best = max(
        sweep_rows,
        key=lambda row: float(row["f1"]) - (float(row["intervention_cost"]) * 0.05),
    )
    threshold = float(best["threshold"])
    blur_threshold = round(min(max(threshold + 0.15, 0.45), 0.8), 2)
    ask_report_threshold = round(min(max(blur_threshold + 0.17, 0.65), 0.92), 2)
    hide_threshold = round(min(max(ask_report_threshold + 0.12, 0.8), 0.97), 2)
    return {
        "badge_threshold": threshold,
        "blur_threshold": blur_threshold,
        "report_prompt_threshold": ask_report_threshold,
        "hide_threshold": hide_threshold,
    }
