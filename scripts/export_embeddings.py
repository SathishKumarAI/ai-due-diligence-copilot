#!/usr/bin/env python3
"""Export the vector space for 3D inspection in the TensorBoard Embedding Projector (F26).

F23 shows *which* chunks were retrieved for one question. F24 checks whether the answer
used them. Neither shows the shape of the space those decisions happen in — why a
question landed near one chunk and not another, or whether the corpus forms distinct
regions at all. That is a geometry question, and geometry wants a picture.

This writes the space out; it does not draw it. The viewer is the **TensorBoard
Embedding Projector** (Apache-2.0), which already does 3D PCA / t-SNE / UMAP with
rotation, search and nearest-neighbour lookup. See docs/EMBEDDING-MAP.md for how to run
it fully offline, and for the reasoning behind every column below.

Three kinds of point go into ONE space, because you cannot see how a question relates to
a chunk if they are plotted separately:

    chunk   the indexed chunks, using the vectors Chroma already stores (never
            re-embedded, so these are literally what retrieval searches)
    token   the corpus vocabulary - the word map
    query   the eval questions, plus any you pass with --question

Every row carries the features you would want *before* clicking a point, because the
projector shows one label at a time and the metadata card needs a click. ``display`` is
the label to select in the UI: it packs the identifying value and the two or three
numbers that matter for that kind of point.

Usage:
    python scripts/export_embeddings.py
    python scripts/export_embeddings.py --tokens 500
    python scripts/export_embeddings.py --question "What is the ARR?"
    python scripts/export_embeddings.py --kinds chunk query      # drop the word cloud
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from app.cache import wrap_embeddings  # noqa: E402
from app.config import settings  # noqa: E402
from app.grounding import _STOPWORDS  # noqa: E402
from app.ingest import load_index  # noqa: E402
from app.providers import get_embeddings  # noqa: E402
from app.retrieval import _tokenize  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = PROJECT_ROOT / "data" / "embeddings"
PREVIEW_CHARS = 140

# Every row writes every column; blanks where a feature does not apply to that kind.
# The projector requires a rectangular file and silently mis-reads a ragged one.
COLUMNS = [
    "kind",
    "display",  # the label to select in the UI — carries the values, so no click needed
    "label",
    "source",
    "chars",
    # --- token features ---
    "tf",  # corpus frequency
    "df",  # chunks containing the term
    "idf",  # BM25 inverse document frequency: how discriminative the term is
    "is_figure",  # contains a digit — money, percentages, dates
    # --- chunk features ---
    "n_tokens",
    "n_unique",
    "extraction",  # text | ocr — F20 provenance
    "origin",  # corpus | upload — was this submitted through /v1/upload?
    "top_terms",  # the chunk's most distinctive terms, by tf*idf
    "nearest_queries",  # how many eval questions land closest to this chunk
    # --- query features ---
    "expected_source",  # ground truth from the eval dataset
    "nearest_source",  # what dense retrieval alone puts closest
    "nearest_ok",  # yes | no — colour by this to see dense accuracy at a glance
    "expected_rank",  # rank of the expected chunk by cosine (1 = best)
    "nearest_dist",  # cosine distance to the closest chunk
]


def _clean(value: object) -> str:
    """Flatten onto one TSV cell: a stray tab or newline shifts every column after it."""
    return " ".join(str(value if value is not None else "").split())


def blank_row() -> dict[str, str]:
    return dict.fromkeys(COLUMNS, "")


def term_stats(documents: list[str]) -> tuple[Counter[str], Counter[str], dict[str, float]]:
    """Corpus frequency, document frequency and BM25 idf for every term.

    idf is the number that matters most on a word map. A term appearing in every chunk
    cannot discriminate between them, so it contributes nothing to lexical retrieval no
    matter how often it occurs — colouring by idf separates the vocabulary that does
    retrieval work from the vocabulary that is merely present.

    Computed the same way app.retrieval.BM25Index computes it, so the numbers plotted are
    the numbers the lexical arm actually uses.
    """
    tf: Counter[str] = Counter()
    df: Counter[str] = Counter()
    for text in documents:
        toks = _tokenize(text)
        tf.update(toks)
        df.update(set(toks))
    n = len(documents)
    idf = {
        term: max(0.0, math.log((n - freq + 0.5) / (freq + 0.5) + 1.0)) for term, freq in df.items()
    }
    return tf, df, idf


def chunk_top_terms(text: str, idf: dict[str, float], k: int = 3) -> str:
    """The terms that make this chunk distinctive: tf within the chunk, weighted by idf."""
    counts = Counter(t for t in _tokenize(text) if t not in _STOPWORDS and len(t) > 1)
    ranked = sorted(counts.items(), key=lambda kv: kv[1] * idf.get(kv[0], 0.0), reverse=True)
    return ", ".join(term for term, _ in ranked[:k])


def main() -> int:
    ap = argparse.ArgumentParser(description="Export vectors for the Embedding Projector.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    ap.add_argument("--tokens", type=int, default=300, help="how many corpus terms to plot")
    ap.add_argument(
        "--kinds",
        nargs="*",
        default=["chunk", "token", "query"],
        choices=["chunk", "token", "query"],
        help="which point kinds to include",
    )
    ap.add_argument("--question", action="append", default=[], help="extra question (repeatable)")
    args = ap.parse_args()

    embeddings = wrap_embeddings(get_embeddings(settings), settings)
    store = load_index(settings, embeddings)
    stored = store._collection.get(include=["embeddings", "documents", "metadatas"])
    documents = list(stored.get("documents") or [])
    if not documents:
        print("The index is empty - run `python -m app.ingest` first.", file=sys.stderr)
        return 1

    metas = [m or {} for m in (stored.get("metadatas") or [])]
    chunk_vectors = np.array(stored["embeddings"], dtype=float)
    tf, df, idf = term_stats(documents)
    uploads_dir = PROJECT_ROOT / "data" / "uploads"

    # Ground truth, when there is any. Absent for a corpus that was just submitted and
    # has no eval questions yet, which must not break the export.
    expected_by_question: dict[str, str] = {}
    dataset = PROJECT_ROOT / "eval" / "qa_dataset.jsonl"
    dataset_questions: list[str] = []
    if dataset.exists():
        for line in dataset.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                dataset_questions.append(row["question"])
                expected_by_question[row["question"]] = row.get("expected_source", "")

    questions = list(args.question)
    if "query" in args.kinds:
        questions += dataset_questions

    # Query vectors are needed before chunk rows are written, so a chunk can report how
    # many questions land on it.
    query_vectors = (
        np.array(embeddings.embed_documents(questions), dtype=float)
        if questions
        else np.zeros((0, chunk_vectors.shape[1]))
    )

    # Vectors are already L2-normalised by the embedding model (verified: every norm is
    # 1.0000), so a dot product IS cosine similarity and no renormalisation is needed.
    nearest_chunk_idx: list[int] = []
    if len(query_vectors):
        sims = query_vectors @ chunk_vectors.T
        nearest_chunk_idx = list(np.argmax(sims, axis=1))
    landed_on = Counter(nearest_chunk_idx)

    vectors: list[list[float]] = []
    rows: list[dict[str, str]] = []

    if "chunk" in args.kinds:
        for i, (vec, text, meta) in enumerate(zip(chunk_vectors, documents, metas, strict=False)):
            toks = _tokenize(text)
            source = _clean(meta.get("source", "unknown"))
            origin = "upload" if (uploads_dir / source).exists() else "corpus"
            row = blank_row()
            row.update(
                kind="chunk",
                display=f"[chunk] {source} · {len(toks)}tok · {landed_on.get(i, 0)}q",
                label=source,
                source=source,
                chars=str(len(text or "")),
                n_tokens=str(len(toks)),
                n_unique=str(len(set(toks))),
                extraction=_clean(meta.get("extraction_method", "")),
                origin=origin,
                top_terms=chunk_top_terms(text, idf),
                nearest_queries=str(landed_on.get(i, 0)),
            )
            vectors.append([float(x) for x in vec])
            rows.append(row)

    if "token" in args.kinds:
        terms = [t for t, _ in tf.most_common() if t not in _STOPWORDS and len(t) > 1][
            : args.tokens
        ]
        if terms:
            for term, vec in zip(terms, embeddings.embed_documents(terms), strict=False):
                row = blank_row()
                row.update(
                    kind="token",
                    display=f"{term} · tf{tf[term]} df{df[term]} idf{idf.get(term, 0.0):.2f}",
                    label=term,
                    chars=str(len(term)),
                    tf=str(tf[term]),
                    df=str(df[term]),
                    idf=f"{idf.get(term, 0.0):.4f}",
                    is_figure="yes" if any(c.isdigit() for c in term) else "no",
                )
                vectors.append([float(x) for x in vec])
                rows.append(row)

    if len(query_vectors):
        for q, vec in zip(questions, query_vectors, strict=False):
            sims = chunk_vectors @ vec
            order = list(np.argsort(-sims))
            best = int(order[0])
            nearest_source = _clean(metas[best].get("source", ""))
            expected = expected_by_question.get(q, "")
            rank = ""
            if expected:
                for pos, ci in enumerate(order, start=1):
                    if _clean(metas[int(ci)].get("source", "")) == expected:
                        rank = str(pos)
                        break
            ok = "" if not expected else ("yes" if nearest_source == expected else "no")
            row = blank_row()
            row.update(
                kind="query",
                display=(
                    f"[q] {_clean(q)[:44]} -> {nearest_source}"
                    + ("" if not ok else f" {'OK' if ok == 'yes' else 'MISS'}")
                ),
                label=_clean(q)[:PREVIEW_CHARS],
                chars=str(len(q)),
                expected_source=expected,
                nearest_source=nearest_source,
                nearest_ok=ok,
                expected_rank=rank,
                nearest_dist=f"{1.0 - float(sims[best]):.4f}",
            )
            vectors.append([float(x) for x in vec])
            rows.append(row)

    args.out.mkdir(parents=True, exist_ok=True)
    vectors_path = args.out / "vectors.tsv"
    metadata_path = args.out / "metadata.tsv"

    # newline="\n" is not cosmetic. Without it Python translates "\n" to "\r\n" on
    # Windows, the projector splits lines on "\n" only, and every last column arrives
    # with a trailing CR — the header became "preview\r" and every value in that column
    # ended in an invisible carriage return. It loads without complaint.
    vectors_path.write_text(
        "\n".join("\t".join(f"{x:.6f}" for x in vec) for vec in vectors) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    metadata_path.write_text(
        "\n".join(["\t".join(COLUMNS)] + ["\t".join(r[c] for c in COLUMNS) for r in rows]) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    counts = Counter(r["kind"] for r in rows)
    dim = len(vectors[0]) if vectors else 0

    # The projector reads a static snapshot, so it silently goes stale the moment anything
    # is ingested or uploaded. Recording what this export was taken from is the only way
    # to notice: compare `chunks` here against /ready's indexed_chunks.
    manifest = {
        "generated_at": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "collection": settings.collection_name,
        "embed_model": settings.hf_embed_model,
        "points": len(vectors),
        "dimensions": dim,
        "chunks": int(counts["chunk"]),
        "tokens": int(counts["token"]),
        "queries": int(counts["query"]),
        "tensor_shape": [len(vectors), dim],
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    # Written so the standalone projector can be pointed straight at this directory
    # without hand-editing a shape that must match the export.
    (args.out / "config.json").write_text(
        json.dumps(
            {
                "embeddings": [
                    {
                        "tensorName": f"{settings.collection_name} - chunks, tokens, queries",
                        "tensorShape": [len(vectors), dim],
                        "tensorPath": "rag_data/vectors.tsv",
                        "metadataPath": "rag_data/metadata.tsv",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"Wrote {len(vectors)} points x {dim} dims to {args.out.relative_to(PROJECT_ROOT)}")
    for kind in ("chunk", "token", "query"):
        if counts[kind]:
            print(f"  {kind:<6} {counts[kind]}")

    scored = [r for r in rows if r["kind"] == "query" and r["nearest_ok"]]
    if scored:
        hits = sum(r["nearest_ok"] == "yes" for r in scored)
        print(f"\nDense-only nearest chunk == expected source: {hits}/{len(scored)}")
    uploaded = sum(r["origin"] == "upload" for r in rows)
    if uploaded:
        print(f"Chunks from submitted documents: {uploaded}")

    print(f"\n  {vectors_path.relative_to(PROJECT_ROOT)}")
    print(f"  {metadata_path.relative_to(PROJECT_ROOT)}")
    print(
        "\nIn the projector set Label by = 'display' (values are in the label, so you can\n"
        "read them without clicking) and Color by = 'kind', 'idf' or 'nearest_ok'.\n"
        "docs/EMBEDDING-MAP.md explains every column."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
