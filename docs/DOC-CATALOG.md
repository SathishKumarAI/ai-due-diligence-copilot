---
title: Document catalog & triage
description: Which docs this project builds vs defers, and why. Tier: Core (reference).
sidebar_position: 11
---

# Document catalog & triage

> Rule: **scale docs to the stakes.** This is a solo-built, production-ready portfolio
> service over synthetic data — so we build the ⭐ Core set + targeted ➕ Growing
> items, and explicitly defer 🏢 Heavy ones (recorded here so nothing is pretended).

## Built

| Doc | Tier | Location |
|-----|------|----------|
| CLAUDE.md (persistent memory) | ⭐ | `CLAUDE.md` |
| Glossary | ⭐ | `GLOSSARY.md` |
| Features list | ⭐ | `FEATURES.md` |
| Feature specs F01–F15 | ⭐ | `docs/specs/` |
| Backlog | ⭐ | `docs/BACKLOG.md` |
| Architecture | ⭐ | `docs/ARCHITECTURE.md` |
| ADRs | ➕ | `docs/adr/` |
| Definition of Done | ⭐ | `docs/DEFINITION-OF-DONE.md` |
| Test strategy | ⭐ | `docs/TEST-STRATEGY.md` |
| CI/CD | ⭐ | `.github/workflows/ci.yml` |
| Security policy | ➕ | `docs/SECURITY.md` |
| Runbook + env/config | ➕ | `docs/RUNBOOK.md` |
| Observability | ➕ | spec F09 + RUNBOOK |
| Frontend approach | ➕ | `docs/FRONTEND.md` |
| Changelog strategy | ➕ | `docs/CHANGELOG-STRATEGY.md` |
| README (front door) | ⭐ | `README.md`, `web/README.md` |
| Secrets / .env.example | ⭐ | `.env.example` |
| CONTRIBUTING | ➕ | `CONTRIBUTING.md` |
| CHANGELOG | ➕ | `CHANGELOG.md` |
| Code style | ⭐ | `pyproject.toml` (ruff) + CLAUDE.md |
| API contract | ➕ | auto-generated at `/docs`, `/openapi.json` |
| LICENSE | ⭐ | `LICENSE` (MIT) |

## Deferred (with reason)

| Doc | Tier | Why |
|-----|------|-----|
| PRD | ➕ | backlog + specs cover what/why at this scale |
| RFC | 🏢 | solo; ADRs suffice |
| Threat model | 🏢 | synthetic data, no PII/money |
| Privacy / compliance | 🏢 | no real personal data |
| Incident / DR / post-mortem | 🏢 | no uptime SLA yet |
| CODEOWNERS | 🏢 | solo |

> Promote a deferred doc the moment its trigger becomes real (real users, real PII,
> a team). A stale doc is worse than none.
