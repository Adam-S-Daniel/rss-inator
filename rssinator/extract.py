"""Turn a fetched page into feed items.

Each extractor is a pure function of the page text and its URL, so tests run
against saved fixtures with no network.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import datetime, timezone
from urllib.parse import urljoin
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bs4 import BeautifulSoup, Tag

from rssinator.feed import Item

MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
DATE_RE = re.compile(rf"\b(?:{MONTHS})[a-z]*\.? \d{{1,2}}(?:st|nd|rd|th)?,? \d{{4}}\b|\b\d{{4}}-\d{{2}}-\d{{2}}\b")
MONTH_RE = re.compile(rf"^(?:{MONTHS})[a-z]* \d{{4}}$")
HEADINGS = ["h1", "h2", "h3", "h4", "h5"]
EXCERPT_CHARS = 280


class ExtractError(ValueError):
    """The page no longer has the structure the extractor expects."""


def parse_date(text: str) -> datetime:
    """Parse 'Oct 3, 2026', 'October 3rd, 2026', '2026-10-03' or an ISO timestamp to an aware datetime."""
    text = text.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        cleaned = re.sub(r"(\d)(st|nd|rd|th)", r"\1", text).replace(".", "").replace(",", "")
        parts = cleaned.split()
        if len(parts) != 3:
            raise ExtractError(f"unrecognized date {text!r}") from None
        parts[0] = parts[0][:3]
        parsed = datetime.strptime(" ".join(parts), "%b %d %Y")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "svg", "noscript"]):
        tag.decompose()
    return soup


def _text(tag: Tag | None) -> str:
    return tag.get_text(" ", strip=True) if tag else ""


def excerpt(text: str, limit: int = EXCERPT_CHARS) -> str:
    """Cut text to at most limit characters at a word boundary."""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"


def release_notes(html: str, url: str) -> list[Item]:
    """Intercom help-center article where each <h3> is a date and the blocks under it are that day's notes."""
    soup = _soup(html)
    article = soup.find("article")
    if article is None:
        raise ExtractError("no <article> element")
    items = []
    for h3 in article.find_all("h3"):
        heading = _text(h3)
        if not DATE_RE.fullmatch(heading):
            continue
        parts = []
        block = h3.find_parent("div") or h3
        for sibling in block.find_next_siblings():
            if sibling.find(["h2", "h3"]) or sibling.name in ("h2", "h3"):
                break
            parts.append(str(sibling))
        body = BeautifulSoup("".join(parts), "lxml")
        first = _text(body.find(["b", "strong"])) or _text(body)[:120]
        link = f"{url}#{h3['id']}" if h3.get("id") else url
        items.append(
            Item(
                title=f"{heading}: {first}" if first else heading,
                link=link,
                published=parse_date(heading),
                # An excerpt, not the full notes: the feed is public, so it links to the text instead of copying it.
                summary=excerpt(_text(body)),
            )
        )
    return items


def dated_cards(
    html: str,
    url: str,
    link_pattern: str,
    skip_link_class: str = "",
    dates_are_events: bool = False,
) -> list[Item]:
    """Listing page of cards: each card has one link matching link_pattern and a date.

    A card is the largest ancestor of a matching link that holds no other
    matching link. The date is the first <time> in it, else the first date-like
    text. With dates_are_events the date is an event date, not a publish date,
    so it goes in the summary and the item has no pubDate.
    """
    soup = _soup(html)
    pattern = re.compile(link_pattern)

    def target(anchor: Tag) -> str | None:
        if skip_link_class and any(skip_link_class in c for c in anchor.get("class", [])):
            return None
        href = urljoin(url, anchor.get("href", "")).split("#")[0]
        return href if pattern.search(href) else None

    items: dict[str, Item] = {}
    for anchor in soup.find_all("a", href=True):
        link = target(anchor)
        if not link or link in items:
            continue
        node: Tag | None = anchor
        found: tuple[Tag, str] | None = None
        while node is not None and node.name != "[document]":
            others = {target(a) for a in node.find_all("a", href=True)} - {None, link}
            if others:
                break
            time_tag = node if node.name == "time" else node.find("time")
            if time_tag is not None and (time_tag.get("datetime") or DATE_RE.search(time_tag.get_text())):
                found = (node, time_tag.get("datetime") or DATE_RE.search(time_tag.get_text()).group(0))
                break
            match = DATE_RE.search(node.get_text(" "))
            if match:
                found = (node, match.group(0))
                break
            node = node.parent
        if found is None:
            continue
        card, date_text = found
        title = _text(card.find(HEADINGS)) or _text(anchor)
        if not title:
            image = anchor.find("img")
            title = image.get("alt", "") if image else ""
        if not title:
            continue
        date = parse_date(date_text)
        if dates_are_events:
            items[link] = Item(title=title, link=link, summary=f"Event date: {date:%B %-d, %Y}")
        else:
            items[link] = Item(title=title, link=link, published=date)
    return list(items.values())


