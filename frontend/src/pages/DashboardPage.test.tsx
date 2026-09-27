import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DashboardPage } from './DashboardPage';
import { api } from '../services/api';

vi.mock('../services/api', () => ({
  api: {
    getDashboardStats: vi.fn(),
  },
}));

const noop = () => {};

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.mocked(api.getDashboardStats).mockReset();
  });

  it('shows a retryable error state instead of an eternal spinner when the initial stats fetch fails', async () => {
    vi.mocked(api.getDashboardStats).mockRejectedValue(new Error('Failed to fetch dashboard statistics'));

    render(
      <DashboardPage onSelectCase={noop} onNavigateNewScreening={noop} onNavigateQueue={noop} />
    );

    // The failure must surface as a real error message, not stay on the
    // loading spinner forever -- reproduces the bug where `loading ||
    // !stats` kept the spinner up even after loading flipped back to
    // false, because a failed fetch never sets `stats`.
    await waitFor(() => {
      expect(screen.getByText(/failed to fetch dashboard statistics/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/loading operations stream/i)).not.toBeInTheDocument();

    // A retry control must be offered, not a dead end.
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('retry button re-fetches and renders the dashboard on success', async () => {
    vi.mocked(api.getDashboardStats)
      .mockRejectedValueOnce(new Error('network error'))
      .mockResolvedValueOnce({
        documents_screened: 42,
        high_risk_cases: 1,
        critical_cases: 0,
        cases_requiring_review: 2,
        cleared_cases: 39,
        avg_processing_time_ms: 1200,
        risk_distribution: { LOW: 40, MEDIUM: 1, HIGH: 1, CRITICAL: 0 },
        latency_breakdown: [],
        document_types: {},
        top_risk_reasons: [],
        recent_cases: [],
      });

    render(
      <DashboardPage onSelectCase={noop} onNavigateNewScreening={noop} onNavigateQueue={noop} />
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole('button', { name: /retry/i }));

    await waitFor(() => {
      // The KPI strip's own container -- a plain hairline-bounded div, not
      // a "card" -- scoped so this doesn't rely on any risk distribution
      // row that might also show a raw count.
      const screenedLabel = screen.getByText('Screened');
      const kpiCell = screenedLabel.parentElement as HTMLElement;
      expect(within(kpiCell).getByText('42')).toBeInTheDocument();
    });
    expect(screen.queryByText(/network error/i)).not.toBeInTheDocument();
    expect(api.getDashboardStats).toHaveBeenCalledTimes(2);
  });

  it('shows the loading spinner while the initial fetch is in flight', async () => {
    let resolveFetch: (value: any) => void = () => {};
    vi.mocked(api.getDashboardStats).mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      })
    );

    render(
      <DashboardPage onSelectCase={noop} onNavigateNewScreening={noop} onNavigateQueue={noop} />
    );

    expect(screen.getByText(/loading operations stream/i)).toBeInTheDocument();

    resolveFetch({
      documents_screened: 1,
      high_risk_cases: 0,
      critical_cases: 0,
      cases_requiring_review: 0,
      cleared_cases: 1,
      avg_processing_time_ms: 100,
      risk_distribution: { LOW: 1, MEDIUM: 0, HIGH: 0, CRITICAL: 0 },
      latency_breakdown: [],
      document_types: {},
      top_risk_reasons: [],
      recent_cases: [],
    });

    await waitFor(() => {
      expect(screen.queryByText(/loading operations stream/i)).not.toBeInTheDocument();
    });
  });
});
