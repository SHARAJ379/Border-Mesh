import { createContext, useContext } from 'react';

// Shares the app's single real scroll container (App's <main>) with any
// component that needs to register a GSAP ScrollTrigger against it --
// there's no window-level scrolling in this dashboard shell.
export const ScrollerContext = createContext<HTMLElement | null>(null);

export function useScroller(): HTMLElement | null {
  return useContext(ScrollerContext);
}
