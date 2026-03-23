from __future__ import annotations

import hashlib
import json
from typing import Any

from truthlens_data_pipeline.acquisition import AcquiredItem
from truthlens_data_pipeline.paths import relative_path, repo_root, write_json, write_jsonl
from truthlens_feature_extractors import (
    count_sensational_tokens,
    extract_thumbnail_features,
    normalize_text,
    transcript_mismatch_score,
    transcript_overlap,
    uppercase_ratio,
)
from truthlens_dataset_governance.validators import validate_dataset_record


def _thumbnail_signal(item: AcquiredItem) -> dict[str, float]:
    thumbnail_path = repo_root() / item.thumbnail_path
    if thumbnail_path.suffix == ".json" and thumbnail_path.exists():
        payload = json.loads(thumbnail_path.read_text(encoding="utf-8"))
        if "thumbnail_signal" in payload:
            signal = payload["thumbnail_signal"]
        else:
            signal = payload
        return {
            "brightness": float(signal.get("brightness", 0.45)),
            "saturation": float(signal.get("saturation", round(item.risk_seed * 0.65, 4))),
            "contrast": float(signal.get("contrast", round(0.18 + item.risk_seed * 0.5, 4))),
            "text_density": float(signal.get("text_density", round(0.15 + item.risk_seed * 0.2, 4))),
            "face_emphasis": float(signal.get("face_emphasis", round(0.12 + item.risk_seed * 0.2, 4))),
            "shock_indicator": float(signal.get("shock_indicator", round(0.1 + item.risk_seed * 0.35, 4))),
            "entropy": float(signal.get("entropy", 0.4)),
            "aspect_ratio": float(signal.get("aspect_ratio", round((16 / 9) / 2.5, 4))),
            "byte_size": float(signal.get("byte_size", thumbnail_path.stat().st_size if thumbnail_path.exists() else 0.0)),
        }
    extracted = extract_thumbnail_features(
        thumbnail_path,
        fallback_signal={
            "saturation": round(item.risk_seed * 0.65, 4),
            "contrast": round(0.18 + item.risk_seed * 0.5, 4),
            "text_density": round(0.15 + item.risk_seed * 0.15, 4),
            "face_emphasis": round(0.1 + item.risk_seed * 0.18, 4),
            "shock_indicator": round(0.08 + item.risk_seed * 0.3, 4),
        },
    )
    return {
        "brightness": float(extracted.get("thumbnail_brightness", 0.45)),
        "saturation": float(extracted.get("thumbnail_saturation", round(item.risk_seed * 0.65, 4))),
        "contrast": float(extracted.get("thumbnail_contrast", round(0.18 + item.risk_seed * 0.5, 4))),
        "text_density": float(extracted.get("thumbnail_text_density", round(0.15 + item.risk_seed * 0.15, 4))),
        "face_emphasis": float(extracted.get("thumbnail_face_emphasis", round(0.1 + item.risk_seed * 0.18, 4))),
        "shock_indicator": float(extracted.get("thumbnail_shock_indicator", round(0.08 + item.risk_seed * 0.3, 4))),
        "entropy": float(extracted.get("thumbnail_entropy", 0.4)),
        "aspect_ratio": float(extracted.get("thumbnail_aspect_ratio", round((16 / 9) / 2.5, 4))),
        "byte_size": float(extracted.get("thumbnail_byte_size", 0.0)),
    }


