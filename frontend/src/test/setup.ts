import '@testing-library/jest-dom/vitest';

// jsdom has no ResizeObserver -- ScrollShadowX (used by table-heavy pages
// like DashboardPage/AnalyticsPage) observes its container's size, which
// would otherwise throw "ResizeObserver is not defined" in every test that
// renders a page using it.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub;

// jsdom has no matchMedia -- GSAP's ScrollTrigger plugin (registered at
// module load by ScrollReveal, used throughout the dashboard for
// scroll-linked reveals) calls window.matchMedia internally when it
// registers, which otherwise throws "matchMedia is not a function" in
// every test that renders a page using ScrollReveal.
window.matchMedia = window.matchMedia || function (query: string) {
  return {
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  } as unknown as MediaQueryList;
};
