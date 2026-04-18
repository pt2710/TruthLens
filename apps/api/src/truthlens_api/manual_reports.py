from __future__ import annotations

import base64
import json
import re

import httpx
from pydantic import ValidationError

from truthlens_api.settings import settings
from truthlens_model_serving import load_feedback_events, summarize_feedback_events
from truthlens_shared_schemas.contracts import (
    ManualReportIssue,
    ManualReviewTag,
    ManualReviewTagSelection,
    ManualReportOptimizationRequest,
    ManualReportOptimizationResponse,
    ManualReportRequestedOutcome,
    ManualReportSuggestionIssue,
    ManualReportSuggestionRequest,
    ManualReportSuggestionResponse,
    ManualReportWorkflowMode,
)

ISSUE_TYPES = (
    "thumbnail",
    "title",
    "description",
    "transcript",
    "channel",
    "other",
)

HEURISTIC_SUGGESTION_MODEL = "truthlens-heuristic-fallback-v1"
HEURISTIC_OPTIMIZATION_MODEL = "truthlens-heuristic-optimizer-v1"
STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "along",
    "also",
    "around",
    "before",
    "being",
    "between",
    "could",
    "does",
    "from",
    "have",
    "into",
    "just",
    "like",
    "made",
    "more",
    "most",
    "only",
    "over",
    "same",
    "should",
    "some",
    "than",
    "that",
    "their",
    "them",
    "there",
    "these",
    "this",
    "those",
    "through",
    "under",
    "very",
    "what",
    "when",
    "with",
    "would",
}
CLICKBAIT_MARKERS = (
    "stay out",
    "shouldn't",
    "shouldnt",
    "do not enter",
    "secret",
    "shocking",
    "exposed",
    "hidden",
    "warning",
    "must see",
    "don't",
    "dont",
    "you won't believe",
    "we shouldn't",
    "never",
    "banned",
)
ALIGNMENT_MARKERS = (
    "weakly aligned",
    "misaligned",
    "mismatch",
    "not consistent",
    "does not accurately represent",
    "misleading",
    "thumbnail",
    "title",
    "clickbait",
)
CHANNEL_PATTERN_MARKERS = (
    "systematic",
    "repeated deceptive",
    "repeated misleading",
    "synthetic spam",
    "ai-generated spam",
    "channel history",
)
POSITIVE_ALIGNMENT_MARKERS = (
    "consistent",
    "transparent",
    "honest",
    "non-clickbait",
    "broadly aligned",
)
MUSIC_TITLE_MARKERS = (
    "official audio",
    "official video",
    "music video",
    "lyric video",
    "lyrics",
    "visualizer",
    "visualiser",
    "remix",
    "cover",
    "instrumental",
    "live session",
    "live performance",
    "single",
    "album track",
    "feat.",
    " ft.",
)
MUSIC_CHANNEL_MARKERS = (
    "records",
    "music",
    "vevo",
    "topic",
    "beats",
    "orchestra",
    "choir",
    "band",
    "artist",
)
MUSIC_TRANSCRIPT_MARKERS = (
    "chorus",
    "verse",
    "refrain",
    "bridge",
    "lyrics",
    "♪",
)
NON_MUSIC_CONTEXT_MARKERS = (
    "trailer",
    "review",
    "documentary",
    "tutorial",
    "interview",
    "podcast",
    "news",
    "update",
    "walkthrough",
    "gameplay",
    "reaction",
)
TUTORIAL_MARKERS = (
    "tutorial",
    "how to",
    "how-to",
    "guide",
    "explained",
    "lesson",
    "learn",
)
WALKTHROUGH_MARKERS = (
    "walkthrough",
    "playthrough",
    "let's play",
    "lets play",
    "full run",
    "speedrun",
    "build guide",
)
TRANSPARENT_CONTEXT_CLASSES = {"music", "art", "gaming"}
FACTUAL_CONTEXT_CLASSES = {"news", "commentary", "documentary", "promo", "unknown"}
AMBIGUOUS_CONTEXT_CLASSES = {"satire"}
CLASS_LABELS = {
    "news": "news",
    "commentary": "commentary",
    "documentary": "documentary",
    "music": "music",
    "art": "art",
    "satire": "satire",
    "gaming": "gaming",
    "promo": "promotional",
    "unknown": "mixed or unclear",
}
MANUAL_REVIEW_TAG_ORDER = (
    ManualReviewTag.CLICKBAIT,
    ManualReviewTag.MUSIC,
    ManualReviewTag.TUTORIAL,
    ManualReviewTag.WALKTHROUGH,
    ManualReviewTag.GAMING,
    ManualReviewTag.NEWS,
    ManualReviewTag.DOCUMENTARY,
    ManualReviewTag.PROMO,
    ManualReviewTag.SATIRE,
    ManualReviewTag.ART,
    ManualReviewTag.UNKNOWN,
)


def _default_tag_rationale(tag: ManualReviewTag) -> str:
    return {
        ManualReviewTag.CLICKBAIT: "The packaging looks deceptive enough that TruthLens defaults to a clickbait review.",
        ManualReviewTag.MUSIC: "The packaging most strongly matches honest music content.",
        ManualReviewTag.TUTORIAL: "The title and surrounding context look closer to a tutorial than to deceptive packaging.",
        ManualReviewTag.WALKTHROUGH: "The visible framing looks like a walkthrough or gameplay run rather than deceptive packaging.",
        ManualReviewTag.GAMING: "The visible framing looks like ordinary gaming content.",
        ManualReviewTag.NEWS: "The visible framing looks like news or current-affairs content.",
        ManualReviewTag.DOCUMENTARY: "The visible framing looks like documentary or explanatory content.",
        ManualReviewTag.PROMO: "The visible framing looks like promotional or trailer-style content.",
        ManualReviewTag.SATIRE: "The visible framing looks like satire or parody content.",
        ManualReviewTag.ART: "The visible framing looks like art or creative work rather than deceptive packaging.",
        ManualReviewTag.UNKNOWN: "TruthLens could not resolve a stronger honest-content category from the available evidence.",
    }[tag]


def _selected_tag(
    tag: ManualReviewTag,
    *,
    selected: bool,
    confidence: float,
    rationale: str | None = None,
) -> ManualReviewTagSelection:
    bounded_confidence = max(0.0, min(1.0, confidence))
    return ManualReviewTagSelection(
        tag=tag,
        selected=selected,
        confidence=round(bounded_confidence, 4),
        rationale=rationale or _default_tag_rationale(tag),
    )


def _preferred_positive_tag(
    payload: ManualReportSuggestionRequest,
    resolved_class: str,
) -> ManualReviewTag:
    combined = " ".join(
        _normalize_text(part).lower()
        for part in (
            payload.title_snapshot,
            payload.description_snapshot,
            payload.transcript_excerpt,
            payload.channel_name,
            payload.channel_context,
        )
        if part
    )
    if _contains_any(combined, WALKTHROUGH_MARKERS):
        return ManualReviewTag.WALKTHROUGH
    if _contains_any(combined, TUTORIAL_MARKERS):
        return ManualReviewTag.TUTORIAL
    return {
        "music": ManualReviewTag.MUSIC,
        "gaming": ManualReviewTag.GAMING,
        "news": ManualReviewTag.NEWS,
        "documentary": ManualReviewTag.DOCUMENTARY,
        "promo": ManualReviewTag.PROMO,
        "satire": ManualReviewTag.SATIRE,
        "art": ManualReviewTag.ART,
    }.get(resolved_class, ManualReviewTag.UNKNOWN)


