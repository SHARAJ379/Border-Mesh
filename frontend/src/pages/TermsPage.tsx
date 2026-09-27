import React from 'react';
import { LegalDocumentPage } from './LegalDocumentPage';

// Content mirrors docs/TERMS_AND_CONDITIONS.md -- keep both in sync by hand
// if either changes (see LegalDocumentPage's own comment on why this isn't
// rendered from the markdown file at runtime).
export const TermsPage: React.FC = () => {
  return (
    <LegalDocumentPage title="Terms &amp; Conditions" lastUpdated="27 September 2026">
      <h2>1. What you're looking at</h2>
      <p>
        BorderMesh is a <strong>prototype and demonstration system</strong>, built to show an
        architectural approach to AI-assisted document and identity screening for the Smart India
        Hackathon. It is <strong>not a certified, production, or operational identity-verification
        product</strong>, and nothing in this system, its outputs, or its documentation should be
        read as a claim otherwise.
      </p>
      <p>
        By using this application — whether as a hackathon judge, an evaluator, a developer, or
        anyone else — you acknowledge that it is being presented as a prototype for evaluation
        purposes, subject to the limitations described below.
      </p>

      <h2>2. Not for live or operational use</h2>
      <p>
        <strong>This system must not be used for actual immigration, border-control,
        law-enforcement, or any other decision affecting a real person's legal rights, travel,
        liberty, or status.</strong> It has not been certified, licensed, independently audited, or
        approved for any such use by any authority. Every screening decision this system produces
        is explicitly framed as a risk indicator requiring human officer review, never a final or
        authoritative determination — and that framing exists precisely because the system is not
        reliable enough, on its own, to make one. Deploying this prototype, or any part of it, in
        a real screening or enforcement context would be a misuse of what it actually is.
      </p>

      <h2>3. Accuracy limitations — stated directly, not buried</h2>
      <p>
        This section exists because a "Terms" document that hides known accuracy limitations from
        a Ministry-facing hackathon submission would be a worse look, if scrutinized, than
        disclosing them here plainly. Every figure below is measured and documented in this
        repository's own <code>KNOWN_LIMITATIONS.md</code>.
      </p>
      <ul>
        <li>
          <strong>Tamper/forgery detection recall on real forgeries is 39.5%</strong>, measured
          against CASIA v2.0 (a real, human-made photo-splice benchmark, not a synthetic one) —
          meaning <strong>60.6% of real, human-made document tampering is missed entirely</strong>{' '}
          by this system's forensic model. A separate, commonly-quoted 87.8% figure elsewhere in
          this project's documentation is the model's own training-validation accuracy on
          synthetic splices — an easier, in-distribution measurement, not a real-world accuracy
          claim, and should not be substituted for the number above.
        </li>
        <li>
          <strong>There is no cryptographic chip or PKD verification of any kind.</strong> Every
          validity check in this system is an OCR read of the printed Machine Readable Zone and a
          recomputation of its check digits. This proves the printed text is internally
          self-consistent; it does <strong>not</strong> prove the document was issued by a real
          authority or that it isn't a well-made counterfeit with a checksum-valid MRZ printed on
          it.
        </li>
        <li>
          <strong>The watchlist screening feature checks against three fictional, simulated
          entries</strong> hardcoded into this codebase. It is not connected to any real sanctions
          list, PEP list, or government watchlist of any kind, and a "no match" result from this
          system says nothing about whether a real person appears on any real watchlist.
        </li>
        <li>
          <strong>The liveness/anti-spoofing signal is an uncertified heuristic</strong>,
          validated only against a self-generated synthetic proxy, never against a real
          presentation-attack capture. It is not ISO/IEC 30107-3 conformant Presentation Attack
          Detection, is explicitly non-blocking in the risk scoring, and must not be relied on to
          actually detect a spoofed or replayed face.
        </li>
        <li>
          <strong>Face matching uses an unmodified, stock pretrained model</strong> (98.0%
          accuracy on a standard same-age benchmark). Two attempts to fine-tune it for better
          cross-age matching were made, measured, and both regressed accuracy badly enough that
          neither was shipped — production face matching in this system has no cross-age-specific
          validation behind it.
        </li>
        <li>
          <strong>This system has never been validated against real-world document captures at
          scale.</strong> Every accuracy figure this project has is measured against clean
          benchmark data (real photographs of real forgeries, or clean digital template renders) —
          not real phone photographs taken at an angle, under variable lighting, of a physical
          document in the field. Real-world accuracy is expected to be worse than the figures
          quoted above, not better.
        </li>
        <li>
          <strong>No load or production-scale testing has been performed.</strong> Reported
          latency figures are single-request timings, not a concurrency or throughput benchmark.
        </li>
        <li>
          This system supports <strong>6 document types</strong> (Passport, Aadhaar, PAN, Driving
          Licence, Voter ID, Travel Visa), each hand-built for this prototype. This is not
          comparable in breadth to commercial identity-verification vendors, which typically
          support document templates across 200+ countries and jurisdictions.
        </li>
      </ul>
      <p>
        Full detail, including how each of these was measured and why each gap exists, is in{' '}
        <code>KNOWN_LIMITATIONS.md</code> in this repository.
      </p>

      <h2>4. No warranty</h2>
      <p>
        This system is provided <strong>"as is,"</strong> as a hackathon prototype, with no
        warranty of any kind — express or implied — including, without limitation, any warranty
        of accuracy, reliability, fitness for a particular purpose, or merchantability. The
        limitations in §3 are not exhaustive; they are the ones judged most important to state
        directly.
      </p>

      <h2>5. Security posture</h2>
      <p>
        This system's access control is a single, shared demo API key gating a small number of
        destructive actions (case deletion, biometric purge, policy updates, blockchain
        anchoring) — it is not a per-officer authentication or authorization system, and there is
        no user-account or session model at all. Biometric data is encrypted at rest with a
        single static demo key committed in this repository's own source, not production key
        management. See the <a href="/privacy" className="text-brass-400 hover:text-brass-300 underline">Privacy Policy</a> for full
        detail. Treat this system as having a demo-appropriate security posture, not a hardened
        one.
      </p>

      <h2>6. Synthetic content and demo data</h2>
      <p>
        This system's built-in specimen generator produces entirely fictional documents for a
        fictional "Republic of Utopia," and its default live-face-comparison demo uses
        AI-generated (StyleGAN2) portraits that do not depict real people. Any resemblance of
        generated content to a real person, organization, or government insignia is coincidental
        and unintentional; this system does not represent, and must not be presented as, any
        actual government's official document format or systems. As noted in the Privacy Policy,
        the upload and webcam-capture features do accept and process real input if provided —
        that data is handled per the Privacy Policy, not exempted from it because most of this
        system's design is built around synthetic specimens.
      </p>

      <h2>7. Intellectual context</h2>
      <p>
        This prototype was built for the Smart India Hackathon 2026 in response to Problem
        Statement SIH26188, issued by the Ministry of Home Affairs, Government of India. It is
        presented for evaluation within that context, as one team's independent submission — this
        document does not establish, and should not be read as implying, any endorsement,
        partnership, or contractual relationship with the Ministry beyond the hackathon's own
        evaluation process. No claim is made here regarding licensing, ownership transfer, or
        commercial rights beyond what the hackathon's own rules and submission terms independently
        govern — those govern this submission, not this document.
      </p>

      <h2>8. Governing context</h2>
      <p>
        This project was built with the Digital Personal Data Protection Act, 2023 (India) as its
        explicit reference point for the privacy-related design choices described in the Privacy
        Policy, and is intended to be read in that legal context. This document is not a
        substitute for legal advice and does not itself constitute a binding contract creating
        obligations beyond accurately describing what this prototype does and does not do.
      </p>

      <h2>9. Changes</h2>
      <p>
        This document reflects the system as of the date above and may be updated as the
        prototype changes during hackathon development or evaluation.
      </p>

      <h2>10. Contact</h2>
      <p>
        As with the Privacy Policy: this is a hackathon prototype, not a live service, so no
        dedicated support or legal contact channel — at this project team or at the Ministry of
        Home Affairs — is designated here. Direct questions to the SIH26188 submission's project
        team through the hackathon's own official channels.
      </p>
    </LegalDocumentPage>
  );
};
