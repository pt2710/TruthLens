from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from truthlens_api.main import app
from truthlens_model_serving.scorer import ModelSignals
from truthlens_shared_schemas.contracts import (
    ItemMetadata,
    MobileResolvedWatchContext,
    ScoreResult,
)


client = TestClient(app)


def _mock_context(*, transcript_available: bool, transcript_excerpt: str | None) -> MobileResolvedWatchContext:
    return MobileResolvedWatchContext(
        target_url="https://www.youtube.com/watch?v=mobile123",
        video_id="mobile123",
        title="Exploring Places We Shouldn't - STAY OUT",
        thumbnail_ref="https://img.youtube.com/vi/mobile123/hqdefault.jpg",
        channel_name="Signal Watch",
        channel_url="https://www.youtube.com/@signalwatch",
        description_snapshot="An exploration teaser that leaves many details intentionally vague.",
        transcript_excerpt=transcript_excerpt,
        transcript_available=transcript_available,
        channel_context="TruthLens has already recorded 2 prior reported items for this channel.",
        metadata=ItemMetadata(duration_seconds=600, view_count=12000, like_count=900),
    )


def _mock_signals(*, music_likelihood: float, content_class: str = "unknown") -> ModelSignals:
    return ModelSignals(
        text_score=0.52,
        vision_score=0.61,
        metadata_score=0.48,
        history_score=0.33,
        anomaly_score=0.44,
        fusion_score=0.57,
        calibrated_score=0.57,
        confidence=0.84,
        uncertainty=0.16,
        model_version="baseline-v1-test",
        mode="trained",
        feature_summary={
            "music_likelihood": music_likelihood,
            "content_class": content_class,
            "content_class_confidence": 0.9 if content_class != "unknown" else 0.2,
        },
    )


def _mock_score_result(
    *,
    action: str,
    risk_score: float,
    confidence: float,
    uncertainty: float,
    content_class: str = "unknown",
    content_class_confidence: float = 0.0,
    negative_biases: list[str] | None = None,
) -> ScoreResult:
    return ScoreResult(
        risk_score=risk_score,
        confidence=confidence,
        uncertainty=uncertainty,
        content_class=content_class,
        content_class_confidence=content_class_confidence,
        bias_profile={
            "metrics": {},
            "positive_biases": [],
            "negative_biases": negative_biases or [],
            "guardrail_applied": None,
        },
        recommended_action=action,
        reasons=["Packaging appears overstated relative to the supporting context."],
        explanation_id="exp-mobile-1",
        explanation_summary="Packaging and context do not align cleanly.",
        evidence=[],
    )


def _mock_suggestion_payload(*, model_name: str) -> dict[str, object]:
    return {
        "issues": [
            {
                "issue_type": "thumbnail",
                "suggested": True,
                "comment": "The thumbnail uses danger-style framing that the supporting context does not clearly verify.",
            },
            {
                "issue_type": "title",
                "suggested": True,
                "comment": "The title uses warning language such as STAY OUT without substantiating that dramatic framing.",
            },
            {
                "issue_type": "description",
                "suggested": True,
                "comment": "The description stays vague and does not clearly explain the scenario implied by the packaging.",
            },
            {"issue_type": "transcript", "suggested": False, "comment": ""},
            {
                "issue_type": "channel",
                "suggested": True,
                "comment": "TruthLens has prior channel feedback indicating this packaging pattern is not isolated.",
            },
            {
                "issue_type": "other",
                "suggested": True,
                "comment": "The overall packaging relies on warning-based clickbait cues.",
            },
        ],
        "suggested_outcome": "moderate",
        "suggested_outcome_reason": "TruthLens recommends Moderate because the packaging overpromises.",
        "suggested_tags": [
            {
                "tag": "Clickbait",
                "selected": True,
                "confidence": 0.91,
                "rationale": "Report mode defaults to Clickbait.",
            }
        ],
        "suggestion_model": model_name,
    }


