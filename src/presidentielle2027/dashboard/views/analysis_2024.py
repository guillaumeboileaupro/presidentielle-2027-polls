from __future__ import annotations

from datetime import date
from pathlib import Path
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from presidentielle2027.analytics.historical_corrections import (
    get_reference_dir,
    load_legislative_2024_national_polls_from_wiki_tables,
    load_legislative_2024_national_results_from_wiki_tables,
    load_legislative_2024_results,
    load_legislative_2024_seats,
)
from presidentielle2027.analytics.trends import build_lowess_curve
from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME
from presidentielle2027.dashboard.wiki_complete_zip import load_complete_layout_lines, load_complete_visual_rows


SECOND_ROUND_TRIANGULAIRES = 89
SECOND_ROUND_DESISTEMENTS = 218
SECOND_ROUND_CONTESTS = 501
TRIANGULAIRES_SOURCE_URL = "https://lcp.fr/actualites/legislatives-2024-501-sieges-a-pourvoir-1094-candidats-89-triangulaires-le-2nd-tour-en"
DESISTEMENTS_SOURCE_URL = "https://rmc.bfmtv.com/actualites/politique/legislatives-grace-a-de-nombreux-desistements-le-nombre-de-triangulaires-moins-important-que-prevu_AV-202407030069.html"

POLL_COLUMNS = ["EXG", "NFP", "DVG", "ECO", "DVC", "ENS", "DVD", "LR", "RN"]
SEAT_PROJECTION_BLOCS = ["NFP / gauche", "Ensemble / centre", "LR / droite", "RN et alliés", "Divers / autres"]
POLL_TO_SEAT_BLOC = {
    "gauche": "NFP / gauche",
    "centre": "Ensemble / centre",
    "droite": "LR / droite",
    "extrême_droite": "RN et alliés",
    "autres": "Divers / autres",
}
SEAT_TO_POLL_BLOC = {value: key for key, value in POLL_TO_SEAT_BLOC.items()}
POLLSTER_MARKERS = ["Ipsos", "Ifop", "Elabe", "OpinionWay", "Opinion", "Harris", "Cluster17", "Odoxa"]
NATIONAL_POLLSTERS_2024 = {
    "Ipsos",
    "Ifop",
    "Elabe",
    "OpinionWay",
    "Harris Interactive",
    "Cluster 17",
    "Odoxa",
}
FRENCH_MONTHS = {
    "mars": 3,
    "avril": 4,
    "juin": 6,
    "juillet": 7,
    "décembre": 12,
    "decembre": 12,
}


def _get_bloc_color(bloc_label: str) -> str:
    return get_political_color(None, bloc_label)


def _analysis_2024_layout_overrides(horizontal_legend: bool = False, extra_right_margin: int = 220) -> dict[str, object]:
    layout = dict(PLOT_LAYOUT_THEME)
    layout["margin"] = {
        **PLOT_LAYOUT_THEME.get("margin", {}),
        "r": extra_right_margin,
    }
    if horizontal_legend:
        layout["legend"] = {
            **PLOT_LAYOUT_THEME.get("legend", {}),
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0.0,
        }
        layout["margin"]["t"] = 96
        layout["margin"]["r"] = 60
    return layout


def _parse_french_date(fragment: str) -> pd.Timestamp | None:
    cleaned = " ".join(fragment.replace("er", "").split())
    match = re.match(r"(?:(\d{1,2})-)?(\d{1,2})\s+([a-zéûîôàèùç]+)\s+(20\d{2})", cleaned, flags=re.IGNORECASE)
    if match is None:
        return None
    day = int(match.group(2))
    month_label = match.group(3).lower()
    month = FRENCH_MONTHS.get(month_label)
    if month is None:
        return None
    year = int(match.group(4))
    try:
        return pd.Timestamp(year=year, month=month, day=day)
    except ValueError:
        return None


def _normalize_percent(token: str) -> float | None:
    cleaned = token.replace("%", "").replace("<", "").replace(">", "").replace("–", "-").strip()
    if not cleaned or cleaned == "—":
        return None
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_pollster_name(line: str) -> str | None:
    compact = " ".join(line.split())
    if not compact:
        return None
    if compact.startswith("Résultats"):
        return "Résultats"
    for marker in POLLSTER_MARKERS:
        if compact.startswith(marker):
            return marker
    return None


def _extract_2024_poll_rows() -> pd.DataFrame:
    reference_dir = get_reference_dir(Path.cwd())
    frame = load_legislative_2024_national_polls_from_wiki_tables(reference_dir)
    if frame.empty:
        return pd.DataFrame()
    return (
        frame.rename(columns={"normalized_bloc": "bloc_label"})
        .sort_values(["bloc_label", "publication_date", "polling_company"])
        .reset_index(drop=True)
    )


