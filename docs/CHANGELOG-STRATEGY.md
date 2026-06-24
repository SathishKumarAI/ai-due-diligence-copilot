---
title: Changelog strategy
description: How changes reach non-technical users as they happen. Tier: Growing.
sidebar_position: 10
---

# Changelog strategy — showing changes to non-technical users

> Two audiences, two registers, one workflow. Engineers read a technical changelog;
> everyone else reads plain-language release notes **inside the app**.

## Context / Why

"View the changes as they happen" means a non-engineer should be able to see, in
words they understand, what's new — without reading commits, diffs, or a markdown
file on GitHub.

## The three surfaces

| Surface | Audience | Register | Source |
|---------|----------|----------|--------|
| [`CHANGELOG.md`](../CHANGELOG.md) | engineers / contributors | technical, Keep-a-Changelog | hand-maintained per PR |
| **GitHub Releases** | public, dated feed | plain language | published per version tag |
| **What's New page** (`/whats-new`) | non-technical app users | plain language | reads GitHub Releases live |

The app's What's New page fetches GitHub Releases via the public API, so a published
release **appears in the product automatically** — no redeploy needed.

## Workflow (per release)

1. During work, add entries under `## [Unreleased]` in `CHANGELOG.md`.
2. To ship: move them under a new `## [x.y.z] — DATE` heading; tag `vx.y.z`.
3. `gh release create vx.y.z --notes "<plain-language summary>"` — write the notes for
   a non-technical reader ("You can now ask follow-up questions" — not
   "added conversation memory to RagEngine").
4. The What's New page shows it within its 5-minute cache window.

## Writing plain-language notes

- Lead with the user benefit, not the implementation.
- One bullet per visible change; skip internal refactors.
- Avoid identifiers and acronyms; if you must, define them.

## Other ways (considered)

- **In-app toast / "new" badge** on first visit after a release — nice for "as they
  happen"; deferred (P2).
- **RSS/Atom from GitHub Releases** — for users who want to subscribe; GitHub already
  exposes `releases.atom`.
- **Email release notes** — only worth it with a real user base.
