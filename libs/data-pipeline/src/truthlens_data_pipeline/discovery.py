from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from truthlens_data_pipeline.manifests import DiscoveryRunManifest, SourceManifestRecord, build_source_manifest
from truthlens_data_pipeline.paths import ensure_dir, make_run_id, repo_root, slugify, write_json, write_jsonl


class DiscoveredItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    platform: str = "youtube"
    source_url: str = Field(min_length=1)
    channel_name: str = Field(min_length=1)
    channel_prior_flags: int = Field(default=0, ge=0)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    tags: list[str]
    hashtags: list[str]
    transcript_excerpt: str = Field(min_length=1)
    upload_time: str = Field(min_length=1)
    duration_seconds: int = Field(ge=0)
    view_count: int = Field(ge=0)
    like_count: int = Field(ge=0)
    template_cluster: str = Field(min_length=1)
    thumbnail_signal: dict[str, float]
    risk_seed: float = Field(ge=0.0, le=1.0)
    mismatch_seed: float = Field(ge=0.0, le=1.0)
    duplicate_of: str | None = None


def _channels() -> list[dict[str, Any]]:
    return [
        {"name": "OpenSky Alerts", "prior_flags": 4, "risk_profile": "elevated"},
        {"name": "Calm Science Daily", "prior_flags": 0, "risk_profile": "balanced"},
        {"name": "Signal Watch Europe", "prior_flags": 3, "risk_profile": "elevated"},
        {"name": "Verified Space Desk", "prior_flags": 0, "risk_profile": "balanced"},
        {"name": "Now Stream Briefing", "prior_flags": 2, "risk_profile": "elevated"},
        {"name": "Context First Media", "prior_flags": 0, "risk_profile": "balanced"},
    ]


def _risk_templates() -> list[dict[str, Any]]:
    return [
        {
            "title": "Breaking aliens confirmed over Europe",
            "description": "A breathless roundup built around vague eyewitness clips and unverifiable claims.",
            "tags": ["breaking", "aliens", "ufo"],
            "hashtags": ["#breaking", "#aliens"],
            "transcript": "Witnesses say everything changed overnight and officials are hiding the truth.",
            "template_cluster": "aliens-confirmed",
            "thumbnail_signal": {
                "saturation": 0.91,
                "contrast": 0.87,
                "text_density": 0.79,
                "face_emphasis": 0.88,
                "shock_indicator": 0.93,
            },
            "risk_seed": 0.94,
            "mismatch_seed": 0.82,
        },
        {
            "title": "Secret lab leak exposed in new footage",
            "description": "Dramatic framing with thin sourcing and strong certainty language.",
            "tags": ["secret", "exposed", "lab"],
            "hashtags": ["#secret", "#exposed"],
            "transcript": "The footage proves what they did not want you to see according to unnamed sources.",
            "template_cluster": "lab-leak-exposed",
            "thumbnail_signal": {
                "saturation": 0.84,
                "contrast": 0.8,
                "text_density": 0.72,
                "face_emphasis": 0.74,
                "shock_indicator": 0.85,
            },
            "risk_seed": 0.88,
            "mismatch_seed": 0.71,
        },
        {
            "title": "What they do not want you to know about tonight",
            "description": "Vague framing designed to create urgency without a specific factual claim.",
            "tags": ["urgent", "secret", "tonight"],
            "hashtags": ["#urgent", "#truth"],
            "transcript": "Something huge is coming and the public is not ready according to the host.",
            "template_cluster": "hidden-truth-tonight",
            "thumbnail_signal": {
                "saturation": 0.83,
                "contrast": 0.78,
                "text_density": 0.7,
                "face_emphasis": 0.66,
                "shock_indicator": 0.76,
            },
            "risk_seed": 0.81,
            "mismatch_seed": 0.64,
        },
    ]


