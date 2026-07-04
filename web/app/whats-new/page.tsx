import { fetchReleases } from "@/lib/api";
import { siteConfig } from "@/lib/config";

// Server component: fetches GitHub Releases so non-technical users see, in plain
// language, what changed and when — no need to read commits or markdown files.
export default async function WhatsNewPage() {
  const releases = await fetchReleases();

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-10">
      <section>
        <h1 className="text-2xl font-semibold">What&apos;s New</h1>
        <p className="mt-1 muted">
          Updates to {siteConfig.name}, newest first. Published from GitHub Releases.
        </p>
      </section>

      {releases.length === 0 ? (
        <p className="surface rounded-xl border p-4 text-sm muted">
          No releases published yet. Once changes ship, they&apos;ll appear here. You can
          also follow the full history in{" "}
          <a
            className="text-[var(--accent)] underline"
            href={`https://github.com/${siteConfig.githubRepo}/blob/main/CHANGELOG.md`}
          >
            CHANGELOG.md
          </a>
          .
        </p>
      ) : (
        <ul className="space-y-4">
          {releases.map((r) => (
            <li key={r.tag} className="surface rounded-xl border p-4">
              <div className="flex items-baseline justify-between gap-3">
                <a href={r.url} className="font-semibold hover:underline">
                  {r.name}
                </a>
                <time className="text-xs muted">
                  {new Date(r.date).toLocaleDateString()}
                </time>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed muted">
                {r.body}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
