"""The feeds this repo builds, and the sites that already publish their own."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial

from rssinator import extract
from rssinator.feed import Item


@dataclass(frozen=True)
class Source:
    slug: str
    title: str
    site_url: str
    extractor: Callable[[str, str], list[Item]]
    fetch_url: str = ""
    limit: int = 50
    # Fetch each item's page for its real title (for extractors that can only guess one).
    fetch_titles: int = 0
    description: str = field(default="")

    @property
    def url(self) -> str:
        return self.fetch_url or self.site_url


SOURCES: tuple[Source, ...] = (
    Source(
        slug="claude-release-notes",
        title="Claude release notes",
        site_url="https://support.claude.com/en/articles/12138966-release-notes",
        extractor=extract.release_notes,
    ),
    Source(
        slug="anthropic-news",
        title="Anthropic news",
        site_url="https://www.anthropic.com/news",
        extractor=partial(
            extract.dated_cards,
            # Model launches link to top-level pages such as /claude-opus-5-5.
            link_pattern=r"^https://www\.anthropic\.com/(news/[^/?]+|claude-[^/?]+)$",
            # Category links ("Announcements", "Product") sit inside every card.
            skip_link_class="TopicLink",
        ),
    ),
    Source(
        slug="anthropic-research",
        title="Anthropic research",
        site_url="https://www.anthropic.com/research",
        extractor=partial(extract.dated_cards, link_pattern=r"^https://www\.anthropic\.com/research/[^/?]+$"),
    ),
    Source(
        slug="anthropic-engineering",
        title="Anthropic engineering",
        site_url="https://www.anthropic.com/engineering",
        # Engineering posts now live under /research/ but are listed here.
        extractor=partial(
            extract.dated_cards, link_pattern=r"^https://www\.anthropic\.com/(engineering|research)/[^/?]+$"
        ),
    ),
    Source(
        slug="claude-blog",
        title="Claude blog",
        site_url="https://claude.com/blog",
        fetch_url="https://claude.com/resources/articles",
        extractor=partial(
            extract.dated_cards, link_pattern=r"^https://claude\.com/(blog|resources/articles)/[^/?]+$"
        ),
    ),
    Source(
        slug="anthropic-alignment",
        title="Anthropic Alignment Science blog",
        site_url="https://alignment.anthropic.com/",
        extractor=extract.month_toc,
    ),
    Source(
        slug="mustafa-suleyman",
        title="Mustafa Suleyman: writing",
        site_url="https://mustafa-suleyman.ai/",
        fetch_url="https://mustafa-suleyman.ai/sitemap.xml",
        extractor=extract.sitemap,
        limit=10,
        fetch_titles=10,
    ),
    Source(
        slug="luma-dc",
        title="Luma: Washington, DC events",
        site_url="https://luma.com/dc",
        extractor=extract.luma,
    ),
    Source(
        slug="luma-dc2",
        title="Luma: DC Data & AI Events",
        site_url="https://luma.com/DC2",
        extractor=extract.luma,
    ),
    Source(
        slug="ai-tinkerers-dc",
        title="AI Tinkerers DC",
        site_url="https://dc.aitinkerers.org/",
        extractor=partial(
            extract.dated_cards,
            link_pattern=r"^https://dc\.aitinkerers\.org/p/[^/?]+$",
            dates_are_events=True,
        ),
    ),
)

# Listed in the OPML so one import covers everything; these sites already publish a feed.
NATIVE_FEEDS: tuple[tuple[str, str, str], ...] = (
    ("Chips and Cheese", "https://chipsandcheese.com/feed", "https://chipsandcheese.com"),
    # openai.com/news/ai-futures/ refuses automated requests (403), so this is
    # OpenAI's own all-news feed; it has no AI Futures category to filter on.
    ("OpenAI News", "https://openai.com/news/rss.xml", "https://openai.com/news/"),
)
