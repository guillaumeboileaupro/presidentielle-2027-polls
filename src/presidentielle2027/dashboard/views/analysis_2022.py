from __future__ import annotations

from datetime import date
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from presidentielle2027.analytics.historical_corrections import (
    FIRST_ROUND_ELECTION_DATE,
    compute_first_round_correction_context,
    get_reference_dir,
    load_historical_2022_results,
)
from presidentielle2027.analytics.trends import build_lowess_curve
from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME
from presidentielle2027.dashboard.table_views import clean_user_facing_frame, rename_user_facing_columns
from presidentielle2027.dashboard.wiki_complete_zip import load_complete_layout_lines, load_complete_visual_rows


SECOND_ROUND_ELECTION_DATE = pd.Timestamp("2022-04-24")
WIKI_2022_TABLES_FILE = Path("sondages_presidentielle_2022_wikipedia_tables.csv")
FRENCH_MONTHS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}

WIKI_2022_FORCE_MAP = {
    "Arthaud (LO)": ("EXG", "Nathalie Arthaud", "far_left"),
    "Poutou (NPA)": ("EXG", "Philippe Poutou", "far_left"),
    "Roussel (PCF)": ("PCF", "Fabien Roussel", "left"),
    "Mélenchon (LFI)": ("LFI", "Jean-Luc Mélenchon", "left"),
    "Hidalgo (PS)": ("PS-PP", "Anne Hidalgo", "left"),
    "Jadot (EELV)": ("EELV", "Yannick Jadot", "green"),
    "Macron (LREM)": ("ENS", "Emmanuel Macron", "centre"),
    "Pécresse (LR)": ("LR", "Valérie Pécresse", "right"),
    "Lassalle (RES)": ("DIV", "Jean Lassalle", "autres"),
    "Dupont-Aignan (DLF)": ("DLF", "Nicolas Dupont-Aignan", "sovereigntist_right"),
    "Le Pen (RN)": ("RN", "Marine Le Pen", "far_right"),
    "Zemmour (REC)": ("REC", "Éric Zemmour", "far_right"),
    "Taubira (DVG)": ("PS-PP", "Christiane Taubira", "left"),
}


def _parse_french_date(fragment: str) -> pd.Timestamp | None:
    cleaned = " ".join(fragment.replace("1er", "1").split())
    parsed = pd.to_datetime(cleaned, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed)


def _to_float_percent(value: str) -> float | None:
    cleaned = value.replace("%", "").replace(",", ".").replace("<", "").strip()
    if not cleaned or cleaned == "—":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_end_date_2022(fragment: object, fallback_year: int | None = None) -> pd.Timestamp | None:
    if fragment is None or pd.isna(fragment):
        return None
    cleaned = " ".join(str(fragment).replace("1er", "1").split())
    if not cleaned:
        return None
    cleaned = cleaned.lower()
    year_match = re.search(r"(20\d{2})", cleaned)
    year = int(year_match.group(1)) if year_match else fallback_year
    if year is None:
        return None
    month_names = "|".join(FRENCH_MONTHS.keys())
    month_matches = list(re.finditer(month_names, cleaned, flags=re.IGNORECASE))
    if not month_matches:
        return None
    month_name = month_matches[-1].group(0).lower()
    month = FRENCH_MONTHS[month_name]
    prefix = cleaned[:month_matches[-1].start()]
    day_numbers = re.findall(r"\d{1,2}", prefix)
    if not day_numbers:
        return None
    day = int(day_numbers[-1])
    try:
        return pd.Timestamp(year=year, month=month, day=day)
    except ValueError:
        return None


