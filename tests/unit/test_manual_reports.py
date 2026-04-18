import base64
import json
import httpx
from pathlib import Path

from truthlens_api.manual_reports import (
    _build_suggestion_prompt,
    optimize_manual_report,
    suggest_manual_report,
)
from truthlens_model_serving import append_feedback_event
from truthlens_shared_schemas.contracts import (
    ManualReportOptimizationRequest,
    ManualReportSuggestionRequest,
)


class _MockResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class _MockImageResponse:
    def __init__(self, content: bytes, content_type: str = "image/jpeg") -> None:
        self.content = content
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        return None


def test_optimize_manual_report_stamps_configured_model_name(
    monkeypatch,
) -> None:
    captured_request: dict[str, object] = {}

    def fake_post(url: str, **kwargs):
        captured_request["url"] = url
        captured_request["timeout"] = kwargs.get("timeout")
        return _MockResponse(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "issues": [
                                                {
                                                    "issue_type": "title",
                                                    "comment": "The title presents an unverified claim as confirmed fact.",
                                                }
                                            ],
                                            "optimization_model": "LLM_Report_Generator",
                                            "report_text": "Please review this video for misleading framing.\n- Title: The title presents an unverified claim as confirmed fact.",
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("truthlens_api.manual_reports.httpx.post", fake_post)
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_api_key",
        "test-key",
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_model",
        "gemini-2.5-flash",
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_api_base",
        "https://generativelanguage.googleapis.com/v1beta",
    )

    result = optimize_manual_report(
        ManualReportOptimizationRequest.model_validate(
            {
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
            }
        )
    )

    assert captured_request["url"].endswith("/models/gemini-2.5-flash:generateContent")
    assert captured_request["timeout"] == 60.0
    assert result.optimization_model == "gemini-2.5-flash"
    assert result.report_text.startswith("Please review this video")


def test_optimize_manual_report_falls_back_when_gemini_is_rate_limited(
    monkeypatch,
) -> None:
    def rate_limited_post(url: str, **kwargs):
        request = httpx.Request("POST", url)
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError(
            "Client error '429 Too Many Requests'",
            request=request,
            response=response,
        )

    monkeypatch.setattr("truthlens_api.manual_reports.httpx.post", rate_limited_post)
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_api_key",
        "test-key",
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_model",
        "gemini-2.5-flash",
    )

    result = optimize_manual_report(
        ManualReportOptimizationRequest.model_validate(
            {
                "target_url": "https://www.youtube.com/watch?v=item-manual-report",
                "title_snapshot": "Exploring Places We Shouldn't - STAY OUT",
                "channel_name": "Ung opfinder",
                "transcript_excerpt": "Transcript excerpt does not clearly support the dramatic packaging.",
                "requested_outcome": "moderate",
                "issues": [
                    {
                        "issue_type": "thumbnail",
                        "comment": "thumbnail image may not accurately represent the scenario suggested by the title",
                    },
                    {
                        "issue_type": "other",
                        "comment": "video packaging uses clickbait or fear-based curiosity cues",
                    },
                ],
            }
        )
    )

    assert result.optimization_model == "truthlens-heuristic-optimizer-v1"
    assert result.issues[0].comment == (
        "Thumbnail image may not accurately represent the scenario or subject suggested by the title, which could mislead users about what the video actually shows. The current packaging also leans on heightened curiosity or warning cues that may amplify the mismatch."
    )
    assert result.issues[1].comment == (
        "Overall packaging appears to rely on clickbait or fear-based curiosity cues rather than clearly representing the actual content."
    )
    assert result.report_text.startswith("Requested action: Please moderate this content")
    assert (
        "- Thumbnail: Thumbnail image may not accurately represent the scenario or subject suggested by the title, which could mislead users about what the video actually shows. The current packaging also leans on heightened curiosity or warning cues that may amplify the mismatch."
        in result.report_text
    )


