from __future__ import annotations

from typing import Any, Iterable

from .text import count_sensational_tokens, normalize_text, uppercase_ratio

CONTENT_CLASSES = (
    "news",
    "commentary",
    "documentary",
    "music",
    "art",
    "satire",
    "gaming",
    "promo",
    "unknown",
)

BENIGN_CONTENT_CLASSES = {"music", "art", "satire", "gaming"}
FACTUAL_CONTENT_CLASSES = {"news", "commentary", "documentary", "promo", "unknown"}

_CLASS_KEYWORDS: dict[str, tuple[str, ...]] = {
    "news": (
        "breaking",
        "news",
        "alert",
        "live",
        "bulletin",
        "officials",
        "report",
        "update",
        "exclusive",
    ),
    "commentary": (
        "commentary",
        "analysis",
        "opinion",
        "reaction",
        "breakdown",
        "review",
        "comparison",
        "first impressions",
        "first impression",
        "hands on",
        "hands-on",
        "versus",
        "vs",
        "guide",
        "tutorial",
        "how to",
        "thoughts",
        "debate",
        "editorial",
    ),
    "documentary": (
        "documentary",
        "explainer",
        "history",
        "source-cited",
        "archive",
        "investigation",
        "deep dive",
        "episode",
        "workflow explained",
        "lecture",
        "lesson",
        "course",
        "seminar",
        "case study",
    ),
    "music": (
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
        "chorus",
        "verse",
        "refrain",
        "track",
        "album",
        "single",
        "vevo",
        "records",
        "topic",
    ),
    "art": (
        "art",
        "artwork",
        "gallery",
        "painting",
        "illustration",
        "concept art",
        "sketchbook",
        "visual art",
        "studio session",
        "exhibition",
    ),
    "satire": (
        "satire",
        "parody",
        "spoof",
        "sketch",
        "meme",
        "joke",
        "comedy",
        "comedian",
        "funny",
    ),
    "gaming": (
        "gameplay",
        "gaming",
        "walkthrough",
        "let's play",
        "boss fight",
        "speedrun",
        "patch notes",
        "build guide",
        "livestream",
        "stream highlights",
    ),
    "promo": (
        "trailer",
        "teaser",
        "promo",
        "preorder",
        "limited time",
        "sale",
        "discount",
        "launch trailer",
        "sponsored",
        "announcement",
        "official trailer",
        "official teaser",
        "reveal trailer",
    ),
}

_TUTORIAL_CONTEXT_MARKERS = (
    "tutorial",
    "how to",
    "how-to",
    "guide",
    "walkthrough",
    "repair",
    "fix",
    "build guide",
    "step by step",
    "step-by-step",
)

_SPORTS_CONTEXT_MARKERS = (
    "highlights",
    "match",
    "goal",
    "goals",
    "transfer",
    "injury",
    "postgame",
    "post-game",
    "tactics",
    "fixture",
    "league",
    "cup",
    "championship",
)

_REVIEW_CONTEXT_MARKERS = (
    "review",
    "reviews",
    "comparison",
    "compare",
    "first impressions",
    "first impression",
    "hands on",
    "hands-on",
    "benchmark",
    "vs",
    "versus",
)

_EDUCATION_CONTEXT_MARKERS = (
    "lesson",
    "lecture",
    "course",
    "seminar",
    "class",
    "study guide",
    "workshop",
    "explainer",
    "teaches",
    "teaching",
)

_COMMERCIAL_CONTEXT_MARKERS = (
    "sponsored",
    "sponsor",
    "product demo",
    "demo",
    "sale",
    "discount",
    "preorder",
    "pre-order",
    "shop",
    "store",
    "advertisement",
    "ad",
)

_OFFICIAL_TRAILER_CONTEXT_MARKERS = (
    "official trailer",
    "official teaser",
    "launch trailer",
    "reveal trailer",
    "teaser trailer",
)

_FALSE_URGENCY_MARKERS = (
    "before it gets deleted",
    "before it's deleted",
    "watch before it gets deleted",
    "watch before it's deleted",
    "act now",
    "right now",
    "hurry",
    "no one is talking about this",
    "nobody is talking about this",
    "everyone is wrong",
    "world is in shock",
)

