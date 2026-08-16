// Domain config — the main file that changes between the three projects.
export const siteConfig = {
  name: "AI Due Diligence Copilot",
  shortName: "Due Diligence Copilot",
  tagline:
    "Ask investor-style questions about the deal documents. Every answer cites the sources it came from.",
  domainLabel: "Finance · VC",
  disclaimer:
    "Informational analysis, not investment advice. Sample data is synthetic.",
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  githubRepo:
    process.env.NEXT_PUBLIC_GITHUB_REPO ?? "SathishKumarAI/ai-due-diligence-copilot",
  apiKey: process.env.NEXT_PUBLIC_API_KEY ?? "",
  // Where the Embedding Projector is being served, if it is. Deliberately empty by
  // default: the projector is a separate process serving a STATIC export, so linking to
  // it unconditionally would offer a dead link on most installs. See docs/EMBEDDING-MAP.md.
  embeddingMapUrl: process.env.NEXT_PUBLIC_EMBEDDING_MAP_URL ?? "",
  examples: [
    "What are the main risks for this company?",
    "What is the ARR and its year-over-year growth?",
    "How much runway does the company have?",
    "What is the post-money valuation and liquidation preference?",
  ],
} as const;
