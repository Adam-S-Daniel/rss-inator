# rss-inator
Creates RSS feeds for sites that don't publish one, so they can be followed in
NetNewsWire (or any feed reader).

An hourly GitHub Actions run ([`feeds.yml`](.github/workflows/feeds.yml))
scrapes each site and publishes the feeds to GitHub Pages at
`https://adam-s-daniel.github.io/rss-inator/`.

## Subscribe

Import every feed at once in NetNewsWire with **File → Import Subscriptions**
and the OPML file: `https://adam-s-daniel.github.io/rss-inator/feeds.opml`.
The index page at the same address lists each feed and whether its last
build succeeded.

| Feed | Source |
| --- | --- |
| `claude-release-notes.xml` | https://support.claude.com/en/articles/12138966-release-notes |
| `anthropic-news.xml` | https://www.anthropic.com/news |
| `anthropic-research.xml` | https://www.anthropic.com/research |
| `anthropic-engineering.xml` | https://www.anthropic.com/engineering |
| `claude-blog.xml` | https://claude.com/blog |
| `anthropic-alignment.xml` | https://alignment.anthropic.com |
| `mustafa-suleyman.xml` | https://mustafa-suleyman.ai |
| `luma-dc.xml` | https://luma.com/dc |
| `luma-dc2.xml` | https://luma.com/DC2 |
| `ai-tinkerers-dc.xml` | https://dc.aitinkerers.org |

Because the site is public, feeds link to the original rather than copy it:
items carry a title, date, link and at most a short excerpt, and the index page
is marked `noindex`.

Event feeds (Luma, AI Tinkerers) carry the event date in the title or
summary rather than as the post date, so the reader shows them when they
first appear.

Sources that need no generated feed, also in the OPML:

- **Chips and Cheese** already publishes https://chipsandcheese.com/feed.
- **OpenAI AI Futures** (https://openai.com/news/ai-futures/) refuses
  automated requests, so the OPML has OpenAI's own all-news feed,
  https://openai.com/news/rss.xml, instead. It has no AI Futures category to
  filter on.

Not supported: **LinkedIn profiles**. LinkedIn requires a signed-in session
and blocks automated access.

## One-time setup

Pages must be switched on once: **Settings → Pages → Build and deployment →
Source: GitHub Actions**. Pages on a private repository needs a paid GitHub
plan, and the published site is public either way.

## Develop

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q tests
python3 -m rssinator.build --out site --base-url https://adam-s-daniel.github.io/rss-inator/
```

Add a site by adding a `Source` to [`rssinator/sources.py`](rssinator/sources.py)
with one of the extractors in [`rssinator/extract.py`](rssinator/extract.py).
When a site changes its layout and its extractor finds nothing, that feed keeps
its last published copy and the run logs a warning.
