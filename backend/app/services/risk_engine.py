from datetime import date
from typing import Dict, Any, List, Optional, Tuple
from app.core.config import settings
from app.services.rules_engine import DocumentRulesEngine
from app.services.risk_types import RiskCheckStatus, RiskFactorKey, make_check, make_evidence

# Heuristic used to discount face-match confidence when the document photo
# was very likely taken long enough ago (or the holder was a minor when it
# was taken) that ordinary facial aging -- not tampering or a genuine
# mismatch -- could plausibly account for a lower similarity score. The MRZ
# only carries DOB and expiry (no issue date), so the document's issue date
# is ESTIMATED from expiry minus the standard ICAO validity period for the
# holder's age bracket. This is a transparent business rule, not a measured
# calibration -- there is no ground-truth cross-age dataset behind these
# thresholds yet (see scripts/finetune_face_embedder.py for that effort in
# progress). Revisit these numbers once real accuracy data exists.
ADULT_PASSPORT_VALIDITY_YEARS = 10
MINOR_PASSPORT_VALIDITY_YEARS = 5
MINOR_AGE_CUTOFF_YEARS = 18

# Children's faces change disproportionately faster per year than adults'
# (well-established in cross-age face-recognition research, e.g. the FG-NET
# dataset this project is fine-tuning against) -- so a photo taken while the
# holder was a minor is weighted as if the elapsed time were longer.
MINOR_AT_ISSUE_GAP_MULTIPLIER = 1.6

AGE_GAP_MODERATE_YEARS = 4.0
AGE_GAP_HIGH_YEARS = 8.0
FACE_WEIGHT_DISCOUNT_MODERATE = 0.75  # 25% weight reduction
FACE_WEIGHT_DISCOUNT_HIGH = 0.50      # 50% weight reduction


def _years_between(earlier: date, later: date) -> float:
    return (later - earlier).days / 365.25


