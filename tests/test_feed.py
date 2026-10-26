import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from rssinator.feed import Feed, Item, sort_items, to_rss

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


def test_sort_items_dedupes_and_orders_newest_first() -> None:
    old = Item("old", "https://example.com/1", datetime(2026, 1, 1, tzinfo=timezone.utc))
    new = Item("new", "https://example.com/2", datetime(2026, 2, 1, tzinfo=timezone.utc))
    undated = Item("undated", "https://example.com/3")
    assert [i.title for i in sort_items([old, new, old, undated], 10)] == ["new", "old", "undated"]
    assert [i.title for i in sort_items([old, new], 1)] == ["new"]


def test_sort_items_keeps_page_order_when_nothing_is_dated() -> None:
    items = [Item("b", "https://example.com/b"), Item("a", "https://example.com/a")]
    assert sort_items(items, 10) == items


def test_to_rss_is_valid_rss_with_escaped_html() -> None:
    feed = Feed(
        slug="s",
        title="Example & co",
        site_url="https://example.com/",
        description="d",
        items=(
            Item("One", "https://example.com/1", datetime(2026, 3, 4, tzinfo=timezone.utc), "<p>Hi</p>"),
            Item("Two", "https://example.com/2", guid="evt-2"),
        ),
    )
    root = ET.fromstring(to_rss(feed, "https://example.net/s.xml", NOW))
    channel = root.find("channel")
    assert channel.findtext("title") == "Example & co"
    first, second = channel.findall("item")
    assert first.findtext("pubDate") == "Wed, 04 Mar 2026 00:00:00 +0000"
    assert first.findtext("description") == "<p>Hi</p>"
    assert first.find("guid").get("isPermaLink") == "true"
    assert second.find("pubDate") is None
    assert second.findtext("guid") == "evt-2"
    assert second.find("guid").get("isPermaLink") == "false"
