"""Tests for claim-level grounding verification (F24, ``app/grounding.py``)."""

from __future__ import annotations

from langchain_core.documents import Document

from app.grounding import (
    GROUNDED_COVERAGE,
    is_refusal,
    split_claims,
    verify_answer,
    verify_claim,
)

PITCH = Document(
    page_content=(
        "# Acme Robotics - Series B Pitch\n"
        "Annual Recurring Revenue (ARR): $12.4M, up from $8.9M the prior year. "
        "Gross margin is 61%. Headquartered in Austin, TX with 84 employees."
    ),
    metadata={"source": "acme_robotics_pitch.md", "page": None},
)
RISKS = Document(
    page_content=(
        "# Acme Robotics - Risk Factors\n"
        "A single customer accounts for 22% of ARR. Key actuators are sourced from a "
        "single overseas supplier."
    ),
    metadata={"source": "acme_risk_factors.md", "page": None},
)
DOCS = [PITCH, RISKS]


def test_claim_supported_by_its_cited_chunk_is_grounded():
    v = verify_claim("ARR is $12.4M, up from $8.9M the prior year", [1], DOCS)
    assert v.status == "grounded", v
    assert v.coverage >= GROUNDED_COVERAGE
    assert v.source == "acme_robotics_pitch.md"
    assert not v.unsupported_figures


def test_invented_figure_is_unsupported_even_when_the_wording_matches():
    # The failure this catches: the single most dangerous RAG error in a finance
    # answer is a number that appears in no filing. Every word here except the figure
    # comes straight from the source, so term coverage alone would pass it.
    v = verify_claim("ARR is $99.9M, up from $8.9M the prior year", [1], DOCS)
    assert v.status == "unsupported", v
    assert "$99.9m" in v.unsupported_figures


def test_percentage_figures_are_checked_whole():
    # Depends on the retrieval tokenizer keeping "22%" intact. If it degraded to "22",
    # this claim would match the "22" inside the source and score as grounded.
    grounded = verify_claim("A single customer accounts for 22% of ARR", [2], DOCS)
    assert grounded.status == "grounded", grounded

    invented = verify_claim("A single customer accounts for 87% of ARR", [2], DOCS)
    assert invented.status == "unsupported", invented
    assert "87%" in invented.unsupported_figures


def test_claim_about_something_absent_is_unsupported():
    v = verify_claim("The company operates a manufacturing plant in Vietnam", [1], DOCS)
    assert v.status == "unsupported", v


def test_span_points_at_the_supporting_text():
    v = verify_claim("Gross margin is 61%", [1], DOCS)
    assert v.status == "grounded"
    assert "gross margin is 61%" in v.span_text.lower()
    assert v.span_start is not None
    assert PITCH.page_content[v.span_start : v.span_end] == v.span_text


def test_marker_out_of_range_falls_back_instead_of_crashing():
    # The model citing [9] when four chunks were retrieved must not raise.
    v = verify_claim("Gross margin is 61%", [9], DOCS)
    assert v.status == "grounded"


def test_split_claims_keeps_figures_and_strips_markers():
    claims = split_claims("ARR is $12.4M [1]. Gross margin is 61% [1].")
    assert [c for c, _ in claims] == ["ARR is $12.4M.", "Gross margin is 61%."]
    assert [m for _, m in claims] == [[1], [1]]


def test_split_claims_treats_each_bullet_as_its_own_claim():
    claims = split_claims("- Customer concentration [1]\n- Supply chain risk [2]")
    assert [c for c, _ in claims] == ["Customer concentration", "Supply chain risk"]
    assert [m for _, m in claims] == [[1], [2]]


def test_refusal_is_not_scored_as_an_unsupported_claim():
    # A refusal is the system working. Scoring it as a hallucination would invert the
    # signal and punish the behaviour the product promises.
    answer = "The provided documents do not cover this. There is no mention of Tesla."
    assert is_refusal(answer)
    report = verify_answer(answer, DOCS)
    assert report.verdict == "refusal"
    assert report.claims == []


