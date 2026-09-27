import { Suspense, lazy, useEffect, useState } from 'react';
import { isLowEndDevice, prefersReducedMotion } from '../lib/deviceCapability';

// ThreeUI (@designcodeio/threeui) ships its own internally-pinned Three.js
// copy per component family -- deliberately scoped to just this one hero
// spot (lazy-loaded, not in the initial bundle) rather than used app-wide,
// so it doesn't compound with the existing hand-built mesh-network
// background's own separate Three.js/R3F stack (see ../SceneBackground).
//
// The library's own stylesheet is loaded here too, not at the app entry --
// it's ~70KB covering every ThreeUI community component, not just this
// one, so it must ride along with this same lazy chunk rather than sit in
// every page's critical-path CSS for the sake of one hero banner.
const DotMatrixBackground = lazy(async () => {
  await import('@designcodeio/threeui/style.css');
  const mod = await import('@designcodeio/threeui/components/DotMatrixBackground');
  return { default: mod.DotMatrixBackground };
});

/**
 * Interactive WebGL background for the Dashboard's hero banner only --
 * a pulsing dot-grid (ThreeUI's "Core Uplink" shader) that reacts to
 * cursor position, read here as a scanning/surveillance motif fitting a
 * border-screening tool. Hue-rotated from its shipped cyan (~189deg) to
 * this app's brass accent (~43deg) -- the same "sanctioned gradient"
 * color the sidebar's own brand mark uses -- via CSS hue-rotate, the only
 * color customization the component's shader actually exposes.
 */
export function DashboardHeroBackground() {
  const [reduced] = useState(() => isLowEndDevice() || prefersReducedMotion());
  // The app-wide ambient mesh (SceneBackground) also mounts a WebGL
  // context+shader compile at roughly the same moment the Dashboard first
  // renders -- two concurrent WebGL context creations measurably stalled
  // the main thread for 700ms+ stretches at mount (profiled directly, not
  // assumed). Deferring this second context past the first paint/idle
  // window keeps them from contending for the same GPU/driver resources
  // at once; the static gradient shows briefly in the meantime instead of
  // nothing.
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (reduced) return;
    const win = window as Window & { requestIdleCallback?: (cb: () => void) => number };
    if (win.requestIdleCallback) {
      const id = win.requestIdleCallback(() => setReady(true));
      return () => (window as any).cancelIdleCallback?.(id);
    }
    const id = window.setTimeout(() => setReady(true), 400);
    return () => window.clearTimeout(id);
  }, [reduced]);

  if (reduced || !ready) {
    return (
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 70% 100% at 30% 0%, rgba(211,174,94,0.14), transparent 65%)',
        }}
      />
    );
  }

  return (
    <div aria-hidden className="absolute inset-0">
      <Suspense fallback={null}>
        <DotMatrixBackground
          hue={-146}
          gridScale={46}
          pulseSpeed={0.45}
          radius={0.16}
          mouseAmount={0.15}
          opacity={0.55}
        />
      </Suspense>
    </div>
  );
}
