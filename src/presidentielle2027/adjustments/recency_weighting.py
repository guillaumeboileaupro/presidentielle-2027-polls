from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd


def compute_recency_weights(
    publication_dates: pd.Series,
    reference_date: date | None = None,
    lambda_: float = 0.03,
) -> pd.Series:
    ref = pd.Timestamp(reference_date or pd.Timestamp.utcnow().date())
    dates = pd.to_datetime(publication_dates, errors="coerce")
    age_in_days = (ref - dates).dt.days.clip(lower=0)
    return pd.Series(np.exp(-lambda_ * age_in_days), index=publication_dates.index, dtype="float64")

