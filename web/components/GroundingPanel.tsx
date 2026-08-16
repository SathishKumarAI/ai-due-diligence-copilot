// Renders the F24 grounding report: every claim in the answer, whether the chunk it
// cites actually supports it, and the exact span to look at. The point is that a reader
// verifies a sentence by glancing at a highlighted phrase instead of re-reading a
// 1000-character chunk — and that an invented figure is impossible to miss.
//
// It also renders F27 source conflicts, which are deliberately placed ABOVE the claims.
// Claim verification answers "does the answer match its sources"; when the sources
// disagree with each other, that question has a reassuring answer and a useless one. The
// measured case: a hostile upload asserting 512 months of runway produced a confidently
// cited answer scored "grounded", while the true 12.8 months never surfaced. A reader who
// saw only the claim verdicts would have had no signal at all.
import type { ClaimStatus, ClaimVerdict, GroundingReport } from "@/lib/api";

const STATUS_STYLE: Record<ClaimStatus, { label: string; className: string }> = {
  grounded: { label: "grounded", className: "bg-emerald-500/15 text-emerald-400" },
  weak: { label: "weak", className: "bg-amber-500/15 text-amber-400" },
  unsupported: { label: "unsupported", className: "bg-red-500/15 text-red-400" },
  meta: { label: "not a claim", className: "bg-white/10 muted" },
};

const VERDICT_STYLE: Record<string, string> = {
  grounded: "bg-emerald-500/15 text-emerald-400",
  mixed: "bg-amber-500/15 text-amber-400",
  unsupported: "bg-red-500/15 text-red-400",
  refusal: "bg-sky-500/15 text-sky-400",
  empty: "bg-white/10 muted",
  unverified: "bg-white/10 muted",
};

// Says *why* a verdict came out the way it did, in the reader's terms. Without this the
// panel shows a colour and a percentage and leaves the reader to infer the rule.
function reason(claim: ClaimVerdict): string {
  const pct = Math.round(claim.coverage * 100);
  switch (claim.status) {
    case "meta":
      return "No factual assertion about the documents — a refusal, a hedge or a lead-in. Excluded from the score.";
    case "unsupported":
      return claim.unsupported_figures.length > 0
        ? `A figure here appears nowhere in the cited source. That outranks everything else: ${pct}% of the wording matched, and it still fails.`
        : `Only ${pct}% of this sentence's meaningful words appear in the source it cites.`;
    case "weak":
      return `${pct}% of this sentence's words appear in the cited source — enough to be related, not enough to call it supported. Often paraphrase rather than invention; read the source.`;
    default:
      return `${pct}% of this sentence's meaningful words appear in the source it cites.`;
  }
}

function ConflictBlock({ report }: { report: GroundingReport }) {
  if (report.conflicts.length === 0) return null;
  return (
    <div className="mt-3 rounded-lg border border-red-500/40 bg-red-500/5 p-2">
      <p className="text-[11px] font-semibold text-red-400">
        SOURCES DISAGREE ({report.conflicts.length})
      </p>
      <p className="mt-0.5 text-[11px] muted">
        Two retrieved documents give different values for the same quantity. Checking the
        answer against its sources cannot catch this — whichever the model picked would
        look supported.
      </p>
      <ul className="mt-2 space-y-2">
        {report.conflicts.map((conflict, i) => (
          <li key={i} className="rounded border border-[var(--border)] p-2">
            <p className="text-[10px] uppercase tracking-wide muted">
              {conflict.context.join(" · ")}
            </p>
            <ul className="mt-1 space-y-0.5">
              {conflict.values.map((v, j) => (
                <li key={j} className="flex flex-wrap items-baseline gap-2 text-xs">
                  <span className="font-mono font-semibold text-red-400">{v.value}</span>
                  <span className="font-mono text-[10px] muted">{v.source}</span>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[10px] muted">
        This is a flag, not a judgement — it does not say which value is right. Check the
        sources before using either number.
      </p>
    </div>
  );
}

export function GroundingPanel({ report }: { report: GroundingReport }) {
  const scored = report.claims.filter((c) => c.status !== "meta");

  return (
    <section className="mt-3 rounded-lg border border-[var(--border)] p-3">
      <header className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-semibold tracking-wide">GROUNDING</span>
        <span className="text-[11px] muted">is every claim supported by what it cites?</span>
        <span
          className={`ml-auto rounded px-2 py-0.5 text-[11px] font-semibold ${
            VERDICT_STYLE[report.verdict] ?? "bg-white/10 muted"
          }`}
        >
          {report.verdict}
          {scored.length > 0 && ` · ${Math.round(report.score * 100)}%`}
        </span>
      </header>

      {/* Above the claims deliberately: a conflict invalidates the reassurance the claim
          list would otherwise give. */}
      <ConflictBlock report={report} />

      {report.verdict === "refusal" ? (
        <p className="mt-2 text-sm muted">
          The answer declined rather than asserting anything, so there is nothing to
          verify. That is the guardrail working.
        </p>
      ) : (
        <ol className="mt-3 space-y-2">
          {report.claims.map((claim, i) => {
            const style = STATUS_STYLE[claim.status];
            return (
              <li key={i} className="rounded border border-[var(--border)] p-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${style.className}`}
                  >
                    {style.label}
                  </span>
                  {claim.status !== "meta" && (
                    <span className="font-mono text-[10px] muted">
                      {Math.round(claim.coverage * 100)}% of terms found
                    </span>
                  )}
                  {claim.markers.length > 0 && (
                    <span className="font-mono text-[10px] muted">
                      cites [{claim.markers.join(", ")}]
                    </span>
                  )}
                  {claim.source && (
                    <span className="font-mono text-[10px] muted">{claim.source}</span>
                  )}
                </div>

                <p className="mt-1 text-sm leading-relaxed">{claim.text}</p>

                <p className="mt-1 text-[11px] muted">{reason(claim)}</p>

                {claim.unsupported_figures.length > 0 && (
                  // The headline failure mode for a finance answer: a number that is in
                  // no filing. Called out separately so it cannot be skimmed past.
                  <p className="mt-1 text-[11px] text-red-400">
                    figures not found in the cited source:{" "}
                    <span className="font-mono">
                      {claim.unsupported_figures.join(", ")}
                    </span>
                  </p>
                )}

                {claim.status !== "meta" && claim.missing_terms.length > 0 && (
                  // Computed by the verifier since F24 shipped and never shown. These are
                  // the words that cost the claim its score, so they are the fastest way
                  // to tell paraphrase apart from invention.
                  <p className="mt-1 text-[11px] muted">
                    words not in the source:{" "}
                    <span className="font-mono">
                      {claim.missing_terms.slice(0, 12).join(", ")}
                      {claim.missing_terms.length > 12 && ` +${claim.missing_terms.length - 12} more`}
                    </span>
                  </p>
                )}

                {claim.span_text && (
                  <p className="mt-1 text-[11px] muted">
                    supporting text:{" "}
                    <mark className="rounded bg-[var(--accent)]/25 px-1 text-[inherit]">
                      {claim.span_text}
                    </mark>
                  </p>
                )}
              </li>
            );
          })}
        </ol>
      )}

      <p className="mt-3 text-[10px] leading-relaxed muted">{report.note}</p>
    </section>
  );
}
