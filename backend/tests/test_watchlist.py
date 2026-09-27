from app.core.database import Base, SessionLocal, engine
from app.services.watchlist_service import DatabaseWatchlistProvider, ensure_seeded

# Other test modules (test_api.py) create tables via the app's lifespan,
# entered through TestClient as a context manager -- this module talks to
# the DB directly via SessionLocal with no app/lifespan involved, so the
# watchlist_entries table (and the canonical demo rows) need creating/
# seeding explicitly, the same way test_identity_gallery_service.py does
# for face_embedding_gallery. Both calls are idempotent.
Base.metadata.create_all(bind=engine)
db = SessionLocal()
ensure_seeded(db)
db.close()

provider = DatabaseWatchlistProvider()


def _check(full_name=None, document_number=None):
    db = SessionLocal()
    try:
        return provider.check_watchlist(db, full_name, document_number)
    finally:
        db.close()


def test_exact_match_still_works():
    """Baseline: exact document number match must keep working."""
    result = _check(full_name="VIKTOR KOROL", document_number="P8892144")
    assert result is not None
    assert result["match_field"] == "Document Number"


def test_document_number_survives_single_ocr_digit_confusion():
    """
    Reproduces a real screening gap: OCR on a genuinely watchlisted document
    misreads one character in the document number (e.g. '8' -> 'B', a common
    Tesseract confusion). The old exact-string check silently misses this --
    the core purpose of the watchlist check is to catch flagged identities
    fed by a noisy OCR pipeline, so a single-character OCR slip should not be
    enough to hide a real match.
    """
    result = _check(full_name=None, document_number="P8B92144")
    assert result is not None
    assert result["entry"]["watchlist_id"] == "WL-SIM-2026-081"


def test_full_name_survives_single_ocr_character_confusion():
    """Same OCR-noise problem, but for the name field: 'O' misread as '0'."""
    result = _check(full_name="VIKT0R KOROL", document_number=None)
    assert result is not None
    assert result["entry"]["watchlist_id"] == "WL-SIM-2026-081"


def test_unrelated_document_number_does_not_match():
    """Fuzzy tolerance must stay narrow enough not to invent false positives."""
    result = _check(full_name=None, document_number="X1234567")
    assert result is None


def test_unrelated_name_does_not_match():
    result = _check(full_name="JOHN SMITH", document_number=None)
    assert result is None


def test_document_number_with_two_differences_does_not_match():
    """Tolerance is calibrated for a single OCR slip, not a genuinely different number."""
    result = _check(full_name=None, document_number="P8B92l44")
    assert result is None


def test_name_matches_multi_token_transliteration_variant():
    """
    Two independent one-edit spelling variants at once (a transliterated
    given name AND surname) -- 'MARCUS VANCE' -> 'MARKUS VANSE'. The old
    whole-string edit-distance check (budget 1 across the whole name) would
    reject this since the combined distance is 2; per-token matching allows
    each name part its own independent one-edit tolerance.
    """
    result = _check(full_name="MARKUS VANSE", document_number=None)
    assert result is not None
    assert result["entry"]["watchlist_id"] == "WL-SIM-2026-103"


def test_name_match_exposes_match_evidence_not_a_bare_boolean():
    """
    Per-token match evidence (method/tokens/edit distance) must reach the
    final watchlist result -- an officer needs to see WHY a fuzzy/phonetic
    name match fired, not just that it did, to judge a plausible false
    positive on its own merits.
    """
    result = _check(full_name="MARKUS VANSE", document_number=None)
    assert result is not None
    assert "match_evidence" in result
    evidence = result["match_evidence"]
    assert len(evidence) == 2
    assert all(e["method"] == "EDIT_DISTANCE" for e in evidence)


def test_document_number_match_has_no_match_evidence():
    """Document-number matches use plain exact/edit-distance string
    comparison (fuzzy_equal), not the token-level phonetic matcher -- no
    match_evidence should be fabricated for it."""
    result = _check(full_name=None, document_number="P8892144")
    assert result is not None
    assert "match_evidence" not in result


def test_name_matches_phonetic_variant_beyond_edit_distance():
    """
    A genuine phonetic/transliteration variant whose Levenshtein distance
    (3) is far outside a single-OCR-slip tolerance, but which shares the
    same Soundex AND Metaphone code as the watchlisted name -- 'MARCUS' vs
    'MARKOOS' is a stand-in for real-world cases like 'Mohammed'/'Muhammad'
    (also Soundex+Metaphone-identical despite distance 2).
    """
    result = _check(full_name="MARKOOS VANCE", document_number=None)
    assert result is not None
    assert result["entry"]["watchlist_id"] == "WL-SIM-2026-103"


def test_name_matching_stays_narrow_for_unrelated_names():
    """Regression guard: phonetic matching must not turn into a blanket
    fuzzy match -- an unrelated name must still not match any entry."""
    result = _check(full_name="JOHN SMITH", document_number=None)
    assert result is None


def test_no_query_input_returns_no_match():
    """Neither a name nor a document number was extracted -- must not scan
    the whole table and return an arbitrary/first row."""
    result = _check(full_name=None, document_number=None)
    assert result is None


def test_ensure_seeded_is_idempotent():
    """Calling ensure_seeded again must not duplicate rows or change
    behavior -- it's called on every app startup, not just once."""
    from app.models import WatchlistEntry

    db = SessionLocal()
    try:
        before_count = db.query(WatchlistEntry).filter(
            WatchlistEntry.watchlist_id == "WL-SIM-2026-081"
        ).count()
        ensure_seeded(db)
        after_count = db.query(WatchlistEntry).filter(
            WatchlistEntry.watchlist_id == "WL-SIM-2026-081"
        ).count()
        assert before_count == after_count == 1
    finally:
        db.close()


def test_inactive_entry_is_not_matched():
    """A deactivated watchlist row (active=False) must be excluded from
    matching -- this is how an entry gets removed from the live watchlist
    without deleting its audit history."""
    import uuid
    from app.models import WatchlistEntry

    db = SessionLocal()
    try:
        db.add(WatchlistEntry(
            watchlist_id=f"WL-TEST-{uuid.uuid4().hex[:8]}",
            name="RETIRED ENTRY",
            document_number="Z0000001",
            category="Test",
            reason="Deactivated test entry.",
            severity="LOW",
            active=False,
        ))
        db.commit()
    finally:
        db.close()

    result = _check(full_name="RETIRED ENTRY", document_number=None)
    assert result is None
