from dataclasses import dataclass, field
from pathlib import Path
import importlib

import pytest

from truthlens_data_pipeline.paths import repo_root
from truthlens_model_serving import (
    append_browser_observation,
    append_feedback_event,
    append_score_event,
    load_browser_observations,
    load_feedback_events,
    load_score_events,
    summarize_browser_observations,
    summarize_feedback_events,
)


def test_feedback_events_are_persisted_to_sqlite_and_jsonl(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    append_feedback_event(
        {
            "item_id": "item-1",
            "item_hash": None,
            "channel_name": "Signal Watch",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "action_shown": "badge",
            "user_action": "report",
            "explanation_id": "exp-1",
            "before_score": 0.61,
            "after_score": 0.81,
            "timestamp": "2026-03-23T10:00:00Z",
        }
    )

    db_path = repo_root() / "artifacts" / "reports" / "feedback_events.sqlite3"
    jsonl_path = repo_root() / "artifacts" / "reports" / "feedback_events.jsonl"
    rows = load_feedback_events()
    summary = summarize_feedback_events(rows)

    assert db_path.exists()
    assert jsonl_path.exists()
    assert len(rows) == 1
    assert rows[0]["explanation_id"] == "exp-1"
    assert summary["total_events"] == 1


def test_browser_observations_are_persisted_to_sqlite_and_jsonl(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    append_browser_observation(
        {
            "observation_id": "obs-1",
            "item_id": "item-1",
            "item_hash": "sig-1",
            "title_snapshot": "Breaking thumbnail packaging",
            "channel_name": "Signal Watch",
            "channel_url": "https://www.youtube.com/@signalwatch",
            "link_url": "https://www.youtube.com/watch?v=item-1",
            "thumbnail_ref": "https://i.ytimg.com/vi/item-1/hqdefault.jpg",
            "description_snapshot": "Description",
            "transcript_excerpt": "Transcript",
            "metadata": {"duration_seconds": 120},
            "runtime_context": {
                "surface": "extension-feed",
                "review_requested": False,
                "source_provenance": "/",
            },
            "distilled_features": {
                "card_index": 0,
                "link_kind": "watch",
                "has_thumbnail": True,
                "has_description_snapshot": True,
                "has_transcript_excerpt": True,
                "title_token_count": 3,
                "description_token_count": 1,
                "channel_known": True,
                "duration_seconds": 120,
            },
            "score_snapshot": {
                "risk_score": 0.74,
                "calibrated_score": 0.71,
                "uncertainty": 0.21,
                "recommended_action": "ask-report",
                "content_class": "news",
                "content_class_confidence": 0.64,
                "explanation_id": "exp-1",
            },
            "provenance": {
                "observed_at": "2026-04-06T10:00:00Z",
                "collector": "extension-dom",
                "collector_version": "extension-runtime",
                "session_id": "session-1",
                "page_url": "https://www.youtube.com/",
                "source_path": "/",
            },
        }
    )

    db_path = repo_root() / "artifacts" / "reports" / "feedback_events.sqlite3"
    jsonl_path = repo_root() / "artifacts" / "reports" / "browser_observations.jsonl"
    rows = load_browser_observations()
    summary = summarize_browser_observations(rows)

    assert db_path.exists()
    assert jsonl_path.exists()
    assert len(rows) == 1
    assert rows[0]["observation_id"] == "obs-1"
    assert summary["total_observations"] == 1
    assert summary["surface_counts"]["extension-feed"] == 1


def test_feedback_summary_keeps_repeated_reports_risky_even_with_many_scored_items(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    for index in range(10):
        append_score_event(
            {
                "item_id": f"scored-{index}",
                "channel_name": "Signal Watch",
                "model_version": "test-model",
                "policy_version": "test-policy",
                "recommended_action": "ask-report" if index < 6 else "none",
                "risk_score": 0.82 if index < 6 else 0.18,
                "confidence": 0.76,
                "uncertainty": 0.24,
                "explanation_id": f"exp-score-{index}",
                "timestamp": f"2026-03-23T10:{index:02d}:00Z",
            }
        )

    for index in range(6):
        append_feedback_event(
            {
                "item_id": f"scored-{index}",
                "item_hash": None,
                "channel_name": "Signal Watch",
                "model_version": "test-model",
                "policy_version": "test-policy",
                "action_shown": "ask-report",
                "user_action": "confirm-report",
                "explanation_id": f"exp-feedback-{index}",
                "before_score": 0.82,
                "after_score": 0.82,
                "timestamp": f"2026-03-23T11:{index:02d}:00Z",
                "manual_report": {
                    "target_url": f"https://www.youtube.com/watch?v=scored-{index}",
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

    rows = load_feedback_events()
    summary = summarize_feedback_events(rows)
    channel = summary["channel_profiles"]["signal watch"]

    assert channel["scored_item_count"] == 10
    assert channel["reported_item_count"] == 6
    assert channel["moderate_request_count"] == 6
    assert channel["effective_sample_count"] == 8.0
    assert channel["repeat_template_rate"] == 0.75
    assert channel["channel_risk_mean"] > 0.7
    assert channel["trust_score"] < 3.0


def test_feedback_summary_does_not_let_large_scored_history_hide_reported_channel_risk(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    for index in range(25):
        append_score_event(
            {
                "item_id": f"airev-{index}",
                "channel_name": "AI Revolution",
                "model_version": "test-model",
                "policy_version": "test-policy",
                "recommended_action": "none",
                "risk_score": 0.18,
                "confidence": 0.72,
                "uncertainty": 0.28,
                "explanation_id": f"exp-airev-score-{index}",
                "timestamp": f"2026-03-23T10:{index:02d}:00Z",
            }
        )

    for index, outcome in enumerate(["moderate", "remove", "remove"]):
        append_feedback_event(
            {
                "item_id": f"airev-{index}",
                "item_hash": None,
                "channel_name": "AI Revolution",
                "model_version": "test-model",
                "policy_version": "test-policy",
                "action_shown": "badge",
                "user_action": "confirm-report",
                "explanation_id": f"exp-airev-feedback-{index}",
                "before_score": 0.42,
                "after_score": 0.42,
                "timestamp": f"2026-03-23T11:{index:02d}:00Z",
                "manual_report": {
                    "target_url": f"https://www.youtube.com/watch?v=airev-{index}",
                    "title_snapshot": "AI Revolution upload",
                    "issues": [
                        {
                            "issue_type": "title",
                            "comment": "The title overstates certainty relative to the visible context.",
                        }
                    ],
                    "requested_outcome": outcome,
                    "optimize_requested": False,
                    "optimize_applied": False,
                    "report_text": "Please review the misleading packaging claims.",
                },
            }
        )

    summary = summarize_feedback_events(load_feedback_events())
    channel = summary["channel_profiles"]["ai revolution"]

    assert channel["scored_item_count"] == 25
    assert channel["reported_item_count"] == 3
    assert channel["effective_sample_count"] == 5.0
    assert channel["repeat_template_rate"] == 0.6
    assert channel["channel_risk_mean"] > 0.7
    assert channel["trust_score"] < 3.0


def test_feedback_summary_rewards_confirmed_transparent_feedback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    for index in range(4):
        append_score_event(
            {
                "item_id": f"transparent-{index}",
                "channel_name": "Context First Media",
                "model_version": "test-model",
                "policy_version": "test-policy",
                "recommended_action": "none",
                "risk_score": 0.16,
                "confidence": 0.84,
                "uncertainty": 0.16,
                "explanation_id": None,
                "timestamp": f"2026-03-23T12:{index:02d}:00Z",
            }
        )
        append_feedback_event(
            {
                "item_id": f"transparent-{index}",
                "item_hash": None,
                "channel_name": "Context First Media",
                "model_version": "test-model",
                "policy_version": "test-policy",
                "action_shown": "none",
                "user_action": "confirm-transparent",
                "explanation_id": None,
                "before_score": 0.16,
                "after_score": 0.12,
                "timestamp": f"2026-03-23T12:{index:02d}:30Z",
                "manual_report": {
                    "workflow_mode": "verify-transparent",
                    "target_url": f"https://www.youtube.com/watch?v=transparent-{index}",
                    "title_snapshot": "Transparent upload",
                    "issues": [
                        {
                            "issue_type": "title",
                            "comment": "The title appears consistent with the visible context.",
                        }
                    ],
                    "requested_outcome": "moderate",
                    "optimize_requested": False,
                    "optimize_applied": False,
                    "report_text": "Transparency verification: the visible packaging appears consistent.",
                },
            }
        )

    summary = summarize_feedback_events(load_feedback_events())
    channel = summary["channel_profiles"]["context first media"]

    assert channel["transparent_count"] == 4
    assert channel["trust_score"] > 6.0


def test_feedback_summary_ignores_unknown_channel_profiles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    append_score_event(
        {
            "item_id": "unknown-score-1",
            "channel_name": "Unknown channel",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "recommended_action": "badge",
            "risk_score": 0.42,
            "confidence": 0.61,
            "uncertainty": 0.39,
            "explanation_id": None,
            "timestamp": "2026-03-23T13:00:00Z",
        }
    )
    append_feedback_event(
        {
            "item_id": "unknown-feedback-1",
            "item_hash": None,
            "channel_name": "Unknown channel",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "action_shown": "badge",
            "user_action": "confirm-report",
            "explanation_id": None,
            "before_score": 0.42,
            "after_score": 0.42,
            "timestamp": "2026-03-23T13:01:00Z",
        }
    )

    summary = summarize_feedback_events(load_feedback_events())

    assert "unknown channel" not in summary["channel_profiles"]


class _FakeCursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self._rows)


class _FakeConnection:
    def __init__(self, store: "_FakePgStore") -> None:
        self._store = store

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def execute(self, sql: str, params: tuple[object, ...] | None = None) -> _FakeCursor:
        normalized = " ".join(sql.split()).lower()
        if normalized.startswith("create table"):
            return _FakeCursor([])
        if normalized.startswith("alter table feedback_events add column"):
            return _FakeCursor([])
        if "insert into feedback_events" in normalized:
            self._store.feedback_events.append(params or ())
            return _FakeCursor([])
        if "insert into score_events" in normalized:
            self._store.score_events.append(params or ())
            return _FakeCursor([])
        if "insert into browser_observations" in normalized:
            self._store.browser_observations.append(params or ())
            return _FakeCursor([])
        if "from feedback_events" in normalized:
            return _FakeCursor(list(self._store.feedback_events))
        if "from score_events" in normalized:
            return _FakeCursor(list(self._store.score_events))
        if "from browser_observations" in normalized:
            return _FakeCursor(list(self._store.browser_observations))
        raise AssertionError(f"Unexpected SQL in fake Postgres connection: {sql}")

    def commit(self) -> None:
        self._store.commit_count += 1


@dataclass
class _FakePgStore:
    feedback_events: list[tuple[object, ...]] = field(default_factory=list)
    score_events: list[tuple[object, ...]] = field(default_factory=list)
    browser_observations: list[tuple[object, ...]] = field(default_factory=list)
    commit_count: int = 0
    dsn: str | None = None


class _FakePsycopg:
    def __init__(self, store: _FakePgStore) -> None:
        self._store = store

    def connect(self, dsn: str) -> _FakeConnection:
        self._store.dsn = dsn
        return _FakeConnection(self._store)


def test_postgres_runtime_event_store_persists_feedback_scores_and_observations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry = importlib.import_module("truthlens_model_serving.registry")
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("TRUTHLENS_RUNTIME_EVENT_STORE", "postgres")
    monkeypatch.setenv("TRUTHLENS_DATABASE_URL", "postgresql+psycopg://truthlens:truthlens@localhost:5432/truthlens")
    monkeypatch.setenv("TRUTHLENS_LOCAL_EVENT_FALLBACK_ENABLED", "false")

    fake_store = _FakePgStore()
    monkeypatch.setattr(registry, "psycopg", _FakePsycopg(fake_store))

    registry.ensure_runtime_event_store()

    append_feedback_event(
        {
            "feedback_id": "feedback-pg-1",
            "item_id": "item-pg-1",
            "item_hash": None,
            "observation_id": "obs-pg-1",
            "channel_name": "Signal Watch",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "action_shown": "badge",
            "user_action": "report",
            "explanation_id": "exp-pg-1",
            "before_score": 0.62,
            "after_score": 0.81,
            "timestamp": "2026-04-11T12:00:00Z",
            "runtime_context": {"surface": "extension-feed"},
            "manual_report": {"requested_outcome": "moderate"},
        }
    )
    append_score_event(
        {
            "item_id": "item-pg-1",
            "channel_name": "Signal Watch",
            "model_version": "test-model",
            "policy_version": "test-policy",
            "recommended_action": "ask-report",
            "risk_score": 0.81,
            "confidence": 0.73,
            "uncertainty": 0.19,
            "explanation_id": "exp-pg-1",
            "timestamp": "2026-04-11T12:00:05Z",
        }
    )
    append_browser_observation(
        {
            "observation_id": "obs-pg-1",
            "item_id": "item-pg-1",
            "item_hash": "hash-pg-1",
            "title_snapshot": "Breaking packaging",
            "channel_name": "Signal Watch",
            "channel_url": "https://www.youtube.com/@signalwatch",
            "link_url": "https://www.youtube.com/watch?v=item-pg-1",
            "thumbnail_ref": "https://i.ytimg.com/vi/item-pg-1/hqdefault.jpg",
            "description_snapshot": "Description",
            "transcript_excerpt": "Transcript",
            "metadata": {"duration_seconds": 120},
            "runtime_context": {"surface": "extension-feed"},
            "distilled_features": {"card_index": 0},
            "score_snapshot": {"recommended_action": "ask-report"},
            "provenance": {"collector": "extension-dom", "observed_at": "2026-04-11T12:00:06Z"},
        }
    )

    feedback_rows = load_feedback_events()
    score_rows = load_score_events()
    observation_rows = load_browser_observations()

    assert registry.runtime_event_store_backend() == "postgres"
    assert fake_store.dsn == "postgresql://truthlens:truthlens@localhost:5432/truthlens"
    assert len(feedback_rows) == 1
    assert feedback_rows[0]["feedback_id"] == "feedback-pg-1"
    assert feedback_rows[0]["runtime_context"] == {"surface": "extension-feed"}
    assert len(score_rows) == 1
    assert score_rows[0]["recommended_action"] == "ask-report"
    assert len(observation_rows) == 1
    assert observation_rows[0]["provenance"]["collector"] == "extension-dom"
    assert not (repo_root() / "artifacts" / "reports" / "feedback_events.jsonl").exists()
    assert not (repo_root() / "artifacts" / "reports" / "feedback_events.sqlite3").exists()
