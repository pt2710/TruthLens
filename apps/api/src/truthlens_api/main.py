from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic
import httpx
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from typing import Any

from truthlens_api.manual_reports import (
    _build_heuristic_suggestion_response,
    gemini_available,
    optimize_manual_report,
    suggest_manual_report,
)
from truthlens_api.annotation_review import (
    SaveAnnotationAdjudicationsRequest,
    SaveAnnotationAdjudicationsResponse,
    build_annotation_batch_response,
    save_annotation_adjudications,
)
from truthlens_api.mobile import (
    completed_status_event,
    infer_review_prompt_state,
    resolve_mobile_share_context,
)
from truthlens_api.settings import settings
from truthlens_api.youtube_reporting import (
    build_youtube_authorization_url,
    complete_youtube_authorization,
    get_youtube_auth_status,
    submit_youtube_report,
    youtube_reporting_configured,
)
from truthlens_model_serving import (
    append_feedback_event,
    append_score_event,
    describe_model,
    predict_item_signals,
    summarize_feedback_events,
    summarize_score_events,
)
from truthlens_policy_engine import get_policy_profile, score_item
from truthlens_shared_schemas.contracts import (
    BatchScoreRequest,
    BatchScoreResponse,
    ExplanationBundlePayload,
    FeedbackEvent,
    ManualReportWorkflowMode,
    MobileAnalyzeShareRequest,
    MobileAnalyzeShareResponse,
    ManualReportOptimizationRequest,
    ManualReportOptimizationResponse,
    ManualReportSuggestionRequest,
    ManualReportSuggestionResponse,
    ScoreItemRequest,
    ScoreResult,
    YouTubeAuthStatus,
    YouTubeReportRequest,
    YouTubeReportResponse,
)

app = FastAPI(title="TruthLens API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=(
        r"^https://www\.youtube\.com$|"
        r"^chrome-extension://.*$|"
        r"^http://(127\.0\.0\.1|localhost)(:\d+)?$"
    ),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,
)
_REQUEST_WINDOWS: dict[str, list[float]] = {}
_REQUEST_COUNTS: dict[str, int] = {}


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit_score_event(
    payload: ScoreItemRequest,
    result: ScoreResult,
    *,
    model_version: str,
    policy_version: str,
) -> None:
    append_score_event(
        {
            "item_id": payload.item_id,
            "channel_name": payload.channel.channel_name,
            "model_version": model_version,
            "policy_version": policy_version,
            "recommended_action": result.recommended_action.value,
            "risk_score": result.risk_score,
            "confidence": result.confidence,
            "uncertainty": result.uncertainty,
            "explanation_id": result.explanation_id,
            "timestamp": _utc_timestamp(),
        }
    )


def _record_request(path: str) -> None:
    _REQUEST_COUNTS[path] = _REQUEST_COUNTS.get(path, 0) + 1


def _request_key(request: Request) -> str:
    host = request.client.host if request.client is not None else "unknown"
    return f"{host}:{request.url.path}"


def _enforce_rate_limit(request: Request) -> JSONResponse | None:
    if request.method == "OPTIONS":
        return None
    if settings.rate_limit_per_minute <= 0:
        return None
    key = _request_key(request)
    now = monotonic()
    window = _REQUEST_WINDOWS.setdefault(key, [])
    _REQUEST_WINDOWS[key] = [timestamp for timestamp in window if now - timestamp < 60.0]
    if len(_REQUEST_WINDOWS[key]) >= settings.rate_limit_per_minute:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded."},
        )
    _REQUEST_WINDOWS[key].append(now)
    return None


def _enforce_api_key(request: Request) -> JSONResponse | None:
    if request.method == "OPTIONS":
        return None
    if not settings.require_api_key:
        return None
    if request.url.path == "/health":
        return None
    expected = settings.api_key or ""
    presented = request.headers.get("x-truthlens-api-key", "")
    if not expected or presented != expected:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid API key."},
        )
    return None


@app.middleware("http")
async def security_middleware(request: Request, call_next: Any) -> Any:
    api_key_response = _enforce_api_key(request)
    if api_key_response is not None:
        api_key_response.headers["X-TruthLens-Request-Id"] = f"req-{uuid4().hex[:12]}"
        return api_key_response
    rate_limit_response = _enforce_rate_limit(request)
    request_id = f"req-{uuid4().hex[:12]}"
    if rate_limit_response is not None:
        rate_limit_response.headers["X-TruthLens-Request-Id"] = request_id
        return rate_limit_response

    response = await call_next(request)
    _record_request(request.url.path)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-TruthLens-Request-Id"] = request_id
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.env}


