from urllib.parse import quote

from presidentielle2027.dashboard.force_selection import (
    cookie_javascript,
    selection_cookie_value,
    selection_from_cookie,
)


def test_selection_cookie_round_trip_and_new_force_default() -> None:
    value = selection_cookie_value(["PS"], ["PS", "PP"])
    restored = selection_from_cookie(
        {"forces": value},
        "forces",
        ["PS", "PP", "EELV"],
        ["PS", "PP"],
    )
    assert restored == ["PS", "EELV"]


def test_removed_and_invalid_cookie_values_are_ignored() -> None:
    stale = quote('{"selected":["LE","PS"],"known":["LE","PS"]}')
    assert selection_from_cookie({"forces": stale}, "forces", ["PS", "PP"], ["PP"]) == ["PS", "PP"]
    assert selection_from_cookie({"forces": "broken"}, "forces", ["PS"], ["PS"]) == ["PS"]


def test_cookie_javascript_has_safe_scope_and_expiry() -> None:
    script = cookie_javascript("forces", selection_cookie_value([], ["PS"]))
    assert "path=/" in script
    assert "max-age=" in script
    assert "SameSite=Lax" in script
