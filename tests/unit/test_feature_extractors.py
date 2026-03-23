from truthlens_feature_extractors import (
    count_sensational_tokens,
    normalize_text,
    transcript_mismatch_score,
    transcript_overlap,
    uppercase_ratio,
)


def test_text_feature_helpers_capture_expected_signals() -> None:
    assert normalize_text("  Breaking   news  ") == "Breaking news"
    assert count_sensational_tokens("Breaking aliens confirmed") >= 2
    assert uppercase_ratio("WOW News") > 0.0


def test_transcript_mismatch_is_higher_for_divergent_text() -> None:
    aligned_overlap = transcript_overlap(
        "Satellite weather imaging workflow explained",
        "This workflow explained how satellite weather imaging is calibrated.",
    )
    divergent_overlap = transcript_overlap(
        "Breaking aliens confirmed over Europe",
        "This segment reviews telescope maintenance and launch cadence.",
    )
    assert aligned_overlap > divergent_overlap
    assert (
        transcript_mismatch_score(
            "Breaking aliens confirmed over Europe",
            "This segment reviews telescope maintenance and launch cadence.",
            2,
        )
        > transcript_mismatch_score(
            "Satellite weather imaging workflow explained",
            "This workflow explained how satellite weather imaging is calibrated.",
            0,
        )
    )
