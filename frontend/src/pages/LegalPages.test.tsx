import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PrivacyPolicyPage } from './PrivacyPolicyPage';
import { TermsPage } from './TermsPage';

describe('PrivacyPolicyPage', () => {
  it('renders the title and Ministry of Home Affairs attribution', () => {
    render(<PrivacyPolicyPage />);
    expect(screen.getByRole('heading', { name: 'Privacy Policy' })).toBeInTheDocument();
    expect(screen.getAllByText(/Ministry of Home Affairs/).length).toBeGreaterThan(0);
  });

  it('discloses the real-input handling honestly, not the README\'s old "exclusively synthetic" claim', () => {
    render(<PrivacyPolicyPage />);
    expect(screen.getByText(/does not currently refuse or special-case real/)).toBeInTheDocument();
  });

  it('discloses the single static demo encryption key, not just "encrypted at rest"', () => {
    render(<PrivacyPolicyPage />);
    expect(screen.getByText(/single static demo key/)).toBeInTheDocument();
    expect(screen.getByText(/no HSM\/KMS involved/)).toBeInTheDocument();
  });

  it('states plainly that this is not a compliance certification', () => {
    render(<PrivacyPolicyPage />);
    expect(screen.getByText(/not a legal compliance opinion or certification/)).toBeInTheDocument();
  });

  it('links to both the Terms page and back to the app', () => {
    render(<PrivacyPolicyPage />);
    const termsLinks = screen.getAllByRole('link', { name: /Terms/ });
    expect(termsLinks.some((a) => a.getAttribute('href') === '/terms')).toBe(true);
    const backLinks = screen.getAllByRole('link', { name: /Back to app/ });
    expect(backLinks.length).toBeGreaterThan(0);
  });
});

describe('TermsPage', () => {
  it('renders the title', () => {
    render(<TermsPage />);
    expect(screen.getByRole('heading', { name: /Terms.*Conditions/ })).toBeInTheDocument();
  });

  it('discloses the real tamper-detection recall figure, not just the training-validation number', () => {
    render(<TermsPage />);
    expect(screen.getByText(/39\.5%/)).toBeInTheDocument();
    expect(screen.getByText(/60\.6%/)).toBeInTheDocument();
  });

  it('states plainly that this is not for live or operational use', () => {
    render(<TermsPage />);
    expect(screen.getByText(/must not be used for actual immigration/)).toBeInTheDocument();
  });

  it('discloses the watchlist is fictional', () => {
    render(<TermsPage />);
    expect(screen.getByText(/three fictional, simulated/)).toBeInTheDocument();
  });

  it('links to the Privacy Policy', () => {
    render(<TermsPage />);
    const privacyLinks = screen.getAllByRole('link', { name: /Privacy Policy/ });
    expect(privacyLinks.some((a) => a.getAttribute('href') === '/privacy')).toBe(true);
  });
});
