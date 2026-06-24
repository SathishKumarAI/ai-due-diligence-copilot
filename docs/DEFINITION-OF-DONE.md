---
title: Definition of Done
description: The shared bar every change clears before it's "done". Tier: Core.
sidebar_position: 5
---

# Definition of Done

> "Done" is not "the agent said so." A change is done when **all** of the following hold.

## Checklist

- [ ] **Spec exists / updated.** Behaviour is captured in [`specs/`](specs/) as
      "WHEN X THEN Y". A behaviour change without a spec change is not done.
- [ ] **Acceptance criteria pass.** Each criterion in the spec maps to a test.
- [ ] **Tests green, offline.** `make test` passes with no network/model calls
      (fakes injected). New logic has unit tests including the no-data / edge cases.
- [ ] **Lint + types clean.** `make lint` and `make typecheck` pass.
- [ ] **Eval not regressed.** If retrieval or generation changed, `make eval`
      hit-rate ≥ 70% and faithfulness ≥ 70%.
- [ ] **Secrets safe.** No keys committed; new config documented in `.env.example`.
- [ ] **Docs updated.** Affected spec, `FEATURES.md`, and `CHANGELOG.md`
      (`## [Unreleased]`) reflect the change.
- [ ] **Verified with evidence.** The PR/commit shows the command run and its output,
      not a claim of success.

## Why each item

- *Offline tests* — RAG that only "works" against a live model isn't testable in CI;
  the provider seam exists so we can prove logic without a network.
- *Eval gate* — turns "the answers seem good" into a measured threshold.
- *Changelog* — every change that reaches `main` should be explainable to a
  non-technical user via [What's New](CHANGELOG-STRATEGY.md).