def test_suggest_manual_report_normalizes_missing_issue_types(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    captured_request: dict[str, object] = {}

    def fake_post(url: str, **kwargs):
        captured_request["url"] = url
        captured_request["json"] = kwargs.get("json")
        return _MockResponse(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
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
                                            "suggestion_model": "LLM_Report_Generator",
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("truthlens_api.manual_reports.httpx.post", fake_post)
    monkeypatch.setattr(
        "truthlens_api.manual_reports.httpx.get",
        lambda *args, **kwargs: _MockImageResponse(b"fake-thumbnail-bytes"),
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_api_key",
        "test-key",
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_model",
        "gemini-2.5-flash",
    )

    result = suggest_manual_report(
        ManualReportSuggestionRequest.model_validate(
            {
                "target_url": "https://www.youtube.com/watch?v=item-manual-report",
                "thumbnail_ref": "https://img.youtube.com/vi/item-manual-report/default.jpg",
                "title_snapshot": "Secret lab leak footage",
                "channel_name": "Signal Watch",
                "channel_url": "https://www.youtube.com/@signalwatch",
                "channel_context": 'Recent public channel titles: "Weekly lab update"; "Facility access discussion"; "Workshop recap"',
                "description_snapshot": "The metadata snippet promises dramatic new footage.",
                "transcript_excerpt": "Transcript claims a secret lab leak without support.",
                "transcript_available": True,
                "explanation_summary": "The title and thumbnail appear weakly aligned.",
                "reasons": ["Title contains sensational framing patterns."],
            }
        )
    )

    assert result.suggestion_model == "gemini-2.5-flash"
    assert result.suggested_outcome.value == "moderate"
    assert result.suggested_outcome_reason
    assert result.suggested_tags[0].tag.value == "Clickbait"
    assert len(result.issues) == 6
    assert result.issues[0].issue_type == "thumbnail"
    assert result.issues[0].suggested is True
    assert result.issues[0].comment == "The thumbnail framing appears disconnected from the stated topic."
    assert result.issues[2].issue_type == "description"
    assert result.issues[2].suggested is True
    assert 'Description currently says "The metadata snippet promises dramatic new footage."' in result.issues[2].comment
    assert result.issues[3].suggested is True
    assert 'Transcript excerpt says "Transcript claims a secret lab leak without support."' in result.issues[3].comment
    assert result.issues[4].suggested is True
    assert "first truthlens report recorded" in result.issues[4].comment.lower()
    request_parts = captured_request["json"]["contents"][0]["parts"]
    assert request_parts[0]["inline_data"]["mime_type"] == "image/jpeg"
    assert request_parts[0]["inline_data"]["data"] == base64.b64encode(
        b"fake-thumbnail-bytes"
    ).decode("ascii")
    assert "Channel URL: https://www.youtube.com/@signalwatch" in request_parts[1]["text"]
    assert (
        'Channel context: Recent public channel titles: "Weekly lab update"; "Facility access discussion"; "Workshop recap"'
        in request_parts[1]["text"]
    )
    assert "Description snippet: The metadata snippet promises dramatic new footage." in request_parts[1]["text"]
    assert "Transcript availability: Available" in request_parts[1]["text"]


def test_suggest_manual_report_falls_back_to_heuristics_when_gemini_fails(
    monkeypatch,
) -> None:
    call_count = 0

    def failing_post(url: str, **kwargs):
        nonlocal call_count
        call_count += 1
        raise ValueError("Gemini returned malformed suggestion JSON.")

    monkeypatch.setattr("truthlens_api.manual_reports.httpx.post", failing_post)
    monkeypatch.setattr(
        "truthlens_api.manual_reports.httpx.get",
        lambda *args, **kwargs: _MockImageResponse(b"heuristic-thumbnail-bytes"),
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_api_key",
        "test-key",
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_model",
        "gemini-2.5-flash",
    )

    result = suggest_manual_report(
        ManualReportSuggestionRequest.model_validate(
            {
                "target_url": "https://www.youtube.com/watch?v=stay-out-demo",
                "thumbnail_ref": "https://img.youtube.com/vi/stay-out-demo/default.jpg",
                "title_snapshot": "Exploring Places We Shouldn't - STAY OUT",
                "channel_name": "Ung opfinder",
                "channel_url": "https://www.youtube.com/@ungopfinder",
                "channel_context": 'Recent public channel titles: "STAY OUT - Hidden tunnel"; "We explored a sealed bunker"; "Do not enter this mine shaft"',
                "description_snapshot": "A dramatic title promises forbidden exploration and danger.",
                "transcript_excerpt": None,
                "transcript_available": False,
                "explanation_summary": "Title and thumbnail appear weakly aligned.",
                "reasons": [
                    "Title and thumbnail appear weakly aligned.",
                    "Video uses clickbait tactics.",
                ],
            }
        )
    )

    assert call_count == 2
    assert result.suggestion_model == "truthlens-heuristic-fallback-v1"
    assert result.suggested_tags[0].tag.value == "Clickbait"
    issue_map = {issue.issue_type: issue for issue in result.issues}
    assert issue_map["thumbnail"].suggested is True
    assert 'title phrases "stay out"' in issue_map["thumbnail"].comment.lower()
    assert "shouldn't" in issue_map["thumbnail"].comment.lower()
    assert 'the description "A dramatic title promises forbidden exploration and danger."' in issue_map["thumbnail"].comment
    assert issue_map["title"].suggested is True
    assert "overselling what the video actually contains" in issue_map["title"].comment
    assert issue_map["description"].suggested is True
    assert 'title phrases "stay out"' in issue_map["description"].comment.lower()
    assert "shouldn't" in issue_map["description"].comment.lower()
    assert issue_map["transcript"].suggested is False
    assert issue_map["transcript"].comment == ""
    assert issue_map["channel"].suggested is True
    assert "recurring clickbait pattern" in issue_map["channel"].comment
    assert issue_map["other"].suggested is True
    assert 'the description "A dramatic title promises forbidden exploration and danger."' in issue_map["other"].comment


def test_suggest_manual_report_can_choose_remove_for_strong_systematic_signals(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "truthlens_api.manual_reports.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("Gemini returned malformed suggestion JSON.")
        ),
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.httpx.get",
        lambda *args, **kwargs: _MockImageResponse(b"heuristic-thumbnail-bytes"),
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_api_key",
        "test-key",
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_model",
        "gemini-2.5-flash",
    )

    result = suggest_manual_report(
        ManualReportSuggestionRequest.model_validate(
            {
                "target_url": "https://www.youtube.com/watch?v=synthetic-clickbait-demo",
                "thumbnail_ref": "https://img.youtube.com/vi/synthetic-clickbait-demo/default.jpg",
                "title_snapshot": "SECRET AI WARNING - STAY OUT",
                "channel_name": "Synthetic Signal Factory",
                "description_snapshot": "Repeated deceptive packaging is used to provoke clicks.",
                "transcript_excerpt": "The available text does not support the packaging and suggests systematic synthetic spam patterns.",
                "explanation_summary": "Thumbnail and title appear misaligned with repeated misleading framing.",
                "reasons": [
                    "Repeated misleading packaging pattern detected.",
                    "Synthetic spam cues detected in channel context.",
                    "Video uses clickbait tactics.",
                ],
            }
        )
    )

    assert result.suggested_outcome.value == "remove"
    assert result.suggested_tags[0].tag.value == "Clickbait"


def test_suggest_manual_report_uses_music_aware_heuristics(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "truthlens_api.manual_reports.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("Gemini returned malformed suggestion JSON.")
        ),
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.httpx.get",
        lambda *args, **kwargs: _MockImageResponse(b"heuristic-thumbnail-bytes"),
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_api_key",
        "test-key",
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_model",
        "gemini-2.5-flash",
    )

    result = suggest_manual_report(
        ManualReportSuggestionRequest.model_validate(
            {
                "workflow_mode": "verify-transparent",
                "target_url": "https://www.youtube.com/watch?v=moonlight-echoes",
                "thumbnail_ref": "https://img.youtube.com/vi/moonlight-echoes/default.jpg",
                "title_snapshot": "Moonlight Echoes (Official Audio)",
                "channel_name": "Aurora Records",
                "channel_url": "https://www.youtube.com/@aurorarecords",
                "channel_context": 'Recent public channel titles: "Moonlight Echoes (Official Audio)"; "Northern Lights (Lyric Video)"; "Solar Tide (Live Session)"',
                "description_snapshot": "Official audio release for Moonlight Echoes by Aurora.",
                "transcript_excerpt": None,
                "transcript_available": False,
                "explanation_summary": "Metadata should be reviewed against the visible packaging.",
                "reasons": ["Structured metadata features contribute strongly to the current risk estimate."],
            }
        )
    )

    assert result.suggestion_model == "truthlens-heuristic-fallback-v1"
    assert any(tag.tag.value == "Music" and tag.selected for tag in result.suggested_tags)
    issue_map = {issue.issue_type: issue for issue in result.issues}
    assert "does not currently show a strong mismatch signal" in issue_map["thumbnail"].comment.lower()
    assert "does not currently show a clear overstatement signal" in issue_map["title"].comment.lower()
    assert issue_map["transcript"].suggested is False
    assert issue_map["transcript"].comment == ""
    assert issue_map["channel"].suggested is False
    assert issue_map["channel"].comment == ""
    assert result.suggested_outcome.value == "moderate"


