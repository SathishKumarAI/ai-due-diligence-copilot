# ADR-0002: Derive citations from retrieval metadata, not the model

- **Status:** Accepted
- **Date:** 2026-06-23

## Context

Citations are the trust mechanism of this product. If the model invents a citation
(a plausible-looking source/page it wasn't given), the feature actively misleads. We
also want citations to work identically across providers (ADR-0001).

## Decision

Number the retrieved chunks `[1..k]` in the prompt. The model is instructed to cite
those markers. We then build the returned `citations[]` by parsing `[n]` markers from
the answer and **mapping each back to the actual retrieved chunk's metadata**
(`source`, `page`, snippet). If the model emits no markers, we fall back to returning
all retrieved chunks as traceable sources.

We deliberately do **not** use a provider's native citation API.

## Consequences

- ✅ A citation can always be traced to a real chunk that was in context; the model
  cannot fabricate a source path.
- ✅ Identical behaviour for `ollama` and `claude`.
- ✅ Simple, testable mapping (`tests/test_citations.py`).
- ⚠️ Citation *precision* depends on the model citing the right marker; a wrong marker
  points at a real-but-wrong chunk. The eval suite's faithfulness metric guards the
  overall grounding.
- ⚠️ We don't get sub-sentence character offsets that a native citation API could give.
