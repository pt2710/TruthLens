from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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


def acquire_discovered_items(
    run_id: str,
    discovered_items: list[DiscoveredItem],
    fetcher: FetchBytes | None = None,
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

    for item in discovered_items:
        transcript_path = transcripts_dir / f"{item.item_id}.txt"
        thumbnail_artifact_kind = "signal-json"
        acquisition_status = "collected"
        thumbnail_path: Path

        if item.thumbnail_url:
            suffix = _artifact_suffix(item.thumbnail_url)
            candidate_thumbnail_path = thumbnails_dir / f"{item.item_id}{suffix}"
            last_error = ""
            downloaded = False
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    retry_count += 1
                try:
                    payload = resolved_fetcher(item.thumbnail_url)
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
                        "thumbnail_url": item.thumbnail_url,
                        "reason": last_error or "thumbnail download failed",
                    },
                )
                failure_rows.append(
                    {
                        "item_id": item.item_id,
                        "source_url": item.source_url,
                        "thumbnail_url": item.thumbnail_url,
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
        transcript_path.write_text(item.transcript_excerpt, encoding="utf-8")

        acquired = AcquiredItem(
            item_id=item.item_id,
            source_run_id=run_id,
            source_url=item.source_url,
            channel_name=item.channel_name,
            channel_prior_flags=item.channel_prior_flags,
            title=item.title,
            description=item.description,
            tags=item.tags,
            hashtags=item.hashtags,
            transcript_excerpt=item.transcript_excerpt,
            upload_time=item.upload_time,
            duration_seconds=item.duration_seconds,
            view_count=item.view_count,
            like_count=item.like_count,
            template_cluster=item.template_cluster,
            thumbnail_source_url=item.thumbnail_url,
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
    manifest = {
        "run_id": run_id,
        "generated_at": utc_now(),
        "status": "collected" if quarantined_count == 0 else "partial",
        "success_count": success_count,
        "failure_count": len(failure_rows),
        "quarantined_count": quarantined_count,
        "retry_count": retry_count,
        "success_rate": round(success_count / max(len(acquired_items), 1), 4),
        "coverage_count": len(acquired_items),
        "metadata_path": relative_path(metadata_path),
        "failure_log_path": relative_path(failure_log_path),
    }
    manifest_path = root / "datasets" / "manifests" / "sources" / f"{run_id}-acquisition.json"
    write_json(manifest_path, manifest)
    return acquired_items, manifest