def _build_tag_suggestions(
    payload: ManualReportSuggestionRequest,
    *,
    resolved_class: str,
    base_confidence: float,
) -> list[ManualReviewTagSelection]:
    selected_tag = (
        ManualReviewTag.CLICKBAIT
        if payload.workflow_mode == ManualReportWorkflowMode.REPORT
        else _preferred_positive_tag(payload, resolved_class)
    )
    selected_confidence = 0.85 if selected_tag == ManualReviewTag.CLICKBAIT else max(
        0.45,
        min(0.95, base_confidence or 0.55),
    )
    selections: list[ManualReviewTagSelection] = []
    for tag in MANUAL_REVIEW_TAG_ORDER:
        if tag == selected_tag:
            rationale = (
                "Report mode assumes suspected deceptive packaging, so TruthLens preselects Clickbait unless you override it."
                if tag == ManualReviewTag.CLICKBAIT
                else _default_tag_rationale(tag)
            )
            selections.append(
                _selected_tag(
                    tag,
                    selected=True,
                    confidence=selected_confidence,
                    rationale=rationale,
                )
            )
            continue
        if payload.workflow_mode == ManualReportWorkflowMode.REPORT and tag != ManualReviewTag.CLICKBAIT:
            confidence = 0.18 if tag == _preferred_positive_tag(payload, resolved_class) else 0.05
        elif payload.workflow_mode == ManualReportWorkflowMode.VERIFY_TRANSPARENT:
            confidence = 0.24 if tag == ManualReviewTag.CLICKBAIT else 0.08
        else:
            confidence = 0.05
        selections.append(_selected_tag(tag, selected=False, confidence=confidence))
    return selections


def _build_outcome_reason(
    payload: ManualReportSuggestionRequest,
    *,
    resolved_class: str,
    suggested_outcome: ManualReportRequestedOutcome,
    has_channel_pattern: bool,
    weak_text_alignment: bool,
    title_clickbait: bool,
) -> str:
    if payload.workflow_mode == ManualReportWorkflowMode.VERIFY_TRANSPARENT:
        selected_tag = _preferred_positive_tag(payload, resolved_class).value
        return (
            f"TruthLens found the packaging broadly consistent and therefore recommends a transparency verification under {selected_tag}."
        )
    if suggested_outcome == ManualReportRequestedOutcome.REMOVE:
        return (
            "TruthLens recommends Remove because the packaging looks materially deceptive and the available evidence suggests a repeated or systematic pattern."
        )
    if has_channel_pattern:
        return (
            "TruthLens recommends Moderate because the current packaging looks misleading and the channel context adds enough concern for human review, but not enough committed evidence for automatic removal."
        )
    if weak_text_alignment or title_clickbait:
        return (
            "TruthLens recommends Moderate because the packaging overpromises relative to the visible description or transcript context."
        )
    return "TruthLens recommends Moderate because the packaging still needs a human clickbait review."


def gemini_available() -> bool:
    return bool((settings.gemini_api_key or "").strip())


def _issue_label(issue_type: str) -> str:
    labels = {
        "thumbnail": "Thumbnail",
        "title": "Title",
        "description": "Description",
        "transcript": "Transcript",
        "channel": "Channel",
        "other": "Other",
    }
    return labels.get(issue_type, issue_type.title())


def _outcome_label(outcome: ManualReportRequestedOutcome) -> str:
    return {
        ManualReportRequestedOutcome.MODERATE: "moderate",
        ManualReportRequestedOutcome.REMOVE: "remove",
    }[outcome]


def _gemini_headers() -> dict[str, str]:
    return {
        "x-goog-api-key": settings.gemini_api_key or "",
        "Content-Type": "application/json",
    }


def _infer_image_mime_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    mime_type = content_type.split(";", maxsplit=1)[0].strip().lower()
    if mime_type.startswith("image/"):
        return mime_type
    return None


def _thumbnail_inline_part(thumbnail_ref: str | None) -> dict[str, object] | None:
    if not thumbnail_ref:
        return None
    try:
        response = httpx.get(
            thumbnail_ref,
            follow_redirects=True,
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    mime_type = _infer_image_mime_type(response.headers.get("content-type"))
    if mime_type is None or not response.content:
        return None

    return {
        "inline_data": {
            "mime_type": mime_type,
            "data": base64.b64encode(response.content).decode("ascii"),
        }
    }


def _build_gemini_contents(
    prompt: str,
    *,
    thumbnail_ref: str | None = None,
) -> list[dict[str, object]]:
    parts: list[dict[str, object]] = []
    thumbnail_part = _thumbnail_inline_part(thumbnail_ref)
    if thumbnail_part is not None:
        parts.append(thumbnail_part)
    parts.append({"text": prompt})
    return [{"role": "user", "parts": parts}]


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _format_series(parts: list[str]) -> str:
    cleaned: list[str] = []
    for part in parts:
        normalized = _normalize_text(part)
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _excerpt_text(value: str, *, limit: int = 110) -> str:
    normalized = _normalize_text(value)
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}…"


def _sampled_channel_titles(channel_context: str) -> list[str]:
    normalized = _normalize_text(channel_context)
    if not normalized:
        return []
    quoted_titles = [
        _normalize_text(match)
        for match in re.findall(r'"([^"]+)"', normalized)
        if _normalize_text(match)
    ]
    if quoted_titles:
        return quoted_titles[:3]
    suffix = normalized.split(":", maxsplit=1)[-1]
    return [_normalize_text(part) for part in suffix.split(";") if _normalize_text(part)][:3]


def _collect_packaging_cues(
    *,
    title: str,
    description: str,
    explanation: str,
    reasons_text: str,
) -> list[str]:
    lower_title = title.lower()
    lower_description = description.lower()
    lower_context = f"{explanation} {reasons_text}".lower()
    cues: list[str] = []
    if "stay out" in lower_title:
        cues.append('warning wording like "STAY OUT"')
    if "do not enter" in lower_title:
        cues.append('forbidden-access wording like "DO NOT ENTER"')
    if any(marker in lower_title for marker in ("shouldn't", "shouldnt", "we shouldn't")):
        cues.append("forbidden-access phrasing")
    if any(marker in lower_title for marker in ("secret", "hidden", "exposed")):
        cues.append("secrecy cues")
    if any(marker in lower_title for marker in ("warning", "urgent", "must see", "shocking", "you won't believe", "never")):
        cues.append("shock or urgency cues")
    uppercase_match = re.search(
        r"\b[A-Z][A-Z'’\-]{2,}(?:\s+[A-Z][A-Z'’\-]{2,})*\b",
        title,
    )
    if uppercase_match:
        cues.append(f'all-caps emphasis like "{uppercase_match.group(0)}"')
    if any(marker in lower_context for marker in ("weakly aligned", "misaligned", "mismatch")):
        cues.append("a weak-alignment signal across the packaging")
    if "clickbait" in lower_context:
        cues.append("clickbait-style framing")
    if description and any(marker in lower_description for marker in CLICKBAIT_MARKERS):
        cues.append("description wording that repeats the same warning or curiosity framing")
    return cues


def _extract_title_signal_phrases(title: str) -> list[str]:
    patterns = (
        r"stay out",
        r"do not enter",
        r"we shouldn't",
        r"shouldn't",
        r"shouldnt",
        r"secret",
        r"hidden",
        r"exposed",
        r"warning",
        r"urgent",
        r"must see",
        r"you won't believe",
        r"never",
        r"banned",
    )
    phrases: list[str] = []
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            phrase = _normalize_text(match.group(0))
            lower_phrase = phrase.lower()
            if phrase and all(
                lower_phrase not in existing.lower() and existing.lower() not in lower_phrase
                for existing in phrases
            ):
                phrases.append(phrase)
    uppercase_match = re.search(
        r"\b[A-Z][A-Z'’\-]{2,}(?:\s+[A-Z][A-Z'’\-]{2,})*\b",
        title,
    )
    if uppercase_match:
        phrase = _normalize_text(uppercase_match.group(0))
        if phrase and phrase not in phrases:
            phrases.append(phrase)
    if not phrases:
        compact_title = _excerpt_text(title, limit=70)
        if compact_title:
            phrases.append(compact_title)
    return phrases[:3]


