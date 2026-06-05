from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from presidentielle2027.dashboard.metadata import build_frame_completeness_summary, load_csv_if_exists


def render_metadata_page(frame: pd.DataFrame) -> None:
    st.subheader("Métadonnées")
    if frame.empty:
        st.info("Aucune donnée pour les filtres sélectionnés.")
        return

    st.markdown(
        '<div class="wiki-panel">Cette vue documente ce que l’on sait réellement des jeux de données et des instituts. '
        'Sans ces informations, les comparaisons et corrections peuvent devenir trompeuses.</div>',
        unsafe_allow_html=True,
    )

    completeness = build_frame_completeness_summary(frame)
    st.markdown("**Couverture des métadonnées sur les lignes actuellement affichées**")
    st.dataframe(completeness, width="stretch")

    dataset_registry = load_csv_if_exists(Path("data/reference/datasets_metadata.csv"))
    if not dataset_registry.empty:
        st.markdown("**Registre des jeux de données connus**")
        st.dataframe(dataset_registry, width="stretch")

    pollster_registry = load_csv_if_exists(Path("data/reference/pollsters_metadata.csv"))
    if not pollster_registry.empty:
        visible_pollsters = sorted(frame["polling_company"].dropna().astype(str).unique().tolist())
        filtered_registry = pollster_registry.loc[pollster_registry["polling_company"].isin(visible_pollsters)].copy()
        st.markdown("**Fiche des instituts présents dans la sélection**")
        st.dataframe(filtered_registry if not filtered_registry.empty else pollster_registry, width="stretch")

    missing_core = frame.loc[
        frame["sample_size"].isna()
        | frame["publication_date"].isna()
        | frame.get("fieldwork_start_date", pd.Series(index=frame.index)).isna()
    ].copy()
    st.markdown("**Lignes avec métadonnées critiques manquantes**")
    columns = [column for column in [
        "poll_id",
        "polling_company",
        "scenario_name",
        "candidate_name",
        "sample_size",
        "fieldwork_start_date",
        "fieldwork_end_date",
        "publication_date",
        "collection_method",
        "commissioner",
        "source_url",
    ] if column in missing_core.columns]
    st.dataframe(missing_core[columns].head(200), width="stretch")

