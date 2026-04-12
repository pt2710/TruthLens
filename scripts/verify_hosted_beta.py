from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from time import time
from typing import Any

import httpx


DEFAULT_BASE_URL = "https://truthlens-beta-api.onrender.com"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def _metric_value(metrics_text: str, metric_name: str) -> float | None:
    prefix = f"{metric_name} "
    for line in metrics_text.splitlines():
        if line.startswith(prefix):
            try:
                return float(line.removeprefix(prefix).strip())
            except ValueError:
                return None
    return None


def _score_payload(run_id: str, *, item_id: str, title: str) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "title": title,
        "thumbnail_ref": None,
        "description_snapshot": "Hosted beta verification sample for TruthLens.",
        "transcript_excerpt": "This clip reviews launch cadence and observational weather patterns.",
        "metadata": {
            "view_count": 14000,
            "like_count": 950,
            "duration_seconds": 91,
        },
        "channel": {
            "channel_name": "Hosted Proof Channel",
            "prior_flags": 2,
            "channel_history_features": {
                "channel_risk_mean": 0.58,
                "repeat_template_rate": 0.44,
                "recent_upload_velocity": 0.31,
                "engagement_anomaly": 1.14,
            },
        },
        "runtime_context": {
            "surface": "api",
            "review_requested": False,
            "source_provenance": run_id,
        },
    }


def _observation_payload(run_id: str, *, item_id: str, title: str) -> dict[str, Any]:
    return {
        "observation_id": f"{run_id}-obs-1",
        "item_id": item_id,
        "item_hash": f"{run_id}-hash-1",
        "title_snapshot": title,
        "channel_name": "Hosted Proof Channel",
        "channel_url": "https://www.youtube.com/@hostedproof",
        "link_url": f"https://www.youtube.com/watch?v={run_id}",
        "thumbnail_ref": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
        "description_snapshot": "Hosted beta verification sample for TruthLens.",
        "transcript_excerpt": "This clip reviews launch cadence and observational weather patterns.",
        "metadata": {
            "duration_seconds": 91,
            "view_count": 14000,
            "like_count": 950,
        },
        "runtime_context": {
            "surface": "extension-feed",
            "review_requested": False,
            "source_provenance": run_id,
        },
        "distilled_features": {
            "card_index": 1,
            "link_kind": "watch",
            "has_thumbnail": True,
            "has_description_snapshot": True,
            "has_transcript_excerpt": True,
            "title_token_count": 5,
            "description_token_count": 6,
            "channel_known": True,
            "duration_seconds": 91,
        },
        "score_snapshot": {
            "risk_score": 0.72,
            "calibrated_score": 0.69,
            "uncertainty": 0.28,
            "recommended_action": "ask-report",
            "content_class": "news",
            "content_class_confidence": 0.66,
            "explanation_id": "exp-hosted-proof-1",
        },
        "provenance": {
            "observed_at": _utc_now(),
            "collector": "api",
            "collector_version": "hosted-proof-script",
            "session_id": run_id,
            "page_url": "https://www.youtube.com/feed/subscriptions",
            "source_path": "/feed/subscriptions",
        },
    }


def _feedback_payload(
    run_id: str,
    *,
    item_id: str,
    observation_id: str,
    score_result: dict[str, Any],
) -> dict[str, Any]:
    artifact_provenance = score_result.get("artifact_provenance", {})
    return {
        "feedback_id": f"{run_id}-feedback-1",
        "item_id": item_id,
        "item_hash": None,
        "observation_id": observation_id,
        "channel_name": "Hosted Proof Channel",
        "model_version": artifact_provenance.get("model_version") or "bootstrap-v0",
        "policy_version": artifact_provenance.get("policy_version") or "unknown-policy",
        "action_shown": score_result.get("recommended_action", "none"),
        "user_action": "confirm-report",
        "explanation_id": score_result.get("explanation_id"),
        "before_score": score_result.get("risk_score"),
        "after_score": score_result.get("risk_score"),
        "timestamp": _utc_now(),
        "runtime_context": {
            "surface": "extension-feed",
            "review_requested": False,
            "source_provenance": run_id,
        },
        "manual_report": {
            "workflow_mode": "report",
            "target_url": f"https://www.youtube.com/watch?v={run_id}",
            "title_snapshot": "Breaking orbital weather bulletin shocks viewers",
            "issues": [
                {
                    "issue_type": "title",
                    "comment": "Hosted beta proof event for persistence verification.",
                }
            ],
            "requested_outcome": "moderate",
            "selected_tags": ["Clickbait"],
            "optimize_requested": False,
            "optimize_applied": False,
            "report_text": "Hosted beta proof report to confirm feedback persistence.",
        },
    }


