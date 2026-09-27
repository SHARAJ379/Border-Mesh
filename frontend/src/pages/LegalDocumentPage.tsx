import React from 'react';
import { Shield, ArrowLeft } from 'lucide-react';

interface LegalDocumentPageProps {
  title: string;
  lastUpdated: string;
  children: React.ReactNode;
}

/**
 * Shared shell for standalone legal pages (Privacy Policy, Terms &
 * Conditions) -- reached via a real, bookmarkable URL (/privacy, /terms;
 * see main.tsx's routing) rather than the tab-based app shell, since a
 * legal document is read once, referenced externally, and doesn't belong
 * inside the case-management workspace's Lenis/GSAP/Three.js chrome.
 *
 * Content is authored directly as JSX in PrivacyPolicyPage.tsx/TermsPage.tsx
 * rather than rendered from docs/PRIVACY_POLICY.md / docs/TERMS_AND_
 * CONDITIONS.md at runtime -- this app has no markdown-rendering dependency,
 * and adding one for two static documents wasn't judged worth it. The two
 * copies (docs/*.md for repo readers, these pages for in-app readers) are
 * the same text and must be kept in sync by hand if either changes.
 */
export const LegalDocumentPage: React.FC<LegalDocumentPageProps> = ({ title, lastUpdated, children }) => {
  return (
    <div className="min-h-screen bg-graphite-950 text-graphite-100 font-sans">
      <header className="border-b border-graphite-800/60">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-5 flex items-center justify-between gap-4">
          <a href="/" className="flex items-center gap-3 shrink-0">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-brass-400 to-brass-700 flex items-center justify-center shadow-lg shadow-brass-950/40 border border-brass-400/30">
              <Shield className="w-4 h-4 text-graphite-950" />
            </div>
            <span className="font-bold text-sm tracking-wider text-graphite-100">
              BORDER<span className="text-brass-400">MESH</span>
            </span>
          </a>
          <a
            href="/"
            className="flex items-center gap-1.5 text-xs text-graphite-400 hover:text-brass-400 transition-colors shrink-0"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to app
          </a>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-10 sm:py-14">
        <div className="mb-8">
          <span className="text-[10px] uppercase tracking-widest text-graphite-500">
            Smart India Hackathon 2026 · SIH26188 · Ministry of Home Affairs, Government of India
          </span>
          <h1 className="text-2xl sm:text-3xl font-bold text-graphite-100 mt-2">{title}</h1>
          <p className="text-xs text-graphite-500 mt-2">Last updated: {lastUpdated}</p>
        </div>

        <div className="legal-prose">{children}</div>

        <nav className="mt-12 pt-6 border-t border-graphite-800/60 flex items-center gap-5 text-xs">
          <a href="/privacy" className="text-graphite-400 hover:text-brass-400 transition-colors">Privacy Policy</a>
          <a href="/terms" className="text-graphite-400 hover:text-brass-400 transition-colors">Terms &amp; Conditions</a>
          <a href="/" className="text-graphite-400 hover:text-brass-400 transition-colors">Back to app</a>
        </nav>
      </main>
    </div>
  );
};
