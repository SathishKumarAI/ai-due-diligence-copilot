---
title: Docs kit
description: What this service does, why, and how "done" is measured. Tier: Core.
sidebar_position: 1
---

# Docs — AI Due Diligence Copilot

> Source of truth for behaviour, design, and the bar for "done". Read before changing code.

## Operating model

Vibecoding gets a prototype fast; the gap to production is **structure that keeps a
fast agent from solving the wrong problem or shipping something unsafe.** Each doc
does one of four jobs:

| Job | Documents | What it buys |
|---|---|---|
| **Steer the agent** | [`../CLAUDE.md`](../CLAUDE.md), [`../GLOSSARY.md`](../GLOSSARY.md) | every session starts knowing the conventions |
| **Define the work** | [`BACKLOG.md`](BACKLOG.md), [`specs/`](specs/), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`adr/`](adr/) | decide *what* and *why* before code |
| **Make "done" measurable** | [`DEFINITION-OF-DONE.md`](DEFINITION-OF-DONE.md), [`TEST-STRATEGY.md`](TEST-STRATEGY.md), CI | "works" = tests + eval gate pass |
| **Enforce safety** | [`SECURITY.md`](SECURITY.md), auth, secrets policy | blast radius bounded by rules, not hope |

## The core loop: explore → plan → implement → verify

1. **Explore** the code + the relevant [spec](specs/). No edits.
2. **Plan** the approach and files to touch. Review the plan, not the diff.
3. **Implement** in small steps, following [`CLAUDE.md`](../CLAUDE.md).
4. **Verify** with evidence (test output), against [Definition of Done](DEFINITION-OF-DONE.md).

## Priority tags

⭐ **Core** (worth it solo) · ➕ **Growing** (real users/team) · 🏢 **Heavy** (regulated).
This project builds Core + targeted Growing; deferred docs are listed in
[`DOC-CATALOG.md`](DOC-CATALOG.md).

## Map

| Doc | Tier | Purpose |
|-----|------|---------|
| [`BACKLOG.md`](BACKLOG.md) | ⭐ | prioritized features → link to specs |
| [`specs/F01..F15`](specs/) | ⭐ | one Feature Spec per feature (behaviour source of truth) |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | ⭐ | system shape, data flow |
| [`adr/`](adr/) | ➕ | key decisions + rationale |
| [`DEFINITION-OF-DONE.md`](DEFINITION-OF-DONE.md) | ⭐ | the bar every change clears |
| [`TEST-STRATEGY.md`](TEST-STRATEGY.md) | ⭐ | what we test + the offline-first rule |
| [`SECURITY.md`](SECURITY.md) | ➕ | secrets, auth, prompt-injection, data |
| [`RUNBOOK.md`](RUNBOOK.md) | ➕ | operate / deploy / troubleshoot |
| [`FRONTEND.md`](FRONTEND.md) | ➕ | the non-technical UI approach + options |
| [`CHANGELOG-STRATEGY.md`](CHANGELOG-STRATEGY.md) | ➕ | how changes reach non-technical users |
| [`DOC-CATALOG.md`](DOC-CATALOG.md) | ⭐ | which docs we built vs deferred, and why |