def month_toc(html: str, url: str) -> list[Item]:
    """Index with month headings ('October 2026') followed by that month's article links."""
    soup = _soup(html)
    toc = soup.select_one(".toc")
    if toc is None:
        raise ExtractError("no .toc element")
    month: datetime | None = None
    items = []
    for child in toc.find_all(recursive=False):
        text = _text(child)
        if child.name != "a" and MONTH_RE.match(text):
            month = datetime.strptime(text[:3] + text[-5:], "%b %Y").replace(tzinfo=timezone.utc)
            continue
        if child.name == "a" and child.get("href"):
            title = _text(child.find(HEADINGS)) or text
            summary = _text(child.select_one(".description"))
            items.append(Item(title=title, link=urljoin(url, child["href"]), published=month, summary=summary))
    return items


SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def sitemap(xml: str, url: str) -> list[Item]:
    """sitemap.xml whose <lastmod> is the publish date. Titles come from the slug until enriched."""
    root = ET.fromstring(xml)
    items = []
    for entry in root.findall("sm:url", SITEMAP_NS):
        loc = (entry.findtext("sm:loc", "", SITEMAP_NS) or "").strip()
        lastmod = entry.findtext("sm:lastmod", "", SITEMAP_NS).strip()
        slug = loc.rstrip("/").rsplit("/", 1)[-1]
        if not loc or not lastmod or loc.rstrip("/") == url.rstrip("/") or "." in slug:
            continue
        title = slug.replace("-", " ").capitalize()
        items.append(Item(title=title, link=loc, published=parse_date(lastmod)))
    return items


def page_title(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    meta = soup.find("meta", property="og:title")
    if meta and meta.get("content"):
        return meta["content"].strip()
    return _text(soup.title)


def _walk(value: object) -> Iterator[dict]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def luma(html: str, url: str) -> list[Item]:
    """Luma calendar or place page: events live in the Next.js __NEXT_DATA__ JSON."""
    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", id="__NEXT_DATA__")
    if script is None or not script.string:
        raise ExtractError("no __NEXT_DATA__ script")
    data = json.loads(script.string)
    items = {}
    for event in _walk(data):
        api_id = event.get("api_id")
        if not (isinstance(api_id, str) and api_id.startswith("evt-")):
            continue
        if not all(isinstance(event.get(k), str) for k in ("name", "start_at", "url")):
            continue
        start = parse_date(event["start_at"])
        try:
            start = start.astimezone(ZoneInfo(event.get("timezone") or "UTC"))
        except (ZoneInfoNotFoundError, ValueError):
            pass
        place = (event.get("geo_address_info") or {}).get("city_state") or (
            "Online" if event.get("location_type") == "online" else ""
        )
        when = f"{start:%a, %b %-d, %Y %-I:%M %p} {start.tzname() or ''}".strip()
        summary = " · ".join(p for p in (when, place) if p)
        items[api_id] = Item(
            title=f"{event['name']} ({start:%b %-d})",
            link=urljoin("https://luma.com/", event["url"]),
            summary=summary,
            guid=api_id,
        )
    return list(items.values())