@app.get("/ready")
def ready() -> dict[str, object]:
    model = describe_model()
    policy = get_policy_profile()
    artifact_status = str(model.get("artifact_status", "missing"))
    return {
        "ready": artifact_status != "incompatible",
        "artifact_status": artifact_status,
        "policy_version": policy.get("policy_version"),
        "model_version": model.get("model_version"),
    }


@app.get("/model-info")
def model_info() -> dict[str, object]:
    return describe_model()


@app.get("/policy-info")
def policy_info() -> dict[str, object]:
    return get_policy_profile()


@app.post("/score-item", response_model=ScoreResult)
def score_single_item(payload: ScoreItemRequest) -> ScoreResult:
    result = score_item(payload)
    model_version = str(describe_model().get("model_version", "bootstrap-v0"))
    policy_version = str(get_policy_profile().get("policy_version", "adaptive-threshold-v1"))
    _audit_score_event(
        payload,
        result,
        model_version=model_version,
        policy_version=policy_version,
    )
    return result


@app.post("/batch-score", response_model=BatchScoreResponse)
def batch_score(payload: BatchScoreRequest) -> BatchScoreResponse:
    model_version = str(describe_model().get("model_version", "bootstrap-v0"))
    policy_version = str(get_policy_profile().get("policy_version", "adaptive-threshold-v1"))
    results: dict[str, ScoreResult] = {}
    for item in payload.items:
        result = score_item(item)
        results[item.item_id] = result
        _audit_score_event(
            item,
            result,
            model_version=model_version,
            policy_version=policy_version,
        )
    return BatchScoreResponse(results=results)


@app.post("/feedback")
def feedback(payload: FeedbackEvent) -> dict[str, str]:
    append_feedback_event(payload.model_dump())
    return {"status": "accepted", "feedback_log_path": settings.feedback_log_path}


@app.get("/annotation-batch/latest")
def annotation_batch_latest() -> dict[str, Any]:
    try:
        return build_annotation_batch_response()
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@app.post("/annotation-batch/adjudications", response_model=SaveAnnotationAdjudicationsResponse)
def annotation_batch_adjudications(
    payload: SaveAnnotationAdjudicationsRequest,
) -> SaveAnnotationAdjudicationsResponse:
    try:
        return save_annotation_adjudications(payload)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@app.post("/mobile/analyze-share", response_model=MobileAnalyzeShareResponse)
