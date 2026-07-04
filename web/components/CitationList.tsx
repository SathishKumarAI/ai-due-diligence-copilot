import type { Citation } from "@/lib/api";

// The traceable source list under an answer. Each card is anchored so the inline
// [n] chips can scroll to it.
export function CitationList({
  citations,
  idPrefix,
}: {
  citations: Citation[];
  idPrefix: string;
}) {
  if (citations.length === 0) return null;
  return (
    <div className="mt-3">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide muted">
        Sources ({citations.length})
      </p>
      <ul className="space-y-2">
        {citations.map((c) => (
          <li
            key={c.marker}
            id={`${idPrefix}-cite-${c.marker}`}
            className="surface scroll-mt-24 rounded-lg border p-3 text-sm"
          >
            <div className="flex items-center gap-2">
              <span className="inline-flex h-5 min-w-5 items-center justify-center rounded bg-[var(--accent)] px-1 text-[11px] font-semibold text-white">
                {c.marker}
              </span>
              <span className="font-medium">{c.source}</span>
              {c.page != null && <span className="muted">· p.{c.page}</span>}
            </div>
            <p className="mt-1.5 muted">{c.snippet}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
