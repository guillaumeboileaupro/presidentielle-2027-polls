from presidentielle2027.extraction.canonicalization import canonicalize_candidate_fields, is_generic_bloc_label


def test_candidate_aliases_are_canonicalized() -> None:
    assert canonicalize_candidate_fields("Bardella", "RN", None)[0] == "Jordan Bardella"
    assert canonicalize_candidate_fields("Jean-Luc Mélenchon", "LFI", None)[0] == "Jean-Luc Mélenchon"
    assert canonicalize_candidate_fields("Edouard Philippe", "HOR", None)[0] == "Édouard Philippe"


def test_ps_pp_candidates_are_split_back_to_their_actual_party() -> None:
    _, glucksmann_party, _ = canonicalize_candidate_fields("Glucksmann", "PS-PP", None)
    _, hollande_party, _ = canonicalize_candidate_fields("Hollande", "PS-PP", None)
    _, faure_party, _ = canonicalize_candidate_fields("Faure", "PS-PP", None)
    _, vallaud_party, _ = canonicalize_candidate_fields("Vallaud", "PS-PP", None)

    assert glucksmann_party == "PP"
    assert hollande_party == "PS"
    assert faure_party == "PS"
    assert vallaud_party == "PS"


def test_generic_bloc_labels_are_identified() -> None:
    assert is_generic_bloc_label("RN") is True
    assert is_generic_bloc_label("ENS") is True
    assert is_generic_bloc_label("Bardella") is False
