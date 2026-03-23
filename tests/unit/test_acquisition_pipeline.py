from pathlib import Path

import pytest

from truthlens_data_pipeline.acquisition import acquire_discovered_items
from truthlens_data_pipeline.discovery import DiscoveredItem
from truthlens_data_pipeline.paths import read_jsonl, repo_root

WATCH_HTML = """
<html>
  <head>
    <meta property="og:title" content="Enriched orbital weather bulletin" />
    <meta property="og:image" content="https://img.youtube.com/vi/rss-item-1/maxresdefault.jpg" />
    <meta name="description" content="Watch-page description with more complete source notes." />
    <script type="application/ld+json">
      {"duration":"PT13M5S","interactionCount":"45678","thumbnailUrl":["https://img.youtube.com/vi/rss-item-1/maxresdefault.jpg"]}
    </script>
    <script>
      var ytInitialPlayerResponse = {"videoDetails":{"shortDescription":"Detailed watch-page description.","lengthSeconds":"785","viewCount":"45678"},"captions":{"playerCaptionsTracklistRenderer":{"captionTracks":[{"baseUrl":"https://example.com/captions.xml"}]}}};
    </script>
  </head>
</html>
"""

CAPTION_XML = """
<transcript>
  <text start="0" dur="2">Orbital weather bulletin with measured source notes.</text>
  <text start="2" dur="2">Transcript enrichment is available from captions.</text>
</transcript>
"""


def _item() -> DiscoveredItem:
    return DiscoveredItem(
        item_id="rss-item-1",
        source_id="rss-source",
        source_type="channel-rss",
        platform="youtube",
        source_url="https://www.youtube.com/watch?v=rss-item-1",
        channel_name="RSS Channel",
        channel_prior_flags=1,
        title="Breaking orbital weather bulletin",
        description="Public bulletin pulled from RSS.",
        tags=["orbital", "weather"],
        hashtags=["#weather"],
        transcript_excerpt="Public bulletin transcript excerpt.",
        upload_time="2026-03-22T12:00:00Z",
        duration_seconds=0,
        view_count=0,
        like_count=0,
        template_cluster="rss-channel",
        thumbnail_url="https://img.youtube.com/vi/rss-item-1/hqdefault.jpg",
        thumbnail_signal={
            "saturation": 0.62,
            "contrast": 0.59,
            "text_density": 0.34,
            "face_emphasis": 0.22,
            "shock_indicator": 0.31,
        },
        risk_seed=0.42,
        mismatch_seed=0.19,
    )


def test_acquisition_downloads_public_thumbnails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    acquired_items, manifest = acquire_discovered_items(
        "run-public-thumb",
        [_item()],
        fetcher=lambda _url: b"fake-jpeg-binary",
    )

    acquired = acquired_items[0]
    thumbnail_path = repo_root() / acquired.thumbnail_path
    metadata_rows = read_jsonl(repo_root() / "datasets/raw/metadata/run-public-thumb.jsonl")

    assert manifest["success_count"] == 1
    assert manifest["failure_count"] == 0
    assert acquired.thumbnail_artifact_kind == "image-binary"
    assert acquired.acquisition_status == "collected"
    assert thumbnail_path.exists()
    assert thumbnail_path.suffix == ".jpg"
    assert metadata_rows[0]["thumbnail_artifact_kind"] == "image-binary"
    assert manifest["thumbnail_download_rate"] == 1.0
    assert manifest["artifact_kind_counts"]["image-binary"] == 1
    assert manifest["status_counts"]["collected"] == 1


def test_acquisition_quarantines_failed_thumbnail_downloads(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    def failing_fetcher(_url: str) -> bytes:
        raise ValueError("network unavailable")

    acquired_items, manifest = acquire_discovered_items(
        "run-public-quarantine",
        [_item()],
        fetcher=failing_fetcher,
        max_retries=1,
    )

    acquired = acquired_items[0]
    failure_rows = read_jsonl(repo_root() / "artifacts/reports/run-public-quarantine-acquisition-failures.jsonl")

    assert manifest["status"] == "partial"
    assert manifest["failure_count"] == 1
    assert manifest["quarantined_count"] == 1
    assert manifest["retry_count"] == 1
    assert manifest["parser_failure_rate"] == 1.0
    assert manifest["corrupted_image_rate"] == 1.0
    assert acquired.acquisition_status == "quarantined"
    assert acquired.thumbnail_artifact_kind == "signal-json"
    assert failure_rows[0]["status"] == "quarantined"


def test_acquisition_enriches_watch_page_metadata_and_captions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    def watch_fetcher(_url: str) -> str:
        return WATCH_HTML

    def caption_fetcher(_url: str) -> str:
        return CAPTION_XML

    acquired_items, manifest = acquire_discovered_items(
        "run-public-enriched",
        [_item()],
        fetcher=lambda _url: b"fake-jpeg-binary",
        watch_page_fetcher=watch_fetcher,
        caption_fetcher=caption_fetcher,
    )

    acquired = acquired_items[0]
    transcript_path = repo_root() / acquired.transcript_path

    assert acquired.title == "Enriched orbital weather bulletin"
    assert acquired.description == "Detailed watch-page description."
    assert acquired.thumbnail_source_url == "https://img.youtube.com/vi/rss-item-1/maxresdefault.jpg"
    assert acquired.duration_seconds == 785
    assert acquired.view_count == 45678
    assert "Transcript enrichment" in acquired.transcript_excerpt
    assert "Transcript enrichment" in transcript_path.read_text(encoding="utf-8")
    assert manifest["watch_page_enrichment_rate"] == 1.0
    assert manifest["caption_enrichment_rate"] == 1.0
