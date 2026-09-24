"""Regression tests for the Streamlit widget monkeypatch in table_views.py.

`install_user_facing_text_guard()` overwrites `st.dataframe`, `st.table`,
`st.selectbox`, `st.multiselect` and `st.radio` at module level so internal
identifiers never leak into the UI. That patch is process-wide and idempotent
(guarded by `st._presidentielle_text_guard_installed`), so these tests reset
that flag and stub the underlying Streamlit callables before each install to
observe the wiring in isolation, independent of test execution order.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import streamlit as st

from presidentielle2027.dashboard import table_views


def _reset_guard() -> None:
    for attr in ("dataframe", "table", "selectbox", "multiselect", "radio"):
        setattr(st, attr, MagicMock(name=attr))
    if hasattr(st, "_presidentielle_text_guard_installed"):
        delattr(st, "_presidentielle_text_guard_installed")


def test_install_is_idempotent() -> None:
    _reset_guard()
    stub_dataframe = st.dataframe
    table_views.install_user_facing_text_guard()
    wrapped_once = st.dataframe
    table_views.install_user_facing_text_guard()
    assert st.dataframe is wrapped_once
    assert st.dataframe is not stub_dataframe


def test_guarded_dataframe_sanitizes_columns_and_values_before_render() -> None:
    _reset_guard()
    stub_dataframe = st.dataframe
    table_views.install_user_facing_text_guard()

    raw = pd.DataFrame(
        {
            "candidate_party": ["centre_left", "green"],
            "estimate_percent": [12.3, 8.1],
        }
    )
    st.dataframe(raw)

    stub_dataframe.assert_called_once()
    rendered = stub_dataframe.call_args.args[0]
    assert list(rendered.columns) == ["Parti", "Score"]
    assert rendered["Parti"].tolist() == ["Centre-gauche", "Écologistes"]


def test_guarded_table_sanitizes_before_render() -> None:
    _reset_guard()
    stub_table = st.table
    table_views.install_user_facing_text_guard()

    raw = pd.DataFrame({"political_family": ["far_right"]})
    st.table(raw)

    stub_table.assert_called_once()
    rendered = stub_table.call_args.args[0]
    assert rendered["Famille politique"].tolist() == ["Extrême droite"]


def test_guarded_selectbox_uses_user_facing_format_func_by_default() -> None:
    _reset_guard()
    stub_selectbox = st.selectbox
    table_views.install_user_facing_text_guard()

    st.selectbox("label", ["centre_left"])

    stub_selectbox.assert_called_once()
    _, kwargs = stub_selectbox.call_args
    assert kwargs["format_func"]("centre_left") == "Centre-gauche"


def test_guarded_selectbox_respects_explicit_format_func() -> None:
    _reset_guard()
    stub_selectbox = st.selectbox
    table_views.install_user_facing_text_guard()

    custom_format = MagicMock(return_value="custom")
    st.selectbox("label", ["centre_left"], format_func=custom_format)

    _, kwargs = stub_selectbox.call_args
    assert kwargs["format_func"] is custom_format
