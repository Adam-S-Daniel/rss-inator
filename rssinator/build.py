"""Build every feed into a directory that GitHub Pages serves.

    python -m rssinator.build --out site --base-url https://example.github.io/rss-inator/

A source that fails keeps its previously published feed (fetched from
--base-url), so one site changing its layout never empties a feed.
"""

from __future__ import annotations

import argparse
import dataclasses
import html
import logging
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from rssinator.extract import ExtractError, page_title
from rssinator.feed import Feed, sort_items, to_rss
from rssinator.sources import NATIVE_FEEDS, SOURCES, Source

USER_AGENT = "rss-inator/1.0 (+https://github.com/Adam-S-Daniel/rss-inator)"
log = logging.getLogger("rssinator")


def fetch(url: str, timeout: float = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def build_feed(source: Source, now: datetime, base_url: str) -> bytes:
    items = sort_items(source.extractor(fetch(source.url), source.url), source.limit)
    if not items:
        raise ExtractError("no items found")
    if source.fetch_titles:
        enriched = []
        for index, item in enumerate(items):
            if index < source.fetch_titles:
                try:
                    item = dataclasses.replace(item, title=page_title(fetch(item.link)) or item.title)
                except (urllib.error.URLError, TimeoutError) as error:
                    log.warning("%s: kept guessed title for %s (%s)", source.slug, item.link, type(error).__name__)
            enriched.append(item)
        items = enriched
    feed = Feed(
        slug=source.slug,
        title=source.title,
        site_url=source.site_url,
        description=source.description or f"Generated from {source.site_url}",
        items=tuple(items),
    )
    return to_rss(feed, f"{base_url}{source.slug}.xml", now)


def opml(base_url: str) -> bytes:
    root = ET.Element("opml", version="2.0")
    ET.SubElement(ET.SubElement(root, "head"), "title").text = "rss-inator feeds"
    body = ET.SubElement(root, "body")
    for source in SOURCES:
        ET.SubElement(
            body, "outline", type="rss", text=source.title, title=source.title,
            xmlUrl=f"{base_url}{source.slug}.xml", htmlUrl=source.site_url,
        )
    for title, feed_url, site_url in NATIVE_FEEDS:
        ET.SubElement(body, "outline", type="rss", text=title, title=title, xmlUrl=feed_url, htmlUrl=site_url)
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def index_page(base_url: str, status: dict[str, str], now: datetime) -> str:
    rows = "\n".join(
        f'<li><a href="{s.slug}.xml">{html.escape(s.title)}</a> '
        f'from <a href="{html.escape(s.site_url)}">{html.escape(s.site_url)}</a> ({status[s.slug]})</li>'
        for s in SOURCES
    )
    native = "\n".join(
        f'<li><a href="{html.escape(u)}">{html.escape(t)}</a> (published by the site)</li>' for t, u, _ in NATIVE_FEEDS
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>rss-inator feeds</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"></head>
<body><h1>rss-inator feeds</h1>
<p>Import every feed at once: <a href="feeds.opml">{html.escape(base_url)}feeds.opml</a></p>
<ul>
{rows}
{native}
</ul>
<p>Built {now:%Y-%m-%d %H:%M} UTC.</p></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base-url", required=True, help="Public URL the --out directory is served from")
    parser.add_argument("--only", action="append", default=[], help="Build only this slug (repeatable)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    base_url = args.base_url.rstrip("/") + "/"
    args.out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    status: dict[str, str] = {}
    for source in SOURCES:
        if args.only and source.slug not in args.only:
            continue
        target = args.out / f"{source.slug}.xml"
        try:
            target.write_bytes(build_feed(source, now, base_url))
            status[source.slug] = "updated"
            log.info("%s: updated", source.slug)
            continue
        except (urllib.error.URLError, TimeoutError, ExtractError, ET.ParseError) as error:
            log.warning("%s: build failed (%s: %s)", source.slug, type(error).__name__, error)
        try:
            target.write_text(fetch(f"{base_url}{source.slug}.xml"), encoding="utf-8")
            status[source.slug] = "stale: kept the last published copy"
            print(f"::warning::{source.slug}: build failed, kept the last published feed")
        except (urllib.error.URLError, TimeoutError) as error:
            status[source.slug] = "unavailable"
            print(f"::warning::{source.slug}: build failed and no published copy ({type(error).__name__})")
    if args.only:
        return 0 if all(v == "updated" for v in status.values()) else 1
    (args.out / "feeds.opml").write_bytes(opml(base_url))
    (args.out / "index.html").write_text(index_page(base_url, status, now), encoding="utf-8")
    # Fail only when nothing at all could be built, so one broken site never blocks the others.
    return 0 if any(v == "updated" for v in status.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
