import React, { useEffect, useState } from 'react';
import App from './App';
import { LoginPage } from './pages/LoginPage';
import { api } from './services/api';
import { getOfficer, getToken, SESSION_CHANGED_EVENT, Officer } from './lib/auth';

/**
 * Gates the operational dashboard behind real officer login -- every API
 * route it calls now requires one (see backend/app/api/deps.py's
 * get_current_officer). On mount, a stored token is revalidated against
 * /api/auth/me rather than trusted blindly (it may have expired or been
 * revoked server-side since the last visit); api.ts's authFetch clears an
 * invalid session automatically on any 401, which this listens for via
 * SESSION_CHANGED_EVENT to fall back to the login screen from anywhere in
 * the app, not just this initial check.
 */
export const AppGate: React.FC = () => {
  const [officer, setOfficer] = useState<Officer | null>(getOfficer());
  const [checking, setChecking] = useState<boolean>(!!getToken());

  useEffect(() => {
    if (getToken()) {
      api.restoreSession()
        .then((restored) => setOfficer(restored))
        .finally(() => setChecking(false));
    }

    const onSessionChanged = () => setOfficer(getOfficer());
    window.addEventListener(SESSION_CHANGED_EVENT, onSessionChanged);
    return () => window.removeEventListener(SESSION_CHANGED_EVENT, onSessionChanged);
  }, []);

  if (checking) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center">
        <div className="relative w-8 h-8">
          <div className="absolute inset-0 border border-hairline" />
          <div className="absolute inset-0 border border-accent border-t-transparent border-r-transparent animate-spin" />
        </div>
      </div>
    );
  }

  if (!officer) {
    return <LoginPage onLoggedIn={() => setOfficer(getOfficer())} />;
  }

  return <App />;
};

export default AppGate;
