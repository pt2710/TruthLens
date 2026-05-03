from fastapi.testclient import TestClient
import json
import pytest
from pathlib import Path

from truthlens_api.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_info_endpoints() -> None:
    model_response = client.get("/model-info")
    policy_response = client.get("/policy-info")
    ready_response = client.get("/ready")

    assert model_response.status_code == 200
    assert "mode" in model_response.json()
    assert "artifact_status" in model_response.json()
    assert "head_specs" in model_response.json()
    assert "architecture_layers" in model_response.json()
    assert "architecture_plan_version" in model_response.json()
    assert "text_encoder_resolution" in model_response.json()
    assert "vision_encoder_resolution" in model_response.json()
    assert "history_encoder_resolution" in model_response.json()

    assert policy_response.status_code == 200
    assert "effective_thresholds" in policy_response.json()
    assert "policy_mode" in policy_response.json()
    assert "runtime_metrics" in policy_response.json()
    assert "bseo_artifact" in policy_response.json()
    assert "rl_artifact" in policy_response.json()
    assert ready_response.status_code == 200
    assert "ready" in ready_response.json()


def test_cors_preflight_is_accepted_for_batch_score() -> None:
    response = client.options(
        "/batch-score",
        headers={
            "Origin": "https://www.youtube.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://www.youtube.com"


def test_score_item_contract() -> None:
    response = client.post(
        "/score-item",
        json={
            "item_id": "item-1",
            "title": "Breaking aliens confirmed",
            "thumbnail_ref": None,
            "metadata": {},
            "channel": {
                "channel_name": "TruthLens Test",
                "prior_flags": 1,
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert {
        "risk_score",
        "fused_score",
        "calibrated_score",
        "confidence",
        "uncertainty",
        "uncertainty_bucket",
        "path_scores",
        "path_contributors",
        "content_class",
        "content_class_confidence",
        "semantic_evidence_route",
        "bias_profile",
        "verification",
        "action_decision_basis",
        "policy_mode",
        "resolved_policy_mode",
        "artifact_provenance",
        "recommended_action",
        "reasons",
        "explanation_id",
        "explanation_summary",
        "evidence",
    }.issubset(payload.keys())
    assert payload["semantic_evidence_route"]["runtime_route"] in {
        "minimal_creative",
        "informational_consistency",
        "high_risk_factual",
        "ambiguous_escalated",
    }
    assert payload["semantic_evidence_route"]["learning_capture_plan"] == "full_multimodal_capture"
    assert "metrics" in payload["bias_profile"]
    assert "status" in payload["verification"]
    assert "threshold_action" in payload["action_decision_basis"]
    if payload["recommended_action"] != "none":
        assert payload["reasons"]
        assert payload["explanation_id"]
        assert payload["explanation_summary"]
        assert payload["evidence"]


def test_score_endpoint_writes_audit_event(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    response = client.post(
        "/score-item",
        json={
            "item_id": "audit-item-1",
            "title": "Breaking aliens confirmed",
            "thumbnail_ref": None,
            "metadata": {},
            "channel": {
                "channel_name": "Audit Channel",
                "prior_flags": 1,
            },
        },
    )

    assert response.status_code == 200
    audit_path = tmp_path / "artifacts" / "reports" / "score_events.jsonl"
    assert audit_path.exists()
    payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["item_id"] == "audit-item-1"
    assert payload["channel_name"] == "Audit Channel"
    assert "model_version" in payload
    assert "policy_version" in payload
    assert payload["content_class"] == "news"
    assert "content_class_confidence" in payload
    assert payload["semantic_evidence_route"]["runtime_route"] == "high_risk_factual"


def test_clean_minimal_creative_skips_remote_thumbnail_fetch_and_preserves_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("clean minimal creative route should not fetch remote thumbnail bytes")

    monkeypatch.setattr("truthlens_model_serving.scorer.urlopen", fail_if_called)

    response = client.post(
        "/score-item",
        json={
            "item_id": "creative-route-item-1",
            "title": "Dark trap instrumental type beat",
            "thumbnail_ref": "https://example.com/thumb.jpg",
            "description_snapshot": "Producer credits, streaming links, and artist notes.",
            "metadata": {},
            "channel": {
                "channel_name": "Aurora Beats",
                "prior_flags": 0,
                "channel_history_features": {
                    "music_likelihood": 0.95,
                    "title_music_signal": 1.0,
                    "channel_music_signal": 1.0,
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    route = payload["semantic_evidence_route"]
    assert route["runtime_route"] == "minimal_creative"
    assert route["adversarial_guard"] == "clean"
    assert route["mismatch_pressure"] == "reduced"
    assert "thumbnail_ref" in route["preserved_learning_evidence"]
    assert "description_snapshot" in route["preserved_learning_evidence"]


def test_feedback_endpoint_accepts_event() -> None:
    response = client.post(
        "/feedback",
        json={
            "item_id": "item-1",
            "item_hash": None,
            "channel_name": "TruthLens Test",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "action_shown": "badge",
            "user_action": "not-misleading",
            "explanation_id": None,
            "before_score": 0.61,
            "after_score": 0.32,
            "timestamp": "2026-03-23T10:00:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert Path("artifacts/reports/feedback_events.sqlite3").exists()


def test_feedback_endpoint_persists_manual_report_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    response = client.post(
        "/feedback",
        json={
            "item_id": "item-manual-report",
            "item_hash": None,
            "channel_name": "TruthLens Test",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "action_shown": "ask-report",
            "user_action": "confirm-report",
            "explanation_id": "exp-manual-1",
            "before_score": 0.81,
            "after_score": 0.81,
            "timestamp": "2026-03-23T10:00:00Z",
            "manual_report": {
                "target_url": "https://www.youtube.com/watch?v=item-manual-report",
                "thumbnail_ref": "https://img.youtube.com/vi/item-manual-report/default.jpg",
                "title_snapshot": "Secret lab leak footage",
                "transcript_excerpt": "Transcript claims a secret lab leak without support.",
                "issues": [
                    {
                        "issue_type": "title",
                        "comment": "The title states the claim as a confirmed fact.",
                        "original_comment": "Title is misleading.",
                    }
                ],
                "requested_outcome": "moderate",
                "optimize_requested": True,
                "optimize_applied": True,
                "optimization_model": "gemini-2.5-flash",
                "report_text": "The title presents an unsupported claim as confirmed fact.",
            },
        },
    )

    assert response.status_code == 200
    log_path = tmp_path / "artifacts" / "reports" / "feedback_events.jsonl"
    db_path = tmp_path / "artifacts" / "reports" / "feedback_events.sqlite3"
    assert log_path.exists()
    assert db_path.exists()
    stored_payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert stored_payload["manual_report"]["issues"][0]["issue_type"] == "title"
    assert stored_payload["manual_report"]["optimize_applied"] is True


def test_manual_report_optimize_endpoint_returns_503_without_gemini_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("truthlens_api.main.settings.gemini_api_key", None)

    response = client.post(
        "/manual-report/optimize",
        json={
            "target_url": "https://www.youtube.com/watch?v=item-manual-report",
            "title_snapshot": "Secret lab leak footage",
            "channel_name": "Signal Watch",
            "transcript_excerpt": "Transcript claims a secret lab leak without support.",
            "requested_outcome": "moderate",
            "issues": [
                {
                    "issue_type": "title",
                    "comment": "The title states the claim as a confirmed fact.",
                }
            ],
        },
    )

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"].lower()


def test_manual_report_optimize_endpoint_returns_structured_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("truthlens_api.main.settings.gemini_api_key", "test-key")
    monkeypatch.setattr(
        "truthlens_api.main.optimize_manual_report",
        lambda payload: {
            "issues": [
                {
                    "issue_type": "title",
                    "comment": "The title presents the allegation as established fact.",
                }
            ],
            "optimization_model": "gemini-2.5-flash",
            "report_text": "The title frames an unverified allegation as confirmed fact.",
        },
    )

    response = client.post(
        "/manual-report/optimize",
        json={
            "target_url": "https://www.youtube.com/watch?v=item-manual-report",
            "title_snapshot": "Secret lab leak footage",
            "channel_name": "Signal Watch",
            "transcript_excerpt": "Transcript claims a secret lab leak without support.",
            "requested_outcome": "moderate",
            "issues": [
                {
                    "issue_type": "title",
                    "comment": "The title states the claim as a confirmed fact.",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["optimization_model"] == "gemini-2.5-flash"
    assert payload["issues"][0]["issue_type"] == "title"
    assert "confirmed fact" in payload["report_text"]


def test_manual_report_suggest_endpoint_returns_heuristic_payload_without_gemini_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("truthlens_api.main.settings.gemini_api_key", None)

    response = client.post(
        "/manual-report/suggest",
        json={
            "target_url": "https://www.youtube.com/watch?v=item-manual-report",
            "title_snapshot": "Secret lab leak footage",
            "channel_name": "Signal Watch",
            "transcript_excerpt": "Transcript claims a secret lab leak without support.",
            "explanation_summary": "The title and thumbnail appear weakly aligned.",
            "reasons": ["Title contains sensational framing patterns."],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggestion_model"] == "truthlens-heuristic-fallback-v1"
    assert payload["suggested_outcome_reason"]
    assert payload["suggested_tags"][0]["tag"] == "Clickbait"


def test_manual_report_suggest_endpoint_returns_structured_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("truthlens_api.main.settings.gemini_api_key", "test-key")
    monkeypatch.setattr(
        "truthlens_api.main.suggest_manual_report",
        lambda payload: {
            "issues": [
                {
                    "issue_type": "thumbnail",
                    "suggested": True,
                    "comment": "The thumbnail framing appears disconnected from the stated topic.",
                },
                {
                    "issue_type": "title",
                    "suggested": True,
                    "comment": "The title overstates certainty relative to the available context.",
                },
                {"issue_type": "description", "suggested": False, "comment": ""},
                {"issue_type": "transcript", "suggested": False, "comment": ""},
                {"issue_type": "channel", "suggested": False, "comment": ""},
                {"issue_type": "other", "suggested": True, "comment": "The packaging resembles clickbait."},
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
            "suggestion_model": "gemini-2.5-flash",
        },
    )

    response = client.post(
        "/manual-report/suggest",
        json={
            "target_url": "https://www.youtube.com/watch?v=item-manual-report",
            "title_snapshot": "Secret lab leak footage",
            "channel_name": "Signal Watch",
            "transcript_excerpt": "Transcript claims a secret lab leak without support.",
            "explanation_summary": "The title and thumbnail appear weakly aligned.",
            "reasons": ["Title contains sensational framing patterns."],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggested_outcome"] == "moderate"
    assert payload["suggested_outcome_reason"]
    assert payload["suggestion_model"] == "gemini-2.5-flash"
    assert len(payload["issues"]) == 6
    assert payload["suggested_tags"][0]["tag"] == "Clickbait"
    assert payload["issues"][0]["issue_type"] == "thumbnail"


def test_model_info_exposes_current_and_planned_architecture_layers() -> None:
    response = client.get("/model-info")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["architecture_layers"], list)
    assert any(layer["status"] == "implemented" for layer in payload["architecture_layers"])
    assert any(layer["status"] == "planned" for layer in payload["architecture_layers"])
    assert any(layer["layer_type"] == "llm-assist" for layer in payload["architecture_layers"])
    assert any(head["name"] == "anomaly" for head in payload["head_specs"])
    assert payload["vision_encoder_resolution"]["actual_encoder"] in {
        "vision-transformer",
        "tiny-cnn-thumbnail",
        "vision-v2",
    }
    assert payload["history_encoder_resolution"]["actual_encoder"] in {
        "lstm-sequence",
        "sequence-summary-v1",
    }
    assert payload["text_encoder_resolution"]["requested_encoder"] in {
        "sentence-transformer",
        "count-vectorizer-bigrams",
    }


def test_youtube_auth_status_endpoint_reports_missing_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "truthlens_api.main.get_youtube_auth_status",
        lambda: {
            "configured": False,
            "connected": False,
            "auth_url": None,
            "channel_name": None,
            "direct_reporting_supported": False,
            "direct_reporting_detail": "YouTube OAuth is not configured.",
        },
    )

    response = client.get("/youtube/auth/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is False
    assert payload["connected"] is False
    assert payload["direct_reporting_supported"] is False


def test_youtube_report_endpoint_returns_503_without_oauth_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("truthlens_api.main.youtube_reporting_configured", lambda: False)

    response = client.post(
        "/youtube/report",
        json={
            "target_url": "https://www.youtube.com/watch?v=item-manual-report",
            "report_text": "Please review this video for misleading framing.",
            "issue_types": ["title", "thumbnail"],
        },
    )

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"].lower()


def test_youtube_report_endpoint_returns_reported_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("truthlens_api.main.youtube_reporting_configured", lambda: True)
    monkeypatch.setattr(
        "truthlens_api.main.submit_youtube_report",
        lambda payload: {
            "status": "reported",
            "reason_id": "MISLEADING",
            "reason_label": "Spam or misleading",
            "secondary_reason_id": "CLICKBAIT",
            "secondary_reason_label": "Misleading metadata",
        },
    )

    response = client.post(
        "/youtube/report",
        json={
            "target_url": "https://www.youtube.com/watch?v=item-manual-report",
            "report_text": "Please review this video for misleading framing.",
            "issue_types": ["title", "thumbnail"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "reported"
    assert payload["reason_label"] == "Spam or misleading"


def test_youtube_report_endpoint_returns_409_when_direct_reporting_is_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from truthlens_api.youtube_reporting import YouTubeDirectReportingUnsupportedError

    monkeypatch.setattr("truthlens_api.main.youtube_reporting_configured", lambda: True)

    def _raise(payload):
        raise YouTubeDirectReportingUnsupportedError(
            "YouTube did not return a suitable 'Spam or misleading' report category for this account."
        )

    monkeypatch.setattr("truthlens_api.main.submit_youtube_report", _raise)

    response = client.post(
        "/youtube/report",
        json={
            "target_url": "https://www.youtube.com/watch?v=item-manual-report",
            "report_text": "Please review this video for misleading framing.",
            "issue_types": ["title", "thumbnail"],
        },
    )

    assert response.status_code == 409
    assert "spam or misleading" in response.json()["detail"].lower()


def test_feedback_summary_endpoint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    client.post(
        "/score-item",
        json={
            "item_id": "item-1",
            "title": "Breaking aliens confirmed",
            "thumbnail_ref": None,
            "metadata": {},
            "channel": {
                "channel_name": "Signal Watch",
                "prior_flags": 1,
            },
        },
    )
    client.post(
        "/feedback",
        json={
            "item_id": "item-1",
            "item_hash": None,
            "channel_name": "Signal Watch",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "action_shown": "badge",
            "user_action": "report",
            "explanation_id": None,
            "before_score": 0.61,
            "after_score": 0.81,
            "timestamp": "2026-03-23T10:00:00Z",
        },
    )
    client.post(
        "/feedback",
        json={
            "item_id": "item-2",
            "item_hash": None,
            "channel_name": "Signal Watch",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "action_shown": "blur",
            "user_action": "not-misleading",
            "explanation_id": None,
            "before_score": 0.55,
            "after_score": 0.21,
            "timestamp": "2026-03-23T10:05:00Z",
        },
    )

    response = client.get("/feedback-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_events"] == 2
    assert payload["action_counts"]["report"] == 1
    assert payload["action_counts"]["not-misleading"] == 1
    assert payload["top_channels"][0]["channel_name"] == "Signal Watch"
    assert payload["top_channels"][0]["scored_item_count"] == 1
    assert "trust_score" in payload["top_channels"][0]


def test_metrics_endpoint_exposes_score_and_feedback_counters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    monkeypatch.setattr("truthlens_api.main._REQUEST_COUNTS", {})
    monkeypatch.setattr("truthlens_api.main._REQUEST_WINDOWS", {})

    client.post(
        "/score-item",
        json={
            "item_id": "metrics-item-1",
            "title": "Breaking aliens confirmed",
            "thumbnail_ref": None,
            "metadata": {},
            "channel": {
                "channel_name": "Metrics Channel",
                "prior_flags": 1,
            },
        },
    )
    client.post(
        "/feedback",
        json={
            "item_id": "metrics-item-1",
            "item_hash": None,
            "channel_name": "Metrics Channel",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "action_shown": "blur",
            "user_action": "report",
            "explanation_id": "exp-metrics-1",
            "before_score": 0.61,
            "after_score": 0.81,
            "timestamp": "2026-03-23T10:00:00Z",
        },
    )

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "truthlens_score_events_total 1" in response.text
    assert "truthlens_feedback_events_total 1" in response.text
    assert 'truthlens_feedback_action_total{action="report"} 1' in response.text
    assert "truthlens_policy_fallback_rate" in response.text
    assert "truthlens_policy_divergence_rate" in response.text
    assert "truthlens_policy_bseo_artifact_available" in response.text
    assert "truthlens_policy_rl_artifact_available" in response.text
    assert "# HELP truthlens_policy_fallback_rate Runtime BSEO fallback rate." in response.text
    assert 'truthlens_api_requests_total{path="/score-item"} 1' in response.text


def test_api_key_can_be_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("truthlens_api.main.settings.require_api_key", True)
    monkeypatch.setattr("truthlens_api.main.settings.api_key", "secret-key")

    unauthorized = client.get("/model-info")
    authorized = client.get("/model-info", headers={"x-truthlens-api-key": "secret-key"})

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200


def test_muted_channel_forces_hide() -> None:
    response = client.post(
        "/score-item",
        json={
            "item_id": "item-muted",
            "title": "Calm telescope update",
            "thumbnail_ref": None,
            "transcript_excerpt": "A calm telescope update with cited methods and no urgent claim.",
            "metadata": {},
            "channel": {
                "channel_name": "Muted Channel",
                "prior_flags": 0,
                "channel_history_features": {},
            },
            "user_context": {
                "strict_mode": False,
                "muted_channels": ["Muted Channel"],
                "prior_corrections": 0,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommended_action"] == "hide"
    assert any("locally muted" in reason.lower() for reason in payload["reasons"])
    assert payload["explanation_id"]
    assert payload["explanation_summary"]


def test_transcript_mismatch_surfaces_reasoning() -> None:
    response = client.post(
        "/score-item",
        json={
            "item_id": "item-mismatch",
            "title": "Breaking aliens confirmed over Europe",
            "thumbnail_ref": None,
            "transcript_excerpt": "This segment calmly reviews telescope maintenance and launch cadence.",
            "metadata": {
                "view_count": 12000,
                "like_count": 900,
            },
            "channel": {
                "channel_name": "Signal Watch Europe",
                "prior_flags": 3,
                "channel_history_features": {
                    "channel_risk_mean": 0.72,
                    "repeat_template_rate": 0.61,
                    "recent_upload_velocity": 0.58,
                    "engagement_anomaly": 1.22,
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(
        "transcript" in reason.lower() or "framing mismatch" in reason.lower()
        for reason in payload["reasons"]
    )
    assert any(entry["kind"] == "transcript" for entry in payload["evidence"])


def test_music_content_dampens_literal_mismatch_penalty() -> None:
    response = client.post(
        "/score-item",
        json={
            "item_id": "item-music",
            "title": "Moonlight Echoes (Official Audio)",
            "thumbnail_ref": None,
            "transcript_excerpt": "Verse one drifts into chorus and refrain under the city lights.",
            "metadata": {
                "view_count": 12000,
                "like_count": 900,
            },
            "channel": {
                "channel_name": "Aurora Records",
                "prior_flags": 0,
                "channel_history_features": {
                    "music_likelihood": 0.95,
                    "title_music_signal": 1.0,
                    "channel_music_signal": 1.0,
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert not any(
        "framing mismatch" in reason.lower() or "transcript excerpt diverge" in reason.lower()
        for reason in payload["reasons"]
    )
    assert any(
        entry["label"] == "Likely music-content context detected"
        for entry in payload["evidence"]
    )
    assert payload["content_class"] == "music"
