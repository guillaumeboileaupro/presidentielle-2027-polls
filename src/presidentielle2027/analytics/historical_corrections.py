from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


HISTORICAL_2022_POLLS_FILE = "historical_polls_2022_first_round.csv"
HISTORICAL_2022_RESULTS_FILE = "historical_results_2022_presidential_first_round.csv"
HISTORICAL_2024_LEGISLATIVE_FILE = "historical_results_2024_legislatives_blocs.csv"
HISTORICAL_2024_LEGISLATIVE_SEATS_FILE = "historical_results_2024_legislatives_seats.csv"
LEGISLATIVE_2024_WIKI_TABLES_FILE = "sondages_legislatives_2024_wikipedia_tables.csv"
REPRESENTATIVITY_FACTORS_FILE = "polling_representativity_factors.csv"
MANUAL_FIRST_ROUND_BIASES_FILE = "manual_first_round_biases.csv"
MANUAL_SECOND_ROUND_BLOC_OVERRIDES_FILE = "manual_second_round_bloc_overrides.csv"

FIRST_ROUND_ELECTION_DATE = pd.Timestamp("2022-04-10")
CURRENT_ELECTION_DATE = pd.Timestamp("2027-04-11")
LEGISLATIVE_2024_ELECTION_DATE = pd.Timestamp("2024-06-30")
FIRST_ROUND_2022_BACKGROUND_WEIGHT = 0.40
FIRST_ROUND_2024_ANCHOR_WEIGHT = 1.00

PARTY_FORCE_MAP: dict[str, str] = {
    "LFI": "LFI",
    "NFP": "LFI",
    "PS": "PS-PP",
    "PS-PP": "PS-PP",
    "PP": "PS-PP",
    "EELV": "EELV",
    "PCF": "PCF",
    "ENS": "ENS",
    "RE": "ENS",
    "HOR": "ENS",
    "MDM": "ENS",
    "MODEM": "ENS",
    "LR": "LR",
    "RN": "RN",
    "UDR": "RN",
    "REC": "REC",
    "DLF": "DLF",
    "EXG": "EXG",
    "DIV": "DIV",
}

BROAD_BLOC_MAP: dict[str, str] = {
    "LFI": "gauche",
    "PS-PP": "gauche",
    "PCF": "gauche",
    "EELV": "gauche",
    "NFP": "gauche",
    "EXG": "gauche",
    "ENS": "centre",
    "RE": "centre",
    "HOR": "centre",
    "MDM": "centre",
    "MODEM": "centre",
    "LR": "droite",
    "DLF": "droite",
    "DIV": "autres",
    "RN": "extrême_droite",
    "REC": "extrême_droite",
    "UDR": "extrême_droite",
}

FAMILY_BROAD_BLOC_MAP: dict[str, str] = {
    "far_left": "gauche",
    "extrême_gauche": "gauche",
    "left": "gauche",
    "gauche": "gauche",
    "gauche_radicale": "gauche",
    "centre_left": "gauche",
    "centre_gauche": "gauche",
    "green": "gauche",
    "greens": "gauche",
    "écologistes": "gauche",
    "centre": "centre",
    "centre_droit": "centre",
    "centre_right": "centre",
    "right": "droite",
    "droite": "droite",
    "gaullist_right": "droite",
    "droite_gaulliste": "droite",
    "sovereigntist_right": "droite",
    "droite_souverainiste": "droite",
    "nationalist_right": "extrême_droite",
    "droite_nationale": "extrême_droite",
    "far_right": "extrême_droite",
    "extrême_droite": "extrême_droite",
}

SECOND_ROUND_TRANSFER_MATRIX: dict[str, dict[str, float]] = {
    "gauche": {"gauche": 1.00, "centre": 0.35, "droite": 0.10, "extrême_droite": 0.02, "autres": 0.10},
    "centre": {"gauche": 0.35, "centre": 1.00, "droite": 0.25, "extrême_droite": 0.12, "autres": 0.15},
    "droite": {"gauche": 0.08, "centre": 0.35, "droite": 1.00, "extrême_droite": 0.38, "autres": 0.15},
    "extrême_droite": {"gauche": 0.03, "centre": 0.10, "droite": 0.18, "extrême_droite": 1.00, "autres": 0.12},
    "autres": {"gauche": 0.12, "centre": 0.20, "droite": 0.15, "extrême_droite": 0.15, "autres": 1.00},
}

DUEL_SPECIFIC_SECOND_ROUND_OVERRIDES: dict[frozenset[str], dict[str, dict[str, float]]] = {
    frozenset({"gauche", "extrême_droite"}): {
        "centre": {"gauche": 0.82, "extrême_droite": 0.03},
    }
}

LEGISLATIVE_BLOC_NORMALIZATION: dict[str, str] = {
    "left": "gauche",
    "gauche": "gauche",
    "centre": "centre",
    "right": "droite",
    "droite": "droite",
    "far_right": "extrême_droite",
    "extrême_droite": "extrême_droite",
    "other": "autres",
    "autres": "autres",
    "regionalist": "autres",
}

LEGISLATIVE_2024_POLL_COLUMNS = ["EXG", "NFP", "DVG", "ECO", "DVC", "ENS", "DVD", "LR", "RN"]
LEGISLATIVE_2024_POLL_TO_BLOC = {
    "EXG": "gauche",
    "NFP": "gauche",
    "DVG": "gauche",
    "ECO": "gauche",
    "DVC": "centre",
    "ENS": "centre",
    "DVD": "droite",
    "LR": "droite",
    "RN": "extrême_droite",
}

LEGISLATIVE_2024_NATIONAL_POLLSTERS = {
    "Ipsos",
    "Ifop",
    "Elabe",
    "Opinion Way",
    "Harris Interactive",
    "Cluster17",
    "Odoxa",
}


