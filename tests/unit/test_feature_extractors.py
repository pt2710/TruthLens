from truthlens_feature_extractors import (
    build_bias_primitives,
    build_bias_profile,
    class_adjusted_mismatch,
    count_sensational_tokens,
    extract_thumbnail_features,
    infer_content_taxonomy,
    infer_bseo_prior_frames,
    make_test_png_bytes,
    normalize_text,
    thumbnail_array_batch,
    thumbnail_array_from_path,
    transcript_mismatch_score,
    transcript_overlap,
    uppercase_ratio,
)
from truthlens_feature_extractors.vision import Image
from pathlib import Path


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


def test_thumbnail_feature_extractor_reads_real_png(tmp_path: Path) -> None:
    image_path = tmp_path / "thumb.png"
    image_path.write_bytes(make_test_png_bytes((250, 40, 40)))

    features = extract_thumbnail_features(
        image_path,
        fallback_signal={
            "text_density": 0.42,
            "face_emphasis": 0.33,
            "shock_indicator": 0.51,
        },
    )

    assert features["thumbnail_byte_size"] > 0
    assert 0.0 <= features["thumbnail_brightness"] <= 1.0
    assert 0.0 <= features["thumbnail_saturation"] <= 1.0
    assert features["thumbnail_text_density"] == 0.42


def test_thumbnail_array_loader_reads_png_and_masks_missing_json(tmp_path: Path) -> None:
    image_path = tmp_path / "thumb.png"
    image_path.write_bytes(make_test_png_bytes((30, 200, 120), width=24, height=24))
    json_path = tmp_path / "thumb.json"
    json_path.write_text('{"brightness": 0.4}', encoding="utf-8")

    image_array = thumbnail_array_from_path(image_path, image_size=32)
    batch, mask = thumbnail_array_batch([image_path, json_path], image_size=32)

    assert batch.shape == (2, 3, 32, 32)
    if Image is None:
        assert image_array is None
        assert mask.tolist() == [False, False]
    else:
        assert image_array is not None
        assert image_array.shape == (3, 32, 32)
        assert mask.tolist() == [True, False]


def test_content_taxonomy_and_bias_profile_capture_music_guardrails() -> None:
    taxonomy = infer_content_taxonomy(
        title="Moonlight Echoes (Official Audio)",
        description="New single from Aurora Records.",
        transcript="Verse one flows into chorus and refrain.",
        channel_name="Aurora Records",
        channel_history_features={"music_likelihood": 0.94, "prior_flags": 0.0},
    )

    adjusted_mismatch, guardrail = class_adjusted_mismatch(0.82, str(taxonomy["content_class"]))
    metrics = build_bias_primitives(
        title="Moonlight Echoes (Official Audio)",
        raw_transcript_mismatch=0.82,
        adjusted_transcript_mismatch=adjusted_mismatch,
        content_class=str(taxonomy["content_class"]),
        content_class_confidence=float(taxonomy["content_class_confidence"]),
        prior_flags=0,
        channel_risk_mean=0.08,
        repeat_template_rate=0.04,
        uncertainty=0.18,
    )
    profile = build_bias_profile(
        metrics=metrics,
        content_class=str(taxonomy["content_class"]),
        content_class_confidence=float(taxonomy["content_class_confidence"]),
        raw_transcript_mismatch=0.82,
        adjusted_transcript_mismatch=adjusted_mismatch,
        uncertainty=0.18,
    )

    assert taxonomy["content_class"] == "music"
    assert guardrail == "music-context-dampens-crossmodal-rigidity"
    assert adjusted_mismatch < 0.82
    assert "stylistic-divergence-tolerance" in profile["positive_biases"]


