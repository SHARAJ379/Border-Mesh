# Known Limitations — Private Q&A Prep Reference

**This is not pitch-deck material.** It exists so that if a judge asks a hard
question about this system, the answer given is the precise, correct one —
not something improvised on the spot. Every number below was either measured
live against real data (and in several cases re-verified again while writing
this document) or is a plain structural fact about what was and wasn't built.
Nothing here is hedged or softened for effect.

If asked "why isn't this fixed," the honest answer for almost everything below
is the same shape: real, held-out evaluation happened late enough in the build
that fixing the finding well would have meant re-architecting or re-training
close to judging, with a real risk of making things worse under time pressure.
Where that's true, it's stated per item rather than repeated as a blanket
excuse.

---

## 1. Tamper detection accuracy on real forgeries

**The number:** measured directly against CASIA v2.0 (real, human-made photo
splices — 24,944 patches: 14,982 authentic, 9,962 tampered), the committed
tamper-forensics CNN scores:

| Metric | Value |
|---|---|
| Accuracy | **71.2%** |
| Recall (tampered patches actually caught) | **39.5%** (TP=3,930, FN=6,032) |
| Precision | 77.2% |
| F1 | 52.2% |
| False-accept rate (authentic flagged as tampered) | 7.8% |
| False-reject rate (tampered missed entirely) | 60.6% |

Independently re-run while preparing this document; matches exactly
(71.155% / 39.450%). Read plainly: **60.6% of real, human-made splices slip
through as "authentic."** This is a genuinely weak recall number, not a
rounding-down of something respectable.

Context that matters: the README separately quotes an 87.8% figure, which is
the model's own *training-validation* accuracy on synthetic splices — a
different, easier, in-distribution test. The 71.2%/39.5% CASIA numbers are the
honest out-of-distribution measurement and are what should be quoted if asked
about real-world accuracy, not the 87.8% figure.

**Why it wasn't retrained close to judging:** it was tried — twice, by two
different theories of the root cause, both of which failed and were reverted.
The committed checkpoint is intentionally unchanged (CASIA-only, trained on
this project's own synthetic splices plus CASIA photo-splice data — not
SIDTD).

*Attempt 1 (undersized model):* a real forgery dataset (SIDTD — real ID
document forgeries, not just generic photo splices like CASIA) was integrated
into the training pipeline specifically to close this gap. Across four
training runs, every SIDTD-blended checkpoint reliably produced a **confident
false positive on the project's own genuine demo specimens** — and it wasn't
random noise, it was isolated specifically to the portrait/photo region. The
suspected root cause: this project's own synthetic document generator pastes
the face photo onto the document with a plain, hard-edged rectangular
`img.paste()` — which is structurally the same signature as a real
crop-and-replace forgery. SIDTD's real portrait-tampering examples taught the
CNN to recognize exactly that signature, so it started flagging the project's
own genuine specimens as tampered. That's a legitimate, independently-found
bug (since fixed — the generator now feathers the paste edge), but it
surfaced days before judging, and the tiny 25k-parameter CNN was suspected too
small to absorb SIDTD's narrow portrait-tampering examples without overfitting
new spurious correlations elsewhere.

