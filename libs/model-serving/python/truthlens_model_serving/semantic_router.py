from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from truthlens_shared_schemas.contracts import ScoreItemRequest


FULL_MULTIMODAL_CAPTURE = "full_multimodal_capture"

PRESERVED_LEARNING_EVIDENCE = [
    "title",
    "description_snapshot",
    "transcript_excerpt",
    "thumbnail_ref",
    "thumbnail_features",
    "channel",
    "metadata",
    "score",
    "content_class",
    "route",
    "class_confidence",
    "adversarial_guard",
    "feedback",
    "verify_report_outcome",
    "user_correction",
    "later_adjudication_state",
]

CREATIVE_TITLE_MARKERS = (
    "official audio",
    "music video",
    "lyric video",
    "lyrics",
    "visualizer",
    "visualiser",
    "instrumental",
    "rap instrumental",
    "type beat",
    "free for profit beat",
    "freestyle beat",
    "rap beat",
    "rap beats",
    "hip hop beat",
    "hiphop beat",
    "boom bap",
    "lofi",
    "lo-fi",
    "hip hop mix",
    "hiphop mix",
    "beat tape",
    "album",
    "single",
    "remix",
    "prod.",
    "produced by",
)

ART_TITLE_MARKERS = (
    "art",
    "artwork",
    "visualizer",
    "visualiser",
    "animation",
    "animated",
    "concept art",
    "illustration",
    "gallery",
    "sketchbook",
)

INFORMATIONAL_MARKERS = (
    "tutorial",
    "how to",
    "how-to",
    "guide",
    "explainer",
    "explained",
    "educational",
    "lecture",
    "lesson",
    "course",
    "documentary",
    "investigation",
    "deep dive",
)

HIGH_RISK_FACTUAL_MARKERS = (
    "breaking",
    "news",
    "politics",
    "election",
    "government",
    "officials",
    "health",
    "vaccine",
    "disease",
    "outbreak",
    "crisis",
    "war",
    "finance",
    "stock",
    "market crash",
    "recession",
    "bank",
    "tax",
    "court",
    "police",
    "confirmed",
    "proof",
)

FAKE_OFFICIAL_MARKERS = (
    "official government",
    "official warning",
    "official report",
    "official leak",
    "official proof",
    "government confirms",
    "government confirmed",
    "police confirmed",
    "court confirms",
    "court confirmed",
    "who confirms",
    "cdc confirms",
    "leaked official",
    "classified official",
)

SCAM_DESCRIPTION_MARKERS = (
    "claim now",
    "free prize",
    "free reward",
    "giveaway",
    "guaranteed profit",
    "double your money",
    "crypto giveaway",
    "whatsapp",
    "telegram",
    "cashapp",
    "limited slots",
    "click the link below to claim",
)


@dataclass(frozen=True, slots=True)
class SemanticRouteDecision:
    content_class: str
    class_confidence: float
    runtime_route: str
    learning_capture_plan: str
    adversarial_guard: str
    mismatch_pressure: str
    required_runtime_evidence: list[str]
    preserved_learning_evidence: list[str]
    route_reasons: list[str]

    def to_payload(self) -> dict[str, Any]:
        return {
            "content_class": self.content_class,
            "class_confidence": round(self.class_confidence, 4),
            "runtime_route": self.runtime_route,
            "learning_capture_plan": self.learning_capture_plan,
            "adversarial_guard": self.adversarial_guard,
            "mismatch_pressure": self.mismatch_pressure,
            "required_runtime_evidence": list(self.required_runtime_evidence),
            "preserved_learning_evidence": list(self.preserved_learning_evidence),
            "route_reasons": list(self.route_reasons),
        }


