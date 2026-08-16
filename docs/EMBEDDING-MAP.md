---
title: Embedding map
description: The 3D map of the vector space this RAG pipeline searches — chunks, corpus words and questions in one projection, what each exported feature means, and how it relates to the app UI.
---

# Embedding map (F26)

F23 shows *which* chunks were retrieved for one question. F24 checks whether the answer
used them. Neither shows **the shape of the space** those decisions happen in — why a
question landed near one chunk and not another, whether the corpus forms distinct
regions, or where the vocabulary of the domain sits.

That is a geometry question, so it wants a picture.

---

## 1. The two UIs, and how they relate

**They are separate processes, and they are not synchronised.** This is the single most
important thing on this page, because nothing in either UI tells you.

```
 documents ─► ingest / upload ─► Chroma ─┬─► FastAPI :8000 ─► web UI :3000     LIVE
                                         │
                                         └─► scripts/export_embeddings.py
                                                    │
                                                    ▼
                                            data/embeddings/*.tsv           SNAPSHOT
                                                    │
                                                    ▼
                                       Embedding Projector :8189
```

The web UI queries Chroma on every request. The projector reads **static TSV files**
written at the moment you last ran the exporter. There is no connection between them.

Demonstrated, uploading one document through the running app:

```
before upload            /ready -> indexed_chunks: 4
POST /v1/upload          {"filename":"acme_board_minutes.md","chunks_added":1}
after upload             /ready -> indexed_chunks: 5
projector snapshot                 still 4 chunks / 247 points
```

The map went stale the instant the document was submitted, silently.

### Detecting staleness

Every export writes `data/embeddings/manifest.json`:

```json
{
  "generated_at": "2026-08-16T18:37:54+00:00",
  "collection": "due_diligence",
  "embed_model": "BAAI/bge-small-en-v1.5",
  "points": 272, "chunks": 5, "tokens": 257, "queries": 10
}
```

Compare `chunks` with `indexed_chunks` from `GET /ready`. Equal means current; different
means re-run the exporter. That check is deliberately manual — see *Why not live* below.

### Navigating between them

Set `NEXT_PUBLIC_EMBEDDING_MAP_URL` in `web/.env` and an **Embedding map** link appears
in the app's nav bar, next to *What's New*:

```
NEXT_PUBLIC_EMBEDDING_MAP_URL=http://127.0.0.1:8189/?config=rag_data/config.json
```

It is **empty by default and the link is hidden when unset**, because the projector is a
separate process most installs will not be running — a dead nav link is worse than no
link. `NEXT_PUBLIC_*` values are baked at build time, so set it before `npm run build`.

There is no link back from the projector; it is upstream software and this repo does not
patch it.

### Why not live

Making the map live would mean streaming vectors to the browser on every ingest, and
re-running a projection whose whole cost is in the fit. UMAP and t-SNE are not
incremental in any useful sense — adding one point re-arranges the layout, so a "live"
map would rearrange itself under you while you read it. A snapshot you re-take
deliberately is the more honest tool. The cost of that choice is staleness, which is why
the manifest exists.

---

## 2. Running it

```bash
python -m app.ingest                    # the index must exist first
python scripts/export_embeddings.py
```

### Viewing it, fully local (recommended, verified)

The projector's standalone build is Apache-2.0 static files with no backend, so this
runs offline and needs no file dialog:

```bash
git clone --depth 1 https://github.com/tensorflow/embedding-projector-standalone.git
cd embedding-projector-standalone
mkdir -p rag_data && cp /path/to/repo/data/embeddings/{vectors.tsv,metadata.tsv,config.json} rag_data/
python -m http.server 8189 --bind 127.0.0.1
```

Open <http://127.0.0.1:8189/?config=rag_data/config.json>. The exporter writes
`config.json` with the correct `tensorShape` already filled in, so it does not need
hand-editing after a re-export.

### Or the hosted page

<https://projector.tensorflow.org> → **Load** → give it the two TSVs. It parses them in
the browser and uploads nothing, which is the only reason a hosted page is acceptable
for a local-first project. The local route avoids the question entirely.

### First two things to set

1. **Label by → `display`.** The default is the first metadata column (`kind`), which
   makes every point read "token" — not a word map. `display` carries the identity *and*
   the numbers, so you can read values **without clicking**.
