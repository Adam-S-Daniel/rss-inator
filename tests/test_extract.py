import json
from datetime import datetime, timezone

import pytest

from rssinator import extract


def test_parse_date_formats() -> None:
    expected = datetime(2026, 3, 4, tzinfo=timezone.utc)
    assert extract.parse_date("Mar 4, 2026") == expected
    assert extract.parse_date("March 4th, 2026") == expected
    assert extract.parse_date("Sept. 4, 2026").month == 9
    assert extract.parse_date("2026-03-04") == expected
    assert extract.parse_date("2026-03-04T12:00:00.000Z").hour == 12


def test_parse_date_rejects_garbage() -> None:
    with pytest.raises(extract.ExtractError):
        extract.parse_date("next Tuesday")


RELEASE_NOTES = """
<html><body><article>
  <div><h2 id="m1">March 2026</h2></div>
  <div><h3 id="d2">March 4, 2026</h3></div>
  <div><p><b>Widgets for everyone</b></p></div>
  <div><p>Widgets now ship to every plan.</p></div>
  <div><h3 id="d1">March 1, 2026</h3></div>
  <div><p>Smaller fix.</p></div>
  <div><h2 id="m0">February 2026</h2></div>
  <div><h3 id="x">Not a date</h3></div>
</article></body></html>
"""


def test_release_notes_one_item_per_dated_h3() -> None:
    items = extract.release_notes(RELEASE_NOTES, "https://example.com/notes")
    assert [i.link for i in items] == ["https://example.com/notes#d2", "https://example.com/notes#d1"]
    assert items[0].title == "March 4, 2026: Widgets for everyone"
    assert "Widgets now ship" in items[0].summary
    assert "Smaller fix" not in items[0].summary
    assert items[1].title == "March 1, 2026: Smaller fix."
    assert items[1].published == datetime(2026, 3, 1, tzinfo=timezone.utc)


def test_release_notes_without_article_is_an_error() -> None:
    with pytest.raises(extract.ExtractError):
        extract.release_notes("<html><body><p>moved</p></body></html>", "https://example.com/notes")


CARDS = """
<html><body>
<nav><a href="/news/first">First post</a></nav>
<div class="grid">
  <article>
    <p><a class="TopicLink-x" href="/news/category">Category</a></p>
    <time>Oct 2, 2026</time>
    <a href="/news/first"><h3>First post</h3></a>
  </article>
  <a class="card" href="/news/second">
    <span>Article</span><span>Sep 30, 2026</span>
    <h3>Second post</h3>
  </a>
  <article><a href="/news/undated"><h3>No date here</h3></a></article>
</div>
<a href="https://other.example.net/news/x">Elsewhere, Oct 1, 2026</a>
</body></html>
"""


def test_dated_cards_pairs_each_link_with_its_card_date() -> None:
    items = extract.dated_cards(
        CARDS, "https://example.com/news", r"^https://example\.com/news/[^/]+$", skip_link_class="TopicLink"
    )
    assert [(i.title, i.link, i.published.day) for i in items] == [
        ("First post", "https://example.com/news/first", 2),
        ("Second post", "https://example.com/news/second", 30),
    ]


def test_dated_cards_without_skip_class_loses_cards_with_category_links() -> None:
    # The category link is a second match inside the card, so the card is ambiguous and dropped.
    items = extract.dated_cards(CARDS, "https://example.com/news", r"^https://example\.com/news/[^/]+$")
    assert [i.link for i in items] == ["https://example.com/news/second"]


def test_dated_cards_event_dates_go_in_summary() -> None:
    items = extract.dated_cards(
        CARDS, "https://example.com/news", r"/news/second$", dates_are_events=True
    )
    assert items[0].published is None
    assert items[0].summary == "Event date: September 30, 2026"


TOC = """
<html><body><div class="toc">
  <div class="date">October 2026</div>
  <a class="note" href="2026/alpha/"><h3>Alpha</h3><div class="description">About alpha.</div></a>
  <div class="date">August 2026</div>
  <a class="paper" href="2026/beta/"><h3>Beta</h3><div class="byline">Someone</div></a>
</div></body></html>
"""


def test_month_toc_dates_items_by_heading_month() -> None:
    items = extract.month_toc(TOC, "https://example.com/")
    assert [(i.title, i.link, i.published.month, i.summary) for i in items] == [
        ("Alpha", "https://example.com/2026/alpha/", 10, "About alpha."),
        ("Beta", "https://example.com/2026/beta/", 8, ""),
    ]


SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://example.com</loc><lastmod>2026-10-13T20:10:37.738Z</lastmod></url>
<url><loc>https://example.com/a-first-essay</loc><lastmod>2026-09-16T00:00:00.000Z</lastmod></url>
<url><loc>https://example.com/feed.xml</loc><lastmod>2026-09-16T00:00:00.000Z</lastmod></url>
<url><loc>https://example.com/no-date</loc></url>
</urlset>"""


def test_sitemap_skips_home_files_and_undated() -> None:
    items = extract.sitemap(SITEMAP, "https://example.com/sitemap.xml".rsplit("/", 1)[0])
    assert [(i.title, i.link) for i in items] == [("A first essay", "https://example.com/a-first-essay")]
    assert items[0].published == datetime(2026, 9, 16, tzinfo=timezone.utc)


def test_page_title_prefers_og_title() -> None:
    page = '<html><head><title>Site | Post</title><meta property="og:title" content="Post"></head></html>'
    assert extract.page_title(page) == "Post"
    assert extract.page_title("<html><head><title>Only</title></head></html>") == "Only"


def _luma_page(data: object) -> str:
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'


def test_luma_finds_events_anywhere_in_page_data() -> None:
    event = {
        "api_id": "evt-abc",
        "name": "Example meetup",
        "start_at": "2026-10-28T21:30:00.000Z",
        "timezone": "America/New_York",
        "url": "example-meetup",
        "geo_address_info": {"city_state": "Example City, EX"},
    }
    page = _luma_page({"props": {"pageProps": {"initialData": {"data": {
        "featured_items": [{"api_id": "calev-1", "event": event}],
        "events": [{"api_id": "evt-abc", "event": event}],
        "calendar": {"api_id": "cal-1", "name": "Not an event"},
    }}}}})
    items = extract.luma(page, "https://example.com/cal")
    assert len(items) == 1
    item = items[0]
    assert item.title == "Example meetup (Oct 28)"
    assert item.link == "https://luma.com/example-meetup"
    assert item.guid == "evt-abc"
    assert item.published is None
    assert item.summary == "Wed, Oct 28, 2026 5:30 PM EDT · Example City, EX"


def test_luma_without_next_data_is_an_error() -> None:
    with pytest.raises(extract.ExtractError):
        extract.luma("<html></html>", "https://example.com/cal")