def test_suggest_manual_report_uses_prior_channel_reports_in_channel_comment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "truthlens_api.manual_reports.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("Gemini returned malformed suggestion JSON.")
        ),
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.httpx.get",
        lambda *args, **kwargs: _MockImageResponse(b"heuristic-thumbnail-bytes"),
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_api_key",
        "test-key",
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_model",
        "gemini-2.5-flash",
    )

    append_feedback_event(
        {
            "item_id": "signal-watch-1",
            "item_hash": None,
            "channel_name": "Signal Watch",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "action_shown": "ask-report",
            "user_action": "confirm-report",
            "explanation_id": None,
            "before_score": 0.7,
            "after_score": 0.7,
            "timestamp": "2026-03-23T10:00:00Z",
            "manual_report": {
                "target_url": "https://www.youtube.com/watch?v=signal-watch-1",
                "title_snapshot": "Signal Watch upload",
                "issues": [
                    {
                        "issue_type": "title",
                        "comment": "The title appears misleading relative to the available context.",
                    }
                ],
                "requested_outcome": "moderate",
                "optimize_requested": False,
                "optimize_applied": False,
                "report_text": "Please moderate the misleading metadata on this upload.",
            },
        }
    )

    result = suggest_manual_report(
        ManualReportSuggestionRequest.model_validate(
            {
                "target_url": "https://www.youtube.com/watch?v=item-manual-report",
                "thumbnail_ref": "https://img.youtube.com/vi/item-manual-report/default.jpg",
                "title_snapshot": "Secret lab leak footage",
                "channel_name": "Signal Watch",
                "channel_url": "https://www.youtube.com/@signalwatch",
                "description_snapshot": "The metadata snippet promises dramatic new footage.",
                "transcript_excerpt": None,
                "transcript_available": False,
                "explanation_summary": "The title and thumbnail appear weakly aligned.",
                "reasons": ["Title contains sensational framing patterns."],
            }
        )
    )

    issue_map = {issue.issue_type: issue for issue in result.issues}
    assert "prior report" in issue_map["channel"].comment.lower()


