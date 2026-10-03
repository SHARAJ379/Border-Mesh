import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, ArrowUpRight, Shield, Link2 } from 'lucide-react';
import { prefersReducedMotion } from '../lib/deviceCapability';
import { SceneBackground } from '../three/SceneBackground';

// Smooth-scrolls the nav's #argument/#demonstration/etc. anchor jumps using
// the browser's own native smooth scroll (each target section already
// carries `scroll-mt-[58px]` so it lands clear of the fixed nav), not a
// JS-driven tween: GSAP's ScrollToPlugin was tried here first, but every
// GSAP tween on this page (this one included) depends on GSAP's own
// requestAnimationFrame ticker, which browsers throttle hard the moment a
// tab isn't the visible/focused one -- exactly the situation this was
// caught in during testing. `scrollIntoView` is driven by the browser's
// own compositor, not page JS, so it isn't subject to that at all.
function smoothScrollTo(hash: string) {
  document.querySelector(hash)?.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });
}

/**
 * Public-facing intro page, redesigned for the blockchain/cybersecurity
 * SIH theme (see git history for the warm-paper "maker's landing page"
 * this replaces): ground #0B1120, ink #EDF1F9, one accent cyan #38BDF8
 * reserved for type/rules/drawn lines, Space Grotesk for headings, Inter
 * for body, JetBrains Mono for data/figures. The revived MeshNetwork/
 * SceneBackground WebGL layer (see ../three) stands in for the old
 * SpreadWordmark-and-photo warm-paper imagery -- a node network reads as
 * "security/verification mesh," not decoration. Content stays grounded in
 * the actual pipeline and KNOWN_LIMITATIONS.md -- see FACTS below -- not
 * invented copy; the one genuinely blockchain-related fact already in the
 * product (hash-chained audit ledger, anchored to Ethereum Sepolia) is
 * surfaced more prominently below rather than inventing new claims.
 */

// Every number here is sourced from the codebase, not invented -- the
// spec's own "Evidence rules" applied to this page's content the same way
// it was applied to the Privacy Policy and Terms & Conditions.
const FACTS = {
  documentTypes: 7, // Passport, Aadhaar, PAN, Driving Licence, Voter ID, Visa, Permit -- app/services/ocr_service.py
  riskFactors: 6, // MRZ_VALIDATION, TAMPER, FACE, CONSISTENCY, WATCHLIST, IDENTITY -- app/services/risk_types.py
  backendTests: 281, // pytest collection count, verified this session
  tamperRecall: '39.5%',
  tamperMissed: '60.6%',
  weights: [
    { key: 'MRZ & document validation', pct: 25 },
    { key: 'Forensic tamper AI (ELA)', pct: 30 },
    { key: 'Biometric face verification', pct: 30 },
    { key: 'Data consistency crosscheck', pct: 10 },
    { key: 'Simulated watchlist adapter', pct: 5 },
  ],
};

const TIERS = [
  { id: 'low', label: 'Low', score: 12, recommendation: 'Clear for entry', factor: 'MRZ checksum verified', checks: '18 of 18 checks passed' },
  { id: 'medium', label: 'Medium', score: 38, recommendation: 'Routine confirmation', factor: 'Minor OCR/MRZ field mismatch', checks: '15 of 18 checks passed' },
  { id: 'high', label: 'High', score: 62, recommendation: 'Secondary inspection', factor: 'ELA flagged 2 tamper regions', checks: '11 of 18 checks passed' },
  { id: 'critical', label: 'Critical', score: 91, recommendation: 'Detain for review', factor: 'Face match below threshold', checks: '6 of 18 checks passed' },
] as const;

function useOnceVisible<T extends HTMLElement>(): [React.RefObject<T | null>, boolean] {
  const ref = useRef<T | null>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (prefersReducedMotion() || typeof IntersectionObserver === 'undefined') { setVisible(true); return; }
    const io = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); io.disconnect(); } },
      { threshold: 0.3 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return [ref, visible];
}

