import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WelcomePage } from './WelcomePage';

describe('WelcomePage', () => {
  it('renders the SIH26188 / Ministry of Home Affairs framing, not generic marketing copy', () => {
    render(<WelcomePage />);
    expect(screen.getAllByText(/SIH26188/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Ministry of Home Affairs/).length).toBeGreaterThan(0);
  });

  it('links into the real dashboard rather than a fake signup flow', () => {
    render(<WelcomePage />);
    const dashboardLinks = screen.getAllByRole('link', { name: /Open.*Dashboard/i });
    expect(dashboardLinks.some((a) => a.getAttribute('href') === '/')).toBe(true);
  });

  it('discloses known limitations up front instead of only claiming accuracy', () => {
    render(<WelcomePage />);
    expect(screen.getAllByText(/39\.5%/).length).toBeGreaterThan(0);
    // The Terms link lives inside a ScrollReveal section -- GSAP's autoAlpha
    // leaves it at visibility:hidden under jsdom's no-op ScrollTrigger,
    // which excludes it from getByRole('link')'s accessible-name query even
    // though it's really there. getByText ignores CSS visibility (see the
    // same pattern in RiskReasons.test.tsx), so find the text node and walk
    // up to its anchor instead.
    const termsLinks = screen.getAllByText(/Terms/).map((el) => el.closest('a')).filter(Boolean) as HTMLAnchorElement[];
    expect(termsLinks.some((a) => a.getAttribute('href') === '/terms')).toBe(true);
  });

  it('links to the Privacy Policy in the footer', () => {
    render(<WelcomePage />);
    // See the note above -- this link is inside the same ScrollReveal-hidden
    // Close section, so query by text rather than accessible role.
    const privacyLinks = screen.getAllByText(/Privacy Policy/).map((el) => el.closest('a')).filter(Boolean) as HTMLAnchorElement[];
    expect(privacyLinks.some((a) => a.getAttribute('href') === '/privacy')).toBe(true);
  });

  it('states plainly this is a decision-support demo, not a live operational system', () => {
    render(<WelcomePage />);
    expect(screen.getByText(/Not for use in live operational screening/)).toBeInTheDocument();
  });
});
