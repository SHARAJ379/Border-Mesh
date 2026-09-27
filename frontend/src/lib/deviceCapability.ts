// Shared heuristics for degrading the 3D background gracefully instead of
// tanking Lighthouse/perf on mobile or low-end hardware. Checked once at
// mount time (not reactively) -- these signals don't change mid-session.

export function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;
}

// Real feature-detection, not an environment-name guess: attempts to
// actually acquire a WebGL context on a throwaway canvas. Covers jsdom
// (unit tests -- HTMLCanvasElement.getContext('webgl'/'webgl2') always
// returns null there, which every WebGL-mounting component in this app
// -- SceneBackground, DashboardHeroBackground -- would otherwise crash
// into an uncaught "Error creating WebGL context" from inside a passive
// effect the moment a test's assertions await long enough for a lazy
// import to resolve) but also real browsers with WebGL genuinely
// disabled/blocked (GPU blocklist, some locked-down enterprise policies,
// certain private-browsing configurations) -- both are legitimately "can't
// render WebGL here," the same category isLowEndDevice already exists to
// degrade gracefully for.
let cachedHasWebGL: boolean | null = null;
export function hasWebGL(): boolean {
  if (cachedHasWebGL !== null) return cachedHasWebGL;
  if (typeof document === 'undefined') {
    cachedHasWebGL = false;
    return cachedHasWebGL;
  }
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    cachedHasWebGL = gl !== null;
  } catch {
    cachedHasWebGL = false;
  }
  return cachedHasWebGL;
}

// Touch/stylus input has no hover state and no cursor to drag a
// fine-grained UI affordance (a magnifier, a precise drag handle) with --
// the same "no cursor to work with" reasoning as the sketchbook-style
// loupe pattern this backs (see Magnifier.tsx), generalized to a shared
// device-capability check rather than a one-off matchMedia call inline in
// that component. `(pointer: coarse)` is the standard media-feature for
// "the primary input can't hover/point precisely" (touchscreens); mouse,
// trackpad, and stylus-with-hover all report `fine`.
export function isCoarsePointer(): boolean {
  return typeof window !== 'undefined' &&
    window.matchMedia?.('(pointer: coarse)').matches === true;
}

export function isLowEndDevice(): boolean {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return true;
  if (!hasWebGL()) return true;

  const smallViewport = window.innerWidth < 768;
  const fewCores = (navigator.hardwareConcurrency ?? 8) <= 4;
  const lowMemory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory !== undefined &&
    (navigator as Navigator & { deviceMemory?: number }).deviceMemory! <= 4;
  const saveData = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData === true;

  return prefersReducedMotion() || saveData || (smallViewport && (fewCores || lowMemory));
}
