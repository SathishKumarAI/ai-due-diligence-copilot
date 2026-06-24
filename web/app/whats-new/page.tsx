import { fetchReleases } from "@/lib/api";
import { siteConfig } from "@/lib/config";

// Server component: fetches GitHub Releases so non-technical users see, in plain
// language, what changed and when — no need to read commits or markdown files.
export default async function WhatsNewPage() {
  const releases = await fetchReleases();

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold">What&apos;s New</h1>
        <p className="mt-1 text-slate-600">
          Updates to {siteConfig.name}, newest first. Published from GitHub Releases.
        </p>
      </section>

      {releases.length === 0 ? (
        <p className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">
          No releases published yet. Once changes ship, they&apos;ll appear here. You can
          also follow the full history in{" "}
          <a
            className="underline"
            href={`https://github.com/${siteConfig.githubRepo}/blob/main/CHANGELOG.md`}
          >
            CHANGELOG.md
          </a>
          .
        </p>
      ) : (
        <ul className="space-y-4">
          {releases.map((r) => (
            <li key={r.tag} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="flex items-baseline justify-between">
                <a href={r.url} className="font-semibold hover:underline">
                  {r.name}
                </a>
                <time className="text-xs text-slate-400">
                  {new Date(r.date).toLocaleDateString()}
                </time>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                {r.body}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