def test_suggest_manual_report_preserves_unsuggested_gemini_fields(
    monkeypatch,
) -> None:
    def fake_post(url: str, **kwargs):
        return _MockResponse(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "issues": [
                                                {
                                                    "issue_type": "thumbnail",
                                                    "suggested": True,
                                                    "comment": "Thumbnail shows a bunker-style entrance while the title promises a forbidden-place reveal.",
                                                },
                                                {
                                                    "issue_type": "title",
                                                    "suggested": True,
                                                    "comment": "Title uses warning wording that the available metadata does not fully substantiate.",
                                                },
                                                {
                                                    "issue_type": "description",
                                                    "suggested": True,
                                                    "comment": "Description repeats dramatic framing without adding clear factual support.",
                                                },
                                                {
                                                    "issue_type": "transcript",
                                                    "suggested": False,
                                                    "comment": "",
                                                },
                                                {
                                                    "issue_type": "channel",
                                                    "suggested": False,
                                                    "comment": "",
                                                },
                                                {
                                                    "issue_type": "other",
                                                    "suggested": True,
                                                    "comment": "The combined packaging leans on secrecy and warning cues to provoke curiosity.",
                                                },
                                            ],
                                            "suggested_outcome": "moderate",
                                            "suggested_outcome_reason": "TruthLens recommends Moderate because the packaging overpromises.",
                                            "suggested_tags": [
                                                {
                                                    "tag": "Clickbait",
                                                    "selected": True,
                                                    "confidence": 0.88,
                                                    "rationale": "Report mode defaults to Clickbait.",
                                                }
                                            ],
                                            "suggestion_model": "LLM_Report_Generator",
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("truthlens_api.manual_reports.httpx.post", fake_post)
    monkeypatch.setattr(
        "truthlens_api.manual_reports.httpx.get",
        lambda *args, **kwargs: _MockImageResponse(b"fake-thumbnail-bytes"),
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_api_key",
        "test-key",
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_model",
        "gemini-2.5-flash",
    )

    result = suggest_manual_report(
        ManualReportSuggestionRequest.model_validate(
            {
                "target_url": "https://www.youtube.com/watch?v=item-manual-report",
                "thumbnail_ref": "https://img.youtube.com/vi/item-manual-report/default.jpg",
                "title_snapshot": "Exploring Places We Shouldn't - STAY OUT",
                "channel_name": "Signal Watch",
                "channel_url": "https://www.youtube.com/@signalwatch",
                "description_snapshot": "The metadata snippet promises dramatic new footage.",
                "transcript_excerpt": None,
                "transcript_available": False,
                "explanation_summary": "The title and thumbnail appear weakly aligned.",
                "reasons": ["Title contains sensational framing patterns."],
            }
        )
    )

    issue_map = {issue.issue_type: issue for issue in result.issues}
    assert issue_map["transcript"].suggested is False
    assert issue_map["transcript"].comment == ""
    assert issue_map["channel"].suggested is False
    assert issue_map["channel"].comment == ""


def test_suggest_manual_report_uses_satire_aware_heuristics(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "truthlens_api.manual_reports.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("Gemini returned malformed suggestion JSON.")
        ),
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.httpx.get",
        lambda *args, **kwargs: _MockImageResponse(b"heuristic-thumbnail-bytes"),
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_api_key",
        "test-key",
    )

    result = suggest_manual_report(
        ManualReportSuggestionRequest.model_validate(
            {
                "workflow_mode": "verify-transparent",
                "target_url": "https://www.youtube.com/watch?v=satire-demo",
                "thumbnail_ref": "https://img.youtube.com/vi/satire-demo/default.jpg",
                "title_snapshot": "Minister admits moon tax in emergency address",
                "channel_name": "Parody Desk",
                "channel_context": 'Recent public channel titles: "Budget hearing parody"; "Fake campaign sketch"; "Satire special"',
                "description_snapshot": "Satirical commentary sketch about public policy panic.",
                "transcript_excerpt": "The monologue plays as parody and jokes about an invented moon tax.",
                "transcript_available": True,
                "content_class": "satire",
                "content_class_confidence": 0.77,
                "bias_profile": {
                    "metrics": {"genre_confusion": 0.64},
                    "positive_biases": ["ambiguity-aware-caution"],
                    "negative_biases": ["genre-confusion"],
                    "guardrail_applied": "satire-context-prefers-review",
                },
                "explanation_summary": "Packaging remains ambiguous because the parody framing is not explicit enough.",
                "reasons": ["Genre confusion remains elevated for this upload."],
            }
        )
    )

    issue_map = {issue.issue_type: issue for issue in result.issues}
    assert "does not currently show a clear overstatement signal" in issue_map["title"].comment.lower()
    assert issue_map["other"].comment.lower().startswith("overall packaging does not currently show a strong clickbait signal")
    assert issue_map["channel"].suggested is False


