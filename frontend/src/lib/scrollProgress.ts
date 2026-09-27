// Tiny external store so the persistent 3D background can react to scroll
// position without the scroller (Lenis, inside App's <main>) re-rendering
// the whole tree on every frame. Consumed via useSyncExternalStore.
let snapshot = { progress: 0, velocity: 0 };
const listeners = new Set<() => void>();

export const scrollProgressStore = {
  set(nextProgress: number, nextVelocity: number) {
    snapshot = { progress: nextProgress, velocity: nextVelocity };
    listeners.forEach((listener) => listener());
  },
  getSnapshot(): { progress: number; velocity: number } {
    return snapshot;
  },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};
