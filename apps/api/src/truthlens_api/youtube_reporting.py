from __future__ import annotations

import secrets
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse

import httpx

from truthlens_api.settings import settings
from truthlens_data_pipeline.paths import ensure_dir, read_json, resolve_runtime_path, write_json
from truthlens_shared_schemas.contracts import (
    YouTubeAuthStatus,
    YouTubeReportRequest,
    YouTubeReportResponse,
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
MISLEADING_PRIMARY_REASON_ID = "S"
MISLEADING_THUMBNAIL_SECONDARY_REASON_ID = "28"
OTHER_MISLEADING_INFO_SECONDARY_REASON_ID = "31"


class YouTubeDirectReportingUnsupportedError(RuntimeError):
    """Raised when the current YouTube account cannot use the direct reporting API for misleading content."""


def youtube_reporting_configured() -> bool:
    return bool(
        (settings.youtube_client_id or "").strip()
        and (settings.youtube_client_secret or "").strip()
        and settings.resolved_youtube_redirect_uri.strip()
    )


def _token_path() -> Path:
    return resolve_runtime_path(settings.youtube_token_path)


def _oauth_state_path() -> Path:
    return resolve_runtime_path(settings.youtube_oauth_state_path)


def _read_json_file(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    payload = read_json(path)
    if not isinstance(payload, dict):
        return None
    return payload


def _write_json_file(path: Path, payload: dict[str, object]) -> None:
    ensure_dir(path.parent)
    write_json(path, payload)


def _build_auth_url(state: str) -> str:
    query = urlencode(
        {
            "client_id": settings.youtube_client_id or "",
            "redirect_uri": settings.resolved_youtube_redirect_uri,
            "response_type": "code",
            "scope": settings.youtube_auth_scope,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
    )
    return f"{GOOGLE_AUTH_URL}?{query}"


def build_youtube_authorization_url() -> str:
    if not youtube_reporting_configured():
        raise RuntimeError("YouTube OAuth is not configured.")

    state = secrets.token_urlsafe(32)
    _write_json_file(
        _oauth_state_path(),
        {
            "state": state,
            "created_at": int(time.time()),
        },
    )
    return _build_auth_url(state)


def _load_token_payload() -> dict[str, object] | None:
    return _read_json_file(_token_path())


def _save_token_payload(payload: dict[str, object]) -> None:
    payload["stored_at"] = int(time.time())
    _write_json_file(_token_path(), payload)


def _authorized_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def _token_is_still_valid(token_payload: dict[str, object]) -> bool:
    access_token = str(token_payload.get("access_token") or "").strip()
    expires_in = int(token_payload.get("expires_in") or 0)
    stored_at = int(token_payload.get("stored_at") or 0)
    return bool(access_token) and (stored_at + expires_in - 60) > int(time.time())


def _refresh_access_token(token_payload: dict[str, object]) -> dict[str, object]:
    refresh_token = str(token_payload.get("refresh_token") or "").strip()
    if not refresh_token:
        raise RuntimeError("Stored YouTube OAuth token does not include a refresh token.")

    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.youtube_client_id or "",
            "client_secret": settings.youtube_client_secret or "",
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30.0,
    )
    response.raise_for_status()
    refreshed = response.json()
    refreshed["refresh_token"] = refreshed.get("refresh_token") or refresh_token
    _save_token_payload(refreshed)
    return refreshed


def _get_access_token() -> str:
    if not youtube_reporting_configured():
        raise RuntimeError("YouTube OAuth is not configured.")

    token_payload = _load_token_payload()
    if not token_payload:
        raise RuntimeError("YouTube OAuth has not been connected yet.")

    if not _token_is_still_valid(token_payload):
        token_payload = _refresh_access_token(token_payload)

    access_token = str(token_payload.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError("YouTube OAuth token is missing an access token.")
    return access_token


def complete_youtube_authorization(code: str, state: str) -> None:
    if not youtube_reporting_configured():
        raise RuntimeError("YouTube OAuth is not configured.")

    expected_state = _read_json_file(_oauth_state_path())
    if not expected_state or expected_state.get("state") != state:
        raise ValueError("YouTube OAuth state did not match the pending authorization request.")

    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.youtube_client_id or "",
            "client_secret": settings.youtube_client_secret or "",
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.resolved_youtube_redirect_uri,
        },
        timeout=30.0,
    )
    response.raise_for_status()
    _save_token_payload(response.json())

    state_path = _oauth_state_path()
    if state_path.exists():
        state_path.unlink()


def _fetch_connected_channel_name(access_token: str) -> str | None:
    response = httpx.get(
        f"{YOUTUBE_API_BASE}/channels",
        headers=_authorized_headers(access_token),
        params={"part": "snippet", "mine": "true"},
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("items", [])
    if not items:
        return None
    snippet = items[0].get("snippet", {})
    if not isinstance(snippet, dict):
        return None
    title = snippet.get("title")
    return title if isinstance(title, str) else None


def get_youtube_auth_status() -> YouTubeAuthStatus:
    if not youtube_reporting_configured():
        return YouTubeAuthStatus(
            configured=False,
            connected=False,
            auth_url=None,
            channel_name=None,
            direct_reporting_supported=False,
            direct_reporting_detail=(
                "Add TRUTHLENS_YOUTUBE_CLIENT_ID, TRUTHLENS_YOUTUBE_CLIENT_SECRET, "
                "and TRUTHLENS_PUBLIC_API_BASE or TRUTHLENS_YOUTUBE_REDIRECT_URI to enable direct reporting."
            ),
        )

    token_payload = _load_token_payload()
    if not token_payload:
        return YouTubeAuthStatus(
            configured=True,
            connected=False,
            auth_url=build_youtube_authorization_url(),
            channel_name=None,
            direct_reporting_supported=False,
            direct_reporting_detail=(
                "Connect your YouTube account to let TruthLens submit direct reports."
            ),
        )

    try:
        access_token = _get_access_token()
        channel_name = _fetch_connected_channel_name(access_token)
    except (RuntimeError, httpx.HTTPError):
        return YouTubeAuthStatus(
            configured=True,
            connected=False,
            auth_url=build_youtube_authorization_url(),
            channel_name=None,
            direct_reporting_supported=False,
            direct_reporting_detail=(
                "TruthLens could not refresh the current YouTube authorization."
            ),
        )

    if not settings.youtube_direct_reporting_enabled:
        direct_reporting_supported = False
        direct_reporting_detail = (
            "Direct YouTube API reporting is turned off for this deployment. "
            "Set TRUTHLENS_YOUTUBE_DIRECT_REPORTING_ENABLED=true to expose hosted OAuth/report-submit."
        )
    else:
        direct_reporting_supported, direct_reporting_detail = probe_direct_reporting_capability(access_token)
    return YouTubeAuthStatus(
        configured=True,
        connected=True,
        auth_url=None,
        channel_name=channel_name,
        direct_reporting_supported=direct_reporting_supported,
        direct_reporting_detail=direct_reporting_detail,
    )


def _extract_video_id(target_url: str) -> str:
    parsed = urlparse(target_url)
    if parsed.path == "/watch":
        query_pairs = dict(
            segment.split("=", maxsplit=1)
            for segment in parsed.query.split("&")
            if "=" in segment
        )
        video_id = query_pairs.get("v")
        if video_id:
            return video_id
    if parsed.path.startswith("/shorts/"):
        _, _, short_id = parsed.path.partition("/shorts/")
        if short_id:
            return short_id
    raise ValueError("Could not determine a YouTube video id from the target URL.")


def _list_video_report_reasons(access_token: str) -> list[dict[str, object]]:
    request_options = [
        {
            "part": "snippet",
            "hl": settings.youtube_language,
        },
        {
            "part": "snippet",
        },
    ]

    last_error: httpx.HTTPStatusError | None = None
    for params in request_options:
        try:
            response = httpx.get(
                f"{YOUTUBE_API_BASE}/videoAbuseReportReasons",
                headers=_authorized_headers(access_token),
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            payload = response.json()
            items = payload.get("items", [])
            return items if isinstance(items, list) else []
        except httpx.HTTPStatusError as error:
            last_error = error
            if error.response.status_code != 400:
                raise

    if last_error is not None:
        raise last_error
    return []


def _pick_secondary_reason(
    reason: dict[str, object],
    issue_types: list[str],
) -> dict[str, str] | None:
    snippet = reason.get("snippet", {})
    if not isinstance(snippet, dict):
        return None
    secondary_reasons = snippet.get("secondaryReasons", [])
    if not isinstance(secondary_reasons, list) or not secondary_reasons:
        return None

    issue_set = set(issue_types)
    preferred_secondary_ids: list[str] = []
    if issue_set == {"thumbnail"}:
        preferred_secondary_ids.append(MISLEADING_THUMBNAIL_SECONDARY_REASON_ID)
    else:
        preferred_secondary_ids.append(OTHER_MISLEADING_INFO_SECONDARY_REASON_ID)
        if "thumbnail" in issue_set:
            preferred_secondary_ids.append(MISLEADING_THUMBNAIL_SECONDARY_REASON_ID)

    for preferred_id in preferred_secondary_ids:
        for entry in secondary_reasons:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("id") or "").strip() == preferred_id:
                label = str(entry.get("label") or "").strip()
                if label:
                    return {"id": preferred_id, "label": label}

    for entry in secondary_reasons:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or "").strip()
        if any(keyword in label.lower() for keyword in ("misleading", "spam", "scam", "deceptive")):
            return {
                "id": str(entry.get("id") or ""),
                "label": label,
            }
    entry = secondary_reasons[0]
    if not isinstance(entry, dict):
        return None
    secondary_id = str(entry.get("id") or "").strip()
    secondary_label = str(entry.get("label") or "").strip()
    if not secondary_id or not secondary_label:
        return None
    return {"id": secondary_id, "label": secondary_label}


def _choose_best_reason(
    reasons: list[dict[str, object]],
    issue_types: list[str],
) -> tuple[dict[str, str], dict[str, str] | None]:
    preferred_reason: dict[str, str] | None = None
    for reason in reasons:
        snippet = reason.get("snippet", {})
        if not isinstance(snippet, dict):
            continue
        label = str(snippet.get("label") or "").strip()
        reason_id = str(reason.get("id") or "").strip()
        if not reason_id or not label:
            continue
        if reason_id == MISLEADING_PRIMARY_REASON_ID:
            preferred_reason = {"id": reason_id, "label": label}
            return preferred_reason, _pick_secondary_reason(reason, issue_types)
        if preferred_reason is None and any(
            keyword in label.lower() for keyword in ("misleading", "deceptive", "spam", "scam")
        ):
            preferred_reason = {"id": reason_id, "label": label}

    if preferred_reason is None:
        available_labels = []
        for reason in reasons:
            snippet = reason.get("snippet", {})
            if not isinstance(snippet, dict):
                continue
            label = str(snippet.get("label") or "").strip()
            if label:
                available_labels.append(label)
        raise RuntimeError(
            "YouTube did not return a suitable 'Spam or misleading' report category for this account. "
            f"Available categories: {', '.join(available_labels) if available_labels else 'none'}."
        )

    matched_reason = next(
        (
            reason
            for reason in reasons
            if str(reason.get("id") or "").strip() == preferred_reason["id"]
        ),
        None,
    )
    return preferred_reason, _pick_secondary_reason(matched_reason or {}, issue_types)


def probe_direct_reporting_capability(access_token: str) -> tuple[bool, str | None]:
    try:
        reasons = _list_video_report_reasons(access_token)
        _choose_best_reason(reasons, ["title", "thumbnail"])
    except RuntimeError as error:
        return False, str(error)
    except httpx.HTTPError as error:
        return False, f"TruthLens could not verify direct YouTube reporting capability: {error}"
    return True, "Direct YouTube API reporting is available for this account."


def submit_youtube_report(payload: YouTubeReportRequest) -> YouTubeReportResponse:
    if not settings.youtube_direct_reporting_enabled:
        raise YouTubeDirectReportingUnsupportedError(
            "Direct YouTube API reporting is turned off for this deployment."
        )
    access_token = _get_access_token()
    video_id = _extract_video_id(payload.target_url)
    reasons = _list_video_report_reasons(access_token)
    try:
        selected_reason, selected_secondary_reason = _choose_best_reason(reasons, payload.issue_types)
    except RuntimeError as error:
        raise YouTubeDirectReportingUnsupportedError(str(error)) from error

    report_payload: dict[str, object] = {
        "videoId": video_id,
        "reasonId": selected_reason["id"],
        "comments": payload.report_text[:1000],
    }
    if selected_secondary_reason is not None:
        report_payload["secondaryReasonId"] = selected_secondary_reason["id"]

    response = httpx.post(
        f"{YOUTUBE_API_BASE}/videos/reportAbuse",
        headers=_authorized_headers(access_token),
        json=report_payload,
        timeout=30.0,
    )
    response.raise_for_status()

    return YouTubeReportResponse(
        status="reported",
        reason_id=selected_reason["id"],
        reason_label=selected_reason["label"],
        secondary_reason_id=selected_secondary_reason["id"]
        if selected_secondary_reason is not None
        else None,
        secondary_reason_label=selected_secondary_reason["label"]
        if selected_secondary_reason is not None
        else None,
    )
