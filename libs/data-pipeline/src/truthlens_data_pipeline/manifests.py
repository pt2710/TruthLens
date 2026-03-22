from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class SourceManifestRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_type: str
    platform: str
    collected_at: str
    access_method: str
    expected_fields: list[str]
    parsing_risk: str
    status: str


class DiscoveryRunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    generated_at: str
    coverage_count: int = Field(ge=0)
    records: list[SourceManifestRecord]


def build_source_manifest(run_id: str, records: list[SourceManifestRecord]) -> DiscoveryRunManifest:
    return DiscoveryRunManifest(
        run_id=run_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        coverage_count=len(records),
        records=records,
    )
