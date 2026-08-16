#!/usr/bin/env python3
"""Export the vector space for 3D inspection in the TensorBoard Embedding Projector (F26).

F23 shows *which* chunks were retrieved for one question. F24 checks whether the answer
used them. Neither shows the shape of the space those decisions happen in — why a query
landed near one chunk and not another, or whether the corpus forms distinct regions at
all. That is a geometry question, and geometry wants a picture.

This writes the space out; it does not draw it. The viewer is the **TensorBoard
Embedding Projector**, which already does 3D PCA / t-SNE / UMAP with rotation, search,
and nearest-neighbour highlighting. Writing another one would be reinventing a wheel
that has been round since 2016.

Three kinds of point go into one space, which is the point — you cannot see how a query
relates to a chunk if they are plotted separately:

    chunk   the indexed chunks, using the vectors Chroma already stores (never re-embedded,
            so this is literally what retrieval searches)
    token   the most frequent corpus terms, embedded with the same model - the "word map"
    query   the eval questions, so you can watch one land among its chunks

Usage:
    python scripts/export_embeddings.py
    python scripts/export_embeddings.py --tokens 500 --kinds chunk token
    python scripts/export_embeddings.py --question "What is the ARR?"

Then open https://projector.tensorflow.org, click **Load**, and pass the two files it
asks for. The page is client-side: the vectors are parsed in the browser and never
uploaded, which is the only reason this is an acceptable suggestion for a project whose
whole posture is local-first. To stay fully offline instead, serve the projector's
static build yourself - it is Apache-2.0 and needs no backend.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cache import wrap_embeddings  # noqa: E402
from app.config import settings  # noqa: E402
from app.grounding import _STOPWORDS  # noqa: E402
from app.ingest import load_index  # noqa: E402
from app.providers import get_embeddings  # noqa: E402
from app.retrieval import _tokenize  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = PROJECT_ROOT / "data" / "embeddings"
PREVIEW_CHARS = 120


def _clean(value: object) -> str:
    """Flatten a value onto one TSV cell: tabs and newlines would shift every column."""
    return " ".join(str(value if value is not None else "").split())


def corpus_terms(documents: list[str], limit: int) -> list[str]:
    """The most frequent content terms in the corpus, most frequent first.

    Uses the same tokenizer as the BM25 retrieval arm, so the words plotted here are the
    words retrieval actually matches on — including figures like ``$12.4m`` and ``39%``,
    which a naive word split would shred. Stopwords are dropped: plotting "the" tells you
    nothing about a corpus and drags the projection toward a meaningless centroid.
    """
    counts: Counter[str] = Counter()
    for text in documents:
        counts.update(t for t in _tokenize(text) if t not in _STOPWORDS and len(t) > 1)
    return [term for term, _ in counts.most_common(limit)]


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
    ap.add_argument(
        "--question",
        action="append",
        default=[],
        help="extra question to plot (repeatable)",
    )
    args = ap.parse_args()

    embeddings = wrap_embeddings(get_embeddings(settings), settings)
    store = load_index(settings, embeddings)
    stored = store._collection.get(include=["embeddings", "documents", "metadatas"])
    documents = list(stored.get("documents") or [])
    if not documents:
        print(
            "The index is empty - run `python -m app.ingest` first.",
            file=sys.stderr,
        )
        return 1

    vectors: list[list[float]] = []
    rows: list[dict[str, str]] = []

    if "chunk" in args.kinds:
        metas = list(stored.get("metadatas") or [])
        for vec, text, meta in zip(stored["embeddings"], documents, metas, strict=False):
            meta = meta or {}
            vectors.append([float(x) for x in vec])
            rows.append(
                {
                    "kind": "chunk",
                    "label": _clean(meta.get("source", "unknown")),
                    "source": _clean(meta.get("source", "")),
                    "page": _clean(meta.get("page", "")),
                    "chars": str(len(text or "")),
                    "preview": _clean(text)[:PREVIEW_CHARS],
                }
            )

    if "token" in args.kinds:
        terms = corpus_terms(documents, args.tokens)
        if terms:
            # One batch: 300 short strings is a single fast pass on the embedding model,
            # and the cache means a re-export costs nothing.
            for term, vec in zip(terms, embeddings.embed_documents(terms), strict=False):
                vectors.append([float(x) for x in vec])
                rows.append(
                    {
                        "kind": "token",
                        "label": term,
                        "source": "",
                        "page": "",
                        "chars": str(len(term)),
                        "preview": term,
                    }
                )

    if "query" in args.kinds or args.question:
        questions = list(args.question)
        dataset = PROJECT_ROOT / "eval" / "qa_dataset.jsonl"
        if "query" in args.kinds and dataset.exists():
            questions += [
                json.loads(line)["question"]
                for line in dataset.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        if questions:
            for q, vec in zip(questions, embeddings.embed_documents(questions), strict=False):
                vectors.append([float(x) for x in vec])
                rows.append(
                    {
                        "kind": "query",
                        "label": _clean(q)[:60],
                        "source": "",
                        "page": "",
                        "chars": str(len(q)),
                        "preview": _clean(q)[:PREVIEW_CHARS],
                    }
                )

    args.out.mkdir(parents=True, exist_ok=True)
    vectors_path = args.out / "vectors.tsv"
    metadata_path = args.out / "metadata.tsv"

    # newline="\n" is not cosmetic. Without it Python translates "\n" to "\r\n" on
    # Windows, the projector splits lines on "\n" only, and every last column arrives
    # with a trailing CR — the header became "preview\r" and every preview value ended
    # in an invisible carriage return. It loads without complaint, which is what makes
    # it worth pinning down.
    vectors_path.write_text(
        "\n".join("\t".join(f"{x:.6f}" for x in vec) for vec in vectors) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    # The projector requires a header row whenever metadata has more than one column,
    # and silently mis-reads the file without it.
    columns = ["kind", "label", "source", "page", "chars", "preview"]
    metadata_path.write_text(
        "\n".join(["\t".join(columns)] + ["\t".join(r[c] for c in columns) for r in rows]) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    counts = Counter(r["kind"] for r in rows)
    dim = len(vectors[0]) if vectors else 0
    print(f"Wrote {len(vectors)} points x {dim} dims to {args.out.relative_to(PROJECT_ROOT)}")
    for kind in ("chunk", "token", "query"):
        if counts[kind]:
            print(f"  {kind:<6} {counts[kind]}")
    print(f"\n  {vectors_path.relative_to(PROJECT_ROOT)}")
    print(f"  {metadata_path.relative_to(PROJECT_ROOT)}")
    print(
        "\nOpen https://projector.tensorflow.org -> Load -> pick those two files.\n"
        "Parsing is client-side; nothing is uploaded. Then colour by 'kind', switch to\n"
        "UMAP or t-SNE, and tick 3D."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