def _quoted_title_signal_summary(title: str) -> str:
    return _format_series([f'"{phrase}"' for phrase in _extract_title_signal_phrases(title)])


def _supporting_text_reference(description: str, transcript: str) -> str:
    references: list[str] = []
    if description:
        references.append(f'the description "{_excerpt_text(description)}"')
    if transcript:
        references.append(f'the transcript excerpt "{_excerpt_text(transcript)}"')
    if not references:
        return "the currently exposed supporting text"
    return _format_series(references)


def _channel_pattern_comment(
    *,
    sampled_titles: list[str],
    prior_report_count: int,
    prior_moderate_count: int,
    prior_remove_count: int,
) -> str:
    if prior_report_count > 0:
        return (
            f"TruthLens has already recorded {prior_report_count} prior report(s) for this channel, "
            f"including {prior_moderate_count} moderation request(s) and {prior_remove_count} removal request(s), "
            "so the current concern no longer looks isolated."
        )
    if not sampled_titles:
        return ""
    flagged_titles = [
        title
        for title in sampled_titles
        if _contains_any(title.lower(), CLICKBAIT_MARKERS)
    ]
    if len(flagged_titles) >= 2:
        sampled_excerpt = _format_series([f'"{title}"' for title in flagged_titles[:2]])
        return (
            f"Sampled channel titles such as {sampled_excerpt} reuse the same warning- or curiosity-driven packaging, "
            "which suggests the current video may be part of a recurring clickbait pattern rather than an isolated upload."
        )
    return ""


def _channel_report_context_comment(
    *,
    sampled_titles: list[str],
    has_recent_channel_context: bool,
) -> str:
    if not has_recent_channel_context:
        return ""
    if sampled_titles:
        sampled_excerpt = _format_series([f'"{title}"' for title in sampled_titles[:2]])
        return (
            f"This appears to be the first TruthLens report recorded for this channel. "
            f"Sampled recent titles such as {sampled_excerpt} do not yet prove a recurring pattern, "
            "so the current concern should be treated as potentially isolated unless similar reports continue."
        )
    return (
        "This appears to be the first TruthLens report recorded for this channel, "
        "so channel-wide pattern evidence is still limited and the current concern should be treated as potentially isolated for now."
    )


def _uses_benign_class_preface(comment: str) -> bool:
    normalized = _normalize_text(comment).lower()
    return normalized.startswith(
        (
            "this appears to be music content",
            "this appears to be art content",
            "this appears to be gaming content",
            "this appears to be satire content",
        )
    )


def _keyword_set(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9']+", text.lower())
        if len(token) >= 4 and token not in STOPWORDS
    }


def _token_overlap_ratio(left: str, right: str) -> float:
    left_tokens = _keyword_set(left)
    right_tokens = _keyword_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _count_phrase_hits(text: str, phrases: tuple[str, ...]) -> int:
    return sum(1 for phrase in phrases if phrase in text)


def _estimate_music_likelihood(
    *,
    title: str,
    description: str,
    transcript: str,
    channel_name: str,
    channel_context: str,
) -> float:
    lower_title = title.lower()
    lower_description = description.lower()
    lower_transcript = transcript.lower()
    lower_channel_name = channel_name.lower()
    lower_channel_context = channel_context.lower()
    title_hits = _count_phrase_hits(lower_title, MUSIC_TITLE_MARKERS)
    description_hits = _count_phrase_hits(lower_description, MUSIC_TITLE_MARKERS)
    channel_hits = _count_phrase_hits(
        f"{lower_channel_name} {lower_channel_context}",
        MUSIC_CHANNEL_MARKERS,
    )
    transcript_hits = _count_phrase_hits(lower_transcript, MUSIC_TRANSCRIPT_MARKERS)
    non_music_hits = _count_phrase_hits(
        f"{lower_title} {lower_description} {lower_transcript}",
        NON_MUSIC_CONTEXT_MARKERS,
    )
    return round(
        max(
            0.0,
            min(
                1.0,
                title_hits * 0.42
                + description_hits * 0.14
                + channel_hits * 0.2
                + transcript_hits * 0.12
                - non_music_hits * 0.18,
            ),
        ),
        4,
    )


def _resolve_manual_report_context(payload: ManualReportSuggestionRequest) -> dict[str, object]:
    raw_content_class = (
        payload.content_class.value
        if hasattr(payload.content_class, "value")
        else str(payload.content_class)
    ).strip().lower()
    normalized_title = _normalize_text(payload.title_snapshot)
    normalized_description = _normalize_text(payload.description_snapshot)
    normalized_transcript = _normalize_text(payload.transcript_excerpt)
    normalized_channel_name = _normalize_text(payload.channel_name)
    normalized_channel_context = _normalize_text(payload.channel_context)
    music_likelihood = _estimate_music_likelihood(
        title=normalized_title,
        description=normalized_description,
        transcript=normalized_transcript,
        channel_name=normalized_channel_name,
        channel_context=normalized_channel_context,
    )
    lower_combined = " ".join(
        part.lower()
        for part in (
            normalized_title,
            normalized_description,
            normalized_transcript,
            normalized_channel_name,
            normalized_channel_context,
        )
        if part
    )
    non_music_hits = _count_phrase_hits(lower_combined, NON_MUSIC_CONTEXT_MARKERS)
    if raw_content_class in CLASS_LABELS and raw_content_class != "unknown":
        resolved_class = raw_content_class
    elif raw_content_class == "unknown":
        resolved_class = (
            "music"
            if music_likelihood >= 0.72
            and payload.content_class_confidence <= 0.35
            and non_music_hits == 0
            else "unknown"
        )
    else:
        resolved_class = "unknown"
    negative_biases = {
        str(bias).strip().lower()
        for bias in payload.bias_profile.negative_biases
    }
    positive_biases = {
        str(bias).strip().lower()
        for bias in payload.bias_profile.positive_biases
    }
    return {
        "resolved_class": resolved_class,
        "class_label": CLASS_LABELS.get(resolved_class, "mixed or unclear"),
        "music_likelihood": music_likelihood,
        "non_music_hits": non_music_hits,
        "transparent_context_class": resolved_class in TRANSPARENT_CONTEXT_CLASSES,
        "factual_context_class": resolved_class in FACTUAL_CONTEXT_CLASSES,
        "ambiguous_context_class": resolved_class in AMBIGUOUS_CONTEXT_CLASSES,
        "negative_biases": negative_biases,
        "positive_biases": positive_biases,
    }


def _channel_feedback_profile(channel_name: str) -> dict[str, object] | None:
    normalized_channel = _normalize_text(channel_name).lower()
    if not normalized_channel or normalized_channel == "unknown channel":
        return None
    summary = summarize_feedback_events(load_feedback_events()[-200:])
    profile = summary.get("channel_profiles", {}).get(normalized_channel)
    return profile if isinstance(profile, dict) else None


def _fallback_suggestion_issue(
    issue_type: str,
    *,
    suggested: bool,
    comment: str,
) -> ManualReportSuggestionIssue:
    return ManualReportSuggestionIssue(
        issue_type=issue_type,
        suggested=suggested,
        comment=comment if suggested else "",
    )


def _normalize_comment_text(comment: str) -> str:
    normalized = _normalize_text(comment)
    if not normalized:
        return normalized
    normalized = normalized[0].upper() + normalized[1:]
    if normalized[-1] not in ".!?":
        normalized = f"{normalized}."
    return normalized