// Entrance reveal for the sections below the fold -- plain CSS opacity/
// transform driven by IntersectionObserver (the same technique already
// proven on this page for the demonstration gauge), not GSAP ScrollTrigger:
// this standalone page mounts every section's trigger simultaneously at
// scrollY 0 with no Lenis/App shell around it, and ScrollTrigger's
// scroll-position polling didn't settle cleanly in that context (tweens
// stuck re-triggering mid-fade instead of completing). IntersectionObserver
// has no such dependency on continuous scroll-position math -- it just
// reports "is this on screen," once, and fires reliably either way. Fires
// once and never un-reveals, per the source spec's own motion-model rule.
const Reveal: React.FC<{ children: React.ReactNode; className?: string; delay?: number }> = ({ children, className, delay = 0 }) => {
  const [ref, visible] = useOnceVisible<HTMLDivElement>();
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(18px)',
        transition: prefersReducedMotion() ? 'none' : `opacity 600ms ease-out ${delay}s, transform 600ms ease-out ${delay}s`,
      }}
    >
      {children}
    </div>
  );
}

const SpreadWordmark: React.FC<{ shrinkOnScroll?: boolean }> = ({ shrinkOnScroll }) => {
  const [spread, setSpread] = useState(0); // 0..1
  const [loaded, setLoaded] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t = setTimeout(() => setLoaded(true), 60);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!shrinkOnScroll || prefersReducedMotion()) return;
    let raf = 0;
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const el = rootRef.current;
        if (!el) return;
        const rect = el.getBoundingClientRect();
        const vh = window.innerHeight;
        // Bound to scroll POSITION (reversible): 0 while the mark sits at
        // the foot of the hero, ramping to 1 as it's scrolled well past.
        const progress = Math.min(Math.max((vh - rect.top) / (vh * 1.4), 0), 1);
        setSpread(progress);
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => { window.removeEventListener('scroll', onScroll); cancelAnimationFrame(raf); };
  }, [shrinkOnScroll]);

  const letters = 'BORDERMESH'.split('');
  return (
    <div
      ref={rootRef}
      aria-hidden="true"
      className="flex w-[104%] -ml-[2%] select-none overflow-hidden"
      style={{ justifyContent: 'space-between' }}
    >
      {letters.map((ch, i) => (
        <span
          key={i}
          className="font-display text-ink"
          style={{
            fontSize: 'clamp(38px, 10vw, 140px)',
            letterSpacing: '-0.04em',
            lineHeight: 1,
            transform: `translateY(${loaded ? '0.15em' : '1.1em'}) translateY(${spread * (i % 2 === 0 ? -6 : 6)}px) translateX(${spread * (i - letters.length / 2) * 3}px)`,
            opacity: loaded ? Math.max(1 - spread * 0.7, 0.3) : 0,
            transition: prefersReducedMotion()
              ? 'none'
              : `transform 900ms cubic-bezier(.16,.8,.24,1) ${i * 22}ms, opacity 900ms ease ${i * 22}ms`,
          }}
        >
          {ch}
        </span>
      ))}
    </div>
  );
};