class AdaptiveSemanticEvidenceRouter:
    def route(
        self,
        payload: ScoreItemRequest,
        feature_summary: dict[str, Any],
    ) -> SemanticRouteDecision:
        title = payload.title.lower()
        description = (payload.description_snapshot or "").lower()
        transcript = (payload.transcript_excerpt or "").lower()
        channel_name = payload.channel.channel_name.lower()
        combined = " ".join(part for part in (title, description, transcript, channel_name) if part)
        content_class = str(feature_summary.get("content_class", "unknown"))
        class_confidence = _bounded_float(feature_summary.get("content_class_confidence", 0.0))

        creative_title_hits = _count_hits(title, CREATIVE_TITLE_MARKERS) + _count_hits(
            title,
            ART_TITLE_MARKERS,
        )
        creative_context = (
            content_class in {"music", "art"} and class_confidence >= 0.55
        ) or creative_title_hits > 0
        informational_context = _contains_any(combined, INFORMATIONAL_MARKERS)
        factual_context = (
            content_class == "news"
            or _contains_any(combined, HIGH_RISK_FACTUAL_MARKERS)
            or _contains_any(combined, FAKE_OFFICIAL_MARKERS)
        )

        reasons: list[str] = []
        guard_triggers: list[str] = []
        if creative_context:
            reasons.append("Title or taxonomy indicates creative music/art context.")
        if _contains_any(combined, FAKE_OFFICIAL_MARKERS):
            guard_triggers.append("Creative-like context is mixed with fake-official factual framing.")
        elif creative_context and _contains_any(combined, HIGH_RISK_FACTUAL_MARKERS):
            suspicious_official_audio_only = (
                "official audio" in title or "official video" in title or "music video" in title
            ) and not _contains_any(combined, ("government", "health", "finance", "election", "crisis"))
            if not suspicious_official_audio_only:
                guard_triggers.append("Creative-like context is mixed with factual claim markers.")
        if _negative_channel_history(payload):
            guard_triggers.append("Negative channel history requires escalation.")
        if _contains_any(description, SCAM_DESCRIPTION_MARKERS):
            guard_triggers.append("Description contains scam or promo-farming patterns.")
        if _sensational_thumbnail(feature_summary):
            guard_triggers.append("Lightweight thumbnail features look sensational despite creative framing.")
        if class_confidence < 0.45 or content_class == "unknown":
            guard_triggers.append("Content class confidence is too low for a light route.")

        if guard_triggers:
            reasons.extend(guard_triggers)

        if creative_context and guard_triggers:
            return _decision(
                content_class=content_class,
                class_confidence=class_confidence,
                runtime_route="ambiguous_escalated",
                adversarial_guard="triggered",
                mismatch_pressure="normal",
                required_runtime_evidence=[
                    "title",
                    "description",
                    "thumbnail",
                    "channel_history",
                    "light_spam_check",
                ],
                route_reasons=reasons + ["Creative route not trusted as sufficient."],
            )

        if factual_context and not creative_context:
            return _decision(
                content_class=content_class,
                class_confidence=class_confidence,
                runtime_route="high_risk_factual",
                adversarial_guard="clean",
                mismatch_pressure="elevated",
                required_runtime_evidence=[
                    "title",
                    "description",
                    "thumbnail",
                    "channel_history",
                    "light_spam_check",
                    "factual_claim_guard",
                ],
                route_reasons=reasons
                + ["Factual or high-risk claim context requires strong consistency analysis."],
            )

        if creative_context and class_confidence >= 0.62:
            return _decision(
                content_class=content_class,
                class_confidence=class_confidence,
                runtime_route="minimal_creative",
                adversarial_guard="clean",
                mismatch_pressure="reduced",
                required_runtime_evidence=["title", "channel_sanity", "light_spam_check"],
                route_reasons=reasons
                + [
                    "No suspicious factual claim detected.",
                    "No negative channel-history escalation detected.",
                ],
            )

        if informational_context or content_class in {"commentary", "documentary"}:
            return _decision(
                content_class=content_class,
                class_confidence=class_confidence,
                runtime_route="informational_consistency",
                adversarial_guard="clean",
                mismatch_pressure="normal",
                required_runtime_evidence=[
                    "title",
                    "description",
                    "thumbnail",
                    "channel_context",
                    "light_spam_check",
                ],
                route_reasons=reasons + ["Informational content expects cross-signal consistency."],
            )

        return _decision(
            content_class=content_class,
            class_confidence=class_confidence,
            runtime_route="ambiguous_escalated",
            adversarial_guard="triggered",
            mismatch_pressure="normal",
            required_runtime_evidence=[
                "title",
                "description",
                "thumbnail",
                "channel_history",
                "light_spam_check",
            ],
            route_reasons=reasons or ["Available signals are insufficient for a light route."],
        )


