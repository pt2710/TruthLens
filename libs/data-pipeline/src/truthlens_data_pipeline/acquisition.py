from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from html import unescape
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import httpx
from pydantic import BaseModel, ConfigDict, Field

from truthlens_data_pipeline.discovery import DiscoveredItem
from truthlens_data_pipeline.paths import (
    ensure_dir,
    relative_path,
    repo_root,
    utc_now,
    write_json,
    write_jsonl,
)


class AcquiredItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1)
    source_run_id: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    channel_name: str = Field(min_length=1)
    channel_prior_flags: int = Field(ge=0)
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
    thumbnail_source_url: str | None = None
    thumbnail_path: str = Field(min_length=1)
    thumbnail_artifact_kind: str = Field(min_length=1)
    transcript_path: str = Field(min_length=1)
    acquisition_status: str = Field(min_length=1)
    risk_seed: float = Field(ge=0.0, le=1.0)
    mismatch_seed: float = Field(ge=0.0, le=1.0)
    duplicate_of: str | None = None


FetchBytes = Callable[[str], bytes]
FetchText = Callable[[str], str]


def _default_fetch_bytes(source_url: str) -> bytes:
    response = httpx.get(source_url, timeout=20.0, follow_redirects=True)
    response.raise_for_status()
    return response.content


def _artifact_suffix(source_url: str | None) -> str:
    if not source_url:
        return ".json"
    path = urlparse(source_url).path
    suffix = Path(path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    return ".bin"


def _parse_iso8601_duration(value: str) -> int:
    match = re.fullmatch(
        r"PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?",
        value.strip(),
    )
    if not match:
        return 0
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return (hours * 3600) + (minutes * 60) + seconds


def _first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1)


def _extract_quoted_json_block(pattern: str, html: str) -> dict[str, Any] | None:
    payload = _first_match(pattern, html)
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def _meta_content(
    html: str,
    *,
    name: str | None = None,
    prop: str | None = None,
    itemprop: str | None = None,
) -> str | None:
    attribute, value = (
        ("name", name)
        if name is not None
        else ("property", prop)
        if prop is not None
        else ("itemprop", itemprop)
    )
    if value is None:
        return None
    pattern = rf"<meta[^>]+{attribute}=[\"']{re.escape(value)}[\"'][^>]+content=[\"']([^\"']+)[\"']"
    found = _first_match(pattern, html)
    return unescape(found) if found else None


def _caption_excerpt(xml_text: str, *, limit: int = 320) -> str:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return ""
    chunks: list[str] = []
    for node in root.findall(".//text"):
        if node.text:
            chunks.append(unescape(node.text).strip())
        if len(" ".join(chunks)) >= limit:
            break
    transcript = " ".join(chunk for chunk in chunks if chunk)
    return transcript[:limit].strip()


def _extract_hashtags(text: str) -> list[str]:
    hashtags = re.findall(r"(#[A-Za-z0-9_]+)", text)
    return sorted({tag.lower() for tag in hashtags})


