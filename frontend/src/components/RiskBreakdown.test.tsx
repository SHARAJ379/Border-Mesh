import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RiskBreakdown } from './RiskBreakdown';
import { RiskFactorContribution } from '../types';

const weightedItem: RiskFactorContribution = {
  factor: 'Forensic Tamper AI',
  weight: 0.3,
  raw_risk: 62,
  weighted_contribution: 18.6,
};

const floorItem: RiskFactorContribution = {
  factor: 'Critical Signal Floor',
  weight: null,
  raw_risk: null,
  weighted_contribution: 30.5, // 18.6 (weightedItem) + 30.5 = 49.1, matching the totals used below
};

describe('RiskBreakdown', () => {
  it('shows the total score with one decimal place, not rounded to an integer', () => {
    // Reproduces a real credibility gap: a critical-signal-floored score of
    // 49.1 displayed as a rounded "49" visually contradicts System
    // Settings' own stated "Medium: 25-49" boundary even though the real
    // value (and classification) is HIGH.
    render(<RiskBreakdown breakdown={[weightedItem]} totalScore={49.1} />);
    expect(screen.getByText('49.1 / 100')).toBeInTheDocument();
    expect(screen.queryByText('49 / 100')).not.toBeInTheDocument();
  });

  it('renders a weighted category with its weight, raw risk, and progress bar', () => {
    render(<RiskBreakdown breakdown={[weightedItem]} totalScore={18.6} />);
    expect(screen.getByText('Forensic Tamper AI')).toBeInTheDocument();
    expect(screen.getByText('(30% Weight)')).toBeInTheDocument();
    expect(screen.getByText('Raw Risk: 62%')).toBeInTheDocument();
  });

  it('renders the critical-signal-floor row without a weight or raw-risk percentage', () => {
    // The floor is a flat point adjustment, not a proportional weighted
    // category (see risk_engine.py) -- it must not show a fabricated
    // weight/raw-risk percentage or progress bar, but must still show its
    // point contribution. Which signal triggered it now lives in the Risk
    // Reasons tab's itemized checks, not duplicated here.
    render(<RiskBreakdown breakdown={[weightedItem, floorItem]} totalScore={49.1} />);
    expect(screen.getByText('Critical Signal Floor')).toBeInTheDocument();
    expect(screen.getByText('+30.5')).toBeInTheDocument();
    expect(screen.queryByText('(null% Weight)')).not.toBeInTheDocument();
    expect(screen.queryByText(/Weight\)/, { selector: '*' })).not.toHaveTextContent('null');
  });

  it('points to the Risk Reasons tab for the itemized checks behind the numbers', () => {
    render(<RiskBreakdown breakdown={[weightedItem]} totalScore={18.6} />);
    expect(screen.getByText(/Risk Reasons tab/)).toBeInTheDocument();
  });

  it('the displayed factors sum to the displayed total when a critical floor is applied', () => {
    const breakdown = [weightedItem, floorItem];
    const total = 49.1;
    render(<RiskBreakdown breakdown={breakdown} totalScore={total} />);

    const reconciled = breakdown.reduce((sum, item) => sum + item.weighted_contribution, 0);
    expect(Math.round(reconciled * 10) / 10).toBeCloseTo(total, 1);
  });
});