@dataclass(frozen=True)
class FirstRoundCorrectionContext:
    pollster_bias: pd.DataFrame
    temporal_bias: pd.DataFrame
    historical_errors: pd.DataFrame
    representativity_factors: pd.DataFrame
    bias_catalog: pd.DataFrame


def get_reference_dir(project_root: Path | None = None) -> Path:
    root = project_root or Path.cwd()
    return root / "data" / "reference"


def _read_reference_csv(reference_dir: Path, filename: str) -> pd.DataFrame:
    path = reference_dir / filename
    if not path.exists():
        if not reference_dir.is_absolute():
            fallback = Path(__file__).resolve().parents[3] / reference_dir / filename
            if fallback.exists():
                path = fallback
            else:
                return pd.DataFrame()
        else:
            return pd.DataFrame()
    return pd.read_csv(path)


def normalize_force_label(candidate_party: object | None, political_family: object | None) -> str:
    party = str(candidate_party).strip() if candidate_party not in (None, "", np.nan) else ""
    family = str(political_family).strip() if political_family not in (None, "", np.nan) else ""
    if party in PARTY_FORCE_MAP:
        return PARTY_FORCE_MAP[party]
    if family in {"green", "greens", "écologistes"}:
        return "EELV"
    if family in {"left", "gauche", "gauche_radicale", "centre_left", "centre_gauche"}:
        return "LFI"
    if family in {"centre", "centre_right", "centre_droit"}:
        return "ENS"
    if family in {"right", "droite", "gaullist_right", "droite_gaulliste", "sovereigntist_right", "droite_souverainiste"}:
        return "LR"
    if family in {"far_right", "nationalist_right", "droite_nationale", "extrême_droite"}:
        return "RN"
    if family in {"far_left", "extrême_gauche"}:
        return "EXG"
    return party or family or "OTHER"


def normalize_broad_bloc(candidate_party: object | None, political_family: object | None) -> str:
    party = str(candidate_party).strip() if candidate_party not in (None, "", np.nan) else ""
    family = str(political_family).strip() if political_family not in (None, "", np.nan) else ""
    if party in BROAD_BLOC_MAP:
        return BROAD_BLOC_MAP[party]
    if family in FAMILY_BROAD_BLOC_MAP:
        return FAMILY_BROAD_BLOC_MAP[family]
    return "autres"


def get_second_round_transfer_map(
    source_bloc: str,
    candidate_a_bloc: str,
    candidate_b_bloc: str,
) -> dict[str, float]:
    base = SECOND_ROUND_TRANSFER_MATRIX.get(source_bloc, SECOND_ROUND_TRANSFER_MATRIX["autres"]).copy()
    duel_key = frozenset({candidate_a_bloc, candidate_b_bloc})
    duel_overrides = DUEL_SPECIFIC_SECOND_ROUND_OVERRIDES.get(duel_key, {})
    source_override = duel_overrides.get(source_bloc)
    if source_override:
        base.update(source_override)
    return base


def compute_days_bucket(days_until_election: pd.Series) -> pd.Series:
    days = pd.to_numeric(days_until_election, errors="coerce")
    return pd.cut(
        days,
        bins=[-np.inf, 30, 90, 180, np.inf],
        labels=["0_30", "31_90", "91_180", "181_plus"],
    ).astype(str)


def load_historical_2022_polls(reference_dir: Path) -> pd.DataFrame:
    frame = _read_reference_csv(reference_dir, HISTORICAL_2022_POLLS_FILE)
    if frame.empty:
        return frame
    frame["fieldwork_end_date"] = pd.to_datetime(frame["fieldwork_end_date"], errors="coerce")
    frame["estimate_percent"] = pd.to_numeric(frame["estimate_percent"], errors="coerce")
    frame["sample_size"] = pd.to_numeric(frame["sample_size"], errors="coerce")
    frame["days_until_election"] = pd.to_numeric(frame["days_until_election"], errors="coerce")
    return frame


def load_historical_2022_results(reference_dir: Path) -> pd.DataFrame:
    frame = _read_reference_csv(reference_dir, HISTORICAL_2022_RESULTS_FILE)
    if frame.empty:
        return frame
    frame["result_percent"] = pd.to_numeric(frame["result_percent"], errors="coerce")
    return frame


def load_legislative_2024_results(reference_dir: Path) -> pd.DataFrame:
    frame = _read_reference_csv(reference_dir, HISTORICAL_2024_LEGISLATIVE_FILE)
    if frame.empty:
        return frame
    frame["percent_expressed"] = pd.to_numeric(frame["percent_expressed"], errors="coerce")
    return frame


