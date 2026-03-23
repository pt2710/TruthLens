from __future__ import annotations

from typing import Any

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
    thumbnail_path: str = Field(min_length=1)
    transcript_path: str = Field(min_length=1)
    risk_seed: float = Field(ge=0.0, le=1.0)
    mismatch_seed: float = Field(ge=0.0, le=1.0)
    duplicate_of: str | None = None


def acquire_discovered_items(
    run_id: str,
    discovered_items: list[DiscoveredItem],
) -> tuple[list[AcquiredItem], dict[str, Any]]:
    root = repo_root()
    metadata_dir = ensure_dir(root / "datasets" / "raw" / "metadata")
    thumbnails_dir = ensure_dir(root / "datasets" / "raw" / "thumbnails")
    transcripts_dir = ensure_dir(root / "datasets" / "raw" / "transcripts")

    acquired_items: list[AcquiredItem] = []
    metadata_rows: list[dict[str, Any]] = []

    for item in discovered_items:
        thumbnail_path = thumbnails_dir / f"{item.item_id}.json"
        transcript_path = transcripts_dir / f"{item.item_id}.txt"
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
            thumbnail_path=relative_path(thumbnail_path),
            transcript_path=relative_path(transcript_path),
            risk_seed=item.risk_seed,
            mismatch_seed=item.mismatch_seed,
            duplicate_of=item.duplicate_of,
        )
        acquired_items.append(acquired)
        metadata_rows.append(acquired.model_dump())

    metadata_path = metadata_dir / f"{run_id}.jsonl"
    write_jsonl(metadata_path, metadata_rows)
    manifest = {
        "run_id": run_id,
        "generated_at": utc_now(),
        "status": "collected",
        "success_count": len(acquired_items),
        "failure_count": 0,
        "success_rate": 1.0,
        "coverage_count": len(acquired_items),
        "metadata_path": relative_path(metadata_path),
    }
    manifest_path = root / "datasets" / "manifests" / "sources" / f"{run_id}-acquisition.json"
    write_json(manifest_path, manifest)
    return acquired_items, manifest