def _neutral_templates() -> list[dict[str, Any]]:
    return [
        {
            "title": "Weekly launch schedule and mission recap",
            "description": "A source-cited review of recent launches, delays, and mission updates.",
            "tags": ["launch", "mission", "recap"],
            "hashtags": ["#space", "#recap"],
            "transcript": "This segment summarizes confirmed launch windows and official mission updates.",
            "template_cluster": "mission-recap",
            "thumbnail_signal": {
                "saturation": 0.36,
                "contrast": 0.42,
                "text_density": 0.18,
                "face_emphasis": 0.14,
                "shock_indicator": 0.09,
            },
            "risk_seed": 0.18,
            "mismatch_seed": 0.09,
        },
        {
            "title": "How telescope calibration improved this month",
            "description": "A calm explainer focused on instrument changes and measured outcomes.",
            "tags": ["telescope", "calibration", "science"],
            "hashtags": ["#science", "#calibration"],
            "transcript": "The calibration update reduced noise and improved the quality of long exposure captures.",
            "template_cluster": "calibration-update",
            "thumbnail_signal": {
                "saturation": 0.31,
                "contrast": 0.33,
                "text_density": 0.14,
                "face_emphasis": 0.08,
                "shock_indicator": 0.04,
            },
            "risk_seed": 0.11,
            "mismatch_seed": 0.05,
        },
        {
            "title": "Satellite weather imaging workflow explained",
            "description": "A practical walkthrough with clear method notes and stable sourcing.",
            "tags": ["satellite", "weather", "workflow"],
            "hashtags": ["#weather", "#satellite"],
            "transcript": "This tutorial explains how analysts align sensor frames before publishing weather composites.",
            "template_cluster": "weather-workflow",
            "thumbnail_signal": {
                "saturation": 0.41,
                "contrast": 0.39,
                "text_density": 0.2,
                "face_emphasis": 0.06,
                "shock_indicator": 0.06,
            },
            "risk_seed": 0.16,
            "mismatch_seed": 0.07,
        },
    ]


def build_discovery_run(run_id: str | None = None) -> tuple[str, DiscoveryRunManifest, list[DiscoveredItem]]:
    resolved_run_id = run_id or make_run_id("discovery")
    records: list[SourceManifestRecord] = []
    items: list[DiscoveredItem] = []
    risk_templates = _risk_templates()
    neutral_templates = _neutral_templates()

    for channel_index, channel in enumerate(_channels()):
        source_slug = slugify(channel["name"])
        records.append(
            SourceManifestRecord(
                source_id=source_slug,
                source_type="channel-feed",
                platform="youtube",
                collected_at=resolved_run_id,
                access_method="synthetic-bootstrap",
                expected_fields=[
                    "title",
                    "description",
                    "thumbnail_signal",
                    "channel_name",
                    "upload_time",
                    "view_count",
                ],
                parsing_risk="low",
                status="pending",
            )
        )
        templates = (
            risk_templates + neutral_templates[:1]
            if channel["risk_profile"] == "elevated"
            else neutral_templates + risk_templates[:1]
        )
        for template_index, template in enumerate(templates):
            item_slug = f"{source_slug}-{template_index + 1}"
            items.append(
                DiscoveredItem(
                    item_id=item_slug,
                    source_id=source_slug,
                    source_type="channel-feed",
                    source_url=f"https://youtube.com/watch?v={item_slug}",
                    channel_name=channel["name"],
                    channel_prior_flags=channel["prior_flags"],
                    title=template["title"],
                    description=template["description"],
                    tags=template["tags"],
                    hashtags=template["hashtags"],
                    transcript_excerpt=template["transcript"],
                    upload_time=f"2026-03-{channel_index + template_index + 1:02d}T12:00:00Z",
                    duration_seconds=420 + template_index * 45,
                    view_count=12500 + channel_index * 2300 + template_index * 800,
                    like_count=1200 + channel_index * 180 + template_index * 70,
                    template_cluster=template["template_cluster"],
                    thumbnail_signal=template["thumbnail_signal"],
                    risk_seed=template["risk_seed"],
                    mismatch_seed=template["mismatch_seed"],
                )
            )

    duplicate_originals = [items[0], items[5]]
    for duplicate_index, original in enumerate(duplicate_originals, start=1):
        items.append(
            original.model_copy(
                update={
                    "item_id": f"{original.item_id}-dup-{duplicate_index}",
                    "source_url": original.source_url,
                    "duplicate_of": original.item_id,
                    "upload_time": f"2026-03-{20 + duplicate_index:02d}T12:00:00Z",
                }
            )
        )

    return resolved_run_id, build_source_manifest(resolved_run_id, records), items


def persist_discovery_run(run_id: str | None = None) -> tuple[str, DiscoveryRunManifest, list[DiscoveredItem]]:
    resolved_run_id, manifest, items = build_discovery_run(run_id)
    root = repo_root()
    discovery_dir = ensure_dir(root / "datasets" / "raw" / "discovery_runs")
    source_manifest_dir = ensure_dir(root / "datasets" / "raw" / "source_manifests")
    write_json(source_manifest_dir / f"{resolved_run_id}.json", manifest.model_dump())
    write_jsonl(discovery_dir / f"{resolved_run_id}.jsonl", [item.model_dump() for item in items])
    return resolved_run_id, manifest, items
