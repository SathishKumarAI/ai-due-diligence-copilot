import { siteConfig } from "./config";

export type Citation = {
  marker: number;
  source: string;
  page: number | null;
  snippet: string;
};

export type AskResponse = {
  question: string;
  answer: string;
  citations: Citation[];
  provider: string;
  cached: boolean;
  timings_ms: Record<string, number>;
};

export async function ask(question: string, topK?: number): Promise<AskResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (siteConfig.apiKey) headers["X-API-Key"] = siteConfig.apiKey;

  const res = await fetch(`${siteConfig.apiBaseUrl}/v1/ask`, {
    method: "POST",
    headers,
    body: JSON.stringify({ question, top_k: topK ?? null }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`Backend error ${res.status}: ${detail}`);
  }
  return res.json();
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
