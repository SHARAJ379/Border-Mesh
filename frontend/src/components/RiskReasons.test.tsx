import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RiskReasons } from './RiskReasons';
import { RiskCheck } from '../types';

const passCheck: RiskCheck = {
  id: 'MRZ_DOCUMENT_NUMBER_CHECKSUM',
  category: 'MRZ',
  factor: 'MRZ_VALIDATION',
  label: 'Document Number Checksum',
  status: 'PASS',
  confidence: 0.99,
  explanation: 'Matches calculated check digit.',
  evidence: { measured_value: '7', threshold_value: '7', unit: 'check_digit' },
  score_impact: 0,
};

const failCheck: RiskCheck = {
  id: 'FACE_BIOMETRIC_MATCH',
  category: 'FACE',
  factor: 'FACE',
  label: 'Biometric Face Mismatch',
  status: 'FAIL',
  severity: 'HIGH',
  confidence: 0.65,
  explanation: 'Similarity below threshold.',
  evidence: { measured_value: 0.34, threshold_value: 0.72, unit: 'cosine_similarity' },
  score_impact: 25.0,
};

const matchCheck: RiskCheck = {
  id: 'WATCHLIST_SCREENING',
  category: 'WATCHLIST',
  factor: 'WATCHLIST',
  label: 'Demo Watchlist Hit: Inquiry Flag',
  status: 'FAIL',
  severity: 'CRITICAL',
  confidence: 0.99,
  explanation: '[SIMULATED DATA] Identity matched.',
  evidence: {
    match: [{ method: 'SOUNDEX', query_token: 'MARKOOS', matched_token: 'MARCUS', edit_distance: null }],
  },
  score_impact: 25.0,
};

describe('RiskReasons', () => {
  it('shows an empty state when there are no checks at all', () => {
    render(<RiskReasons checks={[]} />);
    expect(screen.getByText(/No risk checks recorded/)).toBeInTheDocument();
  });

  it('a document that fails zero checks states that plainly, not silence', () => {
    render(<RiskReasons checks={[passCheck]} />);
    expect(screen.getByText(/All 1 checks passed/)).toBeInTheDocument();
    expect(screen.getByText('Document Number Checksum')).toBeInTheDocument();
  });

  it('a document that fails every check states the flagged count', () => {
    render(<RiskReasons checks={[failCheck, matchCheck]} />);
    expect(screen.getByText('2 of 2 checks flagged.')).toBeInTheDocument();
  });

  it('renders measured-vs-threshold evidence for a numeric check', () => {
    render(<RiskReasons checks={[failCheck]} />);
    expect(screen.getByText(/0\.34/)).toBeInTheDocument();
    expect(screen.getByText(/0\.72/)).toBeInTheDocument();
  });

  it('renders match evidence (method/tokens) for a fuzzy watchlist match instead of a bare pass/fail', () => {
    render(<RiskReasons checks={[matchCheck]} />);
    expect(screen.getByText(/MARCUS/)).toBeInTheDocument();
    expect(screen.getByText(/MARKOOS/)).toBeInTheDocument();
    expect(screen.getByText(/SOUNDEX/)).toBeInTheDocument();
  });

  it('groups checks by factor and shows a per-group flagged count', () => {
    render(<RiskReasons checks={[passCheck, failCheck]} />);
    expect(screen.getByText(/MRZ & Document Validation/)).toBeInTheDocument();
    expect(screen.getByText(/Biometric Face Verification/)).toBeInTheDocument();
    expect(screen.getByText(/all clean/)).toBeInTheDocument();
    expect(screen.getByText(/1 flagged/)).toBeInTheDocument();
  });

  it('two checks tied at the same CRITICAL severity are both retained, not collapsed to one', () => {
    const tiedA: RiskCheck = { ...failCheck, id: 'A', factor: 'FACE', label: 'Alpha Critical', severity: 'CRITICAL' };
    const tiedB: RiskCheck = { ...failCheck, id: 'B', factor: 'FACE', label: 'Beta Critical', severity: 'CRITICAL' };
    render(<RiskReasons checks={[tiedA, tiedB]} />);
    expect(screen.getByText('Alpha Critical')).toBeInTheDocument();
    expect(screen.getByText('Beta Critical')).toBeInTheDocument();
  });

  it('filters by status', async () => {
    // ScrollReveal (GSAP autoAlpha, never triggered under jsdom's no-op
    // ScrollTrigger) leaves the panel at visibility:hidden, which makes
    // dom-accessibility-api compute an empty accessible name for every
    // descendant -- getByRole(name:) can't find it even with hidden:true.
    // getByText ignores CSS visibility, so query by text and click that
    // node directly instead.
    const user = userEvent.setup();
    render(<RiskReasons checks={[passCheck, failCheck]} />);
    await user.click(screen.getByText('FAIL'));
    expect(screen.getByText('Biometric Face Mismatch')).toBeInTheDocument();
    expect(screen.queryByText('Document Number Checksum')).not.toBeInTheDocument();
  });

  it('compact mode renders without the panel chrome or filter controls', () => {
    render(<RiskReasons checks={[failCheck]} compact />);
    expect(screen.getByText('Biometric Face Mismatch')).toBeInTheDocument();
    expect(screen.queryByText('FAIL')).not.toBeInTheDocument();
  });
});
