from __future__ import annotations

import json
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from truthlens_model_serving import summarize_feedback_events
from truthlens_shared_schemas.contracts import (
    ItemMetadata,
    ManualReportWorkflowMode,
    MobileResolvedWatchContext,
    ReviewPhase,
    ReviewPromptState,
    ReviewStatusEvent,
    ScoreResult,
)

WATCH_HEADERS = {
    "User-Agent": "TruthLensMobile/0.1 (+https://github.com/pt2710/TruthLens---Browser-plugin)",
}

TRANSPARENT_REVIEW_CLASSES = {"music", "art", "gaming"}
AMBIGUOUS_REVIEW_CLASSES = {"satire"}
SEVERE_NEGATIVE_BIASES = {
    "sensational-overweighting",
    "channel-lock-in-risk",
}


def _extract_video_id(target_url: str) -> str:
    parsed = urlparse(target_url)
    if parsed.netloc in {"youtu.be", "www.youtu.be"} and parsed.path.strip("/"):
        return parsed.path.strip("/")
    if parsed.path == "/watch":
        query_pairs = parse_qs(parsed.query)
        video_id = query_pairs.get("v", [""])[0]
        if video_id:
            return video_id
    if parsed.path.startswith("/shorts/"):
        _, _, short_id = parsed.path.partition("/shorts/")
        if short_id:
            return short_id
    raise ValueError("Could not determine a YouTube video id from the shared URL.")


