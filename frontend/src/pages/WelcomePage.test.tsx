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
    expect(screen.getByText(/39\.5%/)).toBeInTheDocument();
    const termsLinks = screen.getAllByRole('link', { name: /Terms/ });
    expect(termsLinks.some((a) => a.getAttribute('href') === '/terms')).toBe(true);
  });

  it('links to the Privacy Policy in the footer', () => {
    render(<WelcomePage />);
    const privacyLinks = screen.getAllByRole('link', { name: /Privacy Policy/ });
    expect(privacyLinks.some((a) => a.getAttribute('href') === '/privacy')).toBe(true);
  });

  it('states plainly this is a decision-support demo, not a live operational system', () => {
    render(<WelcomePage />);
    expect(screen.getByText(/not a live operational screening system/)).toBeInTheDocument();
  });
});