_SHOCK_BAIT_MARKERS = (
    "omg",
    "warning",
    "banned",
    "exposed",
    "you won't believe",
    "you wont believe",
    "shocking",
    "must see",
)

_FALSE_OFFICIAL_MARKERS = (
    "official",
    "leaked",
    "confirmed",
    "breaking",
    "exclusive",
)

_FALSE_MYSTERY_MARKERS = (
    "is this the end",
    "is he done",
    "did it really happen",
    "what happened next",
    "could this be it",
)

_EXAGGERATED_OUTCOME_MARKERS = (
    "changes everything",
    "change everything",
    "works 100%",
    "100% works",
    "makes you rich",
    "destroys your body",
    "proof is finally here",
    "beviset er endelig her",
)

_FAKE_GIVEAWAY_MARKERS = (
    "giveaway",
    "win now",
    "free reward",
    "unlock this",
    "claim now",
    "free prize",
)

_AUTHORITY_CHANNEL_MARKERS = (
    "official",
    "news",
    "network",
    "media",
    "breaking",
    "updates",
    "authority",
)

_CONTEXT_MANIPULATION_MARKERS = (
    "full context",
    "they don't want you to know",
    "taken out of context",
    "quote",
    "clip proves",
)

_BSEO_PARAMETER_KEYS = (
    "thumbnail",
    "title",
    "description",
    "transcript",
    "channel",
    "other",
)

_CLASS_GUARDRAILS = {
    "news": "factual-context-amplifies-mismatch",
    "commentary": "argument-context-balances-mismatch",
    "documentary": "evidence-context-amplifies-mismatch",
    "music": "music-context-dampens-crossmodal-rigidity",
    "art": "art-context-preserves-stylistic-divergence",
    "satire": "satire-context-prefers-review",
    "gaming": "gaming-context-lowers-literal-rigidity",
    "promo": "promo-context-amplifies-packaging-scrutiny",
    "unknown": "unknown-context-uses-balanced-guardrail",
}

_CLASS_MISMATCH_MULTIPLIER = {
    "news": 1.16,
    "commentary": 1.04,
    "documentary": 1.14,
    "music": 0.34,
    "art": 0.46,
    "satire": 0.6,
    "gaming": 0.82,
    "promo": 1.1,
    "unknown": 1.0,
}


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(value, high))


def _combine_text_parts(parts: Iterable[str | None]) -> str:
    normalized_parts = [normalize_text(part) for part in parts if isinstance(part, str) and part.strip()]
    return " ".join(normalized_parts)


