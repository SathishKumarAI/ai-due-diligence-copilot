// Renders an answer, turning each [n] marker into a styled citation chip. Keeps the
// component dependency-free (no markdown lib) — preserves line breaks, highlights cites.
export function AnswerText({
  text,
  onCite,
  streaming = false,
}: {
  text: string;
  onCite?: (marker: number) => void;
  streaming?: boolean;
}) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className={`whitespace-pre-wrap leading-relaxed ${streaming ? "caret" : ""}`}>
      {parts.map((part, i) => {
        const m = /^\[(\d+)\]$/.exec(part);
        if (!m) return <span key={i}>{part}</span>;
        const marker = Number(m[1]);
        return (
          <button
            key={i}
            onClick={() => onCite?.(marker)}
            className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded bg-[var(--accent)] px-1 align-baseline text-[11px] font-semibold text-white transition hover:opacity-80"
            title={`Jump to source ${marker}`}
          >
            {marker}
          </button>
        );
      })}
    </p>
  );
}