def _build_heuristic_issue_comment(
    *,
    issue_type: str,
    original_comment: str,
    workflow_mode: ManualReportWorkflowMode,
    title_snapshot: str,
) -> str:
    normalized_original = _normalize_comment_text(original_comment)
    lower_original = normalized_original.lower()
    title_lower = _normalize_text(title_snapshot).lower()
    original_tokens = set(re.findall(r"[a-z0-9']+", lower_original.replace("ai-generated", "ai generated")))
    has_ai_signal = bool(
        {"ai", "generated", "automated", "synthetic"} & original_tokens
    )
    has_resource_signal = any(
        marker in lower_original
        for marker in ("resource", "resources", "unnecessary", "waste")
    )
    has_fear_cue = _contains_any(title_lower, CLICKBAIT_MARKERS) or any(
        marker in lower_original
        for marker in ("fear", "danger", "warning", "curiosity", "clickbait")
    )

    if workflow_mode == ManualReportWorkflowMode.VERIFY_TRANSPARENT:
        templates = {
            "thumbnail": "Thumbnail appears consistent with the scenario suggested by the title and visible context.",
            "title": "Title appears consistent with the thumbnail and does not seem to overstate what the video shows.",
            "description": "Description appears to reinforce the same understanding created by the thumbnail and title.",
            "transcript": "Available transcript context appears to support the expectations created by the thumbnail and title.",
            "channel": "Available context suggests a transparent, non-clickbait presentation style for this channel.",
            "other": "Overall packaging appears transparent rather than clickbait-driven.",
        }
        return templates.get(issue_type, normalized_original)

    templates = {
        "thumbnail": "Thumbnail image may not accurately represent the scenario or subject suggested by the title, which could mislead users about what the video actually shows.",
        "title": "Title may not accurately represent the content implied by the thumbnail and available context, which could mislead users about the video's actual focus.",
        "description": "Description does not clearly reinforce the same understanding created by the thumbnail and title, which may contribute to a misleading impression.",
        "transcript": "Available transcript context does not clearly support the expectations created by the thumbnail and title, which may indicate misleading packaging.",
        "channel": (
            "Channel appears to show a broader pattern of misleading or clickbait-driven packaging across its videos."
            if not has_ai_signal
            else "Channel appears to show a broader pattern of automated or AI-generated clickbait packaging that may systematically mislead users."
        ),
        "other": (
            "Overall packaging appears to rely on clickbait or fear-based curiosity cues rather than clearly representing the actual content."
            if not has_ai_signal
            else "Overall packaging appears to rely on automated or AI-generated clickbait framing rather than clearly representing the actual content."
        ),
    }

    comment = templates.get(issue_type, normalized_original)
    if issue_type == "other" and has_resource_signal:
        comment = (
            f"{comment} This may also generate unnecessary clicks or watch starts without setting clear expectations."
            if comment.endswith(".")
            else f"{comment} This may also generate unnecessary clicks or watch starts without setting clear expectations."
        )
    elif issue_type in {"thumbnail", "title"} and has_fear_cue:
        comment = (
            f"{comment} The current packaging also leans on heightened curiosity or warning cues that may amplify the mismatch."
            if comment.endswith(".")
            else f"{comment} The current packaging also leans on heightened curiosity or warning cues that may amplify the mismatch."
        )
    return comment


def _fallback_report_opening_line(
    workflow_mode: ManualReportWorkflowMode,
    requested_outcome: ManualReportRequestedOutcome,
) -> str:
    if workflow_mode == ManualReportWorkflowMode.VERIFY_TRANSPARENT:
        return "Transparency verification: the visible packaging appears broadly consistent and non-clickbait."
    if requested_outcome == ManualReportRequestedOutcome.REMOVE:
        return "Requested action: Please remove this content because its presentation appears materially misleading."
    return "Requested action: Please moderate this content so the presentation becomes consistent and non-misleading."


def _build_heuristic_optimization_response(
    payload: ManualReportOptimizationRequest,
) -> ManualReportOptimizationResponse:
    normalized_issues = [
        ManualReportIssue(
            issue_type=issue.issue_type,
            comment=_build_heuristic_issue_comment(
                issue_type=issue.issue_type,
                original_comment=issue.comment,
                workflow_mode=payload.workflow_mode,
                title_snapshot=payload.title_snapshot,
            ),
        )
        for issue in payload.issues
    ]
    lines = [
        _fallback_report_opening_line(payload.workflow_mode, payload.requested_outcome),
        f'Video: "{payload.title_snapshot}"',
        f"Channel: {payload.channel_name}",
        "",
        (
            "Transparency notes:"
            if payload.workflow_mode == ManualReportWorkflowMode.VERIFY_TRANSPARENT
            else "Requested review for potentially misleading presentation in these areas:"
        ),
        *[
            f"- {_issue_label(issue.issue_type)}: {issue.comment}"
            for issue in normalized_issues
        ],
    ]
    return ManualReportOptimizationResponse(
        issues=normalized_issues,
        optimization_model=HEURISTIC_OPTIMIZATION_MODEL,
        report_text="\n".join(lines).strip(),
        selected_tags=payload.selected_tags,
    )


