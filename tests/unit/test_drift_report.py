from truthlens_evaluation import build_drift_report


def _row(
    *,
    title_length: float,
    sensational_count: float,
    thumbnail_text_density: float,
    transcript_mismatch_score: float,
    repeat_template_rate: float,
    channel_risk_mean: float,
    clickbait: bool,
) -> dict:
    return {
        "features": {
            "title_length": title_length,
            "sensational_count": sensational_count,
            "thumbnail_text_density": thumbnail_text_density,
            "transcript_mismatch_score": transcript_mismatch_score,
        },
        "history": {
            "channel_history_features": {
                "repeat_template_rate": repeat_template_rate,
                "channel_risk_mean": channel_risk_mean,
            }
        },
        "labels": {
            "clickbait": clickbait,
            "misleading_thumbnail": False,
            "misleading_title": False,
            "fearbait": False,
            "ai_mass_spam": False,
        },
    }


def test_drift_report_emits_retraining_signal_for_large_shift() -> None:
    reference_rows = [
        _row(
            title_length=40,
            sensational_count=0,
            thumbnail_text_density=0.12,
            transcript_mismatch_score=0.1,
            repeat_template_rate=0.1,
            channel_risk_mean=0.15,
            clickbait=False,
        )
        for _ in range(4)
    ]
    current_rows = [
        _row(
            title_length=58,
            sensational_count=1,
            thumbnail_text_density=0.32,
            transcript_mismatch_score=0.45,
            repeat_template_rate=0.38,
            channel_risk_mean=0.42,
            clickbait=True,
        )
        for _ in range(4)
    ]

    report = build_drift_report(reference_rows, current_rows)

    assert report["retraining_recommended"] is True
    assert "label-distribution-drift" in report["trigger_reasons"]
    assert report["label_distribution_shift"]["clickbait"] == 1.0
