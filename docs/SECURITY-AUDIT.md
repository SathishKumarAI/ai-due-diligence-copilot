# Security & Privacy Audit — ai-due-diligence-copilot

Date: 2026-07-03 · Scope: pre-public hardening for P3 (repo is already public).

## Method
- Swept tracked files for API keys, tokens, private keys, passwords, and personal
  contact info (regex over `*.py/*.md/*.ts/*.tsx/*.env*/*.yml/*.json/*.toml`).
- Scanned **full git history** (`git log -p --all`) for the same patterns.
- Verified `.gitignore` covers secret/build/data artifacts.

## Findings

| Severity | Finding | Status |
|---|---|---|
| ✅ none | No API keys, tokens, private keys, or passwords in tracked files | Clean |
| ✅ none | No secrets anywhere in git history | Clean |
| ✅ none | `.env` is **not** tracked; `.gitignore` covers `.env`, `chroma_db/`, `.cache/` | Clean |
| ⚠️ PII | Commit **author metadata** in existing history uses two personal email addresses (redacted here) instead of the GitHub identity | **Action needed** |

The only issue is the git identity. The requirement is "GitHub profile only, no other
personal info." Existing commit metadata uses personal emails; these must be replaced
with the GitHub noreply address. The addresses are deliberately not reproduced in this
document.

## Remediation

- **Done:** repo-local git identity set to `SathishKumarAI@users.noreply.github.com`
  so all future commits use only the GitHub handle. New P3 commits will carry it.
- **Pending your approval (history rewrite):** the *existing* public commits still carry
  the personal emails. Scrubbing them means rewriting history across the repo with
  `git filter-repo --mailmap` (map both personal emails → the noreply address) and a
  **force-push**. This changes every commit SHA and can break existing clones/links, so
  it is a deliberate, user-approved step — not done automatically.

## `.gitignore` coverage (verified)
`.env`, `chroma_db/`, `.cache/` are ignored. New P3 artifacts to keep ignored:
`data/corpus/` (fetched docs), `data/uploads/`, `data/feedback.jsonl` — confirm these
are ignored before committing a fetched corpus (they are generated, not source).
