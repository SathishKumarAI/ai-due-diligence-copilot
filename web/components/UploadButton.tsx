"use client";

import { useRef, useState } from "react";
import { uploadDocument } from "@/lib/api";

const ACCEPT = ".pdf,.md,.markdown,.txt";

// Lets a non-technical user drop their own deal document into the live index (F18).
export function UploadButton({ onUploaded }: { onUploaded?: (name: string) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function handle(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setMsg(null);
    try {
      const r = await uploadDocument(file);
      setMsg(`Added ${r.filename} (${r.chunks_added} chunks)`);
      onUploaded?.(r.filename);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
      setTimeout(() => setMsg(null), 4000);
    }
  }

  return (
    <div className="relative">
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => handle(e.target.files?.[0])}
      />
      <button
        onClick={() => input.current?.click()}
        disabled={busy}
        className="surface flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm transition hover:opacity-80 disabled:opacity-50"
        title="Upload a PDF, Markdown, or text file"
      >
        <span aria-hidden>↑</span>
        {busy ? "Uploading…" : "Upload doc"}
      </button>
      {msg && (
        <p className="surface absolute right-0 top-full z-10 mt-2 w-64 rounded-lg border p-2 text-xs muted shadow-lg">
          {msg}
        </p>
      )}
    </div>
  );
}
