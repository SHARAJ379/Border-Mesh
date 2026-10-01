import hashlib
import json
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from typing import Optional, Dict, Any, List

from app.models import AuditLog, Case, BlockchainAnchor

GENESIS_HASH = "0" * 64

class AuditService:
    @staticmethod
    def canonical_json(data: Optional[Dict[str, Any]]) -> str:
        """Serializes dictionary deterministically for cryptographic hashing."""
        if not data:
            return "{}"
        return json.dumps(data, sort_keys=True, separators=(',', ':'), default=str)

    @staticmethod
    def compute_hash(
        previous_hash: str,
        case_id: Optional[str],
        action: str,
        actor: str,
        timestamp_str: str,
        metadata_str: str
    ) -> str:
        """Computes SHA-256 block hash for the audit ledger."""
        payload = f"{previous_hash}|{case_id or 'SYSTEM'}|{action}|{actor}|{timestamp_str}|{metadata_str}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def log(
        cls,
        db: Session,
        action: str,
        case_id: Optional[str] = None,
        actor: str = "OFFICER-DEMO-01",
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Appends a cryptographically chained, immutable audit log entry."""
        meta = metadata or {}
        now = datetime.utcnow()
        now_iso = now.isoformat()
        meta_str = cls.canonical_json(meta)

        # Get previous block hash from latest entry in chain
        latest_entry = db.query(AuditLog).order_by(desc(AuditLog.timestamp), desc(AuditLog.id)).first()
        prev_hash = latest_entry.entry_hash if (latest_entry and latest_entry.entry_hash) else GENESIS_HASH

        entry_hash = cls.compute_hash(
            previous_hash=prev_hash,
            case_id=case_id,
            action=action,
            actor=actor,
            timestamp_str=now_iso,
            metadata_str=meta_str
        )

        entry = AuditLog(
            case_id=case_id,
            action=action,
            actor=actor,
            timestamp=now,
            metadata_json=meta,
            previous_hash=prev_hash,
            entry_hash=entry_hash
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @classmethod
    def verify_chain(cls, db: Session, case_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Cryptographically verifies the SHA-256 chain-of-custody across the audit ledger.
        Proves mathematical immutability and flags any tampered records.

        The linkage walk always covers the FULL, unfiltered ledger in true
        insertion order -- a hash chain's forward links only hold across the
        real sequence entries were appended in (see `log`'s single global
        `latest_entry` lookup), and a single case's own audit entries are
        interleaved with every other case's, so a case-filtered subsequence
        has no independent chain of its own to check: entry N's stored
        previous_hash points at whatever the previous GLOBAL entry was, not
        at case-filtered entry N-1. When `case_id` is given, the walk still
        runs over the whole ledger (that's the only way a break anywhere can
        be detected at all), but `total_records`/`head_hash` are reported
        scoped to that case for display.
        """
        all_logs = db.query(AuditLog).order_by(asc(AuditLog.timestamp), asc(AuditLog.id)).all()
        case_logs = [l for l in all_logs if l.case_id == case_id] if case_id else all_logs

        if not case_logs:
            return {
                "valid": True,
                "total_records": 0,
                "head_hash": GENESIS_HASH,
                "genesis_hash": GENESIS_HASH,
                "verified_at": datetime.utcnow(),
                "compromised_id": None,
                "reason": "Ledger is empty (0 blocks)."
            }

        # Verify chain integrity. Two independent checks per block, since
        # either alone is insufficient: (1) the block's own entry_hash must
        # match a fresh hash of its own stored fields (catches a block
        # edited without re-signing it at all), and (2) the block's stored
        # previous_hash must equal the ACTUAL previous block's entry_hash in
        # this ordered sequence -- not just whatever previous_hash happens to
        # be stored on the block itself (catches a block whose content was
        # edited and then re-signed in isolation, which trivially passes
        # check (1) against its own unchanged previous_hash field but breaks
        # the real link to its predecessor).
        expected_prev_hash = GENESIS_HASH
        for i, log in enumerate(all_logs):
            if (log.previous_hash or GENESIS_HASH) != expected_prev_hash:
                return {
                    "valid": False,
                    "total_records": len(case_logs),
                    "head_hash": case_logs[-1].entry_hash,
                    "genesis_hash": GENESIS_HASH,
                    "verified_at": datetime.utcnow(),
                    "compromised_id": log.id,
                    "reason": f"Chain linkage broken at block #{i+1} (Action: {log.action}, Actor: {log.actor}): stored previous_hash does not match the preceding block's actual hash."
                }

            meta_str = cls.canonical_json(log.metadata_json)
            ts_str = log.timestamp.isoformat() if isinstance(log.timestamp, datetime) else str(log.timestamp)

            expected_hash = cls.compute_hash(
                previous_hash=log.previous_hash or GENESIS_HASH,
                case_id=log.case_id,
                action=log.action,
                actor=log.actor,
                timestamp_str=ts_str,
                metadata_str=meta_str
            )

            # Check hash match. A missing entry_hash must FAIL this check,
            # not skip it -- `log.entry_hash and ...` previously let a block
            # with a null/empty hash pass silently, the opposite of the
            # "either alone is insufficient" design this function states
            # above. AuditService.log() always computes a real hash before
            # insert, so this path isn't reachable through the application's
            # own writer today, but the verification itself should not rely
            # on that as its only guarantee.
            if not log.entry_hash or log.entry_hash != expected_hash:
                return {
                    "valid": False,
                    "total_records": len(case_logs),
                    "head_hash": case_logs[-1].entry_hash,
                    "genesis_hash": GENESIS_HASH,
                    "verified_at": datetime.utcnow(),
                    "compromised_id": log.id,
                    "reason": f"Hash signature mismatch at block #{i+1} (Action: {log.action}, Actor: {log.actor})."
                }

            expected_prev_hash = log.entry_hash or GENESIS_HASH

        return {
            "valid": True,
            "total_records": len(case_logs),
            "head_hash": case_logs[-1].entry_hash or GENESIS_HASH,
            "genesis_hash": GENESIS_HASH,
            "verified_at": datetime.utcnow(),
            "compromised_id": None,
            "reason": f"All {len(all_logs)} blocks cryptographically verified intact via SHA-256 chaining."
        }

    @classmethod
    def get_case_anchor_proof(cls, db: Session, case_number: str) -> Dict[str, Any]:
        """
        Determines whether a case's audit trail is covered by a public
        blockchain anchor -- keyed by the case's human-facing case_number
        (e.g. "BM-2026-A1B2C"), not the internal UUID, since that's what
        would actually be handed to someone to verify independently.

        A BlockchainAnchor's total_records_at_anchor is the GLOBAL audit
        ledger's entry count at anchor time (see api/routes/audit.py's
        anchor_audit_chain). Since the ledger is one single hash chain
        across every case (see verify_chain's docstring), a case's audit
        trail is cryptographically committed to by any anchor whose
        total_records_at_anchor is at or after that case's own last
        entry's position in the GLOBAL ordered ledger -- the chaining
        property means the anchor's on-chain hash recursively embeds every
        earlier entry's hash, this case's included.

        Deliberately returns nothing beyond proof-of-anchoring: this backs
        a public, unauthenticated endpoint, and must never leak the case's
        risk score, name, document number, or any other case field.
        """
        case = db.query(Case).filter(Case.case_number == case_number).first()
        if not case:
            return {
                "case_number": case_number,
                "case_found": False,
                "chain_valid": False,
                "anchored": False,
                "anchor": None,
                "message": f"No case found with number '{case_number}'."
            }

        verification = cls.verify_chain(db, case_id=case.id)
        if verification["total_records"] == 0:
            return {
                "case_number": case_number,
                "case_found": True,
                "chain_valid": verification["valid"],
                "anchored": False,
                "anchor": None,
                "message": "This case has no audit trail yet."
            }

        if not verification["valid"]:
            return {
                "case_number": case_number,
                "case_found": True,
                "chain_valid": False,
                "anchored": False,
                "anchor": None,
                "message": "This case's audit chain failed cryptographic verification. Do not trust any prior anchor for this case."
            }

        all_logs = db.query(AuditLog).order_by(asc(AuditLog.timestamp), asc(AuditLog.id)).all()
        case_positions = [i for i, log in enumerate(all_logs, start=1) if log.case_id == case.id]
        last_position = case_positions[-1]

        covering_anchor = (
            db.query(BlockchainAnchor)
            .filter(BlockchainAnchor.total_records_at_anchor >= last_position)
            .order_by(asc(BlockchainAnchor.created_at))
            .first()
        )

        if covering_anchor:
            return {
                "case_number": case_number,
                "case_found": True,
                "chain_valid": True,
                "anchored": True,
                "anchor": covering_anchor,
                "message": f"This case's audit trail is anchored on {covering_anchor.network}. Verify independently at the link below."
            }

        return {
            "case_number": case_number,
            "case_found": True,
            "chain_valid": True,
            "anchored": False,
            "anchor": None,
            "message": "This case's audit trail exists and is cryptographically valid, but has not yet been anchored to a public blockchain."
        }