def _count_keyword_hits(text: str, phrases: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(1 for phrase in phrases if phrase in lowered)


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def _append_parameter_frame(
    parameter_frames: dict[str, list[str]],
    parameter: str,
    label: str,
) -> None:
    if parameter not in parameter_frames:
        return
    if label not in parameter_frames[parameter]:
        parameter_frames[parameter].append(label)


def infer_content_taxonomy(
    *,
    title: str,
    description: str | None = None,
    transcript: str | None = None,
    channel_name: str | None = None,
    tags: Iterable[str] | None = None,
    hashtags: Iterable[str] | None = None,
    template_cluster: str | None = None,
    channel_history_features: dict[str, float] | None = None,
) -> dict[str, Any]:
    channel_history_features = channel_history_features or {}
    tags_text = " ".join(tag for tag in (tags or []) if tag)
    hashtags_text = " ".join(tag for tag in (hashtags or []) if tag)
    combined = _combine_text_parts(
        [title, description, transcript, channel_name, template_cluster, tags_text, hashtags_text]
    )
    lowered = combined.lower()

    scores = {content_class: 0.05 for content_class in CONTENT_CLASSES}
    for content_class, keywords in _CLASS_KEYWORDS.items():
        scores[content_class] += _count_keyword_hits(lowered, keywords) * 0.22
    for content_class in CONTENT_CLASSES:
        hint_key = f"taxonomy_hint_{content_class}"
        hint_value = _clip(float(channel_history_features.get(hint_key, 0.0)))
        if hint_value <= 0.0:
            continue
        scores[content_class] += hint_value * (0.42 if content_class != "unknown" else 0.18)

    sensational_hits = count_sensational_tokens(title)
    uppercase = uppercase_ratio(title)
    history_music = float(channel_history_features.get("music_likelihood", 0.0))

    if "records" in lowered or "vevo" in lowered or history_music > 0.3:
        scores["music"] += 0.28 + history_music * 0.35
    if "documentary" in lowered or "explainer" in lowered or "source-cited" in lowered:
        scores["documentary"] += 0.25
    if "breaking" in lowered or "officials" in lowered or "alert" in lowered:
        scores["news"] += 0.24
    if "analysis" in lowered or "reaction" in lowered or "opinion" in lowered:
        scores["commentary"] += 0.22
    if _contains_any(lowered, _TUTORIAL_CONTEXT_MARKERS):
        scores["commentary"] += 0.18
        scores["documentary"] += 0.1
    if _contains_any(lowered, _REVIEW_CONTEXT_MARKERS):
        scores["commentary"] += 0.2
    if _contains_any(lowered, _EDUCATION_CONTEXT_MARKERS):
        scores["documentary"] += 0.18
        scores["commentary"] += 0.08
    if _contains_any(lowered, _SPORTS_CONTEXT_MARKERS):
        scores["commentary"] += 0.14
        scores["news"] += 0.1
    if "art" in lowered or "gallery" in lowered or "illustration" in lowered:
        scores["art"] += 0.24
    if "satire" in lowered or "parody" in lowered or "spoof" in lowered:
        scores["satire"] += 0.26
    if "gameplay" in lowered or "walkthrough" in lowered or "speedrun" in lowered:
        scores["gaming"] += 0.24
    if "trailer" in lowered or "teaser" in lowered or "promo" in lowered:
        scores["promo"] += 0.24

    scores["news"] += sensational_hits * 0.05 + uppercase * 0.06
    scores["promo"] += sensational_hits * 0.04
    scores["satire"] += 0.05 if "meme" in lowered else 0.0
    scores["unknown"] += 0.08 if sensational_hits == 0 and not transcript else 0.0
    scores["unknown"] += 0.12 if max(scores.values()) <= 0.18 else 0.0
    scores["music"] = max(scores["music"], history_music * 0.9)

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    content_class, top_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0.0
    total = sum(scores.values())
    confidence = _clip((top_score / max(total, 0.01)) + (top_score - second_score) * 0.45, 0.18, 0.98)
    if top_score <= 0.16 or confidence <= 0.28:
        content_class = "unknown"
        confidence = _clip(confidence + 0.08, 0.2, 0.75)

    music_likelihood = _clip(scores["music"] / max(total, 0.01), 0.0, 1.0)
    return {
        "content_class": content_class,
        "content_class_confidence": round(confidence, 4),
        "content_class_scores": {name: round(value, 4) for name, value in ordered},
        "music_likelihood": round(music_likelihood, 4),
        "guardrail": _CLASS_GUARDRAILS[content_class],
    }


def infer_bseo_prior_frames(
    *,
    title: str,
    description: str | None = None,
    transcript: str | None = None,
    channel_name: str | None = None,
    content_class: str,
    content_class_confidence: float,
    metrics: dict[str, float],
    prior_flags: int,
    channel_risk_mean: float,
    repeat_template_rate: float,
    channel_history_features: dict[str, float] | None = None,
    thumbnail_text_density: float = 0.0,
    thumbnail_shock_indicator: float = 0.0,
) -> dict[str, Any]:
    resolved_class = content_class if content_class in CONTENT_CLASSES else "unknown"
    history_features = channel_history_features or {}
    combined = _combine_text_parts([title, description, transcript, channel_name]).lower()
    parameter_frames: dict[str, list[str]] = {key: [] for key in _BSEO_PARAMETER_KEYS}
    positive_contexts: list[str] = []
    negative_contexts: list[str] = []

    transparent_count = float(history_features.get("transparent_count", 0.0))
    reported_item_count = float(history_features.get("reported_item_count", 0.0))
    trust_score = float(history_features.get("trust_score", 5.0))

    def add_positive(parameter: str, label: str) -> None:
        if label not in positive_contexts:
            positive_contexts.append(label)
        _append_parameter_frame(parameter_frames, parameter, label)

    def add_negative(parameter: str, label: str) -> None:
        if label not in negative_contexts:
            negative_contexts.append(label)
        _append_parameter_frame(parameter_frames, parameter, label)

    tutorial_context = _contains_any(combined, _TUTORIAL_CONTEXT_MARKERS)
    sports_context = _contains_any(combined, _SPORTS_CONTEXT_MARKERS)
    review_context = _contains_any(combined, _REVIEW_CONTEXT_MARKERS)
    education_context = _contains_any(combined, _EDUCATION_CONTEXT_MARKERS)
    commercial_context = _contains_any(combined, _COMMERCIAL_CONTEXT_MARKERS) or resolved_class == "promo"
    official_trailer_context = _contains_any(combined, _OFFICIAL_TRAILER_CONTEXT_MARKERS)

    if resolved_class in {"music", "art"}:
        add_positive("thumbnail", "artwork-nonliteral-context")
        add_positive("title", "stylistic-title-context")
    if tutorial_context:
        add_positive("title", "tutorial-howto-context")
        add_positive("transcript", "solution-delivery-context")
    if sports_context:
        add_positive("thumbnail", "sports-intensity-context")
        add_positive("title", "sports-reaction-context")
    if review_context:
        add_positive("title", "review-comparison-context")
        add_positive("other", "judgment-format-context")
    if education_context:
        add_positive("title", "educational-delivery-context")
        add_positive("transcript", "topic-explanation-context")
    if official_trailer_context:
        add_positive("title", "official-teaser-context")
        add_positive("channel", "announced-release-context")
    if commercial_context:
        add_positive("description", "commercial-intent-context")
        add_positive("other", "marketing-by-itself-is-not-clickbait")
    if transparent_count >= 2 or (trust_score >= 7.5 and reported_item_count <= max(transparent_count, 1.0)):
        add_positive("channel", "transparent-verification-history")

    if metrics.get("crossmodal_rigidity", 0.0) >= 0.68:
        add_negative("thumbnail", "false-visual-promise")
    if (
        metrics.get("sensational_weight", 0.0) >= 0.5
        and metrics.get("crossmodal_rigidity", 0.0) >= 0.55
    ):
        add_negative("title", "false-title-promise")
    if _contains_any(combined, _SHOCK_BAIT_MARKERS) or (
        thumbnail_shock_indicator >= 0.72 and thumbnail_text_density >= 0.3
    ):
        add_negative("other", "shock-bait-packaging")
    if _contains_any(combined, _FALSE_URGENCY_MARKERS):
        add_negative("title", "false-urgency")
    if (
        _contains_any(combined, _FALSE_OFFICIAL_MARKERS)
        and (
            metrics.get("genre_confusion", 0.0) >= 0.5
            or metrics.get("crossmodal_rigidity", 0.0) >= 0.55
            or content_class_confidence < 0.6
        )
    ):
        add_negative("title", "false-official-claim")
    if (
        _contains_any(combined, _FALSE_MYSTERY_MARKERS)
        and metrics.get("sensational_weight", 0.0) >= 0.45
    ):
        add_negative("title", "false-mystery")
    if _contains_any(combined, _FAKE_GIVEAWAY_MARKERS):
        add_negative("other", "fake-giveaway")
    if (
        _contains_any(combined, _EXAGGERATED_OUTCOME_MARKERS)
        and metrics.get("sensational_weight", 0.0) >= 0.45
    ):
        add_negative("title", "exaggerated-outcome-claim")
    if description and (
        metrics.get("genre_confusion", 0.0) >= 0.58
        and metrics.get("crossmodal_rigidity", 0.0) >= 0.52
    ):
        add_negative("description", "description-conflict")
    if transcript and metrics.get("crossmodal_rigidity", 0.0) >= 0.62:
        add_negative("transcript", "transcript-non-delivery")
    if (
        transcript
        and _contains_any(combined, _CONTEXT_MANIPULATION_MARKERS)
        and metrics.get("crossmodal_rigidity", 0.0) >= 0.48
    ):
        add_negative("transcript", "context-manipulation")
    if repeat_template_rate >= 0.42 and channel_risk_mean >= 0.55:
        add_negative("channel", "repeat-deceptive-channel-pattern")
    if (
        prior_flags >= 3
        and _contains_any((channel_name or "").lower(), _AUTHORITY_CHANNEL_MARKERS)
        and channel_risk_mean >= 0.5
    ):
        add_negative("channel", "authority-imitation")
    if (
        repeat_template_rate >= 0.5
        and channel_risk_mean >= 0.55
        and metrics.get("sensational_weight", 0.0) >= 0.45
    ):
        add_negative("other", "ai-bait-pattern")

    return {
        "positive_contexts": positive_contexts,
        "negative_contexts": negative_contexts,
        "parameter_frames": parameter_frames,
    }


def class_adjusted_mismatch(raw_mismatch: float, content_class: str) -> tuple[float, str]:
    resolved_class = content_class if content_class in _CLASS_MISMATCH_MULTIPLIER else "unknown"
    adjusted = _clip(raw_mismatch * _CLASS_MISMATCH_MULTIPLIER[resolved_class], 0.0, 1.0)
    return round(adjusted, 4), _CLASS_GUARDRAILS[resolved_class]


def build_bias_primitives(
    *,
    title: str,
    description: str | None = None,
    transcript: str | None = None,
    channel_name: str | None = None,
    raw_transcript_mismatch: float,
    adjusted_transcript_mismatch: float,
    content_class: str,
    content_class_confidence: float,
    prior_flags: int,
    channel_risk_mean: float,
    repeat_template_rate: float,
    channel_history_features: dict[str, float] | None = None,
    uncertainty: float | None = None,
) -> dict[str, float]:
    resolved_class = content_class if content_class in CONTENT_CLASSES else "unknown"
    benign_class = resolved_class in BENIGN_CONTENT_CLASSES
    combined = _combine_text_parts([title, description, transcript, channel_name]).lower()
    history_features = channel_history_features or {}
    tutorial_context = _contains_any(combined, _TUTORIAL_CONTEXT_MARKERS)
    sports_context = _contains_any(combined, _SPORTS_CONTEXT_MARKERS)
    review_context = _contains_any(combined, _REVIEW_CONTEXT_MARKERS)
    education_context = _contains_any(combined, _EDUCATION_CONTEXT_MARKERS)
    commercial_context = _contains_any(combined, _COMMERCIAL_CONTEXT_MARKERS) or resolved_class == "promo"
    official_trailer_context = _contains_any(combined, _OFFICIAL_TRAILER_CONTEXT_MARKERS)
    context_allowance = 0.0
    if tutorial_context:
        context_allowance += 0.08
    if sports_context:
        context_allowance += 0.05
    if review_context:
        context_allowance += 0.06
    if education_context:
        context_allowance += 0.07
    if official_trailer_context:
        context_allowance += 0.05
    if commercial_context:
        context_allowance += 0.04
    transparent_count = float(history_features.get("transparent_count", 0.0))
    trust_score = float(history_features.get("trust_score", 5.0))
    sensational_weight = _clip(
        count_sensational_tokens(title) * 0.17
        + uppercase_ratio(title) * 0.22
        + (0.04 if resolved_class in {"news", "promo", "commentary"} else 0.0)
        - context_allowance * 0.45
    )
    crossmodal_rigidity = _clip(
        adjusted_transcript_mismatch + (0.08 if resolved_class in FACTUAL_CONTENT_CLASSES else -0.12)
        - context_allowance
    )
    channel_prior_dependency = _clip(
        min(prior_flags / 4.0, 1.0) * 0.45 + channel_risk_mean * 0.4 + repeat_template_rate * 0.15
        - (0.08 if transparent_count >= 2 else 0.0)
        - (0.06 if trust_score >= 7.5 else 0.0)
    )
    genre_confusion = _clip(
        (1.0 - content_class_confidence)
        + (0.12 if resolved_class == "unknown" else 0.0)
        - min(context_allowance * 0.35, 0.12)
    )
    expected_uncertainty = _clip(
        0.18
        + genre_confusion * 0.45
        + abs(raw_transcript_mismatch - adjusted_transcript_mismatch) * 0.2
        + (0.08 if benign_class else 0.0)
    )
    uncertainty_value = expected_uncertainty if uncertainty is None else float(uncertainty)
    uncertainty_calibration = _clip(abs(uncertainty_value - expected_uncertainty))
    return {
        "sensational_weight": round(sensational_weight, 4),
        "crossmodal_rigidity": round(crossmodal_rigidity, 4),
        "channel_prior_dependency": round(channel_prior_dependency, 4),
        "genre_confusion": round(genre_confusion, 4),
        "uncertainty_calibration": round(uncertainty_calibration, 4),
    }


def dominant_bias_name(metrics: dict[str, float]) -> str:
    if not metrics:
        return "balanced-context"
    return max(metrics.items(), key=lambda item: item[1])[0]


def build_bias_profile(
    *,
    metrics: dict[str, float],
    content_class: str,
    content_class_confidence: float,
    raw_transcript_mismatch: float,
    adjusted_transcript_mismatch: float,
    title: str = "",
    description: str | None = None,
    transcript: str | None = None,
    channel_name: str | None = None,
    prior_flags: int = 0,
    channel_risk_mean: float = 0.0,
    repeat_template_rate: float = 0.0,
    channel_history_features: dict[str, float] | None = None,
    thumbnail_text_density: float = 0.0,
    thumbnail_shock_indicator: float = 0.0,
    prior_frames: dict[str, Any] | None = None,
    uncertainty: float | None = None,
) -> dict[str, Any]:
    resolved_class = content_class if content_class in CONTENT_CLASSES else "unknown"
    frames = prior_frames or infer_bseo_prior_frames(
        title=title,
        description=description,
        transcript=transcript,
        channel_name=channel_name,
        content_class=resolved_class,
        content_class_confidence=content_class_confidence,
        metrics=metrics,
        prior_flags=prior_flags,
        channel_risk_mean=channel_risk_mean,
        repeat_template_rate=repeat_template_rate,
        channel_history_features=channel_history_features,
        thumbnail_text_density=thumbnail_text_density,
        thumbnail_shock_indicator=thumbnail_shock_indicator,
    )
    positive_biases = [str(value) for value in frames.get("positive_contexts", []) if value]
    negative_biases = [str(value) for value in frames.get("negative_contexts", []) if value]

    if resolved_class in {"music", "art"} and metrics.get("crossmodal_rigidity", 0.0) <= 0.45:
        positive_biases.append("stylistic-divergence-tolerance")
    if resolved_class == "satire" and (uncertainty or 0.0) >= 0.2:
        positive_biases.append("ambiguity-aware-caution")
    if metrics.get("uncertainty_calibration", 1.0) <= 0.15:
        positive_biases.append("calibrated-uncertainty")
    if resolved_class in FACTUAL_CONTENT_CLASSES and adjusted_transcript_mismatch >= raw_transcript_mismatch:
        positive_biases.append("factual-scrutiny")

    if metrics.get("sensational_weight", 0.0) >= 0.55:
        negative_biases.append("sensational-overweighting")
    if metrics.get("crossmodal_rigidity", 0.0) >= 0.72 and resolved_class in BENIGN_CONTENT_CLASSES:
        negative_biases.append("crossmodal-overreach")
    if metrics.get("channel_prior_dependency", 0.0) >= 0.62:
        negative_biases.append("channel-lock-in-risk")
    if metrics.get("genre_confusion", 0.0) >= 0.58:
        negative_biases.append("genre-confusion")
    if metrics.get("uncertainty_calibration", 0.0) >= 0.26:
        negative_biases.append("uncertainty-miscalibration")

    return {
        "metrics": metrics,
        "positive_biases": list(dict.fromkeys(positive_biases)),
        "negative_biases": list(dict.fromkeys(negative_biases)),
        "guardrail_applied": _CLASS_GUARDRAILS[resolved_class],
        "content_class_confidence": round(content_class_confidence, 4),
        "dominant_bias": dominant_bias_name(metrics),
    }
