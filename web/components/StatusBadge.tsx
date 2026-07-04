"use client";

import { useEffect, useState } from "react";
import { fetchReady, type ReadyState } from "@/lib/api";

// Live index health, polled from /ready. Tells a non-technical user at a glance
// whether the corpus is ready to answer — and nudges them to ingest if not.
export function StatusBadge() {
  const [state, setState] = useState<ReadyState | null | "loading">("loading");

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      const r = await fetchReady();
      if (alive) setState(r);
    };
    tick();
    const id = setInterval(tick, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const { dot, label, title } = describe(state);
  return (
    <span
      className="surface inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs muted"
      title={title}
    >
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      {label}
    </span>
  );
}

function describe(state: ReadyState | null | "loading") {
  if (state === "loading") return { dot: "bg-slate-400", label: "Connecting…", title: "" };
  if (state === null)
    return { dot: "bg-red-500", label: "Offline", title: "Backend unreachable" };
  if (!state.ready)
    return {
      dot: "bg-amber-500",
      label: "No index",
      title: "Run ingest or upload a document",
    };
  return {
    dot: "bg-emerald-500",
    label: `${state.indexed_chunks.toLocaleString()} chunks`,
    title: "Index ready",
  };
}
