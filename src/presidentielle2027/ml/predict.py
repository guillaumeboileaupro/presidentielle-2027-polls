from __future__ import annotations

import pickle
from datetime import date
from pathlib import Path

import pandas as pd

from presidentielle2027.config import get_settings
from presidentielle2027.ml.features import FEATURE_COLUMNS, build_feature_frame


def predict_poll_bias(model_path: Path, frame: pd.DataFrame, election_date: date | None = None) -> pd.Series:
    with model_path.open("rb") as handle:
        pipeline = pickle.load(handle)
    features = build_feature_frame(frame, election_date or date.fromisoformat(get_settings().default_election_date))
    predictions = pipeline.predict(features[FEATURE_COLUMNS])
    return pd.Series(predictions, index=frame.index, name="predicted_bias")