const TravelingProduct: React.FC = () => {
  const [t, setT] = useState(0); // 0..1 scroll progress through the travel range
  const [reduced] = useState(prefersReducedMotion());

  useEffect(() => {
    if (reduced) return;
    let raf = 0;
    const travelPx = Math.max(window.innerHeight * 0.9, 500);
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        setT(Math.min(Math.max(window.scrollY / travelPx, 0), 1));
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => { window.removeEventListener('scroll', onScroll); cancelAnimationFrame(raf); };
  }, [reduced]);

  if (reduced) return null;

  // Stops expressed as viewport percentages, per the spec, so the path
  // holds at any size. Kept entirely in the right-hand margin, clear of
  // the copy block (max 46vw) and the argument section's content below --
  // it drifts and shrinks slightly, fully faded before the hero itself is
  // scrolled past, per "fade it out once the sections that need it are
  // behind you."
  const stops = [
    { at: 0, x: 82, y: 14, rot: -6, scale: 1, opacity: 1 },
    { at: 0.5, x: 75, y: 30, rot: 2, scale: 0.86, opacity: 0.85 },
    { at: 1, x: 71, y: 44, rot: -2, scale: 0.68, opacity: 0 },
  ];
  let a = stops[0], b = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i++) {
    if (t >= stops[i].at && t <= stops[i + 1].at) { a = stops[i]; b = stops[i + 1]; break; }
  }
  const span = (b.at - a.at) || 1;
  const lp = Math.min(Math.max((t - a.at) / span, 0), 1);
  const lerp = (x: number, y: number) => x + (y - x) * lp;
  const x = lerp(a.x, b.x), y = lerp(a.y, b.y), rot = lerp(a.rot, b.rot), scale = lerp(a.scale, b.scale), opacity = lerp(a.opacity, b.opacity);

  // Swapped from the warm-paper spec's "traveling specimen photo" to a
  // verification HUD chip -- same drift/fade scroll-math, new content: a
  // hash-chain readout tied to the one real blockchain fact this product
  // has (see FACTS/MATERIAL's "Audit anchoring... Ethereum Sepolia
  // testnet" row below), not an invented crypto claim.
  return (
    <div
      aria-hidden="true"
      className="glow-accent"
      style={{
        position: 'fixed',
        left: `${x}%`,
        top: `${y}%`,
        width: 'min(26vw, 230px)',
        aspectRatio: '3 / 4',
        background: 'var(--color-paper-dim)',
        border: '1px solid var(--color-hairline)',
        transform: `translate(-50%, -50%) rotate(${rot}deg) scale(${scale})`,
        opacity,
        visibility: opacity <= 0.01 ? 'hidden' : 'visible',
        pointerEvents: 'none',
        zIndex: 5,
        padding: '10%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
      }}
    >
      <div className="flex items-center justify-between">
        <Shield className="w-5 h-5 text-accent" strokeWidth={1.5} />
        <span className="flex items-center gap-1.5 font-mono text-signal-low" style={{ fontSize: 9, letterSpacing: '0.08em' }}>
          <span className="w-1.5 h-1.5 rounded-full bg-signal-low animate-pulse" />
          VERIFIED
        </span>
      </div>
      {/* Fixed vw/px sizing throughout this row, not percentages -- a
          percentage width nested inside this fixed-position, rotated/
          scaled card reliably resolves to ~0 in Chromium (reproduced with
          flex and grid alike; explicit px/vw is unaffected), so every
          child here is sized the same way the card itself already is. */}
      <div className="space-y-1.5">
        <div className="font-mono text-ink-soft" style={{ fontSize: 9, letterSpacing: '0.04em' }}>
          0x7f3a9e21&hellip;b4d802c1
        </div>
        <div style={{ height: 2, background: 'var(--color-hairline)', width: '100%' }}>
          <div style={{ height: 2, width: '70%', background: 'var(--color-accent)' }} />
        </div>
        <div style={{ height: 2, background: 'var(--color-hairline)', width: '82%' }}>
          <div style={{ height: 2, width: '45%', background: 'var(--color-signal-low)' }} />
        </div>
      </div>
      <span className="flex items-center gap-1 font-mono text-muted" style={{ fontSize: 9, letterSpacing: '0.08em' }}>
        <Link2 className="w-2.5 h-2.5" strokeWidth={1.75} />
        SEPOLIA TESTNET
      </span>
    </div>
  );
};

const RuleRow: React.FC<{ label: string; description: string; value: string }> = ({ label, description, value }) => (
  <div className="rule-row">
    <div className="min-w-0 pr-4">
      <span className="label-eyebrow block mb-1">{label}</span>
      <span className="text-[13px] text-ink-soft">{description}</span>
    </div>
    <span className="figure text-[13px] text-ink shrink-0 whitespace-nowrap">{value}</span>
  </div>
);

const Gauge: React.FC<{ score: number }> = ({ score }) => {
  const circleRef = useRef<SVGCircleElement>(null);
  const [gaugeRef, visible] = useOnceVisible<HTMLDivElement>();
  const [length, setLength] = useState(0);
  const R = 84;
  const CIRCUMFERENCE = 2 * Math.PI * R;

  useEffect(() => {
    const el = circleRef.current;
    if (el && typeof el.getTotalLength === 'function') {
      setLength(el.getTotalLength());
    } else {
      setLength(CIRCUMFERENCE);
    }
  }, [CIRCUMFERENCE]);

  const fraction = score / 100;
  const dashOffset = visible ? CIRCUMFERENCE * (1 - fraction) : CIRCUMFERENCE;

  return (
    <div ref={gaugeRef} className="flex items-center justify-center">
      <svg width="200" height="200" viewBox="0 0 200 200">
        <circle cx="100" cy="100" r={R} fill="none" stroke="var(--color-hairline)" strokeWidth="1.5" />
        <circle
          ref={circleRef}
          cx="100" cy="100" r={R}
          fill="none"
          stroke="var(--color-accent)"
          strokeWidth="2"
          strokeDasharray={length || CIRCUMFERENCE}
          strokeDashoffset={dashOffset}
          strokeLinecap="square"
          transform="rotate(-90 100 100)"
          style={{ transition: prefersReducedMotion() ? 'none' : 'stroke-dashoffset 1.8s cubic-bezier(.2,.7,.2,1)' }}
        />
        <text x="100" y="96" textAnchor="middle" className="font-display" fill="var(--color-ink)" fontSize="40">{score}</text>
        <text x="100" y="120" textAnchor="middle" className="font-sans" fill="var(--color-muted)" fontSize="10" letterSpacing="1">/ 100</text>
      </svg>
    </div>
  );
};

