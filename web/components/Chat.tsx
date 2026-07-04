"use client";

import { useEffect, useRef, useState } from "react";
import { askExplain, askStream, type Citation, type PipelineTrace, type Turn } from "@/lib/api";
import { siteConfig } from "@/lib/config";
import { AnswerText } from "./AnswerText";
import { CitationList } from "./CitationList";
import { FeedbackButtons } from "./FeedbackButtons";
import { TracePanel } from "./TracePanel";

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  streaming?: boolean;
  error?: boolean;
};

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [traces, setTraces] = useState<Record<number, PipelineTrace | "loading" | "error">>({});
  const bottom = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function reset() {
    setMessages([]);
    setInput("");
  }

  function jumpToCite(assistantId: number, marker: number) {
    document
      .getElementById(`msg-${assistantId}-cite-${marker}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  // F23: re-ask this turn with explain=true to fetch and show the pipeline trace.
  async function inspect(assistantId: number) {
    const userIdx = messages.findIndex((x) => x.id === assistantId - 1);
    const question = messages[userIdx]?.content ?? "";
    if (!question) return;
    const history: Turn[] = messages
      .slice(0, userIdx)
      .filter((x) => !x.error)
      .map((x) => ({ role: x.role, content: x.content }));
    setTraces((t) => ({ ...t, [assistantId]: "loading" }));
    try {
      const res = await askExplain(question, history);
      setTraces((t) => ({ ...t, [assistantId]: res.trace ?? "error" }));
    } catch {
      setTraces((t) => ({ ...t, [assistantId]: "error" }));
    }
  }

  async function send(text: string) {
    const q = text.trim();
    if (q.length < 3 || busy) return;
    setBusy(true);
    setInput("");

    // History = the conversation before this turn (F19 multi-turn memory).
    const history: Turn[] = messages
      .filter((m) => !m.error)
      .map((m) => ({ role: m.role, content: m.content }));

    const userId = nextId.current++;
    const aId = nextId.current++;
    setMessages((m) => [
      ...m,
      { id: userId, role: "user", content: q },
      { id: aId, role: "assistant", content: "", streaming: true },
    ]);

    const patch = (id: number, fn: (msg: Message) => Message) =>
      setMessages((m) => m.map((msg) => (msg.id === id ? fn(msg) : msg)));

    try {
      const { citations } = await askStream(q, history, (tok) =>
        patch(aId, (msg) => ({ ...msg, content: msg.content + tok })),
      );
      patch(aId, (msg) => ({ ...msg, citations, streaming: false }));
    } catch (e) {
      patch(aId, (msg) => ({
        ...msg,
        streaming: false,
        error: true,
        content: e instanceof Error ? e.message : "Something went wrong.",
      }));
    } finally {
      setBusy(false);
    }
  }

  const empty = messages.length === 0;

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto">
        {empty ? (
          <EmptyState onPick={send} />
        ) : (
          <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
            {messages.map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="flex justify-end rise">
                  <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-[var(--accent)] px-4 py-2.5 text-white">
                    {m.content}
                  </div>
                </div>
              ) : (
                <div key={m.id} className="rise">
                  <div
                    className={`surface rounded-2xl rounded-bl-sm border px-4 py-3 ${
                      m.error ? "border-red-300 text-red-600" : ""
                    }`}
                  >
                    {m.error ? (
                      <div className="text-sm">
                        <p>{m.content}</p>
                        <p className="mt-1 muted">
                          Is the backend running at <code>{siteConfig.apiBaseUrl}</code>?
                        </p>
                      </div>
                    ) : (
                      <>
                        <AnswerText
                          text={m.content || "…"}
                          streaming={m.streaming}
                          onCite={(marker) => jumpToCite(m.id, marker)}
                        />
                        {m.citations && (
                          <CitationList citations={m.citations} idPrefix={`msg-${m.id}`} />
                        )}
                        {!m.streaming && !m.error && m.content && (
                          <>
                            <div className="flex items-center gap-3">
                              <FeedbackButtons
                                question={
                                  messages.find((u) => u.id === m.id - 1)?.content ?? ""
                                }
                                answer={m.content}
                              />
                              <button
                                onClick={() => inspect(m.id)}
                                disabled={traces[m.id] === "loading"}
                                className="text-xs muted transition hover:text-[var(--accent)] disabled:opacity-50"
                                title="Show how this answer was built (F23)"
                              >
                                {traces[m.id] === "loading" ? "🔍 inspecting…" : "🔍 inspect pipeline"}
                              </button>
                            </div>
                            {traces[m.id] === "error" && (
                              <p className="mt-2 text-xs text-red-500">
                                Could not load the trace. Is the backend running?
                              </p>
                            )}
                            {traces[m.id] && traces[m.id] !== "loading" && traces[m.id] !== "error" && (
                              <TracePanel trace={traces[m.id] as PipelineTrace} />
                            )}
                          </>
                        )}
                      </>
                    )}
                  </div>
                </div>
              ),
            )}
            <div ref={bottom} />
          </div>
        )}
      </div>

      <Composer
        value={input}
        onChange={setInput}
        onSend={() => send(input)}
        busy={busy}
        canReset={!empty}
        onReset={reset}
      />
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center px-4 py-16 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--accent)] text-xl font-bold text-white">
        ◆
      </div>
      <h1 className="text-2xl font-semibold">{siteConfig.name}</h1>
      <p className="mt-2 max-w-md muted">{siteConfig.tagline}</p>
      <div className="mt-8 grid w-full gap-2 sm:grid-cols-2">
        {siteConfig.examples.map((ex) => (
          <button
            key={ex}
            onClick={() => onPick(ex)}
            className="surface rounded-xl border p-3 text-left text-sm transition hover:border-[var(--accent)]"
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}

function Composer({
  value,
  onChange,
  onSend,
  busy,
  canReset,
  onReset,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  busy: boolean;
  canReset: boolean;
  onReset: () => void;
}) {
  return (
    <div className="border-t px-4 py-3" style={{ borderColor: "var(--border)" }}>
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        {canReset && (
          <button
            onClick={onReset}
            className="surface rounded-xl border px-3 py-3 text-sm muted transition hover:opacity-80"
            title="Start a new conversation"
          >
            New
          </button>
        )}
        <div className="surface flex flex-1 items-end gap-2 rounded-2xl border p-2">
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            placeholder="Ask about the documents…  (Shift+Enter for newline)"
            rows={1}
            className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 focus:outline-none"
          />
          <button
            onClick={onSend}
            disabled={busy || value.trim().length < 3}
            className="rounded-xl bg-[var(--accent)] px-4 py-2 font-medium text-white transition hover:opacity-90 disabled:opacity-40"
          >
            {busy ? "…" : "Ask"}
          </button>
        </div>
      </div>
      <p className="mx-auto mt-2 max-w-3xl text-center text-xs muted">
        {siteConfig.disclaimer}
      </p>
    </div>
  );
}
