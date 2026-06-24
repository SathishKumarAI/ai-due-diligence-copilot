# Feature Spec — F15 Release notes / What's New

## Summary
Show non-technical users what changed, in plain language, inside the app — backed by
GitHub Releases and a maintained CHANGELOG.

## Problem / why
"View the changes as they happen" for a non-engineer means readable, dated updates in
the product — not commits or a markdown file.

## Users & context
App users on the `/whats-new` page; maintainers publishing releases.

## Behaviour (acceptance criteria)
- WHEN `/whats-new` loads THEN it lists releases newest-first with name, date, and
  plain-language notes.
- WHEN a new GitHub Release is published THEN it appears in the app within the cache
  window (~5 min) — no redeploy.
- WHEN there are no releases THEN a friendly message points to `CHANGELOG.md`.

## Rules / logic
- `web/lib/api.ts::fetchReleases` reads the public GitHub Releases API for the repo.
- `CHANGELOG.md` (Keep a Changelog) is the technical record; release notes are the
  plain-language register (see `docs/CHANGELOG-STRATEGY.md`).

## Out of scope (for now)
- In-app "new" badge/toast, email/RSS notifications (P2).

## Data touched
- Reads: GitHub Releases API. Writes: none.

## Edge cases
- GitHub API rate-limited/unavailable → empty list with the fallback message ·
  release with empty body → shows title/date only.

## Done when
- `/whats-new` renders releases (or the fallback); the release workflow in
  `CHANGELOG-STRATEGY.md` is documented.