export const WelcomePage: React.FC = () => {
  const [tier, setTier] = useState<typeof TIERS[number]>(TIERS[0]);

  const handleAnchorClick = (e: React.MouseEvent<HTMLAnchorElement>, hash: string) => {
    e.preventDefault();
    smoothScrollTo(hash);
    history.pushState(null, '', hash);
  };

  return (
    <div className="bg-paper text-ink" style={{ fontFamily: 'var(--font-sans)' }}>
      <SceneBackground />
      <TravelingProduct />

      {/* ---------- NAV ---------- */}
      <header className="fixed top-0 inset-x-0 z-40 h-[58px] bg-paper/85 backdrop-blur-md border-b border-hairline">
        <div className="max-w-[1180px] mx-auto h-full px-6 flex items-center justify-between">
          <a href="/welcome" className="font-display text-[19px] text-ink">BorderMesh<span className="text-accent">.</span></a>
          <nav className="hidden md:flex items-center gap-7 text-[11px] uppercase tracking-[0.08em]">
            <a href="#argument" onClick={(e) => handleAnchorClick(e, '#argument')} className="hover:text-accent transition-colors">Pipeline</a>
            <a href="#demonstration" onClick={(e) => handleAnchorClick(e, '#demonstration')} className="hover:text-accent transition-colors">Demonstration</a>
            <a href="#material" onClick={(e) => handleAnchorClick(e, '#material')} className="hover:text-accent transition-colors">Material</a>
            <a href="#measurements" onClick={(e) => handleAnchorClick(e, '#measurements')} className="hover:text-accent transition-colors">Measurements</a>
          </nav>
          <div className="flex items-center gap-4">
            <span className="hidden sm:flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-signal-low">
              <span className="w-1.5 h-1.5 rounded-full bg-signal-low animate-pulse" />
              pipeline online
            </span>
            <a href="/" className="btn-primary text-[11px] px-4 py-2">Open Dashboard</a>
          </div>
        </div>
      </header>

      {/* ---------- HERO ----------
          Background left transparent (not bg-paper-dim) so the revived
          mesh-network WebGL layer, mounted above, is the hero's visual
          centerpiece instead of a flat panel sitting on top of it. */}
      <section className="relative min-h-screen overflow-hidden flex flex-col pt-[58px]">
        <div aria-hidden="true" className="grid-overlay pointer-events-none absolute inset-0 opacity-60" />
        <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-40 bg-gradient-to-b from-transparent to-[var(--color-paper)]" />
        {/* Readability scrim: the mesh's connector lines cross straight
            through the copy column otherwise -- fades paper-solid behind
            the text, full mesh exposure kept on the right where the HUD
            chip/network drift freely. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 left-0 w-[58%] md:w-[50%]"
          style={{ background: 'linear-gradient(to right, var(--color-paper) 0%, var(--color-paper) 40%, transparent 100%)' }}
        />
        <div className="relative max-w-[1180px] mx-auto w-full px-6 flex-1 flex flex-col">
          <div className="flex-1 flex flex-col justify-center py-16" style={{ maxWidth: '46vw' }}>
            <span className="flex items-center gap-2 label-eyebrow mb-5">
              <Link2 className="w-3 h-3 text-accent" strokeWidth={2} />
              SIH26188 &middot; Smart India Hackathon 2026 &middot; Ministry of Home Affairs
            </span>
            <h1 className="hero-title font-display text-ink" style={{ fontSize: 'clamp(32px, 4.6vw, 68px)', lineHeight: 1.04 }}>
              Screen documents.<br />Explain every <em>decision</em>.
            </h1>
            <p className="mt-6 text-[13px] text-ink-soft max-w-[52ch]">
              BorderMesh runs every document through OCR, MRZ validation, forensic tamper analysis,
              face verification and watchlist screening, then hands the officer an itemized,
              evidence-backed reason for the score — not just a number.
            </p>
            <div className="flex items-center gap-4 mt-8">
              <a href="/" className="btn-primary text-[11px] px-5 py-3">Open Screening Dashboard <ArrowRight className="w-3.5 h-3.5" /></a>
              <a href="#demonstration" onClick={(e) => handleAnchorClick(e, '#demonstration')} className="btn-secondary text-[11px] px-5 py-3">See it work</a>
            </div>
          </div>

          <div className="border-t border-hairline py-4 mt-auto grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              ['Document types', String(FACTS.documentTypes)],
              ['Risk factors', String(FACTS.riskFactors)],
              ['Backend tests', String(FACTS.backendTests)],
              ['Tamper recall', FACTS.tamperRecall],
            ].map(([label, value]) => (
              <div key={label}>
                <span className="label-eyebrow block mb-1">{label}</span>
                <span className="figure text-[15px] text-ink">{value}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="max-w-[1180px] mx-auto w-full px-6 pb-2">
          <SpreadWordmark shrinkOnScroll />
        </div>
      </section>

      {/* The mesh-network background is `position: fixed`, so without an
          opaque backdrop it would keep bleeding through every section
          below (confirmed visually -- text contrast against the busy mesh
          lines dropped badly scrolled past the hero). Everything from here
          down sits on solid bg-paper; only the hero stays transparent to
          show the mesh. */}
      <div className="relative z-10 bg-paper">
      {/* ---------- ARGUMENT ---------- */}
      <section id="argument" className="scroll-mt-[58px] max-w-[1180px] mx-auto px-6 py-24 grid grid-cols-1 md:grid-cols-2 gap-12">
        <Reveal>
          <h2 className="font-display text-[30px] leading-tight mb-4">
            One pipeline, not five<br />separate tools.
          </h2>
          <p className="text-[13px] text-ink-soft max-w-[46ch]">
            Manual visual inspection has no forensic backing. OCR, tamper checks and watchlist
            screening run in silos. A flagged case gets no written reason for why. BorderMesh
            runs every signal together and returns a risk score built from itemized checks, each
            with its own evidence, weighted as below.
          </p>
        </Reveal>
        <Reveal delay={0.12}>
          {FACTS.weights.map((w) => (
            <RuleRow key={w.key} label={w.key} description="Contributes to the composite risk score" value={`${w.pct}%`} />
          ))}
        </Reveal>
      </section>

      {/* ---------- DEMONSTRATION ---------- */}
      <section id="demonstration" className="scroll-mt-[58px] max-w-[1180px] mx-auto px-6 py-24">
        <Reveal>
          <h2 className="font-display text-[30px] leading-tight mb-8">A score with its reasons attached.</h2>
          <div className="flex flex-wrap gap-2 mb-8" role="group" aria-label="Risk tier">
            {TIERS.map((tr) => (
              <button
                key={tr.id}
                aria-pressed={tier.id === tr.id}
                onClick={() => setTier(tr)}
                className="tab-flat tab-flat-accent px-3"
              >
                {tr.label}
              </button>
            ))}
          </div>
        </Reveal>
        <Reveal delay={0.12} className="panel p-10 grid grid-cols-1 md:grid-cols-2 gap-10 items-center">
          <Gauge score={tier.score} />
          <div className="space-y-5">
            <RuleRow label="Recommended action" description="Officer makes the final call" value={tier.recommendation} />
            <RuleRow label="Leading factor" description="Highest-weighted contributor" value={tier.factor} />
            <RuleRow label="Itemized checks" description="Pass/fail evidence behind the score" value={tier.checks} />
          </div>
        </Reveal>
      </section>

      {/* ---------- MATERIAL ---------- */}
      <section id="material" className="scroll-mt-[58px] max-w-[1180px] mx-auto px-6 py-24 grid grid-cols-1 md:grid-cols-2 gap-12">
        <Reveal>
          <h2 className="font-display text-[30px] leading-tight mb-4">Built from real,<br />verifiable parts.</h2>
          <p className="text-[13px] text-ink-soft max-w-[46ch]">
            Each subsystem is a real, independently-testable implementation, not a mock —
            demonstrating that the pipeline's architecture works end to end, not that it matches
            commercial vendors' breadth of document coverage.
          </p>
        </Reveal>
        <Reveal delay={0.12}>
          <RuleRow label="OCR extraction" description="Tesseract 5.5 field extraction" value="Active" />
          <RuleRow label="MRZ parser" description="ICAO 9303 checksum validation" value="Active" />
          <RuleRow label="Tamper AI" description="PyTorch CNN + error-level analysis" value="Active" />
          <RuleRow label="Face verification" description="Cosine similarity embedding net" value="Active" />
          <RuleRow label="Audit anchoring" description="Hash-chained ledger, Ethereum Sepolia testnet" value="Optional" />
          <RuleRow label="Data handling" description="DPDP Act 2023 principles, mapped honestly" value="Aligned" />
        </Reveal>
      </section>

      {/* ---------- MEASUREMENTS ---------- */}
      <section id="measurements" className="scroll-mt-[58px] max-w-[820px] mx-auto px-6 py-24">
        <Reveal>
          <h2 className="font-display text-[30px] leading-tight mb-8">What's actually measured.</h2>
          <RuleRow label="Document types" description="Passport, Aadhaar, PAN, Driving Licence, Voter ID, Visa, Permit" value={String(FACTS.documentTypes)} />
          <RuleRow label="Risk factors" description="Each itemized into pass/fail checks with evidence" value={String(FACTS.riskFactors)} />
          <RuleRow label="Backend tests" description="Automated pytest suite, verified this session" value={String(FACTS.backendTests)} />
          <RuleRow label="Tamper recall" description="Real, human-made forgeries caught in testing" value={FACTS.tamperRecall} />
          <RuleRow label="Tamper missed" description="Real forgeries that slip through undetected" value={FACTS.tamperMissed} />
          <RuleRow label="Encryption" description="Fernet, AES-128-CBC + HMAC-SHA256, authenticated" value="At rest" />
          <div className="strip mt-8 py-4 px-1">
            Full breakdown of what's implemented versus simulated, including the watchlist's
            fictional data and the single static demo encryption key, in the{' '}
            <a href="/terms" className="text-accent underline underline-offset-2">Terms &amp; Conditions</a>.
          </div>
        </Reveal>
      </section>

      {/* ---------- CLOSE ---------- */}
      <section className="bg-paper-dim border-t border-hairline">
        <div className="max-w-[1180px] mx-auto px-6 pt-24 pb-6">
          <Reveal>
            <h2 className="font-display leading-tight mb-4" style={{ fontSize: 'clamp(28px, 3.6vw, 46px)' }}>
              Every screening comes<br />with its <em>reasons</em>.
            </h2>
            <p className="text-[12px] text-muted max-w-[60ch] mb-10">
              SIH26188 prototype for the Ministry of Home Affairs — a decision-support demo,
              not a certified or production system. Not for use in live operational screening.
            </p>
            <div className="flex items-center justify-between flex-wrap gap-4 pb-10">
              <a href="/" className="btn-primary text-[11px] px-5 py-3">Open the Dashboard <ArrowRight className="w-3.5 h-3.5" /></a>
              <a href="/terms" className="btn-secondary text-[11px] px-5 py-3">Read the Limitations <ArrowUpRight className="w-3.5 h-3.5" /></a>
            </div>
            <div className="strip py-4 flex flex-wrap gap-x-6 gap-y-2 text-[11px] uppercase tracking-[0.06em]">
              <a href="/" className="hover:text-accent">Dashboard</a>
              <a href="/privacy" className="hover:text-accent">Privacy Policy</a>
              <a href="/terms" className="hover:text-accent">Terms &amp; Conditions</a>
              <span className="text-muted normal-case tracking-normal ml-auto">Theme: Blockchain &amp; Cybersecurity</span>
            </div>
          </Reveal>
          <SpreadWordmark />
        </div>
      </section>
      </div>
    </div>
  );
};
