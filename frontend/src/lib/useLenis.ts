import { useEffect } from 'react';
import Lenis from 'lenis';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { scrollProgressStore } from './scrollProgress';
import { prefersReducedMotion } from './deviceCapability';

gsap.registerPlugin(ScrollTrigger);

/**
 * Wires Lenis smooth-scroll to a specific scroll container (App's <main>,
 * not window -- this is a fixed dashboard shell, not a document that
 * scrolls natively) and keeps GSAP ScrollTrigger in sync with it via the
 * scrollerProxy API, so ScrollTrigger-based reveals inside that container
 * fire at the right offsets.
 */
export function useLenis(scroller: HTMLElement | null) {
  useEffect(() => {
    if (!scroller) return;

    if (prefersReducedMotion()) {
      // Respect the OS-level preference: no smoothing, no scroll-linked
      // background reactivity, just native scrolling.
      return;
    }

    const lenis = new Lenis({
      wrapper: scroller,
      content: scroller.firstElementChild as HTMLElement,
      duration: 1.1,
      smoothWheel: true,
    });

    ScrollTrigger.scrollerProxy(scroller, {
      scrollTop(value) {
        if (value !== undefined) {
          lenis.scrollTo(value, { immediate: true });
        }
        return lenis.scroll;
      },
      getBoundingClientRect() {
        return {
          top: 0,
          left: 0,
          width: scroller.clientWidth,
          height: scroller.clientHeight,
        };
      },
    });

    lenis.on('scroll', ({ scroll, limit, velocity }: { scroll: number; limit: number; velocity: number }) => {
      ScrollTrigger.update();
      scrollProgressStore.set(limit > 0 ? scroll / limit : 0, velocity);
    });

    function raf(time: number) {
      lenis.raf(time);
    }
    gsap.ticker.add(raf);
    gsap.ticker.lagSmoothing(0);

    const trigger = ScrollTrigger.create({ scroller });

    return () => {
      gsap.ticker.remove(raf);
      trigger.kill();
      lenis.destroy();
    };
  }, [scroller]);
}
