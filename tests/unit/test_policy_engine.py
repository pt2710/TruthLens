from pathlib import Path
from collections import Counter
import json

import pytest

from truthlens_explanation_engine.explainer import ExplanationBundle
from truthlens_feature_extractors.image import make_test_png_bytes
from truthlens_model_serving import append_feedback_event
from truthlens_model_serving.scorer import ModelSignals, predict_item_signals
from truthlens_model_serving.registry import ARCHITECTURE_PLAN_VERSION, HEAD_SPEC_VERSION
from truthlens_policy_engine import get_policy_profile, score_item
from truthlens_shared_schemas.contracts import ChannelInfo, ItemMetadata, ScoreItemRequest


def _payload(channel_name: str) -> ScoreItemRequest:
    return ScoreItemRequest(
        item_id="bias-item",
        title="Breaking shocking aliens confirmed",
        thumbnail_ref=None,
        transcript_excerpt="A calm review of telescope maintenance and launch scheduling.",
        metadata=ItemMetadata(),
        channel=ChannelInfo(channel_name=channel_name, prior_flags=3, channel_history_features={}),
    )


def _rank(action: str) -> int:
    return {
        "none": 0,
        "badge": 1,
        "blur": 2,
        "ask-report": 3,
        "hide": 4,
    }[action]


def _reset_runtime_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "truthlens_policy_engine.engine._POLICY_RUNTIME_STATS",
        {
            "total_decisions": 0,
            "threshold_decisions": 0,
            "bseo_live_decisions": 0,
            "bseo_shadow_evaluations": 0,
            "bseo_shadow_divergences": 0,
            "bseo_fallbacks": 0,
            "rl_live_decisions": 0,
            "rl_shadow_evaluations": 0,
            "rl_shadow_divergences": 0,
            "rl_fallbacks": 0,
            "final_action_counts": {action: 0 for action in ["none", "badge", "blur", "ask-report", "hide"]},
            "threshold_action_counts": {action: 0 for action in ["none", "badge", "blur", "ask-report", "hide"]},
            "rl_action_counts": {action: 0 for action in ["none", "badge", "blur", "ask-report", "hide"]},
            "fallback_reasons": Counter(),
        },
    )


def _mock_signals(*, score: float, confidence: float, uncertainty: float) -> ModelSignals:
    return ModelSignals(
        text_score=score,
        vision_score=score,
        metadata_score=score,
        history_score=score,
        anomaly_score=score,
        fusion_score=score,
        calibrated_score=score,
        confidence=confidence,
        uncertainty=uncertainty,
        model_version="baseline-v1-test",
        mode="trained",
        feature_summary={
            "content_class": "news",
            "content_class_confidence": 0.86,
            "transcript_mismatch_score": 0.74,
            "token_hits": 3.0,
            "channel_risk_mean": 0.72,
            "repeat_template_rate": 0.61,
            "bias_primitives": {
                "sensational_weight": 0.72,
                "crossmodal_rigidity": 0.74,
                "channel_prior_dependency": 0.68,
                "genre_confusion": 0.12,
                "uncertainty_calibration": 0.08,
            },
            "bias_profile": {
                "metrics": {
                    "sensational_weight": 0.72,
                    "crossmodal_rigidity": 0.74,
                    "channel_prior_dependency": 0.68,
                    "genre_confusion": 0.12,
                    "uncertainty_calibration": 0.08,
                },
                "positive_biases": ["factual-scrutiny"],
                "negative_biases": ["channel-lock-in-risk"],
                "guardrail_applied": "factual-context-amplifies-mismatch",
            },
        },
    )


def _mock_explanation(*_args, **_kwargs) -> ExplanationBundle:
    return ExplanationBundle(
        explanation_id="exp-policy-test",
        summary="Policy explanation summary.",
        reasons=["Policy explanation reason."],
        evidence=[],
    )


