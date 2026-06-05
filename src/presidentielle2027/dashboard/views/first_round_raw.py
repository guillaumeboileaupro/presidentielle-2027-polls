from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from presidentielle2027.analytics.historical_corrections import CURRENT_ELECTION_DATE
from presidentielle2027.analytics.trends import build_lowess_curve
from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.methodology_text import first_round_methodology_html
from presidentielle2027.dashboard.party_assets import build_force_summary_table
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME
from presidentielle2027.dashboard.table_views import render_poll_results_table


def _build_joint_extension_paths(
    extension_payloads: list[dict[str, object]],
    election_date: pd.Timestamp,
) -> list[dict[str, object]]:
    if not extension_payloads:
        return []

    last_solid_date = max(pd.Timestamp(payload["smoothed"].index.max()) for payload in extension_payloads)
    start_date = last_solid_date
    election_ts = pd.Timestamp(election_date)
    if start_date > election_ts:
        return []

    extension_dates = pd.date_range(start_date, election_ts, freq="D")
    sigma_map: dict[str, float] = {}
    projected_paths: dict[str, np.ndarray] = {}

    for payload in extension_payloads:
        key = str(payload["display_name"])
        smoothed = payload["smoothed"]
        smoothed = smoothed[~smoothed.index.duplicated(keep="last")].sort_index()
        smoothed_extended = smoothed.reindex(smoothed.index.union(pd.DatetimeIndex([last_solid_date]))).sort_index()
        smoothed_extended = smoothed_extended.interpolate(method="time").ffill().bfill()
        anchor_value = float(smoothed_extended.loc[last_solid_date])
        sigma_map[key] = float(payload["sigma"])

        recent_window = smoothed.loc[smoothed.index >= smoothed.index.max() - pd.Timedelta(days=60)]
        if len(recent_window.index) < 2:
            recent_window = smoothed.tail(min(9, len(smoothed.index)))
        recent_span = max(float((recent_window.index.max() - recent_window.index.min()) / pd.Timedelta(days=1)), 1.0)
        raw_slope = float(recent_window.iloc[-1] - recent_window.iloc[0]) / recent_span
        amplitude = float(recent_window.max() - recent_window.min()) if len(recent_window.index) > 1 else 0.0
        slope_cap = max(amplitude / recent_span, 0.01)
        daily_slope = float(np.clip(raw_slope, -slope_cap, slope_cap))
        total_change_cap = max(3.0, min(8.0, amplitude * 1.5 + 1.0))

        horizon_days = np.arange(1, len(extension_dates) + 1, dtype=float)
        horizon_scale = max(float(len(extension_dates)), 1.0)
        damping = 1.0 - 0.55 * np.clip(horizon_days / horizon_scale, 0.0, 1.0)
        path = anchor_value + np.cumsum(daily_slope * damping)
        projected_paths[key] = np.clip(path, anchor_value - total_change_cap, anchor_value + total_change_cap)

    projected_frame = pd.DataFrame(projected_paths, index=extension_dates).clip(lower=0.0, upper=100.0)

    normalized_payloads: list[dict[str, object]] = []
    for payload in extension_payloads:
        key = str(payload["display_name"])
        center = projected_frame[key]
        growth = np.linspace(1.0, 1.8, num=len(extension_dates))
        width = np.clip(sigma_map[key] * growth, 0.8, 6.0)
        smoothed = payload["smoothed"]
        own_last_date = pd.Timestamp(smoothed.index.max())
        own_last_value = float(smoothed.iloc[-1])
        anchor_value = float(payload["anchor_value"])
        transition_days = min(28, max(7, len(extension_dates) // 6))
        transition_steps = np.arange(len(extension_dates), dtype=float)
        transition_weight = np.clip(transition_steps / max(float(transition_days), 1.0), 0.0, 1.0)
        transition_weight = transition_weight * transition_weight * (3.0 - 2.0 * transition_weight)
        normalized_center = center.to_numpy(dtype=float)
        smooth_center = anchor_value + (normalized_center - anchor_value) * transition_weight

        if own_last_date < start_date:
            bridge_dates = pd.date_range(own_last_date, start_date, freq="D")
            bridge_steps = np.linspace(0.0, 1.0, num=len(bridge_dates))
            bridge_weight = bridge_steps * bridge_steps * (3.0 - 2.0 * bridge_steps)
            bridge_center = own_last_value + (anchor_value - own_last_value) * bridge_weight
            bridge_width = np.linspace(0.0, width[0], num=len(bridge_dates))
            full_dates = bridge_dates.append(extension_dates[1:])
            full_center = np.concatenate([bridge_center, smooth_center[1:]])
            full_width = np.concatenate([bridge_width, width[1:]])
        else:
            full_dates = extension_dates
            full_center = smooth_center
            full_width = width

        normalized_payloads.append(
            {
                **payload,
                "x": pd.Series(full_dates),
                "y": pd.Series(full_center),
                "lower": pd.Series(np.clip(full_center - full_width, 0.0, 100.0)),
                "upper": pd.Series(np.clip(full_center + full_width, 0.0, 100.0)),
            }
        )
    return normalized_payloads


def render_first_round_raw_page(frame: pd.DataFrame) -> None:
    st.subheader("Sondages 2027 concernant le premier tour")
    working = frame.loc[(frame["round"] == "first_round") & (~frame["is_generic_bloc"])].copy()
    if working.empty:
        st.info("Aucune donnée de premier tour exploitable.")
        return
    if "source_url" not in working.columns:
        working["source_url"] = pd.NA
    st.markdown(first_round_methodology_html(), unsafe_allow_html=True)
    st.caption(
        "Source de référence : Wikipédia, « Liste de sondages sur l'élection présidentielle française de 2027 ». "
        "Lecture par années 2026, 2025, 2024 et 2023, avec ajustement polynomial par force."
    )

    pollsters = ["Tous"] + sorted(working["polling_company"].dropna().astype(str).unique().tolist())
    min_date = working["publication_date"].min().date() if working["publication_date"].notna().any() else date.today()
    max_date = working["publication_date"].max().date() if working["publication_date"].notna().any() else date.today()

    available_years = sorted(
        working["publication_date"].dropna().dt.year.astype(int).unique().tolist(),
        reverse=True,
    )
    year_options = ["Toutes"] + [str(year) for year in available_years]

    c1, c2, c3, c4, c5, c6 = st.columns([1.0, 1.2, 1.0, 0.8, 0.8, 0.8])
    pollster = c1.selectbox("Institut", pollsters, key="first_round_pollster")
    period = c2.date_input("Période", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="first_round_period")
    grouping = c3.selectbox("Regrouper par", ["Parti politique", "Famille politique"], key="first_round_grouping")
    selected_year = c4.selectbox("Année", year_options, key="first_round_year")
    trend_method = c5.selectbox("Modèle", ["Polynomial", "Bins"], index=0, key="first_round_trend_method")
    polynomial_order = c6.selectbox("Ordre", [1, 2, 3, 4, 5, 6], index=3, key="first_round_polynomial_order")
    show_extension = st.checkbox(
        "Prolongation en pointillé jusqu'à l'élection",
        value=True,
        key="first_round_show_extension",
    )
    filtered = working.copy()
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
    if selected_year != "Toutes":
        filtered = filtered.loc[filtered["publication_date"].dt.year == int(selected_year)]
        year_start = pd.Timestamp(year=int(selected_year), month=1, day=1)
        year_end = pd.Timestamp(year=int(selected_year), month=12, day=31)
        period_start_ts = max(period_start_ts, year_start)
        period_end_ts = min(period_end_ts, year_end)
    if filtered.empty:
        st.warning("Aucune donnée disponible pour ces filtres.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Périmètre", "Tous les sondages du premier tour")
    col2.metric("Lignes", int(len(filtered)))
    col3.metric("Instituts", int(filtered["polling_company"].nunique()))
    col4.metric("Forces", int(filtered["candidate_party"].fillna("Sans parti").nunique() if grouping == "Parti politique" else filtered["political_family"].fillna("Autre").nunique()))

    summary_source = filtered.copy()
    if grouping == "Parti politique":
        summary_source["force_name"] = summary_source["candidate_party"].fillna("Sans parti")
    else:
        summary_source["force_name"] = summary_source["political_family"].fillna("Autre")
    force_summary = build_force_summary_table(summary_source, "force_name", "estimate_percent")
    if not force_summary.empty:
        st.markdown("**Lecture rapide des forces**")
        st.dataframe(
            force_summary,
            width="stretch",
            hide_index=True,
            column_config={
                "party_logo": st.column_config.ImageColumn("Logo"),
                "force_name": st.column_config.TextColumn("Force"),
                "candidate_party": st.column_config.TextColumn("Parti"),
                "political_family": st.column_config.TextColumn("Famille"),
                "value_display": st.column_config.TextColumn("Dernière valeur"),
            },
        )

    grouped = filtered.copy()
    if grouping == "Parti politique":
        grouped["display_name"] = grouped["candidate_party"].fillna("Sans parti")
        grouped["display_party"] = grouped["candidate_party"].fillna("Sans parti")
        grouped["display_family"] = grouped["political_family"].fillna("Autre")
    else:
        grouped["display_name"] = grouped["political_family"].fillna("Autre")
        grouped["display_party"] = grouped["candidate_party"].fillna("Sans parti")
        grouped["display_family"] = grouped["political_family"].fillna("Autre")

    grouped = (
        grouped.groupby(["publication_date", "display_name"], dropna=False)
        .agg(
            estimate_percent=("estimate_percent", "mean"),
            sample_size=("sample_size", "mean"),
            polling_company=("polling_company", "first"),
            candidate_party=("display_party", "first"),
            political_family=("display_family", "first"),
        )
        .reset_index()
        .sort_values(["display_name", "publication_date"])
    )

    figure = go.Figure()
    insufficient_forces: list[str] = []
    extension_payloads: list[dict[str, object]] = []
    for display_name, group in grouped.groupby("display_name", dropna=False):
        ordered = group.sort_values("publication_date")
        party = ordered["candidate_party"].dropna().iloc[0] if ordered["candidate_party"].notna().any() else None
        family = ordered["political_family"].dropna().iloc[0] if ordered["political_family"].notna().any() else None
        color = get_political_color(party, family)
        ordered_for_curve = ordered

        figure.add_trace(
            go.Scatter(
                x=ordered["publication_date"],
                y=ordered["estimate_percent"],
                mode="markers",
                marker={"size": 7, "color": color, "opacity": 0.8, "line": {"color": "#ffffff", "width": 1.0}},
                name=f"{display_name} - points",
                legendgroup=str(display_name),
                showlegend=False,
                customdata=ordered[["polling_company", "sample_size"]].to_numpy(),
                hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<br>Institut: %{customdata[0]}<br>Échantillon: %{customdata[1]}<extra></extra>",
            )
        )
        smoothed = build_lowess_curve(
            ordered_for_curve,
            "estimate_percent",
            frac=0.30,
            degree=polynomial_order,
            method="bins" if trend_method == "Bins" else "polynomial",
        )
        if smoothed is None:
            insufficient_forces.append(str(display_name))
        else:
            smoothed_series = pd.Series(
                smoothed["score_smooth"].to_numpy(dtype=float),
                index=pd.to_datetime(smoothed["publication_date"]),
            )
            figure.add_trace(
                go.Scatter(
                    x=smoothed["publication_date"],
                    y=smoothed["score_smooth"],
                    mode="lines",
                    line={"width": 2.6, "color": color},
                    name=str(display_name),
                    legendgroup=str(display_name),
                    showlegend=True,
                    hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<extra></extra>",
                )
            )
            if show_extension:
                smoothed_on_observed = smoothed_series.reindex(
                    smoothed_series.index.union(pd.to_datetime(ordered["publication_date"]))
                ).sort_index().interpolate(method="time").ffill().bfill()
                aligned_smooth = smoothed_on_observed.reindex(pd.to_datetime(ordered["publication_date"])).to_numpy(dtype=float)
                residuals = ordered["estimate_percent"].to_numpy(dtype=float) - aligned_smooth
                sigma = float(np.nanstd(residuals)) if len(residuals) > 1 else 1.0
                extension_payloads.append(
                        {
                            "display_name": str(display_name),
                            "color": color,
                            "smoothed": smoothed_series,
                            "sigma": sigma,
                            "anchor_value": float(smoothed_series.iloc[-1]),
                        }
                    )
    if show_extension:
        for payload in _build_joint_extension_paths(extension_payloads, CURRENT_ELECTION_DATE):
            figure.add_trace(
                go.Scatter(
                    x=payload["x"],
                    y=payload["upper"],
                    mode="lines",
                    line={"width": 0, "color": payload["color"]},
                    hoverinfo="skip",
                    showlegend=False,
                    legendgroup=f"{payload['display_name']}-extension",
                )
            )
            figure.add_trace(
                go.Scatter(
                    x=payload["x"],
                    y=payload["lower"],
                    mode="lines",
                    line={"width": 0, "color": payload["color"]},
                    fill="tonexty",
                    fillcolor="rgba(120,120,120,0.10)",
                    hoverinfo="skip",
                    showlegend=False,
                    legendgroup=f"{payload['display_name']}-extension",
                )
            )
            figure.add_trace(
                go.Scatter(
                    x=payload["x"],
                    y=payload["y"],
                    mode="lines",
                    line={"width": 1.8, "color": payload["color"], "dash": "dash"},
                    name=f"{payload['display_name']} - prolongation",
                    legendgroup=f"{payload['display_name']}-extension",
                    showlegend=False,
                    hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<br>Scénario exploratoire normalisé à 100%<extra></extra>",
                )
            )
    model_label = f"modèle par bins" if trend_method == "Bins" else f"ajustement polynomial d'ordre {polynomial_order}"
    title = f"{model_label.capitalize()} des sondages publiés entre l'élection présidentielle de 2022 et l'élection présidentielle de 2027"
    if selected_year != "Toutes":
        title = f"Sondages 2027 · {selected_year} · {model_label}"
    figure.update_layout(
        title=title,
        xaxis_title="Date de publication",
        yaxis_title="Intentions de vote (%)",
        **PLOT_LAYOUT_THEME,
    )
    chart_end_ts = max(period_end_ts, CURRENT_ELECTION_DATE) if show_extension else period_end_ts
    figure.update_xaxes(range=[period_start_ts, chart_end_ts])
    figure.update_yaxes(ticksuffix=" %")
    figure.add_vline(x=pd.Timestamp("2022-04-10"), line_width=1, line_color="#999999", opacity=0.6)
    figure.add_vline(x=pd.Timestamp("2027-04-11"), line_width=1, line_color="#999999", opacity=0.6)
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})
    if insufficient_forces:
        st.caption("Tendance non calculée pour certaines forces : données insuffisantes ou scénarios non comparables.")
    if show_extension:
        st.caption("Scénario exploratoire fondé sur la pente récente des courbes lissées, avec fit élargi sur plus de points récents et sans renormalisation finale forcée à 100%. Ce n’est pas une prédiction électorale validée.")
    st.caption("Les données historiques 2017–2022 sont affichées dans la vue `Analyse historique 2022`. Cette vue reste un graphe brut 2027, sans mélange de séries historiques dans la courbe principale.")

    st.markdown("**Tableau détaillé des sondages du premier tour**")
    detailed = filtered.sort_values(["publication_date", "candidate_party", "estimate_percent"], ascending=[False, True, False])
    if "source_url" not in detailed.columns:
        detailed["source_url"] = pd.NA
    if grouping == "Parti politique":
        detailed["force_label"] = detailed["candidate_party"].fillna("Sans parti")
    else:
        detailed["force_label"] = detailed["political_family"].fillna("Autre")
    render_poll_results_table(detailed)
