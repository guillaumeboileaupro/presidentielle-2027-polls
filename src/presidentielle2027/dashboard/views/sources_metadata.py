from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from presidentielle2027.dashboard.metadata import (
    build_dataset_registry_view,
    build_frame_completeness_summary,
    build_pollster_registry_view,
    load_csv_if_exists,
)
from presidentielle2027.dashboard.wiki_complete_zip import (
    WIKI_COMPLETE_FILES,
    build_complete_zip_registry,
    load_complete_layout_lines,
    load_complete_visual_rows,
)


def _render_imported_wiki_zip_section(imported_zip_dir: Path) -> None:
    imported_csvs = sorted(imported_zip_dir.glob("*_wiki_lignes.csv"))
    if not imported_csvs:
        return

    imported_rows = []
    imported_frames: dict[str, pd.DataFrame] = {}
    for csv_path in imported_csvs:
        imported = load_csv_if_exists(csv_path)
        if imported.empty:
            continue
        imported_frames[csv_path.name] = imported
        imported_rows.append(
            {
                "Fichier": csv_path.name,
                "Lignes": int(len(imported)),
                "Première ligne": int(pd.to_numeric(imported.get("line_number"), errors="coerce").min()),
                "Dernière ligne": int(pd.to_numeric(imported.get("line_number"), errors="coerce").max()),
                "Source": imported["source_url"].dropna().iloc[0] if "source_url" in imported.columns and imported["source_url"].notna().any() else "",
                "Format": "Extraction ligne à ligne",
                "Statut": "Importé, non normalisé",
            }
        )

    if not imported_rows:
        return

    st.markdown("**Données importées depuis le zip Wikipédia**")
    st.caption(
        "Ces fichiers conservent l’extraction texte complète des pages Wikipédia 2022, 2024 et 2027. "
        "Ils sont visibles ici comme matière première documentaire, avant normalisation en tables de sondages."
    )
    st.dataframe(
        pd.DataFrame(imported_rows),
        width="stretch",
        hide_index=True,
        column_config={
            "Lignes": st.column_config.NumberColumn("Lignes", format="%d"),
            "Première ligne": st.column_config.NumberColumn("Première ligne", format="%d"),
            "Dernière ligne": st.column_config.NumberColumn("Dernière ligne", format="%d"),
            "Source": st.column_config.LinkColumn("Source"),
        },
    )

    tab_labels = [
        csv_name.replace("_wiki_lignes.csv", "").replace("_", " ").title()
        for csv_name in imported_frames.keys()
    ]
    for tab, (csv_name, imported) in zip(st.tabs(tab_labels), imported_frames.items()):
        with tab:
            search = st.text_input(
                "Filtrer le texte",
                value="",
                key=f"imported_wiki_search_{csv_name}",
                placeholder="Exemple : Mélenchon, sièges, Macron, Le Pen, IFOP",
            ).strip()
            preview = imported.copy()
            if search:
                preview = preview.loc[
                    preview["text"].fillna("").str.contains(search, case=False, na=False)
                ].copy()
            st.caption(
                f"{len(preview)} ligne(s) affichée(s) sur {len(imported)} dans `{csv_name}`."
            )
            st.dataframe(
                preview.head(300),
                width="stretch",
                hide_index=True,
                column_config={
                    "source_url": st.column_config.LinkColumn("Source"),
                    "line_number": st.column_config.NumberColumn("Ligne", format="%d"),
                    "text": st.column_config.TextColumn("Texte", width="large"),
                },
            )
            st.download_button(
                label=f"Télécharger {csv_name}",
                data=imported.to_csv(index=False).encode("utf-8"),
                file_name=csv_name,
                mime="text/csv",
                key=f"download_imported_wiki_{csv_name}",
            )


def _render_complete_wiki_zip_section() -> None:
    registry = build_complete_zip_registry()
    if registry.empty:
        return

    st.markdown("**Zip complet Wikipédia importé**")
    st.caption(
        "Ces fichiers structurés `visual_rows` et `layout_lines` sont maintenant la base brute complète 2022, 2024 et 2027. "
        "Ils remplacent les anciens parsers texte intermédiaires pour les vues historiques."
    )
    st.dataframe(
        registry,
        width="stretch",
        hide_index=True,
        column_config={
            "Visual rows": st.column_config.NumberColumn("Visual rows", format="%d"),
            "Layout lines": st.column_config.NumberColumn("Layout lines", format="%d"),
            "Source": st.column_config.LinkColumn("Source"),
        },
    )

    tabs = st.tabs([config["label"] for config in WIKI_COMPLETE_FILES.values()])
    for tab, (year_key, config) in zip(tabs, WIKI_COMPLETE_FILES.items()):
        with tab:
            visual_rows = load_complete_visual_rows(year_key)
            layout_lines = load_complete_layout_lines(year_key)
            search = st.text_input(
                "Filtrer l’extraction complète",
                value="",
                key=f"complete_wiki_zip_search_{year_key}",
                placeholder="Exemple : Macron, NFP, Bardella, sièges, reports",
            ).strip()
            visual_preview = visual_rows.copy()
            if search:
                visual_preview = visual_preview.loc[
                    visual_preview["row_text"].fillna("").str.contains(search, case=False, na=False)
                ]
            st.caption(f"{len(visual_preview)} visual row(s) affichée(s) sur {len(visual_rows)}.")
            st.dataframe(
                visual_preview[["page", "visual_row", "row_text", "source_url"]].head(200),
                width="stretch",
                hide_index=True,
                column_config={"source_url": st.column_config.LinkColumn("Source")},
            )
            st.caption(f"{len(layout_lines)} layout line(s) disponibles.")
            st.dataframe(
                layout_lines[["page", "layout_line", "raw_line", "source_url"]].head(120),
                width="stretch",
                hide_index=True,
                column_config={"source_url": st.column_config.LinkColumn("Source")},
            )


