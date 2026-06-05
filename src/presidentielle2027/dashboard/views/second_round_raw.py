from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from presidentielle2027.analytics.historical_corrections import (
    CURRENT_ELECTION_DATE,
    SECOND_ROUND_TRANSFER_MATRIX,
    apply_first_round_historical_correction,
    apply_second_round_legislative_correction,
    get_reference_dir,
    normalize_broad_bloc,
)
from presidentielle2027.analytics.trends import build_lowess_curve, exploratory_extension
from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.methodology_text import second_round_methodology_html
from presidentielle2027.dashboard.party_assets import build_candidate_summary_table
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME
from presidentielle2027.dashboard.table_views import render_poll_results_table

FRENCH_BLOC_LABELS = {
    "gauche": "Gauche",
    "centre": "Centre",
    "droite": "Droite",
    "extrême_droite": "Extrême droite",
    "autres": "Autres",
}

SCENARIO_LABELS = {
    "Attal vs Bardella": "Hypothèse Attal – Bardella",
    "Mélenchon vs Bardella": "Hypothèse Mélenchon – Bardella",
    "Philippe vs Bardella": "Hypothèse Philippe – Bardella",
    "Glucksmann vs Bardella": "Hypothèse Glucksmann – Bardella",
    "Retailleau vs Bardella": "Hypothèse Retailleau – Bardella",
    "Philippe vs Le Pen": "Hypothèse Philippe – Le Pen",
    "Attal vs Le Pen": "Hypothèse Attal – Le Pen",
    "Mélenchon vs Le Pen": "Hypothèse Mélenchon – Le Pen",
    "Ruffin vs Le Pen": "Hypothèse Ruffin – Le Pen",
    "Macron vs Le Pen rerun": "Hypothèse Macron – Le Pen",
    "Macron vs Le Pen official 2022": "Référence 2022 · Macron – Le Pen",
}


def _format_second_round_scenario(value: object) -> str:
    label = str(value).strip() if value not in (None, "") else "Scénario non renseigné"
    return SCENARIO_LABELS.get(label, label)


def _build_corrected_transfer_analysis(
    full_frame: pd.DataFrame,
    filtered_second_round: pd.DataFrame,
    candidate_a: str,
    candidate_b: str,
    pollster: str,
    period: object,
    reference_dir: Path,
) -> tuple[pd.DataFrame, dict[str, float]] | tuple[None, None]:
    first_round = full_frame.loc[(full_frame["round"] == "first_round") & (~full_frame["is_generic_bloc"])].copy()
    if first_round.empty:
        return None, None
    if pollster != "Tous":
        first_round = first_round.loc[first_round["polling_company"] == pollster]
    if isinstance(period, tuple) and len(period) == 2:
        first_round = first_round.loc[
            first_round["publication_date"].between(pd.Timestamp(period[0]), pd.Timestamp(period[1]), inclusive="both")
        ]
    if first_round.empty:
        return None, None

    first_round, _ = apply_first_round_historical_correction(first_round, reference_dir)
    first_round["broad_bloc"] = first_round.apply(
        lambda row: normalize_broad_bloc(row.get("candidate_party"), row.get("political_family")),
        axis=1,
    )
    first_round_grouped = (
        first_round.groupby(["publication_date", "broad_bloc"], dropna=False)
        .agg(corrected_share=("historically_corrected_estimate", "mean"))
        .reset_index()
        .sort_values(["broad_bloc", "publication_date"])
    )
    latest_blocs = (
        first_round_grouped.sort_values(["publication_date", "corrected_share"], ascending=[False, False])
        .groupby("broad_bloc", dropna=False)
        .head(1)
        .copy()
    )
    if latest_blocs.empty:
        return None, None

    scenario_candidates = (
        filtered_second_round[["candidate_label", "candidate_name", "candidate_party", "political_family", "broad_bloc"]]
        .drop_duplicates()
        .set_index("candidate_label")
    )
    if candidate_a not in scenario_candidates.index or candidate_b not in scenario_candidates.index:
        return None, None

    candidate_a_bloc = str(scenario_candidates.loc[candidate_a, "broad_bloc"])
    candidate_b_bloc = str(scenario_candidates.loc[candidate_b, "broad_bloc"])
    candidate_a_name = str(scenario_candidates.loc[candidate_a, "candidate_name"])
    candidate_b_name = str(scenario_candidates.loc[candidate_b, "candidate_name"])

    rows: list[dict[str, object]] = []
    total_a = 0.0
    total_b = 0.0
    for _, bloc_row in latest_blocs.sort_values("corrected_share", ascending=False).iterrows():
        source_bloc = str(bloc_row["broad_bloc"])
        corrected_share = float(bloc_row["corrected_share"])
        transfer_map = SECOND_ROUND_TRANSFER_MATRIX.get(source_bloc, SECOND_ROUND_TRANSFER_MATRIX["autres"])
        to_a = float(transfer_map.get(candidate_a_bloc, 0.0))
        to_b = float(transfer_map.get(candidate_b_bloc, 0.0))
        contribution_a = corrected_share * to_a
        contribution_b = corrected_share * to_b
        total_a += contribution_a
        total_b += contribution_b
        rows.append(
            {
                "Bloc source": FRENCH_BLOC_LABELS.get(source_bloc, source_bloc),
                "Part corrigée 1er tour": corrected_share,
                f"Report vers {candidate_a_name}": to_a * 100.0,
                f"Report vers {candidate_b_name}": to_b * 100.0,
                f"Contribution {candidate_a_name}": contribution_a,
                f"Contribution {candidate_b_name}": contribution_b,
                "Dernière date 1er tour": pd.Timestamp(bloc_row["publication_date"]),
            }
        )
    if not rows:
        return None, None

    total = total_a + total_b
    totals = {
        candidate_a_name: total_a / total * 100.0 if total > 0 else 50.0,
        candidate_b_name: total_b / total * 100.0 if total > 0 else 50.0,
    }
    return pd.DataFrame(rows), totals