def _read_legislative_2024_wiki_tables() -> pd.DataFrame:
    candidates = [
        Path.cwd() / "sondages_legislatives_2024_wikipedia_tables.csv",
        Path(__file__).resolve().parents[4] / "sondages_legislatives_2024_wikipedia_tables.csv",
    ]
    for path in candidates:
        if path.exists():
            return pd.read_csv(path)
    return pd.DataFrame()


def _parse_seat_range(token: object) -> tuple[int, int] | None:
    text = str(token).strip()
    if not text or text in {"nan", "—", "— (-)"}:
        return None
    match = re.search(r"(\d+)\s*[–-]\s*(\d+)", text)
    if match is not None:
        return int(match.group(1)), int(match.group(2))
    single_match = re.match(r"(\d+)\b", text)
    if single_match is not None:
        value = int(single_match.group(1))
        return value, value
    return None


def _extract_2024_seat_projection_rows() -> pd.DataFrame:
    frame = _read_legislative_2024_wiki_tables()
    if frame.empty or "section" not in frame.columns:
        return pd.DataFrame()

    pollster_column = "Sondeur | Sondeur"
    date_column = "Date | Date"
    if pollster_column not in frame.columns or date_column not in frame.columns:
        return pd.DataFrame()

    projections = frame.loc[frame["section"] == "Projections en sièges"].copy()
    projections[pollster_column] = projections[pollster_column].fillna("").astype(str).str.strip()
    projections[date_column] = projections[date_column].fillna("").astype(str).str.strip()
    projections = projections.loc[projections[pollster_column].isin(NATIONAL_POLLSTERS_2024)].copy()
    if projections.empty:
        return pd.DataFrame()

    component_columns = {
        "NFP / gauche": [
            "NFP[a] (LFI-PCF-EELV-PS) | Unnamed: 3_level_1",
            "DVG | Unnamed: 4_level_1",
        ],
        "Ensemble / centre": [
            "ENS (RE-MoDem-HOR-PRV-UDI) | Unnamed: 5_level_1",
        ],
        "LR / droite": [
            "DVD | Unnamed: 6_level_1",
            "LR[b] | Unnamed: 7_level_1",
        ],
        "RN et alliés": [
            "RN et alliés | Unnamed: 8_level_1",
            "UPF (DLF-LP) | Unnamed: 9_level_1",
        ],
        "Divers / autres": [
            "Autres | Unnamed: 10_level_1",
        ],
    }

    rows: list[dict[str, object]] = []
    for _, row in projections.iterrows():
        parsed_date = _parse_french_date(str(row[date_column]))
        if parsed_date is None:
            continue
        for bloc_name, columns in component_columns.items():
            low_total = 0
            high_total = 0
            found_component = False
            seen_ranges: set[tuple[int, int]] = set()
            for column in columns:
                if column not in projections.columns:
                    continue
                parsed_range = _parse_seat_range(row[column])
                if parsed_range is None:
                    continue
                # Some Wikipedia seat tables repeat the main bloc range in a sub-column
                # instead of adding a distinct sub-alliance; do not sum duplicates.
                if parsed_range in seen_ranges:
                    continue
                seen_ranges.add(parsed_range)
                low_total += parsed_range[0]
                high_total += parsed_range[1]
                found_component = True
            if not found_component:
                continue
            rows.append(
                {
                    "publication_date": parsed_date,
                    "polling_company": row[pollster_column],
                    "bloc_name": bloc_name,
                    "seat_projection_low": low_total,
                    "seat_projection_high": high_total,
                    "seat_projection_mid": (low_total + high_total) / 2.0,
                }
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame.loc[frame["publication_date"] >= pd.Timestamp("2024-06-09")].copy()
    frame = frame.drop_duplicates(
        subset=["publication_date", "polling_company", "bloc_name", "seat_projection_low", "seat_projection_high"]
    )
    return frame.sort_values(["publication_date", "polling_company", "bloc_name"]).reset_index(drop=True)


def _render_complete_zip_2024_extracts() -> None:
    visual_rows = load_complete_visual_rows("2024")
    layout_lines = load_complete_layout_lines("2024")
    if visual_rows.empty and layout_lines.empty:
        return

    st.markdown("**Données complètes importées depuis le zip 2024**")
    tab1, tab2, tab3 = st.tabs(["Sondages nationaux", "Projections en sièges", "Structure source"])

    with tab1:
        national_rows = visual_rows.loc[
            visual_rows["row_text"].fillna("").str.contains(
                r"Résultats|Ipsos|Harris|Ifop|Elabe|Opinion|Odoxa|Cluster17|NFP|ENS|RN|LR",
                case=False,
                regex=True,
                na=False,
            )
        ][["page", "visual_row", "row_text", "source_url"]].head(140)
        st.dataframe(
            national_rows,
            width="stretch",
            hide_index=True,
            column_config={"source_url": st.column_config.LinkColumn("Source")},
        )

    with tab2:
        seat_rows = visual_rows.loc[
            visual_rows["row_text"].fillna("").str.contains(
                r"sièges|projection|NFP|ENS|UPF|RN|Ifop|OpinionWay|Résultats",
                case=False,
                regex=True,
                na=False,
            )
        ][["page", "visual_row", "row_text", "source_url"]].head(140)
        st.dataframe(
            seat_rows,
            width="stretch",
            hide_index=True,
            column_config={"source_url": st.column_config.LinkColumn("Source")},
        )

    with tab3:
        source_lines = layout_lines.loc[
            layout_lines["raw_line"].fillna("").str.contains(
                r"Sondeur|Résultats|projections en sièges|second tour|triangulaires",
                case=False,
                regex=True,
                na=False,
            )
        ][["page", "layout_line", "raw_line", "source_url"]]
        st.dataframe(
            source_lines,
            width="stretch",
            hide_index=True,
            column_config={"source_url": st.column_config.LinkColumn("Source")},
        )


def _render_2024_smoothed_polls() -> None:
    polls = _extract_2024_poll_rows()
    if polls.empty:
        st.warning("Le tableau national 2024 n’a pas pu être relu depuis le CSV structuré exporté de Wikipédia.")
        return
    min_date = polls["publication_date"].min().date() if polls["publication_date"].notna().any() else date.today()
    max_date = polls["publication_date"].max().date() if polls["publication_date"].notna().any() else date.today()
    selected_period = st.date_input(
        "Période 2024 affichée",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="analysis_2024_period",
    )
    if isinstance(selected_period, tuple) and len(selected_period) == 2:
        polls = polls.loc[
            polls["publication_date"].between(
                pd.Timestamp(selected_period[0]),
                pd.Timestamp(selected_period[1]),
                inclusive="both",
            )
        ].copy()
    if polls.empty:
        st.warning("Aucune donnée 2024 disponible pour cette période.")
        return

    label_order = ["gauche", "centre", "extrême_droite", "droite", "autres"]
    figure = go.Figure()
    visible_labels: list[str] = []
    for bloc_label, group in polls.groupby("bloc_label", dropna=False):
        visible_labels.append(str(bloc_label))
        color = _get_bloc_color(str(bloc_label))
        ordered = group.sort_values("publication_date")
        figure.add_trace(
            go.Scatter(
                x=ordered["publication_date"],
                y=ordered["estimate_percent"],
                mode="markers",
                marker={"size": 5, "color": color, "opacity": 0.35},
                name=f"{bloc_label} - points",
                legendgroup=str(bloc_label),
                showlegend=False,
                customdata=ordered[["polling_company"]].to_numpy(),
                hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<br>Institut: %{customdata[0]}<extra></extra>",
            )
        )
        smoothed = build_lowess_curve(ordered, "estimate_percent", frac=0.34)
        if smoothed is None:
            continue
        figure.add_trace(
            go.Scatter(
                x=smoothed["publication_date"],
                y=smoothed["score_smooth"],
                mode="lines",
                line={"width": 2.2, "color": color},
                name=str(bloc_label),
                legendgroup=str(bloc_label),
                showlegend=True,
                hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<extra></extra>",
            )
        )

    figure.update_layout(
        title="Législatives 2024 · ajustement polynomial des sondages nationaux par bloc",
        xaxis_title="Date de publication",
        yaxis_title="Intentions de vote (%)",
        **_analysis_2024_layout_overrides(horizontal_legend=False, extra_right_margin=180),
    )
    figure.update_yaxes(ticksuffix=" %")
    figure.add_vline(x=pd.Timestamp("2024-06-09"), line_width=1, line_color="#999999", opacity=0.55)
    figure.add_vline(x=pd.Timestamp("2024-06-30"), line_width=1, line_color="#999999", opacity=0.55)
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})

    st.caption(
        "Courbe relue depuis `sondages_legislatives_2024_wikipedia_tables.csv`, "
        "donc depuis les tableaux Wikipédia structurés plutôt que depuis les `visual_rows` du PDF."
    )

    available_order = [label for label in label_order if label in visible_labels]
    if available_order:
        st.caption("Blocs visibles : " + ", ".join(available_order))


