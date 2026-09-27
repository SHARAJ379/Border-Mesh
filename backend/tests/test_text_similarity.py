from app.utils.text_similarity import levenshtein, fuzzy_equal, fuzzy_name_match, phonetic_or_fuzzy_token_equal


def test_levenshtein_identical_strings():
    assert levenshtein("X1234567", "X1234567") == 0


def test_levenshtein_single_substitution():
    assert levenshtein("X1234567", "X1B34567") == 1


def test_fuzzy_equal_within_tolerance():
    assert fuzzy_equal("X1234567", "X1B34567") is True


def test_fuzzy_equal_rejects_two_edits():
    assert fuzzy_equal("X1234567", "X1BB4567") is False


def test_fuzzy_equal_rejects_short_strings_even_with_one_edit():
    assert fuzzy_equal("ABCDE", "ABCDF") is False


# --- Match evidence: WHY two tokens matched, not just whether they did -----

def test_exact_token_match_reports_exact_method():
    evidence = phonetic_or_fuzzy_token_equal("MARCUS", "MARCUS")
    assert evidence == {"method": "EXACT", "query_token": "MARCUS", "matched_token": "MARCUS", "edit_distance": 0}


def test_edit_distance_token_match_reports_the_actual_distance():
    evidence = phonetic_or_fuzzy_token_equal("MARCUS", "MARKUS")
    assert evidence["method"] == "EDIT_DISTANCE"
    assert evidence["edit_distance"] == 1


def test_soundex_only_match_is_labeled_soundex():
    """'SEAN'/'SHAWN' only share a Soundex code (Metaphone's silent-H
    handling keeps them apart) -- the evidence must say which method fired,
    not just that one did."""
    evidence = phonetic_or_fuzzy_token_equal("SEAN", "SHAWN")
    assert evidence is not None
    assert evidence["method"] == "SOUNDEX"
    assert evidence["edit_distance"] is None


def test_metaphone_only_match_is_labeled_metaphone():
    """'KNIGHT'/'NITE' have different Soundex codes (K523 vs N300, since
    Soundex keeps the literal first letter) but an identical Metaphone code
    (silent-K/silent-GH handling) -- and a length gap of 2, outside the
    edit-distance branch's tolerance."""
    evidence = phonetic_or_fuzzy_token_equal("KNIGHT", "NITE")
    assert evidence is not None
    assert evidence["method"] == "METAPHONE"


def test_unrelated_tokens_report_no_match_evidence():
    assert phonetic_or_fuzzy_token_equal("JOHN", "MARCUS") is None


def test_fuzzy_name_match_returns_per_token_evidence_for_a_multi_token_variant():
    """Two independent one-edit spelling variants at once -- the returned
    evidence must cover BOTH tokens, each with its own match detail."""
    matches = fuzzy_name_match("MARCUS VANCE", "MARKUS VANSE")
    assert matches is not None
    assert len(matches) == 2
    assert {m["method"] for m in matches} == {"EDIT_DISTANCE"}
    matched_pairs = {(m["matched_token"], m["query_token"]) for m in matches}
    assert matched_pairs == {("MARCUS", "MARKUS"), ("VANCE", "VANSE")}


def test_fuzzy_name_match_returns_none_when_any_entry_token_is_unmatched():
    assert fuzzy_name_match("MARCUS VANCE", "MARCUS SMITH") is None