2. **Color by → `kind`**, then try `idf` or `nearest_ok` (see recipes below).

Then switch the projection to **UMAP** or **t-SNE** and tick **3D**. PCA is the default
and instant; UMAP takes a few seconds and usually separates groups better.

---

## 3. What is in the space, and why

Three kinds of point, deliberately in **one** space — you cannot see how a question
relates to a chunk if they are plotted separately.

| kind | what it is | vector source |
|---|---|---|
| `chunk` | the indexed chunks | read straight out of Chroma, **never re-embedded** — literally what retrieval searches |
| `token` | the most frequent corpus terms | embedded with the same model at export time |
| `query` | eval questions + anything passed to `--question` | embedded with the same model at export time |

Tokens come from `retrieval._tokenize`, the same tokenizer that drives the BM25 arm, so
the words plotted are the words retrieval actually matches on — including `$12.4m` and
`39%`, which a naive word split would shred.

### The feature set, and the reasoning behind it

A point you cannot interrogate is decoration. Every row carries the features you would
want *before* clicking it, and the design question for each was: **would this change a
decision?**

| column | applies to | why it is there |
|---|---|---|
| `display` | all | The label to select in the UI. Packs identity + the 2–3 numbers that matter for that kind, so values are readable without clicking. |
| `kind` | all | Colour dimension separating the three populations. |
| `label` | all | The plain value — the word, the source filename, the question. |
| `chars` | all | Raw size. Cheap outlier detector: a chunk far from its neighbours in size usually chunked badly. |
| `tf` | token | Corpus frequency. Frequent-but-useless words are visible immediately. |
| `df` | token | How many chunks contain the term. `df == n_chunks` means it cannot discriminate at all. |
| **`idf`** | token | **The most informative column on the word map.** BM25 inverse document frequency, computed the same way `BM25Index` computes it. Separates vocabulary that does retrieval work from vocabulary that is merely present. |
| `is_figure` | token | Contains a digit — money, percentages, dates. In a due-diligence corpus these are the tokens whose corruption causes the worst answers, and F24 checks them separately for the same reason. |
| `n_tokens`, `n_unique` | chunk | Length and lexical diversity. A long chunk with low diversity is boilerplate; a short one with high diversity is dense fact. |
| `extraction` | chunk | `text` vs `ocr` (F20). OCR chunks carry recognition noise; if they cluster oddly, that is why. |
| **`origin`** | chunk | `corpus` vs `upload` — was this document **submitted** through `/v1/upload`? Lets you see immediately whether newly-submitted documents land in their own region or mix into the existing corpus. |
| `top_terms` | chunk | The chunk's most distinctive terms by tf·idf. Tells you what a point *is* without opening it. |
| `nearest_queries` | chunk | How many eval questions land closest to this chunk. Reveals attractor chunks and orphans. |
| `expected_source` | query | Ground truth from the eval dataset. |
| `nearest_source` | query | What **dense retrieval alone** puts closest. |
| **`nearest_ok`** | query | `yes`/`no`. Colour by this to see dense retrieval's accuracy on the map itself. |
| **`expected_rank`** | query | Where the correct chunk ranks by cosine. `1` is a hit; a high number is a *severe* miss, and the distinction matters far more than a boolean. |
| `nearest_dist` | query | Cosine distance to the closest chunk. Calibration: how confident was that nearest match? |

