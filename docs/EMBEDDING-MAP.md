---
title: Embedding map
description: Seeing the vector space this RAG pipeline actually searches — chunks, corpus words and questions in one 3D projection.
---

# Embedding map (F26)

F23 shows *which* chunks were retrieved for one question. F24 checks whether the answer
used them. Neither shows the **shape of the space** those decisions happen in — why a
question landed near one chunk and not another, whether the corpus forms distinct
regions, or where the words of the domain sit relative to each other.

That is a geometry question, so it wants a picture.

## What draws it

The **[TensorBoard Embedding Projector](https://projector.tensorflow.org)** — Apache-2.0,
already does 3D PCA / t-SNE / UMAP with rotation, search and nearest-neighbour
highlighting. This repo writes the data out; it does not draw it. Building another
viewer would be reinventing a wheel that has been round since 2016.

`scripts/export_embeddings.py` writes the two TSV files the projector expects.

## Run it

```bash
python -m app.ingest                      # the index must exist first
python scripts/export_embeddings.py
```

```
Wrote 247 points x 384 dims to data\embeddings
  chunk  4
  token  233
  query  10
```

### Viewing it, fully local (recommended, verified)

The projector's standalone build is Apache-2.0 static files with no backend, so the
whole thing runs offline and the file-picker step disappears:

```bash
git clone --depth 1 https://github.com/tensorflow/embedding-projector-standalone.git
cd embedding-projector-standalone
mkdir -p rag_data && cp /path/to/repo/data/embeddings/*.tsv rag_data/

cat > rag_data/config.json <<'JSON'
{
  "embeddings": [
    {
      "tensorName": "RAG pipeline - chunks, tokens, queries",
      "tensorShape": [247, 384],
      "tensorPath": "rag_data/vectors.tsv",
      "metadataPath": "rag_data/metadata.tsv"
    }
  ]
}
JSON

python -m http.server 8189 --bind 127.0.0.1
```

Open <http://127.0.0.1:8189/?config=rag_data/config.json>. `tensorShape` must match the
export — the exporter prints both numbers.

Set **Label by** to `label` and **Color by** to `kind`. Labelling by `kind` is the
default the first time and makes every point read "token", which is not a word map.

### Or the hosted page

<https://projector.tensorflow.org> → **Load** → give it the two TSVs. It parses them in
the browser and uploads nothing, which is the only reason a hosted page is acceptable
here at all. The local route above avoids the question entirely.

In either: switch the projection to **UMAP** or **t-SNE** and tick **3D**. PCA is the
default and is instant; UMAP takes a few seconds and usually separates the groups better.

## What is in the space

Three kinds of point, deliberately in **one** space — you cannot see how a question
relates to a chunk if they are plotted separately.

| kind | what it is | where the vector comes from |
|---|---|---|
| `chunk` | the indexed chunks | read straight out of Chroma, never re-embedded, so these are literally the vectors retrieval searches |
| `token` | the most frequent corpus terms — the "word map" | embedded with the same model at export time |
| `query` | the eval questions | embedded with the same model at export time |

Tokens come from `retrieval._tokenize`, the same tokenizer that drives the BM25 arm, so
the words plotted are the words retrieval actually matches on — including figures like
`$12.4m` and `39%` that a naive word split would shred. Stopwords are dropped; plotting
"the" says nothing about a corpus and drags the projection toward a meaningless
centroid.

Options:

```bash
python scripts/export_embeddings.py --tokens 500          # a denser word map
python scripts/export_embeddings.py --kinds chunk query   # drop the word cloud
python scripts/export_embeddings.py --question "What is the ARR?"   # plot your own
```

## What the map already showed

Measured on the export, by nearest cosine neighbour among chunks:

```
nearest-chunk == expected_source: 8/10
```

Eight of the ten eval questions have their expected source as the single nearest chunk
in embedding space. The two that miss — "What is the company's gross margin?" and "What
roles on the team are unfilled?" — land nearest a different document.

That number is worth keeping in view: it is the **dense arm on its own**. It is a
concrete reason the shipped default is `RETRIEVAL_MODE=hybrid` rather than pure dense —
the BM25 side exists to catch questions whose wording does not sit closest to the right
chunk. `scripts/simulate.py` measures the same thing from the other end, by comparing
grounded answers across retrieval modes.

## Caveats

- **384 dimensions do not fit in 3.** PCA, t-SNE and UMAP all discard most of the
  variance. Two points looking close on screen is a hint, not a fact; distances the
  retriever uses are computed in the full space, and the projector's own
  nearest-neighbour panel reports those.
- **The corpus here is four synthetic documents.** The map is legible but not
  interesting. It gets useful on a real corpus — which needs `SEC_USER_AGENT`, see
  `docs/INGESTION.md`.
- Output is gitignored (`data/embeddings/`): it is derived from the index and a few MB
  of floats. Regenerate it, do not commit it.
