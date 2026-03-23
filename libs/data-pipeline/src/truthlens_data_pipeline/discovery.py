from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from truthlens_data_pipeline.manifests import DiscoveryRunManifest, SourceManifestRecord, build_source_manifest
from truthlens_data_pipeline.paths import ensure_dir, make_run_id, repo_root, slugify, utc_now, write_json, write_jsonl


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


class PublicSourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    source_type: str = Field(default="channel-rss", min_length=1)
    platform: str = Field(default="youtube", min_length=1)
    source_url: str = Field(min_length=1)
    channel_name: str = Field(min_length=1)
    access_method: str = Field(default="public-rss", min_length=1)
    parsing_risk: str = Field(default="medium", min_length=1)
    channel_prior_flags: int = Field(default=0, ge=0)


FetchText = Callable[[str], str]
ATOM_NAMESPACE = {"atom": "http://www.w3.org/2005/Atom", "media": "http://search.yahoo.com/mrss/"}


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


def _extract_hashtags(*values: str) -> list[str]:
    tags: list[str] = []
    for value in values:
        tags.extend(re.findall(r"#([a-zA-Z0-9_-]+)", value))
    return [f"#{tag.lower()}" for tag in dict.fromkeys(tags)]


def _extract_keywords(*values: str) -> list[str]:
    combined = " ".join(values).lower()
    candidates = re.findall(r"[a-z][a-z0-9-]{3,}", combined)
    keywords = [token for token in candidates if token not in {"https", "watch", "www", "youtube"}]
    return list(dict.fromkeys(keywords[:6]))


def _thumbnail_signal_from_text(title: str, description: str) -> dict[str, float]:
    text = f"{title} {description}".lower()
    sensational_hits = sum(
        token in text for token in ["breaking", "secret", "confirmed", "shocking", "urgent", "exposed", "leak"]
    )
    text_density = min(0.18 + sensational_hits * 0.12 + len(title) / 180.0, 0.9)
    shock_indicator = min(0.08 + sensational_hits * 0.16, 0.95)
    return {
        "saturation": round(min(0.28 + sensational_hits * 0.13, 0.92), 4),
        "contrast": round(min(0.3 + sensational_hits * 0.11, 0.88), 4),
        "text_density": round(text_density, 4),
        "face_emphasis": round(min(0.1 + sensational_hits * 0.09, 0.86), 4),
        "shock_indicator": round(shock_indicator, 4),
    }


def _default_fetch_text(source_url: str) -> str:
    response = httpx.get(source_url, timeout=20.0, follow_redirects=True)
    response.raise_for_status()
    return response.text


def _safe_text(node: ET.Element | None, path: str) -> str:
    if node is None:
        return ""
    found = node.find(path, ATOM_NAMESPACE)
    return found.text.strip() if found is not None and found.text else ""


