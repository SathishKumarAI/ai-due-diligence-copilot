Stage the changes and write a Conventional Commit.

- Subject ≤ 50 chars, imperative: `feat:`, `fix:`, `docs:`, `test:`, `chore:`.
- Body only when the "why" isn't obvious from the subject.
- If behaviour changed, confirm the spec in `docs/specs/` and `CHANGELOG.md`
  (`## [Unreleased]`) were updated; remind me if not.
- Do not commit `.env`, `chroma_db/`, `.cache/`, or `node_modules/`.
