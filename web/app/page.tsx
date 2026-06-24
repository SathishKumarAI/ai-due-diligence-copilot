"use client";

import { useState } from "react";
import { ask, type AskResponse } from "@/lib/api";
import { siteConfig } from "@/lib/config";

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(q: string) {
    if (q.trim().length < 3) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await ask(q));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold">{siteConfig.name}</h1>
        <p className="mt-1 text-slate-600">{siteConfig.tagline}</p>
      </section>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
        className="space-y-3"
      >
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about the documents…"
          rows={3}
          className="w-full rounded-lg border border-slate-300 p-3 focus:outline-none focus:ring-2"
          style={{ outlineColor: siteConfig.accent }}
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg px-4 py-2 font-medium text-white disabled:opacity-50"
          style={{ backgroundColor: siteConfig.accent }}
        >
          {loading ? "Thinking…" : "Ask"}
        </button>
      </form>

      <section>
        <p className="mb-2 text-sm font-medium text-slate-500">Try an example:</p>
        <div className="flex flex-wrap gap-2">
          {siteConfig.examples.map((ex) => (
            <button
              key={ex}
              onClick={() => {
                setQuestion(ex);
                submit(ex);
              }}
              className="rounded-full border border-slate-300 bg-white px-3 py-1 text-sm text-slate-700 hover:border-slate-400"
            >
              {ex}
            </button>
          ))}
        </div>
      </section>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
          <p className="mt-1 text-red-500">
            Is the backend running at <code>{siteConfig.apiBaseUrl}</code>?
          </p>
        </div>
      )}

      {result && (
        <section className="space-y-4">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="whitespace-pre-wrap leading-relaxed">{result.answer}</p>
            <p className="mt-3 text-xs text-slate-400">
              {result.provider}
              {result.cached ? " · cached" : ""}
              {result.timings_ms?.generate_ms
                ? ` · ${Math.round(result.timings_ms.generate_ms)}ms`
                : ""}
            </p>
          </div>

          {result.citations.length > 0 && (
            <div>
              <p className="mb-2 text-sm font-medium text-slate-500">Sources</p>
              <ul className="space-y-2">
                {result.citations.map((c) => (
                  <li
                    key={c.marker}
                    className="rounded-lg border border-slate-200 bg-white p-3 text-sm"
                  >
                    <span
                      className="mr-2 inline-block rounded px-1.5 text-xs font-semibold text-white"
                      style={{ backgroundColor: siteConfig.accent }}
                    >
                      {c.marker}
                    </span>
                    <span className="font-medium">{c.source}</span>
                    {c.page != null && (
                      <span className="text-slate-400"> · p.{c.page}</span>
                    )}
                    <p className="mt-1 text-slate-600">{c.snippet}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