def _extract_balanced_json_blob(html: str, marker: str) -> dict[str, Any] | None:
    marker_index = html.find(marker)
    if marker_index == -1:
        return None
    start_index = html.find("{", marker_index)
    if start_index == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start_index, len(html)):
        character = html[index]
        if in_string:
            if escape:
                escape = False
            elif character == "\\":
                escape = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start_index : index + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _fetch_oembed(target_url: str) -> dict[str, Any]:
    response = httpx.get(
        "https://www.youtube.com/oembed",
        params={"url": target_url, "format": "json"},
        headers=WATCH_HEADERS,
        timeout=8.0,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("YouTube oEmbed did not return a valid object payload.")
    return payload


def _fetch_watch_html(video_id: str) -> str:
    target_url = f"https://www.youtube.com/watch?{urlencode({'v': video_id, 'hl': 'en'})}"
    response = httpx.get(target_url, headers=WATCH_HEADERS, timeout=10.0)
    response.raise_for_status()
    return response.text


def _clean_text_excerpt(text: str | None, *, limit: int = 320) -> str | None:
    if not text:
        return None
    cleaned = " ".join(unescape(text).replace("\n", " ").replace("\r", " ").split())
    if not cleaned:
        return None
    return cleaned[:limit].strip()


def _caption_excerpt_from_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None
    separator = "&" if "?" in base_url else "?"
    transcript_url = f"{base_url}{separator}fmt=json3"
    response = httpx.get(transcript_url, headers=WATCH_HEADERS, timeout=8.0)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        return None
    events = payload.get("events", [])
    if not isinstance(events, list):
        return None
    segments: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        segs = event.get("segs", [])
        if not isinstance(segs, list):
            continue
        for segment in segs:
            if not isinstance(segment, dict):
                continue
            text = segment.get("utf8")
            if isinstance(text, str):
                cleaned = text.strip()
                if cleaned:
                    segments.append(cleaned)
        if len(" ".join(segments)) >= 320:
            break
    return _clean_text_excerpt(" ".join(segments))


def _channel_context(channel_name: str) -> str | None:
    summary = summarize_feedback_events()
    profile = summary["channel_profiles"].get(channel_name.strip().lower())
    if not profile:
        return None
    reported = int(profile.get("reported_item_count", 0))
    transparent = int(profile.get("transparent_count", 0))
    trust_score = float(profile.get("trust_score", 0.0))
    if reported >= 2:
        return (
            f"TruthLens has already recorded {reported} prior reported items for this channel, "
            f"so the current packaging concern does not look isolated. Current local trust score: {trust_score:.1f}/10."
        )
    if transparent >= 2:
        return (
            f"TruthLens has already recorded {transparent} transparent-verification events for this channel. "
            f"Current local trust score: {trust_score:.1f}/10."
        )
    return None


def resolve_mobile_share_context(target_url: str) -> MobileResolvedWatchContext:
    video_id = _extract_video_id(target_url)
    oembed = _fetch_oembed(target_url)
    watch_html = _fetch_watch_html(video_id)
    player_response = _extract_balanced_json_blob(watch_html, "ytInitialPlayerResponse")
    if player_response is None:
        raise ValueError("Could not extract watch metadata from the YouTube watch page.")

    video_details = player_response.get("videoDetails", {})
    microformat = player_response.get("microformat", {}).get("playerMicroformatRenderer", {})
    captions = player_response.get("captions", {}).get("playerCaptionsTracklistRenderer", {})
    caption_tracks = captions.get("captionTracks", []) if isinstance(captions, dict) else []
    first_caption_track = caption_tracks[0] if isinstance(caption_tracks, list) and caption_tracks else {}
    transcript_excerpt = None
    if isinstance(first_caption_track, dict):
        try:
            transcript_excerpt = _caption_excerpt_from_base_url(str(first_caption_track.get("baseUrl") or ""))
        except httpx.HTTPError:
            transcript_excerpt = None

    title = str(video_details.get("title") or oembed.get("title") or "").strip()
    channel_name = str(video_details.get("author") or oembed.get("author_name") or "").strip()
    channel_url = str(
        microformat.get("ownerProfileUrl") or oembed.get("author_url") or ""
    ).strip() or None
    description_snapshot = _clean_text_excerpt(
        str(video_details.get("shortDescription") or microformat.get("description") or "")
    )
    thumbnail_ref = str(video_details.get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url") or oembed.get("thumbnail_url") or "").strip() or None
    transcript_available = bool(caption_tracks)
    metadata = ItemMetadata(
        upload_time=str(microformat.get("publishDate") or microformat.get("uploadDate") or "").strip() or None,
        duration_seconds=int(str(video_details.get("lengthSeconds") or "0") or 0) or None,
        view_count=int(str(video_details.get("viewCount") or "0") or 0) or None,
        like_count=None,
    )
    return MobileResolvedWatchContext(
        target_url=target_url,
        video_id=video_id,
        title=title,
        thumbnail_ref=thumbnail_ref,
        channel_name=channel_name,
        channel_url=channel_url,
        description_snapshot=description_snapshot,
        transcript_excerpt=transcript_excerpt,
        transcript_available=transcript_available,
        channel_context=_channel_context(channel_name),
        metadata=metadata,
    )


def infer_review_prompt_state(
    score: ScoreResult,
    *,
    music_likelihood: float,
) -> ReviewPromptState | None:
    bounded_music_likelihood = min(max(float(music_likelihood), 0.0), 1.0)
    resolved_class = (
        score.content_class.value
        if hasattr(score.content_class, "value")
        else str(score.content_class)
    ).strip().lower()
    content_class_confidence = float(score.content_class_confidence)
    negative_biases = {
        str(bias).strip().lower()
        for bias in score.bias_profile.negative_biases
    }
    if score.recommended_action == "ask-report":
        return ReviewPromptState(
            workflow_mode=ManualReportWorkflowMode.REPORT,
            label="Review report",
            reason="TruthLens wants a manual clickbait review for this item.",
            auto_open=score.confidence >= 0.8 and score.risk_score >= 0.68,
        )
    if (
        resolved_class in AMBIGUOUS_REVIEW_CLASSES
        and score.recommended_action in {"none", "badge", "blur"}
        and (
            "genre-confusion" in negative_biases
            or "uncertainty-miscalibration" in negative_biases
            or score.uncertainty >= 0.22
        )
    ):
        return ReviewPromptState(
            workflow_mode=ManualReportWorkflowMode.REPORT,
            label="Review ambiguity",
            reason="TruthLens sees satire-like or ambiguous packaging that still needs human confirmation.",
            auto_open=score.risk_score >= 0.28 or score.uncertainty >= 0.3,
        )
    if (
        (
            (
                resolved_class in TRANSPARENT_REVIEW_CLASSES
                and content_class_confidence >= 0.7
            )
            or (
                resolved_class == "unknown"
                and bounded_music_likelihood >= 0.5
            )
        )
        and score.risk_score <= 0.32
        and score.confidence >= 0.65
        and score.recommended_action in {"none", "badge"}
        and not negative_biases.intersection(SEVERE_NEGATIVE_BIASES)
    ):
        class_label = (
            resolved_class
            if resolved_class in TRANSPARENT_REVIEW_CLASSES
            else "music"
        )
        return ReviewPromptState(
            workflow_mode=ManualReportWorkflowMode.VERIFY_TRANSPARENT,
            label="Verify transparent",
            reason=f"TruthLens thinks this likely looks like transparent {class_label} content.",
            auto_open=(
                score.confidence >= 0.8
                and score.risk_score <= 0.18
                and score.uncertainty <= 0.18
                and (
                    content_class_confidence >= 0.84
                    or bounded_music_likelihood >= 0.72
                )
            ),
        )
    return None


def completed_status_event(
    phase: ReviewPhase,
    label: str,
    *,
    details: str | None = None,
) -> ReviewStatusEvent:
    return ReviewStatusEvent(
        phase=phase,
        label=label,
        status="completed",
        details=details,
    )
