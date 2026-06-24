import type { Metadata } from "next";
import Link from "next/link";
import { siteConfig } from "@/lib/config";
import "./globals.css";

export const metadata: Metadata = {
  title: siteConfig.name,
  description: siteConfig.tagline,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-slate-200 bg-white">
          <nav className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
            <Link href="/" className="font-semibold" style={{ color: siteConfig.accent }}>
              {siteConfig.name}
            </Link>
            <div className="flex gap-4 text-sm text-slate-600">
              <Link href="/" className="hover:text-slate-900">Ask</Link>
              <Link href="/whats-new" className="hover:text-slate-900">What&apos;s New</Link>
              <a
                href={`https://github.com/${siteConfig.githubRepo}`}
                className="hover:text-slate-900"
                target="_blank"
                rel="noreferrer"
              >
                GitHub
              </a>
            </div>
          </nav>
        </header>
        <main className="mx-auto max-w-3xl px-4 py-8">{children}</main>
        <footer className="mx-auto max-w-3xl px-4 py-8 text-xs text-slate-400">
          {siteConfig.disclaimer}
        </footer>
      </body>
    </html>
  );
}
