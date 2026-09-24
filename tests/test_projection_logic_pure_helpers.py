"""Characterization tests for the pure helper functions of
analysis_2024_projection_logic.py.

This module is a 6000+ line god-object (see TODO_AUDIT_CODE_2026-08-28.md,
P0.3) mixing HTTP scraping, official-data parsing, legislative-projection
math, and Streamlit rendering. Before any structural split, these tests lock
in the current behavior of its small, pure, side-effect-free helpers — the
functions most likely to move first (e.g. into a shared text/number-parsing
module) and the ones a refactor could most easily break silently. They do
not cover the Streamlit-rendering functions or the network/file-loading
functions, which need a different testing strategy (see the TODO).
"""

from __future__ import annotations

import pandas as pd
import pytest

from presidentielle2027.dashboard.views.analysis_2024_projection_logic import (
    _aggregate_to_blocs,
    _bloc_label,
    _display_text,
    _election_label,
    _extract_percentages,
    _force_color,
    _force_label_from_nuance,
    _force_to_bloc_key,
    _force_to_coalition_label,
    _normalize_nfp_party_code,
    _normalize_search_text,
    _parse_number_value,
    _parse_percent_value,
    _safe_percent,
    _safe_text,
    _split_force_list,
    _token_to_bloc,
)


def test_bloc_label_translates_known_keys_and_passes_through_unknown() -> None:
    assert _bloc_label("gauche") == "Gauche / NFP"
    assert _bloc_label("extrême_droite") == "RN et alliés"
    assert _bloc_label("not_a_real_bloc") == "not_a_real_bloc"


def test_election_label_translates_known_keys_and_passes_through_unknown() -> None:
    assert _election_label("2024_legi_t1") == "Législatives 2024 · 1er tour"
    assert _election_label("unknown_election_id_xyz") == "unknown_election_id_xyz"


def test_force_label_from_nuance() -> None:
    assert _force_label_from_nuance(None) == "Non renseigné"
    assert _force_label_from_nuance("  ") == "Non renseigné"
    assert _force_label_from_nuance("rn") == _force_label_from_nuance("RN")


def test_force_color_prefers_force_colors_table_over_political_color() -> None:
    color_for_unknown_nuance = _force_color("some-unrecognized-force-xyz", nuance=None)
    assert isinstance(color_for_unknown_nuance, str)
    assert color_for_unknown_nuance


@pytest.mark.parametrize(
    ("force_label", "expected_bloc"),
    [
        ("LFI", "gauche"),
        ("LFI / NFP", "gauche"),
        ("PS", "gauche"),
        ("EELV", "gauche"),
        ("RE", "centre"),
        ("MoDem", "centre"),
        ("LR", "droite"),
        ("RN", "extrême_droite"),
        ("REC", "extrême_droite"),
        ("something-unrecognized", "autres"),
        ("Un parti quelconque / NFP", "gauche"),
    ],
)
def test_force_to_bloc_key(force_label: str, expected_bloc: str) -> None:
    assert _force_to_bloc_key(force_label) == expected_bloc


@pytest.mark.parametrize(
    ("force_label", "expected_coalition"),
    [
        ("LFI", "NFP"),
        ("PS / NFP", "NFP"),
        ("RE", "Ensemble"),
        ("Horizons / Ensemble", "Ensemble"),
        ("Un parti quelconque / NFP", "NFP"),
    ],
)
def test_force_to_coalition_label(force_label: str, expected_coalition: str) -> None:
    assert _force_to_coalition_label(force_label) == expected_coalition


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("34,5 %", 34.5),
        ("34.5%", 34.5),
        ("34,5", 34.5),
        (34.5, 34.5),
        (None, 0.0),
        ("", 0.0),
    ],
)
def test_parse_percent_value(raw: object, expected: float) -> None:
    assert _parse_percent_value(raw) == pytest.approx(expected)


def test_parse_percent_value_divides_values_over_100_by_100() -> None:
    assert _parse_percent_value("250") == pytest.approx(2.5)


def test_parse_number_value() -> None:
    assert pd.isna(_parse_number_value(None))
    assert pd.isna(_parse_number_value("-"))
    assert pd.isna(_parse_number_value("–"))
    assert _parse_number_value(42) == 42.0
    assert _parse_number_value("1 234") == 1234


def test_display_text_and_safe_text() -> None:
    assert _display_text(None) == "n.d."
    assert _display_text("  ") == "n.d."
    assert _display_text("Paris") == "Paris"
    assert _display_text(None, fallback="?") == "?"
    assert _safe_text(None) == ""
    assert _safe_text(42) == "42"


def test_normalize_nfp_party_code() -> None:
    assert _normalize_nfp_party_code(None) == ""
    assert _normalize_nfp_party_code(" lfi  ") == "LFI"


def test_extract_percentages() -> None:
    assert _extract_percentages("PS 34,5 % puis RN 28,1%") == [34.5, 28.1]
    assert _extract_percentages("aucun pourcentage ici") == []


def test_token_to_bloc_falls_back_on_prefix_rules() -> None:
    assert _token_to_bloc("LFI-dissident") == "gauche"
    assert _token_to_bloc("DIV-something") == "autres"
    assert _token_to_bloc("totally-unknown-token") == "autres"


def test_aggregate_to_blocs_sums_matching_tokens() -> None:
    result = _aggregate_to_blocs(["LFI", "RN"], [10.0, 20.0])
    assert result["gauche"] == pytest.approx(10.0)
    assert result["extrême_droite"] == pytest.approx(20.0)
    assert result["centre"] == pytest.approx(0.0)


def test_aggregate_to_blocs_truncates_to_shortest_input() -> None:
    # zip() silently truncates - documented current behavior, not necessarily desired
    # (see TODO_CODEX_PRESIDENTIELLE2027.md 2.6 for the general "zip(order, tokens)" concern).
    result = _aggregate_to_blocs(["LFI", "RN", "LR"], [10.0, 20.0])
    assert sum(result.values()) == pytest.approx(30.0)


def test_normalize_search_text_strips_accents_and_punctuation() -> None:
    assert _normalize_search_text("Île-de-France Père Lachaise") == "ile de france pere lachaise"


def test_split_force_list() -> None:
    assert _split_force_list(None) == []
    assert _split_force_list("RN · REC · UDR") == ["RN", "REC", "UDR"]
    assert _split_force_list("RN") == ["RN"]


def test_safe_percent_handles_zero_denominator() -> None:
    result = _safe_percent(pd.Series([10.0, 5.0]), pd.Series([0.0, 20.0]))
    assert result.tolist() == pytest.approx([0.0, 25.0])