def _build_heuristic_suggestion_response(
    payload: ManualReportSuggestionRequest,
) -> ManualReportSuggestionResponse:
    title = _normalize_text(payload.title_snapshot)
    description = _normalize_text(payload.description_snapshot)
    transcript = _normalize_text(payload.transcript_excerpt)
    channel_context = _normalize_text(payload.channel_context)
    channel_name = _normalize_text(payload.channel_name)
    explanation = _normalize_text(payload.explanation_summary)
    reasons_text = " ".join(payload.reasons)
    transcript_available = payload.transcript_available
    if transcript_available is None:
        transcript_available = bool(transcript)
    channel_profile = _channel_feedback_profile(channel_name)
    prior_report_count = int(channel_profile.get("report_count", 0)) if channel_profile else 0
    prior_remove_count = int(channel_profile.get("remove_request_count", 0)) if channel_profile else 0
    prior_moderate_count = int(channel_profile.get("moderate_request_count", 0)) if channel_profile else 0
    review_context = _resolve_manual_report_context(payload)
    resolved_class = str(review_context["resolved_class"])
    likely_music_content = resolved_class == "music"
    transparent_context_class = bool(review_context["transparent_context_class"])
    factual_context_class = bool(review_context["factual_context_class"])
    ambiguous_context_class = bool(review_context["ambiguous_context_class"])
    negative_biases = set(review_context["negative_biases"])
    lower_context = " ".join(
        part.lower()
        for part in (title, description, transcript, channel_context, explanation, reasons_text, channel_name)
        if part
    )
    text_alignment_ratio = _token_overlap_ratio(
        title,
        " ".join(part for part in (description, transcript) if part),
    )
    channel_clickbait_hits = _count_phrase_hits((channel_context or "").lower(), CLICKBAIT_MARKERS)
    has_clickbait_title = _contains_any(title.lower(), CLICKBAIT_MARKERS)
    has_alignment_warning = _contains_any(lower_context, ALIGNMENT_MARKERS)
    has_channel_pattern = _contains_any(lower_context, CHANNEL_PATTERN_MARKERS) or channel_clickbait_hits >= 2
    has_positive_alignment = _contains_any(lower_context, POSITIVE_ALIGNMENT_MARKERS)
    weak_text_alignment = bool(description or transcript) and text_alignment_ratio < (
        0.12 if transparent_context_class else 0.22
    )
    has_recent_channel_context = bool(channel_context)
    sampled_titles = _sampled_channel_titles(channel_context)
    channel_pattern_comment = _channel_pattern_comment(
        sampled_titles=sampled_titles,
        prior_report_count=prior_report_count,
        prior_moderate_count=prior_moderate_count,
        prior_remove_count=prior_remove_count,
    )
    channel_report_context_comment = _channel_report_context_comment(
        sampled_titles=sampled_titles,
        has_recent_channel_context=has_recent_channel_context,
    )
    packaging_cues = _collect_packaging_cues(
        title=title,
        description=description,
        explanation=explanation,
        reasons_text=reasons_text,
    )
    cue_summary = _format_series(packaging_cues[:3])
    quoted_title_signals = _quoted_title_signal_summary(title)
    title_cue_phrase = cue_summary or "the title's current warning or curiosity framing"
    supporting_reference = _supporting_text_reference(description, transcript)
    description_excerpt = _excerpt_text(description) if description else ""
    transcript_excerpt = _excerpt_text(transcript) if transcript else ""

    if payload.workflow_mode == ManualReportWorkflowMode.VERIFY_TRANSPARENT:
        transparent_signal = has_positive_alignment or (
            not has_clickbait_title
            and not has_alignment_warning
            and text_alignment_ratio >= (0.12 if transparent_context_class else 0.18)
            and not {"sensational-overweighting", "channel-lock-in-risk"}.intersection(negative_biases)
        )
        transparent_other_comment = (
            "This appears to be music content, so non-literal artwork alone should not be treated as misleading; the overall packaging should instead be reviewed for honest artist, track, or release framing."
            if likely_music_content
            else "This appears to be art content, so non-literal artwork alone should not be treated as misleading; the overall packaging should instead be reviewed for honest artwork or exhibition framing."
            if resolved_class == "art"
            else "This appears to be gaming content, so non-literal scene selection alone should not be treated as misleading; the overall packaging should instead be reviewed for honest gameplay or release framing."
            if resolved_class == "gaming"
            else "Overall packaging does not currently show a strong clickbait signal from the available surface context, but the evidence should still be reviewed holistically."
        )
        issues = [
            _fallback_suggestion_issue(
                "thumbnail",
                suggested=True,
                comment=(
                    "This appears to be music content, and the thumbnail currently looks broadly consistent as artist, track, or release packaging rather than deceptive clickbait."
                    if transparent_signal and likely_music_content
                    else "This appears to be art content, and the thumbnail currently looks broadly consistent as artwork or exhibition packaging rather than deceptive clickbait."
                    if transparent_signal and resolved_class == "art"
                    else "This appears to be gaming content, and the thumbnail currently looks broadly consistent as gameplay or release framing rather than deceptive clickbait."
                    if transparent_signal and resolved_class == "gaming"
                    else (
                        "Thumbnail appears broadly consistent with the title and visible context."
                        if transparent_signal
                        else "Thumbnail does not currently show a strong mismatch signal relative to the title, but the visual packaging should still be reviewed alongside the rest of the context."
                    )
                ),
            ),
            _fallback_suggestion_issue(
                "title",
                suggested=True,
                comment=(
                    "This appears to be music content, and the title currently reads like normal artist or track labeling rather than deceptive overstatement."
                    if transparent_signal and likely_music_content
                    else "This appears to be art content, and the title currently reads like normal artwork or exhibition labeling rather than deceptive overstatement."
                    if transparent_signal and resolved_class == "art"
                    else "This appears to be gaming content, and the title currently reads like ordinary gameplay or release framing rather than deceptive overstatement."
                    if transparent_signal and resolved_class == "gaming"
                    else (
                        "Title appears consistent with the visible packaging and does not appear to overstate the likely content."
                        if transparent_signal
                        else "Title does not currently show a clear overstatement signal relative to the visible packaging, but it should still be reviewed against the full watch-page context."
                    )
                ),
            ),
            _fallback_suggestion_issue(
                "description",
                suggested=True,
                comment=(
                    "Description appears to support the same understanding created by the title and thumbnail."
                    if description and transparent_signal
                    else "Description evidence is limited on the current surface, so this field should be reviewed cautiously against the watch page before making a stronger transparency claim."
                ),
            ),
            _fallback_suggestion_issue(
                "transcript",
                suggested=bool(transcript),
                comment=(
                    "Transcript excerpt appears to support the same understanding created by the visible packaging."
                    if transcript and transparent_signal
                    else ""
                ),
            ),
            _fallback_suggestion_issue(
                "channel",
                suggested=bool(channel_pattern_comment or (transparent_signal and has_recent_channel_context)),
                comment=(
                    channel_pattern_comment
                    if channel_pattern_comment
                    else (
                    "Recent public titles sampled from this channel appear broadly consistent rather than clickbait-driven, which supports a tentative transparency assessment."
                    if transparent_signal and has_recent_channel_context and not has_channel_pattern
                    else (
                        "Recent public titles sampled from this channel do not by themselves prove a misleading pattern, so the channel can only be treated as tentatively transparent from the available evidence."
                        if has_recent_channel_context
                        else "Channel-wide context is still limited for this video, so any transparency conclusion about the channel should remain cautious rather than definitive."
                    )
                    )
                ),
            ),
            _fallback_suggestion_issue(
                "other",
                suggested=True,
                comment=(
                    "Overall packaging appears transparent rather than clickbait-driven."
                    if transparent_signal
                    else transparent_other_comment
                ),
            ),
        ]
        return ManualReportSuggestionResponse(
            issues=issues,
            suggested_outcome=ManualReportRequestedOutcome.MODERATE,
            suggested_outcome_reason=_build_outcome_reason(
                payload,
                resolved_class=resolved_class,
                suggested_outcome=ManualReportRequestedOutcome.MODERATE,
                has_channel_pattern=has_channel_pattern,
                weak_text_alignment=weak_text_alignment,
                title_clickbait=has_clickbait_title,
            ),
            suggested_tags=_build_tag_suggestions(
                payload,
                resolved_class=resolved_class,
                base_confidence=payload.content_class_confidence,
            ),
            suggestion_model=HEURISTIC_SUGGESTION_MODEL,
        )

    thumbnail_suggested = payload.thumbnail_ref is not None
    title_suggested = True
    description_suggested = bool(description)
    transcript_suggested = bool(transcript) and (
        weak_text_alignment
        or has_alignment_warning
        or (
            ambiguous_context_class
            and bool(negative_biases.intersection({"genre-confusion", "uncertainty-miscalibration"}))
        )
    )
    channel_comment = (
        channel_pattern_comment
        or (
            channel_report_context_comment
            if payload.workflow_mode == ManualReportWorkflowMode.REPORT
            else ""
        )
        or (
            "Recent channel context suggests recurring satire or parody framing, so the current upload should be reviewed for whether that framing is explicit enough."
            if ambiguous_context_class and has_recent_channel_context
            else ""
        )
    )
    channel_suggested = bool(channel_comment)
    other_suggested = ambiguous_context_class or not (
        transparent_context_class and not has_alignment_warning and not has_channel_pattern
    )

    issues = [
        _fallback_suggestion_issue(
            "thumbnail",
            suggested=thumbnail_suggested,
            comment=(
                f"The thumbnail should be reviewed against the title phrases {quoted_title_signals}; {supporting_reference} does not clearly confirm that same high-drama premise, so the visual packaging may be selling a stronger scenario than the text evidence supports."
                if quoted_title_signals
                else f"The thumbnail should be reviewed against {supporting_reference} because the visual packaging appears more dramatic than the exposed text clearly confirms."
            ),
        ),
        _fallback_suggestion_issue(
            "title",
            suggested=title_suggested,
            comment=(
                f"The title phrases {quoted_title_signals} create a stronger claim than {supporting_reference} clearly substantiates, so the title risks overselling what the video actually contains."
                if quoted_title_signals
                else f"The title currently makes a stronger claim than {supporting_reference} clearly substantiates."
            ),
        ),
        _fallback_suggestion_issue(
            "description",
            suggested=description_suggested,
            comment=(
                f'Description currently says "{description_excerpt}", but that still does not clearly substantiate the stronger promise carried by the title phrases {quoted_title_signals}.'
                if description_suggested and description_excerpt
                else ""
            ),
        ),
        _fallback_suggestion_issue(
            "transcript",
            suggested=transcript_suggested,
            comment=(
                f'Transcript excerpt says "{transcript_excerpt}", but that still does not clearly substantiate the stronger promise carried by the title phrases {quoted_title_signals}.'
                if transcript_suggested and transcript_excerpt
                else ""
            ),
        ),
        _fallback_suggestion_issue(
            "channel",
            suggested=channel_suggested,
            comment=channel_comment,
        ),
        _fallback_suggestion_issue(
            "other",
            suggested=other_suggested,
            comment=(
                f"Taken together, the packaging leans on cues such as {title_cue_phrase}, while {supporting_reference} still does not clearly confirm the same premise; that overall pattern looks closer to clickbait than transparent framing."
                if other_suggested and title_cue_phrase and factual_context_class
                else f"Taken together, the packaging appears more manipulative than clarifying when the thumbnail, title, and {supporting_reference} are compared side by side."
            ),
        ),
    ]
    severity_points = 0
    severity_points += 2 if has_alignment_warning else 0
    severity_points += 1 if weak_text_alignment else 0
    severity_points += 1 if has_clickbait_title else 0
    severity_points += 2 if channel_suggested else 0
    severity_points += 1 if other_suggested else 0
    suggested_outcome = (
        ManualReportRequestedOutcome.REMOVE
        if severity_points >= 5 and (channel_suggested or "synthetic" in lower_context or "spam" in lower_context)
        else ManualReportRequestedOutcome.MODERATE
    )
    return ManualReportSuggestionResponse(
        issues=issues,
        suggested_outcome=suggested_outcome,
        suggested_outcome_reason=_build_outcome_reason(
            payload,
            resolved_class=resolved_class,
            suggested_outcome=suggested_outcome,
            has_channel_pattern=has_channel_pattern,
            weak_text_alignment=weak_text_alignment,
            title_clickbait=has_clickbait_title,
        ),
        suggested_tags=_build_tag_suggestions(
            payload,
            resolved_class=resolved_class,
            base_confidence=payload.content_class_confidence,
        ),
        suggestion_model=HEURISTIC_SUGGESTION_MODEL,
    )


