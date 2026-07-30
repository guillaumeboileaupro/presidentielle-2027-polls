from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from presidentielle2027.analytics.adjustment_core import (
    build_adaptive_polynomial_curve,
    build_polynomial_curve,
    select_auto_polynomial_degree,
)
from presidentielle2027.analytics.historical_corrections import (
    FIRST_ROUND_ELECTION_DATE,
)
from presidentielle2027.analytics.trends import build_lowess_curve
from presidentielle2027.dashboard.colors import get_political_color
from presidentielle2027.dashboard.methodology_text import first_round_methodology_html
from presidentielle2027.dashboard.plot_theme import PLOT_LAYOUT_THEME
from presidentielle2027.dashboard.table_views import USER_VALUE_REPLACEMENTS, clean_user_facing_frame, render_poll_results_table

PARTY_SOURCE_ORDER = [
    "LO",
    "LFI",
    "PCF",
    "LE",
    "PS",
    "PP",
    "RE",
    "HOR",
    "LR",
    "LFH",
    "DLF",
    "RN",
    "REC",
]

PARTY_DISPLAY_ORDER = [
    "LO",
    "LFI",
    "PCF",
    "ECO",
    "PS",
    "PP",
    "RE",
    "HOR",
    "LR",
    "LFH",
    "DLF",
    "RN",
    "REC",
]

GITLAB_LOESS_SPANS: dict[str, float] = {
    "PCF": 0.25,
    "LFI": 0.25,
    "LE": 0.25,
    "ECO": 0.25,
    "PS": 0.25,
    "PP": 0.25,
    "RE": 0.25,
    "ENS": 0.25,
    "HOR": 0.25,
    "LR": 0.25,
    "RN": 0.25,
    "REC": 0.30,
    "LFH": 0.35,
    "DLF": 0.35,
    "LO": 0.35,
}

WIKIPEDIA_BLOC_MAP: dict[str, str] = {
    "PCF": "PCF",
    "LFI": "LFI",
    "LE": "ECO",
    "EELV": "ECO",
    "PS": "PS",
    "PP": "PS",
    "PS / PP": "PS",
    "PS-PP": "PS",
    "ENS": "ENS",
    "EPR": "ENS",
    "RE": "ENS",
    "REN": "ENS",
    "HOR": "ENS",
    "LR": "LR",
    "RN": "RN",
    "REC": "REC",
}
WIKIPEDIA_BLOC_ORDER = ["PCF", "LFI", "ECO", "PS", "ENS", "LR", "RN", "REC"]
WIKIPEDIA_2027_FIRST_ROUND_DATE = pd.Timestamp("2027-04-18")
HISTORICAL_2022_CAMPAIGN_FILE = Path("data/reference/historical_polls_2022_first_round.csv")

PARTY_GRAPH_LABELS: dict[str, str] = {
    "LE": "ECO",
    "EELV": "ECO",
    "RE": "RE",
    "HOR": "HOR",
    "LFH": "LFH",
    "DLF": "DLF",
    "PP": "PP",
    "PS": "PS",
    "PCF": "PCF",
    "LFI": "LFI",
    "LO": "LO",
    "RN": "RN",
    "REC": "REC",
    "ENS": "ENS",
}

PARTY_FULL_LABELS: dict[str, str] = {
    "LO": "Lutte ouvrière",
    "LFI": "La France insoumise",
    "PCF": "Parti communiste français",
    "LE": "Les Écologistes",
    "PS": "Parti socialiste",
    "PP": "Place publique",
    "RE": "Renaissance",
    "HOR": "Horizons",
    "LFH": "La France humaniste",
    "LR": "Les Républicains",
    "DLF": "Debout la France",
    "RN": "Rassemblement national",
    "REC": "Reconquête",
    "ENS": "Ensemble",
}

