"""Document ingestion pipeline (feature F01).

load (pdf/md/txt) -> split -> embed -> persist to a Chroma collection.

Run as a module to (re)build the index:
    python -m app.ingest
"""
from __future__ import annotations

import logging
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.cache import wrap_embeddings
from app.config import Settings, settings as default_settings
from app.providers import get_embeddings

logger = logging.getLogger(__name__)

_SUPPORTED = {".pdf", ".md", ".txt", ".markdown"}


def load_documents(data_dir: Path) -> list[Document]:
    """Load every supported file under data_dir, preserving source metadata."""
    docs: list[Document] = []
    for path in sorted(data_dir.rglob("*")):
        if path.suffix.lower() not in _SUPPORTED or not path.is_file():
            continue
        if path.suffix.lower() == ".pdf":
            loaded = PyPDFLoader(str(path)).load()
        else:
            loaded = TextLoader(str(path), encoding="utf-8").load()
        for d in loaded:
            d.metadata["source"] = path.name
            d.metadata.setdefault("page", d.metadata.get("page"))
        docs.extend(loaded)
    return docs


def split_documents(docs: list[Document], settings: Settings) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        add_start_index=True,
    )
    return splitter.split_documents(docs)


def build_index(
    settings: Settings | None = None, embeddings: Embeddings | None = None
) -> dict:
    """Build (or rebuild) the Chroma index from settings.data_dir.

    Idempotent: the collection is reset so re-running reflects the current corpus.
    """
    settings = settings or default_settings
    embeddings = embeddings or wrap_embeddings(get_embeddings(settings), settings)

    docs = load_documents(settings.data_dir)
    if not docs:
        raise RuntimeError(f"No documents found in {settings.data_dir}")
    chunks = split_documents(docs, settings)

    store = Chroma(
        collection_name=settings.collection_name,
        persist_directory=str(settings.chroma_dir),
        embedding_function=embeddings,
    )
    # Idempotent rebuild: drop any prior chunks before re-adding.
    try:
        store.reset_collection()
    except Exception:  # noqa: BLE001 - first run: collection may not exist yet
        pass
    store.add_documents(chunks)

    result = {
        "documents": len({d.metadata["source"] for d in docs}),
        "chunks": len(chunks),
        "collection": settings.collection_name,
    }
    logger.info("ingest_complete", extra=result)
    return result


def load_index(settings: Settings, embeddings: Embeddings) -> Chroma:
    """Open the persisted Chroma collection for querying."""
    return Chroma(
        collection_name=settings.collection_name,
        persist_directory=str(settings.chroma_dir),
        embedding_function=embeddings,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    out = build_index()
    print(f"Ingested {out['documents']} documents into "
          f"{out['chunks']} chunks (collection: {out['collection']}).")
