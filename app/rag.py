"""RAG engine (features F02, F03): retrieve -> prompt -> LLM -> answer + citations.

The engine depends only on a vector store and a chat model (both LangChain
interfaces), never a concrete vendor class. That seam is what makes the provider
switch and offline testing possible: tests inject a fake store + fake LLM.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.vectorstores import VectorStore

from app.prompts import SYSTEM_PROMPT

_MARKER_RE = re.compile(r"\[(\d+)\]")
_SNIPPET_LEN = 280


@dataclass
class Citation:
    marker: int
    source: str
    page: int | None
    snippet: str


@dataclass
class Answer:
    question: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)


def _format_context(docs: list[Document]) -> str:
    """Number each retrieved chunk so the model can cite it as [n]."""
    blocks = []
    for i, d in enumerate(docs, start=1):
        src = d.metadata.get("source", "unknown")
        page = d.metadata.get("page")
        loc = f"{src}, p.{page}" if page is not None else src
        blocks.append(f"[{i}] (source: {loc})\n{d.page_content.strip()}")
    return "\n\n".join(blocks)


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    return text[:_SNIPPET_LEN] + ("…" if len(text) > _SNIPPET_LEN else "")


class RagEngine:
    def __init__(
        self,
        vectorstore: VectorStore,
        llm: BaseChatModel,
        *,
        top_k: int = 5,
        provider: str = "ollama",
    ) -> None:
        self.vectorstore = vectorstore
        self.llm = llm
        self.top_k = top_k
        self.provider = provider

    def _retrieve(self, question: str, top_k: int) -> list[Document]:
        return self.vectorstore.similarity_search(question, k=top_k)

    def _build_messages(self, question: str, context: str) -> list[tuple[str, str]]:
        user = (
            f"Context passages:\n\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer using only the passages above and cite with [n] markers."
        )
        return [("system", SYSTEM_PROMPT), ("human", user)]

    def _citations(self, answer_text: str, docs: list[Document]) -> list[Citation]:
        """Return citations for the markers the answer actually used.

        Falls back to all retrieved chunks if the model emitted no markers, so the
        caller always gets a traceable source list.
        """
        used = {int(m) for m in _MARKER_RE.findall(answer_text)}
        indices = sorted(used) if used else list(range(1, len(docs) + 1))
        out: list[Citation] = []
        for i in indices:
            if 1 <= i <= len(docs):
                d = docs[i - 1]
                out.append(
                    Citation(
                        marker=i,
                        source=d.metadata.get("source", "unknown"),
                        page=d.metadata.get("page"),
                        snippet=_snippet(d.page_content),
                    )
                )
        return out

    def answer(self, question: str, top_k: int | None = None) -> Answer:
        k = top_k or self.top_k
        timings: dict[str, float] = {}

        t0 = time.perf_counter()
        docs = self._retrieve(question, k)
        timings["retrieve_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        if not docs:
            return Answer(
                question=question,
                answer="The provided documents do not cover this.",
                citations=[],
                timings_ms=timings,
            )

        context = _format_context(docs)
        messages = self._build_messages(question, context)

        t1 = time.perf_counter()
        response = self.llm.invoke(messages)
        timings["generate_ms"] = round((time.perf_counter() - t1) * 1000, 1)

        text = response.content if isinstance(response.content, str) else str(response.content)
        return Answer(
            question=question,
            answer=text.strip(),
            citations=self._citations(text, docs),
            timings_ms=timings,
        )

    def stream(self, question: str, top_k: int | None = None):
        """Yield answer tokens, then a final ('citations', [...]) tuple (F06)."""
        k = top_k or self.top_k
        docs = self._retrieve(question, k)
        if not docs:
            yield ("token", "The provided documents do not cover this.")
            yield ("citations", [])
            return
        messages = self._build_messages(question, _format_context(docs))
        collected = []
        for chunk in self.llm.stream(messages):
            piece = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
            if piece:
                collected.append(piece)
                yield ("token", piece)
        yield ("citations", self._citations("".join(collected), docs))