def _evaluate_curve_fit_local(
    observed_frame: pd.DataFrame,
    curve_frame: pd.DataFrame,
    value_column: str,
    date_column: str = "publication_date",
) -> dict[str, float] | None:
    observed = pd.DataFrame(
        {
            "date": pd.to_datetime(observed_frame[date_column], errors="coerce"),
            "value": pd.to_numeric(observed_frame[value_column], errors="coerce"),
        }
    ).dropna()
    if observed.empty or curve_frame.empty:
        return None

    curve = pd.DataFrame(
        {
            "date": pd.to_datetime(curve_frame["publication_date"], errors="coerce"),
            "value": pd.to_numeric(curve_frame["score_smooth"], errors="coerce"),
        }
    ).dropna()
    if len(curve.index) < 2:
        return None

    observed = observed.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    curve = curve.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    base_date = pd.Timestamp(observed["date"].iloc[0])
    observed["date_num"] = ((observed["date"] - base_date) / pd.Timedelta(days=1)).astype(float)
    curve["date_num"] = ((curve["date"] - base_date) / pd.Timedelta(days=1)).astype(float)
    interpolated = np.interp(
        observed["date_num"].to_numpy(dtype=float),
        curve["date_num"].to_numpy(dtype=float),
        curve["value"].to_numpy(dtype=float),
    )
    errors = observed["value"].to_numpy(dtype=float) - interpolated
    absolute_errors = np.abs(errors)
    return {
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "mae": float(np.mean(absolute_errors)),
        "max_abs_error": float(np.max(absolute_errors)),
        "point_count": float(len(observed.index)),
    }


def _fr_label(value: object, fallback: str = "Non renseigné") -> str:
    if value is None or pd.isna(value):
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    return USER_VALUE_REPLACEMENTS.get(text, text)


def _party_graph_label(value: object) -> str:
    if value is None or pd.isna(value):
        return "Sans parti"
    party = str(value).strip()
    if not party:
        return "Sans parti"
    return PARTY_GRAPH_LABELS.get(party, party)


def _party_full_label(value: object) -> str:
    if value is None or pd.isna(value):
        return "Sans étiquette"
    party = str(value).strip()
    if not party:
        return "Sans étiquette"
    return PARTY_FULL_LABELS.get(party, party)