Deliberately **not** included: the raw vector norm (every bge-small vector is exactly
L2-normalised — measured, all norms `1.0000` — so it is a constant and carries no
information, and it also means the projector's *Sphereize data* toggle is a no-op here).

---

## 4. Reading the map: four recipes

| Question | Colour by | What to look for |
|---|---|---|
| Which words actually drive retrieval? | `idf` | High-idf terms are the discriminative vocabulary. If your domain's key terms are low-idf, they appear in every chunk and lexical search cannot use them. |
| Where does dense retrieval fail? | `nearest_ok` | Every `no` is a question whose nearest chunk is the wrong document. Click it and read `expected_rank`. |
| Did submitted documents land sensibly? | `origin` | Uploads forming their own island means they are topically distinct; scattered among the corpus means they overlap it. |
| Is chunking sane? | `n_tokens` | Wildly uneven chunk sizes, or chunks the same size as whole documents, mean the splitter is not doing passage-level work. |

---

## 5. What the map has already shown

### Dense retrieval alone gets 8/10

```
Dense-only nearest chunk == expected source: 8/10
```

Two questions miss, and `expected_rank` shows they are not equivalent:

| question | expected | dense picked | rank of expected |
|---|---|---|---|
| What is the company's gross margin? | `acme_robotics_pitch.md` | `acme_10k_excerpt.md` | **4 of 4 — dead last** |
| What roles on the team are unfilled? | `acme_robotics_pitch.md` | `acme_risk_factors.md` | 2 |

The ground truth was checked rather than assumed — `Gross margin: 61%` is literally in
`acme_robotics_pitch.md`, and the vacant VP of Sales role is there too. Both are genuine
dense failures, not label errors.

This is a concrete argument for the shipped `RETRIEVAL_MODE=hybrid`: BM25 matches the
phrase "gross margin" exactly and ranks that chunk first, which is precisely the case
dense ranks last.

### The root cause: chunks are whole documents

Measured:

```
chunk_size=1000  chunk_overlap=150

acme_10k_excerpt.md      637 chars -> 1 chunk
acme_risk_factors.md     893 chars -> 1 chunk
acme_robotics_pitch.md   835 chars -> 1 chunk
acme_term_sheet.md       526 chars -> 1 chunk
```

Every document is smaller than one chunk, so **one chunk == one document** and each
vector is a *document-level average*. The single line `Gross margin: 61%` is averaged
together with everything else in a pitch deck about warehouse robots, and the resulting
vector is not close to a question about margins.

That fully explains the worst miss, and it is a property of this corpus meeting these
settings — not a bug in retrieval. On a real corpus where documents span many chunks,
passage-level retrieval behaves very differently. Worth re-measuring there before tuning
`chunk_size` on the strength of a four-document sample.

### idf is compressed by corpus size

With 4 chunks, `df` can only be 1–4, so idf spans roughly 0.11–0.69 and the word map's
colour range is nearly flat. The column is correct; the corpus is too small for it to
say much. Another thing that gets interesting only on a real corpus.

---

## 6. Caveats

- **384 dimensions do not fit in 3.** PCA here describes about **16.9%** of the
  variance. Two points looking close on screen is a hint, not a fact. The retriever works
  in the full space, and the projector's own nearest-neighbour panel reports true
  distances there — trust that panel over your eyes.
- **The corpus is four synthetic documents plus whatever you have uploaded.** The map is
  legible but not yet interesting. It needs a real corpus, which needs `SEC_USER_AGENT`
  (see `docs/INGESTION.md`).
- **`top_terms` reuses the F24 stopword list**, which was tuned to stop discourse words
  inflating a grounding score, not to extract keywords. It lets through weak terms like
  "pre", "prior" and "single". Good enough to identify a chunk; not a keyword extractor.
- **Output is gitignored** (`data/embeddings/`). It is derived from the index and a few
  MB of floats. Regenerate it; do not commit it.

---

## 7. Design notes and open questions

Kept because the reasoning is the part that does not survive in code.

**Why not build a viewer?** The projector already does 3D PCA/t-SNE/UMAP with rotation,
search and neighbour lookup, under Apache-2.0. Apple's `embedding-atlas` was the other
candidate and is better for very large sets, but it is 2D-oriented and the requirement
here was explicitly 3D. Writing a third one would be reinventing a wheel that has been
round since 2016.

**Why one space instead of three?** The entire question being asked is *relational* —
does this query sit near that chunk? Separate plots cannot answer it. The cost is that
tokens dominate by count (257 of 272 points), so colouring by `kind` is nearly mandatory.

**Why lexical stats on an embedding map?** The pipeline is hybrid. Half of retrieval is
BM25, and BM25's behaviour is entirely determined by tf/df/idf. A map that showed only
the dense half would explain only half the failures.

Open questions, not yet answered:

- Should the token cloud be capped by idf rather than frequency? Ranking by `tf` fills
  the map with common words; ranking by idf would show the discriminative tail instead.
- Should chunk points be sized by `nearest_queries` to make attractor chunks obvious
  without colouring? The projector supports this but it needs a numeric column convention.
- Is `expected_rank` worth surfacing in the app's F23 trace panel too? It is the number
  that distinguishes a near-miss from a total retrieval failure, and today it exists only
  in this export.