def render_sources_metadata_page(frame: pd.DataFrame) -> None:
    st.subheader("Sources et métadonnées")
    if frame.empty:
        st.info("Aucune donnée disponible.")
        return

    working = frame.copy()
    if "source_name" not in working.columns:
        working["source_name"] = "unknown_source"
    if "polling_company" not in working.columns:
        working["polling_company"] = "unknown_pollster"
    if "scenario_name" not in working.columns:
        working["scenario_name"] = "unknown_scenario"
    if "round" not in working.columns:
        working["round"] = "unknown_round"
    if "sample_size" not in working.columns:
        working["sample_size"] = pd.NA
    if "commissioner" not in working.columns:
        working["commissioner"] = pd.NA
    if "media_partner" not in working.columns:
        working["media_partner"] = pd.NA
    if "collection_method" not in working.columns:
        working["collection_method"] = pd.NA
    if "publication_date" not in working.columns:
        working["publication_date"] = pd.NaT

    st.markdown(
        '<div class="wiki-note">Cette vue sert à vérifier ce que le dataset contient réellement, '
        "source par source et institut par institut, avant toute lecture politique.</div>",
        unsafe_allow_html=True,
    )

    source_options = ["Tous"] + sorted(working["source_name"].dropna().astype(str).unique().tolist())
    selected_source = st.selectbox("Dataset / source", source_options, key="sources_metadata_source")
    visible = working if selected_source == "Tous" else working.loc[working["source_name"] == selected_source].copy()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Lignes", int(len(visible)))
    col2.metric("Sondages", int(visible["poll_id"].nunique() if "poll_id" in visible.columns else len(visible)))
    col3.metric("Instituts", int(visible["polling_company"].nunique(dropna=True)))
    col4.metric("Scénarios", int(visible["scenario_name"].nunique(dropna=True)))

    st.markdown("**Couverture des champs critiques**")
    completeness = build_frame_completeness_summary(visible)
    st.dataframe(
        completeness,
        width="stretch",
        hide_index=True,
        column_config={
            "field": st.column_config.TextColumn("Champ technique"),
            "label": st.column_config.TextColumn("Libellé"),
            "filled_count": st.column_config.NumberColumn("Présents", format="%d"),
            "missing_count": st.column_config.NumberColumn("Manquants", format="%d"),
            "coverage_percent": st.column_config.ProgressColumn("Couverture", format="%.1f%%", min_value=0, max_value=100),
        },
    )

    dataset_registry = load_csv_if_exists(Path("data/reference/datasets_metadata.csv"))
    if not dataset_registry.empty:
        st.markdown("**Registre des datasets**")
        dataset_view = build_dataset_registry_view(dataset_registry)
        keep_columns = [
            "Dataset",
            "Source",
            "Tours",
            "Extraction",
            "Échantillon",
            "Dates terrain",
            "Date publication",
            "Collecte",
            "Quotas",
            "Barres erreur",
            "Plot corrigé",
            "Statut",
        ]
        available = [column for column in keep_columns if column in dataset_view.columns]
        st.dataframe(dataset_view[available], width="stretch", hide_index=True)

    latest_web_sources = load_csv_if_exists(Path("data/reference/latest_web_sources.csv"))
    if not latest_web_sources.empty:
        st.markdown("**Sources web récentes repérées**")
        st.dataframe(
            latest_web_sources,
            width="stretch",
            hide_index=True,
            column_config={
                "url": st.column_config.LinkColumn("Lien"),
                "source_url": st.column_config.LinkColumn("Lien"),
            },
        )

    _render_imported_wiki_zip_section(Path("data/imported_wiki_zip"))
    _render_complete_wiki_zip_section()

    reference_files = [
        ("historical_polls_2022_first_round.csv", "Historique des sondages 2022 utilisés pour le redressage"),
        ("historical_results_2022_presidential_first_round.csv", "Résultats officiels du premier tour 2022"),
        ("historical_results_2024_legislatives_blocs.csv", "Blocs des législatives 2024 utilisés pour le second tour"),
        ("historical_results_2024_legislatives_seats.csv", "Sièges 2024 par bloc pour l’analyse institutionnelle"),
        ("polling_representativity_factors.csv", "Facteurs de représentativité inspirés des rapports parlementaires"),
    ]
    reference_rows = []
    for filename, label in reference_files:
        path = Path("data/reference") / filename
        if path.exists():
            reference_rows.append({"Fichier": filename, "Usage": label})
    if reference_rows:
        st.markdown("**Références de correction chargées**")
        st.dataframe(pd.DataFrame(reference_rows), width="stretch", hide_index=True)

    pollster_registry = load_csv_if_exists(Path("data/reference/pollsters_metadata.csv"))
    pollster_summary = (
        visible.groupby("polling_company", dropna=False)
        .agg(
            rows=("poll_id", "count"),
            rounds=("round", "nunique"),
            scenarios=("scenario_name", "nunique"),
            first_publication=("publication_date", "min"),
            last_publication=("publication_date", "max"),
            average_sample_size=("sample_size", "mean"),
            missing_commissioner=("commissioner", lambda s: int(s.isna().sum())),
            missing_media_partner=("media_partner", lambda s: int(s.isna().sum())),
        )
        .reset_index()
        .sort_values(["rows", "last_publication"], ascending=[False, False])
    )
    if not pollster_registry.empty:
        pollster_summary = pollster_summary.merge(pollster_registry, on="polling_company", how="left")
        pollster_summary = build_pollster_registry_view(pollster_summary)
    else:
        pollster_summary = pollster_summary.rename(columns={"polling_company": "Institut"})
    st.markdown("**Instituts présents dans ce dataset**")
    keep_columns = [
        "Institut",
        "rows",
        "rounds",
        "scenarios",
        "average_sample_size",
        "Commission",
        "Collecte par défaut",
        "Population par défaut",
        "Statut",
        "Site web",
    ]
    available = [column for column in keep_columns if column in pollster_summary.columns]
    st.dataframe(
        pollster_summary[available],
        width="stretch",
        hide_index=True,
        column_config={
            "rows": st.column_config.NumberColumn("Lignes", format="%d"),
            "rounds": st.column_config.NumberColumn("Tours", format="%d"),
            "scenarios": st.column_config.NumberColumn("Scénarios", format="%d"),
            "average_sample_size": st.column_config.NumberColumn("Échantillon moyen", format="%.0f"),
            "Site web": st.column_config.LinkColumn("Site web"),
        },
    )

    source_summary = (
        visible.groupby(["source_name", "round"], dropna=False)
        .agg(
            rows=("poll_id", "count"),
            scenarios=("scenario_name", "nunique"),
            pollsters=("polling_company", "nunique"),
            first_publication=("publication_date", "min"),
            last_publication=("publication_date", "max"),
            missing_sample_size=("sample_size", lambda s: int(s.isna().sum())),
            missing_collection_method=("collection_method", lambda s: int(s.isna().sum())),
        )
        .reset_index()
        .sort_values(["rows", "last_publication"], ascending=[False, False])
    )
    st.markdown("**Résumé par source et par tour**")
    st.dataframe(
        source_summary,
        width="stretch",
        hide_index=True,
        column_config={
            "rows": st.column_config.NumberColumn("Lignes", format="%d"),
            "scenarios": st.column_config.NumberColumn("Scénarios", format="%d"),
            "pollsters": st.column_config.NumberColumn("Instituts", format="%d"),
            "missing_sample_size": st.column_config.NumberColumn("Échantillon manquant", format="%d"),
            "missing_collection_method": st.column_config.NumberColumn("Collecte manquante", format="%d"),
        },
    )

    columns = [
        "poll_id",
        "source_name",
        "polling_company",
        "round",
        "scenario_name",
        "candidate_name",
        "sample_size",
        "fieldwork_start_date",
        "fieldwork_end_date",
        "publication_date",
        "commissioner",
        "media_partner",
        "source_url",
    ]
    missing_rows = visible.loc[
        visible["sample_size"].isna()
        | visible["publication_date"].isna()
        | visible.get("fieldwork_start_date", pd.Series(index=visible.index, dtype="datetime64[ns]")).isna()
    ].copy()
    existing_columns = [column for column in columns if column in missing_rows.columns]
    st.markdown("**Lignes avec métadonnées critiques manquantes**")
    st.dataframe(
        missing_rows[existing_columns].head(200),
        width="stretch",
        hide_index=True,
        column_config={"source_url": st.column_config.LinkColumn("Lien source")},
    )