def _write_bseo_policy(thresholds_dir: Path, *, build_id: str) -> None:
    (thresholds_dir / "bseo-policy.json").write_text(
        json.dumps(
            {
                "policy_version": "bseo-control-policy-v1",
                "generated_at": "2026-04-02T09:00:00+00:00",
                "build_id": build_id,
                "head_spec_version": HEAD_SPEC_VERSION,
                "architecture_plan_version": ARCHITECTURE_PLAN_VERSION,
                "recommended_thresholds": {
                    "badge_threshold": 0.18,
                    "blur_threshold": 0.36,
                    "report_prompt_threshold": 0.52,
                    "hide_threshold": 0.62,
                },
                "control_genome": {
                    "global_thresholds": {
                        "badge_threshold": 0.18,
                        "blur_threshold": 0.36,
                        "report_prompt_threshold": 0.52,
                        "hide_threshold": 0.62,
                    },
                    "content_threshold_offsets": {
                        "news": -0.04,
                        "commentary": -0.02,
                        "documentary": -0.03,
                        "music": 0.08,
                        "art": 0.06,
                        "satire": 0.03,
                        "gaming": 0.02,
                        "promo": -0.03,
                        "unknown": 0.0,
                    },
                    "mismatch_weight_by_class": {
                        "news": 1.16,
                        "commentary": 1.05,
                        "documentary": 1.12,
                        "music": 0.72,
                        "art": 0.8,
                        "satire": 0.9,
                        "gaming": 0.94,
                        "promo": 1.08,
                        "unknown": 1.0,
                    },
                    "sensational_weight_by_class": {
                        "news": 1.12,
                        "commentary": 1.02,
                        "documentary": 1.04,
                        "music": 0.84,
                        "art": 0.86,
                        "satire": 0.92,
                        "gaming": 0.96,
                        "promo": 1.1,
                        "unknown": 1.0,
                    },
                    "channel_prior_temperature": 1.08,
                    "uncertainty_escalation_bias": 1.02,
                },
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )


def test_channel_feedback_bias_makes_policy_more_aggressive(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    baseline = score_item(_payload("Bias Channel"))

    for index in range(3):
        append_feedback_event(
            {
                "item_id": f"bias-{index}",
                "item_hash": None,
                "channel_name": "Bias Channel",
                "model_version": "test-model",
                "policy_version": "test-policy",
                "action_shown": "badge",
                "user_action": "report",
                "explanation_id": None,
                "before_score": 0.55,
                "after_score": 0.78,
                "timestamp": f"2026-03-23T10:0{index}:00Z",
            }
        )

    adjusted = score_item(_payload("Bias Channel"))

    assert adjusted.risk_score == baseline.risk_score
    assert _rank(adjusted.recommended_action) >= _rank(baseline.recommended_action)


def test_unknown_channel_feedback_bias_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    baseline = score_item(_payload("Unknown channel"))

    for index in range(3):
        append_feedback_event(
            {
                "item_id": f"unknown-{index}",
                "item_hash": None,
                "channel_name": "Unknown channel",
                "model_version": "test-model",
                "policy_version": "test-policy",
                "action_shown": "badge",
                "user_action": "report",
                "explanation_id": None,
                "before_score": 0.55,
                "after_score": 0.78,
                "timestamp": f"2026-03-23T10:1{index}:00Z",
            }
        )

    adjusted = score_item(_payload("Unknown channel"))

    assert adjusted.risk_score == baseline.risk_score
    assert adjusted.recommended_action == baseline.recommended_action


def test_policy_profile_loads_bandit_adjustments(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    thresholds_dir = tmp_path / "configs" / "thresholds"
    thresholds_dir.mkdir(parents=True, exist_ok=True)
    (thresholds_dir / "contextual-bandit.json").write_text(
        json.dumps(
            {
                "badge_threshold_offset": 0.01,
                "blur_threshold_offset": -0.01,
                "report_prompt_threshold_offset": 0.02,
                "hide_threshold_offset": 0.03,
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    profile = get_policy_profile()

    assert profile["bandit_adjustments"]["hide_threshold_offset"] == 0.03


def test_score_item_surfaces_verification_and_policy_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "truthlens_policy_engine.engine.predict_item_signals",
        lambda _payload: _mock_signals(score=0.67, confidence=0.74, uncertainty=0.38),
    )
    monkeypatch.setattr(
        "truthlens_policy_engine.engine.build_explanation",
        _mock_explanation,
    )
    monkeypatch.setattr(
        "truthlens_policy_engine.engine.get_policy_profile",
        lambda: {
            "policy_version": "adaptive-threshold-v1",
            "policy_mode": "bseo-shadow",
            "resolved_policy_mode": "bseo-shadow",
            "effective_thresholds": {
                "badge_threshold": 0.2,
                "blur_threshold": 0.45,
                "report_prompt_threshold": 0.65,
                "hide_threshold": 0.8,
            },
            "runtime_policy_config": {
                "policy_mode": "bseo-shadow",
                "resolved_policy_mode": "bseo-shadow",
                "bseo_min_confidence": 0.58,
                "bseo_max_uncertainty": 0.45,
                "bseo_artifact_max_age_hours": 168,
            },
            "bseo_artifact": {
                "status": "compatible",
                "build_id": "build-bseo-shadow",
            },
        },
    )
    monkeypatch.setattr(
        "truthlens_policy_engine.engine.load_model_info",
        lambda: {
            "model_version": "baseline-v1-test",
            "build_id": "build-model-test",
        },
    )

    result = score_item(
        ScoreItemRequest(
            item_id="verification-item",
            title="Breaking shocking aliens confirmed",
            transcript_excerpt="A calm review of telescope maintenance and launch scheduling.",
            channel=ChannelInfo(channel_name="Verification Channel", prior_flags=3),
            runtime_context={"surface": "mobile-share", "review_requested": True},
        )
    )

    assert result.verification.status == "completed"
    assert "review-flow" in result.verification.triggers
    assert result.action_decision_basis.verification_considered is True
    assert result.policy_mode == "bseo-shadow"
    assert result.artifact_provenance.model_build_id == "build-model-test"


def test_policy_profile_loads_evolutionary_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    thresholds_dir = tmp_path / "configs" / "thresholds"
    thresholds_dir.mkdir(parents=True, exist_ok=True)
    (thresholds_dir / "evolutionary-search.json").write_text(
        json.dumps(
            {
                "best_thresholds": {
                    "badge_threshold": 0.33,
                    "blur_threshold": 0.57,
                    "report_prompt_threshold": 0.79,
                    "hide_threshold": 0.9,
                },
                "best_fitness": 1.14,
                "population_size": 12,
                "generations": 4,
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    profile = get_policy_profile()

    assert profile["evolutionary_search"]["best_thresholds"]["badge_threshold"] == 0.33


def test_policy_profile_exposes_runtime_bseo_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    _reset_runtime_stats(monkeypatch)
    thresholds_dir = tmp_path / "configs" / "thresholds"
    thresholds_dir.mkdir(parents=True, exist_ok=True)
    (thresholds_dir / "runtime-policy.json").write_text(
        json.dumps(
            {
                "policy_mode": "bseo-shadow",
                "bseo_min_confidence": 0.55,
                "bseo_max_uncertainty": 0.45,
                "bseo_artifact_max_age_hours": 72,
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    _write_bseo_policy(thresholds_dir, build_id="build-test-latest")

    profile = get_policy_profile()

    assert profile["policy_mode"] == "bseo-shadow"
    assert profile["policy_version"] == "bseo-control-policy-v1-shadow"
    assert profile["bseo_artifact"]["available"] is True
    assert profile["bseo_artifact"]["compatible"] is True
    assert profile["rl_artifact"]["available"] is True
    assert profile["resolved_policy_mode"] == "bseo-shadow"
    assert profile["runtime_metrics"]["total_decisions"] == 0


def test_runtime_defaults_now_start_in_bseo_shadow_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    profile = get_policy_profile()

    assert profile["policy_mode"] == "bseo-shadow"
    assert profile["resolved_policy_mode"] == "bseo-shadow"


def test_rl_policy_modes_remain_supported_as_bseo_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    thresholds_dir = tmp_path / "configs" / "thresholds"
    thresholds_dir.mkdir(parents=True, exist_ok=True)
    (thresholds_dir / "runtime-policy.json").write_text(
        json.dumps({"policy_mode": "rl-live"}, ensure_ascii=True),
        encoding="utf-8",
    )
    _write_bseo_policy(thresholds_dir, build_id="build-alias")

    profile = get_policy_profile()

    assert profile["policy_mode"] == "rl-live"
    assert profile["resolved_policy_mode"] == "bseo-live"


def test_bseo_shadow_logs_divergence_without_changing_user_action(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    _reset_runtime_stats(monkeypatch)
    thresholds_dir = tmp_path / "configs" / "thresholds"
    thresholds_dir.mkdir(parents=True, exist_ok=True)
    (thresholds_dir / "runtime-policy.json").write_text(
        json.dumps(
            {
                "policy_mode": "bseo-shadow",
                "bseo_min_confidence": 0.5,
                "bseo_max_uncertainty": 0.5,
                "bseo_artifact_max_age_hours": 400,
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    _write_bseo_policy(thresholds_dir, build_id="build-bseo-shadow")
    monkeypatch.setattr("truthlens_policy_engine.engine.predict_item_signals", lambda payload: _mock_signals(score=0.30, confidence=0.91, uncertainty=0.10))
    monkeypatch.setattr("truthlens_policy_engine.engine.build_explanation", _mock_explanation)

    result = score_item(_payload("Shadow Channel"))
    profile = get_policy_profile()

    assert result.recommended_action == "none"
    assert profile["runtime_metrics"]["bseo_shadow_evaluations"] == 1
    assert profile["runtime_metrics"]["bseo_shadow_divergences"] == 1
    assert profile["runtime_metrics"]["rl_shadow_evaluations"] == 1
    assert profile["runtime_metrics"]["rl_shadow_divergences"] == 1
    assert profile["runtime_metrics"]["rl_live_decisions"] == 0


def test_bseo_live_uses_bseo_action_when_guardrails_pass(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    _reset_runtime_stats(monkeypatch)
    thresholds_dir = tmp_path / "configs" / "thresholds"
    thresholds_dir.mkdir(parents=True, exist_ok=True)
    (thresholds_dir / "runtime-policy.json").write_text(
        json.dumps(
            {
                "policy_mode": "bseo-live",
                "bseo_min_confidence": 0.5,
                "bseo_max_uncertainty": 0.5,
                "bseo_artifact_max_age_hours": 400,
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    _write_bseo_policy(thresholds_dir, build_id="build-bseo-live")
    monkeypatch.setattr("truthlens_policy_engine.engine.predict_item_signals", lambda payload: _mock_signals(score=0.30, confidence=0.91, uncertainty=0.10))
    monkeypatch.setattr("truthlens_policy_engine.engine.build_explanation", _mock_explanation)

    result = score_item(_payload("Live Channel"))
    profile = get_policy_profile()

    assert result.recommended_action == "hide"
    assert profile["runtime_metrics"]["bseo_live_decisions"] == 1
    assert profile["runtime_metrics"]["rl_live_decisions"] == 1
    assert profile["runtime_metrics"]["final_action_counts"]["hide"] == 1


def test_bseo_live_falls_back_to_threshold_policy_when_uncertainty_is_high(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    _reset_runtime_stats(monkeypatch)
    thresholds_dir = tmp_path / "configs" / "thresholds"
    thresholds_dir.mkdir(parents=True, exist_ok=True)
    (thresholds_dir / "runtime-policy.json").write_text(
        json.dumps(
            {
                "policy_mode": "bseo-live",
                "bseo_min_confidence": 0.5,
                "bseo_max_uncertainty": 0.2,
                "bseo_artifact_max_age_hours": 400,
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    _write_bseo_policy(thresholds_dir, build_id="build-bseo-live")
    monkeypatch.setattr("truthlens_policy_engine.engine.predict_item_signals", lambda payload: _mock_signals(score=0.30, confidence=0.91, uncertainty=0.40))
    monkeypatch.setattr("truthlens_policy_engine.engine.build_explanation", _mock_explanation)

    result = score_item(_payload("Fallback Channel"))
    profile = get_policy_profile()

    assert result.recommended_action == "none"
    assert profile["runtime_metrics"]["bseo_live_decisions"] == 0
    assert profile["runtime_metrics"]["bseo_fallbacks"] == 1
    assert profile["runtime_metrics"]["rl_live_decisions"] == 0
    assert profile["runtime_metrics"]["rl_fallbacks"] == 1
    assert profile["runtime_metrics"]["fallback_reasons"]["high-uncertainty"] == 1


def test_remote_thumbnail_bytes_influence_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_urls: list[str] = []

    class _MockRemoteImageResponse:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return self._payload

        def __enter__(self) -> "_MockRemoteImageResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    image_payloads = {
        "https://example.com/thumb-a.png": make_test_png_bytes((240, 80, 60)),
        "https://example.com/thumb-b.png": make_test_png_bytes((30, 180, 220)),
    }

    def fake_urlopen(url: str, timeout: float = 0.0) -> _MockRemoteImageResponse:
        seen_urls.append(url)
        return _MockRemoteImageResponse(image_payloads[url])

    monkeypatch.setattr("truthlens_model_serving.scorer.urlopen", fake_urlopen)

    base_payload = _payload("Remote Thumb Channel")
    score_a = predict_item_signals(
        base_payload.model_copy(
            update={"thumbnail_ref": "https://example.com/thumb-a.png"}
        )
    )
    score_b = predict_item_signals(
        base_payload.model_copy(
            update={"thumbnail_ref": "https://example.com/thumb-b.png"}
        )
    )

    assert seen_urls.count("https://example.com/thumb-a.png") >= 1
    assert seen_urls.count("https://example.com/thumb-b.png") >= 1
    assert score_a.feature_summary["thumbnail_byte_size"] > 0
    assert score_b.feature_summary["thumbnail_byte_size"] > 0
