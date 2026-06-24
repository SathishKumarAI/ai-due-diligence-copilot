"""Synthetic due-diligence corpus generator (the code used to produce data/).

Generates plausible-looking but ENTIRELY FICTIONAL deal documents (a pitch, a financial
summary, a term sheet, and risk factors for an invented company) so the project runs out
of the box without any real or confidential material. Figures are illustrative only.

Usage:
    python scripts/generate_synthetic_data.py            # writes the default corpus
    python scripts/generate_synthetic_data.py --seed 7   # reproducible variation

Deterministic given a seed: no LLM, no network — templates + a seeded RNG.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DISCLAIMER = "> SYNTHETIC SAMPLE — fictional company/figures for demo/testing only.\n"


def pitch(rng: random.Random) -> tuple[str, str]:
    arr = rng.choice([10.2, 12.4, 15.8])
    prev = round(arr / rng.choice([1.30, 1.39, 1.45]), 1)
    growth = round((arr / prev - 1) * 100)
    concentration = rng.choice([18, 22, 27])
    body = f"""# Acme Robotics — Series B Pitch (synthetic sample)

{DISCLAIMER}
## Company
Acme Robotics builds autonomous warehouse picking robots. Founded 2021, HQ in Austin, TX.

## Traction
- Annual Recurring Revenue (ARR): ${arr}M, up from ${prev}M the prior year ({growth}% YoY growth).
- 27 enterprise customers; net revenue retention of 118%.
- Gross margin: 61%.
- Largest customer represents {concentration}% of ARR (customer concentration risk).

## The ask
Raising a $40M Series B at a $220M post-money valuation.

## Team
- CEO: former operations lead at a major logistics firm.
- The VP of Sales role is currently vacant.
"""
    return "acme_robotics_pitch.md", body


def financials(rng: random.Random) -> tuple[str, str]:
    cash = rng.choice([7.5, 9.2, 11.0])
    burn = rng.choice([0.62, 0.72, 0.85])
    runway = round(cash / burn, 1)
    body = f"""# Acme Robotics — Financial Summary Excerpt (synthetic sample)

{DISCLAIMER}
## Income statement (FY, USD)
- Revenue: $12,400,000
- Gross profit: $7,564,000
- Operating loss: $(6,536,000)
- Net loss: $(6,910,000)

## Balance sheet highlights
- Cash and equivalents: ${cash}M
- Monthly net burn: approximately ${burn}M
- Implied runway at current burn: ~{runway} months

## Notes
- The company has never been profitable and expects losses to continue near term.
"""
    return "acme_10k_excerpt.md", body


def term_sheet(rng: random.Random) -> tuple[str, str]:
    body = """# Acme Robotics — Series B Term Sheet (synthetic sample)

{disc}
- Security: Series B Preferred Stock
- Amount: $40,000,000
- Post-money valuation: $220,000,000
- Liquidation preference: 1x non-participating
- Anti-dilution: broad-based weighted average
- Option pool: 12% post-financing, created pre-money (dilutes existing holders)
- Founder vesting: 4 years, 1-year cliff, reset on close
""".format(disc=DISCLAIMER)
    return "acme_term_sheet.md", body


def risks(rng: random.Random) -> tuple[str, str]:
    body = """# Acme Robotics — Risk Factors (synthetic sample)

{disc}
## Customer concentration
A single customer accounts for 22% of ARR. Loss of this customer would materially
reduce revenue.

## Supply chain
Key actuators are sourced from a single overseas supplier. A disruption could halt
production for an estimated 8-12 weeks.

## Regulatory
European market entry requires CE machinery safety certification (6-9 months, not started).

## Financial
The company is unprofitable and will require additional financing beyond the Series B.
""".format(disc=DISCLAIMER)
    return "acme_risk_factors.md", body


GENERATORS = [pitch, financials, term_sheet, risks]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for gen in GENERATORS:
        name, body = gen(rng)
        (DATA_DIR / name).write_text(body, encoding="utf-8")
        print(f"wrote data/{name}")


if __name__ == "__main__":
    main()
