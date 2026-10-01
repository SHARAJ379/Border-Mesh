import re
from typing import List, Optional, TypedDict

import jellyfish


class TokenMatchEvidence(TypedDict):
    """Which method judged two name tokens equivalent, and the exact tokens
    involved -- exposed so an officer can see WHY a watchlist name matched
    and judge for themselves whether it's a plausible false positive,
    rather than a bare boolean."""
    method: str  # "EXACT" | "EDIT_DISTANCE" | "SOUNDEX" | "METAPHONE"
    query_token: str
    matched_token: str
    edit_distance: Optional[int]


def levenshtein(a: str, b: str) -> int:
    """Small edit-distance helper for tolerating single-character OCR slips
    between two independently-read copies of the same short string (a
    document number, a name, a code) -- no extra dependency needed for
    strings this short."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            curr[j] = min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + (0 if ca == cb else 1)
            )
        prev = curr
    return prev[len(b)]


def fuzzy_equal(a: str, b: str, max_distance: int = 1, min_length: int = 6) -> bool:
    """True if a and b are identical or within max_distance edits of each
    other, gated by min_length and a length-difference cap so short strings
    (where a 1-edit tolerance is far more likely to produce a coincidental
    collision) never qualify."""
    if not a or not b:
        return False
    # Both sides must individually clear min_length, not just `a` -- the
    # length-difference cap alone only enforces `len(b) >= min_length -
    # max_distance` on the second argument, one shorter than intended at
    # the boundary (e.g. min_length=6, max_distance=1 let a 5-character
    # `b` through). Both real call sites (watchlist_service.py's document-
    # number check, rules_engine.py's RULE 4 OCR-vs-MRZ crosscheck) pass
    # the noisier/OCR-read value as `b`, so this mattered on the side most
    # likely to actually be short due to a misread.
    if len(a) < min_length or len(b) < min_length or abs(len(a) - len(b)) > max_distance:
        return False
    return levenshtein(a, b) <= max_distance


def _name_tokens(name: str) -> List[str]:
    return [t for t in re.split(r'\s+', name.upper().strip()) if t]


def phonetic_or_fuzzy_token_equal(a: str, b: str) -> Optional[TokenMatchEvidence]:
    """
    Returns match evidence if two individual name tokens are plausibly the
    same identity token -- either OCR noise (small edit distance) or a
    genuine phonetic/transliteration variant (Soundex or Metaphone match),
    e.g. 'MOHAMMED' vs 'MUHAMMAD' or 'STEPHENSON' vs 'STEVENSON'
    (Levenshtein distance 2 -- outside a single-OCR-slip tolerance -- but
    identical under both Soundex and Metaphone). None if no method matches.

    Checks BOTH Soundex and Metaphone rather than either alone, because they
    fail in different, non-overlapping cases (verified empirically):
    'KATHERINE'/'CATHERINE' only share a Metaphone code (Soundex keeps the
    literal first letter, so K/C never collide), while 'SEAN'/'SHAWN' only
    share a Soundex code (Metaphone's silent-H handling keeps them apart).
    """
    if not a or not b:
        return None
    if a == b:
        return {"method": "EXACT", "query_token": b, "matched_token": a, "edit_distance": 0}
    if len(a) >= 4 and len(b) >= 4 and abs(len(a) - len(b)) <= 1:
        dist = levenshtein(a, b)
        if dist <= 1:
            return {"method": "EDIT_DISTANCE", "query_token": b, "matched_token": a, "edit_distance": dist}
    # Phonetic codes on very short tokens (initials, 1-2 letter fragments)
    # collide too easily to be meaningful, and a large length gap undermines
    # the whole premise of "sounds the same" -- gate on both.
    if len(a) >= 3 and len(b) >= 3 and abs(len(a) - len(b)) <= 3:
        if jellyfish.soundex(a) == jellyfish.soundex(b):
            return {"method": "SOUNDEX", "query_token": b, "matched_token": a, "edit_distance": None}
        if jellyfish.metaphone(a) == jellyfish.metaphone(b):
            return {"method": "METAPHONE", "query_token": b, "matched_token": a, "edit_distance": None}
    return None


def fuzzy_name_match(entry_name: str, query_name: str) -> Optional[List[TokenMatchEvidence]]:
    """
    Returns the list of per-token match evidence (one entry per token in
    entry_name) if every token in entry_name (a watchlist record's stored
    name) has a phonetically-or-fuzzily matching token somewhere in
    query_name (the noisy OCR/MRZ-extracted name being screened), regardless
    of token order or extra tokens in the query (e.g. a middle name). None
    if any entry token has no match.

    Deliberately token-level rather than whole-string: a real name can vary
    in two places at once (a transliterated given name AND surname), which a
    single whole-string edit-distance budget would reject even though each
    half is individually a legitimate one-edit or phonetic variant --
    checking each token independently tolerates that.
    """
    entry_tokens = _name_tokens(entry_name)
    query_tokens = _name_tokens(query_name)
    if not entry_tokens or not query_tokens:
        return None

    matches: List[TokenMatchEvidence] = []
    for et in entry_tokens:
        best: Optional[TokenMatchEvidence] = None
        for qt in query_tokens:
            evidence = phonetic_or_fuzzy_token_equal(et, qt)
            if evidence and (best is None or evidence["method"] == "EXACT"):
                best = evidence
                if best["method"] == "EXACT":
                    break
        if best is None:
            return None
        matches.append(best)
    return matches
