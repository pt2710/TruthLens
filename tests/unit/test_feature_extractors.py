from truthlens_feature_extractors import (
    count_sensational_tokens,
    extract_thumbnail_features,
    make_test_png_bytes,
    normalize_text,
    thumbnail_array_batch,
    thumbnail_array_from_path,
    transcript_mismatch_score,
    transcript_overlap,
    uppercase_ratio,
)
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

    assert image_array is not None
    assert image_array.shape == (3, 32, 32)
    assert batch.shape == (2, 3, 32, 32)
    assert mask.tolist() == [True, False]