def _load_2022_first_round_from_wiki_tables(include_archive: bool = False) -> pd.DataFrame:
    path = Path.cwd() / WIKI_2022_TABLES_FILE
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    relevant_sections = {
        "Sondages réalisés après la publication de la liste officielle des candidats",
        "Mars 2022",
        "Février 2022",
        "Janvier 2022",
    }
    if include_archive:
        relevant_sections.update({"Année 2021", "Années 2017-2020"})
    frame = frame.loc[frame["section"].isin(relevant_sections)].copy()
    if frame.empty:
        return pd.DataFrame()

    source_columns = [column for column in frame.columns if "Sondeur | Sondeur | Sondeur" in column]
    date_columns = [column for column in frame.columns if "Date" in column]
    sample_columns = [column for column in frame.columns if "Échantillon" in column]

    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        row_map = row.to_dict()
        section_name = str(row_map.get("section", "")).strip()
        pollster = next((str(row_map[column]).strip() for column in source_columns if pd.notna(row_map.get(column)) and str(row_map.get(column)).strip()), "")
        date_text = next((str(row_map[column]).strip() for column in date_columns if pd.notna(row_map.get(column)) and str(row_map.get(column)).strip()), "")
        sample_text = next((str(row_map[column]).strip() for column in sample_columns if pd.notna(row_map.get(column)) and str(row_map.get(column)).strip()), "")
        if not pollster or pollster == "nan":
            continue
        if any(marker in pollster for marker in ["Arrêt de publication", "annonce sa candidature", "retire sa candidature", "remporte la Primaire"]):
            continue
        fallback_year = 2022
        if section_name == "Année 2021":
            fallback_year = 2021
        publication_date = _parse_end_date_2022(date_text, fallback_year=fallback_year)
        if publication_date is None:
            continue
        sample_size = pd.to_numeric(sample_text.replace(" ", "").split("[")[0], errors="coerce") if sample_text else pd.NA
        source_url = row_map.get("source_url", pd.NA)
        source_label = str(row_map.get("source_page", "Wikipédia 2022"))

        for column_name, (force_label, candidate_name, political_family) in WIKI_2022_FORCE_MAP.items():
            matching_column = next((column for column in frame.columns if column_name in column), None)
            if matching_column is None:
                continue
            value = row_map.get(matching_column)
            estimate = _to_float_percent(str(value)) if pd.notna(value) else None
            if estimate is None:
                continue
            rows.append(
                {
                    "fieldwork_start_date": publication_date,
                    "fieldwork_end_date": publication_date,
                    "sample_size": sample_size,
                    "pollster": pollster,
                    "source_url": source_url,
                    "source_label": source_label,
                    "force_label": force_label,
                    "candidate_name": candidate_name,
                    "political_family": political_family,
                    "estimate_percent": estimate,
                }
            )
    parsed = pd.DataFrame(rows)
    if parsed.empty:
        return parsed
    parsed["fieldwork_end_date"] = pd.to_datetime(parsed["fieldwork_end_date"], errors="coerce")
    parsed["fieldwork_start_date"] = pd.to_datetime(parsed["fieldwork_start_date"], errors="coerce")
    return parsed.drop_duplicates().sort_values(["fieldwork_end_date", "pollster", "force_label"]).reset_index(drop=True)


