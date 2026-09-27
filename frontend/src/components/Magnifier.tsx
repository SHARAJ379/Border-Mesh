import React, { useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { prefersReducedMotion, isCoarsePointer } from '../lib/deviceCapability';

interface MagnifierProps extends Omit<React.ImgHTMLAttributes<HTMLImageElement>, 'onPointerMove' | 'onPointerLeave'> {
  src: string;
  alt: string;
  /** How much larger the lens renders the content under the cursor. */
  zoom?: number;
  /** Lens diameter in CSS pixels. */
  lensSize?: number;
}

interface LensState {
  x: number;
  y: number;
  bgX: number;
  bgY: number;
  bgWidth: number;
  bgHeight: number;
}

/**
 * A drag-free, hover-follow magnifying glass over a single image -- the
 * forensic-inspection pattern adapted from the sketchbook loupe (see
 * https://github.com/MengTo/sketchbook), simplified for a single flat
 * image instead of a whole layered scene:
 *
 * - "Duplicated, scaled content": rather than cloning a DOM subtree (that
 *   project's book is a multi-layer scene a flat copy couldn't capture),
 *   the lens re-renders the SAME image as a `background-image` at a
 *   larger `background-size` -- a real second rendering of the bitmap at
 *   zoom scale, not a CSS transform of the original <img>.
 * - "Clipped with mask-image": a radial-gradient mask gives the lens a
 *   soft circular edge instead of a hard clip.
 * - "No inherited tilt/parallax transform": the lens is portaled to
 *   document.body and position:fixed. This app's ScrollReveal sets a real
 *   `transform` on each panel's wrapper via GSAP (even at rest, not just
 *   mid-animation), and a `position:fixed` descendant of a transformed
 *   ancestor is positioned relative to THAT ancestor, not the viewport --
 *   portaling out to body is what actually guarantees viewport-fixed
 *   behavior, the same reason the original portals its zoomed copy
 *   outside the book's own parallax transform.
 * - The lens position/content is recomputed from a live
 *   getBoundingClientRect() on every pointer move rather than cached, so
 *   it's correct regardless of any ancestor animation in progress -- not
 *   just "usually fine because nothing moves after mount."
 *
 * Disabled entirely under prefers-reduced-motion or a coarse (touch)
 * pointer, checked once at mount via the same shared device-capability
 * module every other motion-gated component in this app already uses
 * (see deviceCapability.ts) -- there's no cursor to hover with on touch,
 * and no second reduced-motion check reinvented here.
 */
export const Magnifier: React.FC<MagnifierProps> = ({
  src,
  alt,
  zoom = 2.5,
  lensSize = 160,
  className,
  ...imgProps
}) => {
  const imgRef = useRef<HTMLImageElement>(null);
  const [lens, setLens] = useState<LensState | null>(null);
  const [enabled] = useState(() => !prefersReducedMotion() && !isCoarsePointer());

  const handleMove = (e: React.PointerEvent<HTMLImageElement>) => {
    const img = imgRef.current;
    const rect = img?.getBoundingClientRect();
    if (!img || !rect || !img.naturalWidth || !img.naturalHeight) return;

    // The <img> element's own box (rect) is NOT the same as the rendered
    // image content whenever `object-fit: contain` letterboxes it -- a
    // document's natural aspect ratio rarely matches a CSS-forced box
    // ratio (e.g. this app's aspect-[3/4]/aspect-[4/5] panels), so the
    // box has blank gutters the pointer math must not treat as image
    // content. Derive the actual rendered content rect from
    // naturalWidth/naturalHeight, the same way the browser's own
    // object-fit: contain layout does.
    const boxRatio = rect.width / rect.height;
    const imgRatio = img.naturalWidth / img.naturalHeight;

    let contentWidth = rect.width;
    let contentHeight = rect.height;
    let offsetX = 0;
    let offsetY = 0;

    if (imgRatio > boxRatio) {
      // Image is relatively wider than the box -- letterboxed top/bottom.
      contentHeight = rect.width / imgRatio;
      offsetY = (rect.height - contentHeight) / 2;
    } else if (imgRatio < boxRatio) {
      // Image is relatively taller than the box -- letterboxed left/right.
      contentWidth = rect.height * imgRatio;
      offsetX = (rect.width - contentWidth) / 2;
    }

    const relX = Math.min(Math.max(e.clientX - rect.left - offsetX, 0), contentWidth);
    const relY = Math.min(Math.max(e.clientY - rect.top - offsetY, 0), contentHeight);
    setLens({
      x: e.clientX,
      y: e.clientY,
      bgX: -(relX * zoom - lensSize / 2),
      bgY: -(relY * zoom - lensSize / 2),
      bgWidth: contentWidth * zoom,
      bgHeight: contentHeight * zoom,
    });
  };

  return (
    <>
      <img
        ref={imgRef}
        src={src}
        alt={alt}
        className={className}
        onPointerMove={enabled ? handleMove : undefined}
        onPointerLeave={enabled ? () => setLens(null) : undefined}
        {...imgProps}
      />
      {enabled && lens && createPortal(
        <div
          aria-hidden="true"
          data-testid="magnifier-lens"
          className="pointer-events-none fixed z-[999] rounded-full border border-ink"
          style={{
            left: lens.x - lensSize / 2,
            top: lens.y - lensSize / 2,
            width: lensSize,
            height: lensSize,
            boxShadow: '4px 4px 0 0 var(--color-hairline)',
            backgroundColor: 'var(--color-paper-dim)',
            backgroundImage: `url(${src})`,
            backgroundRepeat: 'no-repeat',
            backgroundSize: `${lens.bgWidth}px ${lens.bgHeight}px`,
            backgroundPosition: `${lens.bgX}px ${lens.bgY}px`,
            maskImage: 'radial-gradient(circle closest-side, #000 92%, transparent 100%)',
            WebkitMaskImage: 'radial-gradient(circle closest-side, #000 92%, transparent 100%)',
          }}
        />,
        document.body
      )}
    </>
  );
};
