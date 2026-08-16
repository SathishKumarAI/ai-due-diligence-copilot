"""Synthetic due-diligence corpus generator — the code that produces ``data/``.

Writes plausible-looking but ENTIRELY FICTIONAL deal documents (a pitch, a financial
summary, a term sheet, and risk factors for an invented company) so the project runs out
of the box without any real or confidential material. Figures are illustrative only.

Usage:
    python scripts/generate_synthetic_data.py           # rewrite data/ from these templates
    python scripts/generate_synthetic_data.py --check   # verify data/ matches, write nothing

**Output is fixed, not random.** It used to take a ``--seed`` and pick figures with a
seeded RNG, which turned out to be a footgun in two directions at once:

- The corpus drifted away from the generator. ``data/`` was later hand-edited with content
  the templates never had — pre-money valuation, board composition, pro-rata rights, cost
  of revenue, total debt, and two whole risk sections. Anyone running the generator would
  have silently *deleted* all of it, including facts ``eval/qa_dataset.jsonl`` asks about.
- Even undrifted, a different seed rewrote the very numbers the eval set checks. The
  ground-truth answers name $12.4M ARR, 39% YoY, 12.8 months of runway, a $220M
  post-money. ``--seed 7`` invalidated every one of them, and nothing would have said so —
  the eval would simply have started failing as though retrieval had regressed.

Randomised variation was never something this project needed; a stable corpus the eval
set can be written against is. So the templates below *are* ``data/``, byte for byte, and
``tests/test_synthetic_data.py`` fails the build if the two ever diverge again. Use
``--check`` to ask the same question without touching the filesystem.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PITCH = """# Acme Robotics — Series B Pitch (synthetic sample)

## Company
Acme Robotics builds autonomous warehouse picking robots. Founded 2021,
headquartered in Austin, TX. 84 full-time employees as of Q4 2025.

## Traction
- Annual Recurring Revenue (ARR): $12.4M, up from $8.9M the prior year (39% YoY growth).
- 27 enterprise customers; net revenue retention of 118%.
- Gross margin: 61%.
- Largest customer represents 22% of ARR (customer concentration risk).

## The ask
Raising a $40M Series B at a $220M post-money valuation to expand manufacturing
capacity and enter the European market.

## Use of funds
- 45% manufacturing scale-up
- 30% sales & marketing
- 25% R&D (next-gen gripper)

## Team
- CEO: former operations lead at a major logistics firm.
- CTO: robotics PhD, 6 prior patents.
- The VP of Sales role is currently vacant.
"""

FINANCIALS = """# Acme Robotics — Financial Summary Excerpt (synthetic sample)

## Income statement (FY2025, USD)
- Revenue: $12,400,000
- Cost of revenue: $4,836,000
- Gross profit: $7,564,000
- Operating expenses: $14,100,000
- Operating loss: $(6,536,000)
- Net loss: $(6,910,000)

## Balance sheet highlights
- Cash and equivalents: $9,200,000
- Total debt: $3,000,000 (venture debt facility, matures 2027)
- Monthly net burn: approximately $720,000
- Implied runway at current burn: ~12.8 months

## Notes
- Revenue is recognized ratably over the subscription term.
- The company has never been profitable and expects losses to continue near term.
"""

TERM_SHEET = """# Acme Robotics — Series B Term Sheet (synthetic sample)

- Security: Series B Preferred Stock
- Amount: $40,000,000
- Pre-money valuation: $180,000,000
- Post-money valuation: $220,000,000
- Liquidation preference: 1x non-participating
- Anti-dilution: broad-based weighted average
- Board: 5 seats — 2 founders, 2 investors, 1 independent
- Pro-rata rights: yes, for investors above $5M
- Option pool: 12% post-financing, created pre-money (dilutes existing holders)
- Founder vesting: 4 years, 1-year cliff, reset on close
"""

RISKS = """# Acme Robotics — Risk Factors (synthetic sample)

## Customer concentration
A single customer accounts for 22% of ARR. Loss of this customer would materially
reduce revenue.

## Supply chain
Key actuators are sourced from a single overseas supplier. A disruption could halt
production for an estimated 8–12 weeks.

## Competition
Two larger incumbents have announced competing autonomous picking products with
deeper balance sheets.

## Regulatory
European market entry is subject to CE machinery safety certification, which has
historically taken 6–9 months and is not yet started.

## Key person
The CTO holds the core gripper patents personally; the assignment to the company is
documented but the VP of Sales seat is vacant, straining go-to-market execution.

## Financial
The company is unprofitable with ~12.8 months of runway and will require additional
financing beyond the Series B.
"""

CORPUS: dict[str, str] = {
    "acme_robotics_pitch.md": PITCH,
    "acme_10k_excerpt.md": FINANCIALS,
    "acme_term_sheet.md": TERM_SHEET,
    "acme_risk_factors.md": RISKS,
}


def expected_bytes(body: str) -> bytes:
    """The exact bytes a template must occupy on disk, on every platform."""
    return body.encode("utf-8")


def check() -> list[str]:
    """Names of corpus files missing from ``data/`` or differing from the templates."""
    bad = []
    for name, body in CORPUS.items():
        path = DATA_DIR / name
        # Compared as bytes, deliberately. Reading as text would decode CRLF back to "\n"
        # under universal newlines and call a CRLF copy of the corpus identical, which is
        # the one difference most likely to appear and the one that rechunks every file.
        if not path.exists() or path.read_bytes() != expected_bytes(body):
            bad.append(name)
    return bad


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the synthetic due-diligence corpus.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify data/ matches these templates and exit non-zero if not; write nothing",
    )
    # Explicit argv so callers (tests) are not parsing whatever is in sys.argv.
    args = parser.parse_args(argv)

    if args.check:
        bad = check()
        for name in bad:
            print(f"drifted: data/{name}")
        print("data/ matches the generator" if not bad else f"{len(bad)} file(s) differ")
        return 1 if bad else 0

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, body in CORPUS.items():
        # write_bytes, not write_text: text mode translates "\n" to CRLF on Windows, so
        # the same command would produce a different corpus depending on who ran it.
        (DATA_DIR / name).write_bytes(expected_bytes(body))
        print(f"wrote data/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
