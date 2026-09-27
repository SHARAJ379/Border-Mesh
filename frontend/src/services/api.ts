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

const API_BASE = '/api';

// The New Screening pipeline's steps used to call plain fetch() with no
// timeout -- a request that never resolves (backend wedged on a malformed
// upload, network stall, etc.) left the UI stuck on "running" forever with
// no way out but reloading the tab. Each screening-pipeline call below is
// bounded so a stuck request surfaces as a clear, catchable error instead.
const SCREENING_STEP_TIMEOUT_MS = 20000;

async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeoutMs: number = SCREENING_STEP_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (err: any) {
    if (err.name === 'AbortError') {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s -- the server may be unavailable or unable to process this file.`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

// Officer-gated actions (case deletion, biometric purge, policy updates,
// blockchain anchoring -- see backend/app/api/deps.py's require_officer_auth)
// require an X-API-Key header. This USED TO be a literal key value baked
// into this file as a hardcoded fallback constant -- meaning the actual
// secret was always present in plaintext in the built JS bundle, readable
// by anyone with browser devtools, regardless of whether a build-time
// override was configured. There is no key-shaped literal anywhere in this
// module now: the officer enters the password once per browser tab session
// (sessionStorage, cleared when the tab closes), and it's only ever held in
// memory/sessionStorage on the client, never in source or the shipped bundle.
const OFFICER_KEY_STORAGE_KEY = 'bordermesh_officer_key';

function getStoredOfficerKey(): string | null {
  return sessionStorage.getItem(OFFICER_KEY_STORAGE_KEY);
}

function promptForOfficerKey(): string | null {
  const key = window.prompt('Officer authorization required.\n\nEnter the officer password to continue:');
  if (key) sessionStorage.setItem(OFFICER_KEY_STORAGE_KEY, key);
  return key;
}

// Wraps fetch for the 4 officer-gated endpoints: attaches the session's
// stored key (prompting once if none is stored yet), and on a 401 (missing,
// wrong, or stale key) clears whatever was stored and prompts exactly once
// more before giving up -- covers both "never entered a key this session"
// and "entered a wrong/outdated one" without looping indefinitely.
async function officerFetch(url: string, options: RequestInit = {}): Promise<Response> {
  let key = getStoredOfficerKey() ?? promptForOfficerKey();
  if (!key) throw new Error('Officer authorization is required for this action.');

  const withKey = (k: string): RequestInit => ({
    ...options,
    headers: { ...options.headers, 'X-API-Key': k }
  });

  let res = await fetch(url, withKey(key));
  if (res.status === 401) {
    sessionStorage.removeItem(OFFICER_KEY_STORAGE_KEY);
    key = promptForOfficerKey();
    if (!key) throw new Error('Officer authorization is required for this action.');
    res = await fetch(url, withKey(key));
  }
  return res;
}

export const api = {
  async getHealth() {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('Health check failed');
    return res.json();
  },

  async getDashboardStats(): Promise<DashboardStats> {
    const res = await fetch(`${API_BASE}/dashboard/stats`);
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

    const res = await fetch(`${API_BASE}/cases?${query.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch cases list');
    return res.json();
  },

  async getCaseDetail(caseId: string): Promise<CaseDetail> {
    const res = await fetch(`${API_BASE}/cases/${caseId}`);
    if (!res.ok) throw new Error(`Failed to fetch case ${caseId}`);
    return res.json();
  },

  async getCaseChecks(caseId: string): Promise<RiskCheck[]> {
    const res = await fetch(`${API_BASE}/cases/${caseId}/checks`);
    if (!res.ok) throw new Error('Failed to fetch risk checks');
    return res.json();
  },

  async getCaseAuditTrail(caseId: string): Promise<AuditLog[]> {
    const res = await fetch(`${API_BASE}/cases/${caseId}/audit`);
    if (!res.ok) throw new Error('Failed to fetch case audit trail');
    return res.json();
  },

  async recordOfficerDecision(
    caseId: string,
    decision: OfficerDecision,
    notes?: string
  ): Promise<CaseItem> {
    const res = await fetch(`${API_BASE}/cases/${caseId}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, notes, officer_id: 'OFFICER-DEMO-01' })
    });
    if (!res.ok) throw new Error('Failed to record officer decision');
    return res.json();
  },

  async deleteCase(caseId: string): Promise<{ message: string }> {
    const res = await officerFetch(`${API_BASE}/cases/${caseId}`, { method: 'DELETE' });
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
    const res = await officerFetch(`${API_BASE}/cases/${caseId}/purge-biometrics`, { method: 'POST' });
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

    const res = await fetch(`${API_BASE}/audit?${query.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch audit ledger logs');
    return res.json();
  },

  async verifyAuditChain(): Promise<ChainVerificationResult> {
    const res = await fetch(`${API_BASE}/audit/verify`);
    if (!res.ok) throw new Error('Audit ledger chain verification failed');
    return res.json();
  },

  async getDpdpComplianceStatus(): Promise<DpdpComplianceStatus> {
    const res = await fetch(`${API_BASE}/compliance/dpdp-status`);
    if (!res.ok) throw new Error('Failed to load DPDP compliance status');
    return res.json();
  },

  async verifyCaseChain(caseId: string): Promise<ChainVerificationResult> {
    const res = await fetch(`${API_BASE}/audit/cases/${caseId}/verify`);
    if (!res.ok) throw new Error('Case chain verification failed');
    return res.json();
  },

  async listBlockchainAnchors(): Promise<BlockchainAnchor[]> {
    const res = await fetch(`${API_BASE}/audit/anchors`);
    if (!res.ok) throw new Error('Failed to fetch blockchain anchor history');
    return res.json();
  },

  async anchorAuditChain(): Promise<BlockchainAnchor> {
    const res = await officerFetch(`${API_BASE}/audit/anchor`, { method: 'POST' });
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

    const res = await fetchWithTimeout(`${API_BASE}/screening/upload`, {
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
    const res = await fetchWithTimeout(`${API_BASE}/screening/${caseId}/ocr`, { method: 'POST' });
    if (!res.ok) throw new Error('OCR extraction failed');
    return res.json();
  },

  async runStepValidate(caseId: string) {
    const res = await fetchWithTimeout(`${API_BASE}/screening/${caseId}/validate`, { method: 'POST' });
    if (!res.ok) throw new Error('MRZ and rules validation failed');
    return res.json();
  },

  async runStepTamper(caseId: string) {
    const res = await fetchWithTimeout(`${API_BASE}/screening/${caseId}/tamper`, { method: 'POST' });
    if (!res.ok) throw new Error('Tamper forensics failed');
    return res.json();
  },

  async runStepFace(caseId: string, liveFaceFile?: File) {
    const formData = new FormData();
    if (liveFaceFile) {
      formData.append('file', liveFaceFile);
    }
    const res = await fetchWithTimeout(`${API_BASE}/screening/${caseId}/face`, {
      method: 'POST',
      body: liveFaceFile ? formData : undefined
    });
    if (!res.ok) throw new Error('Face verification failed');
    return res.json();
  },

  async runStepRisk(caseId: string) {
    const res = await fetchWithTimeout(`${API_BASE}/screening/${caseId}/risk`, { method: 'POST' });
    if (!res.ok) throw new Error('Risk score aggregation failed');
    return res.json();
  },

  // --- Demo Scenario Automation ---
  async runDemoScenario(scenarioKey: string) {
    const res = await fetch(`${API_BASE}/demo/scenario`, {
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
    const res = await fetchWithTimeout(`${API_BASE}/demo/generate-doc`, {
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
    const res = await fetchWithTimeout(
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
    const res = await fetch(`${API_BASE}/settings/policy`);
    if (!res.ok) throw new Error('Failed to load policy settings');
    return res.json();
  },

  async updatePolicy(policy: PolicySettings): Promise<PolicySettings> {
    const res = await officerFetch(`${API_BASE}/settings/policy`, {
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
