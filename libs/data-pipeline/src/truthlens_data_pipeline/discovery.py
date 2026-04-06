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
    thumbnail_url: str | None = None
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
        {"name": "Archive Lens Docs", "prior_flags": 0, "risk_profile": "balanced"},
        {"name": "Builder How-To Hub", "prior_flags": 1, "risk_profile": "commercial"},
        {"name": "Calm Science Daily", "prior_flags": 0, "risk_profile": "balanced"},
        {"name": "Context First Media", "prior_flags": 0, "risk_profile": "balanced"},
        {"name": "Device Verdict Lab", "prior_flags": 1, "risk_profile": "commercial"},
        {"name": "Launch Trailer Vault", "prior_flags": 1, "risk_profile": "commercial"},
        {"name": "Matchday Tactics Desk", "prior_flags": 1, "risk_profile": "gaming"},
        {"name": "Northern Echo Records", "prior_flags": 0, "risk_profile": "creative"},
        {"name": "Now Stream Briefing", "prior_flags": 2, "risk_profile": "elevated"},
        {"name": "OpenSky Alerts", "prior_flags": 4, "risk_profile": "elevated"},
        {"name": "Orbital Satire Circuit", "prior_flags": 0, "risk_profile": "creative"},
        {"name": "Patch Notes Arena", "prior_flags": 1, "risk_profile": "gaming"},
        {"name": "Signal Watch Europe", "prior_flags": 3, "risk_profile": "elevated"},
        {"name": "Studio Canvas Atlas", "prior_flags": 0, "risk_profile": "creative"},
        {"name": "Verified Space Desk", "prior_flags": 0, "risk_profile": "balanced"},
        {"name": "Viral Evidence Desk", "prior_flags": 4, "risk_profile": "elevated"},
        {"name": "Weekly Orbit Ledger", "prior_flags": 1, "risk_profile": "balanced"},
        {"name": "Zero Chill Bulletins", "prior_flags": 3, "risk_profile": "elevated"},
    ]


_PROFILE_RISK_MULTIPLIER = {
    "elevated": 1.08,
    "balanced": 0.94,
    "creative": 0.82,
    "commercial": 0.98,
    "gaming": 0.88,
}

_PROFILE_MISMATCH_MULTIPLIER = {
    "elevated": 1.1,
    "balanced": 0.95,
    "creative": 0.78,
    "commercial": 0.96,
    "gaming": 0.84,
}


