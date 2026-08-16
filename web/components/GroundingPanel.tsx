// Renders the F24 grounding report: every claim in the answer, whether the chunk it
// cites actually supports it, and the exact span to look at. The point is that a reader
// verifies a sentence by glancing at a highlighted phrase instead of re-reading a
// 1000-character chunk — and that an invented figure is impossible to miss.
import type { ClaimStatus, GroundingReport } from "@/lib/api";

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
                  {claim.source && (
                    <span className="font-mono text-[10px] muted">{claim.source}</span>
                  )}
                </div>

                <p className="mt-1 text-sm leading-relaxed">{claim.text}</p>

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
