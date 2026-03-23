from truthlens_data_pipeline.manifests import SourceManifestRecord, build_source_manifest
from truthlens_dataset_governance.validators import validate_dataset_record, verify_training_gate


def test_source_manifest_builder() -> None:
    manifest = build_source_manifest(
        "run-1",
        [
            SourceManifestRecord(
                source_id="youtube-home",
                source_type="feed",
                platform="youtube",
                source_url="https://www.youtube.com/feed/subscriptions",
                collected_at="2026-03-22T00:00:00Z",
                access_method="public-dom",
                expected_fields=["title", "thumbnail", "channel_name"],
                parsing_risk="medium",
                status="pending",
            )
        ],
    )

    assert manifest.coverage_count == 1
    assert manifest.status_counts["pending"] == 1
    assert manifest.platform_counts["youtube"] == 1


def test_dataset_record_validation() -> None:
    record = validate_dataset_record(
        {
            "item_id": "item-1",
            "platform": "youtube",
            "source_run_id": "run-1",
            "source_url": "https://youtube.com/watch?v=123",
            "collected_at": "2026-03-22T00:00:00Z",
            "title": "Breaking aliens confirmed",
            "channel_name": "TruthLens Test",
            "thumbnail_path": "datasets/raw/thumbnails/item-1.jpg",
            "description": "Description",
            "tags": [],
            "hashtags": [],
            "transcript_excerpt": None,
            "metadata": {},
            "history": {},
            "features": {},
            "labels": {},
            "provenance": {},
            "annotator_notes": [],
        }
    )

    assert record.item_id == "item-1"


def test_training_gate_reports_missing_artifacts() -> None:
    allowed, missing = verify_training_gate({"source_manifest": True})
    assert not allowed
    assert "dataset_card" in missing
