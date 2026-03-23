from __future__ import annotations

from typing import Any


def _mean(values: list[float]) -> float:
    return round(sum(values) / max(len(values), 1), 4)


def build_drift_report(reference_rows: list[dict[str, Any]], current_rows: list[dict[str, Any]]) -> dict[str, Any]:
    reference_title_lengths = [float(row["features"].get("title_length", 0.0)) for row in reference_rows]
    current_title_lengths = [float(row["features"].get("title_length", 0.0)) for row in current_rows]
    reference_sensational = [float(row["features"].get("sensational_count", 0.0)) for row in reference_rows]
    current_sensational = [float(row["features"].get("sensational_count", 0.0)) for row in current_rows]
    return {
        "reference_count": len(reference_rows),
        "current_count": len(current_rows),
        "title_length_shift": round(_mean(current_title_lengths) - _mean(reference_title_lengths), 4),
        "sensational_count_shift": round(
            _mean(current_sensational) - _mean(reference_sensational), 4
        ),
        "label_rate_shift": round(
            (
                _mean(
                    [
                        float(
                            any(
                                bool(row["labels"].get(name, False))
                                for name in [
                                    "clickbait",
                                    "misleading_thumbnail",
                                    "misleading_title",
                                    "fearbait",
                                    "ai_mass_spam",
                                ]
                            )
                        )
                        for row in current_rows
                    ]
                )
                - _mean(
                    [
                        float(
                            any(
                                bool(row["labels"].get(name, False))
                                for name in [
                                    "clickbait",
                                    "misleading_thumbnail",
                                    "misleading_title",
                                    "fearbait",
                                    "ai_mass_spam",
                                ]
                            )
                        )
                        for row in reference_rows
                    ]
                )
            ),
            4,
        ),
    }
