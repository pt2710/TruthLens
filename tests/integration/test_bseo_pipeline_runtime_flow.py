from __future__ import annotations

from pathlib import Path

from truthlens_data_pipeline.paths import read_json, repo_root
from truthlens_feature_extractors import CONTENT_CLASSES
from truthlens_policy_engine import get_policy_profile, score_item
from truthlens_shared_schemas.contracts import ChannelInfo, ItemMetadata, ScoreItemRequest
from truthlens_trainer.pipeline import run_pipeline
from truthlens_trainer.simulate import main as simulate_main
from truthlens_trainer.train import main as train_main


def test_bseo_pipeline_runtime_flow(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    run_pipeline(run_id="integration-bseo-run", build_id="integration-bseo-build")
    train_main()
    simulate_main()

    annotation_batch = read_json(repo_root() / "datasets/labels/annotation_batches/latest.json")
    bseo_policy = read_json(repo_root() / "configs/thresholds/bseo-policy.json")
    simulation_report = read_json(repo_root() / "artifacts/eval_runs/integration-bseo-build-simulation.json")
    bseo_report = read_json(repo_root() / "artifacts/eval_runs/integration-bseo-build-bseo-report.json")
    mutation_bias_atlas = read_json(
        repo_root() / "artifacts/eval_runs/integration-bseo-build-mutation-bias-atlas.json"
    )

    assert annotation_batch["class_coverage"]
    assert annotation_batch["dominant_bias_coverage"]
    assert bseo_policy["policy_version"] == "bseo-control-policy-v1"
    assert "control_genome" in bseo_policy
    assert set(bseo_policy["control_genome"]["content_threshold_offsets"]) == set(CONTENT_CLASSES)
    assert set(bseo_policy["control_genome"]["mismatch_weight_by_class"]) == set(CONTENT_CLASSES)
    assert set(bseo_policy["control_genome"]["sensational_weight_by_class"]) == set(CONTENT_CLASSES)
    assert "channel_prior_temperature" in bseo_policy["control_genome"]
    assert "uncertainty_escalation_bias" in bseo_policy["control_genome"]
    assert simulation_report["bseo_search"]["policy_version"] == "bseo-control-policy-v1"
    assert bseo_report["policy_version"] == "bseo-control-policy-v1"
    assert mutation_bias_atlas["status"] in {"sparse", "clustered"}

    policy_profile = get_policy_profile()
    assert policy_profile["policy_mode"] == "bseo-shadow"
    assert policy_profile["resolved_policy_mode"] == "bseo-shadow"
    assert policy_profile["bseo_artifact"]["available"] is True
    assert policy_profile["bseo_artifact"]["compatible"] is True

    result = score_item(
        ScoreItemRequest(
            item_id="integration-bseo-score-item",
            title="Breaking orbital weather bulletin sparks urgent concern",
            thumbnail_ref=None,
            description_snapshot="A fast-moving news segment about orbital weather disruptions.",
            transcript_excerpt="The bulletin compares headline framing with the verified satellite timeline.",
            metadata=ItemMetadata(view_count=64000, like_count=3100),
            channel=ChannelInfo(
                channel_name="Orbital News Desk",
                prior_flags=2,
                channel_history_features={
                    "channel_risk_mean": 0.68,
                    "repeat_template_rate": 0.44,
                    "recent_upload_velocity": 0.57,
                    "engagement_anomaly": 1.14,
                    "taxonomy_hint_news": 0.92,
                },
            ),
        )
    )

    assert result.content_class != "unknown"
    assert result.bias_profile.guardrail_applied is not None
    assert any(entry.kind == "taxonomy" for entry in result.evidence)
    assert any(entry.kind == "bias" for entry in result.evidence)
