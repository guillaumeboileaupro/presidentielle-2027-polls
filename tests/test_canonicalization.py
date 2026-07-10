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


def test_candidate_party_aliases_and_family_aliases_are_normalized() -> None:
    _, party, family = canonicalize_candidate_fields("Marine Tondelier", "EELV", "greens")
    assert party == "LE"
    assert family == "écologistes"

    _, party, family = canonicalize_candidate_fields("François Bayrou", "MODEM", "centre_left")
    assert party == "MoDem"
    assert family == "centre_gauche"


def test_epr_bucket_is_split_back_to_candidate_party() -> None:
    _, philippe_party, _ = canonicalize_candidate_fields("Édouard Philippe", "EPR", "centre")
    _, attal_party, _ = canonicalize_candidate_fields("Gabriel Attal", "Ensemble pour la République", "centre")

    assert philippe_party == "HOR"
    assert attal_party == "RE"


def test_wiki_party_defaults_override_noisy_presidential_buckets() -> None:
    _, bardella_party, _ = canonicalize_candidate_fields("Jordan Bardella", "UDR", "droite_nationale")
    _, glucksmann_party, _ = canonicalize_candidate_fields("Raphaël Glucksmann", "NFP", "centre_gauche")

    assert bardella_party == "RN"
    assert glucksmann_party == "PP"


def test_final_party_normalization_can_drop_or_rewrite_noisy_codes() -> None:
    _, party_div, family_div = canonicalize_candidate_fields("Candidat inconnu", "DIV", "other")
    _, party_psdvg, family_psdvg = canonicalize_candidate_fields("Candidat inconnu", "PS/DVG", None)

    assert party_div is None
    assert family_div == "other"
    assert party_psdvg == "PS"
    assert family_psdvg == "centre_gauche"
