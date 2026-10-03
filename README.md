# BorderMesh — AI-Based Fake Identity & Document Screening System

**Smart India Hackathon (SIH) 2026 Prototype**  
**Problem Statement:** `SIH26188 — AI-Based Fake Identity & Document Screening System`  
**Theme:** `Blockchain & Cybersecurity`  
**Role:** AI-Assisted Immigration & Border Security Document Screening Decision-Support System

---

## 1. Project Overview

**BorderMesh** is an AI-assisted travel document screening and fraud-detection prototype engineered for immigration officers, border control authorities, and identity screening checkpoints. 

The system implements a multi-signal forensic pipeline that analyzes physical and machine-readable zones of identity documents, inspects image compression and splicing artifacts, verifies facial biometrics against live captures, queries simulated watchlists, and aggregates evidence into an **explainable 0–100 risk score** with actionable recommendations.

> **CRITICAL ETHICAL & LEGAL NOTICE:**  
> This application is an **SIH prototype and decision-support tool**, not a production law enforcement system. It **never** connects to live government or Interpol databases, **never** accuses an individual of being fraudulent, and strictly presents results as *"risk indicators requiring human officer review."*
>
> **On synthetic vs. real data — stated accurately, not softened:** the demo defaults to synthetic data — a built-in generator produces fictional specimens for a fictional "Republic of Utopia," and the default live-face comparison uses AI-generated (StyleGAN2) portraits (`demo-data/faces/person_a.jpg`, `person_b.jpg`) that don't depict real people. **But the document-upload and webcam-capture flows genuinely accept and process real images if you provide one** — there is no special-casing or technical barrier in this codebase that limits it to synthetic input, and a real document photo or a real face capture is stored (encrypted) and processed by the same pipeline as demo data. If you're evaluating this system, use the built-in specimen generator or the provided demo scenarios rather than real documents or faces, unless you specifically intend to test with real data. See [`docs/PRIVACY_POLICY.md`](docs/PRIVACY_POLICY.md) (also reachable in-app at `/privacy`) for exactly what happens to whatever is provided.
>
> **Read [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) before trusting any number in this document.** It states, with exact measured figures and the honest "why," exactly what this system does and doesn't do well — real tamper-CNN recall on human-made forgeries (not the synthetic-validation number quoted below), the unmodified-VGGFace2 face embedder and two fine-tune attempts that were tried and reverted, the fictional watchlist, the single static demo encryption key, and more. This README states what the system does; that file states where it falls short. Treat both as equally authoritative.

---

## 2. Core Processing Pipeline

```text
DOCUMENT UPLOAD / CAPTURE
         ↓
IMAGE PREPROCESSING (OpenCV Normalization, Contrast CLAHE, Deskewing)
         ↓
MODULE 1: OCR EXTRACTION (PyTesseract, Word Layout, Visual Zone Field Parsing)
         ↓
MODULE 2: ICAO 9303 MRZ PARSING & VALIDATION (TD3 / TD1 Checksums: 7-3-1 Algorithm)
         ↓
DOCUMENT RULES ENGINE (Cross-field Mismatch, Expiration, Plausibility)
         ↓
MODULE 3: TAMPER AI FORENSICS (Error Level Analysis ELA, Boundary Seams, CNN)
         ↓
MODULE 4: BIOMETRIC FACE VERIFICATION (OpenCV Face Detection, MobileNet Embeddings)
         ↓
MODULE 5: CENTRAL RISK ENGINE (Configurable Weights, Explainable +pts Breakdown)
         ↓
OFFICER CASE FILE & DETERMINATION (Cleared, Secondary Inspection, Escalated)
         ↓
IMMUTABLE AUDIT TRAIL (Chain of Custody Event Ledger)
```

---

## 3. Four Core AI Forensic Modules

