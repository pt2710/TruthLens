from __future__ import annotations

import hashlib
import json
from typing import Any

from truthlens_data_pipeline.acquisition import AcquiredItem
from truthlens_data_pipeline.paths import relative_path, repo_root, write_json, write_jsonl
from truthlens_dataset_governance.validators import validate_dataset_record

SENSATIONAL_TOKENS = {
    "breaking",
    "shocking",
    "confirmed",
    "aliens",
    "secret",
    "urgent",
    "exposed",
}


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def _uppercase_ratio(value: str) -> float:
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return 0.0
    uppercase = sum(1 for char in letters if char.isupper())
    return round(uppercase / len(letters), 4)


def _count_sensational_tokens(value: str) -> int:
    lowered = value.lower()
    return sum(1 for token in SENSATIONAL_TOKENS if token in lowered)


def normalize_acquired_items(
    run_id: str,
    acquired_items: list[AcquiredItem],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    channel_counts: dict[str, int] = {}
    channel_risk_totals: dict[str, float] = {}
    for item in acquired_items:
        channel_counts[item.channel_name] = channel_counts.get(item.channel_name, 0) + 1
        channel_risk_totals[item.channel_name] = channel_risk_totals.get(item.channel_name, 0.0) + item.risk_seed

    normalized_records: list[dict[str, Any]] = []
    for item in acquired_items:
        normalized_title = _normalize_text(item.title)
        normalized_description = _normalize_text(item.description)
        image_fingerprint = hashlib.sha1(
            json.dumps(
                {
                    "template_cluster": item.template_cluster,
                    "thumbnail_path": item.thumbnail_path,
                    "channel_name": item.channel_name,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        text_fingerprint = hashlib.sha1(
            f"{normalized_title.lower()}::{item.channel_name.lower()}".encode("utf-8")
        ).hexdigest()
        sensational_count = _count_sensational_tokens(normalized_title)
        history_features = {
            "channel_uploads": channel_counts[item.channel_name],
            "channel_risk_mean": round(
                channel_risk_totals[item.channel_name] / channel_counts[item.channel_name], 4
            ),
            "publishing_velocity": round(channel_counts[item.channel_name] / 7.0, 4),
        }
        record = validate_dataset_record(
            {
                "item_id": item.item_id,
                "platform": "youtube",
                "source_run_id": run_id,
                "source_url": item.source_url,
                "collected_at": item.upload_time,
                "title": normalized_title,
                "channel_name": item.channel_name,
                "thumbnail_path": item.thumbnail_path,
                "description": normalized_description,
                "tags": item.tags,
                "hashtags": item.hashtags,
                "transcript_excerpt": item.transcript_excerpt,
                "metadata": {
                    "upload_time": item.upload_time,
                    "duration_seconds": item.duration_seconds,
                    "view_count": item.view_count,
                    "like_count": item.like_count,
                    "channel_prior_flags": item.channel_prior_flags,
                    "template_cluster": item.template_cluster,
                    "risk_seed": item.risk_seed,
                    "mismatch_seed": item.mismatch_seed,
                    "duplicate_of": item.duplicate_of,
                    "transcript_path": item.transcript_path,
                },
                "history": {
                    "channel_history_features": history_features,
                    "prior_flags": item.channel_prior_flags,
                },
                "features": {
                    "image_fingerprint": image_fingerprint,
                    "text_fingerprint": text_fingerprint,
                    "language": "en",
                    "template_cluster": item.template_cluster,
                    "title_length": len(normalized_title),
                    "uppercase_ratio": _uppercase_ratio(item.title),
                    "sensational_count": sensational_count,
                    "mismatch_score": round(item.mismatch_seed, 4),
                    "thumbnail_saturation": round(item.risk_seed * 0.65, 4),
                    "thumbnail_text_density": round(0.15 + sensational_count * 0.15, 4),
                },
                "labels": {},
                "provenance": {
                    "transform_version": "normalize-v1",
                    "dataset_build_id": "unbuilt",
                    "split": "unassigned",
                },
                "annotator_notes": [],
            }
        ).model_dump()
        normalized_records.append(record)

    normalized_path = repo_root() / "datasets" / "interim" / "normalized" / f"{run_id}.jsonl"
    write_jsonl(normalized_path, normalized_records)
    transform_manifest = {
        "run_id": run_id,
        "generated_at": acquired_items[0].upload_time if acquired_items else "",
        "transform_version": "normalize-v1",
        "record_count": len(normalized_records),
        "normalized_path": relative_path(normalized_path),
        "fingerprints": ["image_fingerprint", "text_fingerprint"],
    }
    transform_manifest_path = (
        repo_root() / "datasets" / "manifests" / "transforms" / f"{run_id}-normalize.json"
    )
    write_json(transform_manifest_path, transform_manifest)
    return normalized_records, transform_manifest
