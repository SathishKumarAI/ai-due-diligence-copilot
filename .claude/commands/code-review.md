Review the current diff for this RAG service. Prioritize:

1. **Grounding & citations** — does any change let the model answer without retrieved
   context, or break the marker→chunk mapping (ADR-0002)?
2. **Provider seam** — does any code import a concrete vendor class outside
   `app/providers.py`? It shouldn't (ADR-0001).
3. **Offline tests** — do new tests stay offline (fakes, no network/model)?
4. **Security** — secrets only via env; input validated; no new injection surface.
5. **Spec + docs** — is the relevant `docs/specs/F*` updated, plus FEATURES.md and
   CHANGELOG.md (`## [Unreleased]`)?

Report findings by severity. Skip style nits ruff already handles.