def mobile_analyze_share(payload: MobileAnalyzeShareRequest) -> MobileAnalyzeShareResponse:
    status_stream = []
    try:
        watch_context = resolve_mobile_share_context(payload.target_url)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not resolve the shared YouTube URL: {error}",
        ) from error

    status_stream.append(
        completed_status_event(
            "resolve-share",
            "Resolved shared YouTube URL.",
            details=f"Video id: {watch_context.video_id}",
        )
    )
    status_stream.append(
        completed_status_event(
            "fetch-watch-metadata",
            "Fetched watch metadata and transcript context.",
            details=(
                "Transcript was exposed."
                if watch_context.transcript_available
                else "Transcript was not exposed for this video."
            ),
        )
    )

    feedback_summary = summarize_feedback_events()
    channel_profile = feedback_summary["channel_profiles"].get(watch_context.channel_name.strip().lower(), {})
    reported_item_count = int(channel_profile.get("reported_item_count", 0))
    transparent_count = int(channel_profile.get("transparent_count", 0))
    scored_item_count = max(int(channel_profile.get("scored_item_count", 0)), 1)
    trust_score = float(channel_profile.get("trust_score", 5.0))

    score_request = ScoreItemRequest(
        item_id=watch_context.video_id,
        title=watch_context.title,
        thumbnail_ref=watch_context.thumbnail_ref,
        description_snapshot=watch_context.description_snapshot,
        transcript_excerpt=watch_context.transcript_excerpt,
        metadata=watch_context.metadata,
        channel={
            "channel_name": watch_context.channel_name,
            "channel_url": watch_context.channel_url,
            "prior_flags": reported_item_count,
            "channel_history_features": {
                "channel_risk_mean": round(max(0.0, min(1.0, 1.0 - (trust_score / 10.0))), 4),
                "repeat_template_rate": round(reported_item_count / max(scored_item_count, 1), 4),
                "transparent_count": float(transparent_count),
                "reported_item_count": float(reported_item_count),
            },
        },
        user_context=payload.user_context,
    )
    signals = predict_item_signals(score_request)
    score_result = score_item(score_request)
    model_version = str(describe_model().get("model_version", "bootstrap-v0"))
    policy_version = str(get_policy_profile().get("policy_version", "adaptive-threshold-v1"))
    music_likelihood = float(signals.feature_summary.get("music_likelihood", 0.0))
    watch_context = watch_context.model_copy(
        update={
            "music_likelihood": music_likelihood,
            "content_class": score_result.content_class,
            "content_class_confidence": score_result.content_class_confidence,
        }
    )
    status_stream.append(
        completed_status_event(
            "score-item",
            "Scored the shared YouTube item.",
            details=f"Risk {score_result.risk_score:.2f}, action {score_result.recommended_action.value}.",
        )
    )

    review_prompt = infer_review_prompt_state(score_result, music_likelihood=music_likelihood)
    workflow_mode = (
        review_prompt.workflow_mode
        if review_prompt is not None
        else ManualReportWorkflowMode.REPORT
    )
    suggestion_request = ManualReportSuggestionRequest(
        workflow_mode=workflow_mode,
        target_url=watch_context.target_url,
        thumbnail_ref=watch_context.thumbnail_ref,
        title_snapshot=watch_context.title,
        channel_name=watch_context.channel_name,
        channel_url=watch_context.channel_url,
        channel_context=watch_context.channel_context,
        description_snapshot=watch_context.description_snapshot,
        transcript_excerpt=watch_context.transcript_excerpt,
        transcript_available=watch_context.transcript_available,
        explanation_summary=score_result.explanation_summary,
        reasons=score_result.reasons,
        content_class=score_result.content_class,
        content_class_confidence=score_result.content_class_confidence,
        bias_profile=score_result.bias_profile,
    )
    if gemini_available():
        try:
            draft_suggestion = suggest_manual_report(suggestion_request)
            suggestion_details = "Gemini-backed draft suggestions were prepared."
        except (httpx.HTTPError, ValueError):
            draft_suggestion = _build_heuristic_suggestion_response(suggestion_request)
            suggestion_details = "Gemini suggestions failed, so TruthLens returned heuristic draft suggestions."
    else:
        draft_suggestion = _build_heuristic_suggestion_response(suggestion_request)
        suggestion_details = "Gemini is unavailable, so TruthLens returned heuristic draft suggestions."
    status_stream.append(
        completed_status_event(
            "draft-review",
            "Prepared report or verification drafts.",
            details=suggestion_details,
        )
    )

    youtube_auth = YouTubeAuthStatus.model_validate(get_youtube_auth_status())
    status_stream.append(
        completed_status_event(
            "youtube-auth",
            "Checked YouTube reporting availability.",
            details=(
                f"Connected as {youtube_auth.channel_name}."
                if youtube_auth.connected and youtube_auth.channel_name
                else "Direct YouTube reporting is not connected yet."
            ),
        )
    )

    return MobileAnalyzeShareResponse(
        model_version=model_version,
        policy_version=policy_version,
        watch_context=watch_context,
        score=score_result,
        explanation=ExplanationBundlePayload(
            explanation_id=score_result.explanation_id,
            explanation_summary=score_result.explanation_summary,
            reasons=score_result.reasons,
            evidence=score_result.evidence,
        ),
        review_prompt=review_prompt,
        draft_suggestion=draft_suggestion,
        youtube_auth=youtube_auth,
        status_stream=status_stream,
    )


@app.post("/manual-report/optimize", response_model=ManualReportOptimizationResponse)
def optimize_report(
    payload: ManualReportOptimizationRequest,
) -> ManualReportOptimizationResponse:
    if not gemini_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini optimization is not configured for this API.",
        )
    try:
        return optimize_manual_report(payload)
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini optimization request failed: {error}",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini optimization response was invalid: {error}",
        ) from error


@app.post("/manual-report/suggest", response_model=ManualReportSuggestionResponse)
def suggest_report(
    payload: ManualReportSuggestionRequest,
) -> ManualReportSuggestionResponse:
    if not gemini_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini suggestions are not configured for this API.",
        )
    try:
        return suggest_manual_report(payload)
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini suggestion request failed: {error}",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini suggestion response was invalid: {error}",
        ) from error


@app.get("/youtube/auth/status", response_model=YouTubeAuthStatus)
def youtube_auth_status() -> YouTubeAuthStatus:
    return get_youtube_auth_status()


