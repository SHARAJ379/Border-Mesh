import { useRef, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useSyncExternalStore } from 'react';
import { scrollProgressStore } from '../lib/scrollProgress';

// Accent cyan (primary) and signal green (secondary, used sparingly) --
// matches --color-accent / --color-signal-low in index.css so the 3D layer
// reads as part of the blockchain/cybersecurity system, not a bolted-on
// effect. Recolored from the warm-paper system's brass/teal.
const ACCENT = new THREE.Color('#38BDF8');
const SIGNAL = new THREE.Color('#4ADE80');

interface MeshNetworkProps {
  nodeCount: number;
}

/**
 * A sparse point cloud with nearest-neighbour connecting lines -- reads as
 * a security/verification "mesh network" rather than a decorative
 * starfield. Nodes drift slowly; scroll position (from Lenis, via the
 * shared store) adds a gentle parallax rotation so the background feels
 * connected to the content instead of static wallpaper.
 */
export function MeshNetwork({ nodeCount }: MeshNetworkProps) {
  const groupRef = useRef<THREE.Group>(null);
  const { progress, velocity } = useSyncExternalStore(
    scrollProgressStore.subscribe,
    scrollProgressStore.getSnapshot
  );

  // Lazy initializer, not useMemo -- the point cloud must be generated
  // exactly once (Math.random per node), and useMemo's cache isn't
  // guaranteed to survive forever under future concurrent-rendering
  // semantics, while useState's initializer is. nodeCount is a fixed prop
  // (SceneBackground always passes 90), so this never needs to regenerate.
  const [{ positions, colors, linePositions }] = useState(() => {
    const positions = new Float32Array(nodeCount * 3);
    const colors = new Float32Array(nodeCount * 3);
    const points: THREE.Vector3[] = [];

    for (let i = 0; i < nodeCount; i++) {
      const p = new THREE.Vector3(
        (Math.random() - 0.5) * 16,
        (Math.random() - 0.5) * 10,
        (Math.random() - 0.5) * 8 - 2
      );
      points.push(p);
      positions.set([p.x, p.y, p.z], i * 3);

      const color = Math.random() > 0.75 ? SIGNAL : ACCENT;
      colors.set([color.r, color.g, color.b], i * 3);
    }

    // Connect each node to its nearest few neighbours only -- keeps the
    // line count bounded (O(n)) instead of O(n^2) for the full graph.
    const maxDistance = 3.2;
    const maxNeighbours = 3;
    const linePoints: number[] = [];
    for (let i = 0; i < points.length; i++) {
      const distances = points
        .map((p, j) => ({ j, d: i === j ? Infinity : points[i].distanceTo(p) }))
        .sort((a, b) => a.d - b.d)
        .slice(0, maxNeighbours);

      for (const { j, d } of distances) {
        if (d < maxDistance) {
          linePoints.push(points[i].x, points[i].y, points[i].z, points[j].x, points[j].y, points[j].z);
        }
      }
    }

    return {
      positions,
      colors,
      linePositions: new Float32Array(linePoints),
    };
  });

  useFrame((_, delta) => {
    if (!groupRef.current) return;
    groupRef.current.rotation.y += delta * 0.02;
    groupRef.current.rotation.x = progress * 0.25;
    // Scroll velocity gives a brief extra tilt that eases back out --
    // the "reacts to scroll" requirement without anything jarring.
    groupRef.current.rotation.z += (velocity * 0.002 - groupRef.current.rotation.z) * 0.05;
  });

  return (
    <group ref={groupRef}>
      <points>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
          <bufferAttribute attach="attributes-color" args={[colors, 3]} />
        </bufferGeometry>
        <pointsMaterial size={0.05} vertexColors transparent opacity={0.85} sizeAttenuation />
      </points>
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[linePositions, 3]} />
        </bufferGeometry>
        <lineBasicMaterial color="#38BDF8" transparent opacity={0.18} />
      </lineSegments>
    </group>
  );
}