def load_legislative_2024_seats(reference_dir: Path) -> pd.DataFrame:
    frame = _read_reference_csv(reference_dir, HISTORICAL_2024_LEGISLATIVE_SEATS_FILE)
    if frame.empty:
        return frame
    for column in ["vote_share_percent", "seats", "seat_share_percent", "vote_seat_gap"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _load_complete_2024_visual_rows(reference_dir: Path) -> pd.DataFrame:
    project_root = reference_dir.parent
    path = (
        project_root
        / "imported_wiki_zip_complete"
        / "csv_from_pdf_Liste_de_sondages_sur_les_élections_législatives_françaises_de_2024"
        / "Liste_de_sondages_sur_les_élections_législatives_françaises_de_2024_visual_rows.csv"
    )
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _parse_french_date(fragment: str) -> pd.Timestamp | None:
    cleaned = " ".join(str(fragment).replace("1er", "1").replace("er", "").split())
    month_map = {
        "janvier": 1,
        "fevrier": 2,
        "février": 2,
        "mars": 3,
        "avril": 4,
        "mai": 5,
        "juin": 6,
        "juillet": 7,
        "aout": 8,
        "août": 8,
        "septembre": 9,
        "octobre": 10,
        "novembre": 11,
        "decembre": 12,
        "décembre": 12,
    }
    match = pd.Series([cleaned]).str.extract(
        r"(?:(\d{1,2})-)?(\d{1,2})\s+([a-zéûîôàèùç]+)\s+(20\d{2})",
        flags=0,
        expand=True,
    ).iloc[0]
    if match.notna().all():
        day = int(match.iloc[1])
        month = month_map.get(str(match.iloc[2]).lower())
        year = int(match.iloc[3])
        if month is not None:
            try:
                return pd.Timestamp(year=year, month=month, day=day)
            except ValueError:
                return None
    parsed = pd.to_datetime(cleaned, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed)


def _normalize_percent(token: str) -> float | None:
    cleaned = str(token).replace("%", "").replace("<", "").replace(">", "").replace("–", "-").strip()
    if not cleaned or cleaned == "—":
        return None
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_2024_poll_rows_from_complete_zip(reference_dir: Path) -> pd.DataFrame:
    visual_rows = _load_complete_2024_visual_rows(reference_dir)
    if visual_rows.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    text_rows = visual_rows["row_text"].fillna("").astype(str).tolist()
    for index, raw_line in enumerate(text_rows):
        line = " ".join(raw_line.split())
        if not line:
            continue
        date_match = pd.Series([line]).str.extract(
            r"(\d{1,2}(?:-\d{1,2})?\s+(?:juin|mars|avril|décembre)(?:\s+202[34])?)",
            expand=False,
        ).iloc[0]
        if not isinstance(date_match, str):
            continue
        percent_tokens = pd.Series([line]).str.findall(r"(?:<\s*)?\d{1,2}(?:,\d+)?\s*%|—").iloc[0]
        if len(percent_tokens) < 7:
            continue

        source = "Source à vérifier"
        for offset in range(0, 6):
            if index - offset < 0:
                break
            source_candidate = " ".join(text_rows[index - offset].split())
            if any(name in source_candidate for name in ["Ipsos", "Ifop", "Elabe", "Opinion", "Harris", "Cluster17", "Odoxa"]):
                source = source_candidate.split("(")[0].strip()
                break

        parsed_date = _parse_french_date(f"{date_match} 2024" if "202" not in date_match else date_match)
        if parsed_date is None:
            continue

        for bloc_label, value in zip(LEGISLATIVE_2024_POLL_COLUMNS, percent_tokens[: len(LEGISLATIVE_2024_POLL_COLUMNS)]):
            normalized = _normalize_percent(value)
            if normalized is None:
                continue
            rows.append(
                {
                    "publication_date": parsed_date,
                    "polling_company": source,
                    "poll_bloc_label": bloc_label,
                    "normalized_bloc": LEGISLATIVE_2024_POLL_TO_BLOC.get(bloc_label, "autres"),
                    "estimate_percent": normalized,
                }
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.drop_duplicates().sort_values(["normalized_bloc", "publication_date", "polling_company"]).reset_index(drop=True)


def _read_legislative_2024_wiki_tables(reference_dir: Path) -> pd.DataFrame:
    candidates = [
        reference_dir.parent / LEGISLATIVE_2024_WIKI_TABLES_FILE,
        Path(__file__).resolve().parents[3] / LEGISLATIVE_2024_WIKI_TABLES_FILE,
    ]
    for path in candidates:
        if path.exists():
            return pd.read_csv(path)
    return pd.DataFrame()


def load_legislative_2024_national_polls_from_wiki_tables(reference_dir: Path) -> pd.DataFrame:
    frame = _read_legislative_2024_wiki_tables(reference_dir)
    if frame.empty or "section" not in frame.columns:
        return pd.DataFrame()

    pollster_candidates = [column for column in frame.columns if column.startswith("Sondeur | Sondeur | Sondeur | Sondeur")]
    date_candidates = [column for column in frame.columns if column.startswith("Date | Date | Date | Date")]
    if not pollster_candidates or not date_candidates:
        return pd.DataFrame()
    pollster_column = pollster_candidates[0]
    date_column = date_candidates[0]

    bloc_prefixes = {
        "gauche": ["NFP[a] |", "NFP[a] (LFI-PCF-EELV-PS) |"],
        "centre": ["ENS |", "ENS (RE-MoDem-HOR-PRV-UDI) |"],
        "droite": ["LR[b] |"],
        "extrême_droite": ["RN et alliés |"],
    }

    national = frame.loc[frame["section"] == "Sondages nationaux"].copy()
    national[pollster_column] = national[pollster_column].fillna("").astype(str).str.strip()
    national[date_column] = national[date_column].fillna("").astype(str).str.strip()
    national = national.loc[national[pollster_column].isin(LEGISLATIVE_2024_NATIONAL_POLLSTERS)].copy()
    national = national.loc[national[date_column].str.contains("2024", na=False)].copy()
    if national.empty:
        return pd.DataFrame()

    def parse_percent(series: pd.Series) -> pd.Series:
        return pd.to_numeric(
            series.astype(str).str.extract(r"(\d+(?:,\d+)?)", expand=False).str.replace(",", ".", regex=False),
            errors="coerce",
        )

    rows: list[dict[str, object]] = []
    for bloc_label, prefixes in bloc_prefixes.items():
        matching_columns = [column for column in national.columns if any(column.startswith(prefix) for prefix in prefixes)]
        if not matching_columns:
            continue
        parsed = national[matching_columns].apply(parse_percent)
        bloc_values = parsed.max(axis=1)
        sample = national.loc[bloc_values.notna(), [pollster_column, date_column]].copy()
        if sample.empty:
            continue
        sample["estimate_percent"] = bloc_values.loc[bloc_values.notna()].astype(float).to_numpy()
        sample["publication_date"] = sample[date_column].map(_parse_french_date)
        sample = sample.dropna(subset=["publication_date", "estimate_percent"])
        sample["polling_company"] = sample[pollster_column]
        sample["normalized_bloc"] = bloc_label
        rows.extend(
            sample[["publication_date", "polling_company", "normalized_bloc", "estimate_percent"]].to_dict(orient="records")
        )

    extracted = pd.DataFrame(rows)
    if extracted.empty:
        return extracted
    return extracted.drop_duplicates().sort_values(["normalized_bloc", "publication_date", "polling_company"]).reset_index(drop=True)


def load_legislative_2024_national_results_from_wiki_tables(reference_dir: Path) -> pd.DataFrame:
    frame = _read_legislative_2024_wiki_tables(reference_dir)
    if frame.empty or "section" not in frame.columns:
        return pd.DataFrame()

    pollster_candidates = [column for column in frame.columns if column.startswith("Sondeur | Sondeur | Sondeur | Sondeur")]
    date_candidates = [column for column in frame.columns if column.startswith("Date | Date | Date | Date")]
    if not pollster_candidates or not date_candidates:
        return pd.DataFrame()
    pollster_column = pollster_candidates[0]
    date_column = date_candidates[0]

    bloc_prefixes = {
        "gauche": ["NFP[a] |", "NFP[a] (LFI-PCF-EELV-PS) |"],
        "centre": ["ENS |", "ENS (RE-MoDem-HOR-PRV-UDI) |"],
        "droite": ["LR[b] |"],
        "extrême_droite": ["RN et alliés |"],
    }

    national = frame.loc[frame["section"] == "Sondages nationaux"].copy()
    national[pollster_column] = national[pollster_column].fillna("").astype(str).str.strip()
    national = national.loc[national[pollster_column] == "Résultats"].copy()
    if national.empty:
        return pd.DataFrame()

    def parse_percent(series: pd.Series) -> pd.Series:
        return pd.to_numeric(
            series.astype(str).str.extract(r"(\d+(?:,\d+)?)", expand=False).str.replace(",", ".", regex=False),
            errors="coerce",
        )

    rows: list[dict[str, object]] = []
    for bloc_label, prefixes in bloc_prefixes.items():
        matching_columns = [column for column in national.columns if any(column.startswith(prefix) for prefix in prefixes)]
        if not matching_columns:
            continue
        parsed = national[matching_columns].apply(parse_percent)
        bloc_value = parsed.max(axis=1).dropna()
        if bloc_value.empty:
            continue
        publication_date = _parse_french_date(str(national.iloc[0][date_column]))
        rows.append(
            {
                "bloc_label": bloc_label,
                "actual_result": float(bloc_value.iloc[0]),
                "publication_date": publication_date,
            }
        )

    extracted = pd.DataFrame(rows)
    if extracted.empty:
        return extracted
    return extracted.sort_values("bloc_label").reset_index(drop=True)


def compute_legislative_2024_poll_bias(reference_dir: Path) -> pd.DataFrame:
    polls = load_legislative_2024_national_polls_from_wiki_tables(reference_dir)
    if polls.empty:
        polls = _extract_2024_poll_rows_from_complete_zip(reference_dir)
    actual = load_legislative_2024_national_results_from_wiki_tables(reference_dir)
    if actual.empty:
        results = load_legislative_2024_results(reference_dir)
        actual = (
            results.loc[results["election_round"] == "first_round"]
            .assign(bloc_label=lambda df: df["bloc_label"].map(LEGISLATIVE_BLOC_NORMALIZATION).fillna(df["bloc_label"]))
            .groupby("bloc_label", dropna=False)["percent_expressed"]
            .sum()
            .rename("actual_result")
            .reset_index()
        )
    if polls.empty or actual.empty:
        return pd.DataFrame(columns=["bloc_label", "poll_mean", "actual_result", "poll_bias_2024", "n_points"])
    recent_polls = polls.loc[polls["publication_date"] >= LEGISLATIVE_2024_ELECTION_DATE - pd.Timedelta(days=14)].copy()
    if recent_polls.empty:
        recent_polls = polls.copy()
    poll_bias = (
        recent_polls.groupby("normalized_bloc", dropna=False)
        .agg(
            poll_mean=("estimate_percent", "mean"),
            n_points=("estimate_percent", "count"),
        )
        .reset_index()
        .rename(columns={"normalized_bloc": "bloc_label"})
        .merge(actual, on="bloc_label", how="left")
    )
    poll_bias["poll_bias_2024"] = poll_bias["poll_mean"] - poll_bias["actual_result"]
    return poll_bias


def load_representativity_factors(reference_dir: Path) -> pd.DataFrame:
    frame = _read_reference_csv(reference_dir, REPRESENTATIVITY_FACTORS_FILE)
    if frame.empty:
        return pd.DataFrame(
            {
                "collection_method": ["online", "mixed", "phone", "unknown"],
                "risk_multiplier": [1.15, 1.08, 0.97, 1.20],
            }
        )
    frame["risk_multiplier"] = pd.to_numeric(frame["risk_multiplier"], errors="coerce")
    return frame


def load_manual_first_round_biases(reference_dir: Path) -> pd.DataFrame:
    frame = _read_reference_csv(reference_dir, MANUAL_FIRST_ROUND_BIASES_FILE)
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "force_label",
                "structural_bias",
                "temporal_bias",
                "trajectory_bias",
                "legislative_2024_bias_override",
                "manual_total_bias",
                "notes",
            ]
        )
    for column in ["structural_bias", "temporal_bias", "trajectory_bias", "legislative_2024_bias_override"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["force_label"] = frame["force_label"].fillna("").astype(str).str.strip()
    frame["manual_total_bias"] = (
        frame["structural_bias"].fillna(0.0)
        + frame["temporal_bias"].fillna(0.0)
        + frame["trajectory_bias"].fillna(0.0)
    )
    return frame


def load_manual_second_round_bloc_overrides(reference_dir: Path) -> pd.DataFrame:
    frame = _read_reference_csv(reference_dir, MANUAL_SECOND_ROUND_BLOC_OVERRIDES_FILE)
    if frame.empty:
        return pd.DataFrame(columns=["bloc_label", "seat_projection_gap_points", "notes"])
    frame["bloc_label"] = frame["bloc_label"].fillna("").astype(str).str.strip()
    frame["seat_projection_gap_points"] = pd.to_numeric(frame["seat_projection_gap_points"], errors="coerce")
    return frame


def _compute_recent_slope(dates: pd.Series, values: pd.Series) -> float | None:
    recent = (
        pd.DataFrame(
            {
                "date": pd.to_datetime(dates, errors="coerce"),
                "value": pd.to_numeric(values, errors="coerce"),
            }
        )
        .dropna()
        .sort_values("date")
        .tail(8)
    )
    if len(recent.index) < 5 or recent["date"].nunique() < 2:
        return None
    split = max(2, len(recent.index) // 2)
    early_window = recent.iloc[:split]
    late_window = recent.iloc[-split:]
    day_span = (late_window["date"].median() - early_window["date"].median()) / pd.Timedelta(days=1)
    if not day_span or pd.isna(day_span):
        return None
    return float((late_window["value"].median() - early_window["value"].median()) / day_span)


def _compute_historical_error_momentum(group: pd.DataFrame) -> float | None:
    recent = group.dropna(subset=["days_until_election", "historical_error"]).sort_values("days_until_election").head(8)
    if len(recent.index) < 5 or recent["days_until_election"].nunique() < 2:
        return None
    split = max(2, len(recent.index) // 2)
    close_window = recent.iloc[:split]
    less_close_window = recent.iloc[-split:]
    day_span = float(less_close_window["days_until_election"].median() - close_window["days_until_election"].median())
    if not day_span or pd.isna(day_span):
        return None
    return float((close_window["historical_error"].median() - less_close_window["historical_error"].median()) / day_span)


def _weighted_error_mean(group: pd.DataFrame) -> float:
    days = pd.to_numeric(group["days_until_election"], errors="coerce").fillna(group["days_until_election"].median())
    weights = 1.0 / (1.0 + (days / 90.0).clip(lower=0.0))
    return float(np.average(group["historical_error"], weights=weights))


def _build_current_force_dynamics(current_frame: pd.DataFrame | None) -> pd.DataFrame:
    if current_frame is None or current_frame.empty:
        return pd.DataFrame(
            columns=[
                "force_label",
                "current_days_bucket",
                "current_recent_slope",
                "current_recent_mean",
                "current_poll_count",
            ]
        )

    working = current_frame.copy()
    working["publication_date"] = pd.to_datetime(working["publication_date"], errors="coerce")
    working["estimate_percent"] = pd.to_numeric(working["estimate_percent"], errors="coerce")
    working["force_label"] = working.apply(
        lambda row: normalize_force_label(row.get("candidate_party"), row.get("political_family")),
        axis=1,
    )
    working["days_until_election"] = (CURRENT_ELECTION_DATE - working["publication_date"]).dt.days
    working["days_bucket"] = compute_days_bucket(working["days_until_election"])
    working = working.dropna(subset=["force_label", "publication_date", "estimate_percent"])
    if working.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for force_label, group in working.groupby("force_label", dropna=False):
        grouped = (
            group.groupby("publication_date", dropna=False)
            .agg(estimate_percent=("estimate_percent", "mean"), days_bucket=("days_bucket", "first"))
            .reset_index()
            .sort_values("publication_date")
        )
        rows.append(
            {
                "force_label": force_label,
                "current_days_bucket": grouped["days_bucket"].dropna().iloc[-1] if grouped["days_bucket"].notna().any() else "unknown",
                "current_recent_slope": _compute_recent_slope(grouped["publication_date"], grouped["estimate_percent"]),
                "current_recent_mean": float(grouped["estimate_percent"].tail(min(5, len(grouped.index))).mean()),
                "current_poll_count": int(group["poll_id"].nunique() if "poll_id" in group.columns else len(group.index)),
            }
        )
    return pd.DataFrame(rows)


def _build_bias_catalog(historical_errors: pd.DataFrame, current_frame: pd.DataFrame | None) -> pd.DataFrame:
    if historical_errors.empty:
        return pd.DataFrame()

    current_dynamics = _build_current_force_dynamics(current_frame)
    rows: list[dict[str, object]] = []
    for force_label, group in historical_errors.groupby("force_label", dropna=False):
        force_group = group.dropna(subset=["historical_error"]).copy()
        if force_group.empty:
            rows.append({"force_label": force_label, "status": "données insuffisantes"})
            continue

        weighted_error_mean = _weighted_error_mean(force_group)
        overall_error_mean = float(force_group["historical_error"].mean())
        uncertainty = float(force_group["historical_error"].std(ddof=1) / np.sqrt(len(force_group.index))) if len(force_group.index) > 1 else np.nan
        result_percent = float(force_group["result_percent"].dropna().iloc[0]) if force_group["result_percent"].notna().any() else np.nan

        current_row = (
            current_dynamics.loc[current_dynamics["force_label"] == force_label].iloc[0]
            if not current_dynamics.empty and (current_dynamics["force_label"] == force_label).any()
            else None
        )
        current_bucket = str(current_row["current_days_bucket"]) if current_row is not None else "unknown"
        current_slope = float(current_row["current_recent_slope"]) if current_row is not None and pd.notna(current_row["current_recent_slope"]) else np.nan
        current_poll_count = int(current_row["current_poll_count"]) if current_row is not None else 0

        temporal_group = force_group.loc[force_group["days_bucket"] == current_bucket].copy()
        if temporal_group.empty:
            temporal_group = force_group.copy()
        bucket_error_mean = float(temporal_group["historical_error"].mean())

        historical_momentum = _compute_historical_error_momentum(force_group)
        trajectory_bias = np.nan
        if pd.notna(current_slope) and historical_momentum is not None:
            trajectory_bias = float(np.clip((current_slope - historical_momentum) * 21.0, -4.0, 4.0))

        structural_bias = -weighted_error_mean
        temporal_bias = -(bucket_error_mean - weighted_error_mean)
        total_bias = structural_bias + temporal_bias + (trajectory_bias if pd.notna(trajectory_bias) else 0.0)

        status = "calculé"
        if len(force_group.index) < 6:
            status = "données insuffisantes"
        elif temporal_group["historical_error"].count() < 4 or current_poll_count < 4 or pd.isna(trajectory_bias):
            status = "à vérifier"

        rows.append(
            {
                "force_label": force_label,
                "years_used": "2022",
                "n_polls_used": int(len(force_group.index)),
                "current_poll_count": current_poll_count,
                "result_percent": result_percent,
                "mean_error": overall_error_mean,
                "uncertainty": uncertainty,
                "current_days_bucket": current_bucket,
                "polls_in_matching_bucket": int(temporal_group["historical_error"].count()),
                "structural_bias": structural_bias,
                "temporal_bias": temporal_bias,
                "trajectory_bias": trajectory_bias,
                "total_bias": total_bias,
                "status": status,
            }
        )
    return pd.DataFrame(rows).sort_values("force_label").reset_index(drop=True)


def compute_first_round_correction_context(
    reference_dir: Path,
    current_frame: pd.DataFrame | None = None,
) -> FirstRoundCorrectionContext:
    polls_2022 = load_historical_2022_polls(reference_dir)
    results_2022 = load_historical_2022_results(reference_dir)
    representativity = load_representativity_factors(reference_dir)

    if polls_2022.empty or results_2022.empty:
        empty = pd.DataFrame()
        return FirstRoundCorrectionContext(empty, empty, empty, representativity, empty)

    merged = polls_2022.merge(results_2022[["force_label", "result_percent"]], on="force_label", how="left")
    merged["days_until_election"] = (FIRST_ROUND_ELECTION_DATE - merged["fieldwork_end_date"]).dt.days
    merged["days_bucket"] = compute_days_bucket(merged["days_until_election"])
    merged["historical_error"] = merged["estimate_percent"] - merged["result_percent"]

    temporal_bias = (
        merged.groupby(["force_label", "days_bucket"], dropna=False)["historical_error"]
        .mean()
        .rename("historical_error_bucket_mean")
        .reset_index()
    )
    merged = merged.merge(temporal_bias, on=["force_label", "days_bucket"], how="left")
    merged["pollster_residual_error"] = merged["historical_error"] - merged["historical_error_bucket_mean"].fillna(0.0)
    pollster_bias = (
        merged.groupby(["pollster", "force_label"], dropna=False)["pollster_residual_error"]
        .mean()
        .rename("pollster_bias")
        .reset_index()
    )
    bias_catalog = _build_bias_catalog(merged, current_frame)
    manual_biases = load_manual_first_round_biases(reference_dir)
    if not manual_biases.empty:
        if bias_catalog.empty:
            bias_catalog = manual_biases.rename(columns={"manual_total_bias": "total_bias"}).copy()
            bias_catalog["years_used"] = "2022 + manuel"
            bias_catalog["n_polls_used"] = 0
            bias_catalog["current_poll_count"] = 0
            bias_catalog["result_percent"] = np.nan
            bias_catalog["mean_error"] = np.nan
            bias_catalog["uncertainty"] = np.nan
            bias_catalog["current_days_bucket"] = "unknown"
            bias_catalog["polls_in_matching_bucket"] = 0
            bias_catalog["status"] = "à vérifier"
        else:
            bias_catalog = bias_catalog.merge(
                manual_biases[
                    [
                        "force_label",
                        "structural_bias",
                        "temporal_bias",
                        "trajectory_bias",
                        "legislative_2024_bias_override",
                        "manual_total_bias",
                        "notes",
                    ]
                ].rename(
                    columns={
                        "structural_bias": "manual_structural_bias",
                        "temporal_bias": "manual_temporal_bias",
                        "trajectory_bias": "manual_trajectory_bias",
                    }
                ),
                on="force_label",
                how="left",
            )
            manual_mask = bias_catalog["manual_total_bias"].notna()
            for auto_col, manual_col in [
                ("structural_bias", "manual_structural_bias"),
                ("temporal_bias", "manual_temporal_bias"),
                ("trajectory_bias", "manual_trajectory_bias"),
            ]:
                bias_catalog.loc[manual_mask, auto_col] = bias_catalog.loc[manual_mask, manual_col]
            bias_catalog.loc[manual_mask, "total_bias"] = bias_catalog.loc[manual_mask, "manual_total_bias"]
            bias_catalog.loc[manual_mask, "years_used"] = "2022 + manuel"
        bias_catalog["bias_source"] = np.where(
            bias_catalog["manual_total_bias"].notna(),
            "manual_override",
            "historical_2022",
        )
    elif not bias_catalog.empty:
        bias_catalog["bias_source"] = "historical_2022"
    return FirstRoundCorrectionContext(pollster_bias, temporal_bias, merged, representativity, bias_catalog)


def compute_representativity_multiplier(frame: pd.DataFrame, representativity_factors: pd.DataFrame) -> pd.Series:
    factors = representativity_factors.set_index("collection_method")["risk_multiplier"].to_dict()
    methods = frame.get("collection_method", pd.Series(index=frame.index, dtype=object)).fillna("unknown").astype(str)
    base = methods.map(lambda value: factors.get(value, factors.get("unknown", 1.15))).astype(float)
    if "sample_size" in frame.columns:
        base = base + np.where(pd.to_numeric(frame["sample_size"], errors="coerce").fillna(0) < 1200, 0.04, 0.0)
    if "quota_method" in frame.columns:
        quota = frame["quota_method"].fillna("unknown").astype(str)
        base = base + np.where(quota == "unknown", 0.04, 0.0)
    return pd.Series(base, index=frame.index, dtype=float)


def apply_first_round_historical_correction(frame: pd.DataFrame, reference_dir: Path) -> tuple[pd.DataFrame, FirstRoundCorrectionContext]:
    context = compute_first_round_correction_context(reference_dir, frame)
    if frame.empty:
        return frame.copy(), context

    working = frame.copy()
    working["force_label"] = working.apply(
        lambda row: normalize_force_label(row.get("candidate_party"), row.get("political_family")),
        axis=1,
    )
    working["days_until_election"] = (CURRENT_ELECTION_DATE - pd.to_datetime(working["publication_date"], errors="coerce")).dt.days
    working["days_bucket"] = compute_days_bucket(working["days_until_election"])
    working["representativity_multiplier"] = compute_representativity_multiplier(working, context.representativity_factors)
    working["broad_bloc"] = working.apply(
        lambda row: normalize_broad_bloc(row.get("candidate_party"), row.get("political_family")),
        axis=1,
    )

    if not context.bias_catalog.empty:
        working = working.merge(
            context.bias_catalog[
                [
                    "force_label",
                    "structural_bias",
                    "temporal_bias",
                    "trajectory_bias",
                    "total_bias",
                    "status",
                    "n_polls_used",
                    "uncertainty",
                ]
            ],
            on="force_label",
            how="left",
        )
    else:
        working["structural_bias"] = np.nan
        working["temporal_bias"] = np.nan
        working["trajectory_bias"] = np.nan
        working["total_bias"] = np.nan
        working["status"] = "données insuffisantes"
        working["n_polls_used"] = 0
        working["uncertainty"] = np.nan

    legislative_2024_bias = compute_legislative_2024_poll_bias(reference_dir)
    legislative_bias_map = (
        legislative_2024_bias.set_index("bloc_label")["poll_bias_2024"].to_dict()
        if not legislative_2024_bias.empty
        else {}
    )
    manual_legislative_2024_override = (
        load_manual_first_round_biases(reference_dir)
        .set_index("force_label")["legislative_2024_bias_override"]
        .to_dict()
    )

    working["structural_bias_component_raw"] = pd.to_numeric(working["structural_bias"], errors="coerce").fillna(0.0)
    working["temporal_bias_component_raw"] = pd.to_numeric(working["temporal_bias"], errors="coerce").fillna(0.0)
    working["trajectory_bias_component_raw"] = pd.to_numeric(working["trajectory_bias"], errors="coerce").fillna(0.0)
    working["legislative_2024_bias_component_raw"] = (
        -pd.to_numeric(working["broad_bloc"].map(legislative_bias_map), errors="coerce").fillna(0.0)
    )
    force_leg_2024_override = pd.to_numeric(working["force_label"].map(manual_legislative_2024_override), errors="coerce")
    override_mask = force_leg_2024_override.notna()
    working.loc[override_mask, "legislative_2024_bias_component_raw"] = force_leg_2024_override.loc[override_mask]
    working["has_legislative_2024_anchor"] = (
        working["broad_bloc"].isin(legislative_bias_map.keys()) | override_mask
    )
    working["historical_2022_weight"] = np.where(
        working["has_legislative_2024_anchor"],
        FIRST_ROUND_2022_BACKGROUND_WEIGHT,
        1.0,
    )
    working["legislative_2024_weight"] = np.where(
        working["has_legislative_2024_anchor"],
        FIRST_ROUND_2024_ANCHOR_WEIGHT,
        0.0,
    )
    working["structural_bias_component"] = working["structural_bias_component_raw"] * working["historical_2022_weight"]
    working["temporal_bias_component"] = working["temporal_bias_component_raw"] * working["historical_2022_weight"]
    working["trajectory_bias_component"] = working["trajectory_bias_component_raw"] * working["historical_2022_weight"]
    working["legislative_2024_bias_component"] = (
        working["legislative_2024_bias_component_raw"] * working["legislative_2024_weight"]
    )
    working["representativity_bias_component"] = 0.0
    working["historical_correction"] = (
        working["structural_bias_component"].fillna(0.0)
        + working["temporal_bias_component"].fillna(0.0)
        + working["trajectory_bias_component"].fillna(0.0)
        + working["legislative_2024_bias_component"].fillna(0.0)
    )
    working["historically_corrected_estimate"] = (
        pd.to_numeric(working["estimate_percent"], errors="coerce") + working["historical_correction"]
    ).clip(lower=0.0, upper=100.0)
    working["pollster_bias"] = working["structural_bias_component"]
    return working, context


def compute_force_snapshot(
    frame: pd.DataFrame,
    group_field: str,
    value_field: str,
    family_field: str = "political_family",
    party_field: str = "candidate_party",
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    working = frame.copy()
    working["publication_date"] = pd.to_datetime(working["publication_date"], errors="coerce")
    working = working.dropna(subset=[group_field, value_field, "publication_date"])
    if working.empty:
        return pd.DataFrame()
    latest = (
        working.sort_values(["publication_date", value_field], ascending=[False, False])
        .groupby(group_field, dropna=False)
        .head(1)
        .copy()
    )
    latest["value_display"] = latest[value_field].map(lambda value: f"{value:.1f}%" if pd.notna(value) else "n.d.")
    columns = [group_field, party_field, family_field, value_field, "value_display", "publication_date"]
    available = [column for column in columns if column in latest.columns]
    return latest[available].rename(columns={group_field: "force_name"})


def compute_second_round_legislative_benchmark(
    candidate_a_bloc: str,
    candidate_b_bloc: str,
    legislative_frame: pd.DataFrame,
) -> tuple[float, float]:
    if legislative_frame.empty:
        return 50.0, 50.0

    latest_round = legislative_frame.loc[legislative_frame["election_round"] == "second_round"].copy()
    if latest_round.empty:
        latest_round = legislative_frame.loc[legislative_frame["election_round"] == "first_round"].copy()

    share_column = "seat_share_percent" if "seat_share_percent" in latest_round.columns else "percent_expressed"
    bloc_shares = latest_round.groupby("bloc_label", dropna=False)[share_column].sum().to_dict()
    score_a = 0.0
    score_b = 0.0
    for source_bloc, share in bloc_shares.items():
        normalized_source_bloc = LEGISLATIVE_BLOC_NORMALIZATION.get(str(source_bloc), "autres")
        transfer_map = get_second_round_transfer_map(normalized_source_bloc, candidate_a_bloc, candidate_b_bloc)
        score_a += share * transfer_map.get(candidate_a_bloc, 0.0)
        score_b += share * transfer_map.get(candidate_b_bloc, 0.0)
    total = score_a + score_b
    if total <= 0:
        return 50.0, 50.0
    return score_a / total * 100.0, score_b / total * 100.0


def apply_second_round_legislative_correction(frame: pd.DataFrame, reference_dir: Path) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()

    legislative_results = load_legislative_2024_results(reference_dir)
    legislative_seats = load_legislative_2024_seats(reference_dir)
    legislative_poll_bias = compute_legislative_2024_poll_bias(reference_dir)
    manual_second_round = load_manual_second_round_bloc_overrides(reference_dir)
    working = frame.copy()
    working["broad_bloc"] = working.apply(
        lambda row: normalize_broad_bloc(row.get("candidate_party"), row.get("political_family")),
        axis=1,
    )
    benchmark_rows: list[dict[str, object]] = []
    poll_bias_map = (
        legislative_poll_bias.set_index("bloc_label")["poll_bias_2024"].to_dict()
        if not legislative_poll_bias.empty
        else {}
    )
    seat_projection_override_map = (
        manual_second_round.set_index("bloc_label")["seat_projection_gap_points"].to_dict()
        if not manual_second_round.empty
        else {}
    )
    for scenario_name, scenario_frame in working.groupby("scenario_name", dropna=False):
        scenario_candidates = (
            scenario_frame[["candidate_name", "candidate_party", "political_family", "broad_bloc"]]
            .drop_duplicates()
            .reset_index(drop=True)
        )
        if len(scenario_candidates.index) != 2:
            continue
        first = scenario_candidates.iloc[0]
        second = scenario_candidates.iloc[1]
        first_share, second_share = compute_second_round_legislative_benchmark(
            str(first["broad_bloc"]),
            str(second["broad_bloc"]),
            legislative_seats,
        )
        first_poll_bias = float(poll_bias_map.get(first["broad_bloc"], 0.0))
        second_poll_bias = float(poll_bias_map.get(second["broad_bloc"], 0.0))
        first_share -= first_poll_bias
        second_share -= second_poll_bias
        rebased_total = first_share + second_share
        if rebased_total > 0:
            first_share = first_share / rebased_total * 100.0
            second_share = second_share / rebased_total * 100.0
        first_share += float(seat_projection_override_map.get(first["broad_bloc"], 0.0))
        second_share += float(seat_projection_override_map.get(second["broad_bloc"], 0.0))
        overridden_total = first_share + second_share
        if overridden_total > 0:
            first_share = first_share / overridden_total * 100.0
            second_share = second_share / overridden_total * 100.0
        seat_premium = 0.0
        if not legislative_seats.empty:
            seat_rows = legislative_seats.loc[
                (legislative_seats["election_round"] == "second_round")
                & (legislative_seats["bloc_label"].isin([first["broad_bloc"], second["broad_bloc"]]))
            ].copy()
            if not seat_rows.empty:
                premium_map = seat_rows.set_index("bloc_label")["vote_seat_gap"].to_dict()
                first_share += float(premium_map.get(first["broad_bloc"], 0.0)) * 0.08
                second_share += float(premium_map.get(second["broad_bloc"], 0.0)) * 0.08
                total = first_share + second_share
                if total > 0:
                    first_share = first_share / total * 100.0
                    second_share = second_share / total * 100.0
                seat_premium = float(abs(premium_map.get(first["broad_bloc"], 0.0)) + abs(premium_map.get(second["broad_bloc"], 0.0)))
        benchmark_rows.extend(
            [
                {
                    "scenario_name": scenario_name,
                    "candidate_name": first["candidate_name"],
                    "legislative_benchmark": first_share,
                    "legislative_seat_premium": seat_premium,
                    "legislative_poll_bias": first_poll_bias,
                },
                {
                    "scenario_name": scenario_name,
                    "candidate_name": second["candidate_name"],
                    "legislative_benchmark": second_share,
                    "legislative_seat_premium": seat_premium,
                    "legislative_poll_bias": second_poll_bias,
                },
            ]
        )

    benchmarks = pd.DataFrame(benchmark_rows)
    if benchmarks.empty:
        working["legislative_benchmark"] = np.nan
        working["legislative_seat_premium"] = np.nan
        working["legislative_poll_bias"] = np.nan
        working["legislatively_corrected_estimate"] = working["estimate_percent"]
        return working

    working = working.merge(benchmarks, on=["scenario_name", "candidate_name"], how="left")
    working["legislative_benchmark"] = pd.to_numeric(working["legislative_benchmark"], errors="coerce")
    working["legislative_seat_premium"] = pd.to_numeric(working["legislative_seat_premium"], errors="coerce")
    working["legislative_poll_bias"] = pd.to_numeric(working["legislative_poll_bias"], errors="coerce")
    raw_estimate = pd.to_numeric(working["estimate_percent"], errors="coerce")
    working["legislatively_corrected_estimate"] = (
        0.62 * raw_estimate
        + 0.38 * working["legislative_benchmark"].fillna(raw_estimate)
    ).clip(lower=0.0, upper=100.0)
    return working