def _bootstrap_templates() -> list[dict[str, Any]]:
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
            "title": "Leaked official trailer confirmed before it gets deleted",
            "description": "A fake-official packaging pattern that borrows studio authority and urgency without credible sourcing.",
            "tags": ["leaked", "official trailer", "confirmed"],
            "hashtags": ["#leaked", "#official"],
            "transcript": "The host repeats that this is the real trailer and that viewers must watch now before it disappears.",
            "template_cluster": "fake-official-trailer",
            "thumbnail_signal": {
                "saturation": 0.88,
                "contrast": 0.83,
                "text_density": 0.78,
                "face_emphasis": 0.76,
                "shock_indicator": 0.89,
            },
            "risk_seed": 0.92,
            "mismatch_seed": 0.8,
        },
        {
            "title": "This method works 100% and changes everything",
            "description": "A tutorial-shaped promise with exaggerated outcomes, vague proof claims, and little substantive delivery.",
            "tags": ["tutorial", "100%", "changes everything"],
            "hashtags": ["#guide", "#mustsee"],
            "transcript": "The presenter stalls around a miracle workflow and never demonstrates the promised result in a credible way.",
            "template_cluster": "miracle-guide",
            "thumbnail_signal": {
                "saturation": 0.81,
                "contrast": 0.79,
                "text_density": 0.76,
                "face_emphasis": 0.64,
                "shock_indicator": 0.82,
            },
            "risk_seed": 0.87,
            "mismatch_seed": 0.77,
        },
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
            "title": "Telescope calibration workshop lesson",
            "description": "An educational explainer that walks through each calibration step and the measured improvement.",
            "tags": ["calibration", "lesson", "workshop"],
            "hashtags": ["#science", "#lesson"],
            "transcript": "This lecture explains the calibration process, the expected noise floor, and why the instrument changes mattered.",
            "template_cluster": "calibration-workshop",
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
            "title": "Official audio lyric video live session remix",
            "description": "A music release with album art, non-literal cover imagery, and a transcript that matches a song structure rather than a factual claim.",
            "tags": ["official audio", "lyric video", "remix"],
            "hashtags": ["#music", "#lyrics"],
            "transcript": "Verse one fades into the chorus before the bridge returns in the live session arrangement.",
            "template_cluster": "official-audio-remix",
            "thumbnail_signal": {
                "saturation": 0.58,
                "contrast": 0.44,
                "text_density": 0.18,
                "face_emphasis": 0.16,
                "shock_indicator": 0.06,
            },
            "risk_seed": 0.14,
            "mismatch_seed": 0.1,
        },
        {
            "title": "Gallery illustration sketchbook exhibition",
            "description": "An art studio upload showing concept art, sketches, and exhibition notes without a literal thumbnail-title requirement.",
            "tags": ["gallery", "illustration", "concept art"],
            "hashtags": ["#art", "#gallery"],
            "transcript": "The artist walks through the sketchbook, color studies, and final illustration choices for the exhibition wall.",
            "template_cluster": "gallery-exhibition",
            "thumbnail_signal": {
                "saturation": 0.49,
                "contrast": 0.4,
                "text_density": 0.12,
                "face_emphasis": 0.07,
                "shock_indicator": 0.05,
            },
            "risk_seed": 0.12,
            "mismatch_seed": 0.11,
        },
        {
            "title": "Parody sketch reacts to breaking headlines",
            "description": "A satire format that uses theatrical framing and joke cues rather than factual news delivery.",
            "tags": ["parody", "sketch", "satire"],
            "hashtags": ["#satire", "#comedy"],
            "transcript": "The comedian exaggerates the headline to make the joke obvious and breaks character midway through the sketch.",
            "template_cluster": "satire-sketch",
            "thumbnail_signal": {
                "saturation": 0.56,
                "contrast": 0.51,
                "text_density": 0.26,
                "face_emphasis": 0.52,
                "shock_indicator": 0.22,
            },
            "risk_seed": 0.19,
            "mismatch_seed": 0.16,
        },
        {
            "title": "Gameplay walkthrough highlights and patch notes",
            "description": "A gaming video mixing challenge-run footage, patch analysis, and a build guide.",
            "tags": ["gameplay", "patch notes", "build guide"],
            "hashtags": ["#gaming", "#walkthrough"],
            "transcript": "The host shows the boss fight, explains the patch changes, and then demonstrates the build guide in a live run.",
            "template_cluster": "gameplay-patch-highlights",
            "thumbnail_signal": {
                "saturation": 0.67,
                "contrast": 0.58,
                "text_density": 0.24,
                "face_emphasis": 0.2,
                "shock_indicator": 0.18,
            },
            "risk_seed": 0.2,
            "mismatch_seed": 0.13,
        },
        {
            "title": "Matchday tactics breakdown and highlights review",
            "description": "A sports analysis format with intense visuals, replays, and concrete discussion of match events.",
            "tags": ["matchday", "tactics", "highlights"],
            "hashtags": ["#sports", "#tactics"],
            "transcript": "This post-game breakdown shows the actual goal sequence and explains the tactical adjustment that changed the match.",
            "template_cluster": "sports-tactics-breakdown",
            "thumbnail_signal": {
                "saturation": 0.62,
                "contrast": 0.56,
                "text_density": 0.22,
                "face_emphasis": 0.29,
                "shock_indicator": 0.17,
            },
            "risk_seed": 0.18,
            "mismatch_seed": 0.12,
        },
        {
            "title": "Device review comparison and first impressions",
            "description": "A comparison and benchmark video that actually tests the promised devices and summarizes the tradeoffs.",
            "tags": ["review", "comparison", "benchmark"],
            "hashtags": ["#review", "#tech"],
            "transcript": "The presenter compares battery life, thermals, and camera performance before giving a first-impressions verdict.",
            "template_cluster": "device-review-comparison",
            "thumbnail_signal": {
                "saturation": 0.46,
                "contrast": 0.43,
                "text_density": 0.21,
                "face_emphasis": 0.24,
                "shock_indicator": 0.1,
            },
            "risk_seed": 0.17,
            "mismatch_seed": 0.11,
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


def _thumbnail_url(entry: ET.Element) -> str | None:
    media_group = entry.find("media:group", ATOM_NAMESPACE)
    thumbnail_node = None
    if media_group is not None:
        thumbnail_node = media_group.find("media:thumbnail", ATOM_NAMESPACE)
    if thumbnail_node is None:
        thumbnail_node = entry.find("media:thumbnail", ATOM_NAMESPACE)
    if thumbnail_node is None:
        return None
    candidate = thumbnail_node.attrib.get("url", "").strip()
    return candidate or None


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
        thumbnail_url = _thumbnail_url(entry)
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
                thumbnail_url=thumbnail_url,
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
    bootstrap_templates = _bootstrap_templates()

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
        risk_multiplier = _PROFILE_RISK_MULTIPLIER.get(channel["risk_profile"], 1.0)
        mismatch_multiplier = _PROFILE_MISMATCH_MULTIPLIER.get(channel["risk_profile"], 1.0)
        for template_index, template in enumerate(bootstrap_templates):
            item_slug = f"{source_slug}-{template_index + 1}"
            offset = channel_index * len(bootstrap_templates) + template_index
            month = 3 + (offset // 28)
            day = (offset % 28) + 1
            risk_seed = min(
                max(template["risk_seed"] * risk_multiplier + channel["prior_flags"] * 0.015, 0.02),
                0.98,
            )
            mismatch_seed = min(
                max(template["mismatch_seed"] * mismatch_multiplier + channel["prior_flags"] * 0.012, 0.02),
                0.98,
            )
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
                    upload_time=f"2026-{month:02d}-{day:02d}T12:00:00Z",
                    duration_seconds=420 + template_index * 45,
                    view_count=12500 + channel_index * 1900 + template_index * 950,
                    like_count=1200 + channel_index * 140 + template_index * 85,
                    template_cluster=template["template_cluster"],
                    thumbnail_url=None,
                    thumbnail_signal=template["thumbnail_signal"],
                    risk_seed=round(risk_seed, 4),
                    mismatch_seed=round(mismatch_seed, 4),
                )
            )

    duplicate_originals = [items[0], items[9], items[18], items[27]]
    for duplicate_index, original in enumerate(duplicate_originals, start=1):
        items.append(
            original.model_copy(
                update={
                    "item_id": f"{original.item_id}-dup-{duplicate_index}",
                    "source_url": original.source_url,
                    "duplicate_of": original.item_id,
                    "upload_time": f"2026-11-{20 + duplicate_index:02d}T12:00:00Z",
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