def test_report_totals_and_verdict():
    answer = "ARR is $12.4M [1]. The company runs a plant in Vietnam [1]."
    report = verify_answer(answer, DOCS)
    assert len(report.claims) == 2
    assert report.grounded == 1
    assert report.unsupported == 1
    assert report.verdict == "unsupported"
    assert report.score == 0.5


def test_all_grounded_answer_reports_grounded():
    answer = "ARR is $12.4M [1]. Gross margin is 61% [1]."
    report = verify_answer(answer, DOCS)
    assert report.verdict == "grounded"
    assert report.score == 1.0


def test_no_documents_does_not_crash():
    report = verify_answer("ARR is $12.4M [1].", [])
    assert report.claims[0].status == "unsupported"


# --- API surface (F24) -------------------------------------------------------------


def test_ask_returns_no_grounding_unless_asked(client):
    body = client.post("/v1/ask", json={"question": "What is the ARR?"}).json()
    assert body["grounding"] is None


def test_ask_with_verify_returns_a_grounding_report(client):
    body = client.post("/v1/ask", json={"question": "What is the ARR?", "verify": True}).json()
    report = body["grounding"]
    assert report is not None
    assert report["verdict"] in {"grounded", "mixed", "unsupported", "refusal", "empty"}
    assert isinstance(report["claims"], list)
    assert report["note"]


def test_verify_bypasses_the_answer_cache(client):
    # The cached payload predates verification, so replaying it under verify=true would
    # report "unverified" for an answer that was never checked.
    q = {"question": "What is the gross margin?"}
    client.post("/v1/ask", json=q)  # populate the cache
    verified = client.post("/v1/ask", json={**q, "verify": True}).json()
    assert verified["cached"] is False
    assert verified["grounding"] is not None


# --- soft refusals (F24) -----------------------------------------------------------


def test_hedges_are_not_scored_as_unsupported_claims():
    # Observed live: asked to forecast 2027 revenue the model declined without using the
    # guardrail phrase, and every sentence scored "unsupported" — reading like
    # fabrication when the model was behaving correctly.
    answer = (
        "I cannot provide an estimate of the company's revenue for 2027 as it is not "
        "mentioned in any of the provided passages. If you'd like to know more about "
        "the company's financials, let me know."
    )
    report = verify_answer(answer, DOCS)
    assert report.unsupported == 0, [c.status for c in report.claims]
    assert report.verdict == "refusal"


def test_a_real_claim_alongside_a_hedge_is_still_scored():
    answer = "I cannot forecast 2027. Gross margin is 61% [1]."
    report = verify_answer(answer, DOCS)
    assert report.meta == 1
    assert report.grounded == 1
    assert report.score == 1.0  # the hedge is excluded from the denominator
    assert report.verdict == "grounded"


# --- grouped citation markers ------------------------------------------------------


def test_parse_markers_handles_every_form_a_model_emits():
    from app.grounding import parse_markers

    # The failure this catches: llama3.1:8b wrote "[1, 2, 3, 4, 5]" and the old regex
    # \[(\d+)\] matched none of it. _citations then took its no-markers fallback and
    # returned every retrieved chunk, and the digits stayed in the claim text and
    # dragged its coverage down. Observed against a live answer.
    assert parse_markers("x [1] y") == [1]
    assert parse_markers("x [1, 2, 3] y") == [1, 2, 3]
    assert parse_markers("x [1][2] y") == [1, 2]
    assert parse_markers("x [1; 2] y") == [1, 2]
    assert parse_markers("x [ 3 ] y") == [3]
    assert parse_markers("no markers here") == []


def test_grouped_markers_are_stripped_from_the_claim_text():
    claims = split_claims("Runway is 512 months [1, 2, 3, 4, 5].")
    assert claims == [("Runway is 512 months.", [1, 2, 3, 4, 5])]


def test_grouped_markers_produce_one_citation_each(fake_engine):
    fake_engine.llm.reply = "Everything agrees [1, 2]."
    cites = fake_engine.answer("q").citations
    assert [c.marker for c in cites] == [1, 2]
