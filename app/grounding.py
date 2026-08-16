"""Claim-level grounding verification (feature F24).

F23 shows *which chunks* were put in front of the model. It cannot show whether the
answer actually used them — a `[1]` marker is the model's own assertion, and nothing
checks it. This module closes that gap: it splits an answer into claims and, for each
one, locates the supporting span inside the chunk it cites, so a reader verifies a
sentence by looking at a highlighted phrase rather than re-reading a 1000-character
chunk.

Design notes:

- **No new dependency and no second LLM call.** Verification that costs another
  generation is verification nobody runs on every answer. Scoring is lexical and
  deterministic, so it is cheap enough to attach to any response and produces the same
  verdict every time — which is what makes it usable as a test oracle too.
- **It reuses ``retrieval._tokenize``**, deliberately. That tokenizer keeps ``$12.4m``
  and ``39%`` whole, so a figure in a claim is compared as a figure rather than
  decomposed into a bare number that would match any digit in the source.
- **Figures are checked separately and harder than prose.** Across every domain this
  engine serves, the dangerous failure is not clumsy wording but a number that appears
  in no source document — a revenue figure, a dose, a timeout. Any token containing a
  digit that is absent from the cited chunk marks the claim unsupported regardless of
  how well the surrounding words match.

This is a lexical grounding check, not an entailment model: it answers "is this claim's
material present in the source it cites", not "does the source logically entail it". A
claim that inverts the source's meaning while reusing its vocabulary can still score as
grounded. It is a strong smoke detector, not a proof.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from langchain_core.documents import Document

from app.retrieval import _tokenize

# The exact guardrail emitted by RagEngine when nothing was retrieved, and the phrasing
# the system prompt tells the model to use when the corpus cannot answer. A refusal is
# not an unsupported claim, and must not be scored as one.
REFUSAL_PREFIX = "the provided documents do not cover this"

# Function words carry no evidential weight; keeping them would let a claim score well
# purely for sharing English with the source.
_STOPWORDS = frozenset(
    """
    a an the and or but if then than that this these those of in on at to for from by
    with without into over under is are was were be been being am do does did doing
    have has had having it its as not no nor so such only own same too very can will
    just should now about above below up down out off again further once here there
    when where why how all any both each few more most other some what which who whom
    """.split()
) | frozenset(
    # Discourse words that describe the *act of citing* rather than any evidence.
    # Measured: "However, I can note that the passage mentions a venture debt facility
    # maturing in 2027" scored 0.35 and was called unsupported purely because "however",
    # "note", "passage" and "mentions" are absent from the chunk — while every word that
    # carried the actual assertion was present. Scoring framing as evidence penalises a
    # claim for the way the model introduced it.
    """
    passage passages document documents context source sources chunk excerpt
    mention mentions mentioned note notes noted state states stated say says
    provide provides provided according based given show shows shown indicate
    indicates answer answers question questions summary following here
    """.split()
)

GROUNDED_COVERAGE = 0.70
WEAK_COVERAGE = 0.40

# Sentences where the assistant talks about its own inability, or offers a follow-up,
# assert nothing about the corpus. Observed live: asked to forecast 2027 revenue, the
# model produced a *soft* refusal that never used the guardrail phrase, and all three
# sentences scored "unsupported" — reading like fabrication when the model was in fact
# declining correctly. Scoring those as claims makes the metric loudest exactly where it
# should be reassuring. Deliberately a small, explicit phrase list rather than a clever
# heuristic: a wrong guess here silently discards a real claim from the score.
_META_RE = re.compile(
    r"\b(?:i cannot|i can't|i am unable|i'm unable|cannot provide|can't provide"
    r"|not mentioned|no mention|not provided|no information|do not have|don't have"
    r"|if you'd like|if you would like|would you like|let me know)\b",
    re.IGNORECASE,
)

# Split on sentence enders only when the next chunk starts like a new sentence, so
# "$12.4M." and "Inc." do not fragment a claim mid-figure.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\[])")
_MARKER_RE = re.compile(r"\[(\d+)\]")
_BULLET_PREFIX = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


@dataclass
class ClaimVerdict:
    """One claim from the answer, and what the cited source does or does not support."""

    text: str
    markers: list[int] = field(default_factory=list)
    status: str = "unsupported"  # grounded | weak | unsupported
    coverage: float = 0.0
    missing_terms: list[str] = field(default_factory=list)
    unsupported_figures: list[str] = field(default_factory=list)
    source: str | None = None
    span_text: str = ""
    span_start: int | None = None
    span_end: int | None = None


@dataclass
class GroundingReport:
    """Verdicts for every claim, plus the totals a caller can gate on."""

    claims: list[ClaimVerdict] = field(default_factory=list)
    grounded: int = 0
    weak: int = 0
    unsupported: int = 0
    meta: int = 0  # hedges and offers of help — excluded from the score entirely
    score: float = 0.0
    verdict: str = "unverified"  # grounded | mixed | unsupported | refusal | empty
    note: str = (
        "Lexical grounding: checks whether each claim's terms and figures appear in the "
        "chunk it cites. It is not an entailment model — wording that reuses the "
        "source's vocabulary while inverting its meaning can still score as grounded."
    )


def is_refusal(answer: str) -> bool:
    """True when the answer is the corpus-cannot-answer guardrail rather than a claim."""
    return answer.strip().lower().startswith(REFUSAL_PREFIX)


def split_claims(answer: str) -> list[tuple[str, list[int]]]:
    """Break an answer into (claim text, cited markers) pairs.

    Splits on line breaks first so bulleted answers yield one claim per bullet, then on
    sentence boundaries within each line. Markers are recorded and stripped, so scoring
    compares prose to prose.
    """
    claims: list[tuple[str, list[int]]] = []
    for raw_line in answer.splitlines():
        line = _BULLET_PREFIX.sub("", raw_line).strip()
        if not line:
            continue
        for sentence in _SENTENCE_SPLIT.split(line):
            markers = [int(m) for m in _MARKER_RE.findall(sentence)]
            text = _tidy(_MARKER_RE.sub("", sentence))
            if text:
                claims.append((text, markers))
    return claims


def _tidy(text: str) -> str:
    """Close the gap a stripped ``[n]`` leaves behind ("$12.4M ." -> "$12.4M.")."""
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"\s+([.,;:!?])", r"\1", text).strip()


def _content_terms(text: str) -> list[str]:
    return [t for t in _tokenize(text) if t not in _STOPWORDS]


def _is_figure(token: str) -> bool:
    return any(ch.isdigit() for ch in token)


def _best_span(claim: str, source: str) -> tuple[str, int | None, int | None]:
    """Longest contiguous overlap between claim and source, for highlighting.

    Purely presentational — it tells a reader *where* to look. The verdict comes from
    term coverage, which survives paraphrase; the longest common block does not.
    """
    matcher = SequenceMatcher(None, claim.lower(), source.lower(), autojunk=False)
    match = matcher.find_longest_match(0, len(claim), 0, len(source))
    if match.size < 12:  # shorter than this is a coincidence, not evidence
        return "", None, None
    return source[match.b : match.b + match.size], match.b, match.b + match.size


def _score_claim(claim: str, doc: Document) -> tuple[float, list[str], list[str]]:
    terms = _content_terms(claim)
    if not terms:
        return 1.0, [], []
    present = set(_tokenize(doc.page_content))
    missing = [t for t in terms if t not in present]
    figures = [t for t in missing if _is_figure(t)]
    coverage = (len(terms) - len(missing)) / len(terms)
    return coverage, missing, figures


def verify_claim(claim: str, markers: list[int], docs: list[Document]) -> ClaimVerdict:
    """Score one claim against the chunks it cites, or against all of them if it cites none."""
    verdict = ClaimVerdict(text=claim, markers=list(markers))
    # A sentence ending in a colon introduces the answer, it does not assert anything
    # ("Here are the answers to your question:"). Structural, so it needs no phrase list.
    if _META_RE.search(claim) or claim.rstrip().endswith(":"):
        verdict.status = "meta"
        return verdict
    if not _content_terms(claim):
        # Nothing but stopwords and framing — no assertion to check.
        verdict.status = "meta"
        return verdict
    if not docs:
        return verdict

    # Markers are 1-based positions in the retrieved order, exactly as _format_context
    # numbered them for the prompt. An out-of-range marker is itself a finding: the
    # model invented a source number.
    cited = [docs[m - 1] for m in markers if 1 <= m <= len(docs)]
    candidates = cited or docs

    best: tuple[float, list[str], list[str], Document] | None = None
    for doc in candidates:
        coverage, missing, figures = _score_claim(claim, doc)
        if best is None or coverage > best[0]:
            best = (coverage, missing, figures, doc)
    assert best is not None
    coverage, missing, figures, doc = best

    verdict.coverage = round(coverage, 3)
    verdict.missing_terms = missing
    verdict.unsupported_figures = figures
    verdict.source = doc.metadata.get("source")
    verdict.span_text, verdict.span_start, verdict.span_end = _best_span(claim, doc.page_content)

    if figures:
        # A number that appears nowhere in the cited chunk outranks every other signal.
        verdict.status = "unsupported"
    elif coverage >= GROUNDED_COVERAGE:
        verdict.status = "grounded"
    elif coverage >= WEAK_COVERAGE:
        verdict.status = "weak"
    else:
        verdict.status = "unsupported"
    return verdict


def verify_answer(answer: str, docs: list[Document]) -> GroundingReport:
    """Verify every claim in an answer against the chunks that were retrieved for it."""
    report = GroundingReport()

    if is_refusal(answer):
        report.verdict = "refusal"
        report.score = 1.0
        return report

    for text, markers in split_claims(answer):
        report.claims.append(verify_claim(text, markers, docs))

    if not report.claims:
        report.verdict = "empty"
        return report

    report.grounded = sum(c.status == "grounded" for c in report.claims)
    report.weak = sum(c.status == "weak" for c in report.claims)
    report.unsupported = sum(c.status == "unsupported" for c in report.claims)
    report.meta = sum(c.status == "meta" for c in report.claims)

    scored = len(report.claims) - report.meta
    if scored == 0:
        # Every sentence was a hedge: a soft refusal the guardrail prefix never matches,
        # which is the same outcome as an explicit refusal and must read as one.
        report.verdict = "refusal"
        report.score = 1.0
        return report

    report.score = round(report.grounded / scored, 3)
    if report.unsupported:
        report.verdict = "unsupported"
    elif report.weak:
        report.verdict = "mixed"
    else:
        report.verdict = "grounded"
    return report
