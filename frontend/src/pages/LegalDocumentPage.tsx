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
 * inside the case-management workspace's Lenis/GSAP chrome.
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
    <div className="min-h-screen bg-paper text-ink font-sans">
      <header className="border-b border-hairline">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-5 flex items-center justify-between gap-4">
          <a href="/" className="flex items-center gap-2.5 shrink-0">
            <Shield className="w-[18px] h-[18px] text-ink" strokeWidth={1.75} />
            <span className="font-display text-[17px] text-ink">
              BorderMesh<span className="text-accent">.</span>
            </span>
          </a>
          <a
            href="/"
            className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.06em] text-ink-soft hover:text-accent transition-colors shrink-0"
          >
            <ArrowLeft className="w-3.5 h-3.5" strokeWidth={1.75} />
            Back to app
          </a>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-10 sm:py-14">
        <div className="mb-8">
          <span className="label-eyebrow">
            Smart India Hackathon 2026 &middot; SIH26188 &middot; Ministry of Home Affairs, Government of India
          </span>
          <h1 className="font-display text-[32px] sm:text-[40px] text-ink mt-2">{title}</h1>
          <p className="text-[11px] text-muted mt-2">Last updated: {lastUpdated}</p>
        </div>

        <div className="legal-prose">{children}</div>

        <nav className="mt-12 pt-6 border-t border-hairline flex items-center gap-6 text-[11px] uppercase tracking-[0.06em]">
          <a href="/privacy" className="text-ink-soft hover:text-accent transition-colors">Privacy Policy</a>
          <a href="/terms" className="text-ink-soft hover:text-accent transition-colors">Terms &amp; Conditions</a>
          <a href="/" className="text-ink-soft hover:text-accent transition-colors">Back to app</a>
        </nav>
      </main>
    </div>
  );
};
