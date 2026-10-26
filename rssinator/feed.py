"""Feed items and RSS 2.0 serialization."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime

ATOM_NS = "http://www.w3.org/2005/Atom"


@dataclass(frozen=True)
class Item:
    title: str
    link: str
    published: datetime | None = None
    summary: str = ""
    guid: str = ""

    @property
    def id(self) -> str:
        return self.guid or self.link


@dataclass(frozen=True)
class Feed:
    slug: str
    title: str
    site_url: str
    description: str
    items: tuple[Item, ...]


def sort_items(items: list[Item], limit: int) -> list[Item]:
    """Drop duplicate ids, then put dated items newest first, keeping page order otherwise."""
    seen: set[str] = set()
    unique = []
    for item in items:
        if item.id not in seen:
            seen.add(item.id)
            unique.append(item)
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    if any(i.published for i in unique):
        unique.sort(key=lambda i: i.published or epoch, reverse=True)
    return unique[:limit]


def to_rss(feed: Feed, self_url: str, now: datetime) -> bytes:
    ET.register_namespace("atom", ATOM_NS)
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = feed.title
    ET.SubElement(channel, "link").text = feed.site_url
    ET.SubElement(channel, "description").text = feed.description
    ET.SubElement(channel, f"{{{ATOM_NS}}}link", href=self_url, rel="self", type="application/rss+xml")
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(now)
    ET.SubElement(channel, "generator").text = "rss-inator"
    for item in feed.items:
        el = ET.SubElement(channel, "item")
        ET.SubElement(el, "title").text = item.title
        ET.SubElement(el, "link").text = item.link
        ET.SubElement(el, "guid", isPermaLink="true" if item.id == item.link else "false").text = item.id
        if item.published:
            ET.SubElement(el, "pubDate").text = format_datetime(item.published)
        if item.summary:
            ET.SubElement(el, "description").text = item.summary
    ET.indent(rss)
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True) + b"\n"