def test_suggest_manual_report_report_mode_does_not_emit_benign_art_preface(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "truthlens_api.manual_reports.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("Gemini returned malformed suggestion JSON.")
        ),
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.httpx.get",
        lambda *args, **kwargs: _MockImageResponse(b"heuristic-thumbnail-bytes"),
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_api_key",
        "test-key",
    )

    result = suggest_manual_report(
        ManualReportSuggestionRequest.model_validate(
            {
                "workflow_mode": "report",
                "target_url": "https://www.youtube.com/watch?v=alien-warning-demo",
                "thumbnail_ref": "https://img.youtube.com/vi/alien-warning-demo/default.jpg",
                "title_snapshot": "U.S issues Alien warning",
                "channel_name": "Skizzle",
                "channel_context": 'Recent public channel titles: "Studio update"; "Weekly recap"; "New upload tonight"',
                "description_snapshot": "This is not a joke anymore, but the description still does not clearly verify the alien-warning premise.",
                "transcript_excerpt": None,
                "transcript_available": False,
                "content_class": "art",
                "content_class_confidence": 0.81,
                "bias_profile": {
                    "metrics": {"genre_confusion": 0.52},
                    "positive_biases": ["factual-scrutiny"],
                    "negative_biases": ["transcript-non-delivery"],
                    "guardrail_applied": "factual-context-amplifies-mismatch",
                },
                "explanation_summary": "The title and thumbnail create a stronger warning narrative than the supporting text clearly confirms.",
                "reasons": [
                    "Title contains warning framing.",
                    "The available text does not clearly confirm the same high-drama premise.",
                ],
            }
        )
    )

    issue_map = {issue.issue_type: issue for issue in result.issues}
    assert "art content" not in issue_map["thumbnail"].comment.lower()
    assert "art content" not in issue_map["title"].comment.lower()
    assert "art content" not in issue_map["description"].comment.lower()
    assert "art content" not in issue_map["other"].comment.lower()
    assert issue_map["channel"].suggested is True
    assert "first truthlens report recorded" in issue_map["channel"].comment.lower()


