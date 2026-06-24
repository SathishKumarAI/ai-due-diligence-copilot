# Glossary

Shared vocabulary so humans and the agent use the same words.

| Term | Meaning |
|------|---------|
| **RAG** | Retrieval-Augmented Generation — retrieve relevant text, then have an LLM answer from it. |
| **chunk** | A slice of a source document (≈1000 chars) that is embedded and stored. Retrieval works on chunks, not whole files. |
| **embedding** | A numeric vector representing a chunk's meaning; similar text → nearby vectors. |
| **vector store** | The database of embeddings (Chroma here) that supports similarity search. |
| **retrieval / top-k** | Fetching the `k` chunks most similar to the question. |
| **grounding** | Answering only from retrieved passages; if they don't cover it, say so. |
| **citation** | A `[n]` marker in the answer pointing at a specific retrieved chunk, surfaced with its source filename + snippet. |
| **provider** | The swappable model backend: `ollama` (open-source, default) or `claude`. |
| **faithfulness** | Eval metric: is every claim in the answer supported by the retrieved context? |
| **hit-rate** | Eval metric: did the expected source appear in the top-k retrieved chunks? |
| **ingest** | The pipeline that loads → chunks → embeds → persists documents. |

### Domain terms (due diligence)
| Term | Meaning |
|------|---------|
| **ARR** | Annual Recurring Revenue. |
| **runway** | Months of cash left at the current burn rate. |
| **liquidation preference** | What investors get back first on an exit. |
| **customer concentration** | Risk from one customer being a large share of revenue. |
| **post-money valuation** | Company value immediately after an investment. |