@app.get("/youtube/auth/start")
def youtube_auth_start() -> RedirectResponse:
    if not youtube_reporting_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="YouTube OAuth is not configured for this API.",
        )
    return RedirectResponse(url=build_youtube_authorization_url(), status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get("/youtube/auth/callback", response_class=HTMLResponse)
def youtube_auth_callback(code: str, state: str) -> HTMLResponse:
    try:
        complete_youtube_authorization(code, state)
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"YouTube OAuth token exchange failed: {error}",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return HTMLResponse(
        content=(
            "<html><body>"
            "<h1>TruthLens YouTube connection complete</h1>"
            "<p>You can close this tab and return to the extension.</p>"
            "</body></html>"
        )
    )


@app.post("/youtube/report", response_model=YouTubeReportResponse)
def youtube_report(payload: YouTubeReportRequest) -> YouTubeReportResponse:
    if not youtube_reporting_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="YouTube OAuth is not configured for this API.",
        )
    try:
        return submit_youtube_report(payload)
    except httpx.HTTPError as error:
        response_text = ""
        if isinstance(error, httpx.HTTPStatusError):
            response_text = error.response.text
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"YouTube report submission failed: {error}"
                + (f" | upstream body: {response_text}" if response_text else "")
            ),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@app.get("/feedback-summary")
def feedback_summary() -> dict[str, object]:
    return summarize_feedback_events()


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    score_summary = summarize_score_events()
    feedback_summary_payload = summarize_feedback_events()
    policy_profile_payload = get_policy_profile()
    runtime_metrics = policy_profile_payload.get("runtime_metrics", {})
    bseo_artifact = policy_profile_payload.get("bseo_artifact", {})
    rl_artifact = policy_profile_payload.get("rl_artifact", {})
    lines = [
        "# HELP truthlens_score_events_total Total scored items recorded by the API.",
        "# TYPE truthlens_score_events_total counter",
        f"truthlens_score_events_total {score_summary['total_events']}",
        "# HELP truthlens_feedback_events_total Total feedback events recorded by the API.",
        "# TYPE truthlens_feedback_events_total counter",
        f"truthlens_feedback_events_total {feedback_summary_payload['total_events']}",
        "# HELP truthlens_score_average_risk Average calibrated risk score over scored items.",
        "# TYPE truthlens_score_average_risk gauge",
        f"truthlens_score_average_risk {score_summary['average_risk_score']}",
        "# HELP truthlens_score_average_uncertainty Average uncertainty over scored items.",
        "# TYPE truthlens_score_average_uncertainty gauge",
        f"truthlens_score_average_uncertainty {score_summary['average_uncertainty']}",
        "# HELP truthlens_policy_fallback_rate Runtime BSEO fallback rate.",
        "# TYPE truthlens_policy_fallback_rate gauge",
        f"truthlens_policy_fallback_rate {runtime_metrics.get('fallback_rate', 0.0)}",
        "# HELP truthlens_policy_divergence_rate Runtime BSEO shadow divergence rate.",
        "# TYPE truthlens_policy_divergence_rate gauge",
        f"truthlens_policy_divergence_rate {runtime_metrics.get('divergence_rate', 0.0)}",
        "# HELP truthlens_policy_bseo_artifact_available Whether a BSEO policy artifact is available.",
        "# TYPE truthlens_policy_bseo_artifact_available gauge",
        f"truthlens_policy_bseo_artifact_available {1 if bseo_artifact.get('available') else 0}",
        "# HELP truthlens_policy_rl_artifact_available Whether an RL policy artifact is available.",
        "# TYPE truthlens_policy_rl_artifact_available gauge",
        f"truthlens_policy_rl_artifact_available {1 if rl_artifact.get('available') else 0}",
    ]
    for action, count in score_summary["action_counts"].items():
        lines.append(
            f'truthlens_score_action_total{{action="{action}"}} {count}'
        )
    for action, count in feedback_summary_payload["action_counts"].items():
        lines.append(
            f'truthlens_feedback_action_total{{action="{action}"}} {count}'
        )
    for action, count in runtime_metrics.get("final_action_counts", {}).items():
        lines.append(f'truthlens_policy_final_action_total{{action="{action}"}} {count}')
    for path, count in sorted(_REQUEST_COUNTS.items()):
        lines.append(f'truthlens_api_requests_total{{path="{path}"}} {count}')
    return "\n".join(lines) + "\n"