def _parse_youtube_rss_source(
    run_id: str,
    source: PublicSourceSpec,
    feed_text: str,
) -> list[DiscoveredItem]:
    root = ET.fromstring(feed_text)
    items: list[DiscoveredItem] = []
    for index, entry in enumerate(root.findall("atom:entry", ATOM_NAMESPACE), start=1):
        video_id = _safe_text(entry, "yt:videoId") if "yt" in ATOM_NAMESPACE else ""
        if not video_id:
            video_id = _safe_text(entry, "atom:id").split(":")[-1]
        title = _safe_text(entry, "atom:title") or f"{source.channel_name} item {index}"
        description = _safe_text(entry, "media:group/media:description") or _safe_text(entry, "atom:title")
        upload_time = _safe_text(entry, "atom:published") or utc_now()
        link = ""
        link_node = entry.find("atom:link[@rel='alternate']", ATOM_NAMESPACE) or entry.find("atom:link", ATOM_NAMESPACE)
        if link_node is not None:
            link = link_node.attrib.get("href", "")
        if not link and video_id:
            link = f"https://www.youtube.com/watch?v={video_id}"
        transcript_excerpt = description or title
        keywords = _extract_keywords(title, description)
        hashtags = _extract_hashtags(title, description)
        sensational_hits = sum(token in title.lower() for token in ["breaking", "secret", "confirmed", "urgent", "shocking"])
        risk_seed = round(min(0.14 + sensational_hits * 0.16, 0.92), 4)
        mismatch_seed = round(min(0.08 + sensational_hits * 0.06, 0.52), 4)
        item_id = slugify(video_id or f"{source.source_id}-{index}")
        items.append(
            DiscoveredItem(
                item_id=item_id,
                source_id=source.source_id,
                source_type=source.source_type,
                platform=source.platform,
                source_url=link,
                channel_name=source.channel_name,
                channel_prior_flags=source.channel_prior_flags,
                title=title,
                description=description or title,
                tags=keywords,
                hashtags=hashtags,
                transcript_excerpt=transcript_excerpt,
                upload_time=upload_time,
                duration_seconds=0,
                view_count=0,
                like_count=0,
                template_cluster=slugify(source.channel_name),
                thumbnail_signal=_thumbnail_signal_from_text(title, description),
                risk_seed=risk_seed,
                mismatch_seed=mismatch_seed,
            )
        )
    return items


def _build_public_discovery_run(
    run_id: str,
    public_sources: list[PublicSourceSpec],
    fetcher: FetchText | None = None,
) -> tuple[str, DiscoveryRunManifest, list[DiscoveredItem]]:
    resolved_fetcher = fetcher or _default_fetch_text
    records: list[SourceManifestRecord] = []
    items: list[DiscoveredItem] = []

    for source in public_sources:
        status = "pending"
        try:
            feed_text = resolved_fetcher(source.source_url)
            parsed_items = _parse_youtube_rss_source(run_id, source, feed_text)
            items.extend(parsed_items)
            status = "collected" if parsed_items else "quarantined"
        except (httpx.HTTPError, ET.ParseError, ValueError):
            status = "failed"
        records.append(
            SourceManifestRecord(
                source_id=source.source_id,
                source_type=source.source_type,
                platform=source.platform,
                source_url=source.source_url,
                collected_at=run_id,
                access_method=source.access_method,
                expected_fields=[
                    "title",
                    "description",
                    "source_url",
                    "channel_name",
                    "upload_time",
                    "transcript_excerpt",
                ],
                parsing_risk=source.parsing_risk,
                status=status,
            )
        )

    return run_id, build_source_manifest(run_id, records), items


def build_discovery_run(
    run_id: str | None = None,
    public_sources: list[PublicSourceSpec] | None = None,
    fetcher: FetchText | None = None,
) -> tuple[str, DiscoveryRunManifest, list[DiscoveredItem]]:
    resolved_run_id = run_id or make_run_id("discovery")
    if public_sources:
        return _build_public_discovery_run(resolved_run_id, public_sources, fetcher)
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
                source_url=f"https://www.youtube.com/@{source_slug}",
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


def persist_discovery_run(
    run_id: str | None = None,
    public_sources: list[PublicSourceSpec] | None = None,
    fetcher: FetchText | None = None,
) -> tuple[str, DiscoveryRunManifest, list[DiscoveredItem]]:
    resolved_run_id, manifest, items = build_discovery_run(run_id, public_sources=public_sources, fetcher=fetcher)
    root = repo_root()
    discovery_dir = ensure_dir(root / "datasets" / "raw" / "discovery_runs")
    source_manifest_dir = ensure_dir(root / "datasets" / "raw" / "source_manifests")
    write_json(source_manifest_dir / f"{resolved_run_id}.json", manifest.model_dump())
    write_jsonl(discovery_dir / f"{resolved_run_id}.jsonl", [item.model_dump() for item in items])
    return resolved_run_id, manifest, items