def _parse_second_round_macron_lepen() -> pd.DataFrame:
    visual_rows = load_complete_visual_rows("2022")
    if visual_rows.empty:
        return pd.DataFrame()

    start_matches = visual_rows.index[
        visual_rows["row_text"].fillna("").str.contains("Sondages entre Emmanuel Macron et Marine Le Pen", case=False, na=False)
    ]
    end_matches = visual_rows.index[
        visual_rows["row_text"].fillna("").str.contains("Sondages effectués avant le premier tour", case=False, na=False)
    ]
    if len(start_matches) == 0:
        return pd.DataFrame()
    start_index = int(start_matches[0])
    later_end = [int(index) for index in end_matches if int(index) > start_index]
    end_index = later_end[0] if later_end else min(len(visual_rows), start_index + 250)
    section = visual_rows.iloc[start_index:end_index]

    rows: list[dict[str, object]] = []
    current_source = "Source à vérifier"
    for line in section["row_text"].fillna("").astype(str):
        compact = " ".join(line.split())
        if not compact:
            continue
        if any(name in compact for name in ["Ipsos", "Harris", "Elabe", "Opinionway", "OpinionWay", "BVA", "Odoxa", "Ifop"]):
            current_source = compact.split("(")[0].strip()
        if "Résultats" in compact and "58,55" in compact and "41,45" in compact:
            rows.append(
                {
                    "publication_date": SECOND_ROUND_ELECTION_DATE,
                    "pollster": "Résultat officiel",
                    "sample_size": 32077401,
                    "macron_percent": 58.55,
                    "lepen_percent": 41.45,
                }
            )
            continue
        match = re.search(
            r"(\d{1,2}(?:-\d{1,2})?\s+avril\s+2022)\s+([\d ]{3,})\s+(\d{1,2},?\d*)\s*%\s+(\d{1,2},?\d*)\s*%",
            compact,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        parsed_date = _parse_french_date(match.group(1))
        if parsed_date is None:
            continue
        sample_size = int(match.group(2).replace(" ", ""))
        macron = _to_float_percent(match.group(3))
        lepen = _to_float_percent(match.group(4))
        if macron is None or lepen is None:
            continue
        rows.append(
            {
                "publication_date": parsed_date,
                "pollster": current_source,
                "sample_size": sample_size,
                "macron_percent": macron,
                "lepen_percent": lepen,
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.drop_duplicates().sort_values(["publication_date", "pollster"]).reset_index(drop=True)


def _render_complete_zip_2022_extracts() -> None:
    visual_rows = load_complete_visual_rows("2022")
    layout_lines = load_complete_layout_lines("2022")
    if visual_rows.empty and layout_lines.empty:
        return

    st.markdown("**Données complètes importées depuis le zip 2022**")
    tab1, tab2, tab3 = st.tabs(["Premier tour", "Second tour", "Structure source"])

    with tab1:
        first_round_rows = visual_rows.loc[
            visual_rows["row_text"].fillna("").str.contains(
                r"Résultats|Ipsos|Harris|Elabe|Cluster|BVA|OpinionWay|Opinionway|Ifop|Odoxa",
                case=False,
                regex=True,
                na=False,
            )
        ][["page", "visual_row", "row_text", "source_url"]].head(140)
        st.dataframe(
            first_round_rows,
            width="stretch",
            hide_index=True,
            column_config={"source_url": st.column_config.LinkColumn("Source")},
        )

    with tab2:
        second_round_rows = visual_rows.loc[
            visual_rows["row_text"].fillna("").str.contains(
                r"Macron|Le Pen|Résultats|Ipsos|Harris|Elabe|Opinionway|Ifop|BVA|Odoxa|Cluster",
                case=False,
                regex=True,
                na=False,
            )
        ][["page", "visual_row", "row_text", "source_url"]].head(140)
        st.dataframe(
            second_round_rows,
            width="stretch",
            hide_index=True,
            column_config={"source_url": st.column_config.LinkColumn("Source")},
        )

    with tab3:
        source_lines = layout_lines.loc[
            layout_lines["raw_line"].fillna("").str.contains(
                r"Sondages concernant le premier tour|Sondages concernant le second tour|Reports de voix|Résultats",
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


def _extract_2022_archive_sections() -> dict[str, pd.DataFrame]:
    visual_rows = load_complete_visual_rows("2022")
    if visual_rows.empty:
        return {}

    ordered = visual_rows.reset_index(drop=True).copy()
    headings = [
        ("Mars 2022", r"^Mars 2022$|Sondages de mars 2022"),
        ("Février 2022", r"^Février 2022$|Sondages de février 2022"),
        ("Janvier 2022", r"^Janvier 2022$|Sondages de janvier 2022"),
        ("Année 2021", r"^Année 2021$"),
        ("Années 2017-2020", r"^Années 2017-2020$|Sondages effectués de 2017 à 2020"),
    ]
    positions: list[tuple[str, int]] = []
    for label, pattern in headings:
        matches = ordered.index[ordered["row_text"].fillna("").str.contains(pattern, case=False, regex=True, na=False)]
        if len(matches) > 0:
            positions.append((label, int(matches[0])))
    positions = sorted(positions, key=lambda item: item[1])

    sections: dict[str, pd.DataFrame] = {}
    for index, (label, start) in enumerate(positions):
        end = positions[index + 1][1] if index + 1 < len(positions) else min(len(ordered), start + 260)
        section = ordered.iloc[start:end].copy()
        section = section.loc[section["row_text"].fillna("").str.strip().ne("")]
        sections[label] = section[["page", "visual_row", "row_text", "source_url"]]
    return sections


def _build_fit_curve_on_days(
    frame: pd.DataFrame,
    x_column: str,
    y_column: str,
    method: str,
    degree: int,
) -> pd.DataFrame | None:
    working = frame[[x_column, y_column]].copy()
    working[x_column] = pd.to_numeric(working[x_column], errors="coerce")
    working[y_column] = pd.to_numeric(working[y_column], errors="coerce")
    working = working.dropna().sort_values(x_column)
    if len(working.index) < 5 or working[x_column].nunique() < 2:
        return None

    if method == "bins":
        binned = (
            working.assign(bin_index=(working[x_column] // 30).astype(int))
            .groupby("bin_index", dropna=False)
            .agg(x_value=(x_column, "median"), y_value=(y_column, "median"))
            .reset_index(drop=True)
            .sort_values("x_value")
        )
        if len(binned.index) < 2:
            return None
        return binned.rename(columns={"x_value": x_column, "y_value": y_column})

    fit_degree = min(max(int(degree), 1), max(len(working.index) - 1, 1), 6)
    x = working[x_column].to_numpy(dtype=float)
    y = working[y_column].to_numpy(dtype=float)
    coeffs = np.polyfit(x, y, deg=fit_degree)
    dense_x = np.linspace(float(np.nanmin(x)), float(np.nanmax(x)), num=max(160, len(working.index)))
    dense_y = np.polyval(coeffs, dense_x)
    return pd.DataFrame({x_column: dense_x, y_column: dense_y})


def _load_analysis_2022_history() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    reference_dir = get_reference_dir(Path.cwd())
    context = compute_first_round_correction_context(reference_dir)
    history = context.historical_errors.copy()
    wiki_2022_recent = _load_2022_first_round_from_wiki_tables(include_archive=True)
    official_results = load_historical_2022_results(reference_dir)
    archive_sections = _extract_2022_archive_sections()

    if not wiki_2022_recent.empty:
        results_lookup = (
            official_results[["force_label", "result_percent"]].drop_duplicates()
            if not official_results.empty
            else pd.DataFrame(columns=["force_label", "result_percent"])
        )
        wiki_2022_recent = wiki_2022_recent.merge(results_lookup, on="force_label", how="left")
        wiki_2022_recent["days_until_election"] = (
            FIRST_ROUND_ELECTION_DATE - pd.to_datetime(wiki_2022_recent["fieldwork_end_date"], errors="coerce")
        ).dt.days
        wiki_2022_recent["historical_error"] = wiki_2022_recent["estimate_percent"] - wiki_2022_recent["result_percent"]
        history = pd.concat([history, wiki_2022_recent], ignore_index=True, sort=False)
        history = history.drop_duplicates(
            subset=["fieldwork_end_date", "pollster", "force_label", "estimate_percent"],
            keep="last",
        ).reset_index(drop=True)

    if not history.empty:
        history["publication_date"] = pd.to_datetime(history["fieldwork_end_date"], errors="coerce")
        history["days_before_vote"] = (FIRST_ROUND_ELECTION_DATE - history["publication_date"]).dt.days
        history["months_before_vote"] = history["days_before_vote"] / 30.44
        history["error_poll_minus_result"] = history["historical_error"]
        history["error_result_minus_poll"] = -history["historical_error"]
        history["broad_bloc"] = history["political_family"].fillna("Autre")

    return history, official_results, archive_sections


def _render_2022_comparison_section(filtered_history: pd.DataFrame, prefix: str = "analysis_2022") -> None:
    st.markdown("**Comparaison 2022 : sondage vs résultat au fil du temps avant le scrutin**")
    available_forces = sorted(filtered_history["force_label"].dropna().astype(str).unique().tolist())
    available_pollsters = ["Tous"] + sorted(filtered_history["pollster"].dropna().astype(str).unique().tolist())
    fit_methods = {"Polynomial": "polynomial", "Bins": "bins"}
    c1, c2, c3, c4 = st.columns([1.0, 1.0, 0.8, 0.8])
    selected_force = c1.selectbox("Force 2022", available_forces, key=f"{prefix}_force_fit")
    selected_pollster = c2.selectbox("Institut 2022", available_pollsters, key=f"{prefix}_pollster_fit")
    selected_fit_label = c3.selectbox("Fit", list(fit_methods.keys()), key=f"{prefix}_fit_method")
    selected_degree = c4.selectbox("Ordre fit", [1, 2, 3, 4, 5, 6, 7, 8, 9], index=2, key=f"{prefix}_fit_degree")

    comparison = filtered_history.loc[filtered_history["force_label"] == selected_force].copy()
    if selected_pollster != "Tous":
        comparison = comparison.loc[comparison["pollster"] == selected_pollster].copy()
    comparison = comparison.dropna(subset=["publication_date", "estimate_percent", "result_percent", "days_before_vote"])
    comparison = comparison.sort_values("publication_date")

    if comparison.empty:
        st.info("Aucune donnée 2022 disponible pour cette combinaison force / institut.")
        return

    comparison["x_days"] = comparison["days_before_vote"]
    comparison_curve = _build_fit_curve_on_days(
        comparison,
        x_column="x_days",
        y_column="estimate_percent",
        method=fit_methods[selected_fit_label],
        degree=selected_degree,
    )
    error_curve = _build_fit_curve_on_days(
        comparison,
        x_column="x_days",
        y_column="error_result_minus_poll",
        method=fit_methods[selected_fit_label],
        degree=selected_degree,
    )

    result_value = float(comparison["result_percent"].dropna().iloc[0])
    color = get_political_color(selected_force, None)

    poll_vs_result = go.Figure()
    poll_vs_result.add_trace(
        go.Scatter(
            x=comparison["x_days"],
            y=comparison["estimate_percent"],
            mode="markers",
            marker={"size": 7, "color": color, "opacity": 0.55},
            name="Points de sondage",
            customdata=comparison[["pollster", "candidate_name", "publication_date"]].to_numpy(),
            hovertemplate="J-%{x:.0f}<br>Sondage: %{y:.1f}%<br>Institut: %{customdata[0]}<br>Candidat: %{customdata[1]}<br>Date: %{customdata[2]|%d/%m/%Y}<extra></extra>",
        )
    )
    if comparison_curve is not None:
        poll_vs_result.add_trace(
            go.Scatter(
                x=comparison_curve["x_days"],
                y=comparison_curve["estimate_percent"],
                mode="lines",
                line={"width": 2.6, "color": color},
                name=f"Fit sondage ({selected_fit_label.lower()})",
                hovertemplate="J-%{x:.0f}<br>Fit sondage: %{y:.1f}%<extra></extra>",
            )
        )
    poll_vs_result.add_hline(y=result_value, line_width=2, line_dash="dot", line_color="#111111")
    poll_vs_result.update_layout(
        title=f"2022 · {selected_force} · sondage versus résultat officiel",
        xaxis_title="Jours avant le scrutin",
        yaxis_title="Score (%)",
        **PLOT_LAYOUT_THEME,
    )
    poll_vs_result.update_xaxes(autorange="reversed")
    poll_vs_result.update_yaxes(ticksuffix=" %")
    st.plotly_chart(poll_vs_result, width="stretch", config={"displayModeBar": False, "responsive": True})

    error_plot = go.Figure()
    error_plot.add_trace(
        go.Scatter(
            x=comparison["x_days"],
            y=comparison["error_result_minus_poll"],
            mode="markers",
            marker={"size": 7, "color": color, "opacity": 0.55},
            name="Ecart resultat - sondage",
            customdata=comparison[["pollster", "publication_date"]].to_numpy(),
            hovertemplate="J-%{x:.0f}<br>Ecart: %{y:.2f}<br>Institut: %{customdata[0]}<br>Date: %{customdata[1]|%d/%m/%Y}<extra></extra>",
        )
    )
    if error_curve is not None:
        error_plot.add_trace(
            go.Scatter(
                x=error_curve["x_days"],
                y=error_curve["error_result_minus_poll"],
                mode="lines",
                line={"width": 2.6, "color": color},
                name=f"Fit ecart ({selected_fit_label.lower()})",
                hovertemplate="J-%{x:.0f}<br>Fit ecart: %{y:.2f}<extra></extra>",
            )
        )
    error_plot.add_hline(y=0.0, line_width=1, line_dash="dot", line_color="#666666")
    error_plot.update_layout(
        title=f"2022 · {selected_force} · ecart au résultat officiel",
        xaxis_title="Jours avant le scrutin",
        yaxis_title="Resultat officiel - sondage",
        **PLOT_LAYOUT_THEME,
    )
    error_plot.update_xaxes(autorange="reversed")
    st.plotly_chart(error_plot, width="stretch", config={"displayModeBar": False, "responsive": True})
    st.caption("Lecture : au-dessus de zero, le sondage sous-estime la force ; en dessous de zero, il la surestime.")


def render_analysis_2022_comparison_page() -> None:
    st.subheader("Comparaison 2022 sondages vs résultat")
    history, _, _ = _load_analysis_2022_history()
    if history.empty:
        st.info("Aucune donnée 2022 disponible.")
        return

    min_date = history["publication_date"].min().date() if history["publication_date"].notna().any() else date.today()
    max_date = history["publication_date"].max().date() if history["publication_date"].notna().any() else date.today()
    selected_period = st.date_input(
        "Période 2022 affichée",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="analysis_2022_comparison_period",
    )
    filtered_history = history.copy()
    if isinstance(selected_period, tuple) and len(selected_period) == 2:
        filtered_history = filtered_history.loc[
            filtered_history["publication_date"].between(
                pd.Timestamp(selected_period[0]),
                pd.Timestamp(selected_period[1]),
                inclusive="both",
            )
        ]
    if filtered_history.empty:
        st.warning("Aucune donnée 2022 disponible pour cette période.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Lignes 2022", int(len(filtered_history)))
    col2.metric("Instituts 2022", int(filtered_history["pollster"].nunique()))
    col3.metric("Forces 2022", int(filtered_history["force_label"].nunique()))

    _render_2022_comparison_section(filtered_history, prefix="analysis_2022_comparison")


def render_analysis_2022_page() -> None:
    st.subheader("Analyse historique 2022")
    reference_dir = get_reference_dir(Path.cwd())
    context = compute_first_round_correction_context(reference_dir)
    history, official_results, archive_sections = _load_analysis_2022_history()
    if history.empty:
        st.info("Aucune donnée 2022 disponible.")
        return

    min_date = history["publication_date"].min().date() if history["publication_date"].notna().any() else date.today()
    max_date = history["publication_date"].max().date() if history["publication_date"].notna().any() else date.today()
    selected_period = st.date_input(
        "Période 2022 affichée",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="analysis_2022_period",
    )
    filtered_history = history.copy()
    if isinstance(selected_period, tuple) and len(selected_period) == 2:
        filtered_history = filtered_history.loc[
            filtered_history["publication_date"].between(
                pd.Timestamp(selected_period[0]),
                pd.Timestamp(selected_period[1]),
                inclusive="both",
            )
        ]
    if filtered_history.empty:
        st.warning("Aucune donnée 2022 disponible pour cette période.")
        return

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Lignes 2022", int(len(filtered_history)))
    col2.metric("Instituts 2022", int(filtered_history["pollster"].nunique()))
    col3.metric("Forces 2022", int(filtered_history["force_label"].nunique()))
    col4.metric("Date du vote", FIRST_ROUND_ELECTION_DATE.strftime("%d/%m/%Y"))
    earliest_archive = "2017" if "Années 2017-2020" in archive_sections else "2021"
    col5.metric("Archive source", earliest_archive)

    if archive_sections:
        st.markdown("**Archive complète Wikipédia 2022**")
        st.caption(
            "La source complète couvre bien `2022`, `2021` et `2017-2020`. "
            "Le bloc ci-dessous expose ces sections au lieu de s’arrêter au seul segment récent."
        )
        tabs = st.tabs(list(archive_sections.keys()))
        for tab, (label, section) in zip(tabs, archive_sections.items()):
            with tab:
                st.caption(f"{len(section)} ligne(s) extraites pour `{label}`.")
                st.dataframe(
                    section.head(220),
                    width="stretch",
                    hide_index=True,
                    column_config={"source_url": st.column_config.LinkColumn("Source")},
                )

    if not official_results.empty:
        st.markdown("**Résultats officiels du premier tour 2022**")
        st.dataframe(
            official_results.rename(
                columns={
                    "force_label": "Force",
                    "candidate_name": "Candidat",
                    "result_percent": "Résultat officiel",
                    "source_url": "Lien source",
                    "source_label": "Source",
                }
            ),
            width="stretch",
            hide_index=True,
            column_config={
                "Résultat officiel": st.column_config.NumberColumn("Résultat officiel", format="%.2f %%"),
                "Lien source": st.column_config.LinkColumn("Lien source"),
            },
        )

    grouped = (
        filtered_history.groupby(["publication_date", "force_label"], dropna=False)
        .agg(
            estimate_percent=("estimate_percent", "mean"),
            result_percent=("result_percent", "first"),
            political_family=("political_family", "first"),
        )
        .reset_index()
        .sort_values(["force_label", "publication_date"])
    )
    figure = go.Figure()
    insufficient_forces: list[str] = []
    for force_name, group in grouped.groupby("force_label", dropna=False):
        ordered = group.sort_values("publication_date")
        family = ordered["political_family"].dropna().iloc[0] if ordered["political_family"].notna().any() else None
        color = get_political_color(force_name, family)
        result_value = ordered["result_percent"].dropna().iloc[0] if ordered["result_percent"].notna().any() else None
        figure.add_trace(
            go.Scatter(
                x=ordered["publication_date"],
                y=ordered["estimate_percent"],
                mode="markers",
                marker={"size": 5, "color": color, "opacity": 0.30},
                name=f"{force_name} - points",
                legendgroup=str(force_name),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        smoothed = build_lowess_curve(ordered, "estimate_percent", frac=0.28)
        if smoothed is None:
            insufficient_forces.append(str(force_name))
        else:
            figure.add_trace(
                go.Scatter(
                    x=smoothed["publication_date"],
                    y=smoothed["score_smooth"],
                    mode="lines",
                    line={"width": 2.3, "color": color},
                    name=str(force_name),
                    legendgroup=str(force_name),
                    showlegend=True,
                    hovertemplate=f"{force_name}<br>%{{x|%d/%m/%Y}}<br>%{{y:.1f}}%<extra></extra>",
                )
            )
        if pd.notna(result_value):
            figure.add_hline(y=float(result_value), line_width=1, line_dash="dot", line_color=color, opacity=0.55)

    figure.update_layout(
        title="2022 · sondages, ajustement polynomial et résultat final",
        xaxis_title="Date terrain / publication",
        yaxis_title="Score (%)",
        **PLOT_LAYOUT_THEME,
    )
    figure.update_yaxes(ticksuffix=" %")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})
    if insufficient_forces:
        st.caption("Tendance non calculée pour certaines forces : données insuffisantes ou scénarios non comparables.")

    _render_2022_comparison_section(filtered_history, prefix="analysis_2022")

    st.markdown("**Écarts moyens par candidat / force**")
    bias_by_force = (
        filtered_history.groupby(["force_label", "candidate_name"], dropna=False)
        .agg(
            avg_poll_minus_result=("error_poll_minus_result", "mean"),
            median_poll_minus_result=("error_poll_minus_result", "median"),
            mean_abs_error=("error_poll_minus_result", lambda s: float(s.abs().mean())),
            polls=("pollster", "count"),
            official_result=("result_percent", "first"),
        )
        .reset_index()
        .sort_values("avg_poll_minus_result")
    )
    st.dataframe(
        clean_user_facing_frame(rename_user_facing_columns(bias_by_force)),
        width="stretch",
        hide_index=True,
        column_config={
            "Erreur moyenne": st.column_config.NumberColumn("Erreur moyenne", format="%.2f"),
            "Erreur médiane": st.column_config.NumberColumn("Erreur médiane", format="%.2f"),
            "Erreur absolue moyenne": st.column_config.NumberColumn("Erreur absolue moyenne", format="%.2f"),
            "Lignes": st.column_config.NumberColumn("Lignes", format="%d"),
            "Résultat officiel": st.column_config.NumberColumn("Résultat officiel", format="%.2f %%"),
        },
    )

    st.markdown("**Écarts par institut et par force**")
    bias_by_pollster = (
        filtered_history.groupby(["pollster", "force_label"], dropna=False)
        .agg(
            avg_poll_minus_result=("error_poll_minus_result", "mean"),
            median_poll_minus_result=("error_poll_minus_result", "median"),
            polls=("candidate_name", "count"),
        )
        .reset_index()
        .sort_values(["force_label", "avg_poll_minus_result"])
    )
    st.dataframe(
        clean_user_facing_frame(rename_user_facing_columns(bias_by_pollster)),
        width="stretch",
        hide_index=True,
        column_config={
            "Erreur moyenne": st.column_config.NumberColumn("Erreur moyenne", format="%.2f"),
            "Erreur médiane": st.column_config.NumberColumn("Erreur médiane", format="%.2f"),
            "Lignes": st.column_config.NumberColumn("Lignes", format="%d"),
        },
    )

    st.markdown("**Erreur temporelle RN / LFI**")
    temporal_windows = []
    for force_name in ["RN", "LFI"]:
        force_frame = filtered_history.loc[filtered_history["force_label"] == force_name].copy()
        if force_frame.empty:
            continue
        for months in [18, 12, 6, 3, 1]:
            target_days = months * 30.44
            nearby = force_frame.loc[(force_frame["days_before_vote"] - target_days).abs() <= 45].copy()
            temporal_windows.append(
                {
                    "Force": force_name,
                    "Fenêtre": f"{months} mois",
                    "Erreur moyenne": float(nearby["error_poll_minus_result"].mean()) if not nearby.empty else pd.NA,
                    "Erreur médiane": float(nearby["error_poll_minus_result"].median()) if not nearby.empty else pd.NA,
                    "Points": int(len(nearby.index)),
                }
            )
    st.dataframe(pd.DataFrame(temporal_windows), width="stretch", hide_index=True)

    error_grouped = (
        filtered_history.loc[filtered_history["force_label"].isin(["RN", "LFI"])]
        .groupby(["publication_date", "force_label"], dropna=False)
        .agg(error_poll_minus_result=("error_poll_minus_result", "mean"))
        .reset_index()
        .sort_values(["force_label", "publication_date"])
    )
    if not error_grouped.empty:
        error_figure = go.Figure()
        for force_name, group in error_grouped.groupby("force_label", dropna=False):
            color = get_political_color(force_name, None)
            error_figure.add_trace(
                go.Scatter(
                    x=group["publication_date"],
                    y=group["error_poll_minus_result"],
                    mode="markers",
                    marker={"size": 6, "color": color, "opacity": 0.35},
                    name=f"{force_name} - points",
                    legendgroup=f"err-{force_name}",
                    showlegend=False,
                )
            )
            smoothed_error = build_lowess_curve(
                group.rename(columns={"error_poll_minus_result": "estimate_percent"}),
                "estimate_percent",
                frac=0.32,
            )
            if smoothed_error is not None:
                error_figure.add_trace(
                    go.Scatter(
                        x=smoothed_error["publication_date"],
                        y=smoothed_error["score_smooth"],
                        mode="lines",
                        line={"width": 2.3, "color": color},
                        name=f"{force_name} - erreur lissée",
                        legendgroup=f"err-{force_name}",
                        showlegend=True,
                    )
                )
        error_figure.add_hline(y=0.0, line_width=1, line_dash="dot", line_color="#666666")
        error_figure.update_layout(title="Erreur RN / LFI en fonction du temps", **PLOT_LAYOUT_THEME)
        st.plotly_chart(error_figure, width="stretch", config={"displayModeBar": False, "responsive": True})

    second_round = _parse_second_round_macron_lepen()
    if not second_round.empty:
        if isinstance(selected_period, tuple) and len(selected_period) == 2:
            second_round = second_round.loc[
                second_round["publication_date"].between(
                    pd.Timestamp(selected_period[0]),
                    pd.Timestamp(selected_period[1]),
                    inclusive="both",
                )
            ].copy()
        if second_round.empty:
            st.info("Aucune donnée de second tour 2022 dans cette période.")
            _render_complete_zip_2022_extracts()
            return
        st.markdown("**Second tour 2022 · Macron vs Le Pen**")
        second_round["error_lepen"] = second_round["lepen_percent"] - 41.45
        second_round["error_macron"] = second_round["macron_percent"] - 58.55

        st.dataframe(
            second_round.rename(
                columns={
                    "publication_date": "Publication",
                    "pollster": "Institut",
                    "sample_size": "Échantillon",
                    "macron_percent": "Macron",
                    "lepen_percent": "Le Pen",
                    "error_macron": "Erreur Macron",
                    "error_lepen": "Erreur Le Pen",
                }
            ),
            width="stretch",
            hide_index=True,
            column_config={
                "Macron": st.column_config.NumberColumn("Macron", format="%.2f %%"),
                "Le Pen": st.column_config.NumberColumn("Le Pen", format="%.2f %%"),
                "Erreur Macron": st.column_config.NumberColumn("Erreur Macron", format="%.2f pts"),
                "Erreur Le Pen": st.column_config.NumberColumn("Erreur Le Pen", format="%.2f pts"),
                "Échantillon": st.column_config.NumberColumn("Échantillon", format="%d"),
            },
        )

        second_round_chart = go.Figure()
        for label, column, color in [
            ("Macron", "macron_percent", "#F4A300"),
            ("Le Pen", "lepen_percent", "#0D47A1"),
        ]:
            ordered = second_round.sort_values("publication_date")
            second_round_chart.add_trace(
                go.Scatter(
                    x=ordered["publication_date"],
                    y=ordered[column],
                    mode="markers",
                    marker={"size": 6, "color": color, "opacity": 0.45},
                    name=f"{label} - points",
                    legendgroup=label,
                    showlegend=False,
                )
            )
            smoothed = build_lowess_curve(ordered.rename(columns={column: "estimate_percent"}), "estimate_percent", frac=0.45)
            if smoothed is not None:
                second_round_chart.add_trace(
                    go.Scatter(
                        x=smoothed["publication_date"],
                        y=smoothed["score_smooth"],
                        mode="lines",
                        line={"width": 2.4, "color": color},
                        name=label,
                        legendgroup=label,
                        showlegend=True,
                    )
                )
        second_round_chart.add_hline(y=58.55, line_width=1, line_dash="dot", line_color="#F4A300", opacity=0.6)
        second_round_chart.add_hline(y=41.45, line_width=1, line_dash="dot", line_color="#0D47A1", opacity=0.6)
        second_round_chart.update_layout(
            title="Second tour 2022 · sondages et résultat final",
            xaxis_title="Date",
            yaxis_title="Score (%)",
            **PLOT_LAYOUT_THEME,
        )
        second_round_chart.update_yaxes(ticksuffix=" %")
        st.plotly_chart(second_round_chart, width="stretch", config={"displayModeBar": False, "responsive": True})

    _render_complete_zip_2022_extracts()
