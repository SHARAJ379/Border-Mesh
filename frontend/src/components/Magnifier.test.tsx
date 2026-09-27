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
