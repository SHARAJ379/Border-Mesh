import React, { useState } from 'react';
import { Shield, LogIn, Loader2, AlertTriangle } from 'lucide-react';
import { api } from '../services/api';

interface LoginPageProps {
  onLoggedIn: () => void;
}

/**
 * Real per-officer login -- replaces the old single shared officer
 * password (a window.prompt() triggered lazily the first time a
 * destructive action was attempted). Every route now requires a real
 * session (see backend/app/api/deps.py's get_current_officer), so this is
 * the dashboard's actual front door, not an occasional interruption.
 */
export const LoginPage: React.FC<LoginPageProps> = ({ onLoggedIn }) => {
  const [badgeId, setBadgeId] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!badgeId.trim() || !password) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.login(badgeId.trim(), password);
      onLoggedIn();
    } catch (err: any) {
      setError(err.message || 'Login failed.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-paper text-ink flex items-center justify-center p-4">
      <div className="w-full max-w-sm border border-hairline p-8 space-y-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <Shield className="w-8 h-8 text-accent" strokeWidth={1.5} />
          <h1 className="font-display text-[20px] text-ink">BorderMesh</h1>
          <p className="text-[11px] uppercase tracking-[0.06em] text-muted">
            Officer sign-in required
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label-eyebrow block mb-1.5" htmlFor="badge_id">
              Badge ID
            </label>
            <input
              id="badge_id"
              type="text"
              autoComplete="username"
              value={badgeId}
              onChange={(e) => setBadgeId(e.target.value)}
              placeholder="OFFICER-DEMO-01"
              className="field w-full"
              autoFocus
            />
          </div>
          <div>
            <label className="label-eyebrow block mb-1.5" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="field w-full"
            />
          </div>

          {error && (
            <div className="flex items-start gap-2 text-[12px] text-signal-critical">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.75} />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !badgeId.trim() || !password}
            className="btn-primary w-full px-5 py-2.5 text-[11px] font-bold flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={2} />
            ) : (
              <LogIn className="w-3.5 h-3.5" strokeWidth={1.75} />
            )}
            <span>Sign in</span>
          </button>
        </form>

        <p className="text-[10px] text-muted text-center leading-relaxed">
          SIH26188 prototype. Demo credential: badge <span className="figure">OFFICER-DEMO-01</span>,
          password set via <span className="figure">DEFAULT_OFFICER_PASSWORD</span> (see .env.example).
        </p>
      </div>
    </div>
  );
};
