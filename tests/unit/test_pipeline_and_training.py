from pathlib import Path

import pytest

from truthlens_data_pipeline import PublicSourceSpec
from truthlens_data_pipeline.paths import read_json, read_jsonl, repo_root
from truthlens_model_serving import describe_model
from truthlens_policy_engine import score_item
from truthlens_shared_schemas.contracts import ChannelInfo, ItemMetadata, ScoreItemRequest
from truthlens_trainer.pipeline import run_pipeline
from truthlens_trainer.simulate import main as simulate_main
from truthlens_trainer.train import main as train_main


def test_pipeline_creates_build_outputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    result = run_pipeline(run_id="discovery-test-latest", build_id="build-test-latest")

    assert result["build_manifest"]["counts"]["train"] > 0
    assert result["build_manifest"]["counts"]["validation"] > 0
    assert result["build_manifest"]["counts"]["test"] > 0
    assert result["audit_report"]["training_gate_passed"] is True
    assert result["build_manifest"]["sources"]["source_manifest"]["status_counts"]["pending"] > 0
    assert "artifact_kind_counts" in result["build_manifest"]["sources"]["raw_acquisition_outputs"]
    assert "missing_field_rate" in result["build_manifest"]["sources"]["transform_manifest"]
    normalized_rows = read_jsonl(repo_root() / "datasets/interim/normalized/discovery-test-latest.jsonl")
    latest_annotation_batch = read_json(repo_root() / "datasets/labels/annotation_batches/latest.json")
    assert all("transcript_mismatch_score" in row["features"] for row in normalized_rows)
    assert all("repeat_template_rate" in row["history"]["channel_history_features"] for row in normalized_rows)
    assert latest_annotation_batch["run_id"] == "discovery-test-latest"
    assert "queue_reason" in latest_annotation_batch["review_queue"][0]
    assert "channel_name" in latest_annotation_batch["review_queue"][0]


def test_training_and_simulation_generate_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    run_pipeline(run_id="discovery-test-latest", build_id="build-test-latest")
    train_main()
    simulate_main()

    model_info = describe_model()
    model_dir = repo_root() / "artifacts/trained_models/latest"
    eval_report = read_json(repo_root() / "artifacts/eval_runs/build-test-latest.json")
    simulation_report = read_json(repo_root() / "artifacts/eval_runs/build-test-latest-simulation.json")
    drift_report = read_json(repo_root() / "artifacts/drift_reports/build-test-latest.json")
    audit_report = read_json(repo_root() / "datasets/manifests/audits/build-test-latest.json")

    assert model_info["mode"] == "trained"
    assert model_info["artifact_status"] == "compatible"
    assert "runtime_library_versions" in model_info
    assert "training_library_versions" in model_info
    assert "head_specs" in model_info
    assert "architecture_layers" in model_info
    assert "architecture_plan_version" in model_info
    assert "text_encoder_resolution" in model_info
    assert "history_encoder_resolution" in model_info
    assert model_info["head_specs"][0]["name"] == "text"
    assert any(head["name"] == "anomaly" for head in model_info["head_specs"])
    history_head = next(head for head in model_info["head_specs"] if head["name"] == "history")
    assert any(layer["component_id"] == "vae-anomaly-head" for layer in model_info["architecture_layers"])
    assert any(layer["component_id"] == "temporal-lstm-encoder" for layer in model_info["architecture_layers"])
    assert model_info["text_encoder_resolution"]["actual_encoder"] in {
        "sentence-transformer",
        "count-vectorizer-bigrams",
    }
    assert model_info["history_encoder_resolution"]["actual_encoder"] in {
        "lstm-sequence",
        "sequence-summary-v1",
    }
    assert history_head["encoder"] == model_info["history_encoder_resolution"]["actual_encoder"]
    assert "fusion_profile" in model_info
    assert "anomaly" in model_info["fusion_profile"]["head_weights"]
    assert "anomaly" in model_info["per_head_metrics"]
    assert model_dir.joinpath("model_bundle.pkl").exists()
    assert model_dir.joinpath("model_info.json").exists()
    assert (repo_root() / "artifacts/eval_runs").exists()
    assert (repo_root() / "artifacts/drift_reports").exists()
    assert "calibration_error" in model_info
    assert "per_head_metrics" in model_info
    assert "confusion_matrix" in model_info
    assert "validation_calibration_error" in eval_report
    assert "calibration_error" in eval_report
    assert "policy" in simulation_report
    assert "bellman_state_values" in simulation_report
    assert "replay_summary" in simulation_report
    assert "evolutionary_search" in simulation_report
    assert "contextual_bandit" in simulation_report
    assert "bandit_threshold_adjustments" in simulation_report
    assert simulation_report["replay_summary"]["steps"] > 0
    assert "retraining_recommended" in drift_report
    assert "label_distribution_shift" in drift_report
    assert "corrupted_image_rate" in audit_report
    assert "parser_failure_rate" in audit_report
    assert (repo_root() / "configs/thresholds/contextual-bandit.json").exists()
    assert (repo_root() / "configs/thresholds/evolutionary-search.json").exists()


def test_trained_scoring_surfaces_model_contributor_details(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    run_pipeline(run_id="discovery-test-latest", build_id="build-test-latest")
    train_main()

    result = score_item(
        ScoreItemRequest(
            item_id="trained-evidence-item",
            title="Breaking aliens confirmed over Europe",
            thumbnail_ref=None,
            transcript_excerpt="This segment reviews telescope maintenance and launch cadence.",
            metadata=ItemMetadata(view_count=12000, like_count=900),
            channel=ChannelInfo(
                channel_name="Signal Watch Europe",
                prior_flags=3,
                channel_history_features={
                    "channel_risk_mean": 0.72,
                    "repeat_template_rate": 0.61,
                    "recent_upload_velocity": 0.58,
                    "engagement_anomaly": 1.22,
                },
            ),
        )
    )

    assert any(
        entry.details is not None and "Top" in entry.details
        for entry in result.evidence
    )
    assert any(
        entry.details is not None and "fusion risk drops" in entry.details
        for entry in result.evidence
    )


def test_pipeline_supports_public_rss_sources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    rss_fixture = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
      <entry>
        <id>yt:video:public001</id>
        <title>Breaking orbital weather bulletin</title>
        <link rel="alternate" href="https://www.youtube.com/watch?v=public001" />
        <published>2026-03-22T12:00:00+00:00</published>
        <media:group>
          <media:description>Bulletin text with #weather and #orbit.</media:description>
        </media:group>
      </entry>
    </feed>
    """
    public_sources = [
        PublicSourceSpec(
            source_id="public-rss-source",
            source_url="https://www.youtube.com/feeds/videos.xml?channel_id=public",
            channel_name="Public RSS Source",
            channel_prior_flags=1,
        )
    ]

    result = run_pipeline(
        run_id="discovery-public-rss",
        build_id="build-public-rss",
        public_sources=public_sources,
        fetcher=lambda _url: rss_fixture,
    )

    manifest_path = repo_root() / "datasets" / "raw" / "source_manifests" / "discovery-public-rss.json"
    manifest = read_json(manifest_path)

    assert result["build_manifest"]["counts"]["train"] >= 0
    assert manifest["records"][0]["status"] == "collected"
    assert manifest["records"][0]["access_method"] == "public-rss"
