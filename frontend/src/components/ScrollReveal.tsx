import React, { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useScroller } from '../lib/ScrollerContext';
import { prefersReducedMotion } from '../lib/deviceCapability';

gsap.registerPlugin(ScrollTrigger);

interface ScrollRevealProps {
  children: React.ReactNode;
  className?: string;
  /** Stagger index for grid/list children entering in sequence. */
  delay?: number;
}

/**
 * The one reveal primitive every page uses for its sections/cards, so
 * transitions between sections feel consistent instead of each page
 * inventing its own entrance animation. Fades + lifts content in as it
 * scrolls into the shared scroller's viewport; no-ops entirely under
 * prefers-reduced-motion.
 */
export function ScrollReveal({ children, className, delay = 0 }: ScrollRevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const scroller = useScroller();

  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return;

    const ctx = gsap.context(() => {
      gsap.fromTo(
        el,
        { autoAlpha: 0, y: 18 },
        {
          autoAlpha: 1,
          y: 0,
          duration: 0.6,
          delay,
          ease: 'power2.out',
          scrollTrigger: {
            trigger: el,
            scroller: scroller ?? undefined,
            start: 'top 92%',
            toggleActions: 'play none none none',
          },
        }
      );
    });

    return () => ctx.revert();
  }, [scroller, delay]);

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}