def test_mobile_analyze_share_returns_structured_payload_for_video_with_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "truthlens_api.main.resolve_mobile_share_context",
        lambda target_url: _mock_context(
            transcript_available=True,
            transcript_excerpt="The transcript calmly describes an abandoned structure and does not confirm imminent danger.",
        ),
    )
    monkeypatch.setattr("truthlens_api.main.predict_item_signals", lambda payload: _mock_signals(music_likelihood=0.12))
    monkeypatch.setattr(
        "truthlens_api.main.score_item",
        lambda payload: _mock_score_result(
            action="ask-report",
            risk_score=0.74,
            confidence=0.88,
            uncertainty=0.12,
            content_class="news",
            content_class_confidence=0.82,
            negative_biases=["sensational-overweighting"],
        ),
    )
    monkeypatch.setattr("truthlens_api.main.gemini_available", lambda: True)
    monkeypatch.setattr(
        "truthlens_api.main.suggest_manual_report",
        lambda payload: _mock_suggestion_payload(model_name="gemini-2.5-flash"),
    )
    monkeypatch.setattr(
        "truthlens_api.main.get_youtube_auth_status",
        lambda: {
            "configured": True,
            "connected": True,
            "auth_url": None,
            "channel_name": "Signal Watch",
        },
    )

    response = client.post(
        "/mobile/analyze-share",
        json={
            "target_url": "https://www.youtube.com/watch?v=mobile123",
            "user_context": {"strict_mode": False, "muted_channels": [], "prior_corrections": 0},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["watch_context"]["transcript_available"] is True
    assert payload["score"]["recommended_action"] == "ask-report"
    assert payload["review_prompt"]["workflow_mode"] == "report"
    assert payload["draft_suggestion"]["suggestion_model"] == "gemini-2.5-flash"
    assert len(payload["status_stream"]) == 5


def test_mobile_analyze_share_uses_heuristic_drafts_when_gemini_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_payload: dict[str, object] = {}

    monkeypatch.setattr(
        "truthlens_api.main.resolve_mobile_share_context",
        lambda target_url: _mock_context(transcript_available=False, transcript_excerpt=None),
    )
    monkeypatch.setattr("truthlens_api.main.predict_item_signals", lambda payload: _mock_signals(music_likelihood=0.05))
    monkeypatch.setattr(
        "truthlens_api.main.score_item",
        lambda payload: _mock_score_result(
            action="badge",
            risk_score=0.31,
            confidence=0.7,
            uncertainty=0.2,
            content_class="commentary",
            content_class_confidence=0.66,
        ),
    )
    monkeypatch.setattr("truthlens_api.main.gemini_available", lambda: False)
    monkeypatch.setattr(
        "truthlens_api.main._build_heuristic_suggestion_response",
        lambda payload: captured_payload.update(payload.model_dump()) or _mock_suggestion_payload(model_name="truthlens-heuristic-suggester-v1"),
    )
    monkeypatch.setattr(
        "truthlens_api.main.get_youtube_auth_status",
        lambda: {
            "configured": False,
            "connected": False,
            "auth_url": None,
            "channel_name": None,
        },
    )

    response = client.post(
        "/mobile/analyze-share",
        json={"target_url": "https://www.youtube.com/watch?v=mobile123"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["watch_context"]["transcript_available"] is False
    assert payload["draft_suggestion"]["suggestion_model"] == "truthlens-heuristic-suggester-v1"
    assert payload["youtube_auth"]["connected"] is False
    assert captured_payload["content_class"] == "commentary"
    assert captured_payload["content_class_confidence"] == pytest.approx(0.66, 0.001)


def test_mobile_analyze_share_recommends_verify_for_music_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "truthlens_api.main.resolve_mobile_share_context",
        lambda target_url: MobileResolvedWatchContext(
            target_url="https://www.youtube.com/watch?v=music123",
            video_id="music123",
            title="Moonlight Echoes (Official Audio)",
            thumbnail_ref="https://img.youtube.com/vi/music123/hqdefault.jpg",
            channel_name="Aurora Records",
            channel_url="https://www.youtube.com/@aurorarecords",
            description_snapshot="Official audio release for Moonlight Echoes.",
            transcript_excerpt="Verse one drifts into chorus and refrain under the city lights.",
            transcript_available=True,
            channel_context=None,
            metadata=ItemMetadata(duration_seconds=220, view_count=90000, like_count=4500),
        ),
    )
    monkeypatch.setattr(
        "truthlens_api.main.predict_item_signals",
        lambda payload: _mock_signals(music_likelihood=0.93, content_class="music"),
    )
    monkeypatch.setattr(
        "truthlens_api.main.score_item",
        lambda payload: _mock_score_result(
            action="none",
            risk_score=0.14,
            confidence=0.89,
            uncertainty=0.11,
            content_class="music",
            content_class_confidence=0.92,
        ),
    )
    monkeypatch.setattr("truthlens_api.main.gemini_available", lambda: False)
    monkeypatch.setattr(
        "truthlens_api.main._build_heuristic_suggestion_response",
        lambda payload: _mock_suggestion_payload(model_name="truthlens-heuristic-suggester-v1"),
    )
    monkeypatch.setattr(
        "truthlens_api.main.get_youtube_auth_status",
        lambda: {
            "configured": True,
            "connected": False,
            "auth_url": "http://127.0.0.1:8000/youtube/auth/start",
            "channel_name": None,
        },
    )

    response = client.post(
        "/mobile/analyze-share",
        json={"target_url": "https://www.youtube.com/watch?v=music123"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["watch_context"]["music_likelihood"] == pytest.approx(0.93, 0.001)
    assert payload["review_prompt"]["workflow_mode"] == "verify-transparent"
    assert payload["review_prompt"]["auto_open"] is True


def test_mobile_analyze_share_routes_satire_ambiguity_to_report_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "truthlens_api.main.resolve_mobile_share_context",
        lambda target_url: _mock_context(
            transcript_available=True,
            transcript_excerpt="The segment reads like a parody monologue rather than a literal alert.",
        ),
    )
    monkeypatch.setattr(
        "truthlens_api.main.predict_item_signals",
        lambda payload: _mock_signals(music_likelihood=0.02, content_class="satire"),
    )
    monkeypatch.setattr(
        "truthlens_api.main.score_item",
        lambda payload: _mock_score_result(
            action="badge",
            risk_score=0.29,
            confidence=0.71,
            uncertainty=0.31,
            content_class="satire",
            content_class_confidence=0.68,
            negative_biases=["genre-confusion"],
        ),
    )
    monkeypatch.setattr("truthlens_api.main.gemini_available", lambda: False)
    monkeypatch.setattr(
        "truthlens_api.main._build_heuristic_suggestion_response",
        lambda payload: _mock_suggestion_payload(model_name="truthlens-heuristic-suggester-v1"),
    )
    monkeypatch.setattr(
        "truthlens_api.main.get_youtube_auth_status",
        lambda: {
            "configured": False,
            "connected": False,
            "auth_url": None,
            "channel_name": None,
        },
    )

    response = client.post(
        "/mobile/analyze-share",
        json={"target_url": "https://www.youtube.com/watch?v=mobile123"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["review_prompt"]["workflow_mode"] == "report"
    assert payload["review_prompt"]["label"] == "Review ambiguity"


def test_mobile_analyze_share_rejects_invalid_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "truthlens_api.main.resolve_mobile_share_context",
        lambda target_url: (_ for _ in ()).throw(ValueError("Could not determine a YouTube video id from the shared URL.")),
    )

    response = client.post(
        "/mobile/analyze-share",
        json={"target_url": "https://example.com/not-youtube"},
    )

    assert response.status_code == 400
    assert "video id" in response.json()["detail"].lower()
