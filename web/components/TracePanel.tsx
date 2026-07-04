"use client";

import { useState } from "react";
import type { PipelineTrace } from "@/lib/api";

/**
 * Pipeline introspection panel (feature F23).
 *
 * Renders how an answer was produced so a viewer can *see* the RAG pipeline:
 * question → (condense) → tokenize → retrieve (with scores) → prompt → answer.
 */
export function TracePanel({ trace }: { trace: PipelineTrace }) {
  const stages = [
    "question",
    ...(trace.condensed ? ["condense"] : []),
    "tokenize",
    trace.retrieval_mode === "hybrid" ? "retrieve (dense+BM25)" : "retrieve (dense)",
    ...(trace.rerank_enabled ? ["rerank"] : []),
    "prompt",
    "answer",
  ];

  return (
    <div className="surface mt-3 rounded-xl border p-4 text-sm">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide muted">
          Pipeline trace
        </span>
        <span className="text-xs muted">how this answer was built</span>
      </div>

      {/* stage strip */}
      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        {stages.map((s, i) => (
          <span key={s} className="flex items-center gap-1.5">
            <span className="rounded-md border px-2 py-0.5 text-xs" style={{ borderColor: "var(--border)" }}>
              {s}
            </span>
            {i < stages.length - 1 && <span className="muted">→</span>}
          </span>
        ))}
      </div>

      {trace.condensed && (
        <Section title="Condensed query (F19)">
          <p className="muted">Follow-up rewritten to a standalone query for retrieval:</p>
          <p className="mt-1 font-mono text-xs">{trace.condensed_query}</p>
        </Section>
      )}

      <Section title={`Tokenization — ${trace.tokenization.token_count} tokens`}>
        <div className="mb-2 flex flex-wrap gap-1">
          {trace.tokenization.tokens.map((t, i) => (
            <span
              key={`${t}-${i}`}
              className="rounded bg-[var(--accent)]/10 px-1.5 py-0.5 font-mono text-xs"
            >
              {t}
            </span>
          ))}
        </div>
        <p className="text-xs muted">
          {trace.tokenization.char_count} chars · {trace.tokenization.word_count} words ·{" "}
          {trace.tokenization.tokenizer}
        </p>
        <p className="mt-1 text-xs muted">{trace.tokenization.note}</p>
      </Section>

      <Section
        title={`Retrieved ${trace.retrieved.length} chunks — ${trace.retrieval_mode}${
          trace.rerank_enabled ? " + rerank" : ""
        }`}
      >
        <div className="space-y-2">
          {trace.retrieved.map((c) => (
            <ChunkRow key={c.rank} chunk={c} all={trace.retrieved} />
          ))}
        </div>
      </Section>

      <Collapsible title={`Prompt sent to the model (${trace.context_char_len} ctx chars)`}>
        <p className="mb-1 text-xs font-semibold muted">System</p>
        <pre className="mb-3 whitespace-pre-wrap rounded-md border p-2 text-xs" style={{ borderColor: "var(--border)" }}>
          {trace.system_prompt}
        </pre>
        <p className="mb-1 text-xs font-semibold muted">User</p>
        <pre className="whitespace-pre-wrap rounded-md border p-2 text-xs" style={{ borderColor: "var(--border)" }}>
          {trace.user_prompt}
        </pre>
      </Collapsible>

      <div className="mt-3 flex flex-wrap gap-3 text-xs muted">
        {Object.entries(trace.timings_ms).map(([k, v]) => (
          <span key={k}>
            {k.replace("_ms", "")}: <span className="font-mono">{v}ms</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function ChunkRow({
  chunk,
  all,
}: {
  chunk: PipelineTrace["retrieved"][number];
  all: PipelineTrace["retrieved"];
}) {
  // Chroma returns a distance (smaller = closer). Draw the bar so the closest chunk
  // is fullest; skip bars if scores are unavailable (non-Chroma store / fake).
  const scores = all.map((c) => c.dense_score).filter((s): s is number => s !== null);
  let width: number | null = null;
  if (chunk.dense_score !== null && scores.length > 1) {
    const min = Math.min(...scores);
    const max = Math.max(...scores);
    width = max === min ? 100 : Math.round(((max - chunk.dense_score) / (max - min)) * 100);
  }
  return (
    <div className="rounded-lg border p-2" style={{ borderColor: "var(--border)" }}>
      <div className="mb-1 flex items-center gap-2 text-xs">
        <span className="font-mono font-semibold">[{chunk.rank}]</span>
        <span className="truncate">{chunk.source}</span>
        {chunk.page !== null && <span className="muted">p.{chunk.page}</span>}
        <span
          className="rounded px-1.5 py-0.5 text-[10px] uppercase"
          style={{ background: chunk.extraction_method === "ocr" ? "var(--accent)" : "transparent", color: chunk.extraction_method === "ocr" ? "#fff" : "inherit", border: "1px solid var(--border)" }}
          title="How this text was extracted"
        >
          {chunk.extraction_method}
        </span>
        <span className="ml-auto font-mono muted" title="Vector distance — lower is closer">
          {chunk.dense_score !== null ? `dist ${chunk.dense_score.toFixed(3)}` : "—"}
        </span>
      </div>
      {width !== null && (
        <div className="mb-1 h-1 w-full overflow-hidden rounded-full" style={{ background: "var(--border)" }}>
          <div className="h-full rounded-full bg-[var(--accent)]" style={{ width: `${width}%` }} />
        </div>
      )}
      <p className="text-xs muted">{chunk.snippet}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <p className="mb-1.5 text-xs font-semibold">{title}</p>
      {children}
    </div>
  );
}

function Collapsible({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="text-xs font-semibold hover:underline"
      >
        {open ? "▾" : "▸"} {title}
      </button>
      {open && <div className="mt-2">{children}</div>}
    </div>
  );
}
