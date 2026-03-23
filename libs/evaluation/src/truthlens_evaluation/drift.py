from __future__ import annotations

from typing import Any


def _mean(values: list[float]) -> float:
    return round(sum(values) / max(len(values), 1), 4)


def _label_rate(rows: list[dict[str, Any]], label_name: str) -> float:
    return _mean([float(bool(row["labels"].get(label_name, False))) for row in rows])


def _feature_mean(rows: list[dict[str, Any]], feature_name: str) -> float:
    return _mean([float(row["features"].get(feature_name, 0.0)) for row in rows])


def _history_mean(rows: list[dict[str, Any]], feature_name: str) -> float:
    return _mean(
        [float(row["history"]["channel_history_features"].get(feature_name, 0.0)) for row in rows]
    )


def build_drift_report(reference_rows: list[dict[str, Any]], current_rows: list[dict[str, Any]]) -> dict[str, Any]:
    reference_title_lengths = [float(row["features"].get("title_length", 0.0)) for row in reference_rows]
    current_title_lengths = [float(row["features"].get("title_length", 0.0)) for row in current_rows]
    reference_sensational = [float(row["features"].get("sensational_count", 0.0)) for row in reference_rows]
    current_sensational = [float(row["features"].get("sensational_count", 0.0)) for row in current_rows]
    label_distribution_shift = {
        label_name: round(_label_rate(current_rows, label_name) - _label_rate(reference_rows, label_name), 4)
        for label_name in [
            "clickbait",
            "misleading_thumbnail",
            "misleading_title",
            "fearbait",
            "ai_mass_spam",
        ]
    }
    title_length_shift = round(_mean(current_title_lengths) - _mean(reference_title_lengths), 4)
    sensational_count_shift = round(_mean(current_sensational) - _mean(reference_sensational), 4)
    thumbnail_text_density_shift = round(
        _feature_mean(current_rows, "thumbnail_text_density")
        - _feature_mean(reference_rows, "thumbnail_text_density"),
        4,
    )
    transcript_mismatch_shift = round(
        _feature_mean(current_rows, "transcript_mismatch_score")
        - _feature_mean(reference_rows, "transcript_mismatch_score"),
        4,
    )
    repeat_template_rate_shift = round(
        _history_mean(current_rows, "repeat_template_rate")
        - _history_mean(reference_rows, "repeat_template_rate"),
        4,
    )
    channel_risk_mean_shift = round(
        _history_mean(current_rows, "channel_risk_mean")
        - _history_mean(reference_rows, "channel_risk_mean"),
        4,
    )
    label_rate_shift = round(
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
    )
    report = {
        "reference_count": len(reference_rows),
        "current_count": len(current_rows),
        "title_length_shift": title_length_shift,
        "sensational_count_shift": sensational_count_shift,
        "thumbnail_text_density_shift": thumbnail_text_density_shift,
        "transcript_mismatch_shift": transcript_mismatch_shift,
        "repeat_template_rate_shift": repeat_template_rate_shift,
        "channel_risk_mean_shift": channel_risk_mean_shift,
        "label_rate_shift": label_rate_shift,
        "label_distribution_shift": label_distribution_shift,
    }
    trigger_reasons = []
    if abs(title_length_shift) >= 8.0:
        trigger_reasons.append("title-length-drift")
    if abs(sensational_count_shift) >= 0.25:
        trigger_reasons.append("sensational-pattern-drift")
    if abs(thumbnail_text_density_shift) >= 0.12:
        trigger_reasons.append("thumbnail-style-drift")
    if abs(transcript_mismatch_shift) >= 0.15:
        trigger_reasons.append("title-transcript-mismatch-drift")
    if abs(repeat_template_rate_shift) >= 0.12:
        trigger_reasons.append("template-repeat-drift")
    if abs(channel_risk_mean_shift) >= 0.12:
        trigger_reasons.append("channel-risk-drift")
    if any(abs(shift) >= 0.1 for shift in label_distribution_shift.values()):
        trigger_reasons.append("label-distribution-drift")
    report["retraining_recommended"] = bool(trigger_reasons)
    report["trigger_reasons"] = trigger_reasons
    return report
