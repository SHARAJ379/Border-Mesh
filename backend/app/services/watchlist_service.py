from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import re

from sqlalchemy.orm import Session

from app.utils.text_similarity import fuzzy_equal, fuzzy_name_match
from app.models import WatchlistEntry


class WatchlistProvider(ABC):
    @abstractmethod
    def check_watchlist(self, db: Session, full_name: Optional[str], document_number: Optional[str]) -> Optional[Dict[str, Any]]:
        """Queries the watchlist for matching identity records."""
        pass


# Fictional seed data for the demo watchlist table -- see
# scripts/seed_cases.py, which inserts these (idempotently, keyed on
# watchlist_id) the same way it seeds demo cases. Kept here, not in the
# seed script, so this module stays the one place that defines what the
# demo watchlist's content actually is; the seed script just persists it.
DEMO_WATCHLIST_SEED: List[Dict[str, Any]] = [
    {
        "watchlist_id": "WL-SIM-2026-081",
        "name": "VIKTOR KOROL",
        "document_number": "P8892144",
        "category": "Travel Alert (Simulated)",
        "reason": "Simulated stolen passport blank alert in demonstration scenario.",
        "severity": "CRITICAL"
    },
    {
        "watchlist_id": "WL-SIM-2026-094",
        "name": "ELENA ROSTOVA",
        "document_number": "A9938210",
        "category": "Document Revocation (Simulated)",
        "reason": "Simulated administrative document cancellation notice in test catalog.",
        "severity": "HIGH"
    },
    {
        "watchlist_id": "WL-SIM-2026-103",
        "name": "MARCUS VANCE",
        "document_number": "M7744112",
        "category": "Inquiry Flag (Simulated)",
        "reason": "Simulated secondary customs examination request.",
        "severity": "MEDIUM"
    }
]


class DatabaseWatchlistProvider(WatchlistProvider):
    """
    DB-backed Sandbox Watchlist Provider -- queries the watchlist_entries
    table (see app.models.WatchlistEntry) instead of a hardcoded in-process
    Python list, so entries are real, auditable rows rather than something
    only a code change and redeploy could ever update.

    IMPORTANT NOTICE, unchanged from before this became DB-backed:
    SIMULATED DATA — NOT CONNECTED TO GOVERNMENT SYSTEMS OR REAL LAW ENFORCEMENT.
    Every row is fictional, whether seeded by DEMO_WATCHLIST_SEED above or
    added later through this same table. Moving from a Python list to a
    real table changes how the data is stored and managed; it does not,
    and structurally cannot, make it a connection to any actual
    government or law-enforcement watchlist.
    """

    LABEL = "DEMO WATCHLIST — SIMULATED DATA — NOT CONNECTED TO GOVERNMENT SYSTEMS"

    # Watchlist screening is fed by OCR, which is noisy by nature -- a single
    # misread character (e.g. '8' -> 'B', 'O' -> '0') must not be enough to
    # silently hide a real match, since that defeats the entire purpose of
    # this check. Tolerate up to one character edit, but only when the
    # lengths are already close and the string is long enough that a
    # coincidental one-edit collision with an unrelated identity is unlikely.
    FUZZY_MAX_DISTANCE = 1
    FUZZY_MIN_LENGTH = 6

    def check_watchlist(self, db: Session, full_name: Optional[str], document_number: Optional[str]) -> Optional[Dict[str, Any]]:
        clean_doc = re.sub(r'[^A-Za-z0-9]', '', document_number or '').upper()
        clean_name = re.sub(r'[^A-Za-z\s]', '', full_name or '').upper().strip()

        if not clean_doc and not clean_name:
            return None

        # Brute-force scan over active entries, same "premature optimization
        # at this scale" reasoning as identity_gallery_service.py's 1:N
        # gallery search -- a demo/hackathon-sized watchlist table, not a
        # real production-scale one.
        entries = db.query(WatchlistEntry).filter(WatchlistEntry.active == True).all()  # noqa: E712

        for row in entries:
            entry_doc = re.sub(r'[^A-Za-z0-9]', '', row.document_number).upper()
            entry_name = row.name.upper()
            entry_dict = {
                "watchlist_id": row.watchlist_id,
                "name": row.name,
                "document_number": row.document_number,
                "category": row.category,
                "reason": row.reason,
                "severity": row.severity,
            }

            # Check document number match or name match
            if clean_doc and (entry_doc == clean_doc or fuzzy_equal(entry_doc, clean_doc, self.FUZZY_MAX_DISTANCE, self.FUZZY_MIN_LENGTH)):
                return {
                    "matched": True,
                    "provider": self.LABEL,
                    "entry": entry_dict,
                    "match_field": "Document Number",
                    "explanation": f"Document ID matched simulated test record {row.watchlist_id} ({row.category})."
                }

            # Name matching uses phonetic (Soundex/Metaphone) + per-token edit
            # distance -- see fuzzy_name_match -- rather than a whole-string
            # comparison, because genuine name variants (transliteration,
            # spelling variants like 'Mohammed'/'Muhammad') commonly differ
            # by more than the single-OCR-slip edit-distance budget used for
            # document numbers, and can differ in more than one token at once.
            if clean_name:
                token_matches = fuzzy_name_match(entry_name, clean_name)
                if token_matches:
                    return {
                        "matched": True,
                        "provider": self.LABEL,
                        "entry": entry_dict,
                        "match_field": "Full Name",
                        "explanation": f"Identity matched simulated test record {row.watchlist_id} ({row.category}).",
                        # Per-token match evidence (method/tokens/edit distance)
                        # -- lets an officer see WHY this matched, not just
                        # that it did, and judge a phonetic/fuzzy hit on its
                        # own merits instead of a bare true/false.
                        "match_evidence": token_matches,
                    }

        return None


def ensure_seeded(db: Session) -> None:
    """
    Idempotently upserts DEMO_WATCHLIST_SEED into watchlist_entries by
    watchlist_id -- unlike scripts/seed_cases.py (which only runs once,
    gated on the cases table being completely empty), this runs on every
    startup so the demo watchlist always has its canonical entries
    regardless of how many real screenings have accumulated. Safe to call
    repeatedly: an existing row (matched by watchlist_id) is left alone,
    never duplicated or overwritten.
    """
    existing_ids = {row.watchlist_id for row in db.query(WatchlistEntry.watchlist_id).all()}
    for seed in DEMO_WATCHLIST_SEED:
        if seed["watchlist_id"] in existing_ids:
            continue
        db.add(WatchlistEntry(
            watchlist_id=seed["watchlist_id"],
            name=seed["name"],
            document_number=seed["document_number"],
            category=seed["category"],
            reason=seed["reason"],
            severity=seed["severity"],
            active=True,
        ))
    db.commit()


def get_watchlist_provider() -> WatchlistProvider:
    return DatabaseWatchlistProvider()