def _call_gemini_json(contents: list[dict[str, object]], schema: dict[str, object]) -> dict[str, object]:
    response = httpx.post(
        f"{settings.gemini_api_base}/models/{settings.gemini_model}:generateContent",
        headers=_gemini_headers(),
        json={
            "contents": contents,
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        },
        timeout=60.0,
    )
    response.raise_for_status()
    response_payload = response.json()
    candidate_text = (
        response_payload.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    if not candidate_text:
        raise ValueError("Gemini returned an empty manual-report response.")
    parsed = json.loads(candidate_text)
    if not isinstance(parsed, dict):
        raise ValueError("Gemini returned a non-object manual-report response.")
    return parsed


def _suggestion_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "issues": {
                "type": "array",
                "minItems": 6,
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "properties": {
                        "issue_type": {
                            "type": "string",
                            "enum": list(ISSUE_TYPES),
                        },
                        "suggested": {"type": "boolean"},
                        "comment": {
                            "type": "string",
                            "description": "A concise draft comment for this issue type.",
                        },
                    },
                    "required": ["issue_type", "suggested", "comment"],
                    "additionalProperties": False,
                },
            },
            "suggested_outcome": {
                "type": "string",
                "enum": ["moderate", "remove"],
            },
            "suggested_outcome_reason": {
                "type": "string",
                "description": "A concise explanation for why this outcome was chosen.",
            },
            "suggested_tags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tag": {
                            "type": "string",
                            "enum": [tag.value for tag in MANUAL_REVIEW_TAG_ORDER],
                        },
                        "selected": {"type": "boolean"},
                        "confidence": {"type": "number"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["tag", "selected", "confidence", "rationale"],
                    "additionalProperties": False,
                },
            },
            "suggestion_model": {
                "type": "string",
                "description": "Return the model name used for drafting.",
            },
        },
        "required": [
            "issues",
            "suggested_outcome",
            "suggested_outcome_reason",
            "suggested_tags",
            "suggestion_model",
        ],
        "additionalProperties": False,
    }


def _optimization_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "issue_type": {
                            "type": "string",
                            "enum": list(ISSUE_TYPES),
                        },
                        "comment": {
                            "type": "string",
                            "description": "A concise, factual, platform-safe formulation.",
                        },
                    },
                    "required": ["issue_type", "comment"],
                    "additionalProperties": False,
                },
            },
            "optimization_model": {
                "type": "string",
                "description": "Return the model name used for optimization.",
            },
            "report_text": {
                "type": "string",
                "description": "A short combined report text for manual submission.",
            },
        },
        "required": ["issues", "optimization_model", "report_text"],
        "additionalProperties": False,
    }


