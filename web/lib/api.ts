import { siteConfig } from "./config";

export type Citation = {
  marker: number;
  source: string;
  page: number | null;
  snippet: string;
};

export type Turn = { role: "user" | "assistant"; content: string };

// --- pipeline trace / introspection (F23) ---
export type TokenizationTrace = {
  text: string;
  char_count: number;
  word_count: number;
  tokens: string[];
  token_count: number;
  tokenizer: string;
  note: string;
};

export type RetrievedChunkTrace = {
  rank: number;
  source: string;
  page: number | null;
  extraction_method: string;
  chars: number;
  dense_score: number | null;
  snippet: string;
};

export type PipelineTrace = {
  original_question: string;
  condensed_query: string;
  condensed: boolean;
  tokenization: TokenizationTrace;
  retrieval_mode: string;
  rerank_enabled: boolean;
  retrieved: RetrievedChunkTrace[];
  context_char_len: number;
  system_prompt: string;
  user_prompt: string;
  answer: string;
  timings_ms: Record<string, number>;
};

// --- claim grounding / verification (F24) ---
export type ClaimStatus = "grounded" | "weak" | "unsupported" | "meta";

export type ClaimVerdict = {
  text: string;
  markers: number[];
  status: ClaimStatus;
  coverage: number;
  missing_terms: string[];
  unsupported_figures: string[];
  source: string | null;
  span_text: string;
  span_start: number | null;
  span_end: number | null;
};

// Two retrieved sources disagreeing about the same quantity (F27). Distinct from a claim
// verdict on purpose: claim checking asks "does the answer match its sources", which is
// silent when the sources themselves conflict.
export type FigureConflict = {
  context: string[];
  values: { value: string; source: string; snippet: string }[];
};

export type GroundingReport = {
  claims: ClaimVerdict[];
  conflicts: FigureConflict[];
  grounded: number;
  weak: number;
  unsupported: number;
  meta: number;
  score: number;
  verdict: "grounded" | "mixed" | "unsupported" | "refusal" | "empty" | "unverified";
  note: string;
};

export type AskResponse = {
  question: string;
  answer: string;
  citations: Citation[];
  provider: string;
  cached: boolean;
  timings_ms: Record<string, number>;
  trace?: PipelineTrace | null;
  grounding?: GroundingReport | null;
};

/**
 * Ask with explain=true for the pipeline trace (F23) and verify=true for the claim
 * grounding report (F24). Not streamed — the inspector re-asks the turn to get both.
 */
export async function askExplain(
  question: string,
  history: Turn[] = [],
  topK?: number,
): Promise<AskResponse> {
  const res = await fetch(`${siteConfig.apiBaseUrl}/v1/ask`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      question,
      history,
      top_k: topK ?? null,
      explain: true,
      verify: true,
    }),
  });
  if (!res.ok) throw await asError(res);
  return res.json();
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  if (siteConfig.apiKey) headers["X-API-Key"] = siteConfig.apiKey;
  return headers;
}

async function asError(res: Response): Promise<Error> {
  let detail = res.statusText;
  try {
    const body = await res.json();
    detail = body?.detail ?? JSON.stringify(body);
  } catch {
    detail = (await res.text().catch(() => res.statusText)) || res.statusText;
  }
  return new Error(`${res.status}: ${detail}`);
}

/** Non-streaming ask. Falls back here when streaming isn't desired. */
export async function ask(
  question: string,
  history: Turn[] = [],
  topK?: number,
): Promise<AskResponse> {
  const res = await fetch(`${siteConfig.apiBaseUrl}/v1/ask`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ question, history, top_k: topK ?? null }),
  });
  if (!res.ok) throw await asError(res);
  return res.json();
}

/** Streaming ask over SSE-on-POST: parses the event stream from the response body. */
export async function askStream(
  question: string,
  history: Turn[],
  onToken: (t: string) => void,
  signal?: AbortSignal,
): Promise<{ citations: Citation[] }> {
  const res = await fetch(`${siteConfig.apiBaseUrl}/v1/ask/stream`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ question, history, top_k: null }),
    signal,
  });
  if (!res.ok || !res.body) throw await asError(res);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let citations: Citation[] = [];

  // SSE frames are separated by a blank line; each frame has event: / data: lines.
  const handleFrame = (frame: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
    }
    const data = dataLines.join("\n");
    if (event === "token") onToken(data);
    else if (event === "citations") {
      try {
        citations = JSON.parse(data) as Citation[];
      } catch {
        /* ignore malformed trailing frame */
      }
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // sse-starlette terminates lines with CRLF, so frames arrive separated by
    // "\r\n\r\n". Splitting on "\n\n" alone never matched: every frame stayed in the
    // buffer, the whole stream was handed to handleFrame once as a single malformed
    // frame at end-of-stream, JSON.parse threw, and the catch swallowed it — so the
    // UI showed a caret and never a single token. Normalise the buffer (not the raw
    // chunk) so a CR landing on a chunk boundary still pairs with its LF.
    buffer = buffer.replace(/\r\n/g, "\n");
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      handleFrame(buffer.slice(0, sep));
      buffer = buffer.slice(sep + 2);
    }
  }
  if (buffer.trim()) handleFrame(buffer);
  return { citations };
}

export type UploadResult = {
  filename: string;
  chunks_added: number;
  collection: string;
};

export async function uploadDocument(file: File): Promise<UploadResult> {
  const res = await fetch(
    `${siteConfig.apiBaseUrl}/v1/upload?filename=${encodeURIComponent(file.name)}`,
    { method: "POST", headers: authHeaders(), body: file },
  );
  if (!res.ok) throw await asError(res);
  return res.json();
}

export type FeedbackResult = { ok: boolean; up: number; down: number; total: number };

export async function sendFeedback(
  question: string,
  answer: string,
  rating: "up" | "down",
  comment?: string,
): Promise<FeedbackResult> {
  const res = await fetch(`${siteConfig.apiBaseUrl}/v1/feedback`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ question, answer, rating, comment: comment ?? null }),
  });
  if (!res.ok) throw await asError(res);
  return res.json();
}

export type ReadyState = { ready: boolean; indexed_chunks: number };

export async function fetchReady(): Promise<ReadyState | null> {
  try {
    const res = await fetch(`${siteConfig.apiBaseUrl}/ready`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export type Release = {
  name: string;
  tag: string;
  body: string;
  date: string;
  url: string;
};

// "What's New" feed — public GitHub Releases, no auth needed for public repos.
export async function fetchReleases(): Promise<Release[]> {
  const res = await fetch(
    `https://api.github.com/repos/${siteConfig.githubRepo}/releases`,
    { headers: { Accept: "application/vnd.github+json" }, next: { revalidate: 300 } },
  );
  if (!res.ok) return [];
  const data = (await res.json()) as Array<{
    name: string | null;
    tag_name: string;
    body: string | null;
    published_at: string;
    html_url: string;
  }>;
  return data.map((r) => ({
    name: r.name || r.tag_name,
    tag: r.tag_name,
    body: r.body || "",
    date: r.published_at,
    url: r.html_url,
  }));
}
