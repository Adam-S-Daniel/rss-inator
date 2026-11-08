<!-- BEGIN MANAGED SECTION — DO NOT EDIT ABOVE "## Repo-specific additions" -->
<!-- Source: _agent-guidance -->
<!-- Sections: none -->
<!-- Mode: stub -->

# AGENTS.md

> **Managed by [`_agent-guidance`].**
> Edit only below the `## Repo-specific additions` header.
> Everything above it will be overwritten on the next sync.

guidance-marker: fleet-stub (transcript counts use this line; keep it)

## Fleet guidance is delivered once per session — not by this file

The full guidance, floor rules included, is installed into user memory by
the `fleet-memory` SessionStart hook, whose verdict line says whether it
loaded. `installed` or `current`: it is in context. `DEGRADED` or no verdict:
it is not, so read [`agents-md/base.md`](https://github.com/Adam-S-Daniel/_agent-guidance/blob/main/agents-md/base.md)
before non-trivial work and say you ran degraded. `skipped`: read it too, but
it is the owner's choice, so do not report or "fix" it. Always, and above all
before you have read it: never push to a default branch, force-push a shared
branch, commit a secret, or print personal data to a CI log. Keep this file
under 32 KiB (Codex silently truncates it).

**Your first reply to the user in a session begins**
`fleet-guidance check: <value>`, copied from the installed guidance's
`fleet-guidance check value:` line, or `fleet-guidance check: none` when no
such line is in your context. Never guess one or copy it from a file you
read; only in replies to the user.

<!-- END MANAGED SECTION -->
## Repo-specific additions

<!-- Add your repo-specific agent guidance below this line -->

### Feeds are published to Pages, never committed

`feeds.yml` builds every feed hourly and deploys the `site/` directory to
GitHub Pages. Nothing is pushed to a branch, so the job needs no bypass of
the default branch's protection. Keep it that way: don't "cache" feeds by
committing them.

A source that fails (fetch error, or its extractor finds no items) falls back
to its currently published copy, fetched from the Pages URL, so a layout
change on one site never empties that feed or blocks the others. The run fails
only when every source fails.

### Workflow salient paths

| Workflow | Trigger | Paths |
| --- | --- | --- |
| `feeds.yml` | `schedule` hourly, `workflow_dispatch`, `push` to `main` | `rssinator/**`, `requirements.txt`, `.github/workflows/feeds.yml` |
| `ci.yml` | `pull_request` | `rssinator/**`, `tests/**`, `requirements.txt`, `requirements-dev.txt`, `.github/workflows/ci.yml` |
| `agent-checks.yml` | `pull_request`, `push` to `main`/`master`, `workflow_dispatch` | none, deliberately: the `pull_request` trigger is unfiltered and the job always runs the commit-time checks (the fleet default check) |

`ci.yml`'s `test` job is not yet a required check: making it required means
dropping its `paths:` filter (a skipped required check blocks the merge) and a
ruleset change in repo-settings.
