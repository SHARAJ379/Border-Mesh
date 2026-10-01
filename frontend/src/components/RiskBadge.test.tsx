import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { RiskBadge } from './RiskBadge';

describe('RiskBadge', () => {
  it('maps NO_FACE_DETECTED to the HIGH-severity badge class', () => {
    // face_service.py's own FACE_DOCUMENT_PORTRAIT_DETECTION /
    // FACE_LIVE_CAPTURE_DETECTION checks are HIGH severity server-side --
    // this used to fall through to the neutral/gray default, reading as
    // LESS concerning than a plain below-threshold REVIEW_REQUIRED match.
    const { container } = render(<RiskBadge status="NO_FACE_DETECTED" />);
    const badge = container.querySelector('.badge-signal');
    expect(badge?.className).toContain('badge-high');
    expect(badge?.textContent).toBe('NO FACE DETECTED');
  });

  it('maps MULTIPLE_FACES to the MEDIUM-severity badge class', () => {
    // MEDIUM severity server-side (face_service.py) -- one tier below
    // NO_FACE_DETECTED's HIGH, same reasoning.
    const { container } = render(<RiskBadge status="MULTIPLE_FACES" />);
    const badge = container.querySelector('.badge-signal');
    expect(badge?.className).toContain('badge-medium');
  });

  it('still maps REVIEW_REQUIRED to the HIGH-severity badge class', () => {
    const { container } = render(<RiskBadge status="REVIEW_REQUIRED" />);
    const badge = container.querySelector('.badge-signal');
    expect(badge?.className).toContain('badge-high');
  });

  it('still maps MATCH to the LOW-severity badge class', () => {
    const { container } = render(<RiskBadge status="MATCH" />);
    const badge = container.querySelector('.badge-signal');
    expect(badge?.className).toContain('badge-low');
  });

  it('falls back to neutral for a genuinely unrecognized status rather than throwing', () => {
    const { container } = render(<RiskBadge status="SOMETHING_NEW" />);
    const badge = container.querySelector('.badge-signal');
    expect(badge?.className).toContain('badge-neutral');
  });
});