def _build_suggestion_prompt(payload: ManualReportSuggestionRequest) -> str:
    description_line = payload.description_snapshot or "Not available."
    transcript_line = payload.transcript_excerpt or "Not available."
    review_context = _resolve_manual_report_context(payload)
    resolved_class = str(review_context["resolved_class"])
    class_label = str(review_context["class_label"])
    music_likelihood = float(review_context["music_likelihood"])
    negative_biases = sorted(str(value) for value in review_context["negative_biases"])
    positive_biases = sorted(str(value) for value in review_context["positive_biases"])
    class_context_line = (
        f"{class_label} ({payload.content_class_confidence:.0%} confidence)"
        if resolved_class != "unknown" or payload.content_class_confidence > 0.0
        else "mixed or unclear"
    )
    positive_bias_line = ", ".join(positive_biases) if positive_biases else "None recorded."
    negative_bias_line = ", ".join(negative_biases) if negative_biases else "None recorded."
    transcript_availability = (
        "Available"
        if payload.transcript_available is True
        else "Unavailable"
        if payload.transcript_available is False
        else "Unknown"
    )
    target_line = payload.target_url or "Not available."
    channel_url_line = payload.channel_url or "Not available."
    channel_context_line = payload.channel_context or "Not available."
    channel_profile = _channel_feedback_profile(_normalize_text(payload.channel_name))
    channel_history_line = (
        f"{int(channel_profile.get('report_count', 0))} prior TruthLens report(s), "
        f"{int(channel_profile.get('moderate_request_count', 0))} moderation request(s), "
        f"{int(channel_profile.get('remove_request_count', 0))} removal request(s)."
        if channel_profile
        else "No prior TruthLens channel reports recorded."
    )
    explanation_summary = payload.explanation_summary or "Not available."
    reasons = "\n".join(f"- {reason}" for reason in payload.reasons) or "- Not available."
    issue_lines = "\n".join(f"- {_issue_label(issue_type)}" for issue_type in ISSUE_TYPES)
    if payload.workflow_mode == ManualReportWorkflowMode.VERIFY_TRANSPARENT:
        return (
            "You are drafting initial positive verification comments for a browser tool named TruthLens. "
            "Reason about whether the thumbnail image, title, description snippet, and transcript excerpt appear mutually consistent, honest, and representative of the likely content. "
            "Return JSON only.\n\n"
            f"Video title: {payload.title_snapshot}\n"
            f"Channel: {payload.channel_name}\n"
            f"Channel URL: {channel_url_line}\n"
            f"Target URL: {target_line}\n"
            f"Channel context: {channel_context_line}\n"
            f"TruthLens channel history: {channel_history_line}\n"
            f"TruthLens content class: {class_context_line}\n"
            f"TruthLens music-likelihood fallback: {music_likelihood:.2f}\n"
            f"TruthLens positive biases: {positive_bias_line}\n"
            f"TruthLens negative biases: {negative_bias_line}\n"
            f"Description snippet: {description_line}\n"
            f"Transcript availability: {transcript_availability}\n"
            f"Transcript excerpt: {transcript_line}\n"
            f"TruthLens explanation summary: {explanation_summary}\n"
            "TruthLens reasons:\n"
            f"{reasons}\n\n"
            "Issue types to evaluate in this exact order:\n"
            f"{issue_lines}\n\n"
            "Rules:\n"
            "- Return all six issue types.\n"
            "- Return all six issue types, but you may set suggested to false when a field genuinely lacks evidence to comment on.\n"
            "- When suggested is false, leave comment empty.\n"
            "- Prefer leaving Transcript unsuggested instead of inventing a generic missing-transcript comment.\n"
            "- Prefer leaving Channel unsuggested unless the supplied channel context or TruthLens channel history shows a real recurring pattern.\n"
            "- Start from the supplied TruthLens content class and bias profile unless the visible evidence strongly contradicts it.\n"
            "- If it appears to be music content, do not treat non-literal artwork, performance imagery, lyric phrasing, or missing captions as automatic mismatch.\n"
            "- If it appears to be art content, do not treat stylized or non-literal artwork as automatic mismatch.\n"
            "- If it appears to be gaming content, do not treat selective scene choice or hype framing as automatic mismatch unless it overstates the actual gameplay or release context.\n"
            "- For music content, focus on whether the artist, track, or release framing appears honest rather than literal scene-to-title alignment.\n"
            "- Prefer reasoning about alignment and transparency across thumbnail, title, description, and transcript.\n"
            "- For Thumbnail, mention at least one concrete visible cue from the image itself before judging alignment.\n"
            "- For Title, quote or paraphrase the exact claim, warning cue, or overstatement that matters.\n"
            "- For Description and Transcript, quote the concrete detail that reinforces or undermines the packaging when possible.\n"
            "- If Transcript availability is marked Unavailable, leave Transcript unsuggested instead of writing a generic absence note.\n"
            "- For Channel, use the supplied recent channel-title context and TruthLens channel history before making any broader claim.\n"
            "- For Other, use it for the overall combined packaging assessment.\n"
            f"- suggested_tags must cover this UI tag set: {', '.join(tag.value for tag in MANUAL_REVIEW_TAG_ORDER)}.\n"
            "- Select exactly one positive tag as selected=true for this verification workflow, and leave Clickbait unselected unless the visible evidence strongly contradicts the workflow.\n"
            "- suggested_outcome_reason must explain why this should be treated as transparent and which positive tag fits best.\n"
            "- Avoid vague visual comments such as 'text-heavy'.\n"
            "- Never use generic boilerplate like 'may not accurately represent', 'available text context', 'should still be reviewed', or 'could not be sampled deeply enough'.\n"
            "- Prefer comments like:\n"
            "  * Thumbnail appears broadly consistent with the title and visible context.\n"
            "  * Title appears consistent with the thumbnail and does not overstate the apparent content.\n"
            "  * Packaging appears transparent rather than clickbait-driven.\n"
            "- suggested_outcome must be 'moderate' for this workflow.\n"
        )
    return (
        "You are drafting initial report comments for a browser tool named TruthLens. "
        "Your job is to reason about whether the thumbnail image, title, description snippet, and transcript excerpt are mutually consistent and honestly representative of the content. "
        "Prioritize misleading framing, clickbait, or mismatch reasoning over superficial style observations. "
        "Return JSON only.\n\n"
        f"Video title: {payload.title_snapshot}\n"
        f"Channel: {payload.channel_name}\n"
        f"Channel URL: {channel_url_line}\n"
        f"Target URL: {target_line}\n"
        f"Channel context: {channel_context_line}\n"
        f"TruthLens channel history: {channel_history_line}\n"
        f"TruthLens content class: {class_context_line}\n"
        f"TruthLens music-likelihood fallback: {music_likelihood:.2f}\n"
        f"TruthLens positive biases: {positive_bias_line}\n"
        f"TruthLens negative biases: {negative_bias_line}\n"
        f"Description snippet: {description_line}\n"
        f"Transcript availability: {transcript_availability}\n"
        f"Transcript excerpt: {transcript_line}\n"
        f"TruthLens explanation summary: {explanation_summary}\n"
        "TruthLens reasons:\n"
        f"{reasons}\n\n"
        "Primary reasoning goal:\n"
        "- Compare the thumbnail image to the title.\n"
        "- Compare the title to the description snippet and transcript excerpt.\n"
        "- Identify whether the packaging overpromises, misstates, or visually suggests something different from the text context.\n\n"
        "Issue types to evaluate in this exact order:\n"
        f"{issue_lines}\n\n"
        "Rules:\n"
        "- Return all six issue types.\n"
        "- Return all six issue types, but you may set suggested to false when a field genuinely lacks evidence to comment on.\n"
        "- When suggested is false, leave comment empty.\n"
        "- This workflow was explicitly opened as a report flow, so default to suspected clickbait or misleading packaging review.\n"
        "- Prefer leaving Transcript unsuggested instead of inventing a generic missing-transcript comment.\n"
        "- Prefer leaving Channel unsuggested unless the supplied channel context or TruthLens channel history shows a real recurring pattern.\n"
        "- Start from the supplied TruthLens content class and bias profile unless the visible evidence strongly contradicts it.\n"
        "- Use class context only to calibrate the mismatch analysis; do not start issue comments with phrases like 'This appears to be art content' or replace the clickbait review with a benign-category explanation.\n"
        "- If it appears to be music, art, gaming, or satire content, use that only to explain why a specific mismatch is weaker or stronger, not as the primary draft framing.\n"
        "- Keep comments neutral, specific, and useful for a human reviewer.\n"
        "- For Thumbnail, describe the main visible subject, setting, or on-image text before explaining the mismatch.\n"
        "- For Title, quote or paraphrase the exact wording that looks overstated, sensational, forbidden, or curiosity-driven.\n"
        "- For Description, quote the relevant detail it does or does not provide, rather than saying evidence is limited in generic terms.\n"
        "- For Transcript, quote the relevant spoken detail when it exists; if it does not exist, leave Transcript unsuggested.\n"
        "- For Channel, use the supplied channel titles and TruthLens channel history to say either that this looks like a repeated pattern or that this appears to be the first recorded concern for the channel.\n"
        "- For Other, use it for the overall clickbait or manipulative packaging assessment after considering all other fields together.\n"
        f"- suggested_tags must cover this UI tag set: {', '.join(tag.value for tag in MANUAL_REVIEW_TAG_ORDER)}.\n"
        "- Select Clickbait as selected=true by default for this report workflow unless the visible evidence strongly contradicts the workflow.\n"
        "- suggested_outcome_reason must explain why the packaging should be reviewed as clickbait and why the chosen outcome fits.\n"
        "- Do not invent channel-wide abuse or AI-generated-content claims unless the supplied evidence strongly supports it.\n"
        "- Do not use generic comments such as 'Thumbnail appears text-heavy' or comments about colors/fonts unless those traits are the actual misleading mechanism.\n"
        "- Never use generic boilerplate like 'may not accurately represent', 'available text context', 'should still be reviewed', or 'could not be sampled deeply enough'.\n"
        "- Prefer comments that explain inconsistency or clickbait clearly, for example:\n"
        "  * Thumbnail shows a dark tunnel entrance and hazard-style framing, while the title promises a forbidden-location reveal that the supporting text does not clearly verify.\n"
        "  * Title uses warning wording like 'STAY OUT', but the available description does not substantiate that dramatic framing.\n"
        "  * The packaging combines secrecy and warning cues to provoke clicks before the actual scenario is made clear.\n"
        "- suggested_outcome should be 'moderate' by default. Use 'remove' only for strong signs of systematic deceptive spam or synthetic clickbait abuse.\n"
    )