def test_suggest_manual_report_sanitizes_benign_gemini_report_language(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    def fake_post(url: str, **kwargs):
        return _MockResponse(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "issues": [
                                                {
                                                    "issue_type": "thumbnail",
                                                    "suggested": True,
                                                    "comment": "This appears to be art content. Review whether the thumbnail honestly represents the artwork, artist, or exhibition context rather than implying a literal event the supporting text does not confirm.",
                                                },
                                                {
                                                    "issue_type": "title",
                                                    "suggested": True,
                                                    "comment": "This appears to be art content. Review whether the title honestly identifies the artwork, artist, or exhibition framing rather than implying a literal event the packaging does not support.",
                                                },
                                                {
                                                    "issue_type": "description",
                                                    "suggested": True,
                                                    "comment": "This appears to be art content. Review whether the description honestly labels the artwork, exhibition, or studio context instead of overstating what the video contains.",
                                                },
                                                {
                                                    "issue_type": "transcript",
                                                    "suggested": False,
                                                    "comment": "",
                                                },
                                                {
                                                    "issue_type": "channel",
                                                    "suggested": False,
                                                    "comment": "",
                                                },
                                                {
                                                    "issue_type": "other",
                                                    "suggested": True,
                                                    "comment": "This appears to be art content. Broad stylistic packaging alone should not be treated as misleading; review instead whether the overall packaging overstates the artwork or exhibition context.",
                                                },
                                            ],
                                            "suggested_outcome": "moderate",
                                            "suggested_outcome_reason": "TruthLens recommends Moderate because the packaging overpromises.",
                                            "suggested_tags": [
                                                {
                                                    "tag": "Clickbait",
                                                    "selected": True,
                                                    "confidence": 0.85,
                                                    "rationale": "Report mode defaults to Clickbait.",
                                                }
                                            ],
                                            "suggestion_model": "LLM_Report_Generator",
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("truthlens_api.manual_reports.httpx.post", fake_post)
    monkeypatch.setattr(
        "truthlens_api.manual_reports.httpx.get",
        lambda *args, **kwargs: _MockImageResponse(b"fake-thumbnail-bytes"),
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_api_key",
        "test-key",
    )
    monkeypatch.setattr(
        "truthlens_api.manual_reports.settings.gemini_model",
        "gemini-2.5-flash",
    )

    result = suggest_manual_report(
        ManualReportSuggestionRequest.model_validate(
            {
                "workflow_mode": "report",
                "target_url": "https://www.youtube.com/watch?v=alien-warning-demo",
                "thumbnail_ref": "https://img.youtube.com/vi/alien-warning-demo/default.jpg",
                "title_snapshot": "U.S issues Alien warning",
                "channel_name": "Skizzle",
                "channel_context": 'Recent public channel titles: "Studio update"; "Weekly recap"; "New upload tonight"',
                "description_snapshot": "This is not a joke anymore, but the description still does not clearly verify the alien-warning premise.",
                "transcript_excerpt": None,
                "transcript_available": False,
                "content_class": "art",
                "content_class_confidence": 0.81,
                "bias_profile": {
                    "metrics": {"genre_confusion": 0.52},
                    "positive_biases": ["factual-scrutiny"],
                    "negative_biases": ["transcript-non-delivery"],
                    "guardrail_applied": "factual-context-amplifies-mismatch",
                },
                "explanation_summary": "The title and thumbnail create a stronger warning narrative than the supporting text clearly confirms.",
                "reasons": [
                    "Title contains warning framing.",
                    "The available text does not clearly confirm the same high-drama premise.",
                ],
            }
        )
    )

    issue_map = {issue.issue_type: issue for issue in result.issues}
    assert "art content" not in issue_map["thumbnail"].comment.lower()
    assert "art content" not in issue_map["title"].comment.lower()
    assert "art content" not in issue_map["description"].comment.lower()
    assert "art content" not in issue_map["other"].comment.lower()
    assert issue_map["channel"].suggested is True
    assert "first truthlens report recorded" in issue_map["channel"].comment.lower()


def test_build_suggestion_prompt_includes_taxonomy_and_bias_context() -> None:
    prompt = _build_suggestion_prompt(
        ManualReportSuggestionRequest.model_validate(
            {
                "target_url": "https://www.youtube.com/watch?v=music123",
                "title_snapshot": "Moonlight Echoes (Official Audio)",
                "channel_name": "Aurora Records",
                "content_class": "music",
                "content_class_confidence": 0.92,
                "bias_profile": {
                    "metrics": {"crossmodal_rigidity": 0.28},
                    "positive_biases": ["stylistic-divergence-tolerance"],
                    "negative_biases": [],
                    "guardrail_applied": "music-context-dampens-crossmodal-rigidity",
                },
                "reasons": ["Class-conditioned guardrail reduced the mismatch penalty."],
            }
        )
    )

    assert "TruthLens content class: music (92% confidence)" in prompt
    assert "TruthLens positive biases: stylistic-divergence-tolerance" in prompt
    assert "TruthLens negative biases: None recorded." in prompt
