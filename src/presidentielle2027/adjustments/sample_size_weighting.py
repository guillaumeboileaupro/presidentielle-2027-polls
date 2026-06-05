from __future__ import annotations

import numpy as np
import pandas as pd


def compute_sample_size_weights(sample_sizes: pd.Series) -> pd.Series:
    values = pd.to_numeric(sample_sizes, errors="coerce").fillna(0)
    return pd.Series(np.sqrt(values.clip(lower=0)), index=sample_sizes.index, dtype="float64")

