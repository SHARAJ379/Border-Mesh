import React, { useEffect } from 'react';
import {
  Shield, ScanLine, FileSearch, Fingerprint, Link2, ListChecks,
  ArrowRight, ArrowUpRight, CheckCircle2, XCircle, AlertTriangle,
} from 'lucide-react';

/**
 * Public-facing intro/marketing page -- deliberately NOT the operational
 * dashboard's dark brass/graphite design system. This is a distinct visual
 * identity (Neo-Brutalist: hard black borders, offset drop-shadows, a single
 * loud yellow, Unbounded/Plus Jakarta Sans) adapted from a design spec the
 * user asked to have implemented here, with real BorderMesh content in place
 * of the original's generic SaaS copy. Every claim below is grounded in
 * KNOWN_LIMITATIONS.md / the actual codebase -- see the "Known limitations"
 * callout, which links to /terms rather than hiding the caveats a marketing
 * page would normally omit.
 *
 * Scoped entirely under .bm-landing (own fonts, own CSS vars, own <style>
 * block) so nothing here leaks into or collides with the dashboard's Tailwind
 * classes -- the two are never mounted in the same document (see main.tsx).
 */
export const WelcomePage: React.FC = () => {
  useEffect(() => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://fonts.googleapis.com/css2?family=Unbounded:wght@400;500;600;700;800;900&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap';
    document.head.appendChild(link);
  }, []);

  return (
    <div className="bm-landing">
      <style>{css}</style>

      {/* ---------- NAV ---------- */}
      <header className="bm-nav">
        <div className="bm-nav-inner">
          <a href="/welcome" className="bm-brand">
            <span className="bm-brand-mark"><Shield size={18} strokeWidth={2.5} /></span>
            <span className="bm-brand-name">BORDERMESH</span>
          </a>
          <nav className="bm-nav-links">
            <a href="#pipeline">Pipeline</a>
            <a href="#features">Features</a>
            <a href="#compliance">Compliance</a>
            <a href="#judges">For judges</a>
          </nav>
          <a href="/" className="bm-btn bm-btn-sm">Open Dashboard <ArrowRight size={15} /></a>
        </div>
      </header>

      {/* Honest disclaimer strip -- this is a public page, so the same
          candor the Terms page discloses in full gets a visible one-liner
          here rather than being buried three clicks deep. */}
      <div className="bm-disclaimer">
        <span>
          SIH26188 prototype for the Ministry of Home Affairs — a decision-support demo, not a live operational screening system.
        </span>
        <a href="/terms">Read the known limitations <ArrowUpRight size={13} /></a>
      </div>

      {/* ---------- HERO ---------- */}
      <section className="bm-hero">
        <div className="bm-hero-copy">
          <span className="bm-eyebrow">SIH26188 &middot; SMART INDIA HACKATHON 2026 &middot; BLOCKCHAIN &amp; CYBERSECURITY</span>
          <h1 className="bm-h1">
            Screen documents.<br />Explain every <span className="bm-stroke">decision</span>.
          </h1>
          <p className="bm-lead">
            BorderMesh runs every document through OCR, MRZ validation, forensic tamper analysis,
            face verification and watchlist screening — then hands the officer an itemized,
            evidence-backed reason for the score, not just a number.
          </p>
          <div className="bm-hero-ctas">
            <a href="/" className="bm-btn bm-btn-lg">Open Screening Dashboard <ArrowRight size={17} /></a>
            <a href="#how-it-works" className="bm-btn bm-btn-lg bm-btn-ghost">See how it works</a>
          </div>
        </div>

        <div className="bm-hero-visual" aria-hidden="true">
          <div className="bm-mock">
            <div className="bm-mock-bar">
              <span className="bm-dot" /><span className="bm-dot" /><span className="bm-dot" />
              <span className="bm-mock-url">bordermesh.local/dashboard</span>
            </div>
            <div className="bm-mock-body">
              <div className="bm-mock-stats">
                <div className="bm-mock-stat"><strong>2,481</strong><span>Screened</span></div>
                <div className="bm-mock-stat"><strong>63</strong><span>Review queue</span></div>
                <div className="bm-mock-stat bm-mock-stat-warn"><strong>19</strong><span>High risk</span></div>
                <div className="bm-mock-stat bm-mock-stat-crit"><strong>4</strong><span>Critical</span></div>
              </div>
              <div className="bm-mock-checks">
                <div className="bm-mock-check bm-pass"><CheckCircle2 size={15} /> MRZ validation — checksum digits match</div>
                <div className="bm-mock-check bm-fail"><XCircle size={15} /> Tamper analysis — ELA flagged 2 regions</div>
                <div className="bm-mock-check bm-pass"><CheckCircle2 size={15} /> Face match — 0.91 cosine similarity</div>
                <div className="bm-mock-check bm-warn"><AlertTriangle size={15} /> Watchlist — sandboxed name partial match</div>
              </div>
              <div className="bm-mock-score">
                <span>Risk score</span>
                <strong>62 / 100 — Medium</strong>
              </div>
            </div>
          </div>
          <div className="bm-blob" />
        </div>
      </section>

      {/* ---------- MARQUEE: built with, not fake client logos ---------- */}
      <div className="bm-marquee">
        <div className="bm-marquee-track">
          {[...Array(2)].map((_, i) => (
            <div className="bm-marquee-group" key={i} aria-hidden={i === 1}>
              {['TESSERACT OCR', 'ICAO 9303', 'PYTORCH', 'FASTAPI', 'REACT 19', 'ETHEREUM SEPOLIA', 'FERNET AES-128', 'DPDP ACT 2023'].map((t) => (
                <span key={t}>{t}</span>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* ---------- PROBLEM / SOLUTION ---------- */}
      <section className="bm-section" id="pipeline">
        <div className="bm-ps-grid">
          <div className="bm-ps-card bm-ps-old">
            <span className="bm-ps-label">THE OLD WAY</span>
            <ul>
              <li>Manual visual inspection, no forensic backing</li>
              <li>OCR, tamper checks and watchlist screening run in silos</li>
              <li>A flagged case with no written reason for why</li>
              <li>No tamper-evident record of who reviewed what</li>
            </ul>
          </div>
          <div className="bm-ps-arrow"><ArrowRight size={28} strokeWidth={3} /></div>
          <div className="bm-ps-card bm-ps-new">
            <span className="bm-ps-label">THE BORDERMESH WAY</span>
            <ul>
              <li>One pipeline: OCR &rarr; MRZ &rarr; Tamper AI &rarr; Face &rarr; Risk score</li>
              <li>Every factor returns PASS / FAIL / INFO with its own evidence</li>
              <li>A risk score an officer can trace back, check by check</li>
              <li>Hash-chained audit ledger, optionally anchored on-chain</li>
            </ul>
          </div>
        </div>
      </section>

      {/* ---------- FEATURES ---------- */}
      <section className="bm-section" id="features">
        <h2 className="bm-h2">Built as one pipeline, not five separate tools</h2>
        <div className="bm-feature-grid">
          <div className="bm-card bm-card-yellow">
            <div className="bm-card-icon"><ScanLine size={22} /></div>
            <h3>Multi-signal forensic pipeline</h3>
            <p>OCR field extraction, ICAO 9303 MRZ checksum validation, error-level-analysis
              tamper detection, biometric face matching and watchlist screening — run
              together on every case, across 7 document types.</p>
          </div>
          <div className="bm-card">
            <div className="bm-card-icon"><ListChecks size={22} /></div>
            <h3>Explainable risk reasons</h3>
            <p>The risk score isn't a black box: it's built from itemized checks, each with a
              status and the underlying evidence (a checksum, a similarity score, a flagged
              region) — the reasoning an officer can actually read and challenge.</p>
          </div>
          <div className="bm-card bm-card-sage">
            <div className="bm-card-icon"><Link2 size={22} /></div>
            <h3>Tamper-evident audit trail</h3>
            <p>Every action writes to a hash-chained ledger where each entry embeds the
              previous one's hash, with an officer-triggered option to anchor the chain's
              head hash to the public Ethereum Sepolia testnet.</p>
          </div>
        </div>
      </section>

      {/* ---------- HOW IT WORKS ---------- */}
      <section className="bm-section" id="how-it-works">
        <h2 className="bm-h2">From document to decision, in three steps</h2>
        <div className="bm-steps">
          <div className="bm-step">
            <span className="bm-step-num"><FileSearch size={20} /></span>
            <h3>1. Upload or capture</h3>
            <p>A document image and, where relevant, a live face capture — the demo defaults
              to synthetic specimens, but the same upload path accepts real images with no
              special-casing.</p>
          </div>
          <div className="bm-step">
            <span className="bm-step-num"><Fingerprint size={20} /></span>
            <h3>2. Multi-signal AI analysis</h3>
            <p>OCR, MRZ validation, tamper AI, face verification and watchlist screening each
              run and report back a PASS / FAIL / INFO check with its own evidence.</p>
          </div>
          <div className="bm-step">
            <span className="bm-step-num"><Shield size={20} /></span>
            <h3>3. Officer reviews &amp; decides</h3>
            <p>BorderMesh surfaces a risk score and the itemized reasons behind it — the
              officer makes the call. Nothing here auto-approves or auto-rejects a case.</p>
          </div>
        </div>
      </section>

      {/* ---------- PERSONAS ---------- */}
      <section className="bm-section">
        <h2 className="bm-h2">Who this is built for</h2>
        <div className="bm-persona-grid">
          <div className="bm-persona">
            <span className="bm-persona-tag">01</span>
            <h3>Border &amp; immigration officers</h3>
            <p>A single screen for OCR, forensic and biometric signals instead of switching
              between separate tools — with reasons attached to the score, not just the score.</p>
          </div>
          <div className="bm-persona bm-persona-alt">
            <span className="bm-persona-tag">02</span>
            <h3>Compliance &amp; audit teams</h3>
            <p>A DPDP Act 2023-aligned data-handling model and a tamper-evident, hash-chained
              log of every screening and officer action.</p>
          </div>
          <div className="bm-persona">
            <span className="bm-persona-tag">03</span>
            <h3>SIH 2026 judges &amp; evaluators</h3>
            <p>The full pipeline, working end to end — plus a plain accounting of what's real,
              what's simulated, and what isn't validated yet. No inflated numbers.</p>
          </div>
        </div>
      </section>

      {/* ---------- BY THE NUMBERS ---------- */}
      <section className="bm-section" id="compliance">
        <h2 className="bm-h2">What's actually built</h2>
        <div className="bm-stat-grid">
          <div className="bm-stat"><strong>7</strong><span>document types, end to end</span></div>
          <div className="bm-stat"><strong>6</strong><span>independent risk factors</span></div>
          <div className="bm-stat"><strong>281</strong><span>automated backend tests</span></div>
          <div className="bm-stat"><strong>AES-128</strong><span>Fernet-encrypted biometric artifacts</span></div>
        </div>
        <div className="bm-limits">
          <AlertTriangle size={18} />
          <p>
            <strong>Honestly, not everything here is production-ready.</strong> Tamper
            detection catches 39.5% of real, human-made forgeries in testing — the rest is
            disclosed, not hidden. Full breakdown, including the watchlist's fictional data
            and the encryption key's demo-only status, in the <a href="/terms">Terms &amp; Conditions</a>.
          </p>
        </div>
      </section>

      {/* ---------- FINAL CTA ---------- */}
      <section className="bm-cta" id="judges">
        <h2>Every screening comes with its reasons.</h2>
        <p>Built for SIH26188 — Ministry of Home Affairs, Government of India.</p>
        <a href="/" className="bm-btn bm-btn-lg bm-btn-invert">Open the Dashboard <ArrowRight size={17} /></a>
      </section>

      {/* ---------- FOOTER ---------- */}
      <footer className="bm-footer">
        <div className="bm-footer-grid">
          <div>
            <div className="bm-brand">
              <span className="bm-brand-mark"><Shield size={16} strokeWidth={2.5} /></span>
              <span className="bm-brand-name">BORDERMESH</span>
            </div>
            <p>AI-based fake identity &amp; document screening — a decision-support prototype
              for SIH26188, not a certified or production system.</p>
          </div>
          <div>
            <span className="bm-footer-head">Product</span>
            <a href="/">Dashboard</a>
            <a href="#pipeline">Pipeline</a>
            <a href="#features">Features</a>
          </div>
          <div>
            <span className="bm-footer-head">Legal</span>
            <a href="/privacy">Privacy Policy</a>
            <a href="/terms">Terms &amp; Conditions</a>
          </div>
          <div>
            <span className="bm-footer-head">About</span>
            <span className="bm-footer-plain">SIH26188 &middot; Ministry of Home Affairs</span>
            <span className="bm-footer-plain">Theme: Blockchain &amp; Cybersecurity</span>
          </div>
        </div>
        <div className="bm-footer-bottom">
          Smart India Hackathon 2026 prototype. Not for use in live operational screening.
        </div>
      </footer>
    </div>
  );
};

const css = `
.bm-landing {
  --bm-yellow: #ffe17c;
  --bm-yellow-hi: #ffbc2e;
  --bm-charcoal: #171e19;
  --bm-sage: #b7c6c2;
  --bm-white: #ffffff;
  --bm-black: #000000;
  --bm-gray-lt: #f4f4f5;
  --bm-gray-md: #d4d4d8;
  --bm-gray-dk: #272727;
  --bm-font-display: 'Unbounded', 'Segoe UI', system-ui, sans-serif;
  --bm-font-body: 'Plus Jakarta Sans', 'Segoe UI', system-ui, sans-serif;
  font-family: var(--bm-font-body);
  color: var(--bm-black);
  background: var(--bm-white);
  overflow-x: clip;
}
.bm-landing * { box-sizing: border-box; }
.bm-landing a { color: inherit; text-decoration: none; }
.bm-landing ul { margin: 0; padding: 0; list-style: none; }
.bm-landing img { max-width: 100%; }

.bm-btn {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--bm-font-display); font-weight: 700; font-size: 0.8rem;
  letter-spacing: 0.02em; text-transform: uppercase;
  background: var(--bm-yellow); color: var(--bm-black);
  border: 2px solid var(--bm-black); border-radius: 8px;
  padding: 10px 18px; box-shadow: 4px 4px 0 var(--bm-black);
  transition: transform 0.12s ease, box-shadow 0.12s ease;
  cursor: pointer; white-space: nowrap;
}
.bm-btn:hover { transform: translate(-2px, -2px); box-shadow: 6px 6px 0 var(--bm-black); }
.bm-btn:active { transform: translate(1px, 1px); box-shadow: 2px 2px 0 var(--bm-black); }
.bm-btn-sm { padding: 8px 14px; font-size: 0.72rem; box-shadow: 3px 3px 0 var(--bm-black); }
.bm-btn-lg { padding: 14px 24px; font-size: 0.88rem; box-shadow: 5px 5px 0 var(--bm-black); }
.bm-btn-ghost { background: var(--bm-white); }
.bm-btn-invert { background: var(--bm-black); color: var(--bm-yellow); border-color: var(--bm-black); box-shadow: 5px 5px 0 var(--bm-yellow); }
.bm-btn-invert:hover { box-shadow: 7px 7px 0 var(--bm-yellow); }

.bm-nav { position: sticky; top: 0; z-index: 40; background: var(--bm-white); border-bottom: 2px solid var(--bm-black); }
.bm-nav-inner { max-width: 1180px; margin: 0 auto; padding: 14px 24px; display: flex; align-items: center; gap: 24px; }
.bm-brand { display: flex; align-items: center; gap: 10px; }
.bm-brand-mark { display: grid; place-items: center; width: 32px; height: 32px; background: var(--bm-black); color: var(--bm-yellow); border-radius: 7px; flex-shrink: 0; }
.bm-brand-name { font-family: var(--bm-font-display); font-weight: 800; font-size: 1rem; letter-spacing: 0.02em; }
.bm-nav-links { display: flex; gap: 22px; margin-left: auto; font-size: 0.85rem; font-weight: 600; }
.bm-nav-links a:hover { text-decoration: underline; text-underline-offset: 4px; }

.bm-disclaimer {
  background: var(--bm-charcoal); color: var(--bm-sage);
  font-size: 0.78rem; padding: 9px 24px; display: flex; flex-wrap: wrap;
  gap: 6px 16px; justify-content: center; text-align: center; align-items: center;
}
.bm-disclaimer a { display: inline-flex; align-items: center; gap: 4px; color: var(--bm-yellow); font-weight: 700; text-decoration: underline; text-underline-offset: 3px; }

.bm-hero { max-width: 1180px; margin: 0 auto; padding: 64px 24px 40px; display: grid; grid-template-columns: 1.05fr 0.95fr; gap: 48px; align-items: center; }
.bm-eyebrow { display: inline-block; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.06em; background: var(--bm-yellow); border: 2px solid var(--bm-black); border-radius: 999px; padding: 6px 14px; margin-bottom: 22px; }
.bm-h1 { font-family: var(--bm-font-display); font-weight: 800; font-size: clamp(2.1rem, 4.2vw, 3.4rem); line-height: 1.08; margin: 0 0 22px; text-wrap: balance; }
.bm-stroke { -webkit-text-stroke: 2px var(--bm-black); color: var(--bm-white); text-shadow: 3px 3px 0 var(--bm-black); }
.bm-lead { font-size: 1.05rem; line-height: 1.6; color: var(--bm-gray-dk); max-width: 46ch; margin: 0 0 30px; }
.bm-hero-ctas { display: flex; flex-wrap: wrap; gap: 14px; }

.bm-hero-visual { position: relative; }
.bm-blob { position: absolute; inset: 10% -8% auto auto; width: 200px; height: 200px; background: var(--bm-sage); border: 2px solid var(--bm-black); border-radius: 40% 60% 55% 45% / 50% 45% 55% 50%; z-index: -1; }
.bm-mock { background: var(--bm-white); border: 2px solid var(--bm-black); border-radius: 14px; box-shadow: 10px 10px 0 var(--bm-black); overflow: hidden; }
.bm-mock-bar { display: flex; align-items: center; gap: 6px; padding: 10px 12px; border-bottom: 2px solid var(--bm-black); background: var(--bm-gray-lt); }
.bm-dot { width: 9px; height: 9px; border-radius: 999px; background: var(--bm-black); opacity: 0.15; }
.bm-mock-url { margin-left: 10px; font-size: 0.72rem; font-weight: 600; color: var(--bm-gray-dk); }
.bm-mock-body { padding: 18px; display: flex; flex-direction: column; gap: 14px; }
.bm-mock-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.bm-mock-stat { border: 2px solid var(--bm-black); border-radius: 8px; padding: 8px 6px; text-align: center; }
.bm-mock-stat strong { display: block; font-family: var(--bm-font-display); font-size: 1.1rem; }
.bm-mock-stat span { font-size: 0.62rem; font-weight: 600; color: var(--bm-gray-dk); text-transform: uppercase; }
.bm-mock-stat-warn { background: var(--bm-yellow); }
.bm-mock-stat-crit { background: var(--bm-black); color: var(--bm-white); }
.bm-mock-stat-crit span { color: var(--bm-gray-md); }
.bm-mock-checks { display: flex; flex-direction: column; gap: 7px; }
.bm-mock-check { display: flex; align-items: center; gap: 8px; font-size: 0.75rem; font-weight: 600; border: 2px solid var(--bm-black); border-radius: 7px; padding: 7px 10px; }
.bm-pass { color: #14532d; background: #ecfdf3; }
.bm-fail { color: #7f1d1d; background: #fef2f2; }
.bm-warn { color: #713f12; background: #fffbeb; }
.bm-mock-score { display: flex; justify-content: space-between; align-items: center; border: 2px solid var(--bm-black); border-radius: 8px; padding: 9px 12px; background: var(--bm-charcoal); color: var(--bm-white); font-size: 0.78rem; }
.bm-mock-score strong { font-family: var(--bm-font-display); color: var(--bm-yellow); }

.bm-marquee { border-top: 2px solid var(--bm-black); border-bottom: 2px solid var(--bm-black); background: var(--bm-charcoal); overflow: hidden; padding: 14px 0; }
.bm-marquee-track { display: flex; width: max-content; animation: bm-scroll 26s linear infinite; }
.bm-marquee-group { display: flex; align-items: center; }
.bm-marquee-group span { color: var(--bm-sage); font-family: var(--bm-font-display); font-weight: 700; font-size: 0.82rem; letter-spacing: 0.04em; padding: 0 26px; white-space: nowrap; }
@keyframes bm-scroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
@media (prefers-reduced-motion: reduce) { .bm-marquee-track { animation: none; } }

.bm-section { max-width: 1180px; margin: 0 auto; padding: 72px 24px; }
.bm-h2 { font-family: var(--bm-font-display); font-weight: 800; font-size: clamp(1.5rem, 2.6vw, 2.1rem); margin: 0 0 34px; text-wrap: balance; }

.bm-ps-grid { display: grid; grid-template-columns: 1fr auto 1fr; gap: 20px; align-items: center; }
.bm-ps-card { border: 2px solid var(--bm-black); border-radius: 14px; padding: 26px; box-shadow: 6px 6px 0 var(--bm-black); }
.bm-ps-old { background: var(--bm-gray-lt); }
.bm-ps-new { background: var(--bm-yellow); }
.bm-ps-label { display: inline-block; font-size: 0.7rem; font-weight: 800; letter-spacing: 0.06em; margin-bottom: 14px; }
.bm-ps-card li { position: relative; padding-left: 20px; margin-bottom: 10px; font-size: 0.9rem; line-height: 1.5; }
.bm-ps-card li::before { content: '\\2022'; position: absolute; left: 0; font-weight: 900; }
.bm-ps-arrow { display: grid; place-items: center; }

.bm-feature-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.bm-card { border: 2px solid var(--bm-black); border-radius: 14px; padding: 26px; background: var(--bm-white); box-shadow: 6px 6px 0 var(--bm-black); }
.bm-card-yellow { background: var(--bm-yellow); }
.bm-card-sage { background: var(--bm-sage); }
.bm-card-icon { display: grid; place-items: center; width: 44px; height: 44px; background: var(--bm-black); color: var(--bm-yellow); border-radius: 10px; margin-bottom: 16px; }
.bm-card h3 { font-family: var(--bm-font-display); font-size: 1.05rem; margin: 0 0 10px; }
.bm-card p { font-size: 0.88rem; line-height: 1.55; color: var(--bm-gray-dk); margin: 0; }

.bm-steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; }
.bm-step-num { display: grid; place-items: center; width: 48px; height: 48px; border-radius: 999px; background: var(--bm-charcoal); color: var(--bm-yellow); box-shadow: 0 0 0 4px var(--bm-yellow), 0 0 22px rgba(255,225,124,0.55); margin-bottom: 16px; }
.bm-step h3 { font-family: var(--bm-font-display); font-size: 1rem; margin: 0 0 8px; }
.bm-step p { font-size: 0.88rem; line-height: 1.55; color: var(--bm-gray-dk); margin: 0; }

.bm-persona-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.bm-persona { border: 2px solid var(--bm-black); border-radius: 0 20px 0 20px; padding: 24px; background: var(--bm-white); }
.bm-persona-alt { background: var(--bm-charcoal); color: var(--bm-white); border-radius: 20px 0 20px 0; }
.bm-persona-tag { font-family: var(--bm-font-display); font-weight: 800; font-size: 0.75rem; color: var(--bm-yellow-hi); }
.bm-persona h3 { font-family: var(--bm-font-display); font-size: 1rem; margin: 10px 0 8px; }
.bm-persona p { font-size: 0.86rem; line-height: 1.55; color: var(--bm-gray-dk); margin: 0; }
.bm-persona-alt p { color: var(--bm-sage); }

.bm-stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 26px; }
.bm-stat { border: 2px solid var(--bm-black); border-radius: 12px; padding: 20px 14px; text-align: center; background: var(--bm-gray-lt); }
.bm-stat strong { display: block; font-family: var(--bm-font-display); font-size: 1.7rem; }
.bm-stat span { font-size: 0.74rem; font-weight: 600; color: var(--bm-gray-dk); }
.bm-limits { display: flex; gap: 12px; align-items: flex-start; border: 2px solid var(--bm-black); border-radius: 12px; padding: 18px; background: #fffbeb; }
.bm-limits svg { flex-shrink: 0; margin-top: 2px; color: #b45309; }
.bm-limits p { margin: 0; font-size: 0.86rem; line-height: 1.6; }
.bm-limits a { text-decoration: underline; text-underline-offset: 3px; font-weight: 700; }

.bm-cta { text-align: center; padding: 80px 24px; background: var(--bm-charcoal); color: var(--bm-white); border-top: 2px solid var(--bm-black); border-bottom: 2px solid var(--bm-black); }
.bm-cta h2 { font-family: var(--bm-font-display); font-weight: 800; font-size: clamp(1.6rem, 3.2vw, 2.4rem); margin: 0 0 10px; text-wrap: balance; }
.bm-cta p { color: var(--bm-sage); margin: 0 0 26px; }

.bm-footer { background: var(--bm-white); padding: 52px 24px 24px; }
.bm-footer-grid { max-width: 1180px; margin: 0 auto; display: grid; grid-template-columns: 1.4fr 1fr 1fr 1fr; gap: 32px; }
.bm-footer-grid p { font-size: 0.82rem; line-height: 1.5; color: var(--bm-gray-dk); margin: 12px 0 0; max-width: 32ch; }
.bm-footer-head { display: block; font-family: var(--bm-font-display); font-weight: 700; font-size: 0.78rem; letter-spacing: 0.03em; margin-bottom: 12px; }
.bm-footer-grid a, .bm-footer-plain { display: block; font-size: 0.85rem; margin-bottom: 8px; color: var(--bm-gray-dk); }
.bm-footer-grid a:hover { text-decoration: underline; }
.bm-footer-bottom { max-width: 1180px; margin: 40px auto 0; padding-top: 20px; border-top: 2px solid var(--bm-black); font-size: 0.76rem; color: var(--bm-gray-dk); text-align: center; }

@media (max-width: 860px) {
  .bm-hero { grid-template-columns: 1fr; padding-top: 40px; }
  .bm-nav-links { display: none; }
  .bm-ps-grid { grid-template-columns: 1fr; }
  .bm-ps-arrow { transform: rotate(90deg); }
  .bm-feature-grid, .bm-steps, .bm-persona-grid { grid-template-columns: 1fr; }
  .bm-stat-grid { grid-template-columns: repeat(2, 1fr); }
  .bm-footer-grid { grid-template-columns: 1fr 1fr; }
  .bm-mock-stats { grid-template-columns: repeat(2, 1fr); }
}
`;
