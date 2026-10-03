import { Suspense, useEffect, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { MeshNetwork } from './MeshNetwork';
import { isLowEndDevice, prefersReducedMotion } from '../lib/deviceCapability';

/**
 * One persistent WebGL layer for the whole app, mounted once in App.tsx
 * behind the sidebar/main content (fixed, z-0, pointer-events-none) --
 * not per-page canvases. Degrades to a static CSS gradient on low-end
 * devices or when the user has requested reduced motion, instead of
 * forcing the particle network everywhere.
 */
export function SceneBackground() {
  // Lazy initializer, not an effect -- this component only ever mounts
  // client-side (it's behind React.lazy in App.tsx), so reading
  // window/navigator once up front is safe and avoids an extra
  // render+effect pass just to set a value that never changes after mount.
  const [reduced] = useState(() => isLowEndDevice() || prefersReducedMotion());
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const onVisibility = () => setVisible(document.visibilityState === 'visible');
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, []);

  if (reduced) {
    return (
      <div
        aria-hidden
        className="fixed inset-0 z-0 pointer-events-none"
        style={{
          background:
            'radial-gradient(ellipse 80% 60% at 20% 0%, rgba(56,189,248,0.10), transparent 60%),' +
            'radial-gradient(ellipse 70% 50% at 100% 100%, rgba(74,222,128,0.07), transparent 60%)',
        }}
      />
    );
  }

  return (
    <div aria-hidden className="fixed inset-0 z-0 pointer-events-none">
      <Canvas
        dpr={[1, 1.5]}
        gl={{ antialias: false, alpha: true, powerPreference: 'low-power' }}
        camera={{ position: [0, 0, 6], fov: 45 }}
        frameloop={visible ? 'always' : 'never'}
      >
        <Suspense fallback={null}>
          <MeshNetwork nodeCount={90} />
        </Suspense>
      </Canvas>
    </div>
  );
}
