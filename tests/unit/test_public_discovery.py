from truthlens_data_pipeline import PublicSourceSpec, build_discovery_run


RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
  <title>Example Channel</title>
  <entry>
    <id>yt:video:abc123</id>
    <title>Breaking launch update confirmed</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abc123" />
    <published>2026-03-22T12:00:00+00:00</published>
    <media:group>
      <media:thumbnail url="https://img.youtube.com/vi/abc123/hqdefault.jpg" />
      <media:description>Official update text with #launch and #space tags.</media:description>
    </media:group>
  </entry>
  <entry>
    <id>yt:video:def456</id>
    <title>Weekly mission recap</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=def456" />
    <published>2026-03-21T12:00:00+00:00</published>
    <media:group>
      <media:description>Measured recap with low drama and clear sourcing.</media:description>
    </media:group>
  </entry>
</feed>
"""


def test_public_rss_discovery_builds_manifest_and_items() -> None:
    source = PublicSourceSpec(
        source_id="example-channel",
        source_url="https://www.youtube.com/feeds/videos.xml?channel_id=example",
        channel_name="Example Channel",
    )

    run_id, manifest, items = build_discovery_run(
        "discovery-public-test",
        public_sources=[source],
        fetcher=lambda _url: RSS_FIXTURE,
    )

    assert run_id == "discovery-public-test"
    assert manifest.coverage_count == 1
    assert manifest.records[0].status == "collected"
    assert manifest.records[0].source_url == source.source_url
    assert len(items) == 2
    assert items[0].source_url == "https://www.youtube.com/watch?v=abc123"
    assert items[0].thumbnail_url == "https://img.youtube.com/vi/abc123/hqdefault.jpg"
    assert items[0].risk_seed > items[1].risk_seed
    assert "#launch" in items[0].hashtags


def test_public_rss_discovery_marks_failed_sources() -> None:
    source = PublicSourceSpec(
        source_id="broken-channel",
        source_url="https://www.youtube.com/feeds/videos.xml?channel_id=broken",
        channel_name="Broken Channel",
    )

    _run_id, manifest, items = build_discovery_run(
        "discovery-public-failed",
        public_sources=[source],
        fetcher=lambda _url: "<feed>",
    )

    assert items == []
    assert manifest.records[0].status == "failed"
