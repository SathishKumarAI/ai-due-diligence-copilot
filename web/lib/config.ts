// Domain config — the only file that changes between the three projects.
export const siteConfig = {
  name: "AI Due Diligence Copilot",
  tagline:
    "Ask investor-style questions about the deal documents. Every answer cites the sources it came from.",
  accent: "#2563eb", // blue
  disclaimer: "Informational analysis, not investment advice. Sample data is synthetic.",
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  githubRepo: process.env.NEXT_PUBLIC_GITHUB_REPO ?? "SathishKumarAI/ai-due-diligence-copilot",
  apiKey: process.env.NEXT_PUBLIC_API_KEY ?? "",
  examples: [
    "What are the main risks for this company?",
    "What is the ARR and its year-over-year growth?",
    "How much runway does the company have?",
    "What is the post-money valuation and liquidation preference?",
  ],
};