def route_adjusted_mismatch(
    raw_mismatch: float,
    content_class: str,
    semantic_route: dict[str, Any] | None,
) -> tuple[float, str]:
    route = semantic_route or {}
    pressure = str(route.get("mismatch_pressure", "normal"))
    runtime_route = str(route.get("runtime_route", "ambiguous_escalated"))
    guard = str(route.get("adversarial_guard", "triggered"))
    if pressure == "reduced" and runtime_route == "minimal_creative" and guard == "clean":
        return round(_clip(raw_mismatch * 0.28), 4), "semantic-route-minimal-creative-reduces-mismatch-pressure"
    if pressure == "elevated":
        return round(_clip(raw_mismatch * 1.16), 4), "semantic-route-high-risk-amplifies-mismatch-pressure"
    if runtime_route == "informational_consistency":
        multiplier = 1.14 if content_class == "documentary" else 1.04
        return round(_clip(raw_mismatch * multiplier), 4), "semantic-route-informational-keeps-consistency-pressure"
    return round(_clip(raw_mismatch), 4), "semantic-route-normal-mismatch-pressure"


def _decision(
    *,
    content_class: str,
    class_confidence: float,
    runtime_route: str,
    adversarial_guard: str,
    mismatch_pressure: str,
    required_runtime_evidence: list[str],
    route_reasons: list[str],
) -> SemanticRouteDecision:
    return SemanticRouteDecision(
        content_class=content_class if content_class else "unknown",
        class_confidence=class_confidence,
        runtime_route=runtime_route,
        learning_capture_plan=FULL_MULTIMODAL_CAPTURE,
        adversarial_guard=adversarial_guard,
        mismatch_pressure=mismatch_pressure,
        required_runtime_evidence=required_runtime_evidence,
        preserved_learning_evidence=list(PRESERVED_LEARNING_EVIDENCE),
        route_reasons=list(dict.fromkeys(route_reasons)),
    )


def _bounded_float(value: Any) -> float:
    try:
        return _clip(float(value))
    except (TypeError, ValueError):
        return 0.0


def _clip(value: float) -> float:
    return max(0.0, min(value, 1.0))


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def _count_hits(text: str, phrases: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(1 for phrase in phrases if phrase in lowered)


def _negative_channel_history(payload: ScoreItemRequest) -> bool:
    history = payload.channel.channel_history_features
    reported_item_count = float(history.get("reported_item_count", payload.channel.prior_flags))
    channel_risk_mean = float(history.get("channel_risk_mean", 0.0))
    repeat_template_rate = float(history.get("repeat_template_rate", 0.0))
    trust_score = float(history.get("trust_score", 5.0))
    return (
        payload.channel.prior_flags >= 2
        or reported_item_count >= 2.0
        or channel_risk_mean >= 0.55
        or repeat_template_rate >= 0.45
        or trust_score <= 4.0
    )


def _sensational_thumbnail(feature_summary: dict[str, Any]) -> bool:
    shock = _bounded_float(feature_summary.get("thumbnail_shock_indicator", 0.0))
    text_density = _bounded_float(feature_summary.get("thumbnail_text_density", 0.0))
    return shock >= 0.85 or (shock >= 0.72 and text_density >= 0.3)
