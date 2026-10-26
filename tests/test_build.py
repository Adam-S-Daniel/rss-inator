import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from rssinator import build
from rssinator.feed import Item
from rssinator.sources import SOURCES, Source

BASE = "https://example.net/feeds/"


def _fake_fetch(pages: dict[str, str]):
    def fetch(url: str, timeout: float = 30) -> str:
        if url in pages:
            return pages[url]
        raise urllib.error.URLError("offline")

    return fetch


def _one_source(monkeypatch: pytest.MonkeyPatch, extractor) -> Source:
    source = Source(slug="demo", title="Demo", site_url="https://example.com/", extractor=extractor)
    monkeypatch.setattr(build, "SOURCES", (source,))
    monkeypatch.setattr(build, "NATIVE_FEEDS", (("Native", "https://example.org/feed", "https://example.org/"),))
    return source


def test_build_writes_feed_opml_and_index(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _one_source(monkeypatch, lambda page, url: [Item(page, "https://example.com/1")])
    monkeypatch.setattr(build, "fetch", _fake_fetch({"https://example.com/": "Hello"}))
    assert build.main(["--out", str(tmp_path), "--base-url", BASE]) == 0
    feed = ET.parse(tmp_path / "demo.xml").getroot()
    assert feed.find("channel/item/title").text == "Hello"
    outlines = ET.parse(tmp_path / "feeds.opml").getroot().findall("body/outline")
    assert [o.get("xmlUrl") for o in outlines] == [f"{BASE}demo.xml", "https://example.org/feed"]
    index = (tmp_path / "index.html").read_text()
    assert "updated" in index
    assert '<meta name="robots" content="noindex, nofollow">' in index


def test_failed_source_keeps_last_published_copy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _one_source(monkeypatch, lambda page, url: [])
    monkeypatch.setattr(build, "fetch", _fake_fetch({"https://example.com/": "x", f"{BASE}demo.xml": "<rss/>"}))
    # The only source failed, so the run reports failure, but the old copy is still written.
    assert build.main(["--out", str(tmp_path), "--base-url", BASE]) == 1
    assert (tmp_path / "demo.xml").read_text() == "<rss/>"
    assert "stale" in (tmp_path / "index.html").read_text()


def test_fetch_titles_replaces_guessed_titles(monkeypatch: pytest.MonkeyPatch) -> None:
    source = Source(
        slug="demo", title="Demo", site_url="https://example.com/",
        extractor=lambda page, url: [Item("guess", "https://example.com/post")], fetch_titles=1,
    )
    monkeypatch.setattr(build, "fetch", _fake_fetch({
        "https://example.com/": "",
        "https://example.com/post": '<meta property="og:title" content="Real title">',
    }))
    rss = ET.fromstring(build.build_feed(source, build.datetime.now(build.timezone.utc), BASE))
    assert rss.find("channel/item/title").text == "Real title"


def test_every_source_has_a_unique_slug() -> None:
    slugs = [s.slug for s in SOURCES]
    assert len(slugs) == len(set(slugs))
