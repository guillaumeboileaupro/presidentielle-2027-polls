from __future__ import annotations

import pandas as pd


def apply_turnout_adjustment(frame: pd.DataFrame, abstention_penalty: float = 0.1) -> pd.DataFrame:
    adjusted = frame.copy()
    abstention = pd.to_numeric(adjusted.get("abstention_estimate"), errors="coerce").fillna(0)
    adjusted["adjusted_estimate_turnout"] = adjusted["estimate_percent"] * (1 - abstention_penalty * abstention / 100)
    return adjusted