def estimate_face_age_gap(mrz_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Estimates how long ago the document's photo was likely captured, using
    only MRZ DOB + expiry (no issue date is machine-readable). Returns None
    when there isn't enough valid MRZ date data to estimate anything --
    callers must not penalize face-match confidence on missing/unparseable
    dates, only on a genuine, computed large gap.
    """
    if not mrz_data:
        return None
    dob_date = DocumentRulesEngine.parse_yymmdd(mrz_data.get("birth_date", ""))
    expiry_date = DocumentRulesEngine.parse_yymmdd(mrz_data.get("expiry_date", ""))
    if not dob_date or not expiry_date:
        return None

    age_at_expiry_years = _years_between(dob_date, expiry_date)
    validity_years = (
        MINOR_PASSPORT_VALIDITY_YEARS if age_at_expiry_years < MINOR_AGE_CUTOFF_YEARS
        else ADULT_PASSPORT_VALIDITY_YEARS
    )
    try:
        estimated_issue_date = expiry_date.replace(year=expiry_date.year - validity_years)
    except ValueError:
        # Feb 29 on a non-leap estimated issue year.
        estimated_issue_date = expiry_date.replace(year=expiry_date.year - validity_years, day=28)

    photo_age_years = max(0.0, _years_between(estimated_issue_date, date.today()))
    age_at_issue_years = _years_between(dob_date, estimated_issue_date)
    was_minor_at_issue = age_at_issue_years < MINOR_AGE_CUTOFF_YEARS

    effective_gap_years = photo_age_years * (
        MINOR_AT_ISSUE_GAP_MULTIPLIER if was_minor_at_issue else 1.0
    )

    return {
        "photo_age_years": round(photo_age_years, 1),
        "effective_gap_years": round(effective_gap_years, 1),
        "was_minor_at_issue": was_minor_at_issue,
        "estimated_issue_date": estimated_issue_date,
    }


def face_weight_discount_for_gap(effective_gap_years: float) -> Tuple[float, Optional[str]]:
    """Returns (multiplier, tier_label). tier_label is None when no discount applies."""
    if effective_gap_years >= AGE_GAP_HIGH_YEARS:
        return FACE_WEIGHT_DISCOUNT_HIGH, "HIGH"
    if effective_gap_years >= AGE_GAP_MODERATE_YEARS:
        return FACE_WEIGHT_DISCOUNT_MODERATE, "MODERATE"
    return 1.0, None


class RiskEngine:
    """
    Central Risk Intelligence Layer.
    Aggregates multi-factor forensic signals into an explainable 0-100 risk score.
    Outputs factor breakdown, an itemized list of every risk CHECK run (pass,
    fail, or non-blocking note -- see app.services.risk_types), risk tier,
    and human-in-the-loop recommendations.
    """

    def __init__(self, policy=None):
        """
        `policy` is an optional PolicySettings row (see policy_service.py) --
        the live, officer-editable weights/thresholds from the Settings page.
        Falls back to the static app.core.config defaults when omitted (e.g.
        existing tests that construct RiskEngine() directly).
        """
        self.w_mrz = policy.weight_mrz if policy else settings.WEIGHT_MRZ
        self.w_tamper = policy.weight_tamper if policy else settings.WEIGHT_TAMPER
        self.w_face = policy.weight_face if policy else settings.WEIGHT_FACE
        self.w_consistency = policy.weight_consistency if policy else settings.WEIGHT_CONSISTENCY
        self.w_watchlist = policy.weight_watchlist if policy else settings.WEIGHT_WATCHLIST
        self.threshold_low = policy.threshold_low if policy else settings.THRESHOLD_LOW
        self.threshold_medium = policy.threshold_medium if policy else settings.THRESHOLD_MEDIUM
        self.threshold_high = policy.threshold_high if policy else settings.THRESHOLD_HIGH

    def calculate(
        self,
        mrz_data: Optional[Dict[str, Any]],
        validation_data: Dict[str, Any],
        tamper_data: Dict[str, Any],
        face_data: Optional[Dict[str, Any]],
        watchlist_match: Optional[Dict[str, Any]],
        duplicate_identity_match: Optional[Dict[str, Any]] = None,
        duplicate_identity_checked: bool = False,
    ) -> Dict[str, Any]:
        all_checks: List[Dict[str, Any]] = []

        # --- 1. MRZ & Document Validation Factor (25%) + Consistency (10%) ---
        #
        # Both factors are fed by the SAME rules_engine.evaluate() output,
        # but each check contributes to exactly ONE of them, chosen by its
        # own `factor` tag -- rules_engine tags the visual-vs-MRZ document-
        # number crosscheck as CONSISTENCY (a genuine cross-source
        # agreement check) and every other rule (checksums, expiration,
        # format, presence) as MRZ_VALIDATION. This replaces a previous bug
        # where the SAME failed rule counted twice: once via its own
        # score_impact summed into MRZ_VALIDATION, and AGAIN via a blunt
        # `failed_count * 30` formula that re-penalized every validation
        # failure a second time under Consistency, regardless of whether it
        # was actually a cross-source inconsistency. A failed check must
        # only ever move the score once.
        validation_checks = validation_data.get("checks", []) if validation_data else []
        all_checks.extend(validation_checks)

        mrz_checks = [c for c in validation_checks if c.get("factor") == RiskFactorKey.MRZ_VALIDATION]
        consistency_checks = [c for c in validation_checks if c.get("factor") == RiskFactorKey.CONSISTENCY]

        mrz_raw_risk = min(100.0, sum(c["score_impact"] for c in mrz_checks))
        mrz_contrib = round(mrz_raw_risk * self.w_mrz, 1)

        consistency_raw_risk = min(100.0, sum(c["score_impact"] for c in consistency_checks))
        consistency_contrib = round(consistency_raw_risk * self.w_consistency, 1)

        # --- 2. Tamper Analysis Factor (30%) ---
        #
        # tamper_service.py now builds its own fully-shaped checks (severity
        # escalation against the document-level CRITICAL verdict already
        # applied there) -- risk_engine just aggregates them. raw_risk keeps
        # its own bespoke, already-calibrated formula (ELA + trained-CNN
        # probability + heuristic signals, see TamperDetectionService.
        # _aggregate_tamper_score) rather than summing check score_impacts:
        # those remain a display/evidence-list number, same as before.
        tamper_checks = tamper_data.get("checks", []) if tamper_data else []
        all_checks.extend(tamper_checks)
        tamper_raw_risk = min(100.0, (tamper_data.get("tamper_risk", 0.1) if tamper_data else 0.1) * 100.0)
        tamper_contrib = round(tamper_raw_risk * self.w_tamper, 1)

        # --- 3. Face Verification Factor (30%) ---
        face_raw_risk = 0.0
        face_weight = self.w_face
        if face_data:
            similarity = face_data.get("similarity", 1.0)
            status = face_data.get("status", "MATCH")

            if status == "MATCH":
                face_raw_risk = max(0.0, (1.0 - similarity) * 40.0)
            elif status == "REVIEW_REQUIRED":
                face_raw_risk = max(60.0, (1.0 - similarity) * 100.0)
            elif status in ["NO_FACE_DETECTED", "MULTIPLE_FACES"]:
                face_raw_risk = 85.0

            all_checks.extend(face_data.get("checks", []))

            # Discount the face module's weight when the MRZ DOB (combined
            # with expiry, since issue date isn't machine-readable) implies
            # the document photo is likely old enough -- or was taken young
            # enough -- that ordinary facial aging plausibly explains a
            # lower similarity score, distinct from tampering or a genuine
            # identity mismatch. Only ever discounts risk (never amplifies
            # it) and only fires on a REAL computed gap, never on missing
            # MRZ data -- see estimate_face_age_gap's None-on-insufficient-
            # data contract.
            #
            # Restricted to status == "MATCH": the aging rationale only
            # supports softening a borderline SIMILARITY SCORE. It must
            # never fire on REVIEW_REQUIRED/NO_FACE_DETECTED/MULTIPLE_FACES
            # -- those are the module's own affirmative mismatch/no-face
            # verdicts, not aging uncertainty, and discounting them would
            # soften the exact signal that caught a genuine impersonation
            # on an old-but-unaltered document.
            age_gap = estimate_face_age_gap(mrz_data) if status == "MATCH" else None
            if age_gap:
                discount, tier = face_weight_discount_for_gap(age_gap["effective_gap_years"])
                if tier:
                    face_weight = round(self.w_face * discount, 4)
                    minor_note = " (holder was a minor when the document was likely issued)" if age_gap["was_minor_at_issue"] else ""
                    all_checks.append(make_check(
                        id=f"FACE_AGE_GAP_DISCOUNT_{tier}", category="FACE", factor=RiskFactorKey.FACE,
                        label=f"Age-Gap-Adjusted Face Confidence ({tier})", status=RiskCheckStatus.INFO,
                        confidence=0.7,
                        explanation=(
                            f"Face similarity lower-confidence due to an estimated "
                            f"{age_gap['photo_age_years']:.0f}-year gap since likely document "
                            f"photo capture{minor_note}. Face verification's weight in the "
                            f"composite risk score was reduced from {self.w_face:.2f} to "
                            f"{face_weight:.2f} to avoid over-penalizing a plausible aging "
                            f"effect rather than tampering or a genuine mismatch. Estimated "
                            f"issue date is not authoritative -- derived from MRZ expiry minus "
                            f"standard ICAO validity, since issue date isn't MRZ-readable."
                        ),
                        evidence=make_evidence(
                            measured_value=age_gap["photo_age_years"], threshold_value=AGE_GAP_MODERATE_YEARS,
                            unit="estimated_photo_age_years",
                        ),
                    ))
        else:
            # Face verification pending or not performed yet
            face_raw_risk = 15.0

        face_raw_risk = min(100.0, face_raw_risk)
        face_contrib = round(face_raw_risk * face_weight, 1)

        # --- 4. Simulated Watchlist Adapter (5%) ---
        watchlist_raw_risk = 0.0
        if watchlist_match:
            watchlist_raw_risk = 100.0
            entry = watchlist_match["entry"]
            match_evidence = watchlist_match.get("match_evidence")
            all_checks.append(make_check(
                id="WATCHLIST_SCREENING", category="WATCHLIST", factor=RiskFactorKey.WATCHLIST,
                label=f"Demo Watchlist Hit: {entry['category']}", status=RiskCheckStatus.FAIL,
                severity=entry.get("severity", "CRITICAL"), confidence=0.99,
                explanation=f"[SIMULATED DATA] {watchlist_match['explanation']} Requires officer identity review.",
                evidence=make_evidence(match=match_evidence) if match_evidence else None,
                score_impact=25.0,
            ))
        else:
            all_checks.append(make_check(
                id="WATCHLIST_SCREENING", category="WATCHLIST", factor=RiskFactorKey.WATCHLIST,
                label="Watchlist Screening", status=RiskCheckStatus.PASS, confidence=0.9,
                explanation="No match found against active simulated watchlist records "
                            "(document number or full name).",
            ))
        watchlist_contrib = round(watchlist_raw_risk * self.w_watchlist, 1)

        # --- 5. Cross-Case Duplicate Identity Check (HIGH signal, flat unweighted add) ---
        #
        # A gallery hit (see identity_gallery_service.py) means this
        # screening's live face is the CLOSEST match (at or above
        # GALLERY_MATCH_THRESHOLD) among every OTHER case's stored live
        # embedding -- a real corroborating identity signal, but NOT the
        # near-certain rule violation CRITICAL severity implies here (an
        # expired document, a watchlist hit). scripts/evaluate_gallery_scale_far.py
        # measured the REAL 1:N behavior at gallery scale (1,200 distinct
        # identities, not the 500 1:1 pairs the threshold was originally
        # picked from): at GALLERY_MATCH_THRESHOLD=0.80, empirical 1:N
        # false-accept rate was 26.0% -- roughly 1 in 4 genuinely innocent
        # travelers, at this gallery size, would score a "match" against
        # SOME other unrelated person purely from gallery-size compounding.
        # So this is HIGH severity, not CRITICAL, added as a flat,
        # unweighted addition to the total rather than a new weighted
        # factor (no PolicySettings migration tooling for a 6th weight).
        if duplicate_identity_match:
            matched_case_number = duplicate_identity_match["case_number"]
            similarity = duplicate_identity_match.get("similarity", 0.0)
            duplicate_identity_score_impact = 30.0
            all_checks.append(make_check(
                id="IDENTITY_DUPLICATE_GALLERY_MATCH", category="IDENTITY", factor=RiskFactorKey.IDENTITY,
                label=f"Possible Duplicate Identity: matches Case {matched_case_number}",
                status=RiskCheckStatus.FAIL, severity="HIGH", confidence=round(similarity, 2),
                explanation=(
                    f"This individual's live facial biometric is the closest gallery match to a "
                    f"PREVIOUS screening (Case {matched_case_number}), filed under a different "
                    f"name or document number. Similarity: {round(similarity * 100, 1)}%. "
                    f"A 1:N gallery match at this threshold has a measured ~26% false-accept "
                    f"rate at gallery scale (see scripts/evaluate_gallery_scale_far.py) -- treat "
                    f"as a corroborating lead requiring officer identity review, not confirmed fraud."
                ),
                evidence=make_evidence(measured_value=round(similarity, 3), threshold_value=0.80, unit="cosine_similarity"),
                score_impact=duplicate_identity_score_impact,
            ))
        else:
            duplicate_identity_score_impact = 0.0
            if duplicate_identity_checked:
                all_checks.append(make_check(
                    id="IDENTITY_DUPLICATE_GALLERY_MATCH", category="IDENTITY", factor=RiskFactorKey.IDENTITY,
                    label="Cross-Case Duplicate Identity Screening", status=RiskCheckStatus.PASS, confidence=0.9,
                    explanation="No cross-case duplicate-identity match found among prior screenings' live "
                                "facial embeddings.",
                ))

        # Total Aggregated Score (0 to 100)
        total_risk = round(
            mrz_contrib + tamper_contrib + face_contrib + consistency_contrib
            + watchlist_contrib + duplicate_identity_score_impact,
            1
        )
        total_risk = max(0.0, min(100.0, total_risk))
        pre_floor_total = total_risk

        # Deterministic hard-stop override: a CRITICAL-severity signal (e.g. an
        # expired document, a watchlist hit) is a definitive rule violation, not
        # a probabilistic risk that unrelated clean signals should be able to
        # dilute -- a clean face match doesn't make an expired passport valid
        # for travel. Floor the score so it can never classify below HIGH when
        # any such signal is present.
        critical_floor_applied = False
        if any(c.get("severity") == "CRITICAL" for c in all_checks) and total_risk <= self.threshold_medium:
            total_risk = self.threshold_medium + 0.1
            critical_floor_applied = True

        # Same hard-stop reasoning, for the converse case: a REVIEW_REQUIRED
        # face verdict is the 1:1 face module's own affirmative finding that
        # the live subject is NOT the person in the document photo -- not a
        # probabilistic/corroborating signal the way the cross-case 1:N
        # gallery match is (that one stays an uncapped, non-flooring HIGH
        # contribution on purpose -- see IdentityGalleryService's own
        # disclosure of its measured 26% false-accept rate at gallery scale).
        # This is the system's single most direct anti-impersonation check,
        # calibrated against the LFW 1:1 benchmark at 98.0% accuracy / 0.60%
        # false-accept rate (face_service.py), and REVIEW_REQUIRED's raw-risk
        # floor of 60 (set deliberately low to avoid over-penalizing a
        # borderline similarity score) combined with the 30% face weight
        # could previously total as little as 18 points -- below
        # threshold_low, so a confirmed biometric mismatch against an
        # otherwise-clean, UNTAMPERED document (e.g. someone presenting
        # another person's genuine passport) could classify LOW RISK / "CLEAR
        # FOR ENTRY". A clean document doesn't make an unverified identity
        # acceptable, same as a clean face match doesn't make an expired
        # passport valid. NO_FACE_DETECTED/MULTIPLE_FACES aren't included
        # here: their raw-risk floor of 85 already clears threshold_low on
        # its own, and unlike REVIEW_REQUIRED they aren't necessarily an
        # affirmative mismatch finding (could just be a capture/quality
        # failure), so they're left to the ordinary weighted score instead of
        # a hard floor.
        face_mismatch_floor_applied = False
        if face_data and face_data.get("status") == "REVIEW_REQUIRED" and total_risk <= self.threshold_medium:
            total_risk = self.threshold_medium + 0.1
            face_mismatch_floor_applied = True

        # Risk Tier Classification
        if total_risk <= self.threshold_low:
            risk_level = "LOW"
            recommendation = "CLEAR FOR ENTRY — Routine processing permitted"
        elif total_risk <= self.threshold_medium:
            risk_level = "MEDIUM"
            recommendation = "ROUTINE VERIFICATION — Officer visual confirmation recommended"
        elif total_risk <= self.threshold_high:
            risk_level = "HIGH"
            recommendation = "SECONDARY INSPECTION — Multiple document risk indicators detected"
        else:
            risk_level = "CRITICAL"
            recommendation = "SUPERVISOR ESCALATION — Significant anomalies requiring physical document review"

        breakdown = [
            {
                "factor": "MRZ & Document Validation",
                "weight": self.w_mrz,
                "raw_risk": round(mrz_raw_risk, 1),
                "weighted_contribution": mrz_contrib,
            },
            {
                "factor": "Forensic Tamper AI",
                "weight": self.w_tamper,
                "raw_risk": round(tamper_raw_risk, 1),
                "weighted_contribution": tamper_contrib,
            },
            {
                "factor": "Biometric Face Verification",
                "weight": face_weight,
                "raw_risk": round(face_raw_risk, 1),
                "weighted_contribution": face_contrib,
            },
            {
                "factor": "Data Consistency Crosscheck",
                "weight": self.w_consistency,
                "raw_risk": round(consistency_raw_risk, 1),
                "weighted_contribution": consistency_contrib,
            },
            {
                "factor": "Simulated Watchlist Adapter",
                "weight": self.w_watchlist,
                "raw_risk": round(watchlist_raw_risk, 1),
                "weighted_contribution": watchlist_contrib,
            }
        ]

        # Same "Explainable" reconciliation requirement as the critical-floor
        # entry below: the duplicate-identity match is a flat, unweighted
        # addition (see the comment at its point of computation above), so it
        # needs its own breakdown line for the same reason the floor override
        # does -- otherwise the 5 named categories would sum to less than the
        # displayed total with no line item accounting for the difference.
        if duplicate_identity_match:
            breakdown.append({
                "factor": "Cross-Case Duplicate Identity",
                "weight": None,
                "raw_risk": None,
                "weighted_contribution": duplicate_identity_score_impact,
            })

        # Makes the hard-stop override (above) visible as its own line, not
        # just an invisible jump between the weighted categories' sum and the
        # displayed total.
        if critical_floor_applied:
            breakdown.append({
                "factor": "Critical Signal Floor",
                "weight": None,
                "raw_risk": None,
                "weighted_contribution": round(total_risk - pre_floor_total, 1),
            })
        elif face_mismatch_floor_applied:
            # Same reconciliation purpose as the Critical Signal Floor line
            # above, kept as its own distinct, honestly-labeled entry rather
            # than folded into that one -- an officer reading the breakdown
            # should see this floored because of a confirmed face mismatch,
            # not an expired document or a watchlist hit.
            breakdown.append({
                "factor": "Face Identity Mismatch Floor",
                "weight": None,
                "raw_risk": None,
                "weighted_contribution": round(total_risk - pre_floor_total, 1),
            })

        return {
            "risk_score": total_risk,
            "risk_level": risk_level,
            "recommendation": recommendation,
            "critical_floor_applied": critical_floor_applied,
            "face_mismatch_floor_applied": face_mismatch_floor_applied,
            "breakdown": breakdown,
            "checks": all_checks,
        }

def get_risk_engine(policy=None) -> RiskEngine:
    return RiskEngine(policy=policy)