def _watch_page_metadata(
    html: str,
    *,
    caption_fetcher: FetchText | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    json_ld = _extract_quoted_json_block(
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>\s*(\{.*?\})\s*</script>",
        html,
    )
    if isinstance(json_ld, dict):
        duration = json_ld.get("duration")
        interaction_count = json_ld.get("interactionCount")
        description = json_ld.get("description")
        keywords = json_ld.get("keywords")
        thumbnail_url = json_ld.get("thumbnailUrl")
        if isinstance(duration, str):
            metadata["duration_seconds"] = _parse_iso8601_duration(duration)
        if isinstance(interaction_count, str) and interaction_count.isdigit():
            metadata["view_count"] = int(interaction_count)
        if isinstance(description, str) and description.strip():
            metadata["description"] = description.strip()
        if isinstance(keywords, list):
            metadata["tags"] = [str(keyword).strip().lower() for keyword in keywords if str(keyword).strip()]
        if isinstance(thumbnail_url, list) and thumbnail_url:
            metadata["thumbnail_source_url"] = str(thumbnail_url[0])
        elif isinstance(thumbnail_url, str) and thumbnail_url.strip():
            metadata["thumbnail_source_url"] = thumbnail_url.strip()

    player_response = _extract_quoted_json_block(
        r"ytInitialPlayerResponse\s*=\s*(\{.*?\})\s*;",
        html,
    )
    if isinstance(player_response, dict):
        video_details = player_response.get("videoDetails", {})
        if isinstance(video_details, dict):
            short_description = video_details.get("shortDescription")
            length_seconds = video_details.get("lengthSeconds")
            view_count = video_details.get("viewCount")
            keywords = video_details.get("keywords")
            if isinstance(short_description, str) and short_description.strip():
                metadata["description"] = short_description.strip()
            if isinstance(length_seconds, str) and length_seconds.isdigit():
                metadata["duration_seconds"] = int(length_seconds)
            if isinstance(view_count, str) and view_count.isdigit():
                metadata["view_count"] = int(view_count)
            if isinstance(keywords, list):
                metadata["tags"] = [str(keyword).strip().lower() for keyword in keywords if str(keyword).strip()]

        captions = player_response.get("captions", {})
        if isinstance(captions, dict):
            renderer = captions.get("playerCaptionsTracklistRenderer", {})
            if isinstance(renderer, dict):
                caption_tracks = renderer.get("captionTracks", [])
                if isinstance(caption_tracks, list) and caption_tracks and caption_fetcher is not None:
                    first_track = caption_tracks[0]
                    if isinstance(first_track, dict):
                        base_url = str(first_track.get("baseUrl", "")).strip()
                        if base_url:
                            try:
                                metadata["transcript_excerpt"] = _caption_excerpt(caption_fetcher(base_url))
                            except (httpx.HTTPError, OSError, ValueError):
                                pass

    description = metadata.get("description") or _meta_content(html, name="description")
    if description:
        metadata["description"] = str(description).strip()
        metadata["hashtags"] = _extract_hashtags(metadata["description"])
    thumbnail_url = metadata.get("thumbnail_source_url") or _meta_content(html, prop="og:image")
    if thumbnail_url:
        metadata["thumbnail_source_url"] = str(thumbnail_url).strip()
    title = _meta_content(html, itemprop="name") or _meta_content(html, prop="og:title")
    if title:
        metadata["title"] = str(title).strip()
    return metadata


def acquire_discovered_items(
    run_id: str,
    discovered_items: list[DiscoveredItem],
    fetcher: FetchBytes | None = None,
    watch_page_fetcher: FetchText | None = None,
    caption_fetcher: FetchText | None = None,
    max_retries: int = 2,
) -> tuple[list[AcquiredItem], dict[str, Any]]:
    root = repo_root()
    metadata_dir = ensure_dir(root / "datasets" / "raw" / "metadata")
    thumbnails_dir = ensure_dir(root / "datasets" / "raw" / "thumbnails")
    transcripts_dir = ensure_dir(root / "datasets" / "raw" / "transcripts")
    quarantine_dir = ensure_dir(thumbnails_dir / "quarantine")
    failure_log_dir = ensure_dir(root / "artifacts" / "reports")
    resolved_fetcher = fetcher or _default_fetch_bytes

    acquired_items: list[AcquiredItem] = []
    metadata_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    retry_count = 0
    watch_page_enrichment_count = 0
    caption_enrichment_count = 0

    for item in discovered_items:
        watch_metadata: dict[str, Any] = {}
        if watch_page_fetcher is not None and item.source_url and item.source_url.startswith("http"):
            try:
                watch_metadata = _watch_page_metadata(
                    watch_page_fetcher(item.source_url),
                    caption_fetcher=caption_fetcher,
                )
                if watch_metadata:
                    watch_page_enrichment_count += 1
                if watch_metadata.get("transcript_excerpt"):
                    caption_enrichment_count += 1
            except (httpx.HTTPError, OSError, ValueError):
                watch_metadata = {}
        transcript_path = transcripts_dir / f"{item.item_id}.txt"
        thumbnail_artifact_kind = "signal-json"
        acquisition_status = "collected"
        thumbnail_path: Path
        thumbnail_source_url = str(watch_metadata.get("thumbnail_source_url") or item.thumbnail_url or "").strip() or None
        description = str(watch_metadata.get("description") or item.description)
        transcript_excerpt = str(watch_metadata.get("transcript_excerpt") or item.transcript_excerpt)
        title = str(watch_metadata.get("title") or item.title)
        duration_seconds = int(watch_metadata.get("duration_seconds") or item.duration_seconds)
        view_count = int(watch_metadata.get("view_count") or item.view_count)
        tags = [str(tag) for tag in (watch_metadata.get("tags") or item.tags)]
        hashtags = [str(tag) for tag in (watch_metadata.get("hashtags") or item.hashtags)]

        if thumbnail_source_url:
            suffix = _artifact_suffix(thumbnail_source_url)
            candidate_thumbnail_path = thumbnails_dir / f"{item.item_id}{suffix}"
            last_error = ""
            downloaded = False
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    retry_count += 1
                try:
                    payload = resolved_fetcher(thumbnail_source_url)
                    candidate_thumbnail_path.write_bytes(payload)
                    thumbnail_path = candidate_thumbnail_path
                    thumbnail_artifact_kind = "image-binary"
                    downloaded = True
                    break
                except (httpx.HTTPError, OSError, ValueError) as error:
                    last_error = str(error)
            else:
                thumbnail_path = quarantine_dir / f"{item.item_id}.json"
                thumbnail_artifact_kind = "signal-json"
                acquisition_status = "quarantined"
                write_json(
                    thumbnail_path,
                    {
                        "thumbnail_signal": item.thumbnail_signal,
                        "thumbnail_url": thumbnail_source_url,
                        "reason": last_error or "thumbnail download failed",
                    },
                )
                failure_rows.append(
                    {
                        "item_id": item.item_id,
                        "source_url": item.source_url,
                        "thumbnail_url": thumbnail_source_url,
                        "status": acquisition_status,
                        "error": last_error or "thumbnail download failed",
                    }
                )
            if not downloaded and acquisition_status != "quarantined":
                thumbnail_path = quarantine_dir / f"{item.item_id}.json"
                write_json(thumbnail_path, item.thumbnail_signal)
                acquisition_status = "quarantined"
                thumbnail_artifact_kind = "signal-json"
        else:
            thumbnail_path = thumbnails_dir / f"{item.item_id}.json"
            write_json(thumbnail_path, item.thumbnail_signal)
        transcript_path.write_text(transcript_excerpt, encoding="utf-8")

        acquired = AcquiredItem(
            item_id=item.item_id,
            source_run_id=run_id,
            source_url=item.source_url,
            channel_name=item.channel_name,
            channel_prior_flags=item.channel_prior_flags,
            title=title,
            description=description,
            tags=tags,
            hashtags=hashtags,
            transcript_excerpt=transcript_excerpt,
            upload_time=item.upload_time,
            duration_seconds=duration_seconds,
            view_count=view_count,
            like_count=item.like_count,
            template_cluster=item.template_cluster,
            thumbnail_source_url=thumbnail_source_url,
            thumbnail_path=relative_path(thumbnail_path),
            thumbnail_artifact_kind=thumbnail_artifact_kind,
            transcript_path=relative_path(transcript_path),
            acquisition_status=acquisition_status,
            risk_seed=item.risk_seed,
            mismatch_seed=item.mismatch_seed,
            duplicate_of=item.duplicate_of,
        )
        acquired_items.append(acquired)
        metadata_rows.append(acquired.model_dump())

    metadata_path = metadata_dir / f"{run_id}.jsonl"
    write_jsonl(metadata_path, metadata_rows)
    failure_log_path = failure_log_dir / f"{run_id}-acquisition-failures.jsonl"
    write_jsonl(failure_log_path, failure_rows)
    quarantined_count = sum(1 for item in acquired_items if item.acquisition_status == "quarantined")
    success_count = len(acquired_items) - quarantined_count
    artifact_kind_counts = Counter(item.thumbnail_artifact_kind for item in acquired_items)
    status_counts = Counter(item.acquisition_status for item in acquired_items)
    downloaded_items = sum(1 for item in acquired_items if item.thumbnail_artifact_kind == "image-binary")
    manifest = {
        "run_id": run_id,
        "generated_at": utc_now(),
        "status": "collected" if quarantined_count == 0 else "partial",
        "success_count": success_count,
        "failure_count": len(failure_rows),
        "quarantined_count": quarantined_count,
        "retry_count": retry_count,
        "success_rate": round(success_count / max(len(acquired_items), 1), 4),
        "thumbnail_download_rate": round(downloaded_items / max(len(acquired_items), 1), 4),
        "watch_page_enrichment_rate": round(watch_page_enrichment_count / max(len(acquired_items), 1), 4),
        "caption_enrichment_rate": round(caption_enrichment_count / max(len(acquired_items), 1), 4),
        "artifact_kind_counts": dict(sorted(artifact_kind_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "corrupted_image_rate": round(quarantined_count / max(len(acquired_items), 1), 4),
        "parser_failure_rate": round(len(failure_rows) / max(len(acquired_items), 1), 4),
        "coverage_count": len(acquired_items),
        "metadata_path": relative_path(metadata_path),
        "failure_log_path": relative_path(failure_log_path),
    }
    manifest_path = root / "datasets" / "manifests" / "sources" / f"{run_id}-acquisition.json"
    write_json(manifest_path, manifest)
    return acquired_items, manifest
