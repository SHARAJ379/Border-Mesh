import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Magnifier } from './Magnifier';
import * as deviceCapability from '../lib/deviceCapability';

const STUB_RECT: DOMRect = {
  x: 100, y: 50, left: 100, top: 50,
  width: 400, height: 300, right: 500, bottom: 350,
  toJSON: () => ({}),
};

beforeEach(() => {
  vi.spyOn(HTMLImageElement.prototype, 'getBoundingClientRect').mockReturnValue(STUB_RECT);
  // Default: natural image ratio (4:3) matches the stub rect's ratio
  // (400x300 = 4:3), so object-contain renders edge-to-edge with no
  // letterbox gutter -- existing pixel-math tests below assume this.
  vi.spyOn(HTMLImageElement.prototype, 'naturalWidth', 'get').mockReturnValue(800);
  vi.spyOn(HTMLImageElement.prototype, 'naturalHeight', 'get').mockReturnValue(600);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('Magnifier', () => {
  it('always renders the underlying image regardless of device capability', () => {
    render(<Magnifier src="/doc.jpg" alt="Document" />);
    expect(screen.getByAltText('Document')).toBeInTheDocument();
  });

  it('shows the lens on pointer move over the image, and hides it on pointer leave', () => {
    render(<Magnifier src="/doc.jpg" alt="Document" />);
    const img = screen.getByAltText('Document');

    expect(screen.queryByTestId('magnifier-lens')).not.toBeInTheDocument();

    fireEvent.pointerMove(img, { clientX: 300, clientY: 200 });
    expect(screen.getByTestId('magnifier-lens')).toBeInTheDocument();

    fireEvent.pointerLeave(img);
    expect(screen.queryByTestId('magnifier-lens')).not.toBeInTheDocument();
  });

  it('positions the lens centered on the pointer, in fixed/viewport coordinates', () => {
    render(<Magnifier src="/doc.jpg" alt="Document" lensSize={160} />);
    const img = screen.getByAltText('Document');
    fireEvent.pointerMove(img, { clientX: 300, clientY: 200 });

    const lens = screen.getByTestId('magnifier-lens') as HTMLElement;
    expect(lens.style.left).toBe(`${300 - 80}px`);
    expect(lens.style.top).toBe(`${200 - 80}px`);
    // `fixed` is a Tailwind class (position: fixed lives in the stylesheet,
    // not inline style) -- and it must be portaled to <body>, not nested
    // under any transformed ScrollReveal ancestor, or `fixed` wouldn't mean
    // viewport-fixed at all (see the component's own top-of-file comment).
    expect(lens.className).toContain('fixed');
    expect(lens.parentElement).toBe(document.body);
  });

  it('computes background-position from where the pointer sits within the image, scaled by zoom', () => {
    // Pointer at (300, 200) over a rect starting at (100, 50) -> 200,150
    // relative to the image. zoom=2, lensSize=160:
    // bgX = -(200*2 - 80) = -320; bgY = -(150*2 - 80) = -220.
    render(<Magnifier src="/doc.jpg" alt="Document" zoom={2} lensSize={160} />);
    const img = screen.getByAltText('Document');
    fireEvent.pointerMove(img, { clientX: 300, clientY: 200 });

    const lens = screen.getByTestId('magnifier-lens') as HTMLElement;
    expect(lens.style.backgroundPosition).toBe('-320px -220px');
    expect(lens.style.backgroundSize).toBe('800px 600px'); // rect 400x300 * zoom 2
  });

  it('clamps background-position at the image edges instead of showing an out-of-bounds offset', () => {
    render(<Magnifier src="/doc.jpg" alt="Document" zoom={2} lensSize={160} />);
    const img = screen.getByAltText('Document');
    // Far outside the rect (rect is x:100-500, y:50-350) -- must clamp to
    // the rect's own edge, not extrapolate negative/overflowing values.
    fireEvent.pointerMove(img, { clientX: 5000, clientY: 5000 });

    const lens = screen.getByTestId('magnifier-lens') as HTMLElement;
    // relX clamps to rect.width (400), relY to rect.height (300):
    // bgX = -(400*2 - 80) = -720; bgY = -(300*2 - 80) = -520.
    expect(lens.style.backgroundPosition).toBe('-720px -520px');
  });

  it('accounts for object-contain letterboxing when the image ratio does not match the box ratio', () => {
    // Rect is 400x300 (4:3, box ratio 1.333) but the natural image is
    // 200x300 (2:3, ratio 0.667) -- narrower than the box, so
    // object-contain fits it to the box's full height and letterboxes
    // 100px of empty gutter on each side: content spans x=[200,400) of
    // the box's own 400-wide rect (offsetX=100, contentWidth=200),
    // full height (offsetY=0, contentHeight=300).
    vi.spyOn(HTMLImageElement.prototype, 'naturalWidth', 'get').mockReturnValue(200);
    vi.spyOn(HTMLImageElement.prototype, 'naturalHeight', 'get').mockReturnValue(300);
    render(<Magnifier src="/doc.jpg" alt="Document" zoom={2} lensSize={160} />);
    const img = screen.getByAltText('Document');

    // Pointer at (300, 200) -> 200,150 relative to the rect's top-left
    // (100, 50). Subtracting the letterbox offset (100, 0):
    // relX = 200 - 100 = 100 (within [0, 200]); relY = 150 (within [0, 300]).
    // bgX = -(100*2 - 80) = -120; bgY = -(150*2 - 80) = -220.
    // bgWidth = contentWidth(200)*2 = 400; bgHeight = contentHeight(300)*2 = 600.
    fireEvent.pointerMove(img, { clientX: 300, clientY: 200 });
    let lens = screen.getByTestId('magnifier-lens') as HTMLElement;
    expect(lens.style.backgroundPosition).toBe('-120px -220px');
    expect(lens.style.backgroundSize).toBe('400px 600px');

    // Pointer inside the left letterbox gutter (box x=100..200, content
    // starts at x=200) must clamp to the content's own left edge, not
    // treat the gutter as if it were image content.
    fireEvent.pointerMove(img, { clientX: 150, clientY: 200 });
    lens = screen.getByTestId('magnifier-lens') as HTMLElement;
    expect(lens.style.backgroundPosition).toBe('80px -220px'); // relX clamped to 0 -> bgX = -(0*2-80) = 80
  });

  it('never shows the lens under prefers-reduced-motion, even on pointer move', () => {
    vi.spyOn(deviceCapability, 'prefersReducedMotion').mockReturnValue(true);
    render(<Magnifier src="/doc.jpg" alt="Document" />);
    const img = screen.getByAltText('Document');
    fireEvent.pointerMove(img, { clientX: 300, clientY: 200 });
    expect(screen.queryByTestId('magnifier-lens')).not.toBeInTheDocument();
  });

  it('never shows the lens on a coarse (touch) pointer, even on pointer move', () => {
    vi.spyOn(deviceCapability, 'isCoarsePointer').mockReturnValue(true);
    render(<Magnifier src="/doc.jpg" alt="Document" />);
    const img = screen.getByAltText('Document');
    fireEvent.pointerMove(img, { clientX: 300, clientY: 200 });
    expect(screen.queryByTestId('magnifier-lens')).not.toBeInTheDocument();
  });

  it('is decorative to assistive tech -- the lens carries no information beyond the underlying image', () => {
    render(<Magnifier src="/doc.jpg" alt="Document" />);
    const img = screen.getByAltText('Document');
    fireEvent.pointerMove(img, { clientX: 300, clientY: 200 });
    expect(screen.getByTestId('magnifier-lens')).toHaveAttribute('aria-hidden', 'true');
  });
});
