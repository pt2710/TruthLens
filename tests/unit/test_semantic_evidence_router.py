from __future__ import annotations

from typing import Any

from truthlens_model_serving.semantic_router import (
    AdaptiveSemanticEvidenceRouter,
    route_adjusted_mismatch,
)
from truthlens_shared_schemas.contracts import ChannelInfo, ScoreItemRequest


def _route(
    *,
    title: str,
    description: str | None = None,
    content_class: str = "unknown",
    confidence: float = 0.0,
    prior_flags: int = 0,
    history: dict[str, float] | None = None,
    feature_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = ScoreItemRequest(
        item_id="router-item",
        title=title,
        thumbnail_ref="https://example.com/thumb.jpg",
        description_snapshot=description,
        channel=ChannelInfo(
            channel_name="Aurora Beats",
            prior_flags=prior_flags,
            channel_history_features=history or {},
        ),
    )
    summary: dict[str, Any] = {
        "content_class": content_class,
        "content_class_confidence": confidence,
    }
    summary.update(feature_overrides or {})
    return AdaptiveSemanticEvidenceRouter().route(payload, summary).to_payload()


def test_genuine_instrumental_beat_routes_minimal_and_preserves_learning_capture() -> None:
    route = _route(
        title="Dark trap instrumental type beat",
        description="Stream links, credits, and producer notes.",
        content_class="music",
        confidence=0.91,
    )

    assert route["runtime_route"] == "minimal_creative"
    assert route["adversarial_guard"] == "clean"
    assert route["mismatch_pressure"] == "reduced"
    assert route["required_runtime_evidence"] == [
        "title",
        "channel_sanity",
        "light_spam_check",
    ]
    assert route["learning_capture_plan"] == "full_multimodal_capture"
    assert "description_snapshot" in route["preserved_learning_evidence"]
    assert "thumbnail_ref" in route["preserved_learning_evidence"]
    assert "feedback" in route["preserved_learning_evidence"]
    assert "verify_report_outcome" in route["preserved_learning_evidence"]


def test_album_cover_music_upload_routes_minimal_creative() -> None:
    route = _route(
        title="Moonlight Echoes album visualizer",
        description="Album credits, merch links, and streaming links.",
        content_class="music",
        confidence=0.88,
    )

    assert route["runtime_route"] == "minimal_creative"
    assert route["adversarial_guard"] == "clean"


def test_art_visualizer_routes_minimal_creative() -> None:
    route = _route(
        title="Digital art visualizer animation study",
        description="Artist notes and gallery context.",
        content_class="art",
        confidence=0.84,
    )

    assert route["runtime_route"] == "minimal_creative"
    assert route["content_class"] == "art"


def test_tutorial_routes_to_informational_consistency() -> None:
    route = _route(
        title="How to calibrate a telescope guide",
        description="Step-by-step tutorial with tools and safety notes.",
        content_class="commentary",
        confidence=0.79,
    )

    assert route["runtime_route"] == "informational_consistency"
    assert route["mismatch_pressure"] == "normal"
    assert "description" in route["required_runtime_evidence"]
    assert "thumbnail" in route["required_runtime_evidence"]


def test_documentary_and_news_keep_stronger_consistency_routes() -> None:
    documentary = _route(
        title="The history of telescope maintenance documentary",
        description="A sourced documentary explainer.",
        content_class="documentary",
        confidence=0.82,
    )
    news = _route(
        title="Breaking health officials confirmed new outbreak",
        description="News update with public-health claims.",
        content_class="news",
        confidence=0.86,
    )

    assert documentary["runtime_route"] in {
        "informational_consistency",
        "high_risk_factual",
    }
    assert news["runtime_route"] == "high_risk_factual"
    assert news["mismatch_pressure"] == "elevated"


def test_fake_news_disguised_as_music_does_not_receive_creative_discount() -> None:
    route = _route(
        title="Lo-fi hiphop instrumental - official government warning confirms bank collapse",
        description="Urgent official report says everyone must act now.",
        content_class="music",
        confidence=0.78,
    )

    assert route["runtime_route"] == "ambiguous_escalated"
    assert route["adversarial_guard"] == "triggered"
    assert route["mismatch_pressure"] != "reduced"


def test_negative_channel_history_escalates_creative_looking_title() -> None:
    route = _route(
        title="Free for profit beat - midnight piano instrumental",
        content_class="music",
        confidence=0.87,
        prior_flags=3,
        history={"channel_risk_mean": 0.71, "repeat_template_rate": 0.62, "trust_score": 2.4},
    )

    assert route["runtime_route"] == "ambiguous_escalated"
    assert route["adversarial_guard"] == "triggered"
    assert route["mismatch_pressure"] == "normal"


def test_scammy_description_escalates_creative_looking_title() -> None:
    route = _route(
        title="Boom bap instrumental type beat",
        description="Claim now through Telegram for a guaranteed profit crypto giveaway.",
        content_class="music",
        confidence=0.86,
    )

    assert route["runtime_route"] == "ambiguous_escalated"
    assert route["adversarial_guard"] == "triggered"


def test_sensational_thumbnail_features_escalate_creative_title_when_available() -> None:
    route = _route(
        title="Ambient visualizer animation loop",
        content_class="art",
        confidence=0.8,
        feature_overrides={"thumbnail_shock_indicator": 0.9, "thumbnail_text_density": 0.4},
    )

    assert route["runtime_route"] == "ambiguous_escalated"
    assert route["adversarial_guard"] == "triggered"


def test_low_confidence_title_routes_to_ambiguous_escalated() -> None:
    route = _route(
        title="Midnight signal update",
        description="Sparse context.",
        content_class="unknown",
        confidence=0.31,
    )

    assert route["runtime_route"] == "ambiguous_escalated"
    assert route["adversarial_guard"] == "triggered"


def test_route_adjusted_mismatch_reduces_only_clean_minimal_creative_pressure() -> None:
    minimal, minimal_guardrail = route_adjusted_mismatch(
        0.8,
        "music",
        {
            "runtime_route": "minimal_creative",
            "adversarial_guard": "clean",
            "mismatch_pressure": "reduced",
        },
    )
    guarded, guarded_guardrail = route_adjusted_mismatch(
        0.8,
        "music",
        {
            "runtime_route": "ambiguous_escalated",
            "adversarial_guard": "triggered",
            "mismatch_pressure": "normal",
        },
    )

    assert minimal < guarded
    assert minimal == 0.224
    assert guarded == 0.8
    assert minimal_guardrail == "semantic-route-minimal-creative-reduces-mismatch-pressure"
    assert guarded_guardrail == "semantic-route-normal-mismatch-pressure"
