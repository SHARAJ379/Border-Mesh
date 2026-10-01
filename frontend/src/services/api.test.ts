import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api } from './api';
import { setSession, clearSession, getToken, getOfficer } from '../lib/auth';

describe('per-officer session auth', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('login() stores the returned token and officer on success', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: 'a-real-looking-jwt',
          token_type: 'bearer',
          officer: { badge_id: 'OFFICER-DEMO-01', full_name: 'Demo Officer' }
        }),
        { status: 200 }
      )
    );

    const { officer } = await api.login('OFFICER-DEMO-01', 'correct-password');

    expect(officer.badge_id).toBe('OFFICER-DEMO-01');
    expect(getToken()).toBe('a-real-looking-jwt');
    expect(getOfficer()?.full_name).toBe('Demo Officer');
  });

  it('login() throws and stores nothing on a 401', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Invalid badge ID or password.' }), { status: 401 })
    );

    await expect(api.login('OFFICER-DEMO-01', 'wrong')).rejects.toThrow(/invalid badge/i);
    expect(getToken()).toBeNull();
  });

  it('attaches the stored session token as an Authorization header on every authenticated call', async () => {
    setSession('a-real-looking-jwt', { badge_id: 'OFFICER-DEMO-01', full_name: 'Demo Officer' });
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));

    await api.listCases();

    const [, options] = fetchSpy.mock.calls[0];
    expect((options?.headers as Record<string, string>).Authorization).toBe('Bearer a-real-looking-jwt');
  });

  it('sends no Authorization header when there is no stored session', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(JSON.stringify([]), { status: 401 }));

    await api.listCases().catch(() => {});

    const [, options] = fetchSpy.mock.calls[0];
    expect((options?.headers as Record<string, string> | undefined)?.Authorization).toBeUndefined();
  });

  it('clears the stored session when the server responds 401 (expired/invalid token)', async () => {
    setSession('a-stale-jwt', { badge_id: 'OFFICER-DEMO-01', full_name: 'Demo Officer' });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Session expired or invalid.' }), { status: 401 })
    );

    await api.listCases().catch(() => {});

    expect(getToken()).toBeNull();
    expect(getOfficer()).toBeNull();
  });

  it('applies the same session-header handling to every previously officer-gated action', async () => {
    setSession('shared-session-token', { badge_id: 'OFFICER-DEMO-01', full_name: 'Demo Officer' });
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async () => new Response(JSON.stringify({ message: 'ok' }), { status: 200 }));

    await api.purgeBiometrics('case-1');
    await api.anchorAuditChain();
    await api.updatePolicy({} as any);
    await api.deleteCase('case-1');

    expect(fetchSpy).toHaveBeenCalledTimes(4);
    for (const call of fetchSpy.mock.calls) {
      const [, options] = call;
      expect((options?.headers as Record<string, string>).Authorization).toBe('Bearer shared-session-token');
    }
  });

  it('logout() clears the stored session', () => {
    setSession('a-token', { badge_id: 'OFFICER-DEMO-01', full_name: 'Demo Officer' });
    api.logout();
    expect(getToken()).toBeNull();
  });
});

describe('clearSession / setSession', () => {
  afterEach(() => localStorage.clear());

  it('round-trips a session through localStorage', () => {
    setSession('tok', { badge_id: 'B-1', full_name: 'Someone' });
    expect(getToken()).toBe('tok');
    expect(getOfficer()).toEqual({ badge_id: 'B-1', full_name: 'Someone' });

    clearSession();
    expect(getToken()).toBeNull();
    expect(getOfficer()).toBeNull();
  });
});
