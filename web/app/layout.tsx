import type { Metadata } from "next";
import Link from "next/link";
import { StatusBadge } from "@/components/StatusBadge";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UploadButton } from "@/components/UploadButton";
import { siteConfig } from "@/lib/config";
import "./globals.css";

export const metadata: Metadata = {
  title: siteConfig.name,
  description: siteConfig.tagline,
};

// Applies the saved theme before first paint to avoid a flash of the wrong colors.
const themeInit = `(function(){try{var t=localStorage.getItem('theme');var d=t? t==='dark' : matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.classList.toggle('dark', d);}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body className="flex min-h-screen flex-col">
        <header
          className="sticky top-0 z-20 border-b backdrop-blur"
          style={{ borderColor: "var(--border)", background: "color-mix(in srgb, var(--bg) 80%, transparent)" }}
        >
          <nav className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-2.5">
            <Link href="/" className="flex items-center gap-2 font-semibold">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--accent)] text-sm text-white">
                ◆
              </span>
              <span className="hidden sm:inline">{siteConfig.shortName}</span>
            </Link>
            <span className="surface-2 hidden rounded-full px-2 py-0.5 text-xs muted md:inline">
              {siteConfig.domainLabel}
            </span>

            <div className="ml-auto flex items-center gap-2 text-sm">
              <StatusBadge />
              <UploadButton />
              <Link
                href="/whats-new"
                className="hidden rounded-lg px-2.5 py-1.5 transition hover:opacity-70 sm:inline muted"
              >
                What&apos;s New
              </Link>
              <a
                href={`https://github.com/${siteConfig.githubRepo}`}
                target="_blank"
                rel="noreferrer"
                className="hidden rounded-lg px-2.5 py-1.5 transition hover:opacity-70 sm:inline muted"
              >
                GitHub
              </a>
              <ThemeToggle />
            </div>
          </nav>
        </header>

        <main className="min-h-0 flex-1">{children}</main>
      </body>
    </html>
  );
}