def test_content_taxonomy_uses_generic_extension_hints() -> None:
    taxonomy = infer_content_taxonomy(
        title="Signal rundown",
        description="A creator breaks down today's events.",
        transcript="Context remains sparse in the visible snippet.",
        channel_name="Signal Desk",
        channel_history_features={
            "taxonomy_hint_commentary": 0.88,
            "taxonomy_hint_news": 0.14,
            "prior_flags": 0.0,
        },
    )

    assert taxonomy["content_class"] == "commentary"
    assert taxonomy["content_class_scores"]["commentary"] > taxonomy["content_class_scores"]["news"]


def test_bseo_prior_frames_preserve_benign_contexts() -> None:
    metrics = build_bias_primitives(
        title="How to repair a gaming mouse in 10 minutes",
        description="Hands-on tutorial and side-by-side review for the latest gaming peripherals.",
        transcript="This tutorial shows the full repair method and explains each step clearly.",
        channel_name="Hardware Workshop",
        raw_transcript_mismatch=0.18,
        adjusted_transcript_mismatch=0.14,
        content_class="commentary",
        content_class_confidence=0.83,
        prior_flags=0,
        channel_risk_mean=0.12,
        repeat_template_rate=0.08,
        channel_history_features={"transparent_count": 3.0, "reported_item_count": 0.0, "trust_score": 8.4},
        uncertainty=0.12,
    )
    frames = infer_bseo_prior_frames(
        title="How to repair a gaming mouse in 10 minutes",
        description="Hands-on tutorial and side-by-side review for the latest gaming peripherals.",
        transcript="This tutorial shows the full repair method and explains each step clearly.",
        channel_name="Hardware Workshop",
        content_class="commentary",
        content_class_confidence=0.83,
        metrics=metrics,
        prior_flags=0,
        channel_risk_mean=0.12,
        repeat_template_rate=0.08,
        channel_history_features={"transparent_count": 3.0, "reported_item_count": 0.0, "trust_score": 8.4},
        thumbnail_text_density=0.18,
        thumbnail_shock_indicator=0.12,
    )

    assert "tutorial-howto-context" in frames["positive_contexts"]
    assert "review-comparison-context" in frames["positive_contexts"]
    assert "transparent-verification-history" in frames["positive_contexts"]
    assert "tutorial-howto-context" in frames["parameter_frames"]["title"]
    assert not frames["negative_contexts"]


def test_bseo_prior_frames_escalate_deceptive_packaging_patterns() -> None:
    metrics = build_bias_primitives(
        title="BREAKING OMG: Official leak proves everything before it gets deleted",
        description="Exclusive shocking proof that changes everything.",
        transcript="The clip never provides the promised proof and keeps repeating the same vague claim.",
        channel_name="World News Authority",
        raw_transcript_mismatch=0.84,
        adjusted_transcript_mismatch=0.9,
        content_class="news",
        content_class_confidence=0.58,
        prior_flags=4,
        channel_risk_mean=0.72,
        repeat_template_rate=0.63,
        channel_history_features={"reported_item_count": 8.0, "transparent_count": 0.0, "trust_score": 3.2},
        uncertainty=0.28,
    )
    frames = infer_bseo_prior_frames(
        title="BREAKING OMG: Official leak proves everything before it gets deleted",
        description="Exclusive shocking proof that changes everything.",
        transcript="The clip never provides the promised proof and keeps repeating the same vague claim.",
        channel_name="World News Authority",
        content_class="news",
        content_class_confidence=0.58,
        metrics=metrics,
        prior_flags=4,
        channel_risk_mean=0.72,
        repeat_template_rate=0.63,
        channel_history_features={"reported_item_count": 8.0, "transparent_count": 0.0, "trust_score": 3.2},
        thumbnail_text_density=0.46,
        thumbnail_shock_indicator=0.81,
    )

    assert "false-urgency" in frames["negative_contexts"]
    assert "false-official-claim" in frames["negative_contexts"]
    assert "shock-bait-packaging" in frames["negative_contexts"]
    assert "repeat-deceptive-channel-pattern" in frames["negative_contexts"]
    assert "false-urgency" in frames["parameter_frames"]["title"]
    assert "repeat-deceptive-channel-pattern" in frames["parameter_frames"]["channel"]