### Module 1 — OCR Field Extraction & Document Type Detection
- **Image Preprocessing:** High-resolution normalization (1600px width), grayscale conversion, Contrast Limited Adaptive Histogram Equalization (CLAHE), and Gaussian denoising.
- **Engine:** PyTesseract with layout analysis.
- **7 Document Types, Auto-Detected from Content:** Passport (ICAO MRZ), Aadhaar, PAN, Driving Licence, Voter ID (EPIC), Visa, and Residence/Work/Entry/Transit Permit — detected from issuer-specific text markers (`ocr_service.py`'s `_detect_document_type`), not a user-selected dropdown. Only Passport carries an ICAO MRZ in this system's model; the other six (Visa included) skip MRZ parsing entirely rather than risk fabricating a fake MRZ from a card's own boilerplate text.
- **Extracted Fields:** Full Name, Document Number, Nationality, Country of Issue, Date of Birth, Date of Issue, Date of Expiry, Sex, and (for MRZ-bearing documents) the MRZ text buffer.
- **Confidence Scoring:** Real-time average word-level confidence calculation.
- **Dedicated MRZ-Band Pass:** A second, separate OCR pass crops just the machine-readable zone, upscales it 3x, binarizes it, and restricts Tesseract to the `A-Z0-9<` character set with a single-uniform-block layout mode — the standard technique for reliable MRZ OCR, far more accurate than reading the MRZ off the general whole-document pass. Includes a reconstruction step that recovers under-counted runs of the `<` filler character without corrupting fixed-position check digits.

### Module 2 — ICAO 9303 MRZ Checksum Validator & Rules Engine
- **MRZ Standard Compliance:** Full Doc 9303 specification compliance for TD3 (Passport: 2 lines × 44 characters), TD1, and TD2.
- **7-3-1 Weight Verification:** True mathematical check-digit calculations over:
  - Document Number Checksum
  - Date of Birth Checksum
  - Expiry Date Checksum
  - Composite Checksum (Full record payload)
- **Document Rules Engine:** Cross-validates visual zone text against machine-readable zone, verifies calendar plausibility (flags future birth dates and expired documents), and detects inconsistent document numbers.

### Module 3 — Tamper AI (Forensic Multi-Signal Pipeline)
- **Signal A — Error Level Analysis (ELA):** Resaves image at 90% JPEG quality, computes amplified pixel deltas, and generates an interactive thermal jet heatmap visualizer.
- **Signal B — Edge Discontinuity & Splicing:** Laplacian high-frequency gradient variance to identify pasted rectangular patches.
- **Signal C — Portrait Seam Analysis:** Boundary gradient consistency check around the photo perimeter to detect photo replacement.
- **Signal D — Text Compression Inconsistency:** Compares ELA compression ratios between MRZ and document body.
- **Signal E — Lightweight CNN:** 3-layer Convolutional Neural Network patch classifier, sampled across the portrait/center/MRZ regions (not just the document center, where tampering rarely occurs). An untrained network is deliberately excluded from the score rather than mixed in as noise — `TamperDetectionService` only uses its output once a trained checkpoint exists (`backend/app/ml/weights/tamper_cnn.pth`, committed to this repo). Trained via `scripts/train_tamper_cnn.py` on a blend of the synthetic splice-forgery generator's patches and real human-made splices from the CASIA v2.0 image tampering dataset (real photographs, not documents, but a far less predictable splice signature than synthetic rectangular copy-paste alone) — **87.8% validation accuracy**. Re-run training yourself with `CASIA2_DIR=<path to extracted CASIA2> PYTHONPATH=backend python scripts/train_tamper_cnn.py` (falls back to synthetic-only if `CASIA2_DIR` is unset).

  **That 87.8% is training-validation accuracy, not real-world recall — stated plainly rather than left to imply more than it does.** Evaluated directly against the full CASIA v2.0 held-out set (24,944 real, human-made splice patches), the same checkpoint scores **71.2% accuracy, 39.5% recall** — meaning **60.6% of real forgeries are missed** by this signal alone. See [`KNOWN_LIMITATIONS.md` §1](KNOWN_LIMITATIONS.md#1-tamper-detection-accuracy-on-real-forgeries) for the full breakdown and why this wasn't re-architected before judging. This is one signal of five feeding the risk engine below, not a standalone verdict — but it is the weakest of the five, and the one most likely to matter if you're deciding how much to trust a CLEAR result.

  **Known ceiling, and how to push past it:** three independent local experiments (bigger model, added regularization/augmentation, 5x more training data) each held out a good validation accuracy but failed a direct sanity check against fresh genuine specimens -- consistent evidence that this model's size and CPU-only local training, not any single tunable, is the actual constraint. [`notebooks/BorderMesh_Tamper_CNN_Colab.ipynb`](notebooks/BorderMesh_Tamper_CNN_Colab.ipynb) is a GPU-based Colab notebook (open it directly at `https://colab.research.google.com/github/<your-fork>/SyntaxSquad/blob/main/notebooks/BorderMesh_Tamper_CNN_Colab.ipynb`) that trains a proper transfer-learning model (MobileNetV3-Small) on a real GPU, blending in [IDNet](https://arxiv.org/abs/2408.01690) (CC0-licensed, ~837k synthetic ID document images with fraud ground truth) alongside CASIA and this project's own generator -- reusing the exact domain-balanced sampling and sanity-check discipline from the local experiments so a checkpoint isn't trusted on validation accuracy alone.

### Module 4 — Biometric Face Verification
- **Portrait Extraction:** Isolates face crop from travel document.
- **Live Subject Capture:** Integrates live webcam frame or photo upload.
- **Detection & Embedding:** MTCNN face detection + InceptionResnetV1 (pretrained on VGGFace2, via `facenet-pytorch`) — a genuine 512-dimensional L2-normalized deep face embedding, not a hand-rolled network.
- **Cosine Similarity:** Computes biometric match score against a **0.72 verification threshold** (`MATCH` vs `REVIEW REQUIRED`), calibrated against the standard **LFW face-verification benchmark** (500 genuine + 500 impostor pairs): **98.0% accuracy, 0.6% false-accept rate, 3.4% false-reject rate**. Re-run the calibration yourself with `scripts/calibrate_face_threshold.py`.
- **Quality & Anti-Spoofing:** Evaluates image sharpness (Laplacian variance), brightness/exposure, and liveness texture scores.

---

## 4. Central Risk Intelligence Layer

The Risk Engine synthesizes all forensic signals into an explainable 0–100 score:

| Factor | Default Weight | Key Signals Evaluated |
| :--- | :---: | :--- |
| **MRZ & Rules Validation** | **25%** | Check digit checksums, expiration status, field cross-checks |
| **Forensic Tamper AI** | **30%** | ELA compression anomalies, edge splicing, photo seams |
| **Face Verification** | **30%** | Biometric cosine distance, quality and liveness score |
| **Data Consistency** | **10%** | Cross-field visual vs MRZ mismatches |
| **Watchlist Adapter** | **5%** | Simulated sandbox alert list hit |

### Risk Tiers & Recommendations
- **0 – 24 (LOW):** `CLEAR FOR ENTRY — Routine processing permitted`
- **25 – 49 (MEDIUM):** `ROUTINE VERIFICATION — Officer visual confirmation recommended`
- **50 – 74 (HIGH):** `SECONDARY INSPECTION — Multiple document risk indicators detected`
- **75 – 100 (CRITICAL):** `SUPERVISOR ESCALATION — Significant anomalies requiring physical review`

### Critical-Signal Floor
A weighted average alone can let a definitive rule violation — an expired document, a watchlist hit, a high-confidence forgery finding — get diluted by unrelated clean signals (a clean face match doesn't make an expired passport valid for travel). Any `CRITICAL`-severity signal floors the outcome at **HIGH** regardless of the weighted score; the response includes `critical_floor_applied` so this is auditable, not silent.

### Face-Identity-Mismatch Floor
The converse gap existed until a live test surfaced it: pairing a GENUINE, untampered document with a live capture of a different real person produced a correctly-flagged `REVIEW_REQUIRED` (similarity below the 72% 1:1 threshold), but the overall case could still total as little as ~18–23/100 — LOW RISK, "CLEAR FOR ENTRY" — because `REVIEW_REQUIRED`'s raw-risk floor of 60 at the face module's 30% weight contributes only 18 points, and a clean, untampered document supplies no other signal to escalate it. A clean document doesn't make an unverified identity acceptable, the same way a clean face match doesn't make an expired passport valid. Any `REVIEW_REQUIRED` 1:1 face verdict (document-vs-live-capture, calibrated at 98.0% accuracy / 0.60% false-accept rate on LFW — not the cross-case 1:N gallery match, which deliberately stays uncapped due to its own measured 26% false-accept rate at gallery scale) now floors the outcome at **HIGH** the same way a `CRITICAL` signal does; the response includes `face_mismatch_floor_applied`. `NO_FACE_DETECTED`/`MULTIPLE_FACES` are left out of this floor — their raw-risk value of 85 already clears LOW on its own, and unlike `REVIEW_REQUIRED` they aren't necessarily an affirmative mismatch finding (could be a capture/quality failure instead).

---

## 5. Technology Stack

- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, Recharts, Lucide Icons
- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0
- **Database:** PostgreSQL 16 (with automatic zero-friction SQLite fallback for instant local execution)
- **Forensics & ML:** PyTorch 2.x, `facenet-pytorch` (MTCNN + InceptionResnetV1/VGGFace2), OpenCV 4.x, Pillow, PyTesseract, Scikit-Learn, SciPy
- **DevOps:** Docker, Docker Compose, Nginx

---

## 6. Project Directory Structure

```text
border-mesh/
├── .github/workflows/ci.yml            # Backend pytest + frontend vitest/lint/build on every push/PR
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI application entrypoint & lifespan
│   │   ├── core/                       # Config, database fallback, security hashing
│   │   ├── models/                     # SQLAlchemy models (Case, DocumentAnalysis, RiskSignal, AuditLog)
│   │   ├── schemas/                    # Pydantic schemas for requests and responses
│   │   ├── services/                   # Business logic (OCR, MRZ, Rules, Tamper, Face, Risk, Watchlist, Audit)
│   │   ├── ml/                         # PyTorch CNN tamper classifier & Face Embedder
│   │   ├── utils/                      # Synthetic passport generator & image processing
│   │   └── api/routes/                 # REST endpoints (auth, cases, screening, dashboard, demo, health)
│   ├── tests/                          # 288 automated unit & integration tests (100% pass rate)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/                 # RiskScore, MRZValidator, TamperHeatmap, FaceVerification, etc.
│   │   ├── pages/                      # Dashboard, Screening, CaseDetail, ReviewQueue, Analytics, Audit, Settings,
│   │   │                               # Compliance (DPDP Act 2023), ChangeDetection, WelcomePage, Privacy/Terms
│   │   ├── services/api.ts             # Typed REST client
│   │   ├── types/index.ts              # TypeScript interfaces
│   │   ├── App.tsx                     # Master layout and tab router (operations dashboard)
│   │   └── main.tsx                    # Resolves /welcome, /privacy, /terms vs the dashboard app by path
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json                    # 67 automated component/unit tests (vitest, 100% pass rate)
├── demo-data/
│   ├── samples/                        # Pre-generated synthetic test specimen images
│   └── faces/                          # AI-generated (StyleGAN2) demo portraits -- not real people
├── docs/
│   └── PRIVACY_POLICY.md               # Also reachable in-app at /privacy
├── notebooks/
│   └── BorderMesh_Tamper_CNN_Colab.ipynb # GPU transfer-learning notebook for the tamper CNN (see Module 3)
├── scripts/
│   ├── seed_cases.py                   # Seeds 20 realistic synthetic cases into DB
│   ├── generate_demo_docs.py           # Generates offline test specimens
│   ├── calibrate_face_threshold.py     # Calibrates the face-match threshold against the LFW benchmark
│   ├── generate_tamper_training_data.py # Synthetic splice-forgery dataset generator for the tamper CNN
│   └── train_tamper_cnn.py             # Trains the tamper CNN; run once, then restart the backend
├── docker-compose.yml                  # Complete stack (Postgres + Backend + Frontend)
├── .env.example
├── KNOWN_LIMITATIONS.md                # What this system doesn't do well, with real numbers -- read this
└── README.md
```

---

## 7. Quick Start & Local Development

### Option A: Docker Compose (Recommended — just works)

The full stack (PostgreSQL, FastAPI backend, Nginx-served frontend) runs from one command, with the face-verification model's pretrained weights baked into the image at build time — no local Python setup, no manual dependency wrangling:

```bash
docker compose up --build
```

Access:
- **Frontend Dashboard:** `http://localhost:5173`
- **Backend Swagger Docs:** `http://localhost:8000/docs`

The first build downloads ~107MB of pretrained face-embedding weights (needs internet once, during the build); the container runs fully offline after that. The database auto-seeds 20 synthetic demo cases **and one demo officer account** on first boot: badge ID `OFFICER-DEMO-01`, password from `DEFAULT_OFFICER_PASSWORD` (see `.env.example`) — log in with these at the dashboard's login screen before anything else works (see section 10B).

---

### Option B: Local Run (for active development)

#### 0. Prerequisite: install Tesseract OCR

Unlike Option A, this path doesn't run inside a container that already has
`tesseract-ocr` installed -- you need it on your own machine, on your PATH:

```bash
# macOS
brew install tesseract

# Debian/Ubuntu
sudo apt-get install tesseract-ocr

# Windows
# Install from https://github.com/UB-Mannheim/tesseract/wiki, then either add
# its install directory to PATH or set TESSERACT_PATH in .env to the full
# path of tesseract.exe.
```

#### 1. Backend Setup
```bash
# In project root
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# facenet-pytorch (face verification) is installed separately: its declared
# version pins are years stale and conflict with the modern stack above, even
# though its actual code runs fine against them. --no-deps skips those pins;
# requests/tqdm (its own lightweight deps) are already in requirements.txt.
pip install --no-deps facenet-pytorch>=2.6.0

# Run database seed (auto-creates SQLite if PostgreSQL is not active)
PYTHONPATH=backend python scripts/seed_cases.py

# Start FastAPI server on port 8000
PYTHONPATH=backend uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```

The first time face verification runs, it downloads ~107MB of pretrained VGGFace2 weights (needs internet once; cached under `~/.cache/torch` afterward).

> **macOS + python.org Python note:** if that download fails with `CERTIFICATE_VERIFY_FAILED`, your Python install is missing its CA bundle (a known python.org installer issue, unrelated to this project). Fix it once with either:
> ```bash
> # Run the certificate installer that ships with python.org Python:
> "/Applications/Python 3.12/Install Certificates.command"
> # Or point at the certifi bundle already in your venv for this run:
> export SSL_CERT_FILE=$(python3 -c "import certifi; print(certifi.where())")
> ```
> This isn't needed on Linux/Docker — Debian's system CA bundle just works.

#### 2. Frontend Setup (in a separate terminal)
```bash
cd frontend
npm install
npm run dev
```

Open your browser at **`http://localhost:5173`**.

---

## 8. Running Automated Tests

To execute the automated unit and integration tests across MRZ checksum algorithms, rules engine, tamper detection, risk calculation, and REST endpoints:

```bash
PYTHONPATH=backend ./venv/bin/pytest backend/tests -v
```

All 288 backend tests pass with 100% success rate across core logic, ML signals, and security APIs (plus 67 frontend component/unit tests via `npm test` in `frontend/`, also 100% passing — React Testing Library + Vitest). `test_api.py` uses `TestClient` as a context manager so the app's startup lifespan (table creation + seeding) actually runs — a bare `TestClient(app)` silently skips it.

> Both suites run automatically on every push/PR via GitHub Actions (`.github/workflows/ci.yml`) — backend pytest, frontend vitest, `oxlint`, and a full `tsc -b && vite build`. A red CI run means the suite actually failed on that commit, not that nobody happened to run it locally.

> **Platform note:** `test_api.py::test_demo_scenario_execution` asserts the "genuine" demo scenario scores LOW. The specimen image's exact pixels (and therefore the tamper CNN's score) depend on which font PIL falls back to for text rendering, which differs between macOS (Helvetica) and the Linux container (DejaVu, installed in `backend/Dockerfile`) -- this can occasionally push the score to the MEDIUM/LOW boundary locally on macOS even though it is reliably LOW in the actual deployment target. Docker is the authoritative environment for this test; run it there (`docker compose exec backend python3 -m pytest tests/test_api.py -v` from `backend/`) for a result that matches production.

**API & integration** (`test_api.py`) — health, dashboard stats, case listing, demo scenario execution, officer decisions, SHA-256 blockchain ledger verification, GDPR Art. 17 biometric purge, policy settings (weights/thresholds validated both at the API layer and, independently, inside the service function itself so a future caller can't bypass it), CORS configuration (an arbitrary origin must not be reflected back), and that the face-verification API reports the same match threshold it actually used to decide MATCH vs REVIEW_REQUIRED.

**Authentication** (`test_auth.py`) — the real login/session flow end-to-end against an unmocked dependency (not the overridden one `test_api.py` uses for every other test): login with the seeded demo officer, rejection of a wrong password and an unknown badge ID with the same error either way, a protected route rejecting a missing/garbage token, a real issued token authenticating a protected route, and the `/uploads` route accepting the session token as either an `Authorization` header or a `?token=` query parameter.

**MRZ** (`test_mrz.py`) — 7-3-1 check digit algorithm, TD3 parsing, tamper detection, and the filler-run reconstruction fix that recovers correct checksums from under-counted OCR output.

**Face verification** (`test_face_verifier.py`) — embedding shape/normalization, determinism, graceful handling of missing embeddings and empty crops, detection fallback. (The 98.0% LFW-benchmark accuracy figure comes from `scripts/calibrate_face_threshold.py`, run separately since it downloads ~475MB of benchmark data — not part of this fast suite.)

**Risk engine** (`test_risk_engine.py`) — low-risk aggregation, critical tampering + watchlist combination, and the critical-signal floor (an isolated CRITICAL validation signal, and a CRITICAL tamper verdict, must each floor the outcome to at least HIGH regardless of otherwise-clean signals).

**Rules engine** (`test_rules.py`) — genuine/expired/mismatched document rule evaluation.

**Tamper service** (`test_tamper_service.py`) — the score-aggregation formula weights the trained CNN and each heuristic signal by their own confidence rather than flat amounts.

**Watchlist** (`test_watchlist.py`) — exact matches, and bounded fuzzy tolerance (max 1 character edit) so a single OCR misread doesn't hide a real match.

---

## 9. SIH Demonstration Scenarios (1-Click Judging)

Use the top toolbar **"Demo scenario"** selector to demonstrate predefined test cases. Each generates a fresh synthetic document, runs the full pipeline, and shows real (not scripted) module output — verified end-to-end against a clean Docker rebuild:

1. **Genuine Document:** Real photo, valid checksums, matching live face $\rightarrow$ `LOW RISK — CLEAR FOR ENTRY` (face similarity ~0.99 MATCH, no tamper signals).
2. **MRZ Tampering:** Intentionally corrupted check digits in line 2 $\rightarrow$ `HIGH RISK — SECONDARY INSPECTION` (checksum-invalid CRITICAL signal floors the score regardless of a clean face/tamper result).
3. **Photo Replacement:** Document photo is Person A, live capture is Person B — a genuine biometric mismatch, not a scripted one $\rightarrow$ `HIGH RISK — SECONDARY INSPECTION` (face similarity ~0.61 REVIEW_REQUIRED, plus a real edge-discontinuity splice signal).
4. **Expired Document:** Travel validity expired before present calendar date $\rightarrow$ `HIGH RISK — SECONDARY INSPECTION` (an expired document is a CRITICAL, deterministic rule violation, floored to HIGH regardless of how clean the biometric/tamper signals are).
5. **Multiple Anomalies:** Tampered MRZ + mismatched face + simulated watchlist hit $\rightarrow$ `HIGH RISK — SECONDARY INSPECTION`.
6. **Watchlist Evasion Attempt:** Every signal looks clean — valid MRZ, matching face, no tamper — except the traveler's name and document number are each a single character off from a real watchlist entry $\rightarrow$ `HIGH RISK — SECONDARY INSPECTION`. Demonstrates the bounded fuzzy-matching fix: an exact-match-only watchlist check would have missed this entirely and cleared the traveler as LOW risk.
7. **PAN Card Verification:** Non-MRZ document type, Income Tax Dept. issuer markers, PAN structure/entity-type validation $\rightarrow$ `LOW RISK — CLEAR FOR ENTRY`.
8. **Driving Licence — Expired:** Non-MRZ document, expired validity $\rightarrow$ `HIGH RISK — SECONDARY INSPECTION`.
9. **Voter ID (EPIC) Verification:** Non-MRZ document $\rightarrow$ `LOW RISK — CLEAR FOR ENTRY`.
10. **Travel Visa — Stay Duration Expired:** $\rightarrow$ `HIGH RISK — SECONDARY INSPECTION`.
11. **Residence Permit — Expired:** $\rightarrow$ `HIGH RISK — SECONDARY INSPECTION`.
12. **Duplicate Identity Detection:** A document with an entirely different, individually-clean claimed identity (different name, different document number) whose live face matches a *prior* screening's live face via the cross-case embedding gallery $\rightarrow$ `MEDIUM RISK — ROUTINE VERIFICATION`. Every signal on this document alone is clean; only the 1:N gallery lookup catches it — a real capability most hackathon demos skip because it requires persisting embeddings across cases, not just within one.

A 13th flow, **Same-Identity Change Detection** (toolbar: "Change Detection"), is structurally different from the twelve above — it doesn't score a single document, it generates two submissions for one claimed identity and reports exactly which fields (DOB, expiry, portrait photo) differ between them, catching a resubmission whose MRZ checksum alone validates perfectly.

Manual "New Screening" uploads can use the same specimens directly: `demo-data/samples/specimen_*.jpg` paired with `sample_live_face.jpg` (matching person, for a MATCH result) or `sample_live_face_mismatch.jpg` (different person, for a REVIEW_REQUIRED result).

---

## 10. Blockchain & Cybersecurity Theme Alignment

The project is built specifically under the **Blockchain & Cybersecurity** theme of SIH 2026:

### A. Cryptographic Chain-of-Custody (Blockchain-Style Ledger)
- **SHA-256 Chained Blocks:** Every screening event (Document Upload, OCR, MRZ Validation, Tamper AI, Face Verification, Risk Aggregation, Officer Determination, Biometric Purge) generates a cryptographically signed block with `entry_hash` linked to `previous_hash` (Genesis hash `0`*64).
- **Mathematical Immutability:** Any retroactive modification to officer notes, AI scores, or case timestamps immediately breaks the hash chain, triggering instant tamper alerts.
- **On-Demand Ledger Verification:** Officers and auditors can click *"Verify Blockchain Chain"* or query `/api/audit/verify` to perform full-ledger mathematical proofs of non-repudiation.

### B. Cybersecurity & Privacy-by-Design
- **Identifier Hashing:** Document numbers are stored as SHA-256 hashes (`document_number_hash`) in query indices, preventing citizen PII leakage.
- **Encryption at Rest for Biometric Artifacts:** Every document scan, live face capture, extracted face crop, tamper-analysis heatmap, and cross-case face embedding under `UPLOAD_DIR`/the `face_embedding_gallery` table is Fernet-encrypted (AES-128-CBC + HMAC-SHA256, authenticated) before it ever touches disk (`backend/app/core/encryption.py`) — plaintext exists only transiently, in memory or in a temp file deleted immediately after the OCR/tamper/face pipeline step that needed it. The old `/uploads` static file mount was replaced with a route that decrypts and streams on request, so nothing plaintext is ever served or stored.

  **Honest scope of this, for anyone evaluating it as a security control:** `BIOMETRIC_ENCRYPTION_KEY` is a real Fernet key read from an environment variable (`backend/app/core/config.py`), not a literal baked into the encryption logic — but it is **not** production-grade key management. One static key for the whole deployment, no key rotation, no envelope encryption or per-record data keys, no HSM/KMS integration. The key ships with a working default so the app runs out of the box for a demo; any real deployment must override it via its own env var. This is the same "real, but not production-hardened" posture as `SECRET_KEY`/`ANCHOR_PRIVATE_KEY` elsewhere in this config, made explicit here because biometric data is the highest-sensitivity thing this app touches.
- **GDPR Article 17 Biometric Purge Scrubber:** Dedicated protocol permanently scrubs raw passport scans, webcam selfies, and facial crops from disk while preserving the anonymized case ID and cryptographic ledger signature.
- **Multi-Signal Forensics:** Dual-domain ELA and Laplacian edge discontinuity detection prevents digital impersonation.
- **Sandboxed Watchlists:** Air-gapped in-memory mock database prevents accidental leaks or live government queries.

  **Real per-officer authentication:** every route — not just case deletion and biometric purge — requires a logged-in `Officer` (`POST /api/auth/login`, bcrypt-hashed password, JWT session, see `backend/app/api/deps.py`'s `get_current_officer`). Audit-trail entries (`CASE_VIEWED`, `DOCUMENT_UPLOADED`, `OFFICER_DECISION_RECORDED`, etc.) record the real authenticated officer's badge ID, not a hardcoded string. One demo account (`OFFICER-DEMO-01`) is auto-seeded on first boot from `DEFAULT_OFFICER_PASSWORD` — same "real default so the app runs out of the box" tradeoff as `SECRET_KEY`/`BIOMETRIC_ENCRYPTION_KEY` above.

  **Honest scope of this, stated with the same bar as the encryption-key caveat above:** this is single-tenant demo identity, not a production auth system — one seeded account, no self-registration or admin UI, no role-based access control (every officer can do everything), no password reset/MFA/lockout, and no server-side session revocation (a token is valid until its 12-hour expiry, full stop). The decrypt-and-stream `/uploads` route also accepts the session token as a `?token=` query parameter (not just an `Authorization` header), since an `<img src="...">` tag can't attach custom headers — a real, if minor, exposure (query strings can land in access logs) that a hardened deployment would close with short-lived signed URLs instead. See [`KNOWN_LIMITATIONS.md` §6](KNOWN_LIMITATIONS.md#6-per-officer-authentication-exists-now-but-with-real-stated-limits) for the full list. **Do not deploy this against real traveler data without adding real identity-provider integration and RBAC first.**

---

## 11. Performance Benchmarks

Every case's audit trail timestamps each pipeline step, so these numbers are computed from real `AuditLog` deltas across actually-processed cases (`GET /api/dashboard/stats`, `latency_breakdown` — see `backend/app/api/routes/dashboard.py`), not hardcoded estimates. They'll shift slightly as more cases run; this is a representative snapshot, reproducible by hitting that endpoint yourself.

| Operation | Measured Latency | Samples |
| :--- | :---: | :---: |
| OCR Text & Field Extraction | ~980 ms | n=109 |
| MRZ Checksum Verification | ~165 ms | n=109 |
| Tamper AI (ELA + CNN) | ~50 ms | n=109 |
| Biometric Face Verification | ~550 ms | n=109 |
| Risk Score Aggregation | ~11 ms | n=109 |
| **Total Staged Pipeline (avg, wall-clock)** | **~2.0 seconds** *(Well within 5.0s SIH target)* | |

The named-step sum (~1.76s) runs a bit under the measured wall-clock average (~2.0s) — the gap is real overhead outside any single named step (image I/O, database writes, network) that the per-module breakdown doesn't attribute to one module.

---

## 12. Authors & License

Developed for **Smart India Hackathon 2026** by the BorderMesh Engineering Team.  
Distributed under the MIT License for academic and demonstration evaluation.