def _build_optimization_prompt(payload: ManualReportOptimizationRequest) -> str:
    issue_lines = "\n".join(
        f"- {_issue_label(issue.issue_type)}: {issue.comment}" for issue in payload.issues
    )
    transcript_line = payload.transcript_excerpt or "Not available."
    target_line = payload.target_url or "Not available."
    if payload.workflow_mode == ManualReportWorkflowMode.VERIFY_TRANSPARENT:
        return (
            "Rewrite the user's positive verification notes so they are concise, factual, specific, "
            "and suitable for recording transparent, non-clickbait packaging feedback. "
            "Do not invent evidence. Preserve the meaning of each issue. Return JSON only.\n\n"
            f"Video title: {payload.title_snapshot}\n"
            f"Channel: {payload.channel_name}\n"
            f"Target URL: {target_line}\n"
            f"Transcript excerpt: {transcript_line}\n"
            "Issues:\n"
            f"{issue_lines}\n\n"
            "Rules:\n"
            "- Keep the same issue order.\n"
            "- Each issue comment must stay short, neutral, and factual.\n"
            "- Emphasize consistency, transparency, and non-clickbait framing.\n"
            "- report_text must be a clean multi-line verification summary with one short opening line and one bullet-style line per issue.\n"
            "- The opening line should clearly state that the content appears transparently presented.\n"
            "- Do not mention Gemini, optimization, or JSON in the report text."
        )
    return (
        "Rewrite the user's manual video-report notes so they are concise, factual, specific, "
        "and suitable for a platform abuse, spam, clickbait, or misinformation report. "
        "Do not invent evidence. Preserve the meaning of each issue. "
        "Return JSON only.\n\n"
        f"Video title: {payload.title_snapshot}\n"
        f"Channel: {payload.channel_name}\n"
        f"Target URL: {target_line}\n"
        f"Transcript excerpt: {transcript_line}\n"
        f"Requested outcome: {_outcome_label(payload.requested_outcome)}\n"
        "Issues:\n"
        f"{issue_lines}\n\n"
        "Rules:\n"
        "- Keep the same issue order.\n"
        "- Each issue comment must stay short, neutral, and factual.\n"
        "- Avoid legal claims, certainty language, or emotional wording unless the user already used it.\n"
        "- report_text must be a clean multi-line manual report with one short opening line and one "
        "bullet-style line per issue, using plain text.\n"
        f"- The opening line should clearly state that the request is for {_outcome_label(payload.requested_outcome)}.\n"
        "- Do not mention Gemini, optimization, or JSON in the report text."
    )


def _normalize_suggestion_response(
    payload: dict[str, object],
    *,
    request_payload: ManualReportSuggestionRequest | None = None,
    fallback: ManualReportSuggestionResponse | None = None,
) -> ManualReportSuggestionResponse:
    raw_issues = payload.get("issues", [])
    if not isinstance(raw_issues, list):
        raise ValueError("Gemini suggestion response did not contain an issues array.")

    issues_by_type: dict[str, ManualReportSuggestionIssue] = {}
    for entry in raw_issues:
        issue = ManualReportSuggestionIssue.model_validate(entry)
        issues_by_type[issue.issue_type] = issue

    fallback_by_type = {
        issue.issue_type: issue for issue in (fallback.issues if fallback else [])
    }
    normalized_issues = []
    for issue_type in ISSUE_TYPES:
        raw_issue = issues_by_type.get(issue_type)
        fallback_issue = fallback_by_type.get(issue_type)
        suggested = raw_issue.suggested if raw_issue is not None else (
            fallback_issue.suggested if fallback_issue is not None else False
        )
        comment = _normalize_text(raw_issue.comment if raw_issue else "")
        if suggested and not comment and fallback_issue is not None and fallback_issue.suggested:
            comment = fallback_issue.comment
        if (
            request_payload is not None
            and request_payload.workflow_mode == ManualReportWorkflowMode.REPORT
            and fallback_issue is not None
        ):
            if issue_type == "channel" and not suggested and fallback_issue.suggested and fallback_issue.comment:
                suggested = True
                comment = fallback_issue.comment
            elif suggested and comment and _uses_benign_class_preface(comment) and fallback_issue.comment:
                comment = fallback_issue.comment
        normalized_issues.append(
            ManualReportSuggestionIssue(
                issue_type=issue_type,
                suggested=suggested,
                comment=comment if suggested else "",
            )
        )
    suggested_outcome = payload.get("suggested_outcome", "moderate")
    raw_outcome_reason = _normalize_text(str(payload.get("suggested_outcome_reason") or ""))
    fallback_reason = fallback.suggested_outcome_reason if fallback else ""
    normalized_outcome_reason = raw_outcome_reason or fallback_reason
    raw_tag_entries = payload.get("suggested_tags", [])
    tags_by_name: dict[str, ManualReviewTagSelection] = {}
    if isinstance(raw_tag_entries, list):
        for entry in raw_tag_entries:
            try:
                selection = ManualReviewTagSelection.model_validate(entry)
            except ValidationError:
                continue
            tags_by_name[selection.tag.value] = selection
    fallback_tags_by_name = {
        selection.tag.value: selection for selection in (fallback.suggested_tags if fallback else [])
    }
    normalized_tags: list[ManualReviewTagSelection] = []
    for tag in MANUAL_REVIEW_TAG_ORDER:
        selection = tags_by_name.get(tag.value) or fallback_tags_by_name.get(tag.value)
        if selection is None:
            normalized_tags.append(_selected_tag(tag, selected=False, confidence=0.0))
            continue
        normalized_tags.append(selection)
    suggestion_model = str(payload.get("suggestion_model") or settings.gemini_model)
    return ManualReportSuggestionResponse(
        issues=normalized_issues,
        suggested_outcome=ManualReportRequestedOutcome(suggested_outcome),
        suggested_outcome_reason=normalized_outcome_reason,
        suggested_tags=normalized_tags,
        suggestion_model=suggestion_model,
    )


def suggest_manual_report(
    payload: ManualReportSuggestionRequest,
) -> ManualReportSuggestionResponse:
    heuristic_fallback = _build_heuristic_suggestion_response(payload)
    if not gemini_available():
        return heuristic_fallback
    prompt = _build_suggestion_prompt(payload)
    thumbnail_attempts = [payload.thumbnail_ref] if payload.thumbnail_ref else []
    thumbnail_attempts.append(None)

    for thumbnail_ref in thumbnail_attempts:
        try:
            response_payload = _call_gemini_json(
                _build_gemini_contents(
                    prompt,
                    thumbnail_ref=thumbnail_ref,
                ),
                _suggestion_schema(),
            )
            normalized = _normalize_suggestion_response(
                response_payload,
                request_payload=payload,
                fallback=heuristic_fallback,
            )
            return ManualReportSuggestionResponse(
                issues=normalized.issues,
                suggested_outcome=normalized.suggested_outcome,
                suggested_outcome_reason=normalized.suggested_outcome_reason,
                suggested_tags=normalized.suggested_tags,
                suggestion_model=settings.gemini_model,
            )
        except (httpx.HTTPError, ValidationError, ValueError, json.JSONDecodeError):
            continue

    return heuristic_fallback


def optimize_manual_report(
    payload: ManualReportOptimizationRequest,
) -> ManualReportOptimizationResponse:
    if not gemini_available():
        raise RuntimeError("Gemini optimization is not configured.")

    try:
        response_payload = _call_gemini_json(
            _build_gemini_contents(_build_optimization_prompt(payload)),
            _optimization_schema(),
        )
        optimized = ManualReportOptimizationResponse.model_validate(response_payload)
        normalized_issues = []
        for issue in optimized.issues:
            normalized_issues.append(
                ManualReportIssue(
                    issue_type=issue.issue_type,
                    comment=issue.comment,
                )
            )
        return ManualReportOptimizationResponse(
            issues=normalized_issues,
            optimization_model=settings.gemini_model,
            report_text=optimized.report_text,
            selected_tags=payload.selected_tags,
        )
    except (httpx.HTTPError, ValidationError, ValueError, json.JSONDecodeError):
        return _build_heuristic_optimization_response(payload)
