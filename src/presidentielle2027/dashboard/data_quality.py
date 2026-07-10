from __future__ import annotations

import pandas as pd


SCENARIO_COLUMNS = ["poll_id", "round", "scenario_name"]


def repair_scaled_first_round_scenarios(frame: pd.DataFrame) -> pd.DataFrame:
    """Repair first-round scenarios accidentally divided by ten during raw parsing.

    A complete first-round scenario should total roughly 100 percentage points. The
    previous raw-table heuristic could divide a valid scenario by ten when its
    extracted total exceeded 110, producing totals around 10 and values such as
    17 -> 1.7 or 32 -> 3.2. Only this unmistakable tenfold signature is repaired.
    """
    if frame.empty or not set(SCENARIO_COLUMNS + ["estimate_percent"]).issubset(frame.columns):
        return frame.copy()

    repaired = frame.copy()
    repaired["estimate_percent"] = pd.to_numeric(repaired["estimate_percent"], errors="coerce")

    first_round = repaired["round"].astype(str).eq("first_round")
    for _, indexes in repaired.loc[first_round].groupby(SCENARIO_COLUMNS, dropna=False).groups.items():
        indexes = list(indexes)
        values = repaired.loc[indexes, "estimate_percent"]
        total = values.sum(min_count=1)
        maximum = values.max()
        if pd.notna(total) and pd.notna(maximum) and 8.0 <= float(total) <= 12.0 and float(maximum) <= 5.0:
            repaired.loc[indexes, "estimate_percent"] = values * 10.0

    return repaired
