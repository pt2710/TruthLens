from __future__ import annotations

from typing import Any


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