def _render_2024_poll_vs_seats_timeline(
    polls: pd.DataFrame,
    seat_projections: pd.DataFrame,
    final_seats: pd.DataFrame,
    reference_dir: Path,
) -> None:
    if polls.empty or seat_projections.empty or final_seats.empty:
        return

    final_vote_lookup = {}
    wiki_results = load_legislative_2024_national_results_from_wiki_tables(reference_dir)
    if not wiki_results.empty:
        final_vote_lookup = wiki_results.set_index("bloc_label")["actual_result"].to_dict()
    if not final_vote_lookup:
        final_vote_lookup = final_seats.set_index("bloc_label")["vote_share_percent"].to_dict()

    final_seat_lookup = final_seats.set_index("bloc_label")["seats"].to_dict()
    comparison_options = [bloc for bloc in SEAT_PROJECTION_BLOCS if bloc in seat_projections["bloc_name"].unique()]
    if not comparison_options:
        return

    selected_seat_bloc = st.selectbox(
        "Bloc pour comparer sondages, projections de sièges et résultat obtenu",
        comparison_options,
        key="analysis_2024_vote_seat_comparison_bloc",
    )
    selected_poll_bloc = SEAT_TO_POLL_BLOC.get(selected_seat_bloc)
    if selected_poll_bloc is None:
        return

    poll_frame = polls.loc[polls["bloc_label"] == selected_poll_bloc].copy()
    seat_frame = seat_projections.loc[seat_projections["bloc_name"] == selected_seat_bloc].copy()
    if poll_frame.empty or seat_frame.empty:
        return

    vote_result = final_vote_lookup.get(selected_poll_bloc)
    seat_result = final_seat_lookup.get(selected_poll_bloc)
    color = _get_bloc_color(str(selected_poll_bloc))

    comparison_chart = go.Figure()
    comparison_chart.add_trace(
        go.Scatter(
            x=poll_frame["publication_date"],
            y=poll_frame["estimate_percent"],
            mode="markers",
            marker={"size": 6, "color": color, "opacity": 0.35},
            name="Sondages (%)",
            yaxis="y1",
            customdata=poll_frame[["polling_company"]].to_numpy(),
            hovertemplate="%{x|%d/%m/%Y}<br>Sondage: %{y:.1f}%<br>Institut: %{customdata[0]}<extra></extra>",
        )
    )
    smooth_polls = build_lowess_curve(poll_frame.sort_values("publication_date"), "estimate_percent", frac=0.34)
    if smooth_polls is not None:
        comparison_chart.add_trace(
            go.Scatter(
                x=smooth_polls["publication_date"],
                y=smooth_polls["score_smooth"],
                mode="lines",
                line={"width": 2.4, "color": color},
                name="Tendance sondages (%)",
                yaxis="y1",
                hovertemplate="%{x|%d/%m/%Y}<br>Tendance: %{y:.1f}%<extra></extra>",
            )
        )

    comparison_chart.add_trace(
        go.Scatter(
            x=seat_frame["publication_date"],
            y=seat_frame["seat_projection_mid"],
            mode="markers",
            marker={"size": 7, "symbol": "diamond", "color": "#7c5ea8", "opacity": 0.45},
            name="Projection sièges",
            yaxis="y2",
            customdata=seat_frame[["polling_company", "seat_projection_low", "seat_projection_high"]].to_numpy(),
            hovertemplate="%{x|%d/%m/%Y}<br>Projection médiane: %{y:.1f}<br>Institut: %{customdata[0]}<br>Fourchette: %{customdata[1]}-%{customdata[2]}<extra></extra>",
        )
    )
    smooth_seats = build_lowess_curve(
        seat_frame.sort_values("publication_date").rename(columns={"seat_projection_mid": "estimate_percent"}),
        "estimate_percent",
        frac=0.40,
    )
    if smooth_seats is not None:
        comparison_chart.add_trace(
            go.Scatter(
                x=smooth_seats["publication_date"],
                y=smooth_seats["score_smooth"],
                mode="lines",
                line={"width": 2.4, "color": "#7c5ea8"},
                name="Tendance sièges",
                yaxis="y2",
                hovertemplate="%{x|%d/%m/%Y}<br>Tendance sièges: %{y:.1f}<extra></extra>",
            )
        )

    if vote_result is not None:
        comparison_chart.add_shape(
            type="line",
            x0=0,
            x1=1,
            xref="paper",
            y0=float(vote_result),
            y1=float(vote_result),
            yref="y",
            line={"width": 1, "dash": "dot", "color": color},
            opacity=0.8,
        )
        comparison_chart.add_annotation(
            x=0.01,
            xref="paper",
            y=float(vote_result),
            yref="y",
            text=f"Résultat voix: {float(vote_result):.2f}%",
            showarrow=False,
            font={"color": color},
            bgcolor="rgba(255,255,255,0.7)",
        )
    if seat_result is not None:
        comparison_chart.add_shape(
            type="line",
            x0=0,
            x1=1,
            xref="paper",
            y0=float(seat_result),
            y1=float(seat_result),
            yref="y2",
            line={"width": 1, "dash": "dash", "color": "#7c5ea8"},
            opacity=0.8,
        )
        comparison_chart.add_annotation(
            x=0.99,
            xref="paper",
            y=float(seat_result),
            yref="y2",
            text=f"Sièges obtenus: {int(seat_result)}",
            showarrow=False,
            xanchor="right",
            font={"color": "#7c5ea8"},
            bgcolor="rgba(255,255,255,0.7)",
        )

    comparison_layout = _analysis_2024_layout_overrides(horizontal_legend=True, extra_right_margin=60)
    comparison_layout["xaxis"] = {
        **PLOT_LAYOUT_THEME.get("xaxis", {}),
        "title": {"text": "Date de publication"},
    }
    comparison_layout["yaxis"] = {
        **PLOT_LAYOUT_THEME.get("yaxis", {}),
        "title": {"text": "Intentions de vote (%)"},
        "ticksuffix": " %",
    }
    comparison_layout["yaxis2"] = {
        "title": {"text": "Sièges projetés"},
        "overlaying": "y",
        "side": "right",
    }
    comparison_chart.update_layout(
        title=f"Législatives 2024 · {selected_seat_bloc} : sondages vs temps, sièges et résultat obtenu",
        **comparison_layout,
    )
    comparison_chart.add_vline(x=pd.Timestamp("2024-06-30"), line_width=1, line_color="#999999", opacity=0.55)
    comparison_chart.add_vline(x=pd.Timestamp("2024-07-07"), line_width=1, line_color="#999999", opacity=0.55)
    st.plotly_chart(comparison_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    latest_poll = poll_frame.sort_values("publication_date").tail(1)["estimate_percent"].mean()
    latest_seat = seat_frame.sort_values("publication_date").tail(1)["seat_projection_mid"].mean()
    comparison_table = pd.DataFrame(
        [
            {
                "Bloc": selected_seat_bloc,
                "Dernier sondage (%)": latest_poll,
                "Résultat voix (%)": vote_result,
                "Écart sondage - résultat (pts)": None if vote_result is None else latest_poll - float(vote_result),
                "Dernière projection sièges": latest_seat,
                "Sièges obtenus": seat_result,
                "Écart projection - obtenu": None if seat_result is None else latest_seat - float(seat_result),
            }
        ]
    )
    st.dataframe(
        comparison_table,
        width="stretch",
        hide_index=True,
        column_config={
            "Dernier sondage (%)": st.column_config.NumberColumn("Dernier sondage (%)", format="%.2f"),
            "Résultat voix (%)": st.column_config.NumberColumn("Résultat voix (%)", format="%.2f"),
            "Écart sondage - résultat (pts)": st.column_config.NumberColumn("Écart sondage - résultat (pts)", format="%.2f"),
            "Dernière projection sièges": st.column_config.NumberColumn("Dernière projection sièges", format="%.1f"),
            "Sièges obtenus": st.column_config.NumberColumn("Sièges obtenus", format="%d"),
            "Écart projection - obtenu": st.column_config.NumberColumn("Écart projection - obtenu", format="%.1f"),
        },
    )

    summary_rows: list[dict[str, object]] = []
    for seat_bloc in comparison_options:
        poll_bloc = SEAT_TO_POLL_BLOC.get(seat_bloc)
        if poll_bloc is None:
            continue
        bloc_poll_frame = polls.loc[polls["bloc_label"] == poll_bloc].sort_values("publication_date")
        bloc_seat_frame = seat_projections.loc[seat_projections["bloc_name"] == seat_bloc].sort_values("publication_date")
        if bloc_poll_frame.empty or bloc_seat_frame.empty:
            continue
        last_poll_value = float(bloc_poll_frame.iloc[-1]["estimate_percent"])
        last_poll_date = bloc_poll_frame.iloc[-1]["publication_date"]
        last_seat_value = float(bloc_seat_frame.iloc[-1]["seat_projection_mid"])
        last_seat_date = bloc_seat_frame.iloc[-1]["publication_date"]
        bloc_vote_result = final_vote_lookup.get(poll_bloc)
        bloc_seat_result = final_seat_lookup.get(poll_bloc)
        summary_rows.append(
            {
                "Bloc": seat_bloc,
                "Dernier point sondage": last_poll_date,
                "Dernier sondage (%)": last_poll_value,
                "Résultat voix (%)": bloc_vote_result,
                "Écart sondage - résultat (pts)": None if bloc_vote_result is None else last_poll_value - float(bloc_vote_result),
                "Dernier point sièges": last_seat_date,
                "Dernière projection sièges": last_seat_value,
                "Sièges obtenus": bloc_seat_result,
                "Écart projection - obtenu": None if bloc_seat_result is None else last_seat_value - float(bloc_seat_result),
            }
        )
    if summary_rows:
        st.markdown("**Synthèse bloc par bloc**")
        summary_table = pd.DataFrame(summary_rows).sort_values("Bloc")
        st.dataframe(
            summary_table,
            width="stretch",
            hide_index=True,
            column_config={
                "Dernier point sondage": st.column_config.DateColumn("Dernier point sondage", format="DD/MM/YYYY"),
                "Dernier sondage (%)": st.column_config.NumberColumn("Dernier sondage (%)", format="%.2f"),
                "Résultat voix (%)": st.column_config.NumberColumn("Résultat voix (%)", format="%.2f"),
                "Écart sondage - résultat (pts)": st.column_config.NumberColumn("Écart sondage - résultat (pts)", format="%.2f"),
                "Dernier point sièges": st.column_config.DateColumn("Dernier point sièges", format="DD/MM/YYYY"),
                "Dernière projection sièges": st.column_config.NumberColumn("Dernière projection sièges", format="%.1f"),
                "Sièges obtenus": st.column_config.NumberColumn("Sièges obtenus", format="%d"),
                "Écart projection - obtenu": st.column_config.NumberColumn("Écart projection - obtenu", format="%.1f"),
            },
        )


def _render_2024_violin_distributions(polls: pd.DataFrame, seat_projections: pd.DataFrame) -> None:
    if polls.empty and seat_projections.empty:
        return

    left, right = st.columns(2)
    with left:
        st.markdown("**Violons sondages 2024**")
        if polls.empty:
            st.info("Aucune distribution de sondages disponible.")
        else:
            poll_options = sorted(polls["bloc_label"].dropna().astype(str).unique().tolist())
            poll_bloc = st.selectbox(
                "Bloc sondages",
                poll_options,
                key="analysis_2024_violin_poll_bloc",
            )
            poll_frame = polls.loc[polls["bloc_label"] == poll_bloc].copy()
            if not poll_frame.empty:
                poll_frame["date_label"] = poll_frame["publication_date"].dt.strftime("%d/%m")
                poll_color = _get_bloc_color(poll_bloc)
                poll_violin = go.Figure()
                poll_violin.add_trace(
                    go.Violin(
                        x=poll_frame["date_label"],
                        y=poll_frame["estimate_percent"],
                        box_visible=True,
                        meanline_visible=True,
                        points="all",
                        pointpos=0,
                        jitter=0.08,
                        marker={"size": 5, "opacity": 0.45, "color": poll_color},
                        line={"color": poll_color},
                        fillcolor=poll_color,
                        opacity=0.55,
                        hovertemplate="Date: %{x}<br>Sondage: %{y:.1f}%<extra></extra>",
                        name=poll_bloc,
                        showlegend=False,
                    )
                )
                poll_violin.update_layout(
                    title=f"Législatives 2024 · distribution des sondages · {poll_bloc}",
                    **_analysis_2024_layout_overrides(horizontal_legend=False, extra_right_margin=80),
                )
                poll_violin.update_xaxes(title_text="Date de publication")
                poll_violin.update_yaxes(title_text="Intentions de vote (%)", ticksuffix=" %")
                st.plotly_chart(poll_violin, width="stretch", config={"displayModeBar": False, "responsive": True})

    with right:
        st.markdown("**Violons projections sièges 2024**")
        if seat_projections.empty:
            st.info("Aucune distribution de projections en sièges disponible.")
        else:
            seat_options = sorted(seat_projections["bloc_name"].dropna().astype(str).unique().tolist())
            seat_bloc = st.selectbox(
                "Bloc sièges",
                seat_options,
                key="analysis_2024_violin_seat_bloc",
            )
            seat_frame = seat_projections.loc[seat_projections["bloc_name"] == seat_bloc].copy()
            if not seat_frame.empty:
                seat_frame["date_label"] = seat_frame["publication_date"].dt.strftime("%d/%m")
                seat_color = _get_bloc_color(SEAT_TO_POLL_BLOC.get(seat_bloc, "autres"))
                seat_violin = go.Figure()
                seat_violin.add_trace(
                    go.Violin(
                        x=seat_frame["date_label"],
                        y=seat_frame["seat_projection_mid"],
                        box_visible=True,
                        meanline_visible=True,
                        points="all",
                        pointpos=0,
                        jitter=0.08,
                        marker={"size": 5, "opacity": 0.45, "color": seat_color},
                        line={"color": seat_color},
                        fillcolor=seat_color,
                        opacity=0.55,
                        hovertemplate="Date: %{x}<br>Projection médiane: %{y:.1f}<extra></extra>",
                        name=seat_bloc,
                        showlegend=False,
                    )
                )
                seat_violin.update_layout(
                    title=f"Législatives 2024 · distribution des sièges projetés · {seat_bloc}",
                    **_analysis_2024_layout_overrides(horizontal_legend=False, extra_right_margin=80),
                )
                seat_violin.update_xaxes(title_text="Date de publication")
                seat_violin.update_yaxes(title_text="Sièges projetés")
                st.plotly_chart(seat_violin, width="stretch", config={"displayModeBar": False, "responsive": True})


def render_analysis_2024_page() -> None:
    st.subheader("Analyse législatives 2024")
    reference_dir = get_reference_dir(Path.cwd())
    votes = load_legislative_2024_results(reference_dir)
    seats = load_legislative_2024_seats(reference_dir)
    if votes.empty or seats.empty:
        st.info("Les données de blocs et de sièges 2024 ne sont pas disponibles.")
        return

    final_seats = seats.loc[seats["election_round"] == "second_round"].copy()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Blocs suivis", int(final_seats["bloc_label"].nunique()))
    col2.metric("Sièges", int(final_seats["seats"].sum()))
    col3.metric("Triangulaires", SECOND_ROUND_TRIANGULAIRES)
    col4.metric("Désistements", SECOND_ROUND_DESISTEMENTS)

    st.markdown(
        """
        Cette vue lit les législatives 2024 d’abord comme un scrutin de blocs et de sièges.
        Le graphe du haut reproduit la lecture visuelle des sondages nationaux, puis la partie basse montre
        comment ces blocs se transforment en pouvoir parlementaire.
        """
    )

    _render_2024_smoothed_polls()
    polls = _extract_2024_poll_rows()

    seat_projections = _extract_2024_seat_projection_rows()
    if not seat_projections.empty and "analysis_2024_period" in st.session_state:
        selected_period = st.session_state["analysis_2024_period"]
        if isinstance(selected_period, tuple) and len(selected_period) == 2:
            seat_projections = seat_projections.loc[
                seat_projections["publication_date"].between(
                    pd.Timestamp(selected_period[0]),
                    pd.Timestamp(selected_period[1]),
                    inclusive="both",
                )
            ].copy()
    final_lookup = {
        "NFP / gauche": 193,
        "Ensemble / centre": 165,
        "LR / droite": 66,
        "RN et alliés": 143,
        "Divers / autres": 10,
    }
    if not seat_projections.empty:
        st.markdown("**Distributions 2024 par date**")
        _render_2024_violin_distributions(polls, seat_projections)

        st.markdown("**Sondages vs temps, sièges et résultat obtenu**")
        _render_2024_poll_vs_seats_timeline(polls, seat_projections, final_seats, reference_dir)

        st.markdown("**Projections en sièges par institut**")
        latest_projection = (
            seat_projections.sort_values(["publication_date", "polling_company"])
            .groupby(["polling_company", "bloc_name"], dropna=False)
            .tail(1)
            .copy()
        )
        latest_projection["sièges finaux"] = latest_projection["bloc_name"].map(final_lookup)
        latest_projection["écart médian"] = latest_projection["seat_projection_mid"] - latest_projection["sièges finaux"]
        projection_table = latest_projection.rename(
            columns={
                "publication_date": "Publication",
                "polling_company": "Institut",
                "bloc_name": "Bloc",
                "seat_projection_low": "Projection basse",
                "seat_projection_high": "Projection haute",
                "seat_projection_mid": "Projection médiane",
                "sièges finaux": "Sièges finaux",
                "écart médian": "Écart médian",
            }
        ).sort_values(["Publication", "Institut", "Bloc"], ascending=[False, True, True])
        st.dataframe(
            projection_table,
            width="stretch",
            hide_index=True,
            column_config={
                "Projection basse": st.column_config.NumberColumn("Projection basse", format="%d"),
                "Projection haute": st.column_config.NumberColumn("Projection haute", format="%d"),
                "Projection médiane": st.column_config.NumberColumn("Projection médiane", format="%.1f"),
                "Sièges finaux": st.column_config.NumberColumn("Sièges finaux", format="%d"),
                "Écart médian": st.column_config.NumberColumn("Écart médian", format="%.1f"),
            },
        )

        focus_bloc = st.selectbox(
            "Bloc pour la lecture des projections en sièges",
            SEAT_PROJECTION_BLOCS,
            key="analysis_2024_projection_bloc",
        )
        bloc_frame = seat_projections.loc[seat_projections["bloc_name"] == focus_bloc].copy()
        if not bloc_frame.empty:
            projection_chart = go.Figure()
            projection_chart.add_trace(
                go.Scatter(
                    x=bloc_frame["publication_date"],
                    y=bloc_frame["seat_projection_mid"],
                    mode="markers",
                    marker={"size": 7, "color": "#7c5ea8", "opacity": 0.45},
                    customdata=bloc_frame[["polling_company", "seat_projection_low", "seat_projection_high"]].to_numpy(),
                    showlegend=False,
                    hovertemplate="%{x|%d/%m/%Y}<br>Médiane: %{y:.1f}<br>Institut: %{customdata[0]}<br>Fourchette: %{customdata[1]}-%{customdata[2]}<extra></extra>",
                )
            )
            smooth_projection = build_lowess_curve(
                bloc_frame.rename(columns={"seat_projection_mid": "estimate_percent"}),
                "estimate_percent",
                frac=0.40,
            )
            if smooth_projection is not None:
                projection_chart.add_trace(
                    go.Scatter(
                        x=smooth_projection["publication_date"],
                        y=smooth_projection["score_smooth"],
                        mode="lines",
                        line={"width": 2.4, "color": "#7c5ea8"},
                        name="Projection lissée",
                        showlegend=False,
                    )
                )
            projection_chart.add_hline(
                y=final_lookup[focus_bloc],
                line_width=1,
                line_dash="dot",
                line_color="#333333",
                opacity=0.7,
            )
            projection_chart.update_layout(
                title=f"Projections en sièges 2024 · {focus_bloc}",
                xaxis_title="Date de publication",
                yaxis_title="Sièges projetés",
                **_analysis_2024_layout_overrides(horizontal_legend=False, extra_right_margin=120),
            )
            st.plotly_chart(projection_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    ordered = final_seats.sort_values("seats", ascending=False)
    seat_share_chart = go.Figure()
    seat_share_chart.add_bar(
        x=ordered["bloc_name"],
        y=ordered["seat_share_percent"],
        name="Part des sièges",
        marker_color="#7c5ea8",
        customdata=ordered[["seats"]].to_numpy(),
        hovertemplate="%{x}<br>Part des sièges: %{y:.2f}%<br>Sièges: %{customdata[0]}<extra></extra>",
    )
    seat_share_chart.update_layout(
        barmode="group",
        title="Législatives 2024 · part des sièges par bloc",
        xaxis_title="Bloc",
        yaxis_title="Part (%)",
        **_analysis_2024_layout_overrides(horizontal_legend=False, extra_right_margin=120),
    )
    seat_share_chart.update_yaxes(ticksuffix=" %")
    st.plotly_chart(seat_share_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    gap_chart = go.Figure()
    gap_chart.add_bar(
        x=ordered["bloc_name"],
        y=ordered["vote_seat_gap"],
        marker_color=[
            "#2d6a4f" if value > 0 else "#ae2d3c"
            for value in ordered["vote_seat_gap"]
        ],
        name="Écart sièges - voix",
    )
    gap_chart.update_layout(
        title="Effet majoritaire 2024 · écart sièges moins voix",
        xaxis_title="Bloc",
        yaxis_title="Écart (points)",
        **_analysis_2024_layout_overrides(horizontal_legend=False, extra_right_margin=120),
    )
    gap_chart.update_yaxes(ticksuffix=" pts")
    st.plotly_chart(gap_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    detailed = final_seats[
        [
            "bloc_name",
            "seats",
            "seat_share_percent",
            "vote_seat_gap",
            "source_url",
        ]
    ].rename(
        columns={
            "bloc_name": "Bloc",
            "seats": "Sièges",
            "seat_share_percent": "Part des sièges",
            "vote_seat_gap": "Effet majoritaire net",
            "source_url": "Lien source",
        }
    )
    st.dataframe(
        detailed,
        width="stretch",
        hide_index=True,
        column_config={
            "Sièges": st.column_config.NumberColumn("Sièges", format="%d"),
            "Part des sièges": st.column_config.NumberColumn("Part des sièges", format="%.2f %%"),
            "Effet majoritaire net": st.column_config.NumberColumn("Effet majoritaire net", format="%.2f pts"),
            "Lien source": st.column_config.LinkColumn("Lien source"),
        },
    )

    left, centre, far_right = st.columns(3)
    left.markdown(
        """
        **Effet majoritaire**

        Le NFP et le centre convertissent mieux leur rapport de force en sièges au second tour.
        Le RN et ses alliés restent sous-performants en sièges relativement à leur poids électoral.
        """
    )
    centre.markdown(
        f"""
        **Triangulaires et retraits**

        `501` sièges ont été attribués au second tour, avec `89` triangulaires recensées après retraits.
        Les désistements ont réduit la prime mécanique du premier bloc en voix.

        [Source triangulaires]({TRIANGULAIRES_SOURCE_URL})
        """
    )
    far_right.markdown(
        f"""
        **Conséquence pour 2027**

        Pour les projections de second tour, 2024 ne peut pas être lu comme un simple score national.
        Il faut intégrer la capacité d’un bloc à agréger des réserves et à convertir des voix en sièges.

        [Source désistements]({DESISTEMENTS_SOURCE_URL})
        """
    )

    with st.expander("Détail complet 2024", expanded=False):
        merged = seats.merge(
            votes[["election_round", "bloc_label", "percent_expressed"]],
            on=["election_round", "bloc_label"],
            how="left",
        ).rename(columns={"percent_expressed": "vote_share_secondary"})
        st.dataframe(
            merged,
            width="stretch",
            hide_index=True,
            column_config={"source_url": st.column_config.LinkColumn("Lien source")},
        )

    _render_complete_zip_2024_extracts()
