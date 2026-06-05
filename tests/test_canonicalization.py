from presidentielle2027.extraction.canonicalization import canonicalize_candidate_fields, is_generic_bloc_label


def test_candidate_aliases_are_canonicalized() -> None:
    assert canonicalize_candidate_fields("Bardella", "RN", None)[0] == "Jordan Bardella"
    assert canonicalize_candidate_fields("Jean-Luc Mélenchon", "LFI", None)[0] == "Jean-Luc Mélenchon"
    assert canonicalize_candidate_fields("Edouard Philippe", "HOR", None)[0] == "Édouard Philippe"


def test_generic_bloc_labels_are_identified() -> None:
    assert is_generic_bloc_label("RN") is True
    assert is_generic_bloc_label("ENS") is True
    assert is_generic_bloc_label("Bardella") is False
