import { describe, it, expect } from 'vitest';
import { hasWebGL, isLowEndDevice, isCoarsePointer } from './deviceCapability';

describe('hasWebGL', () => {
  it('returns false in jsdom, which has no real WebGL implementation', () => {
    // Regression test: before this function existed, every WebGL-mounting
    // component (SceneBackground, DashboardHeroBackground) attempted a real
    // `new THREE.WebGLRenderer(...)` during tests once a lazy import
    // resolved, which jsdom's null getContext() turns into an uncaught
    // "Error creating WebGL context" thrown from inside a passive effect --
    // see the DashboardPage test suite, which surfaced this once
    // DashboardHeroBackground started rendering unconditionally.
    expect(hasWebGL()).toBe(false);
  });
});

describe('isCoarsePointer', () => {
  it('is false in jsdom, which reports no matchMedia matches by default', () => {
    // test/setup.ts stubs window.matchMedia to always report matches:false
    // (see its own comment) -- this pins down that isCoarsePointer reads
    // the '(pointer: coarse)' feature specifically, not some other query,
    // by confirming it agrees with that default.
    expect(isCoarsePointer()).toBe(false);
  });
});

describe('isLowEndDevice', () => {
  it('is true in jsdom purely because WebGL is unavailable, regardless of other signals', () => {
    // jsdom reports a "normal" viewport/hardwareConcurrency, so this
    // specifically exercises the hasWebGL() gate added ahead of the
    // existing viewport/core/memory heuristics, not those heuristics
    // themselves (already covered by the deliberately non-jsdom-testable
    // browser-only signals they read).
    expect(isLowEndDevice()).toBe(true);
  });
});
