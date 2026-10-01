import {
  DashboardStats,
  CaseItem,
  CaseDetail,
  RiskCheck,
  AuditLog,
  OfficerDecision,
  ChainVerificationResult,
  PolicySettings,
  BlockchainAnchor,
  ChangeDetectionResult,
  DpdpComplianceStatus
} from '../types';
import { authHeader, clearSession, setSession, getOfficer, Officer } from '../lib/auth';

const API_BASE = '/api';

// The New Screening pipeline's steps used to call plain fetch() with no
// timeout -- a request that never resolves (backend wedged on a malformed
// upload, network stall, etc.) left the UI stuck on "running" forever with
// no way out but reloading the tab. Each screening-pipeline call below is
// bounded so a stuck request surfaces as a clear, catchable error instead.
const SCREENING_STEP_TIMEOUT_MS = 20000;

// Every API call now requires a real logged-in officer (see
// backend/app/api/deps.py's get_current_officer) -- this wraps fetch to
// attach the session's Authorization header automatically, and to clear
// the stored session (and let the app shell fall back to the login screen,
// via lib/auth.ts's SESSION_CHANGED_EVENT) on a 401, instead of every
// individual call site having to handle that itself. Replaces the old
// `officerFetch`, which only wrapped the 4 most sensitive endpoints with a
// single shared password prompted via window.prompt.
async function authFetch(
  url: string,
  options: RequestInit = {},
  timeoutMs: number = SCREENING_STEP_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(url, {
      ...options,
      headers: { ...options.headers, ...authHeader() },
      signal: controller.signal
    });
  } catch (err: any) {
    if (err.name === 'AbortError') {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s -- the server may be unavailable or unable to process this file.`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 401) {
    clearSession();
  }
  return res;
}

export const api = {
  async login(badgeId: string, password: string): Promise<{ officer: Officer }> {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ badge_id: badgeId, password })
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail || 'Invalid badge ID or password.');
    }
    const data = await res.json();
    setSession(data.access_token, data.officer);
    return { officer: data.officer };
  },

  logout(): void {
    clearSession();
  },

  /** Restores a session on page reload: confirms the stored token is still
   * valid and refreshes the cached officer display name. */
  async restoreSession(): Promise<Officer | null> {
    const res = await authFetch(`${API_BASE}/auth/me`);
    if (!res.ok) return null;
    return res.json();
  },

  getCachedOfficer: getOfficer,

  async getHealth() {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('Health check failed');
    return res.json();
  },

  async getDashboardStats(): Promise<DashboardStats> {
    const res = await authFetch(`${API_BASE}/dashboard/stats`);
    if (!res.ok) throw new Error('Failed to fetch dashboard statistics');
    return res.json();
  },

  async listCases(params?: {
    status?: string;
    risk_level?: string;
    country?: string;
    limit?: number;
    offset?: number;
  }): Promise<CaseItem[]> {
    const query = new URLSearchParams();
    if (params?.status) query.append('status', params.status);
    if (params?.risk_level) query.append('risk_level', params.risk_level);
    if (params?.country) query.append('country', params.country);
    if (params?.limit) query.append('limit', params.limit.toString());
    if (params?.offset) query.append('offset', params.offset.toString());

    const res = await authFetch(`${API_BASE}/cases?${query.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch cases list');
    return res.json();
  },

  async getCaseDetail(caseId: string): Promise<CaseDetail> {
    const res = await authFetch(`${API_BASE}/cases/${caseId}`);
    if (!res.ok) throw new Error(`Failed to fetch case ${caseId}`);
    return res.json();
  },

  async getCaseChecks(caseId: string): Promise<RiskCheck[]> {
    const res = await authFetch(`${API_BASE}/cases/${caseId}/checks`);
    if (!res.ok) throw new Error('Failed to fetch risk checks');
    return res.json();
  },

  async getCaseAuditTrail(caseId: string): Promise<AuditLog[]> {
    const res = await authFetch(`${API_BASE}/cases/${caseId}/audit`);
    if (!res.ok) throw new Error('Failed to fetch case audit trail');
    return res.json();
  },

  async recordOfficerDecision(
    caseId: string,
    decision: OfficerDecision,
    notes?: string
  ): Promise<CaseItem> {
    const res = await authFetch(`${API_BASE}/cases/${caseId}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, notes })
    });
    if (!res.ok) throw new Error('Failed to record officer decision');
    return res.json();
  },

  async deleteCase(caseId: string): Promise<{ message: string }> {
    const res = await authFetch(`${API_BASE}/cases/${caseId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete case data');
    return res.json();
  },

  async purgeBiometrics(caseId: string): Promise<{
    case_id: string;
    message: string;
    biometrics_purged: boolean;
    purged_files_count: number;
    audit_hash: string;
  }> {
    const res = await authFetch(`${API_BASE}/cases/${caseId}/purge-biometrics`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to purge case biometrics');
    return res.json();
  },

  async getAuditLogs(params?: {
    action?: string;
    actor?: string;
    case_id?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<AuditLog[]> {
    const query = new URLSearchParams();
    if (params?.action) query.append('action', params.action);
    if (params?.actor) query.append('actor', params.actor);
    if (params?.case_id) query.append('case_id', params.case_id);
    if (params?.search) query.append('search', params.search);
    if (params?.limit) query.append('limit', params.limit.toString());
    if (params?.offset) query.append('offset', params.offset.toString());

    const res = await authFetch(`${API_BASE}/audit?${query.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch audit ledger logs');
    return res.json();
  },

  async verifyAuditChain(): Promise<ChainVerificationResult> {
    const res = await authFetch(`${API_BASE}/audit/verify`);
    if (!res.ok) throw new Error('Audit ledger chain verification failed');
    return res.json();
  },

  async getDpdpComplianceStatus(): Promise<DpdpComplianceStatus> {
    const res = await authFetch(`${API_BASE}/compliance/dpdp-status`);
    if (!res.ok) throw new Error('Failed to load DPDP compliance status');
    return res.json();
  },

  async verifyCaseChain(caseId: string): Promise<ChainVerificationResult> {
    const res = await authFetch(`${API_BASE}/audit/cases/${caseId}/verify`);
    if (!res.ok) throw new Error('Case chain verification failed');
    return res.json();
  },

  async listBlockchainAnchors(): Promise<BlockchainAnchor[]> {
    // Deliberately plain fetch, not authFetch: this one stays public
    // without login (see backend/app/api/routes/audit.py) -- everything it
    // returns is already public on-chain once anchored.
    const res = await fetch(`${API_BASE}/audit/anchors`);
    if (!res.ok) throw new Error('Failed to fetch blockchain anchor history');
    return res.json();
  },

  async anchorAuditChain(): Promise<BlockchainAnchor> {
    const res = await authFetch(`${API_BASE}/audit/anchor`, { method: 'POST' });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail || 'Failed to anchor audit chain to testnet');
    }
    return res.json();
  },

  // --- Staged Screening Pipeline Steps ---
  async uploadScreeningDocument(
    file: File,
    documentType: string = 'Passport',
    country: string = 'Unknown'
  ): Promise<{
    case_id: string;
    case_number: string;
    document_image_url: string;
    document_type: string;
    status: string;
  }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);
    formData.append('country', country);

    const res = await authFetch(`${API_BASE}/screening/upload`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  async runStepOCR(caseId: string) {
    const res = await authFetch(`${API_BASE}/screening/${caseId}/ocr`, { method: 'POST' });
    if (!res.ok) throw new Error('OCR extraction failed');
    return res.json();
  },

  async runStepValidate(caseId: string) {
    const res = await authFetch(`${API_BASE}/screening/${caseId}/validate`, { method: 'POST' });
    if (!res.ok) throw new Error('MRZ and rules validation failed');
    return res.json();
  },

  async runStepTamper(caseId: string) {
    const res = await authFetch(`${API_BASE}/screening/${caseId}/tamper`, { method: 'POST' });
    if (!res.ok) throw new Error('Tamper forensics failed');
    return res.json();
  },

  async runStepFace(caseId: string, liveFaceFile?: File) {
    const formData = new FormData();
    if (liveFaceFile) {
      formData.append('file', liveFaceFile);
    }
    const res = await authFetch(`${API_BASE}/screening/${caseId}/face`, {
      method: 'POST',
      body: liveFaceFile ? formData : undefined
    });
    if (!res.ok) throw new Error('Face verification failed');
    return res.json();
  },

  async runStepRisk(caseId: string) {
    const res = await authFetch(`${API_BASE}/screening/${caseId}/risk`, { method: 'POST' });
    if (!res.ok) throw new Error('Risk score aggregation failed');
    return res.json();
  },

  // --- Demo Scenario Automation ---
  async runDemoScenario(scenarioKey: string) {
    const res = await authFetch(`${API_BASE}/demo/scenario`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_key: scenarioKey })
    });
    if (!res.ok) throw new Error('Failed to run demo scenario');
    return res.json();
  },

  async generateSpecimenDoc(params: {
    mode: string;
    surname?: string;
    given_names?: string;
    doc_number?: string;
    country_name?: string;
  }) {
    const res = await authFetch(`${API_BASE}/demo/generate-doc`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });
    if (!res.ok) throw new Error('Failed to generate specimen document');
    return res.json();
  },

  async runChangeDetectionDemo(): Promise<ChangeDetectionResult> {
    // Generates two specimens and runs OCR/MRZ/face comparison on both --
    // slower than the other demo endpoints, so this gets its own longer
    // timeout rather than the shared 20s SCREENING_STEP_TIMEOUT_MS.
    const res = await authFetch(
      `${API_BASE}/demo/change-detection`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' } },
      40000
    );
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail || 'Failed to run change detection demo');
    }
    return res.json();
  },

  async getPolicy(): Promise<PolicySettings> {
    const res = await authFetch(`${API_BASE}/settings/policy`);
    if (!res.ok) throw new Error('Failed to load policy settings');
    return res.json();
  },

  async updatePolicy(policy: PolicySettings): Promise<PolicySettings> {
    const res = await authFetch(`${API_BASE}/settings/policy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(policy)
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail || 'Failed to update policy settings');
    }
    return res.json();
  }
};
