"""RAG engine (features F02, F03, F16, F17, F19): retrieve -> rerank -> prompt ->
LLM -> answer + citations, with optional hybrid retrieval, cross-encoder reranking,
and multi-turn follow-up condensing.

The engine depends only on small interfaces — a ``Retriever``, a ``Reranker``, and a
chat model — never a concrete vendor class. That seam is what makes the provider
switch and offline testing possible: tests inject fakes for every collaborator.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.vectorstores import VectorStore

from app import trace as _trace
from app.prompts import CONDENSE_PROMPT, SYSTEM_PROMPT
from app.rerank import NoOpReranker, Reranker
from app.retrieval import DenseRetriever, HybridRetriever, Retriever

_MARKER_RE = re.compile(r"\[(\d+)\]")
_SNIPPET_LEN = 280


@dataclass
class Citation:
    marker: int
    source: str
    page: int | None
    snippet: str


@dataclass
class Turn:
    """One prior exchange in a conversation (F19)."""

    role: str  # "user" | "assistant"
    content: str


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
        retriever: Retriever | None = None,
        reranker: Reranker | None = None,
        fetch_k: int = 20,
        history_max_turns: int = 6,
    ) -> None:
        self.vectorstore = vectorstore
        self.llm = llm
        self.top_k = top_k
        self.provider = provider
        self.retriever = retriever or DenseRetriever(vectorstore)
        self.reranker = reranker or NoOpReranker()
        self.fetch_k = fetch_k
        self.history_max_turns = history_max_turns

    # --- conversation memory (F19) ---

    def _condense(self, question: str, history: list[Turn] | None) -> str:
        """Rewrite a follow-up into a standalone query using recent history.

        No history → the question is already standalone. On any failure or empty
        rewrite, fall back to the original question (never regress single-turn).
        """
        if not history:
            return question
        recent = history[-self.history_max_turns :]
        convo = "\n".join(f"{t.role}: {t.content}" for t in recent)
        user = f"Conversation so far:\n{convo}\n\nFollow-up question: {question}"
        try:
            resp = self.llm.invoke([("system", CONDENSE_PROMPT), ("human", user)])
            text = resp.content if isinstance(resp.content, str) else str(resp.content)
            text = text.strip()
            return text or question
        except Exception:  # noqa: BLE001 - condensing is best-effort
            return question

    # --- retrieval (F02 / F16 / F17) ---

    def _retrieve(self, query: str, top_k: int) -> list[Document]:
        """Fetch candidates then (optionally) rerank down to ``top_k``."""
        fetch = max(top_k, self.fetch_k) if not isinstance(self.reranker, NoOpReranker) else top_k
        candidates = self.retriever.retrieve(query, fetch)
        return self.reranker.rerank(query, candidates, top_k)

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

    def answer(
        self,
        question: str,
        top_k: int | None = None,
        history: list[Turn] | None = None,
    ) -> Answer:
        k = top_k or self.top_k
        timings: dict[str, float] = {}

        tc = time.perf_counter()
        query = self._condense(question, history)
        if history:
            timings["condense_ms"] = round((time.perf_counter() - tc) * 1000, 1)

        t0 = time.perf_counter()
        docs = self._retrieve(query, k)
        timings["retrieve_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        if not docs:
            return Answer(
                question=question,
                answer="The provided documents do not cover this.",
                citations=[],
                timings_ms=timings,
            )

        context = _format_context(docs)
        # Generate from the condensed standalone query so follow-ups whose phrasing
        # depends on history ("what about their revenue?") are self-contained for the LLM.
        messages = self._build_messages(query, context)

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

    def _retrieval_mode(self) -> str:
        return "hybrid" if isinstance(self.retriever, HybridRetriever) else "dense"

    def answer_with_trace(
        self,
        question: str,
        top_k: int | None = None,
        history: list[Turn] | None = None,
    ) -> tuple[Answer, "_trace.PipelineTrace"]:
        """Answer a question AND return a full pipeline trace (feature F23).

        Same behaviour as :meth:`answer`, but records every stage — condensed query,
        tokenization, retrieved chunks with dense scores, the exact prompt, and the
        answer — so the introspection UI can render how the answer was produced.
        """
        k = top_k or self.top_k
        timings: dict[str, float] = {}

        tc = time.perf_counter()
        query = self._condense(question, history)
        if history:
            timings["condense_ms"] = round((time.perf_counter() - tc) * 1000, 1)
        condensed = bool(history) and query.strip() != question.strip()

        t0 = time.perf_counter()
        docs = self._retrieve(query, k)
        timings["retrieve_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        tok = _trace.tokenize_trace(query)
        score_map = _trace.dense_scores(self.vectorstore, query, max(k, self.fetch_k))
        retrieved = _trace.chunk_traces(docs, score_map)

        if not docs:
            ans = Answer(
                question=question,
                answer="The provided documents do not cover this.",
                citations=[],
                timings_ms=timings,
            )
            tr = _trace.PipelineTrace(
                original_question=question,
                condensed_query=query,
                condensed=condensed,
                tokenization=tok,
                retrieval_mode=self._retrieval_mode(),
                rerank_enabled=not isinstance(self.reranker, NoOpReranker),
                retrieved=[],
                context_char_len=0,
                system_prompt=SYSTEM_PROMPT,
                user_prompt="",
                answer=ans.answer,
                timings_ms=timings,
            )
            return ans, tr

        context = _format_context(docs)
        # Generate from the condensed standalone query so follow-ups whose phrasing
        # depends on history ("what about their revenue?") are self-contained for the LLM.
        messages = self._build_messages(query, context)

        t1 = time.perf_counter()
        response = self.llm.invoke(messages)
        timings["generate_ms"] = round((time.perf_counter() - t1) * 1000, 1)
        text = response.content if isinstance(response.content, str) else str(response.content)

        ans = Answer(
            question=question,
            answer=text.strip(),
            citations=self._citations(text, docs),
            timings_ms=timings,
        )
        tr = _trace.PipelineTrace(
            original_question=question,
            condensed_query=query,
            condensed=condensed,
            tokenization=tok,
            retrieval_mode=self._retrieval_mode(),
            rerank_enabled=not isinstance(self.reranker, NoOpReranker),
            retrieved=retrieved,
            context_char_len=len(context),
            system_prompt=messages[0][1],
            user_prompt=messages[1][1],
            answer=ans.answer,
            timings_ms=timings,
        )
        return ans, tr

    def stream(
        self,
        question: str,
        top_k: int | None = None,
        history: list[Turn] | None = None,
    ):
        """Yield answer tokens, then a final ('citations', [...]) tuple (F06)."""
        k = top_k or self.top_k
        query = self._condense(question, history)
        docs = self._retrieve(query, k)
        if not docs:
            yield ("token", "The provided documents do not cover this.")
            yield ("citations", [])
            return
        messages = self._build_messages(query, _format_context(docs))
        collected = []
        for chunk in self.llm.stream(messages):
            piece = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
            if piece:
                collected.append(piece)
                yield ("token", piece)
        yield ("citations", self._citations("".join(collected), docs))
