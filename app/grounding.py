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
    # Absence claims. Measured over the eval set: "The provided documents do not
    # explicitly state the potential financial impact" was scored *unsupported* at 0.20
    # coverage, which reads as "the model made this up" when the model did the opposite -
    # it declined, correctly, and said so. A lexical checker cannot verify an absence
    # anyway: there is no span in the source that proves something is missing from it.
    # Scoring it as a failed claim is worse than not scoring it.
    r"|do(?:es)? not (?:explicitly |specifically )?(?:state|specify|mention|say|indicate"
    r"|detail|disclose|cover|include|provide)"
    r"|don't (?:explicitly |specifically )?(?:state|specify|mention|say)"
    r"|if you'd like|if you would like|would you like|let me know)\b",
    re.IGNORECASE,
)

# Split on sentence enders only when the next chunk starts like a new sentence, so
# "$12.4M." and "Inc." do not fragment a claim mid-figure.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\[])")
# Citation markers. Models group them as "[1, 2, 3]" and "[1][2]" as often as they
# write "[1]", and matching only the last form is not cosmetic: an answer citing
# "[1, 2, 3, 4, 5]" parsed as *no markers at all*, which sent _citations down its
# fallback path (returning every retrieved chunk) and left the digits in the claim
# text for the grounding scorer, tanking its coverage. Observed live.
_MARKER_RE = re.compile(r"\[\s*(\d+(?:\s*[,;]\s*\d+)*)\s*\]")


def parse_markers(text: str) -> list[int]:
    """Every citation index in ``text``, flattening grouped markers like "[1, 2, 3]"."""
    out: list[int] = []
    for group in _MARKER_RE.findall(text):
        out.extend(int(n) for n in re.split(r"[,;]", group) if n.strip())
    return out


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
class FigureConflict:
    """The same quantity, given two different values by two different retrieved chunks."""

    context: list[str] = field(default_factory=list)  # shared words naming the quantity
    values: list[dict] = field(default_factory=list)  # {value, source, snippet}


@dataclass
class GroundingReport:
    """Verdicts for every claim, plus the totals a caller can gate on."""

    claims: list[ClaimVerdict] = field(default_factory=list)
    # Disagreements *between the sources themselves*, which claim-level verification is
    # structurally blind to. See find_conflicts.
    conflicts: list[FigureConflict] = field(default_factory=list)
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


def asserts_nothing(answer: str) -> bool:
    """True when the answer makes no factual claim about the corpus.

    Covers the explicit guardrail *and* soft refusals — "I cannot provide an estimate…",
    a bare "Here are the answers:" — where every sentence is a hedge, an offer of help or
    a lead-in. Used by the engine to decide whether attaching citations would be honest:
    a citation asserts that a source supports something, and an answer that supports
    nothing must not carry any.
    """
    if is_refusal(answer):
        return True
    claims = split_claims(answer)
    if not claims:
        return True
    return all(
        _META_RE.search(text) or text.rstrip().endswith(":") or not _content_terms(text)
        for text, _ in claims
    )


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
            markers = parse_markers(sentence)
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


_CONTEXT_WINDOW = 6  # content words either side of a figure that name what it measures
_CONTEXT_OVERLAP = 0.34  # Jaccard above which two figures are talking about the same thing


def _unit(token: str) -> str:
    """Coarse unit signature, so a percentage is never compared against a dollar amount."""
    if token.endswith("%"):
        return "pct"
    if token.startswith("$"):
        return "money"
    return "plain"


def _numeric_value(token: str) -> float | None:
    cleaned = token.strip("$%").replace(",", "")
    # Trailing magnitude suffixes the tokenizer keeps attached ("12.4m").
    scale = {"k": 1e3, "m": 1e6, "b": 1e9}.get(cleaned[-1:], None)
    if scale is not None:
        cleaned = cleaned[:-1]
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value * scale if scale else value


def _looks_like_a_year(token: str, value: float | None) -> bool:
    """Years share context with everything nearby and would swamp the signal."""
    return (
        _unit(token) == "plain" and token.isdigit() and value is not None and 1900 <= value <= 2100
    )


