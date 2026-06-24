from langchain_core.documents import Document

from app.config import settings
from app.ingest import load_documents, split_documents


def test_split_preserves_source_metadata():
    long_text = "Section. " * 800  # ~6k chars -> multiple chunks
    docs = [Document(page_content=long_text, metadata={"source": "big.md", "page": None})]
    chunks = split_documents(docs, settings)
    assert len(chunks) > 1
    assert all(c.metadata["source"] == "big.md" for c in chunks)


def test_load_documents_reads_corpus_and_sets_source():
    docs = load_documents(settings.data_dir)
    assert docs, "sample corpus should not be empty"
    assert all("source" in d.metadata for d in docs)
    assert any(d.metadata["source"].endswith(".md") for d in docs)
