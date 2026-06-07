from presidentielle2027.dashboard.party_assets import get_party_logo_url


def test_ps_pp_logo_depends_on_candidate_name() -> None:
    glucksmann_logo = get_party_logo_url("PS-PP", "Raphaël Glucksmann")
    hollande_logo = get_party_logo_url("PS-PP", "François Hollande")
    pp_logo = get_party_logo_url("PP", "Raphaël Glucksmann")

    assert "Logo%20Place%20publique.svg" in glucksmann_logo
    assert "Le%20Parti%20socialiste%20wordmark.svg" in hollande_logo
    assert "Logo%20Place%20publique.svg" in pp_logo