def _get_json(client: httpx.Client, base_url: str, path: str) -> tuple[int, dict[str, Any] | None, str]:
    response = client.get(f"{base_url}{path}")
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        return response.status_code, response.json(), response.text
    return response.status_code, None, response.text


def _post_json(
    client: httpx.Client, base_url: str, path: str, payload: dict[str, Any]
) -> tuple[int, dict[str, Any] | None, str]:
    response = client.post(f"{base_url}{path}", json=payload)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        return response.status_code, response.json(), response.text
    return response.status_code, None, response.text


def build_report(base_url: str, *, write_events: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "generated_at": _utc_now(),
        "base_url": base_url,
        "live_service": {},
        "endpoint_checks": {},
        "write_checks": None,
        "closure_status": {
            "closed": [],
            "open": [],
        },
    }
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        health_status, health_json, _ = _get_json(client, base_url, "/health")
        ready_status, ready_json, _ = _get_json(client, base_url, "/ready")
        model_status, model_json, _ = _get_json(client, base_url, "/model-info")
        policy_status, policy_json, _ = _get_json(client, base_url, "/policy-info")
        metrics_status, _, metrics_text = _get_json(client, base_url, "/metrics")

        report["live_service"] = {
            "health_status": health_status,
            "ready_status": ready_status,
            "model_info_status": model_status,
            "policy_info_status": policy_status,
            "metrics_status": metrics_status,
            "event_store": (health_json or {}).get("event_store"),
            "env": (health_json or {}).get("env"),
            "ready": (ready_json or {}).get("ready"),
            "ready_artifact_status": (ready_json or {}).get("artifact_status"),
            "model_version": (model_json or {}).get("model_version"),
            "model_mode": (model_json or {}).get("mode"),
            "model_artifact_status": (model_json or {}).get("artifact_status"),
            "policy_version": (policy_json or {}).get("policy_version"),
            "policy_mode": (policy_json or {}).get("policy_mode"),
            "resolved_policy_mode": (policy_json or {}).get("resolved_policy_mode"),
            "metrics": {
                "score_events_total": _metric_value(metrics_text, "truthlens_score_events_total"),
                "feedback_events_total": _metric_value(metrics_text, "truthlens_feedback_events_total"),
                "browser_observations_total": _metric_value(
                    metrics_text, "truthlens_browser_observations_total"
                ),
                "bseo_artifact_available": _metric_value(
                    metrics_text, "truthlens_policy_bseo_artifact_available"
                ),
            },
        }
        report["endpoint_checks"] = {
            "get": {
                "/health": health_status,
                "/ready": ready_status,
                "/model-info": model_status,
                "/policy-info": policy_status,
                "/metrics": metrics_status,
            }
        }

        report["closure_status"]["closed"].extend(
            [
                "live-host-confirmed",
                "public-api-base-confirmed-externally",
                "live-ready-health-confirmed",
                "hosted-get-endpoints-confirmed",
            ]
        )

        if (model_json or {}).get("artifact_status") != "compatible":
            report["closure_status"]["open"].append("runtime-model-bundle-proof")
        if (model_json or {}).get("mode") == "bootstrap":
            report["closure_status"]["open"].append("non-bootstrap-runtime-model")
        report["closure_status"]["open"].append("extension-to-live-host-proof")

        if write_events:
            run_id = f"hosted-proof-{int(time())}"
            first_item_id = f"{run_id}-score-1"
            score_payload = _score_payload(
                run_id,
                item_id=first_item_id,
                title="Breaking orbital weather bulletin shocks viewers",
            )
            second_score_payload = _score_payload(
                run_id,
                item_id=f"{run_id}-score-2",
                title="Urgent hidden archive finally revealed",
            )
            metrics_before = report["live_service"]["metrics"]

            score_status, score_json, _ = _post_json(client, base_url, "/score-item", score_payload)
            batch_status, batch_json, _ = _post_json(
                client,
                base_url,
                "/batch-score",
                {"items": [score_payload, second_score_payload]},
            )
            observation_payload = _observation_payload(
                run_id,
                item_id=first_item_id,
                title=score_payload["title"],
            )
            observation_status, observation_json, _ = _post_json(
                client, base_url, "/browser-observation", observation_payload
            )
            feedback_payload = _feedback_payload(
                run_id,
                item_id=first_item_id,
                observation_id=observation_payload["observation_id"],
                score_result=score_json or {},
            )
            feedback_status, feedback_json, _ = _post_json(client, base_url, "/feedback", feedback_payload)
            feedback_summary_status, feedback_summary_json, _ = _get_json(
                client, base_url, "/feedback-summary"
            )
            _, _, metrics_after_text = _get_json(client, base_url, "/metrics")
            metrics_after = {
                "score_events_total": _metric_value(metrics_after_text, "truthlens_score_events_total"),
                "feedback_events_total": _metric_value(metrics_after_text, "truthlens_feedback_events_total"),
                "browser_observations_total": _metric_value(
                    metrics_after_text, "truthlens_browser_observations_total"
                ),
            }
            persistence_proven = (
                report["live_service"]["event_store"] == "postgres"
                and observation_status == 200
                and feedback_status == 200
                and (metrics_after["feedback_events_total"] or 0.0)
                > (metrics_before.get("feedback_events_total") or 0.0)
                and (metrics_after["browser_observations_total"] or 0.0)
                > (metrics_before.get("browser_observations_total") or 0.0)
            )
            if persistence_proven:
                report["closure_status"]["closed"].append("postgres-feedback-observation-proof")
            else:
                report["closure_status"]["open"].append("postgres-feedback-observation-proof")

            report["write_checks"] = {
                "run_id": run_id,
                "post": {
                    "/score-item": score_status,
                    "/batch-score": batch_status,
                    "/browser-observation": observation_status,
                    "/feedback": feedback_status,
                    "/feedback-summary": feedback_summary_status,
                },
                "result_excerpt": {
                    "score_recommended_action": (score_json or {}).get("recommended_action"),
                    "score_policy_mode": (score_json or {}).get("policy_mode"),
                    "score_resolved_policy_mode": (score_json or {}).get("resolved_policy_mode"),
                    "score_model_version": ((score_json or {}).get("artifact_provenance") or {}).get(
                        "model_version"
                    ),
                    "batch_result_count": len((batch_json or {}).get("results", {})),
                    "feedback_status": (feedback_json or {}).get("status"),
                    "observation_status": (observation_json or {}).get("status"),
                    "feedback_summary_total_events": (feedback_summary_json or {}).get("total_events"),
                },
                "metrics_before": metrics_before,
                "metrics_after": metrics_after,
                "postgres_persistence_proven": persistence_proven,
            }

    report["closure_status"]["closed"] = sorted(set(report["closure_status"]["closed"]))
    report["closure_status"]["open"] = sorted(set(report["closure_status"]["open"]))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the hosted TruthLens beta contract.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--write-events",
        action="store_true",
        help="POST score, browser observation, and feedback samples to prove hosted persistence.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Optional path to write the JSON verification report.",
    )
    args = parser.parse_args()

    report = build_report(_normalize_base_url(args.base_url), write_events=args.write_events)
    payload = json.dumps(report, indent=2, ensure_ascii=True)
    if args.report_path is not None:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