*Attempt 2 (bigger model, to test that theory directly):* a ~250k-parameter,
4-conv-layer version of the CNN was trained on the same SIDTD-blended data,
with a corrected (and now-committed) `_split_files` train/test split so the
held-out numbers would be genuinely unseen data for once. Held-out accuracy on
CASIA/SIDTD themselves did get genuinely better (SIDTD recall roughly
32%→89%), confirming capacity was part of the story — but the bigger model's
own sanity check (fresh genuine specimens from this project's own generator)
still scored a confident 0.94 mean tamper-risk, no better than attempt 1's
failures. **Model capacity was not the actual root cause.** The model, at
either size, keeps learning real-photograph sensor/compression statistics
(CASIA and SIDTD are both camera photos) that conflict with this project's
clean, noise-free synthetic document renders — a domain-mismatch problem, not
a capacity problem. This attempt was also reverted; the committed checkpoint
and architecture are unchanged from before either attempt. Don't re-attempt a
bigger model as the fix without addressing the domain mismatch directly (e.g.
photographing/degrading the project's own synthetic specimens before
training, not just reweighting domain sampling or scaling the model — both
already tried). The `_split_files`-based held-out split infrastructure in
`scripts/generate_tamper_training_data.py` is kept and now used by both
`scripts/evaluate_tamper_on_casia.py --split test` and the new
`scripts/evaluate_tamper_on_sidtd.py`, for whenever a future attempt happens.

**A second, independent out-of-distribution number, measured for the first
time while writing this update:** the committed checkpoint — trained on
synthetic splices + CASIA only, never on SIDTD in any form — was run against
the full SIDTD document-forgery set (11,332 patches: 6,444 authentic, 4,888
tampered) via the new `scripts/evaluate_tamper_on_sidtd.py`:

| Metric | Value |
|---|---|
| Accuracy | **60.0%** |
| Recall (tampered patches actually caught) | **32.0%** (TP=1,562, FN=3,326) |
| Precision | 56.5% |
| F1 | 40.8% |
| False-accept rate (authentic flagged as tampered) | 18.7% |
| False-reject rate (tampered missed entirely) | 68.0% |

Read plainly: against real document forgeries specifically (as opposed to
CASIA's generic photo splices), the committed model does worse on every axis
— recall drops from 39.5% to 32.0%, and the false-accept rate more than
doubles (7.8%→18.7%). This is consistent with, not contradicted by, attempt
2's 89% recall figure above: that number came from a differently-trained,
differently-sized, since-reverted checkpoint, not the one actually shipped.

**If asked directly:** "71% accuracy, 40% recall on real photo splices (CASIA);
60% accuracy, 32% recall on real document forgeries specifically (SIDTD),
measured honestly and both out-of-distribution for the committed model. We
tried twice to close the gap with real document-forgery training data — first
suspecting the model was too small, then confirming a bigger model wasn't the
fix either — and both attempts produced a confident false positive on our own
genuine specimens, so both were reverted rather than shipped under time
pressure. The actual blocker is a domain mismatch between real camera photos
and our clean synthetic renders, not model size, and fixing that properly
needs more than a retrain."

---

## 2. No cryptographic chip/PKD verification

There is no ePassport chip read (BAC/PACE, no Passive Authentication against
ICAO PKD-issued document signer certificates) anywhere in this system. Every
"validity" check is: OCR the printed MRZ, recompute its check digits, compare.

**What that actually proves:** the printed characters are internally
consistent with each other (the check digits weren't mistyped/OCR-garbled and
still add up). **What it does not prove:** that the document was issued by a
real authority, that the chip (if one exists) matches the printed data, or
that the physical document isn't a well-made counterfeit with a
checksum-valid MRZ printed on it. A sufficiently competent forger can compute
a valid MRZ checksum by hand; this system has no way to tell that document
apart from a genuine one.

**If asked directly:** "MRZ checksum validation proves the printed text is
internally consistent — it's a plausibility check, not an authenticity proof.
Real document authentication needs chip-level PKD verification, which is out
of scope here: it requires accredited certificate access this project has no
path to."

---

## 3. Watchlist is entirely fictional

The "watchlist" is `MockWatchlistProvider.DEMO_WATCHLIST` — **exactly 3
hardcoded fictional entries** (`WL-SIM-2026-081/094/103`), each explicitly
labeled `(Simulated)` in its category and reason text, with the whole provider
labeled `DEMO WATCHLIST — SIMULATED DATA — NOT CONNECTED TO GOVERNMENT
SYSTEMS`. It is an in-memory Python list. There is no real backing of any
kind — no INTERPOL, no national database, no live data source, not even a
large synthetic dataset standing in for one.

The fuzzy/phonetic name-matching logic layered on top of it (edit-distance,
Soundex, Metaphone) is real and genuinely tested — but it's real matching
logic running against 3 fictional names. There is no accuracy number for
watchlist matching at any realistic scale, because no benchmark of that scale
exists in this project.

**If asked directly:** "The watchlist is 3 fictional demo entries, clearly
labeled as simulated everywhere it surfaces. What's real is the fuzzy-matching
logic around it; what's fictional is everything it's matching against. A real
deployment would need to integrate with an actual watchlist data source,
which this project doesn't attempt."

---

## 4. Liveness heuristic: real but narrow, and non-certified

The FFT-based liveness signal (`FaceDetectorAndVerifier.
analyze_frequency_artifacts`) measures, honestly:

| Test condition | Result |
|---|---|
| Recall on synthetic **moire**-pattern overlay (n=800, real LFW crops) | **98.5%** |
| Recall on synthetic **halftone**-pattern overlay (n=800, same crops) | **41.9%** |
| False-positive rate on clean, unaltered real face crops | 5.4% |

Moire (screen-replay) detection is strong; halftone (print) detection catches
well under half. This is disclosed in the code itself, not just here.

**Explicitly non-certified:** this has never been tested against a real
screen-replay or print-and-rescan attack — only a self-generated synthetic
proxy (real face photos with a synthetic periodic pattern overlaid in
software), because this project has no real spoof-attempt captures. No
ISO/IEC 30107-3 conformant Presentation Attack Detection (PAD) testing has
been done. It is wired in as a LOW-severity, non-blocking signal for exactly
this reason — it informs an officer, it never gates a decision on its own.

**If asked directly:** "It's a real, measured heuristic — strong against
screen-replay patterns, weak against print/halftone patterns, and explicitly
not certified PAD. It's advisory only, by design, because it hasn't been
validated against anything but a synthetic proxy."

---

## 5. Face matching is unmodified stock VGGFace2

**Production face matching today is the original, untouched
facenet-pytorch InceptionResnetV1 pretrained on VGGFace2** — 98.0% LFW
same-age accuracy, 0.60% false-accept rate, 3.40% false-reject rate at the
0.72 match threshold. No fine-tuning of any kind is active.

**Five fine-tuning attempts were made, all measured, none promoted to
production — the fourth and fifth are the closest yet, and neither is a
win:**

| | Baseline (production) | Attempt 1: FG-NET only | Attempt 2: FG-NET + CALFW | Attempt 3: FG-NET + CALFW, ArcFace loss | Attempt 4: + CelebA + WebFace4M sample, ArcFace | Attempt 5: full CelebA + 4x WebFace4M sample, ArcFace (partial) |
|---|---|---|---|---|---|---|
| Training data | — (stock pretrained) | 82 identities, cross-age only | FG-NET + CALFW combined | same as attempt 2 | FG-NET + CALFW + CelebA (6 shards) + WebFace4M (6-shard/~211k-image sample), 221,516 images, 52,978 identities | FG-NET + CALFW + CelebA (all 19 shards) + WebFace4M (24-shard/~843k-image sample), ~1.26M images |
| Objective | — | softmax classification | softmax classification | ArcFace additive angular margin | same as attempt 3 | same as attempt 3/4 |
| Images/identity (avg) | — | — | ~3.2 | ~3.2 | ~4.2 (CelebA alone: ~21; WebFace4M alone: ~4.6) | similar ratio, ~4.6x attempt 4's volume |
| Epochs completed | — | — | — | — | 8/8 (full) | **4/5 — OOM-killed by the OS before the 5th**, see below |
| LFW same-age accuracy | **98.0%** | 86.7% (best threshold) | 52.1% (best threshold — near coin-flip) | 83.5% (best threshold) | 96.7% (best threshold) | **96.4%** (best threshold) |
| False-accept rate | **0.60%** | 10.20% (~17× worse) | 93.4% (essentially broken) | 9.40% (~16× worse) | 3.00% (5× worse) | **2.40%** (4× worse) |
| False-reject rate | **3.40%** | — | — | 23.6% | 3.60% | **4.80%** |
| Outcome | shipped | wired in briefly, then reverted | never promoted past candidate | never promoted past candidate | clears the project's literal ≥95% gate; NOT shipped anyway (see below) | same as attempt 4 — clears ≥95%, NOT shipped |

All right-hand numbers were independently re-run while preparing this
document, against the actual preserved checkpoint files, not taken on faith.

- **Attempt 1 (FG-NET only):** unfroze only the embedder's last block, trained
  on 82 cross-age identities. Improved cross-age matching but, with no
  same-age diversity in training, overfit and stopped reliably telling
  different people apart in the ordinary (non-cross-age) case — a ~17× jump
  in false accepts. It was briefly live, recalibrated to threshold 0.70,
  caught in evaluation, and reverted. The checkpoint is kept on disk
  (renamed so it's no longer auto-loaded) purely for reproducibility.
- **Attempt 2 (FG-NET + CALFW):** the intended fix for attempt 1's narrowness
  — CALFW added real same-age diversity FG-NET alone lacked. The result was
  worse, not better: at its best achievable threshold, genuine and impostor
  pairs became nearly indistinguishable (mean similarity 0.983 vs. 0.971),
  collapsing accuracy to barely better than chance. It was never wired into
  the app even briefly — caught at the candidate-checkpoint evaluation gate
  this project's own policy requires before promotion.
- **Attempt 3 (FG-NET + CALFW, ArcFace loss):** same data as attempt 2, a
  different hypothesis — that attempt 1/2's plain softmax classification
  head was the root cause (optimizing closed-set classification accuracy on
  training identities, not the open-set cosine-similarity structure
  verification actually needs), not data volume. Replaced it with ArcFace
  (additive angular margin loss, Deng et al. 2019), which trains the
  embedding directly against the same cosine-similarity scoring
  `face_verifier.py` uses at inference. Result: still a regression (98.0% →
  83.5% at best threshold, 9.40% false-accept), on the same order as attempt
  1, not the catastrophic collapse of attempt 2, but not a fix either. The
  hypothesis was only partly right — changing the objective avoided the
  total collapse, but didn't close the gap. The more likely dominant factor:
  13,175 images across 4,106 identities is ~3.2 images per identity on
  average, a thin margin for learning a robust metric under *any* objective.
  Checkpoint kept on disk as `face_embedder_finetuned_arcface.pth`
  (deliberately not the auto-loaded filename) for reproducibility.

- **Attempt 4 (FG-NET + CALFW + CelebA + WebFace4M sample, ArcFace):** tested
  the hypothesis attempt 3 left open directly — that per-identity thinness
  (~3.2 images/identity), not the loss function, was the dominant cause of
  attempts 1-3's failures. Added two real, properly-licensed datasets with
  real depth: CelebA (flwrlabs/celeba, official research-release-agreement
  license, ~21 images/identity) and a 6-shard (~211k-image) sample of the
  official WebFace4M subset of WebFace42M (gaunernst/webface4m-wds-gz,
  non-commercial-research license) — not the full 42M-image corpus, which
  would be a multi-day multi-GPU undertaking, not something run here.
  Explicitly excluded LFW (would contaminate the evaluation benchmark every
  number on this page is measured against), WIDER FACE (face-detection-only,
  zero identity labels — confirmed, not assumed), FairFace (single image per
  sample, no identity grouping — confirmed, not assumed), and MS-Celeb-1M
  (withdrawn by Microsoft in 2019 after non-consensual scraping was exposed,
  documented use by surveillance vendors in human-rights-abuse contexts —
  not used regardless of mirror availability). Result: 96.7% accuracy, 3.00%
  false-accept at best threshold — by far the closest any attempt has come,
  and the first to clear the project's own stated ≥95% candidate-promotion
  bar. **Not shipped anyway.** That bar was written as a regression floor
  against catastrophic failures (52%, 86.7%), not as "ship anything above
  95% even when the thing already in production is better" — and the stock
  model is still better on every metric, including a 5× lower false-accept
  rate, the specific failure mode (matching two different people as the same
  person) that matters most for a border-security tool. Clearing the literal
  number isn't the same as this being an improvement; it confirms the
  per-identity-depth hypothesis was right without actually fixing the
  product. Checkpoint kept on disk as `face_embedder_finetuned_bigdata.pth`
  for reproducibility.
- **Attempt 5 (full CelebA + 4x WebFace4M sample, ArcFace, partial):** scaled
  attempt 4 up further -- all 19 CelebA shards instead of 6, 24 WebFace4M
  shards instead of 6 (~1.26M images total, ~4.6x attempt 4's volume) -- to
  test whether the per-identity-depth lever had more room to run. It didn't,
  clearly: 96.4% accuracy, 2.40% false-accept at 4/5 epochs (the run was
  OOM-killed by the OS before the 5th epoch could complete on this 15.2GB-RAM
  machine -- see below). That's statistically a wash against attempt 4's
  96.7%/3.00%, not a further improvement, despite 4.6x more data. Confirms
  diminishing returns on the "more data, same approach" lever specifically,
  independent of the memory ceiling that cut the run short. Checkpoint kept
  on disk as `face_embedder_finetuned_bigdata_v2.pth`.

**Infrastructure note (attempt 5):** two earlier launch attempts at this
scale were OOM-killed almost immediately (one with 24 WebFace4M shards/4
DataLoader workers, one with a reduced 12-shard/1-worker config) -- both
failed at an almost identical ~3.6GB-free ceiling, pointing at persistent
baseline load from other applications already running on the host rather
than this script's own tunables. The third launch (after freeing some
memory) survived the critical allocation phase at under 0.5GB free and
completed 4 epochs before the OS killed it again. Not a face-recognition
finding -- a reminder that this project's training runs are bounded by
whatever else is running on the machine they're executed on, not just by
data/model size.

**Why not keep going on this lever:** five attempts across three different
angles (data breadth, training objective, and now data depth at two scales)
have progressively closed the gap without closing it, and the jump from
attempt 4 to attempt 5's 4.6x-larger dataset produced no further improvement.
The remaining honest options are the same as before: FG-NET + YLFW-Dev-Train-
Balanced (still license-gated, never obtained) or a larger properly-licensed
dataset with even deeper per-identity coverage than CelebA/WebFace4M
provided -- not simply more of the same shape of data. Diminishing, not
exhausted -- but nothing on hand right now has closed the remaining gap.

**If asked directly:** "Face matching is stock, pretrained VGGFace2 — 98%
accuracy on the standard benchmark. We've tried fine-tuning it for better
cross-age matching five times now — different training objectives, then
dramatically more and richer data at two scales — measured every attempt
honestly. The closest attempts got to ~96.5-96.7% accuracy and 2.4-3%
false-accept, still worse than
the 98%/0.6% already shipping, so none of the five were promoted. The
dataset that might actually close the remaining gap is gated behind a
license we don't have."

---

## 6. Per-officer authentication exists now, but with real, stated limits

**Updated 2026-10-01 — this used to say there was no login at all (a single
shared `OFFICER_API_KEY` gated 2 destructive endpoints and nothing else).
That's now built: real `Officer` accounts, bcrypt-hashed passwords, JWT
sessions (`POST /api/auth/login`), and every route in the app — not just the
2 destructive ones — requires a valid session (see
`backend/app/api/deps.py`'s `get_current_officer`). Audit-trail attribution
(`CASE_VIEWED`, `DOCUMENT_UPLOADED`, `OFFICER_DECISION_RECORDED`, etc.) now
records the real logged-in officer's badge ID, not a hardcoded string.**

What's real: password hashing (bcrypt, not reversible), signed/expiring
tokens (JWT, HS256, 12-hour expiry), and a real 401 on every route for a
missing/invalid/expired session — confirmed with real end-to-end tests
(`backend/tests/test_auth.py`), not just unit tests of the dependency.

What's still a real, stated gap, not production-grade identity:

- **No self-registration or officer-management UI.** One demo account
  (`OFFICER-DEMO-01`) is auto-seeded on first boot from
  `DEFAULT_OFFICER_PASSWORD` (same "real default so the demo runs out of the
  box" tradeoff as `SECRET_KEY`/`BIOMETRIC_ENCRYPTION_KEY` — see
  `default_secrets_still_in_use`'s enforcement). Adding more officers today
  means inserting rows directly; there's no admin screen, deliberately —
  that's a real feature to build, not a quick patch.
- **No RBAC.** Every authenticated officer can do everything (view any case,
  delete any case, change policy weights). A real deployment needs roles
  (e.g. an officer who can screen but not delete, a supervisor who can).
- **No password reset, no MFA, no account lockout after failed attempts,
  no audit of failed login attempts themselves.** All standard real-identity-
  system features this doesn't have.
- **The `/uploads` image route accepts the session token as a `?token=`
  query parameter**, not just an `Authorization` header — necessary because
  an `<img src="...">` tag can't attach custom headers, but a query-string
  token can leak into server access logs or a `Referer` header in a way a
  header never would. Mitigated by the 12-hour token expiry, not eliminated.
  A hardened deployment would issue short-lived, single-resource signed URLs
  instead.
- **No session revocation.** A JWT is valid until it expires; there is no
  server-side "log this officer out everywhere" (a stolen token works until
  its 12-hour expiry, full stop).

**If asked directly:** "Per-officer login is real now — not a shared key —
but it's a single-tenant demo identity system: one seeded account, no roles,
no account lifecycle management, no session revocation. A real deployment
needs a real identity provider (SSO/OIDC) and role-based access control on
top of what exists today."

---

## 7. 6 document types, not parity with commercial vendors

Supported document types: **Passport, Aadhaar, PAN, Driving Licence, Voter ID
(EPIC), Travel Visa — 6 total.** Each was hand-built: a synthetic specimen
generator, a dedicated OCR field parser, and (where applicable) dedicated
validation rules. Real commercial identity-verification vendors support
thousands of document templates across 200+ countries and jurisdictions, with
teams dedicated to template ingestion and maintenance as documents change.

This project's 6 types should never be presented as approaching that scope —
they're a deliberately narrow, deep demonstration of the pipeline's
architecture (OCR → validation → tamper → face → risk), not breadth of
document coverage. Adding a 7th type (as Visa was) is a multi-hour task per
type, not a config change.

**If asked directly:** "6 document types, each fully built end-to-end, versus
thousands at real vendors. This demonstrates the pipeline works, not that the
document coverage is commercially complete — that would be a much larger,
ongoing effort."

---

## 8. Permit documents and stamp-forgery detection: scoped, then deprioritized

Both were considered and explicitly not built, for the same underlying
reason each of the 6 shipped document types didn't have: **no single,
concrete real template to build against, and no calibration data to validate
against once built.**

- **Permit documents** (e.g. work/residence permits) don't have one
  consistent real-world layout the way a passport's ICAO 9303 MRZ format
  does, or even the way this project's own fictional Visa specimen has one
  consistent design to be internally consistent against. Every issuing
  jurisdiction's permit looks different, with no common machine-readable
  standard to validate against — building one "generic permit" parser would
  either be so generic it validates nothing meaningful, or would silently
  imply a specific real jurisdiction's format this project has no license or
  reference to actually match.
- **Dedicated stamp-forgery detection** (as opposed to the general tamper CNN,
  which already looks at compression/splice artifacts anywhere in an image,
  stamps included) would need its own labeled training data of genuine vs.
  forged stamps to calibrate a detector against — the same class of problem
  that made the tamper CNN's own real-data attempt (see item 1) risky this
  close to judging, except starting from zero rather than an existing,
  measured baseline.

Both were judged better left out entirely than shipped as a shallow,
unvalidated feature that implies more rigor than it has.

**If asked directly:** "Both were scoped and deliberately cut, not
overlooked. Neither had a real template or real calibration data to build
against in the time available, and we'd rather not ship them than ship
something that looks handled but isn't validated."

---

## 9. Never validated against real-world documents at scale

Every accuracy number in this project's evaluation scripts (tamper CNN vs.
CASIA, MRZ/OCR vs. MIDV-2020) is measured against **real, but clean, source
data** — CASIA's real photographs and human-made splices, or MIDV-2020's
digital template renders. MIDV-2020 in particular has no camera noise, no
lighting/glare/perspective distortion — a genuinely easier case than a real
phone photo of a physical document held at an angle under variable lighting.
Those numbers are explicitly a **lower bound** on real-world error, not an
upper bound.

The only actual real-world-capture testing that happened was ad hoc and
bug-driven: a handful of real Aadhaar card photos surfaced specific OCR
failures (a crashing MRZ extractor, garbled date-of-birth extraction, a page-
segmentation mode that failed on real photographed layouts), which were
fixed. That is evidence real-world input is *harder* than the synthetic/clean
benchmarks suggest — not evidence the system has been validated at any
meaningful scale against it. There is no systematic real-world accuracy
number for this system, for any document type, at any scale.

**If asked directly:** "Every accuracy number we have is against real-but-
clean data or our own synthetic data — never a systematic real-world corpus
at scale. The real-world captures we did test surfaced real bugs, which
tells us the true real-world numbers are likely worse than what's documented,
not better."

---

## 10. No production-scale load testing; gallery validated at ~1,200 entries only

There is no load-testing infrastructure in this project at all — no
concurrency testing, no throughput benchmarking, nothing simulating multiple
simultaneous officers or a production request volume. The "Performance
Benchmarks" table in the README measures per-request pipeline latency
(~2.0s wall-clock for one screening, sequentially) — that is a latency
number, not a load/capacity number, and shouldn't be conflated with one.

The one component that WAS specifically scale-tested is the cross-case
duplicate-identity face gallery, and even that only at a modest, single fixed
scale: a synthetic 1,200-identity gallery (real LFW photographs, not this
project's synthetic actors), which found a real problem — a 1:N false-accept
rate of 26.0% at the threshold that looked clean on a 500-pair 1:1 benchmark.
That finding is exactly why this signal is modeled as a HIGH-severity,
non-overriding contribution rather than an automatic critical floor (see the
risk engine's own documentation). But 1,200 entries is still a demo-scale
gallery, not a national-database scale one — there is no measurement of how
this degrades at 10,000, 100,000, or higher.

**If asked directly:** "No load testing exists — the latency numbers we quote
are single-request pipeline timing, not concurrent capacity. The
duplicate-identity gallery is the one thing we did scale-test, at 1,200
entries, and what we found there (a real false-accept problem) is exactly why
it's modeled cautiously in the risk engine rather than as a hard stop."

---

## 11. Blockchain anchor is Sepolia testnet, not mainnet

The audit-chain anchoring feature writes to **Ethereum Sepolia**, a public
test network (chain ID 11155111), using a throwaway wallet funded via a
public faucet — not Ethereum mainnet or any production chain. This is
appropriate for a prototype and is not being misrepresented as
production-grade: Sepolia transactions are real, publicly verifiable, and
demonstrate the actual mechanism (anchoring a SHA-256 chain-of-custody hash
on a public, immutable ledger), but they carry no real economic finality or
mainnet-level security guarantees, and the feature is entirely optional
(the app works fully with it disabled — it's an on-demand action an officer
explicitly triggers, not something every case depends on).

**If asked directly:** "It's Sepolia testnet, by design — this demonstrates
the real anchoring mechanism without asking anyone to spend real funds or
depend on mainnet for a prototype. Moving to mainnet would be a
straightforward config change, not an architecture change, if this went to
production."

## 12. Case deletion does not repair the audit hash chain

`DELETE /api/cases/{id}` removes that case's `audit_logs` rows outright (via
`ON DELETE CASCADE`) with no chain-repair step, so deleting any case that
already has audit entries permanently breaks `/api/audit/verify` for the
whole ledger from that point forward — the only recovery is truncating
`audit_logs` (and `blockchain_anchors`, whose anchored hashes stop being
verifiable once the chain they anchored is gone), since this app has no
migration tooling to patch the ledger in place.

---

## 13. Positioning against real commercial/border-security products

The gaps below are structural — they exist because of what this prototype's
input and scope are, not because of a tunable that was measured and fell
short. Confirmed against real competitor products' public documentation.

- **No chip/NFC reading or ICAO PKD Passive Authentication** (already #2)
  — real vendors (e.g. Entrust, Regula) read the ePassport chip and
  cryptographically validate it against issuer certificates; this system
  only OCRs the printed MRZ off a photograph, a structurally weaker trust
  model. Entrust's own documentation states NFC scanning "halv[es] the
  turnaround time of verification and return[s] a 95% pass rate on
  successful scans" versus its standard (OCR/photo-based) document check —
  Entrust's number, not independently re-measured here.
- **No multi-spectral forensic imaging.** Real document-forensics hardware
  inspects UV, IR, and oblique/coaxial white light to check holograms,
  optically variable devices, and microprint. This system only ever
  receives a single visible-light photo, so it cannot structurally detect
  any security feature that isn't visible in ordinary light.
- **Liveness heuristic is not ISO/IEC 30107-3 certified** (already #4) —
  Jumio (Level 2) and Veriff (Level 1 and 2) both hold Presentation Attack
  Detection conformance under this standard, independently tested by the
  NIST/NVLAP-accredited iBeta lab; this system's FFT-based signal is an
  uncertified heuristic indicator only, never independently evaluated.
- **Tamper detection targets classical splice/copy-paste forgery only.**
  It does not detect generative-AI or deepfake-manipulated documents.
  AU10TIX's Q1 2026 report (9M+ verification transactions, Jan–Mar 2026)
  states AI-generated identity fraud surpassed physical document forgery
  for the first time on record; Veriff's 2026 fraud report separately found
  document forgery attempts down 13% year-over-year as attackers shifted to
  AI-generated/altered media instead.
- **Watchlist is 3 fictional demo entries** (already #3) — real vendors
  screen against continuously-updated global sanctions/PEP databases,
  refreshed on the order of minutes to hours, at a scale of millions of
  records.
