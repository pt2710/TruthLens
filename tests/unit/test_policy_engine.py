from pathlib import Path
import json

import pytest

from truthlens_model_serving import append_feedback_event
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