def _image_fingerprint(item: AcquiredItem) -> str:
    thumbnail_path = repo_root() / item.thumbnail_path
    if thumbnail_path.exists():
        return hashlib.sha1(thumbnail_path.read_bytes()).hexdigest()
    return hashlib.sha1(
        json.dumps(
            {
                "template_cluster": item.template_cluster,
                "thumbnail_path": item.thumbnail_path,
                "channel_name": item.channel_name,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def normalize_acquired_items(
    run_id: str,
    acquired_items: list[AcquiredItem],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    channel_counts: dict[str, int] = {}
    channel_risk_totals: dict[str, float] = {}
    channel_template_counts: dict[str, dict[str, int]] = {}
    channel_like_ratios: dict[str, list[float]] = {}
    for item in acquired_items:
        channel_counts[item.channel_name] = channel_counts.get(item.channel_name, 0) + 1
        channel_risk_totals[item.channel_name] = channel_risk_totals.get(item.channel_name, 0.0) + item.risk_seed
        channel_template_counts.setdefault(item.channel_name, {})
        channel_template_counts[item.channel_name][item.template_cluster] = (
            channel_template_counts[item.channel_name].get(item.template_cluster, 0) + 1
        )
        channel_like_ratios.setdefault(item.channel_name, []).append(
            item.like_count / max(item.view_count, 1)
        )

    normalized_records: list[dict[str, Any]] = []
    for item in acquired_items:
        normalized_title = normalize_text(item.title)
        normalized_description = normalize_text(item.description)
        thumbnail_signal = _thumbnail_signal(item)
        title_transcript_overlap = transcript_overlap(normalized_title, item.transcript_excerpt)
        sensational_count = count_sensational_tokens(normalized_title)
        transcript_mismatch = transcript_mismatch_score(
            normalized_title,
            item.transcript_excerpt,
            sensational_count,
        )
        image_fingerprint = _image_fingerprint(item)
        text_fingerprint = hashlib.sha1(
            f"{normalized_title.lower()}::{item.channel_name.lower()}".encode("utf-8")
        ).hexdigest()
        channel_like_ratio = item.like_count / max(item.view_count, 1)
        average_like_ratio = sum(channel_like_ratios[item.channel_name]) / max(
            len(channel_like_ratios[item.channel_name]),
            1,
        )
        engagement_anomaly = round(channel_like_ratio / max(average_like_ratio, 0.0001), 4)
        repeat_template_rate = round(
            channel_template_counts[item.channel_name].get(item.template_cluster, 0)
            / max(channel_counts[item.channel_name], 1),
            4,
        )
        history_features = {
            "channel_uploads": channel_counts[item.channel_name],
            "channel_risk_mean": round(
                channel_risk_totals[item.channel_name] / channel_counts[item.channel_name], 4
            ),
            "publishing_velocity": round(channel_counts[item.channel_name] / 7.0, 4),
            "recent_upload_velocity": round(channel_counts[item.channel_name] / 7.0, 4),
            "repeat_template_rate": repeat_template_rate,
            "engagement_anomaly": engagement_anomaly,
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
                    "thumbnail_source_url": item.thumbnail_source_url,
                    "thumbnail_artifact_kind": item.thumbnail_artifact_kind,
                    "acquisition_status": item.acquisition_status,
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
                    "uppercase_ratio": uppercase_ratio(item.title),
                    "sensational_count": sensational_count,
                    "mismatch_score": round(item.mismatch_seed, 4),
                    "transcript_title_overlap": title_transcript_overlap,
                    "transcript_mismatch_score": transcript_mismatch,
                    "thumbnail_brightness": round(thumbnail_signal["brightness"], 4),
                    "thumbnail_saturation": round(thumbnail_signal["saturation"], 4),
                    "thumbnail_contrast": round(thumbnail_signal["contrast"], 4),
                    "thumbnail_text_density": round(thumbnail_signal["text_density"], 4),
                    "thumbnail_face_emphasis": round(thumbnail_signal["face_emphasis"], 4),
                    "thumbnail_shock_indicator": round(thumbnail_signal["shock_indicator"], 4),
                    "thumbnail_entropy": round(thumbnail_signal["entropy"], 4),
                    "thumbnail_aspect_ratio": round(thumbnail_signal["aspect_ratio"], 4),
                    "thumbnail_artifact_kind": item.thumbnail_artifact_kind,
                    "thumbnail_byte_size": round(thumbnail_signal["byte_size"], 4),
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