def _wikipedia_bloc_label(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    return WIKIPEDIA_BLOC_MAP.get(str(value).strip())


def _party_family_label(party: object, family: object) -> str:
    party_code = str(party).strip() if party not in (None, "") and not pd.isna(party) else ""
    if party_code in {"RN", "REC"}:
        return "Extrême droite"
    if party_code == "DLF":
        return "Droite souverainiste"
    if party_code == "LR":
        return "Droite"
    if party_code in {"RE", "ENS", "HOR", "LFH"}:
        return "Centre"
    if party_code in {"PP", "PS"}:
        return "Centre gauche"
    if party_code in {"LFI", "PCF", "LO"}:
        return "Gauche"
    if party_code in {"LE", "EELV", "ECO"}:
        return "Écologistes"
    return _fr_label(family, "Non renseigné")


def _party_sort_key(party: object) -> int:
    value = str(party).strip() if party not in (None, "") else ""
    if value in PARTY_SOURCE_ORDER:
        return PARTY_SOURCE_ORDER.index(value)
    return len(PARTY_SOURCE_ORDER) + 100


def _display_sort_key(label: object) -> int:
    value = str(label).strip() if label not in (None, "") else ""
    if value in PARTY_DISPLAY_ORDER:
        return PARTY_DISPLAY_ORDER.index(value)
    return len(PARTY_DISPLAY_ORDER) + 100


@st.cache_data(show_spinner=False, max_entries=64)
def _select_primary_first_round_scenarios(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "scenario_name" not in frame.columns or "poll_id" not in frame.columns:
        return frame

    scenario_rank = (
        frame.groupby(["poll_id", "scenario_name"], dropna=False)
        .agg(
            candidate_count=("candidate_name", "nunique"),
            party_count=("candidate_party", "nunique"),
            total_score=("estimate_percent", "sum"),
        )
        .reset_index()
        .sort_values(
            ["poll_id", "candidate_count", "party_count", "total_score", "scenario_name"],
            ascending=[True, False, False, False, True],
        )
    )
    primary = scenario_rank.groupby("poll_id", dropna=False).head(1)[["poll_id", "scenario_name"]]
    return frame.merge(primary, on=["poll_id", "scenario_name"], how="inner")


def _align_smoothed_values_to_observations(
    smoothed_series: pd.Series,
    observation_dates: pd.Series,
) -> np.ndarray:
    """Interpolate a curve on observations, including repeated publication dates."""
    curve = smoothed_series.copy()
    curve.index = pd.to_datetime(curve.index)
    curve = curve.groupby(level=0).last().sort_index()
    requested_dates = pd.DatetimeIndex(pd.to_datetime(observation_dates))
    unique_dates = pd.DatetimeIndex(requested_dates.dropna().unique()).sort_values()
    interpolation_index = curve.index.union(unique_dates).drop_duplicates().sort_values()
    interpolated = curve.reindex(interpolation_index).interpolate(method="time").ffill().bfill()
    return interpolated.reindex(requested_dates).to_numpy(dtype=float)


@st.cache_data(show_spinner=False, max_entries=256)
def _cached_trend_curve(
    frame: pd.DataFrame,
    trend_method: str,
    polynomial_order: int,
    loess_frac: float,
) -> tuple[pd.DataFrame | None, int]:
    resolved_order = polynomial_order
    if trend_method == "Polynôme auto":
        resolved_order = select_auto_polynomial_degree(
            frame,
            "estimate_percent",
            max_degree=polynomial_order,
        )
        curve = build_polynomial_curve(
            frame,
            "estimate_percent",
            degree=resolved_order,
        )
    else:
        curve = build_lowess_curve(
            frame,
            "estimate_percent",
            frac=loess_frac,
            degree=resolved_order,
            method=(
                "loess"
                if trend_method == "Régression locale (LOESS)"
                else ("bins" if trend_method == "Classes temporelles" else "polynomial")
            ),
            dense_points=300,
        )
    return curve, resolved_order


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


def _build_2022_campaign_extension_paths(
    extension_payloads: list[dict[str, object]],
    election_date: pd.Timestamp,
    historical_frame: pd.DataFrame | None = None,
) -> list[dict[str, object]]:
    """Blend current momentum with 2022 campaign-stage movements and bounded plateaus."""
    paths = _build_joint_extension_paths(extension_payloads, election_date)
    if not paths:
        return paths
    if historical_frame is None:
        if not HISTORICAL_2022_CAMPAIGN_FILE.exists():
            return paths
        historical_frame = pd.read_csv(HISTORICAL_2022_CAMPAIGN_FILE)

    force_map = {
        "ECO": "EELV",
        "LE": "EELV",
        "PS": "PS-PP",
        "PP": "PS-PP",
        "RE": "ENS",
        "HOR": "ENS",
    }
    history = historical_frame.copy()
    history["days_until_election"] = pd.to_numeric(
        history["days_until_election"], errors="coerce"
    )
    history["estimate_percent"] = pd.to_numeric(history["estimate_percent"], errors="coerce")
    history = history.dropna(subset=["force_label", "days_until_election", "estimate_percent"])
    election_ts = pd.Timestamp(election_date)

    for path in paths:
        key = str(path["display_name"])
        historical_force = force_map.get(key, key)
        force_history = history.loc[history["force_label"].astype(str) == historical_force]
        if force_history.empty:
            continue
        trajectory = (
            force_history.groupby("days_until_election")["estimate_percent"]
            .median()
            .sort_index()
        )
        xp = trajectory.index.to_numpy(dtype=float)
        fp = trajectory.to_numpy(dtype=float)
        dates = pd.to_datetime(path["x"])
        remaining_days = ((election_ts - dates) / pd.Timedelta(days=1)).to_numpy(dtype=float)
        historical_levels = np.interp(remaining_days, xp, fp)
        historical_start = float(np.interp(remaining_days[0], xp, fp))
        historical_delta = historical_levels - historical_start

        current_path = pd.to_numeric(path["y"], errors="coerce").to_numpy(dtype=float)
        anchor = float(current_path[0])
        current_delta = current_path - anchor
        blended_delta = 0.35 * current_delta + 0.65 * historical_delta
        plateaued = anchor + np.clip(blended_delta, -4.0, 4.0)
        if historical_force == "RN":
            plateaued = np.minimum(plateaued, anchor)

        path["y"] = pd.Series(plateaued)
        width = (
            pd.to_numeric(path["upper"], errors="coerce").to_numpy(dtype=float)
            - pd.to_numeric(path["lower"], errors="coerce").to_numpy(dtype=float)
        ) / 2.0
        path["lower"] = pd.Series(np.clip(plateaued - width, 0.0, 100.0))
        path["upper"] = pd.Series(np.clip(plateaued + width, 0.0, 100.0))
    return paths


def render_first_round_raw_page(frame: pd.DataFrame) -> None:
    st.subheader("Sondages 2027 concernant le premier tour")
    working = frame.loc[(frame["round"] == "first_round") & (~frame["is_generic_bloc"])].copy()
    if working.empty:
        st.info("Aucune donnée de premier tour exploitable.")
        return
    scenario_totals = (
        working.groupby(["poll_id", "scenario_name"], dropna=False)["estimate_percent"]
        .sum(min_count=1)
        .dropna()
    )
    if "source_url" not in working.columns:
        working["source_url"] = pd.NA
    st.markdown(first_round_methodology_html(), unsafe_allow_html=True)
    st.caption(
        "Source de référence : Wikipédia, « Liste de sondages sur l'élection présidentielle française de 2027 ». "
        "L’ajustement appliqué ici trace soit un polynôme réel par force, soit un lissage de type GitLab selon le modèle choisi."
    )
    if not scenario_totals.empty:
        st.caption(
            "Contrôle après correction des décimales : "
            f"{len(scenario_totals)} scénarios conservés, sommes de "
            f"{scenario_totals.min():.1f} % à {scenario_totals.max():.1f} % "
            f"(médiane {scenario_totals.median():.1f} %)."
        )

    pollsters = ["Tous"] + sorted(working["polling_company"].dropna().astype(str).unique().tolist())
    min_date = FIRST_ROUND_ELECTION_DATE.date()
    max_date = WIKIPEDIA_2027_FIRST_ROUND_DATE.date()

    available_years = sorted(
        working["publication_date"].dropna().dt.year.astype(int).unique().tolist(),
        reverse=True,
    )
    year_options = ["Toutes"] + [str(year) for year in available_years]
    c1, c2, c3, c4, c5, c6 = st.columns([1.0, 1.2, 1.0, 0.8, 0.8, 0.8])
    pollster = c1.selectbox("Institut", pollsters, key="first_round_pollster")
    selected_year = c2.selectbox("Année", year_options, index=0, key="first_round_year")
    period = c3.date_input(
        "Période",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="first_round_period",
    )
    grouping = c4.selectbox(
        "Regrouper par",
        ["Blocs Wikipédia", "Parti politique", "Famille politique"],
        index=0,
        key="first_round_grouping",
    )
    trend_method = c5.selectbox(
        "Modèle",
        ["Régression locale (LOESS)", "Polynôme auto", "Classes temporelles", "Polynôme manuel"],
        index=0,
        key="first_round_trend_method",
    )
    polynomial_order = c6.selectbox("Ordre max", list(range(1, 6)), index=3, key="first_round_polynomial_order")
    available_parties = sorted(working["candidate_party"].dropna().astype(str).unique().tolist(), key=_party_sort_key)
    default_parties = [party for party in PARTY_SOURCE_ORDER if party in available_parties]
    if not default_parties:
        default_parties = available_parties[: min(len(available_parties), 12)]
    show_all_parties = False
    selected_parties: list[str] = []
    if grouping == "Parti politique":
        show_all_parties = st.checkbox(
            "Afficher toutes les forces",
            value=False,
            key="first_round_show_all_parties",
        )
        selected_parties = st.multiselect(
            "Forces affichées",
            available_parties,
            default=available_parties if show_all_parties else default_parties,
            key="first_round_selected_parties",
        )
    show_extension = st.checkbox(
        "Prolongation en pointillé jusqu'à l'élection",
        value=False,
        key="first_round_show_extension",
    )
    extension_model = "Dynamique récente"
    if show_extension:
        extension_model = st.selectbox(
            "Scénario de prolongation",
            ["Dynamique récente", "Comparer avec la campagne 2022 (rose)"],
            key="first_round_extension_model",
        )
    filtered = working.copy()
    fitting_frame = working.copy()
    if pollster != "Tous":
        filtered = filtered.loc[filtered["polling_company"] == pollster]
        fitting_frame = fitting_frame.loc[fitting_frame["polling_company"] == pollster]
    if selected_year != "Toutes":
        selected_year_number = int(selected_year)
        filtered = filtered.loc[filtered["publication_date"].dt.year == selected_year_number]
        fitting_frame = fitting_frame.loc[fitting_frame["publication_date"].dt.year == selected_year_number]
    if grouping == "Parti politique" and selected_parties:
        filtered = filtered.loc[filtered["candidate_party"].astype(str).isin(selected_parties)].copy()
        fitting_frame = fitting_frame.loc[fitting_frame["candidate_party"].astype(str).isin(selected_parties)].copy()
    if isinstance(period, tuple) and len(period) == 2:
        filtered = filtered.loc[
            filtered["publication_date"].between(pd.Timestamp(period[0]), pd.Timestamp(period[1]), inclusive="both")
        ]
        fitting_frame = fitting_frame.loc[
            fitting_frame["publication_date"].between(pd.Timestamp(period[0]), pd.Timestamp(period[1]), inclusive="both")
        ]
        period_start_ts = pd.Timestamp(period[0])
        period_end_ts = pd.Timestamp(period[1])
    else:
        period_start_ts = pd.Timestamp(min_date)
        period_end_ts = pd.Timestamp(max_date)
    filtered = filtered.loc[
        filtered["publication_date"].between(period_start_ts, period_end_ts, inclusive="both")
    ].copy()
    fitting_frame = fitting_frame.loc[
        fitting_frame["publication_date"].between(period_start_ts, period_end_ts, inclusive="both")
    ].copy()
    filtered = _select_primary_first_round_scenarios(filtered)
    fitting_frame = _select_primary_first_round_scenarios(fitting_frame)
    if grouping == "Blocs Wikipédia":
        filtered["wikipedia_bloc"] = filtered["candidate_party"].map(_wikipedia_bloc_label)
        fitting_frame["wikipedia_bloc"] = fitting_frame["candidate_party"].map(_wikipedia_bloc_label)
        filtered = filtered.dropna(subset=["wikipedia_bloc"])
        fitting_frame = fitting_frame.dropna(subset=["wikipedia_bloc"])
    if filtered.empty or fitting_frame.empty:
        st.warning("Aucune donnée disponible pour ces filtres.")
        return
    st.caption(
        "Période tracée : "
        f"{period_start_ts.strftime('%d/%m/%Y')} -> {period_end_ts.strftime('%d/%m/%Y')}"
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Périmètre", "Tous les sondages du premier tour")
    col2.metric("Lignes", int(len(filtered)))
    col3.metric("Instituts", int(filtered["polling_company"].nunique()))
    col4.metric(
        "Forces",
        int(
            filtered["candidate_party"].fillna("Sans parti").nunique()
            if grouping == "Parti politique"
            else (
                filtered["wikipedia_bloc"].nunique()
                if grouping == "Blocs Wikipédia"
                else filtered["political_family"].fillna("Autre").nunique()
            )
        ),
    )

    if grouping == "Parti politique":
        force_summary = (
            filtered.sort_values(["publication_date", "estimate_percent"], ascending=[False, False])
            .groupby("candidate_party", dropna=False)
            .head(1)
            .copy()
        )
        force_summary["Sigle"] = force_summary["candidate_party"].map(_party_graph_label)
        force_summary["Force"] = force_summary["candidate_party"].map(_party_full_label)
        force_summary["Famille"] = force_summary.apply(
            lambda row: _party_family_label(row.get("candidate_party"), row.get("political_family")),
            axis=1,
        )
        force_summary["Dernière valeur"] = force_summary["estimate_percent"].map(lambda value: f"{value:.1f}%")
        force_summary["__ordre_valeur"] = force_summary["estimate_percent"].astype(float)
        force_summary["__ordre_sigle"] = force_summary["Sigle"].map(_display_sort_key)
        force_summary = force_summary.sort_values(["__ordre_valeur", "__ordre_sigle"], ascending=[False, True])[
            ["Sigle", "Force", "Famille", "Dernière valeur"]
        ]
    elif grouping == "Blocs Wikipédia":
        summary_by_bloc = (
            filtered.groupby(
                ["poll_id", "scenario_name", "publication_date", "wikipedia_bloc"],
                dropna=False,
            )["estimate_percent"]
            .sum()
            .reset_index()
        )
        force_summary = (
            summary_by_bloc.sort_values(["publication_date", "estimate_percent"], ascending=[False, False])
            .groupby("wikipedia_bloc", dropna=False)
            .head(1)
            .copy()
        )
        force_summary["Bloc"] = force_summary["wikipedia_bloc"]
        force_summary["Dernière valeur"] = force_summary["estimate_percent"].map(lambda value: f"{value:.1f}%")
        force_summary = force_summary[["Bloc", "Dernière valeur"]]
    else:
        force_summary = (
            filtered.sort_values(["publication_date", "estimate_percent"], ascending=[False, False])
            .groupby("political_family", dropna=False)
            .head(1)
            .copy()
        )
        force_summary["Famille"] = force_summary["political_family"].map(lambda value: _fr_label(value, "Autre"))
        force_summary["Dernière valeur"] = force_summary["estimate_percent"].map(lambda value: f"{value:.1f}%")
        force_summary = force_summary[["Famille", "Dernière valeur"]]
    if not force_summary.empty:
        force_summary = clean_user_facing_frame(force_summary)
        st.markdown("**Lecture rapide des forces**")
        st.table(force_summary.reset_index(drop=True))

    grouped = filtered.copy()
    grouped_fit = fitting_frame.copy()
    for current in (grouped, grouped_fit):
        if grouping == "Parti politique":
            current["display_name"] = current["candidate_party"].map(_party_graph_label).fillna("Sans parti")
            current["display_party"] = current["candidate_party"].fillna("Sans parti")
            current["display_family"] = current["political_family"].map(lambda value: _fr_label(value, "Autre"))
            current["display_order"] = current["candidate_party"].map(_party_sort_key)
            current["display_label_order"] = current["display_name"].map(_display_sort_key)
        elif grouping == "Blocs Wikipédia":
            current["display_name"] = current["wikipedia_bloc"]
            current["display_party"] = current["wikipedia_bloc"]
            current["display_family"] = current["political_family"].map(lambda value: _fr_label(value, "Autre"))
            current["display_order"] = current["wikipedia_bloc"].map(
                {bloc: index for index, bloc in enumerate(WIKIPEDIA_BLOC_ORDER)}
            )
            current["display_label_order"] = current["display_order"]
        else:
            current["display_name"] = current["political_family"].map(lambda value: _fr_label(value, "Autre"))
            current["display_party"] = current["candidate_party"].fillna("Sans parti")
            current["display_family"] = current["political_family"].map(lambda value: _fr_label(value, "Autre"))
            current["display_order"] = len(PARTY_SOURCE_ORDER) + 100
            current["display_label_order"] = len(PARTY_DISPLAY_ORDER) + 100

    estimate_aggregation = "sum" if grouping == "Blocs Wikipédia" else "mean"
    grouped = (
        grouped.groupby(
            ["poll_id", "scenario_name", "publication_date", "display_name", "display_order", "display_label_order"],
            dropna=False,
        )
        .agg(
            estimate_percent=("estimate_percent", estimate_aggregation),
            sample_size=("sample_size", "mean"),
            polling_company=("polling_company", "first"),
            candidate_party=("display_party", "first"),
            political_family=("display_family", "first"),
        )
        .reset_index()
        .sort_values(["display_order", "display_label_order", "publication_date", "display_name"])
    )
    grouped_fit = (
        grouped_fit.groupby(
            ["poll_id", "scenario_name", "publication_date", "display_name", "display_order", "display_label_order"],
            dropna=False,
        )
        .agg(
            estimate_percent=("estimate_percent", estimate_aggregation),
            sample_size=("sample_size", "mean"),
            polling_company=("polling_company", "first"),
            candidate_party=("display_party", "first"),
            political_family=("display_family", "first"),
        )
        .reset_index()
        .sort_values(["display_order", "display_label_order", "publication_date", "display_name"])
    )

    figure = go.Figure()
    insufficient_forces: list[str] = []
    extension_payloads: list[dict[str, object]] = []
    fit_diagnostics_rows: list[dict[str, object]] = []
    ordered_display_names = (
        grouped[["display_name", "display_order", "display_label_order"]]
        .drop_duplicates()
        .sort_values(["display_order", "display_label_order", "display_name"])
        ["display_name"]
        .tolist()
    )
    for display_name in ordered_display_names:
        group_display = grouped.loc[grouped["display_name"] == display_name].copy()
        group_fit = grouped_fit.loc[grouped_fit["display_name"] == display_name].copy()
        if group_display.empty or group_fit.empty:
            continue
        ordered = group_display.sort_values("publication_date")
        ordered_fit = group_fit.sort_values("publication_date")
        display_name = str(ordered["display_name"].iloc[0])
        party = ordered_fit["candidate_party"].dropna().iloc[0] if ordered_fit["candidate_party"].notna().any() else None
        family = ordered_fit["political_family"].dropna().iloc[0] if ordered_fit["political_family"].notna().any() else None
        color = get_political_color(party, family)
        ordered_for_curve = ordered_fit

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
        loess_frac = GITLAB_LOESS_SPANS.get(display_name, GITLAB_LOESS_SPANS.get(str(party).strip(), 0.25))
        if grouping == "Blocs Wikipédia":
            loess_frac = max(loess_frac, 0.50)
        fit_quality: dict[str, float] | None = None
        smoothed, resolved_polynomial_order = _cached_trend_curve(
            ordered_for_curve[["publication_date", "estimate_percent"]].reset_index(drop=True),
            trend_method,
            polynomial_order,
            loess_frac,
        )
        if smoothed is None:
            insufficient_forces.append(str(display_name))
        else:
            if fit_quality is None:
                fit_quality = _evaluate_curve_fit_local(
                    ordered,
                    smoothed,
                    "estimate_percent",
                    date_column="publication_date",
                )
            smoothed = smoothed.loc[
                smoothed["publication_date"].between(period_start_ts, period_end_ts, inclusive="both")
            ].copy()
            smoothed = (
                smoothed.sort_values("publication_date")
                .drop_duplicates(subset=["publication_date"], keep="last")
                .reset_index(drop=True)
            )
            if fit_quality is not None:
                fit_diagnostics_rows.append(
                    {
                        "Force": display_name,
                        "Ordre": resolved_polynomial_order if trend_method in {"Polynôme auto", "Polynôme manuel"} else "n.d.",
                        "Erreur moyenne": fit_quality["mae"],
                        "Erreur quadratique": fit_quality["rmse"],
                        "Erreur max": fit_quality["max_abs_error"],
                        "Points": int(fit_quality["point_count"]),
                    }
                )
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
                aligned_smooth = _align_smoothed_values_to_observations(
                    smoothed_series,
                    ordered["publication_date"],
                )
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
        extension_sets = [
            (
                _build_joint_extension_paths(
                    extension_payloads,
                    WIKIPEDIA_2027_FIRST_ROUND_DATE,
                ),
                "Dynamique récente",
                None,
            )
        ]
        if extension_model == "Comparer avec la campagne 2022 (rose)":
            extension_sets.append(
                (
                    _build_2022_campaign_extension_paths(
                        extension_payloads,
                        WIKIPEDIA_2027_FIRST_ROUND_DATE,
                    ),
                    "Dynamique de campagne 2022 avec paliers",
                    "#d63384",
                )
            )
        for extension_paths, scenario_label, scenario_color in extension_sets:
            for payload in extension_paths:
                line_color = scenario_color or payload["color"]
                line_dash = "dot" if scenario_color else "dash"
                show_scenario_legend = bool(scenario_color)
                figure.add_trace(
                    go.Scatter(
                        x=payload["x"],
                        y=payload["upper"],
                        mode="lines",
                        line={"width": 0, "color": line_color},
                        hoverinfo="skip",
                        showlegend=False,
                        legendgroup=f"{payload['display_name']}-{scenario_label}",
                    )
                )
                figure.add_trace(
                    go.Scatter(
                        x=payload["x"],
                        y=payload["lower"],
                        mode="lines",
                        line={"width": 0, "color": line_color},
                        fill="tonexty",
                        fillcolor="rgba(214,51,132,0.06)" if scenario_color else "rgba(120,120,120,0.10)",
                        hoverinfo="skip",
                        showlegend=False,
                        legendgroup=f"{payload['display_name']}-{scenario_label}",
                    )
                )
                figure.add_trace(
                    go.Scatter(
                        x=payload["x"],
                        y=payload["y"],
                        mode="lines",
                        line={"width": 2.0 if scenario_color else 1.8, "color": line_color, "dash": line_dash},
                        name=f"{payload['display_name']} · {scenario_label}",
                        legendgroup=f"{payload['display_name']}-{scenario_label}",
                        showlegend=show_scenario_legend,
                        hovertemplate=f"%{{x|%d/%m/%Y}}<br>%{{y:.1f}}%<br>{scenario_label}<extra></extra>",
                    )
                )
    model_label = (
        "régression locale (LOESS) par force politique"
        if trend_method == "Régression locale (LOESS)"
        else (
            "lissage stable par fenêtres"
            if trend_method == "Classes temporelles"
            else ("polynôme auto par parti" if trend_method == "Polynôme auto" else f"polynôme manuel jusqu'à l'ordre {polynomial_order}")
        )
    )
    title = f"Sondages 2027 · {model_label}"
    figure.update_layout(
        title=title,
        xaxis_title="Date de publication",
        yaxis_title="Intentions de vote (%)",
        **PLOT_LAYOUT_THEME,
    )
    figure.update_layout(legend={**PLOT_LAYOUT_THEME["legend"], "traceorder": "normal"})
    chart_end_ts = max(period_end_ts, WIKIPEDIA_2027_FIRST_ROUND_DATE) if show_extension else period_end_ts
    figure.update_xaxes(range=[period_start_ts, chart_end_ts])
    figure.update_yaxes(ticksuffix=" %")
    figure.add_vline(x=pd.Timestamp("2022-04-10"), line_width=1, line_color="#999999", opacity=0.6)
    figure.add_vline(x=WIKIPEDIA_2027_FIRST_ROUND_DATE, line_width=1, line_color="#999999", opacity=0.6)
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})
    if fit_diagnostics_rows:
        diagnostics_frame = pd.DataFrame(fit_diagnostics_rows).sort_values("Erreur moyenne")
        mean_mae = float(diagnostics_frame["Erreur moyenne"].mean())
        mean_rmse = float(diagnostics_frame["Erreur quadratique"].mean())
        worst_error = float(diagnostics_frame["Erreur max"].max())
        m1, m2, m3 = st.columns(3)
        m1.metric("Erreur moyenne des courbes", f"{mean_mae:.2f} pts")
        m2.metric("Erreur quadratique moyenne", f"{mean_rmse:.2f} pts")
        m3.metric("Écart maximal observé", f"{worst_error:.2f} pts")
        with st.expander("Crédibilité du tracé par force"):
            diagnostics_frame["Erreur moyenne"] = diagnostics_frame["Erreur moyenne"].map(lambda value: f"{value:.2f} pts")
            diagnostics_frame["Erreur quadratique"] = diagnostics_frame["Erreur quadratique"].map(lambda value: f"{value:.2f} pts")
            diagnostics_frame["Erreur max"] = diagnostics_frame["Erreur max"].map(lambda value: f"{value:.2f} pts")
            st.table(clean_user_facing_frame(diagnostics_frame).reset_index(drop=True))
    if insufficient_forces:
        st.caption("Tendance non calculée pour certaines forces : données insuffisantes ou scénarios non comparables.")
    if show_extension:
        if extension_model == "Comparer avec la campagne 2022 (rose)":
            st.caption(
                "Scénario exploratoire combinant 35 % de dynamique récente et 65 % des "
                "mouvements observés au même stade de la campagne 2022. Les variations sont "
                "plafonnées à ±4 points et le RN ne peut pas dépasser son niveau lissé au "
                "départ de la prolongation. Ce n’est pas une prédiction électorale validée."
            )
        else:
            st.caption(
                "Scénario exploratoire fondé sur la pente récente des courbes lissées, "
                "sans renormalisation finale forcée à 100 %. Ce n’est pas une prédiction "
                "électorale validée."
            )
    st.caption("Les données historiques 2017–2022 sont affichées dans la vue `Analyse historique 2022`. Cette vue reste un graphe brut 2027, sans mélange de séries historiques dans la courbe principale.")

    if st.checkbox(
        "Afficher le tableau détaillé des sondages",
        value=False,
        key="show_first_round_detailed_table",
    ):
        detailed = filtered.sort_values(
            ["publication_date", "candidate_party", "estimate_percent"],
            ascending=[False, True, False],
        )
        if "source_url" not in detailed.columns:
            detailed["source_url"] = pd.NA
        if grouping == "Parti politique":
            detailed["force_label"] = detailed["candidate_party"].fillna("Sans parti")
        elif grouping == "Blocs Wikipédia":
            detailed["force_label"] = detailed["wikipedia_bloc"]
        else:
            detailed["force_label"] = detailed["political_family"].fillna("Autre")
        render_poll_results_table(detailed)