def render_second_round_raw_page(frame: pd.DataFrame) -> None:
    st.subheader("Sondages 2027 concernant le second tour")
    working = frame.loc[frame["round"] == "second_round"].copy()
    if working.empty:
        st.info("Aucune hypothèse de second tour disponible.")
        return
    if "source_url" not in working.columns:
        working["source_url"] = pd.NA

    st.markdown(second_round_methodology_html(), unsafe_allow_html=True)
    st.caption(
        "Hypothèses de second tour alignées sur la page Wikipédia 2027 : Attal, Mélenchon, Philippe, Glucksmann, Retailleau, Ruffin face à Bardella ou Le Pen selon les cas."
    )
    working["scenario_label"] = working["scenario_name"].map(_format_second_round_scenario)
    working["candidate_label"] = working["candidate_name"].fillna("Inconnu") + " · " + working["candidate_party"].fillna("Sans parti")

    candidate_catalog = (
        working[["candidate_name", "candidate_party", "candidate_label"]]
        .dropna(subset=["candidate_name"])
        .drop_duplicates()
        .sort_values(["candidate_name", "candidate_party"])
    )
    candidate_labels = candidate_catalog["candidate_label"].tolist()
    default_a = candidate_labels[0]
    default_b = candidate_labels[1] if len(candidate_labels) > 1 else candidate_labels[0]

    pollsters = ["Tous"] + sorted(working["polling_company"].dropna().astype(str).unique().tolist())
    scenarios = ["Toutes"] + sorted(working["scenario_label"].dropna().astype(str).unique().tolist())
    min_date = working["publication_date"].min().date() if working["publication_date"].notna().any() else date.today()
    max_date = working["publication_date"].max().date() if working["publication_date"].notna().any() else date.today()

    c1, c2 = st.columns(2)
    candidate_a = c1.selectbox("Candidat A", candidate_labels, index=0, key="second_round_candidate_a")
    candidate_b_options = [label for label in candidate_labels if label != candidate_a]
    candidate_b = c2.selectbox(
        "Candidat B",
        candidate_b_options,
        index=0 if candidate_b_options else None,
        key="second_round_candidate_b",
    )

    c3, c4, c5, c6, c7, c8, c9 = st.columns([0.9, 0.9, 0.9, 1.2, 0.8, 0.8, 0.7])
    scenario_filter = c3.selectbox("Hypothèse", scenarios, key="second_round_scenario_filter")
    pollster = c4.selectbox("Institut", pollsters, key="second_round_pollster")
    display_mode = c5.selectbox("Série affichée", ["Brut", "Corrigé 2024"], key="second_round_mode")
    period = c6.date_input("Période", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="second_round_period")
    trend_method = c7.selectbox("Modèle", ["Polynomial", "Bins"], index=0, key="second_round_trend_method")
    polynomial_order = c8.selectbox("Ordre", [1, 2, 3, 4, 5, 6], index=3, key="second_round_polynomial_order")
    show_extension = c9.checkbox(
        "Pointillé",
        value=True,
        key="second_round_extension",
    )

    selected_labels = [candidate_a, candidate_b]
    filtered = working.loc[working["candidate_label"].isin(selected_labels)].copy()
    if scenario_filter != "Toutes":
        filtered = filtered.loc[filtered["scenario_label"] == scenario_filter]
    if pollster != "Tous":
        filtered = filtered.loc[filtered["polling_company"] == pollster]
    if isinstance(period, tuple) and len(period) == 2:
        filtered = filtered.loc[
            filtered["publication_date"].between(pd.Timestamp(period[0]), pd.Timestamp(period[1]), inclusive="both")
        ]
        period_start_ts = pd.Timestamp(period[0])
        period_end_ts = pd.Timestamp(period[1])
    else:
        period_start_ts = pd.Timestamp(min_date)
        period_end_ts = pd.Timestamp(max_date)
    if filtered.empty:
        st.warning("Aucune donnée disponible pour cette combinaison.")
        return

    filtered = (
        filtered.groupby(["scenario_name", "publication_date", "poll_id"], dropna=False)
        .filter(lambda group: set(group["candidate_label"]) == set(selected_labels))
        .copy()
    )
    if filtered.empty:
        st.warning("Aucun duel complet correspondant n’existe dans le dataset pour ces deux candidats.")
        return

    filtered = apply_second_round_legislative_correction(filtered, get_reference_dir(Path.cwd()))
    value_column = "legislatively_corrected_estimate" if display_mode == "Corrigé 2024" else "estimate_percent"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Duel libre", f"{candidate_a.split(' · ')[0]} vs {candidate_b.split(' · ')[0]}")
    col2.metric("Lignes", int(len(filtered)))
    col3.metric("Instituts", int(filtered["polling_company"].nunique()))
    col4.metric("Scénarios", int(filtered["scenario_name"].nunique()))

    candidate_summary = build_candidate_summary_table(filtered, value_column)
    if not candidate_summary.empty:
        st.dataframe(
            candidate_summary,
            width="stretch",
            hide_index=True,
            column_config={
                "party_logo": st.column_config.ImageColumn("Logo"),
                "candidate_name": st.column_config.TextColumn("Candidat"),
                "candidate_party": st.column_config.TextColumn("Parti"),
                "political_family": st.column_config.TextColumn("Famille"),
                "value_display": st.column_config.TextColumn("Dernière valeur"),
            },
        )

    figure = go.Figure()
    insufficient: list[str] = []
    for candidate_name, group in filtered.groupby("candidate_name", dropna=False):
        ordered = group.sort_values("publication_date")
        party = ordered["candidate_party"].dropna().iloc[0] if ordered["candidate_party"].notna().any() else None
        family = ordered["political_family"].dropna().iloc[0] if ordered["political_family"].notna().any() else None
        color = get_political_color(party, family)
        figure.add_trace(
            go.Scatter(
                x=ordered["publication_date"],
                y=ordered[value_column],
                mode="markers",
                marker={"size": 7, "color": color, "opacity": 0.45, "line": {"color": "#ffffff", "width": 1.0}},
                name=f"{candidate_name} - points",
                legendgroup=str(candidate_name),
                showlegend=False,
                customdata=ordered[["polling_company", "scenario_name", "source_url"]].to_numpy(),
                hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<br>Institut: %{customdata[0]}<br>Hypothèse: %{customdata[1]}<extra></extra>",
            )
        )
        smoothed = build_lowess_curve(
            ordered.rename(columns={value_column: "estimate_percent"}),
            "estimate_percent",
            frac=0.32,
            degree=polynomial_order,
            method="bins" if trend_method == "Bins" else "polynomial",
        )
        if smoothed is None:
            insufficient.append(str(candidate_name))
        else:
            figure.add_trace(
                go.Scatter(
                    x=smoothed["publication_date"],
                    y=smoothed["score_smooth"],
                    mode="lines",
                    line={"width": 2.8, "color": color},
                    name=str(candidate_name),
                    legendgroup=str(candidate_name),
                    showlegend=True,
                    hovertemplate=f"{candidate_name}<br>%{{x|%d/%m/%Y}}<br>%{{y:.1f}}%<extra></extra>",
                )
            )
        if show_extension:
            extension = exploratory_extension(
                ordered.rename(columns={value_column: "estimate_percent"}),
                election_date=CURRENT_ELECTION_DATE,
                value_column="estimate_percent",
                recent_days=30,
                degree=polynomial_order,
                method="bins" if trend_method == "Bins" else "polynomial",
            )
            if extension is not None:
                figure.add_trace(
                    go.Scatter(
                        x=extension.x,
                        y=extension.y,
                        mode="lines",
                        line={"width": 1.8, "color": color, "dash": "dot"},
                        name=f"{candidate_name} - prolongation",
                        legendgroup=str(candidate_name),
                        showlegend=False,
                    )
                )
    title_suffix = "corrigé 2024" if display_mode == "Corrigé 2024" else "brut"
    model_label = "modèle par bins" if trend_method == "Bins" else f"ajustement polynomial d'ordre {polynomial_order}"
    figure.update_layout(
        title=f"Second tour 2027 · points, {model_label} et prolongation exploratoire {title_suffix}",
        xaxis_title="Date de publication",
        yaxis_title="Intentions de vote (%)",
        **PLOT_LAYOUT_THEME,
    )
    chart_end_ts = max(period_end_ts, CURRENT_ELECTION_DATE) if show_extension else period_end_ts
    figure.update_xaxes(range=[period_start_ts, chart_end_ts])
    figure.update_yaxes(ticksuffix=" %")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})
    if insufficient:
        st.caption("Tendance non calculée pour certaines séries : données insuffisantes ou scénarios non comparables.")

    if "legislative_benchmark" in filtered.columns and filtered["legislative_benchmark"].notna().any():
        benchmark_view = (
            filtered.sort_values(["publication_date", "legislatively_corrected_estimate"], ascending=[False, False])
            .groupby("candidate_name", dropna=False)
            .head(1)[
                [
                    "candidate_name",
                    "candidate_party",
                    "broad_bloc",
                    "estimate_percent",
                    "legislative_benchmark",
                    "legislatively_corrected_estimate",
                ]
            ]
            .rename(
                columns={
                    "candidate_name": "Candidat",
                    "candidate_party": "Parti",
                    "broad_bloc": "Bloc",
                    "estimate_percent": "Brut",
                    "legislative_benchmark": "Benchmark blocs 2024",
                    "legislatively_corrected_estimate": "Corrigé 2024",
                }
            )
        )
        benchmark_view["Bloc"] = benchmark_view["Bloc"].map(lambda value: FRENCH_BLOC_LABELS.get(value, value))
        st.dataframe(
            benchmark_view,
            width="stretch",
            hide_index=True,
            column_config={
                "Brut": st.column_config.NumberColumn("Brut", format="%.1f %%"),
                "Benchmark blocs 2024": st.column_config.NumberColumn("Benchmark blocs 2024", format="%.1f %%"),
                "Corrigé 2024": st.column_config.NumberColumn("Corrigé 2024", format="%.1f %%"),
            },
        )

    transfer_table, transfer_totals = _build_corrected_transfer_analysis(
        full_frame=frame,
        filtered_second_round=filtered,
        candidate_a=candidate_a,
        candidate_b=candidate_b,
        pollster=pollster,
        period=period,
        reference_dir=get_reference_dir(Path.cwd()),
    )
    if transfer_table is not None and transfer_totals is not None:
        st.markdown("**Analyse des reports de voix depuis le premier tour corrigé**")
        total_cols = st.columns(2)
        total_items = list(transfer_totals.items())
        total_cols[0].metric(f"Projection reports · {total_items[0][0]}", f"{total_items[0][1]:.1f}%")
        total_cols[1].metric(f"Projection reports · {total_items[1][0]}", f"{total_items[1][1]:.1f}%")

        contribution_cols = [column for column in transfer_table.columns if column.startswith("Contribution ")]
        candidate_a_contrib, candidate_b_contrib = contribution_cols[:2]
        contribution_chart = go.Figure()
        contribution_chart.add_bar(
            x=transfer_table["Bloc source"],
            y=transfer_table[candidate_a_contrib],
            name=candidate_a_contrib.replace("Contribution ", ""),
            marker_color="#d34a6a",
        )
        contribution_chart.add_bar(
            x=transfer_table["Bloc source"],
            y=transfer_table[candidate_b_contrib],
            name=candidate_b_contrib.replace("Contribution ", ""),
            marker_color="#3159c9",
        )
        contribution_chart.update_layout(
            barmode="group",
            title="Reports de voix projetés à partir du premier tour corrigé",
            xaxis_title="Bloc source du premier tour",
            yaxis_title="Contribution projetée",
            **PLOT_LAYOUT_THEME,
        )
        contribution_chart.update_yaxes(ticksuffix=" pts")
        st.plotly_chart(contribution_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

        st.dataframe(
            transfer_table.sort_values("Part corrigée 1er tour", ascending=False),
            width="stretch",
            hide_index=True,
            column_config={
                "Part corrigée 1er tour": st.column_config.NumberColumn("Part corrigée 1er tour", format="%.1f %%"),
                candidate_a_contrib: st.column_config.NumberColumn(candidate_a_contrib, format="%.1f pts"),
                candidate_b_contrib: st.column_config.NumberColumn(candidate_b_contrib, format="%.1f pts"),
                "Dernière date 1er tour": st.column_config.DateColumn("Dernière date 1er tour", format="DD/MM/YYYY"),
            },
        )
        st.caption(
            "Cette lecture prend le dernier premier tour corrigé disponible par bloc sur la période filtrée, "
            "puis applique la matrice de reports entre blocs pour le duel sélectionné."
        )

    detailed = filtered.sort_values(["publication_date", "estimate_percent"], ascending=[False, False]).copy()
    if "broad_bloc" in detailed.columns:
        detailed["force_label"] = detailed["broad_bloc"].map(lambda value: FRENCH_BLOC_LABELS.get(value, value))
    render_poll_results_table(detailed)