def _figures_with_context(doc: Document) -> list[tuple[str, float, set[str]]]:
    """Every figure in a chunk, paired with the content words that say what it measures."""
    tokens = _tokenize(doc.page_content)
    out: list[tuple[str, float, set[str]]] = []
    for i, token in enumerate(tokens):
        if not _is_figure(token):
            continue
        value = _numeric_value(token)
        if value is None or _looks_like_a_year(token, value):
            continue
        lo, hi = max(0, i - _CONTEXT_WINDOW), min(len(tokens), i + _CONTEXT_WINDOW + 1)
        context = {
            t
            for t in tokens[lo:i] + tokens[i + 1 : hi]
            if t not in _STOPWORDS and not _is_figure(t)
        }
        if context:
            out.append((token, value, context))
    return out


def find_conflicts(docs: list[Document]) -> list[FigureConflict]:
    """Figures that describe the same quantity but disagree, across retrieved chunks.

    This exists because claim-level verification cannot catch the attack that actually
    worked against this system. F24 checks an answer against *the chunks that were
    retrieved for it*, so when an attacker controls what gets retrieved, a false figure is
    faithfully "grounded" — measured live: an uploaded document asserting 512 months of
    runway produced a confidently cited answer, while the true 12.8 months never surfaced.
    Verification against the sources cannot help when the sources are the problem.

    What can help is noticing that the retrieved set *disagrees with itself*. Two chunks
    saying "runway ... 12.8 months" and "runway ... 512 months" is a fact about the corpus,
    visible without trusting either one.

    Deliberately a flag, not a judgement: it says "these two disagree, look", never which
    is right. Comparison is restricted to figures sharing a unit signature and enough
    surrounding vocabulary, and years are skipped — they sit near everything and would
    bury the real signal.
    """
    entries: list[tuple[str, float, set[str], Document]] = []
    for doc in docs:
        for token, value, context in _figures_with_context(doc):
            entries.append((token, value, context, doc))

    conflicts: list[FigureConflict] = []
    used: set[int] = set()
    for i, (tok_a, val_a, ctx_a, doc_a) in enumerate(entries):
        if i in used:
            continue
        group = [(tok_a, val_a, doc_a)]
        shared = set(ctx_a)
        source_a = str(doc_a.metadata.get("source", "unknown"))
        for j in range(i + 1, len(entries)):
            tok_b, val_b, ctx_b, doc_b = entries[j]
            if j in used or _unit(tok_a) != _unit(tok_b) or val_a == val_b:
                continue
            # Only across sources. Two figures inside one document are that author's own
            # prose, not a contradiction between sources, and neighbouring metrics share
            # far too much vocabulary: "Gross margin: 61%. Net revenue retention of 118%."
            # matched at overlap 1.0 and was reported as a conflict between two entirely
            # different measures. A document that genuinely contradicts itself is not
            # caught by this, which is the honest cost of removing that whole false-
            # positive class.
            if str(doc_b.metadata.get("source", "unknown")) == source_a:
                continue
            overlap = len(ctx_a & ctx_b) / len(ctx_a | ctx_b)
            if overlap < _CONTEXT_OVERLAP:
                continue
            group.append((tok_b, val_b, doc_b))
            shared &= ctx_b
            used.add(j)
        if len(group) < 2:
            continue
        used.add(i)
        conflicts.append(
            FigureConflict(
                context=sorted(shared),
                values=[
                    {
                        "value": tok,
                        "source": str(doc.metadata.get("source", "unknown")),
                        "snippet": " ".join(doc.page_content.split())[:160],
                    }
                    for tok, _, doc in group
                ],
            )
        )
    return conflicts


def verify_answer(answer: str, docs: list[Document]) -> GroundingReport:
    """Verify every claim in an answer against the chunks that were retrieved for it."""
    report = GroundingReport()
    # Computed regardless of what the answer said. A contradiction between two sources is
    # a property of the retrieved set, so it is worth surfacing even when the model
    # declined to answer - arguably especially then.
    report.conflicts = find_conflicts(docs)

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
