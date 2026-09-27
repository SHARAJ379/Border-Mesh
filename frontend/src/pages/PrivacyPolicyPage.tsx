import React from 'react';
import { LegalDocumentPage } from './LegalDocumentPage';

// Content mirrors docs/PRIVACY_POLICY.md -- keep both in sync by hand if
// either changes (see LegalDocumentPage's own comment on why this isn't
// rendered from the markdown file at runtime).
export const PrivacyPolicyPage: React.FC = () => {
  return (
    <LegalDocumentPage title="Privacy Policy" lastUpdated="27 September 2026">
      <p>
        This document describes what BorderMesh actually does with data, as built today. It is
        written against the code in this repository, not against what a production version might
        eventually do. Where a control doesn't exist yet, this policy says so plainly rather than
        describing an aspiration as if it were shipped.
      </p>
      <p>
        <strong>This is not a live service processing real individuals' data as part of any
        operational program.</strong> It is a hackathon prototype, run by its own developers for
        demonstration and evaluation purposes. If you are a judge, evaluator, or anyone else
        trying the system, the sections below tell you exactly what happens to whatever you feed
        it.
      </p>

      <h2>1. What this system is, and what it isn't</h2>
      <p>
        BorderMesh is a decision-support prototype for immigration/border document screening: it
        runs OCR, MRZ checksum validation, forensic tamper analysis, biometric face comparison,
        and a simulated watchlist check against an uploaded document image and a live face
        capture, then produces an explainable 0–100 risk score for a human officer to review. It
        never issues a final determination on its own.
      </p>
      <p>
        It is <strong>not connected to any real government database, law-enforcement system, or
        national identity registry.</strong> The "watchlist" it checks against is three fictional,
        clearly-labeled demo entries hardcoded into this codebase — not a real sanctions list, PEP
        list, or lookalike system.
      </p>

      <h2>2. What data this system actually processes</h2>
      <p>
        The interface is built around synthetic demo specimens by design — a built-in generator
        can produce a fictional passport/Aadhaar/PAN/Driving Licence/Voter ID/Visa specimen for a
        fictional "Republic of Utopia" identity, and the default live-face comparison uses
        AI-generated (StyleGAN2) demo portraits that don't depict real people.
      </p>
      <p>
        <strong>That said, this prototype does not currently refuse or special-case real
        input.</strong> The document upload dropzone and the "capture from webcam" control both
        accept and process whatever image is actually provided. If you upload a real photograph of
        an identity document, or capture your own face through the webcam control, that real image
        is processed by the same pipeline as a synthetic specimen — OCR runs on it, a face
        embedding is computed from it, and it is stored (encrypted, see §3) exactly like demo data
        would be. There is no technical barrier in this codebase preventing real personal data
        from being entered, and no separate handling path for it. If you're testing this system,
        we recommend using the built-in specimen generator or one of the provided demo scenarios
        rather than your own or someone else's real document or face, unless you specifically
        intend to test with real data and accept the handling described below.
      </p>
      <p>Concretely, what's collected and derived per screening:</p>
      <ul>
        <li>The document image itself, and the live face image (webcam capture or uploaded file).</li>
        <li>
          OCR-extracted fields (name, document number, dates, nationality, etc.) and, where
          applicable, parsed Machine Readable Zone data.
        </li>
        <li>
          A face embedding (a numeric vector derived from the live face image), used both for the
          document/live match and for cross-case duplicate-identity comparison against every other
          case in the same database.
        </li>
        <li>Derived risk signals, scores, and an audit trail of the processing steps performed on that case.</li>
        <li>
          The document number, hashed (SHA-256) for indexing — the plaintext document number
          itself is not stored in the case record once hashed.
        </li>
      </ul>

      <h2>3. How this data is protected</h2>
      <ul>
        <li>
          <strong>Biometric artifacts are encrypted at rest.</strong> Document scans, live face
          captures, extracted face crops, tamper-analysis heatmaps, and cross-case face embeddings
          are all encrypted using Fernet (AES-128-CBC with an HMAC-SHA256 authentication tag)
          before they touch disk.
        </li>
        <li>
          <strong>Honestly: the shipped encryption key is a single static demo key, committed in
          this repository's own source, not a production secret.</strong> There is no key
          rotation, no envelope encryption or per-record data keys, and no HSM/KMS involved — it
          is one symmetric key, generated once, the same way this project's other demo secrets
          are. Anyone who has this repository's source code has the key. This is disclosed, not
          hidden: see <code>backend/app/core/config.py</code>'s own comment on{' '}
          <code>BIOMETRIC_ENCRYPTION_KEY</code>, and the startup check (
          <code>default_secrets_still_in_use</code>) that refuses to boot with this default if{' '}
          <code>ENVIRONMENT</code> is ever set to anything other than <code>development</code>. A
          real deployment would need real key management; this prototype does not have it.
        </li>
        <li>
          <strong>Document numbers are hashed, not stored in plaintext</strong>, using SHA-256,
          for indexing and cross-case matching without retaining the raw value in the case record.
        </li>
        <li>
          <strong>Sensitive actions require a shared API key.</strong> Permanently deleting a
          case, purging biometric artifacts, updating risk-policy settings, and triggering
          blockchain anchoring all require an <code>X-API-Key</code> header matching a configured
          officer key. This is a minimal gate against a bare, credential-free request — it is{' '}
          <strong>not</strong> a per-officer identity or authentication system. There is no login,
          no user accounts, and every action in the audit trail is attributed to a single
          hardcoded demo actor, not a real, distinguishable officer.
        </li>
        <li>
          <strong>No data is sent to any third-party AI service.</strong> OCR (Tesseract), face
          detection and embedding (a local facenet-pytorch model), and tamper analysis (a
          locally-trained CNN plus classical image-forensics heuristics) all run on this
          application's own server. Nothing in this pipeline calls out to an external AI API with
          document or biometric content.
        </li>
      </ul>

      <h2>4. The optional blockchain anchoring feature</h2>
      <p>
        An officer can, on demand, anchor the current audit-chain hash to a public blockchain.{' '}
        <strong>This writes to Ethereum Sepolia — a public test network — using a throwaway,
        faucet-funded wallet, not Ethereum mainnet.</strong> The only thing ever written to that
        public, permanent ledger is a SHA-256 hash of the audit chain's state, not any personal
        data, document content, or biometric data itself. That said, once anchored, that hash is
        on a public, immutable ledger permanently and cannot be deleted or amended — worth knowing
        before using this feature, even though the hash itself doesn't reveal document content.
        This feature is entirely optional; the application works fully with it never used.
      </p>

      <h2>5. Data retention and deletion</h2>
      <p>
        <strong>There is no automatic data retention limit or scheduled deletion in this
        system.</strong> A case, its documents, its biometric artifacts, and its derived data
        persist indefinitely until one of the following officer-triggered actions occurs:
      </p>
      <ul>
        <li>
          <strong>Biometric purge</strong> (<code>POST /api/cases/{'{case_id}'}/purge-biometrics</code>)
          permanently deletes the raw document image, live face image, extracted face crops,
          tamper heatmap, and the case's cross-case face embedding from disk and the database,
          while retaining the anonymized case record and risk score for audit purposes. This
          action requires the officer API key and is logged as an immutable, hash-chained audit
          event.
        </li>
        <li>
          <strong>Case deletion</strong> (<code>DELETE /api/cases/{'{case_id}'}</code>) removes the
          case and its associated files entirely. Note: deleting a case that already has audit log
          entries breaks the cryptographic verification of the audit chain for every case after
          it, since there is no chain-repair mechanism — this is a known limitation, not a hidden
          side effect.
        </li>
      </ul>
      <p>
        There is currently <strong>no self-service mechanism for an individual to request access
        to, correction of, or erasure of their own data</strong> — both actions above are
        officer-triggered, not something a data subject can invoke themselves through this
        application.
      </p>

      <h2>6. Alignment with the Digital Personal Data Protection Act, 2023</h2>
      <p>
        This section mirrors the in-app Compliance Dashboard ("DPDP Compliance" in the sidebar),
        which reads these facts live from the running system — if the two ever disagree, the
        dashboard's live figures are authoritative, not this document.
      </p>
      <p><strong>What genuinely exists:</strong></p>
      <table>
        <thead>
          <tr>
            <th>DPDP Act 2023 principle</th>
            <th>What this system actually does</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Reasonable Security Safeguards (Sec. 8(5))</td>
            <td>Biometric artifacts encrypted at rest (Fernet/AES-128-CBC+HMAC); see §3 for the honest caveat about the demo key.</td>
          </tr>
          <tr>
            <td>Storage Limitation &amp; Erasure (Sec. 8(7)–8(8))</td>
            <td>Officer-triggered biometric purge and case deletion exist and are audit-logged; no automatic/scheduled erasure exists.</td>
          </tr>
          <tr>
            <td>Accountability (Sec. 8, general)</td>
            <td>A cryptographically hash-chained audit log records every processing step per case, independently verifiable.</td>
          </tr>
          <tr>
            <td>Data Minimization (implicit in Sec. 5)</td>
            <td>Document numbers are stored as SHA-256 hashes, not plaintext.</td>
          </tr>
        </tbody>
      </table>
      <p><strong>What does not exist, stated plainly rather than omitted:</strong></p>
      <ul>
        <li>No consent-capture flow — this application has no mechanism to record or manage a data subject's consent.</li>
        <li>No self-service Data Principal rights portal (access, correction, or erasure requests initiated by the individual).</li>
        <li>No data breach notification mechanism to India's Data Protection Board or to affected individuals.</li>
        <li>No cross-border data transfer safeguards.</li>
        <li>None of the Significant Data Fiduciary obligations (Data Protection Impact Assessment, independent data auditor, designated Data Protection Officer) are implemented.</li>
      </ul>
      <p>
        <strong>This is illustrative for a hackathon prototype, not a legal compliance opinion or
        certification.</strong> Nothing in this document or the Compliance Dashboard should be
        read as a representation that this system satisfies the DPDP Act 2023 or any other
        data-protection law in full; the mapping above identifies which specific provisions are
        and are not addressed by existing code, so that gap is visible rather than assumed away.
      </p>

      <h2>7. Grievance / contact</h2>
      <p>
        Because this is a hackathon prototype and not a live deployment processing real
        individuals' data under any operational mandate, <strong>no grievance officer or
        dedicated privacy-contact channel is designated</strong> — inventing one, or naming a
        Ministry of Home Affairs contact this project has no actual relationship with, would
        misrepresent this project's actual status. Questions about this prototype should go
        through the SIH26188 submission's own project team and the Smart India Hackathon's
        official channels, not through any contact address implied by this document or by the
        problem statement's issuing organization.
      </p>

      <h2>8. Changes to this policy</h2>
      <p>
        This document reflects the system as of the date above and will be updated if the
        system's actual data handling changes during hackathon development or evaluation. It
        carries no obligation beyond describing this prototype honestly.
      </p>
    </LegalDocumentPage>
  );
};
