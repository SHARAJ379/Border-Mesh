import { useEffect } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

/**
 * Resets the dashboard's single scroll container (App's <main>) to the top
 * whenever `resetKey` changes. App.tsx swaps its whole page body under this
 * SAME scroller on every sidebar tab change (single-page, tab-state driven,
 * no router remount -- see App.tsx), so without this the newly-shown page
 * silently inherits whatever scroll offset the previous page was left at
 * instead of starting at its own top.
 *
 * Plain native scrolling -- this used to wrap `scroller` in Lenis for a
 * smoothed/eased wheel feel, but that replaced the user's own scroll input
 * with Lenis's animated easing curve, which read as the page auto-scrolling
 * instead of responding directly to wheel/trackpad input. Removed per user
 * report. ScrollReveal's GSAP ScrollTrigger instances point `scroller` at
 * this same native element directly -- no proxy needed now that there's no
 * animated scroll position to bridge.
 */
export function useLenis(scroller: HTMLElement | null, resetKey?: unknown) {
  useEffect(() => {
    if (resetKey === undefined || !scroller) return;
    scroller.scrollTop = 0;
    ScrollTrigger.refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey]);
}
